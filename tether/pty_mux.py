#!/usr/bin/env python3
"""
Tether PTY multiplexer — runs an agent inside a pseudo-terminal that Tether owns.

This is the no-tmux replacement for prompt-box injection. Instead of scraping a
tmux pane and using send-keys, Tether *is* the parent of the agent process: it
owns the agent's stdin/stdout via a PTY, passes your keystrokes through
transparently, and — when a tmail lands — types the resolved instruction into
the agent's input and hits enter. Wake-on-notification, fire-once, no tmux.

Boot order:
  1. Start Tether (dashboard + this multiplexer host).
  2. Launch each teammate inside its wrapper:
       tether mux --agent codex -- codex
       tether mux --agent gemini -- gemini-cli
  3. Talk to them normally. When Claude sends Codex a tmail, it lands in
     Codex's input and autofires — you never relay the handle.

Injection waits for the output stream to go quiet (the agent is idle / at a
prompt) before typing, so it won't stomp mid-generation. Tune with --quiet-ms.

If stdin is not a TTY (headless / daemonized), the wrapper runs without
keystroke passthrough — still spawns the agent and injects tmails. Useful for
agents launched by the dashboard Connect button.
"""
import argparse
import fcntl
import json
import logging
import os
import pty
import select
import signal
import struct
import sys
import termios
import threading
import time
import tty
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from tether.ping_daemon import _db_path, _heartbeat_loop, IDLE_PATTERNS
from tether.agent_server import WakeQueue, _resolve_handle_text


def _collapse_ws(text: str) -> str:
    """Flatten an instruction to a single line so it submits as one turn."""
    return " ".join(text.split())


def _get_winsize(fd: int) -> tuple[int, int]:
    try:
        data = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _, _ = struct.unpack("HHHH", data)
        return rows, cols
    except Exception:
        return 24, 80


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except Exception:
        pass


