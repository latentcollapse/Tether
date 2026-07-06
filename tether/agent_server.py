#!/usr/bin/env python3
"""
Tether agent server — the canonical "agent-as-service" wake receiver.

This is the no-tmux delivery model. Instead of Tether puppeting a terminal,
each agent owns an HTTP socket. Tether's send path POSTs the tmail metadata
to that socket (via tether_ping_endpoints + _send_message_with_ping), and the
agent's own runtime pulls the message on its next loop cycle — out of band,
no prompt-box injection.

Delivery is push, fire-once — never a poll loop. A tmail lands, the receiver
resolves it to the instruction and wakes the agent a single time.

Endpoints
  POST /            Receive a tmail ping from Tether. Resolves the handle and
                    wakes the agent once (wake command and/or injection).
  GET  /pending     Non-blocking inspection / optional pull of buffered tmails.
  GET  /health      Receiver status + buffer depth.

Wake actions (how the agent is actually woken on a tmail)
  --wake "CMD"      Run a shell command on each tmail. The instruction text is
                    passed on stdin and in $TETHER_TEXT. Use this to feed a
                    wrapped CLI or trigger a fresh one-shot invocation.
  --inject          Write the instruction into the agent's input and autofire
                    via the tmux/desktop path (reuses ping_daemon).

Presence: registers the endpoint + heartbeats every 5s so the dashboard graph
shows the agent online and routes resolve. Shares the dashboard DB via TETHER_DB.

Usage:
  python3 -m tether.agent_server --agent gemini [--port 0] [--wake "CMD"] [--inject]
"""
import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from tether.ping_daemon import (
    _db_path,
    _heartbeat_loop,
    deliver_desktop,
    inject_when_idle,
)


def _resolve_handle_text(handle: str) -> str:
    """Best-effort: resolve a tmail handle to its instruction text.

    This is what lets an agent act on the *content* of a message without a
    human ever relaying the handle — the north star. Failures are silent;
    the agent still gets the handle and can resolve it itself.
    """
    if not handle:
        return ""
    try:
        from tether.sqlite_runtime import SQLiteRuntime
        rt = SQLiteRuntime(db_path=_db_path())
        try:
            value = rt.resolve(handle)
        finally:
            rt.close()
        if isinstance(value, dict):
            return str(value.get("text") or value.get("content") or "")
        return str(value) if value is not None else ""
    except Exception:
        return ""


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class WakeQueue:
    """Thread-safe buffer of tmails awaiting injection.

    Serializes delivery so concurrent tmails don't collide while an inject is
    waiting for the agent to go idle. Not a poll target — delivery is push.
    """

    def __init__(self, maxlen: int = 200):
        self._items: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._total_received = 0

    def push(self, item: dict) -> None:
        with self._lock:
            self._items.append(item)
            self._total_received += 1

    def drain(self) -> list[dict]:
        with self._lock:
            items = list(self._items)
            self._items.clear()
            return items

    def depth(self) -> int:
        with self._lock:
            return len(self._items)

    def total(self) -> int:
        with self._lock:
            return self._total_received


def _run_wake_command(cmd: str, notification: str, payload: dict) -> None:
    """Fire the agent's wake command, passing the tmail on stdin and env."""
    try:
        env = dict(os.environ)
        env["TETHER_NOTIFICATION"] = notification
        env["TETHER_FROM"] = str(payload.get("from", ""))
        env["TETHER_SUBJECT"] = str(payload.get("subject", ""))
        env["TETHER_HANDLE"] = str(payload.get("handle", ""))
        env["TETHER_TEXT"] = str(payload.get("text", ""))
        subprocess.Popen(
            cmd, shell=True, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).stdin.write(notification.encode() + b"\n")
    except Exception:
        pass  # a failed wake command must never crash the receiver


