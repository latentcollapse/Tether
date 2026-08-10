#!/usr/bin/env python3
"""
Tether Konsole delivery ACK+retry loop (v2.1).

Why this exists
---------------
Konsole's D-Bus `sendText` is a fire-and-forget datagram: it returns success the
instant the bytes are handed to the PTY, with no knowledge of whether the agent's
TUI ingested them into its prompt buffer. Whether an injection lands depends on
what the TUI is doing at the microsecond the bytes arrive — idle (lands), mid
screen-redraw (the next frame clobbers the input line), or mid escape-sequence
parse (misreads the bytes). Agents print status output during long runs, so the
redraw collisions come and go. The result is the maddening "works sometimes" flake.

You cannot make a single unacknowledged injection 100% reliable — you're racing an
application you don't control and getting no receipt. So instead of perfecting the
transport, we build delivery semantics on top of it: at-least-once delivery with
acknowledgment + retry. The unreliable datagram (UDP) gets TCP-like guarantees.

How it works
------------
- On send, `konsole_deliver` injects once AND registers the message in
  tether_konsole_pending (see SQLiteRuntime.konsole_pending_add).
- This loop scans for due pending deliveries on an interval. For each:
    * If the recipient has read the handle (a row in tether_reads, written when it
      runs tether_receive) -> mark 'acked'. Done.
    * Else if attempts are exhausted -> mark 'exhausted' and stop nudging (the
      message still sits unread in the DB; the agent's next inbox poll or the
      dashboard surfaces it — exhaustion is "we stopped poking", not data loss).
    * Else re-inject the same short handle-line and reschedule.
- Idempotent: the handle is content-addressed and reading it marks it done, so a
  duplicate nudge after a read is a harmless no-op.

The loop runs as a daemon thread inside the dashboard server process (the same
process that owns the D-Bus binding and serves /api/konsole/deliver).
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

SCAN_INTERVAL_SECONDS = 5    # how often to check for due deliveries
SETTLE_SECONDS = 0.6         # wait after an inject before reading the screen back


def process_due(rt) -> dict:
    """Run one pass over due pending deliveries. Returns a small stats dict.

    Terminator is DELIVERY CONFIRMATION, not blind retry. For each pending row, in order:
      - acked    : the agent read the handle (tether_reads) — best outcome, stop.
      - unbound  : the agent's tab is gone — stop (nothing to deliver to).
      - delivered: the handle is visible on the agent's screen — it landed, stop. (This is
                   the key fix: a delivered message stops the loop even if the agent can't
                   ACK because it's down / rate-limited / mid-task — no more futile spam.)
      - else     : the inject genuinely didn't land (lost a redraw race) → re-inject, settle,
                   and re-confirm. Only if it STILL hasn't landed does it count an attempt.
    max_attempts is now just a safety backstop against a pathological never-landing inject
    (e.g. a broken transport), not the primary stop mechanism.
    """
    from tether import konsole_driver
    from tether.delivery import _live_konsole_target

    stats = {"acked": 0, "delivered": 0, "unbound": 0, "reinjected": 0, "exhausted": 0}
    for row in rt.konsole_pending_due():
        handle, agent = row["handle"], row["agent"]

        if rt.is_read(handle, agent):
            rt.konsole_pending_resolve(handle, agent, "acked")
            rt.delivery_record(handle, agent, "delivered", "read_receipt", confirmed=True)
            stats["acked"] += 1
            continue

        target = _live_konsole_target(rt, agent)
        if not target:
            # A closed/restarted tab is temporary, not a terminal delivery
            # result.  Keep the durable notice eligible for a future live tab.
            rt.konsole_pending_defer(handle, agent, row["interval_seconds"])
            rt.delivery_record(
                handle, agent, "queued", "database", detail="recipient has no live Konsole target"
            )
            stats["unbound"] += 1
            continue
        svc, sess = target["service"], target["session"]
        original_pid = row.get("target_pid")
        if original_pid and str(target.get("pid") or "") != str(original_pid):
            # The recipient process died or restarted.  Never deliver an old
            # prompt write into a replacement process; the durable inbox is the
            # recovery path for this message.
            rt.konsole_pending_resolve(handle, agent, "target_changed")
            rt.delivery_record(
                handle,
                agent,
                "queued",
                "database",
                detail="original recipient process exited; automatic injection stopped",
            )
            stats["unbound"] += 1
            continue

        # Enter is authorized only by the current composer being wholly owned
        # by this exact Tether notice.  Visibility in transcript or a status
        # panel is never enough.
        if konsole_driver.composer_contains(svc, sess, handle):
            state = konsole_driver.prompt_state(svc, sess)
            if state != "empty" or not konsole_driver.composer_is_tether_owned(svc, sess, handle):
                rt.delivery_record(
                    handle,
                    agent,
                    "delivered",
                    "konsole",
                    prompt_state=state,
                    confirmed=True,
                    held=True,
                    detail="notice held in current prompt; no automatic Enter",
                )
                rt.konsole_pending_defer(handle, agent, row["interval_seconds"])
                continue
            if not konsole_driver.session_agent_is_live(
                svc, sess, agent, expected_pid=original_pid
            ):
                rt.konsole_pending_resolve(handle, agent, "target_changed")
                stats["unbound"] += 1
                continue
            submitted = konsole_driver.send_line(svc, sess, "\r", submit=False)
            time.sleep(SETTLE_SECONDS)
            # An empty prompt turning nonempty/busy is the only safe indication
            # that the TUI accepted the queued Tether follow-up.  If it remains
            # empty we leave it pending rather than duplicate or force it.
            if submitted and konsole_driver.prompt_state(svc, sess) != "empty":
                rt.konsole_pending_resolve(handle, agent, "delivered")
                rt.delivery_record(
                    handle, agent, "delivered", "konsole", prompt_state="empty",
                    submitted=True, confirmed=True,
                )
                stats["delivered"] += 1
            else:
                rt.konsole_pending_defer(handle, agent, row["interval_seconds"])
            continue

        # A stale copy elsewhere in the viewport grants no special treatment.
        # If the real composer is empty, a normal prompt-safe reinjection is the
        # correct recovery; if it is busy/draft/unknown, inject_tether_notice
        # holds without Enter.
        _, state = konsole_driver.inject_tether_notice(
            svc,
            sess,
            row["line"],
            expected_agent=agent,
            expected_pid=original_pid,
        )
        time.sleep(SETTLE_SECONDS)
        if state == "empty":
            rt.konsole_pending_resolve(handle, agent, "delivered")
            rt.delivery_record(
                handle, agent, "delivered", "konsole", prompt_state=state,
                submitted=True, confirmed=konsole_driver.screen_contains(svc, sess, handle),
            )
            stats["delivered"] += 1
            continue

        # The agent was busy, a human draft was present, or the transport did
        # not land the line.  Retain the durable handle and retry after the
        # normal interval; neither case is a transport failure.
        if state in {"busy", "draft", "unknown"}:
            confirmed = konsole_driver.composer_contains(svc, sess, handle)
            rt.delivery_record(
                handle,
                agent,
                "delivered" if confirmed else "notified",
                "konsole",
                prompt_state=state,
                confirmed=confirmed,
                held=True,
            )
            rt.konsole_pending_defer(handle, agent, row["interval_seconds"])
            continue

        # Still didn't land — count an attempt; give up only at the safety backstop.
        rt.konsole_pending_mark_attempt(handle, agent, row["interval_seconds"])
        if row["attempts"] + 1 >= row["max_attempts"]:
            rt.konsole_pending_resolve(handle, agent, "exhausted"); stats["exhausted"] += 1
            logger.warning("konsole delivery never landed after %d injects (transport issue?)",
                           row["attempts"] + 1, extra={"agent": agent, "handle": handle})
        else:
            stats["reinjected"] += 1
    return stats


def _loop(db_path: str, stop_event: threading.Event) -> None:
    from tether.sqlite_runtime import SQLiteRuntime
    while not stop_event.is_set():
        stop_event.wait(SCAN_INTERVAL_SECONDS)
        if stop_event.is_set():
            break
        try:
            rt = SQLiteRuntime(db_path=db_path)
            try:
                process_due(rt)
            finally:
                rt.close()
        except Exception:
            # A retry-loop crash must never take down the dashboard server.
            logger.exception("konsole retry loop pass failed")


def start(db_path: str) -> threading.Event:
    """Start the retry loop as a daemon thread. Returns the stop Event so the caller
    can shut it down cleanly."""
    stop_event = threading.Event()
    thread = threading.Thread(target=_loop, args=(db_path, stop_event), daemon=True)
    thread.start()
    logger.info("konsole delivery retry loop started (scan=%ds)", SCAN_INTERVAL_SECONDS)
    return stop_event
