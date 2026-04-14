#!/usr/bin/env python3
"""
Tether ping daemon — capture-pane guard version.

On POST, writes notification to a buffer file, polls tmux capture-pane
every 2s to detect an idle prompt, then injects only when safe.

Usage: python3 ping_daemon.py --agent <name> --pane <tmux_pane_id> --port <port>
Example: python3 ping_daemon.py --agent qwen --pane %5 --port 7701
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

IDLE_PATTERNS = [
    re.compile(r'\$\s*$'),                    # bash/zsh prompt
    re.compile(r'>\s*$'),                     # Qwen Code / Gemini idle prompt
    re.compile(r'Waiting for your input'),     # Claude Code idle text
    re.compile(r'^\?\s*$'),                   # Claude Code ? prompt
]

IDLE_POLL_INTERVAL = 2  # seconds
IDLE_MAX_WAIT = 30       # seconds — inject anyway after this


def pane_is_idle(pane: str) -> bool:
    """Check if the tmux pane is at an idle prompt."""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", pane, "-p"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if not lines:
            return False
        # Check last few non-empty lines
        for line in reversed(lines[-5:]):
            stripped = line.strip()
            if not stripped:
                continue
            for pat in IDLE_PATTERNS:
                if pat.search(stripped):
                    return True
        # Fallback: if the last line is empty, pane is likely idle
        if lines[-1].strip() == "":
            return True
        return False
    except (subprocess.TimeoutExpired, Exception):
        return False


def is_enabled(agent: str) -> bool:
    """Check if pings are enabled for this agent (flag file exists)."""
    return os.path.exists(f"/tmp/tether-ping-{agent}.enabled")


def inject_when_idle(pane: str, notification: str, agent: str, timeout: int = IDLE_MAX_WAIT):
    """Wait for idle prompt, then inject notification. Only fires if enabled."""
    if not is_enabled(agent):
        return  # Pings disabled — drop silently

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            # Capture twice with a gap — if output hasn't changed, pane is settled
            r1 = subprocess.run(
                ["tmux", "capture-pane", "-t", pane, "-p"],
                capture_output=True, text=True, timeout=5,
            )
            time.sleep(0.5)
            r2 = subprocess.run(
                ["tmux", "capture-pane", "-t", pane, "-p"],
                capture_output=True, text=True, timeout=5,
            )
            if r1.stdout == r2.stdout:
                break  # Pane settled
        except Exception:
            break
        time.sleep(IDLE_POLL_INTERVAL)

    # Inject the command, wait a beat, then submit
    # C-m is Ctrl+M (raw Enter) which works more reliably than "Enter" key
    try:
        # Type the text
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, notification],
            check=False,
        )
        time.sleep(0.5)  # Let the CLI process the input
        # Submit with C-m
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "C-m"],
            check=False,
        )
    except Exception:
        pass


class PingHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, agent=None, pane=None, **kwargs):
        self.agent = agent
        self.pane = pane
        super().__init__(*args, **kwargs)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            sender = data.get("from", "unknown")
            subject = data.get("subject", "no subject")
            handle = data.get("handle", "")
            # Shell-safe notification: plain text, no # or ! that could trigger
            # bash history expansion or comment processing. Single quotes around
            # handle protect against shell interpretation of special chars like &.
            notification = f"[Tether] From agent: {sender}  Handle: '{handle}'"

            # Write to buffer file for observability
            buf_path = f"/tmp/tether-ping-{self.agent}.txt"
            with open(buf_path, "w") as f:
                f.write(notification)

            # Inject in background thread so HTTP handler returns fast
            thread = threading.Thread(
                target=inject_when_idle,
                args=(self.pane, notification, self.agent),
                daemon=True,
            )
            thread.start()
        except (json.JSONDecodeError, Exception):
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence request logs


def main():
    parser = argparse.ArgumentParser(description="Tether ping daemon")
    parser.add_argument("--agent", required=True, help="Agent name (e.g. qwen)")
    parser.add_argument("--pane", required=True, help="Tmux pane ID (e.g. %%5)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    args = parser.parse_args()

    def handler_factory(*a, **kw):
        return PingHandler(*a, agent=args.agent, pane=args.pane, **kw)

    server = HTTPServer(("localhost", args.port), handler_factory)
    print(f"Ping daemon for {args.agent} listening on http://localhost:{args.port} (pane {args.pane})")
    print(f'Register with: tether_register_ping(agent="{args.agent}", url="http://localhost:{args.port}")')
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
