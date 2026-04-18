#!/usr/bin/env python3
"""
Tether ping daemon — hybrid notification delivery.

Delivery strategy per agent type:
  - DESKTOP_NOTIFY_AGENTS (e.g. claude): notify-send desktop popup +
    ~/.tether_notify for PROMPT_COMMAND pickup. Never injects into terminal —
    Claude Code input cannot be interrupted safely.
  - All other agents: tmux send-keys injection after idle-prompt detection.
    tmux is the fallback for CLI agents (Codex, Gemini, Qwen) that don't
    expose an HTTP API. OpenClaw agents should register an HTTP endpoint
    in their Tether skill instead (see T-053).

Usage: python3 ping_daemon.py --agent <name> --pane <tmux_pane_id> --port <port>
       python3 ping_daemon.py --agent claude --port 7703   (no --pane needed)
"""
import argparse
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# These agents get desktop notifications only — never tmux injection.
DESKTOP_NOTIFY_AGENTS = {"claude"}

IDLE_PATTERNS = [
    re.compile(r'\$\s*$'),                   # bash/zsh prompt
    re.compile(r'>\s*$'),                    # Qwen Code / Gemini idle prompt
    re.compile(r'\u276f\s*$'),              # Claude Code ❯ prompt
    re.compile(r'\u25c7\s*$'),              # Codex CLI ◇ idle prompt
    re.compile(r'Waiting for your input'),   # Claude Code idle text
    re.compile(r'^\?\s*$'),                  # Claude Code ? prompt
    re.compile(r'Ready'),                    # Codex CLI "◇  Ready" state
]

IDLE_POLL_INTERVAL = 2   # seconds
IDLE_MAX_WAIT = 30        # seconds — inject anyway after this


def is_enabled(agent: str) -> bool:
    return os.path.exists(f"/tmp/tether-ping-{agent}.enabled")


# ── Desktop notification path (Claude) ────────────────────────────────────────

def desktop_notify(notification: str) -> None:
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(
                ["notify-send", "-a", "Tether", "-t", "8000", "Tether", notification],
                check=False, timeout=3,
            )
        elif system == "Darwin":
            script = f'display notification "{notification}" with title "Tether"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=3)
        elif system == "Windows":
            ps = (
                '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;'
                '$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);'
                f'$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("Tether")) | Out-Null;'
                f'$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{notification}")) | Out-Null;'
                '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Tether").Show([Windows.UI.Notifications.ToastNotification]::new($t));'
            )
            subprocess.run(["powershell", "-Command", ps], check=False, timeout=5)
    except Exception:
        pass
    # Also write ~/.tether_notify for PROMPT_COMMAND pickup in bashrc
    try:
        with open(os.path.expanduser("~/.tether_notify"), "w") as f:
            f.write(notification + "\n")
    except Exception:
        pass


# ── tmux injection path (Codex, Gemini, Qwen, other CLI agents) ───────────────

def pane_is_idle(pane: str) -> bool:
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", pane, "-p"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if not lines:
            return False
        for line in reversed(lines[-5:]):
            stripped = line.strip()
            if not stripped:
                continue
            for pat in IDLE_PATTERNS:
                if pat.search(stripped):
                    return True
        # NOTE: do NOT treat a blank last line as idle — that fires mid-typing.
        return False
    except Exception:
        return False


def resolve_pane(agent: str, fallback_pane: str) -> str:
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}|#{pane_current_command}|#{pane_title}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return fallback_pane
        heuristics = {
            "qwen":   [re.compile(r"Qwen")],
            "gemini": [re.compile(r"✦"), re.compile(r"gemini")],
            "codex":  [re.compile(r"Codex"), re.compile(r"◇"), re.compile(r"Ready")],
            "kilo":   [re.compile(r"Kilo")],
        }
        patterns = heuristics.get(agent.lower(), [])
        for line in result.stdout.strip().split("\n"):
            parts = line.split("|")
            if len(parts) < 3:
                continue
            pane_id, command, title = parts[0], parts[1], parts[2]
            if command.lower() == agent.lower():
                return pane_id
            for pat in patterns:
                if pat.search(title) or pat.search(command):
                    return pane_id
        return fallback_pane
    except Exception:
        return fallback_pane


def inject_when_idle(fallback_pane: str, notification: str, agent: str) -> None:
    if not is_enabled(agent):
        return
    pane = resolve_pane(agent, fallback_pane)
    deadline = time.time() + IDLE_MAX_WAIT
    while time.time() < deadline:
        if pane_is_idle(pane):
            break
        time.sleep(IDLE_POLL_INTERVAL)
    try:
        subprocess.run(["tmux", "send-keys", "-t", pane, notification], check=False)
        time.sleep(0.5)
        subprocess.run(["tmux", "send-keys", "-t", pane, "C-m"], check=False)
    except Exception:
        pass


# ── HTTP handler ───────────────────────────────────────────────────────────────

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
            handle = data.get("handle", "")
            notification = f"[Tether] From agent: {sender}  Handle: '{handle}'"

            # Buffer file for observability
            try:
                with open(f"/tmp/tether-ping-{self.agent}.txt", "w") as f:
                    f.write(notification + "\n")
            except Exception:
                pass

            if self.agent.lower() in DESKTOP_NOTIFY_AGENTS:
                thread = threading.Thread(target=desktop_notify, args=(notification,), daemon=True)
            else:
                thread = threading.Thread(
                    target=inject_when_idle,
                    args=(self.pane or "", notification, self.agent),
                    daemon=True,
                )
            thread.start()
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Tether ping daemon")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--pane", default="", help="tmux pane ID (not needed for desktop-notify agents)")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    if args.agent.lower() not in DESKTOP_NOTIFY_AGENTS and not args.pane:
        print(f"WARNING: --pane not set for {args.agent}. tmux injection will use dynamic pane lookup only.")

    def handler_factory(*a, **kw):
        return PingHandler(*a, agent=args.agent, pane=args.pane, **kw)

    server = HTTPServer(("localhost", args.port), handler_factory)
    mode = "desktop notify" if args.agent.lower() in DESKTOP_NOTIFY_AGENTS else f"tmux inject (pane {args.pane or 'dynamic'})"
    print(f"Tether ping daemon [{args.agent}] on http://localhost:{args.port} — {mode}")
    print(f'Register: tether_register_ping(agent="{args.agent}", url="http://localhost:{args.port}")')
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
