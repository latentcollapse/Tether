#!/usr/bin/env python3
"""
Tether ping daemon — universal desktop notification delivery.

On POST, delivers notifications via:
  1. notify-send (Linux desktop popup) — works for any app, no tmux needed
  2. ~/.tether_notify — file pickup via PROMPT_COMMAND in bashrc
  3. /tmp/tether-ping-{agent}.txt — buffer file for observability

No tmux. No pane detection. No idle polling. Works with Claude Code,
Codex CLI, Qwen Code, Gemini CLI, OpenClaw, or any other agent on the machine.

Usage: python3 ping_daemon.py --agent <name> --port <port>
Example: python3 ping_daemon.py --agent claude --port 7703
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


def is_enabled(agent: str) -> bool:
    return os.path.exists(f"/tmp/tether-ping-{agent}.enabled")


def desktop_notify(title: str, body: str) -> None:
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(
                ["notify-send", "-a", "Tether", "-t", "8000", title, body],
                check=False, timeout=3,
            )
        elif system == "Darwin":
            script = f'display notification "{body}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=3)
        elif system == "Windows":
            # PowerShell toast — works on Win10+
            ps = (
                f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;'
                f'$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);'
                f'$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}")) | Out-Null;'
                f'$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{body}")) | Out-Null;'
                f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Tether").Show([Windows.UI.Notifications.ToastNotification]::new($t));'
            )
            subprocess.run(["powershell", "-Command", ps], check=False, timeout=5)
    except Exception:
        pass


def file_notify(agent: str, notification: str) -> None:
    # ~/.tether_notify — picked up by PROMPT_COMMAND in bashrc at next shell prompt
    try:
        notify_path = os.path.expanduser("~/.tether_notify")
        with open(notify_path, "w") as f:
            f.write(notification + "\n")
    except Exception:
        pass
    # /tmp buffer for observability / debugging
    try:
        with open(f"/tmp/tether-ping-{agent}.txt", "w") as f:
            f.write(notification + "\n")
    except Exception:
        pass


def deliver(agent: str, notification: str) -> None:
    if not is_enabled(agent):
        return
    desktop_notify("Tether", notification)
    file_notify(agent, notification)


class PingHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, agent=None, **kwargs):
        self.agent = agent
        super().__init__(*args, **kwargs)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            sender = data.get("from", "unknown")
            handle = data.get("handle", "")
            notification = f"[Tether] From agent: {sender}  Handle: '{handle}'"
            threading.Thread(
                target=deliver,
                args=(self.agent, notification),
                daemon=True,
            ).start()
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Tether ping daemon")
    parser.add_argument("--agent", required=True, help="Agent name (e.g. claude)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    args = parser.parse_args()

    def handler_factory(*a, **kw):
        return PingHandler(*a, agent=args.agent, **kw)

    server = HTTPServer(("localhost", args.port), handler_factory)
    print(f"Tether ping daemon [{args.agent}] on http://localhost:{args.port}")
    print(f'Register: tether_register_ping(agent="{args.agent}", url="http://localhost:{args.port}")')
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
