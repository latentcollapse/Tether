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

SCAN_INTERVAL_SECONDS = 5  # how often to check for due deliveries


def _reinject(rt, agent: str, line: str) -> bool:
    """Re-inject a handle-line using the agent's CURRENT binding (not a stored one,
    so a rebound tab is followed). Returns whether the D-Bus call succeeded."""
    from tether import konsole_driver
    binding = rt.konsole_binding(agent)
    if not binding:
        return False
    return konsole_driver.send_line(binding["service"], binding["session"], line)


def process_due(rt) -> dict:
    """Run one pass over due pending deliveries. Returns a small stats dict.
    Separated from the loop so it is unit-testable and callable on demand."""
    stats = {"acked": 0, "reinjected": 0, "exhausted": 0, "failed": 0}
    for row in rt.konsole_pending_due():
        handle, agent = row["handle"], row["agent"]
        # ACK check first — the recipient may have read it between attempts.
        if rt.is_read(handle, agent):
            rt.konsole_pending_resolve(handle, agent, "acked")
            stats["acked"] += 1
            continue
        if row["attempts"] >= row["max_attempts"]:
            rt.konsole_pending_resolve(handle, agent, "exhausted")
            stats["exhausted"] += 1
            logger.warning("konsole delivery exhausted after %d attempts",
                           row["attempts"], extra={"agent": agent, "handle": handle})
            continue
        ok = _reinject(rt, agent, row["line"])
        # Bump the attempt counter regardless of D-Bus return: the call is
        # fire-and-forget so "ok" only means the bytes were accepted, not landed.
        # The ACK (a read) is the only real success signal; keep nudging until then.
        rt.konsole_pending_mark_attempt(handle, agent, row["interval_seconds"])
        if ok:
            stats["reinjected"] += 1
        else:
            stats["failed"] += 1
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
