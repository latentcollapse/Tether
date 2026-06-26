#!/usr/bin/env python3
"""
Tether process reaping — kill orphaned delivery daemons before a fresh start.

The problem this solves: Tether spawns background delivery processes (ping_daemons,
agent_servers, the dashboard, the http_server, mcp_servers) with subprocess.Popen.
Those children DETACH — closing the launching terminal tab does not kill them. So a
"restart" that just closes tabs leaves every prior daemon alive as an orphan, and the
next launch stacks a fresh set on top. Over many restarts you get N copies of every
daemon, all racing over the same ping-endpoint rows — the source of erratic delivery.

The fix: reap before respawn. `reap()` finds every live Tether-owned background process
(by command-line marker), excludes the caller's own process tree, SIGTERMs them, waits,
and SIGKILLs any stragglers. Call it at the top of `tether serve` so every launch
starts from a clean slate, and expose it as `python -m tether reap` for manual use.

Linux-only (scans /proc). That matches the deployment.
"""
import os
import signal
import time

# Command-line markers identifying a Tether-owned DELIVERY/dashboard background process.
# These are the things that sprawl across restarts. Kept specific so we never match an
# unrelated python process or a shell that merely mentions "tether".
#
# NEVER reap the MCP servers (tether/mcp_server.py): those are agent-OWNED stdio
# transports — each agent's client spawns one to call tether_receive/tether_send, and
# they do NOT respawn mid-session. Reaping one closes that agent's tool transport
# ("Transport closed"), which is the opposite of what we want. They are not delivery
# sprawl; they belong to the agents, not the dashboard.
REAP_MARKERS = (
    "tether/ping_daemon.py", "tether.ping_daemon",
    "tether.agent_server", "tether/agent_server",
    "tether.http_server", "tether/http_server",
    "from tether.__main__ import main", "tether.__main__",
    "-m tether ",  # `python -m tether serve` style dashboard launches
)

# Hard exclusions — process markers that must NEVER be reaped even if matched above.
REAP_NEVER = (
    "mcp_server",  # agent-owned MCP stdio transport (see note above)
)


def _cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""


def find_orphans(exclude_pids=()) -> list[tuple[int, str]]:
    """Every live Tether-owned background process, minus the caller's own tree."""
    me = os.getpid()
    exclude = set(exclude_pids) | {me, os.getppid()}
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid in exclude:
            continue
        cmd = _cmdline(pid)
        if not cmd or "python" not in cmd:
            continue  # only python processes — never a shell/grep mentioning tether
        if any(n in cmd for n in REAP_NEVER):
            continue  # agent-owned transports (MCP) are never sprawl — never kill them
        if any(m in cmd for m in REAP_MARKERS):
            found.append((pid, cmd))
    return found


def reap(dry_run: bool = False, exclude_pids=(), grace_seconds: float = 2.0):
    """Reap orphaned Tether daemons. Returns (victims, killed) where each is a list of
    (pid, cmdline). In dry_run mode nothing is killed and `killed` is empty."""
    victims = find_orphans(exclude_pids)
    if dry_run or not victims:
        return victims, []
    for pid, _ in victims:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(grace_seconds)
    killed = []
    for pid, cmd in victims:
        try:
            os.kill(pid, 0)            # still alive after SIGTERM?
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass                        # exited cleanly on SIGTERM
        killed.append((pid, cmd))
    return victims, killed


def _short(cmd: str, width: int = 90) -> str:
    return cmd if len(cmd) <= width else cmd[:width - 1] + "…"


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Reap orphaned Tether delivery daemons")
    parser.add_argument("--dry-run", action="store_true", help="list what would be killed, kill nothing")
    args = parser.parse_args(argv)

    victims, killed = reap(dry_run=args.dry_run)
    if not victims:
        print("No orphaned Tether processes found — already clean.")
        return
    verb = "Would reap" if args.dry_run else "Reaped"
    print(f"{verb} {len(victims)} orphaned Tether process(es):")
    for pid, cmd in victims:
        print(f"  pid {pid:>7}  {_short(cmd)}")
    if not args.dry_run:
        print(f"\n{len(killed)} process(es) signalled. Run with --dry-run to verify the slate is clean.")


if __name__ == "__main__":
    main()
