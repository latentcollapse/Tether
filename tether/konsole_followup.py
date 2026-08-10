"""Finish a safely queued Tether wake once a Konsole agent becomes idle.

Direct CLI delivery normally exits immediately.  When Cursor is already working,
Konsole accepts the notice into its follow-up queue but cannot accept its Enter
key yet.  This tiny detached helper waits for the *same* Tether-owned handle to
remain visible alongside a positively identified empty composer, then submits
it.  It never presses Enter over a human draft or an unknown terminal state.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable

from tether import konsole_driver


def record_result(*, db_path: str, agent: str, handle: str, result: str) -> None:
    """Persist the terminal outcome without making terminal visibility an ACK.

    The direct CLI route has no dashboard retry thread.  A busy Cursor delivery
    therefore needs the same durable pending row as dashboard delivery before a
    detached waiter is allowed to own Enter.  Only a successful submission ends
    that row; every other outcome remains recoverable for a future retry worker.
    """
    from tether.sqlite_runtime import SQLiteRuntime

    runtime = SQLiteRuntime(db_path=db_path)
    try:
        if result in {"submitted", "acknowledged", "target_changed"}:
            terminal_status = "target_changed" if result == "target_changed" else "delivered"
            runtime.konsole_pending_resolve(handle, agent, terminal_status)
            runtime.delivery_record(
                handle,
                agent,
                "queued" if result == "target_changed" else "delivered",
                "read_receipt" if result == "acknowledged" else "konsole",
                submitted=result == "submitted",
                confirmed=result != "target_changed",
                detail=(
                    "original recipient process exited; automatic injection stopped"
                    if result == "target_changed" else None
                ),
            )
        else:
            runtime.konsole_pending_defer(handle, agent, interval_seconds=30)
    finally:
        runtime.close()


def submit_when_idle(
    service: str,
    session: str,
    handle: str,
    *,
    timeout_seconds: float = 600.0,
    poll_seconds: float = 1.0,
    submit_settle_seconds: float = 0.25,
    initial_visibility_grace_seconds: float = 10.0,
    reinject_after_seconds: float = 30.0,
    expected_line: str | None = None,
    expected_agent: str,
    expected_pid: str | int | None = None,
    is_acknowledged: Callable[[], bool] | None = None,
    monotonic=time.monotonic,
    sleep=time.sleep,
) -> str:
    """Submit an existing visible Tether follow-up only at a safe idle prompt."""
    started = monotonic()
    deadline = started + timeout_seconds
    visible_deadline = started + min(initial_visibility_grace_seconds, timeout_seconds)
    seen_visible = False
    last_seen_at = None
    idle_observations = 0
    while True:
        now = monotonic()
        if now >= deadline:
            break
        # The Konsole session is only an address.  The live foreground process
        # is the identity, and it must remain the original agent/PID throughout
        # this detached wait.  A shell or restarted TUI inheriting the tab must
        # never receive bytes or Enter from an old delivery.
        if not konsole_driver.session_agent_is_live(
            service, session, expected_agent, expected_pid=expected_pid
        ):
            return "target_changed"
        # A real ``tether resolve`` is stronger evidence than terminal state.
        # Stop immediately once the recipient has read the exact handle, so a
        # completed follow-up never lingers as a stale retry candidate.
        if is_acknowledged is not None and is_acknowledged():
            return "acknowledged"
        # Never manufacture a second copy: this helper owns only the already
        # visible direct-delivery notice bearing its exact durable handle.
        if not konsole_driver.composer_contains(service, session, handle):
            # D-Bus sendText returns before Cursor has necessarily repainted its
            # follow-up panel. Give a new delivery a brief chance to appear;
            # after that, absence is conclusive and we still never type a copy.
            state = konsole_driver.prompt_state(service, session)
            may_reinject = (
                expected_line is not None
                and state == "empty"
                and now >= visible_deadline
                and (last_seen_at is None or now - last_seen_at >= reinject_after_seconds)
            )
            if may_reinject:
                ok, injected_state = konsole_driver.inject_tether_notice(
                    service,
                    session,
                    expected_line,
                    expected_agent=expected_agent,
                    expected_pid=expected_pid,
                )
                if not ok:
                    return "send_failed"
                if injected_state == "empty":
                    return "submitted"
                sleep(poll_seconds)
                continue
            if now >= visible_deadline and not seen_visible and expected_line is None:
                return "not_visible"
            sleep(poll_seconds)
            continue
        seen_visible = True
        last_seen_at = now
        state = konsole_driver.prompt_state(service, session)
        if state != "empty" or not konsole_driver.composer_is_tether_owned(service, session, handle):
            # A Cursor redraw can transiently expose an empty-looking composer
            # immediately before its activity line appears.  Never let that
            # one frame queue a follow-up inside a still-running turn.
            idle_observations = 0
            sleep(poll_seconds)
            continue
        idle_observations += 1
        if idle_observations >= 2:
            # qdbus acknowledges text injection, not the TUI's interpretation
            # of Enter.  Confirm that the exact Tether-only composer stopped
            # being empty before declaring success.  Some Cursor builds accept
            # LF where CR is merely inserted into the follow-up buffer, so use
            # one safe fallback while we still own this exact notice.
            if not konsole_driver.session_agent_is_live(
                service, session, expected_agent, expected_pid=expected_pid
            ):
                return "target_changed"
            if not konsole_driver.send_line(service, session, "\r", submit=False):
                return "send_failed"
            sleep(submit_settle_seconds)
            after_cr = konsole_driver.prompt_state(service, session)
            if after_cr != "empty":
                return "submitted"
            if not konsole_driver.composer_contains(service, session, handle):
                return "submitted"
            if not konsole_driver.session_agent_is_live(
                service, session, expected_agent, expected_pid=expected_pid
            ):
                return "target_changed"
            if not konsole_driver.send_line(service, session, "\n", submit=False):
                return "send_failed"
            sleep(submit_settle_seconds)
            after_lf = konsole_driver.prompt_state(service, session)
            if after_lf != "empty" or not konsole_driver.composer_contains(service, session, handle):
                return "submitted"
            return "not_accepted"
        # Require a second positive idle observation.  This adds one small
        # polling interval but closes the redraw race above.
        sleep(poll_seconds)
    return "timed_out"


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit one queued Tether Konsole follow-up when safe")
    parser.add_argument("--service", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--handle", required=True)
    parser.add_argument("--agent", help="recipient identity for durable direct delivery")
    parser.add_argument("--db", help="SQLite authority used by the originating send")
    parser.add_argument("--pid", help="original live foreground process id")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    runtime = None
    is_acknowledged = None
    expected_line = None
    if args.db and args.agent:
        from tether.sqlite_runtime import SQLiteRuntime

        runtime = SQLiteRuntime(db_path=args.db)
        is_acknowledged = lambda: runtime.is_read(args.handle, args.agent)
        pending = runtime.konsole_pending_get(args.handle, args.agent)
        expected_line = pending.get("line") if pending else None
    try:
        result = submit_when_idle(
            args.service,
            args.session,
            args.handle,
            timeout_seconds=args.timeout,
            is_acknowledged=is_acknowledged,
            expected_line=expected_line,
            expected_agent=args.agent or "",
            expected_pid=args.pid,
        )
    finally:
        if runtime is not None:
            runtime.close()
    if args.db and args.agent:
        record_result(db_path=args.db, agent=args.agent, handle=args.handle, result=result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