class WakeHandler(BaseHTTPRequestHandler):
    agent = None
    queue: WakeQueue = None
    wake_cmd = None
    inject = False
    delivery_mode = "desktop"
    state = None  # shared dict for inject path

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._json(200, {
                "agent": self.agent,
                "ok": True,
                "queue_depth": self.queue.depth(),
                "total_received": self.queue.total(),
                "wake": "command" if self.wake_cmd else ("inject" if self.inject else "pull"),
            })
        elif path == "/pending":
            # Non-blocking inspection / optional pull. Not a poll loop — just
            # lets you see what's buffered if an inject is waiting for idle.
            self._json(200, {"messages": self.queue.drain()})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
        sender = payload.get("from", "unknown")
        subject = payload.get("subject", "")
        handle = payload.get("handle", "")
        if subject:
            notification = f"[Tether] {sender}: {subject}  Handle: '{handle}'"
        else:
            notification = f"[Tether] From agent: {sender}  Handle: '{handle}'"

        # Resolve the handle to the actual instruction so the agent acts on
        # content, not a handle to chase. This is the north star mechanism.
        text = payload.get("text") or _resolve_handle_text(handle)

        item = {
            "from": sender,
            "subject": subject,
            "handle": handle,
            "text": text,
            "notification": notification,
            "received_at": _now_iso(),
        }
        self.queue.push(item)

        # Buffer file for observability (parity with ping_daemon)
        try:
            with open(f"/tmp/tether-agent-{self.agent}.txt", "w") as f:
                f.write(notification + "\n")
        except Exception:
            pass

        # Fire wake command for SDK/wrapped agents. Pass the resolved text so
        # the agent begins executing on the instruction directly.
        if self.wake_cmd:
            wake_payload = dict(payload)
            wake_payload["text"] = text
            threading.Thread(
                target=_run_wake_command,
                args=(self.wake_cmd, notification, wake_payload),
                daemon=True,
            ).start()

        # Legacy fallback: tmux/desktop injection for terminal REPLs
        if self.inject:
            if self.delivery_mode == "desktop":
                threading.Thread(
                    target=deliver_desktop,
                    args=(notification, self.state, "agent_server inject fallback"),
                    daemon=True,
                ).start()
            else:
                threading.Thread(
                    target=inject_when_idle,
                    args=(notification, self.agent, self.state),
                    daemon=True,
                ).start()

        self._json(200, {"ok": True, "queued": True})

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Tether agent-as-service wake receiver")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--port", type=int, default=0, help="0 = auto-assign a free port")
    parser.add_argument("--wake", default=None, help="Shell command to run on each tmail")
    parser.add_argument("--inject", action="store_true", help="Also deliver via tmux/desktop (legacy fallback)")
    parser.add_argument("--delivery-mode", choices=("desktop", "tmux"), default="desktop",
                        help="Injection path when --inject is set")
    args = parser.parse_args()

    queue = WakeQueue()
    inject_state = {"lock": threading.Lock()}

    WakeHandler.agent = args.agent
    WakeHandler.queue = queue
    WakeHandler.wake_cmd = args.wake
    WakeHandler.inject = args.inject
    WakeHandler.delivery_mode = args.delivery_mode
    WakeHandler.state = inject_state

    # Threaded so a blocking /wait long-poll never freezes incoming tmails.
    server = ThreadingHTTPServer(("localhost", args.port), WakeHandler)
    port = server.server_port
    url = f"http://localhost:{port}"

    # Register endpoint + start heartbeat against the shared DB
    try:
        import sqlite3
        db = _db_path()
        os.makedirs(os.path.dirname(db), exist_ok=True)
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tether_ping_endpoints "
            "(agent TEXT PRIMARY KEY, url TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1)"
        )
        # Konsole-bound agents deliver via the dashboard's /api/konsole/deliver
        # (D-Bus injection + ACK/retry — the reliable, acknowledged path). Do NOT
        # clobber that routing: if this agent has a konsole binding, leave its ping
        # URL alone and let the konsole path win. Only register self as the ping
        # target for agents with no konsole binding (SDK/tmux/desktop agents).
        konsole_bound = False
        try:
            row = conn.execute(
                "SELECT 1 FROM tether_konsole_bindings WHERE agent=?", (args.agent,)
            ).fetchone()
            konsole_bound = row is not None
        except sqlite3.OperationalError:
            konsole_bound = False  # bindings table not created yet -> no binding
        if konsole_bound:
            print(f"[agent_server] {args.agent} is konsole-bound; leaving ping URL "
                  f"on the konsole D-Bus delivery path (not registering {url})", flush=True)
        else:
            conn.execute(
                "INSERT INTO tether_ping_endpoints (agent, url, enabled) VALUES (?, ?, 1) "
                "ON CONFLICT(agent) DO UPDATE SET url=excluded.url, enabled=1",
                (args.agent, url),
            )
            conn.commit()
        conn.close()
    except Exception as e:
        # Surface this — a silent failure here means the agent never registers its wake
        # endpoint and silently never receives pings ("why didn't my agent get the message").
        logging.getLogger(__name__).warning("ping endpoint registration failed for %s: %s", args.agent, e)

    stop_event = threading.Event()
    hb = threading.Thread(target=_heartbeat_loop, args=(args.agent, port, stop_event), daemon=True)
    hb.start()

    def _shutdown(sig, frame):
        stop_event.set()
        hb.join(timeout=6)
        server.shutdown()
    signal.signal(signal.SIGTERM, _shutdown)

    wake_desc = "command" if args.wake else ("tmux/desktop inject" if args.inject else "buffer (/pending)")
    print(f"Tether agent server [{args.agent}] on {url} — wake: {wake_desc}")
    print("Endpoint registered. Delivery is push, fire-once on each tmail.")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_event.set()
        hb.join(timeout=6)
        server.shutdown()


if __name__ == "__main__":
    main()
