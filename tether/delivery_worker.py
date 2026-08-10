"""Single-owner, prompt-safe Tether delivery dispatcher."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

POLL_SECONDS = 1.0


def delivery_authority_path() -> str:
    """Return the only database allowed to address live terminals.

    ``TETHER_DB`` intentionally does not broaden this boundary: tests and
    one-off tools commonly point it at temporary databases.  Operators who
    deliberately maintain a different live authority must opt in explicitly
    with ``TETHER_DELIVERY_DB``.
    """
    explicit = os.environ.get("TETHER_DELIVERY_DB")
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return os.path.abspath(os.path.join(data_home, "tether", "postoffice.db"))


def is_delivery_authority(db_path: str) -> bool:
    return os.path.abspath(os.path.expanduser(db_path)) == delivery_authority_path()


def _unit_name(db_path: str) -> str:
    digest = hashlib.sha256(os.path.abspath(db_path).encode()).hexdigest()[:12]
    return f"tether-delivery-{digest}"


def _lock_path(db_path: str) -> str:
    return os.path.abspath(db_path) + ".delivery.lock"


def ensure_started(db_path: str) -> None:
    """Ensure the one dispatcher for this database is running."""
    db_path = os.path.abspath(db_path)
    if not is_delivery_authority(db_path):
        return
    command = [sys.executable, "-m", "tether.delivery_worker", "--db", db_path]
    unit = _unit_name(db_path)
    try:
        active = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", unit],
            check=False,
            timeout=2,
        )
        if active.returncode == 0:
            return
        started = subprocess.run(
            [
                "systemd-run", "--user", "--quiet", "--collect",
                f"--unit={unit}", f"--working-directory={Path(__file__).resolve().parents[1]}",
                *command,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
        if started.returncode == 0:
            return
    except (OSError, subprocess.SubprocessError):
        pass

    # Non-systemd environments still get the same singleton semantics because
    # every worker must hold the database-specific flock for its lifetime.
    subprocess.Popen(
        command,
        cwd=str(Path(__file__).resolve().parents[1]),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def process_once(runtime) -> dict[str, int]:
    """Attempt at most one pending handle per recipient."""
    from tether import konsole_driver
    from tether.delivery import _live_konsole_target, notice_line

    stats = {"delivered": 0, "waiting": 0, "missing": 0}
    if runtime.delivery_is_paused():
        return stats

    for row in runtime.konsole_pending_due():
        # Recheck the global kill switch between recipients, not merely per tick.
        if runtime.delivery_is_paused():
            break
        handle, agent = row["handle"], row["agent"]
        target = _live_konsole_target(runtime, agent)
        if target is None:
            stats["missing"] += 1
            continue
        line = notice_line(to_agent=agent, from_agent="", subject="", handle=handle)
        ok, state = konsole_driver.inject_tether_notice(
            target["service"],
            target["session"],
            line,
            expected_agent=agent,
            expected_pid=target.get("pid"),
        )
        if ok and state == "empty":
            runtime.konsole_pending_resolve(handle, agent, "delivered")
            runtime.delivery_record(
                handle, agent, "delivered", "konsole",
                prompt_state="empty", submitted=True, confirmed=True,
            )
            stats["delivered"] += 1
        else:
            stats["waiting"] += 1
    return stats


def run(db_path: str, poll_seconds: float = POLL_SECONDS) -> int:
    from tether.sqlite_runtime import SQLiteRuntime

    if not is_delivery_authority(db_path):
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    lock_file = open(_lock_path(db_path), "a+", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0

    while True:
        runtime = SQLiteRuntime(db_path=db_path)
        try:
            process_once(runtime)
        finally:
            runtime.close()
        time.sleep(poll_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tether internal delivery dispatcher")
    parser.add_argument("--db", required=True)
    parser.add_argument("--poll", type=float, default=POLL_SECONDS)
    args = parser.parse_args(argv)
    return run(args.db, args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