class PtyMux:
    def __init__(self, agent: str, command: list[str], quiet_ms: int):
        self.agent = agent
        self.command = command
        self.quiet_secs = max(0.1, quiet_ms / 1000.0)
        self.master_fd = -1
        self.child_pid = -1
        self.queue = WakeQueue()
        self.last_output = time.time()
        self._out_lock = threading.Lock()
        self._tail = bytearray()
        self.stop = threading.Event()

    # ── injection ────────────────────────────────────────────────────────────

    def _mark_output(self, data: bytes) -> None:
        with self._out_lock:
            self.last_output = time.time()
            self._tail.extend(data)
            if len(self._tail) > 4096:
                del self._tail[:-4096]

    def _quiet_for(self) -> float:
        with self._out_lock:
            return time.time() - self.last_output

    def _looks_idle(self) -> bool:
        """Quiet stream is the primary gate; idle patterns let us inject sooner."""
        if self._quiet_for() < self.quiet_secs:
            return False
        with self._out_lock:
            tail = self._tail[-400:].decode("utf-8", "replace")
        last_lines = [ln for ln in tail.splitlines() if ln.strip()][-3:]
        for ln in last_lines:
            for pat in IDLE_PATTERNS:
                if pat.search(ln.strip()):
                    return True
        # No explicit prompt match, but the stream has been quiet long enough.
        return True

    def _format_injection(self, item: dict) -> str:
        text = _collapse_ws(item.get("text") or "")
        sender = item.get("from", "unknown")
        handle = item.get("handle", "")
        if text:
            return f"[Tether from {sender}] {text} (handle: {handle})"
        return f"[Tether from {sender}] new message — resolve {handle}"

    def _inject(self, line: str) -> None:
        if self.master_fd < 0:
            return
        try:
            os.write(self.master_fd, line.encode("utf-8", "replace"))
            time.sleep(0.3)
            os.write(self.master_fd, b"\r")
        except OSError:
            pass

    def _injector_loop(self) -> None:
        while not self.stop.is_set():
            items = self.queue.drain()
            if not items:
                self.stop.wait(0.25)
                continue
            for item in items:
                # Wait for the agent to be idle before typing, bounded so a
                # chatty agent doesn't block delivery forever.
                deadline = time.time() + 120
                while not self.stop.is_set() and not self._looks_idle():
                    if time.time() > deadline:
                        break
                    self.stop.wait(0.2)
                self._inject(self._format_injection(item))

    # ── HTTP receiver (Tether push target) ────────────────────────────────────

    def serve_receiver(self, port: int) -> int:
        mux = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.split("?")[0] == "/health":
                    self._json(200, {"agent": mux.agent, "ok": True,
                                     "queue_depth": mux.queue.depth(),
                                     "quiet_secs": mux.quiet_secs})
                else:
                    self._json(404, {"error": "not_found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {}
                handle = payload.get("handle", "")
                payload["text"] = payload.get("text") or _resolve_handle_text(handle)
                mux.queue.push(payload)
                self._json(200, {"ok": True, "queued": True})

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("localhost", port), Handler)
        bound = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self._server = server
        return bound

    def register_endpoint(self, port: int) -> None:
        try:
            import sqlite3
            db = _db_path()
            os.makedirs(os.path.dirname(db), exist_ok=True)
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tether_ping_endpoints "
                "(agent TEXT PRIMARY KEY, url TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1)"
            )
            conn.execute(
                "INSERT INTO tether_ping_endpoints (agent, url, enabled) VALUES (?, ?, 1) "
                "ON CONFLICT(agent) DO UPDATE SET url=excluded.url, enabled=1",
                (self.agent, f"http://localhost:{port}"),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Surface this — a silent failure here means the agent never registers its wake
            # endpoint and silently never receives pings.
            logging.getLogger(__name__).warning("ping endpoint registration failed for %s: %s", self.agent, e)

    # ── child + io loop ────────────────────────────────────────────────────────

    def spawn_child(self) -> None:
        master_fd, slave_fd = pty.openpty()
        rows, cols = _get_winsize(sys.stdin.fileno()) if sys.stdin.isatty() else (40, 120)
        _set_winsize(slave_fd, rows, cols)

        pid = os.fork()
        if pid == 0:
            # Child: new session, make the slave our controlling terminal
            os.setsid()
            try:
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            except Exception:
                pass
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            os.close(master_fd)
            try:
                os.execvp(self.command[0], self.command)
            except Exception as e:
                sys.stderr.write(f"tether mux: failed to exec {self.command!r}: {e}\n")
                os._exit(127)
        # Parent
        os.close(slave_fd)
        self.master_fd = master_fd
        self.child_pid = pid

    def run(self, port: int) -> int:
        bound = self.serve_receiver(port)
        self.register_endpoint(bound)

        stop_hb = threading.Event()
        hb = threading.Thread(target=_heartbeat_loop, args=(self.agent, bound, stop_hb), daemon=True)
        hb.start()

        self.spawn_child()
        threading.Thread(target=self._injector_loop, daemon=True).start()

        is_tty = sys.stdin.isatty()
        old_attrs = None
        if is_tty:
            old_attrs = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())

            def _winch(sig, frame):
                r, c = _get_winsize(sys.stdin.fileno())
                _set_winsize(self.master_fd, r, c)
            signal.signal(signal.SIGWINCH, _winch)
            _winch(None, None)

        print(f"\r\nTether mux [{self.agent}] on http://localhost:{bound} — agent: {' '.join(self.command)}\r")
        sys.stdout.flush()

        try:
            self._io_loop(is_tty)
        finally:
            self.stop.set()
            stop_hb.set()
            if old_attrs is not None:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attrs)
            try:
                self._server.shutdown()
            except Exception:
                pass

        # Reap child, return its exit status
        try:
            _, status = os.waitpid(self.child_pid, 0)
            return os.waitstatus_to_exitcode(status)
        except Exception:
            return 0

    def _io_loop(self, is_tty: bool) -> None:
        stdin_fd = sys.stdin.fileno()
        watch = [self.master_fd] + ([stdin_fd] if is_tty else [])
        while True:
            try:
                readable, _, _ = select.select(watch, [], [], 0.5)
            except (OSError, select.error):
                break
            if self.master_fd in readable:
                try:
                    data = os.read(self.master_fd, 65536)
                except OSError:
                    break  # child exited (EIO on master)
                if not data:
                    break
                self._mark_output(data)
                os.write(sys.stdout.fileno(), data)
            if is_tty and stdin_fd in readable:
                try:
                    data = os.read(stdin_fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                os.write(self.master_fd, data)
            # Detect child exit even when no output is pending
            try:
                pid, _ = os.waitpid(self.child_pid, os.WNOHANG)
                if pid == self.child_pid:
                    break
            except ChildProcessError:
                break


def main():
    parser = argparse.ArgumentParser(
        description="Run an agent inside a Tether-owned PTY (no-tmux delivery)")
    parser.add_argument("--agent", required=True, help="Agent identity for Tether")
    parser.add_argument("--port", type=int, default=0, help="0 = auto-assign")
    parser.add_argument("--quiet-ms", type=int, default=800,
                        help="Stream must be quiet this long before injecting")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="-- followed by the agent command to run")
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("provide the agent command after --, e.g. tether mux --agent codex -- codex")

    mux = PtyMux(args.agent, command, args.quiet_ms)
    sys.exit(mux.run(args.port))


if __name__ == "__main__":
    main()
