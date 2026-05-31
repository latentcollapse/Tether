#!/usr/bin/env python3
"""
Tether ping daemon — hybrid notification delivery.

Delivery strategy:
  - auto: desktop notify for configured agents, tmux injection for everyone else
  - desktop: force desktop notifications only
  - tmux: force tmux send-keys injection after idle-prompt detection

Desktop mode writes notify-send plus ~/.tether_notify for PROMPT_COMMAND pickup.
tmux is the fallback for CLI agents (Codex, Gemini, Qwen, Claude Code) that don't
expose an HTTP API. OpenClaw agents should register an HTTP endpoint in their
Tether skill instead (see T-053).

Usage: python3 ping_daemon.py --agent <name> --port <port> [--delivery-mode auto|desktop|tmux]
"""
import argparse
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

DEFAULT_DESKTOP_NOTIFY_AGENTS = {"openclaw"}

PERSISTENT_PINS_PATH = os.path.expanduser("~/.config/tether/pane_pins.json")


def load_persistent_pins() -> dict[str, str]:
    try:
        with open(PERSISTENT_PINS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k.lower(): v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_persistent_pin(agent: str, pane: str) -> None:
    os.makedirs(os.path.dirname(PERSISTENT_PINS_PATH), exist_ok=True)
    pins = load_persistent_pins()
    pins[agent.lower()] = pane
    with open(PERSISTENT_PINS_PATH, "w", encoding="utf-8") as f:
        json.dump(pins, f, indent=2)
        f.write("\n")

IDLE_PATTERNS = [
    re.compile(r'\$\s*$'),                   # bash/zsh prompt
    re.compile(r'>\s*$'),                    # Qwen Code / Gemini idle prompt
    re.compile(r'\u276f\s*$'),              # Claude Code ❯ prompt
    re.compile(r'\u25c7\s*$'),              # Codex CLI ◇ idle prompt
    re.compile(r'\u203a\s*$'),              # Codex CLI › input prompt
    re.compile(r'Waiting for your input'),   # Claude Code idle text (legacy)
    re.compile(r'bypass permissions'),       # Claude Code active session toolbar
    re.compile(r'auto-compact'),             # Claude Code session status bar
    re.compile(r'esc to interrupt'),         # Claude Code interrupt hint
    re.compile(r'^\?\s*$'),                  # Claude Code ? prompt
    re.compile(r'Ready'),                    # Codex CLI "◇  Ready" state
    re.compile(r'gpt-'),                     # Codex CLI status line
    re.compile(r'Type your message'),        # Codex CLI input prompt
]

AGENT_PATTERNS = {
    "codex": [
        re.compile(r'gpt-', re.IGNORECASE),
        re.compile(r'\u203a'),
        re.compile(r'codex', re.IGNORECASE),
        re.compile(r'\u25c7'),
        re.compile(r'Ready', re.IGNORECASE),
    ],
    "gemini": [
        re.compile(r'gemini', re.IGNORECASE),
        re.compile(r'\u2726'),
        re.compile(r'\u25c7'),
    ],
    "qwen": [
        re.compile(r'qwen', re.IGNORECASE),
    ],
    "kilo": [
        re.compile(r'kilo', re.IGNORECASE),
    ],
    "deepseek": [
        re.compile(r'deepseek', re.IGNORECASE),
        re.compile(r'hermes', re.IGNORECASE),
    ],
}

IDLE_POLL_INTERVAL = 0.5  # seconds
IDLE_MAX_WAIT = 5         # seconds — inject anyway after this
logger = logging.getLogger(__name__)


def is_enabled(agent: str) -> bool:
    return os.path.exists(f"/tmp/tether-ping-{agent}.enabled")


def desktop_notify_agents() -> set[str]:
    raw = os.environ.get("TETHER_PING_DESKTOP_AGENTS")
    if raw is None:
        return set(DEFAULT_DESKTOP_NOTIFY_AGENTS)
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def uses_desktop_notify(agent: str, delivery_mode: str) -> bool:
    if delivery_mode == "desktop":
        return True
    if delivery_mode == "tmux":
        return False
    return agent.lower() in desktop_notify_agents()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def update_state(state: dict, **fields) -> None:
    with state["lock"]:
        state.update(fields)


# ── Desktop notification path ────────────────────────────────────────────────

def write_prompt_fallback(notification: str) -> bool:
    """Persist a prompt pickup file as the last local notification fallback."""
    try:
        with open(os.path.expanduser("~/.tether_notify"), "w", encoding="utf-8") as f:
            f.write(notification + "\n")
        return True
    except OSError:
        logger.exception("failed to write prompt fallback")
        return False


def desktop_notify(notification: str) -> bool:
    """Attempt a desktop notification; return whether the desktop path succeeded."""
    system = platform.system()
    try:
        if system == "Linux":
            result = subprocess.run(
                ["notify-send", "-a", "Tether", "-t", "8000", "Tether", notification],
                check=False, timeout=3,
            )
            return result.returncode == 0
        elif system == "Darwin":
            script = f'display notification "{notification}" with title "Tether"'
            result = subprocess.run(["osascript", "-e", script], check=False, timeout=3)
            return result.returncode == 0
        elif system == "Windows":
            ps = (
                '[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;'
                '$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);'
                f'$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("Tether")) | Out-Null;'
                f'$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{notification}")) | Out-Null;'
                '[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Tether").Show([Windows.UI.Notifications.ToastNotification]::new($t));'
            )
            result = subprocess.run(["powershell", "-Command", ps], check=False, timeout=5)
            return result.returncode == 0
        return False
    except OSError:
        logger.exception("desktop notify failed")
        return False


def deliver_desktop(notification: str, state: dict, reason: str) -> bool:
    """Deliver a ping through the desktop fallback chain."""
    logger.warning("using desktop fallback", extra={"reason": reason})
    delivered = desktop_notify(notification)
    update_state(state, last_delivery_path="desktop" if delivered else "prompt_file")
    if delivered:
        return True
    file_written = write_prompt_fallback(notification)
    if file_written:
        logger.warning("desktop notify failed; wrote prompt fallback", extra={"reason": reason})
    else:
        logger.error("all ping delivery paths failed", extra={"reason": reason})
    return file_written


# ── tmux injection path (Codex, Gemini, Qwen, other CLI agents) ───────────────

def capture_pane_lines(pane: str) -> list[str]:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", pane, "-p"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        return []
    return result.stdout.split("\n")


def pane_is_idle(pane: str) -> bool:
    try:
        lines = capture_pane_lines(pane)
        if not lines:
            return False

        recent = lines[-8:]
        if recent and not recent[-1].strip():
            for line in reversed(recent[:-1]):
                stripped = line.strip()
                if not stripped:
                    continue
                for pat in IDLE_PATTERNS:
                    if pat.search(stripped):
                        return True
            return True

        for line in reversed(recent):
            stripped = line.strip()
            if not stripped:
                continue
            for pat in IDLE_PATTERNS:
                if pat.search(stripped):
                    return True
        return False
    except Exception:
        return False


def pane_exists(pane: str) -> bool:
    if not pane:
        return False
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        return pane in result.stdout.splitlines()
    except Exception:
        return False


def pane_matches_agent(pane: str, agent: str) -> bool:
    patterns = AGENT_PATTERNS.get(agent.lower(), [])
    if not patterns or not pane:
        return False
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}|#{pane_current_command}|#{pane_title}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        metadata = ""
        for line in result.stdout.splitlines():
            parts = line.split("|", 2)
            if parts and parts[0] == pane:
                metadata = " ".join(parts[1:])
                break
        haystack = metadata
        if agent.lower() == "codex":
            haystack += " " + "\n".join(capture_pane_lines(pane)[-8:])
        return any(pattern.search(haystack) for pattern in patterns)
    except Exception:
        return False


def resolve_pane(agent: str) -> str:
    try:
        # 1. /tmp session override — highest priority, dynamic, tmux-lifecycle
        pin_file = f"/tmp/tether-pane-{agent}"
        if os.path.exists(pin_file):
            try:
                pinned = open(pin_file).read().strip()
                if pinned and pane_exists(pinned):
                    return pinned
            except Exception:
                pass

        # 2. Persistent config — survives reboots
        persistent = load_persistent_pins().get(agent.lower(), "")
        if persistent and pane_exists(persistent):
            return persistent

        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}|#{pane_current_command}|#{pane_title}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return ""
        patterns = AGENT_PATTERNS.get(agent.lower(), [])
        candidates = []
        for line in result.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            pane_id, command, title = parts[0], parts[1], parts[2]
            if command.lower() == agent.lower():
                return pane_id
            for pat in patterns:
                if pat.search(title) or pat.search(command):
                    candidates.append(pane_id)
                    break
        for pane_id in candidates:
            if pane_matches_agent(pane_id, agent):
                return pane_id
        for line in result.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            pane_id = parts[0]
            if pane_matches_agent(pane_id, agent):
                return pane_id
        return ""
    except Exception:
        logger.exception("failed to resolve pane", extra={"agent": agent})
        return ""


def inject_when_idle(notification: str, agent: str, state: dict) -> None:
    if not is_enabled(agent):
        update_state(state, last_inject_attempt_at=now_iso(), last_inject_success=False, last_delivery_path="disabled")
        return
    pane = ""
    deadline = time.time() + IDLE_MAX_WAIT
    pane_was_idle = False
    while time.time() < deadline:
        pane = resolve_pane(agent)
        if not pane:
            time.sleep(IDLE_POLL_INTERVAL)
            continue
        if pane_is_idle(pane):
            pane_was_idle = True
            break
        time.sleep(IDLE_POLL_INTERVAL)
    if not pane:
        update_state(
            state,
            pane="",
            last_inject_attempt_at=now_iso(),
            last_inject_pane="",
            last_pane_was_idle=False,
            last_inject_success=False,
        )
        deliver_desktop(notification, state, "no tmux pane found")
        return
    try:
        update_state(
            state,
            pane=pane,
            last_inject_attempt_at=now_iso(),
            last_inject_pane=pane,
            last_pane_was_idle=pane_was_idle,
        )
        literal = subprocess.run(["tmux", "send-keys", "-t", pane, "-l", notification], check=False)
        time.sleep(0.5)
        enter = subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], check=False)
        if literal.returncode == 0 and enter.returncode == 0:
            update_state(state, last_inject_success=True, last_inject_success_at=now_iso(), last_delivery_path="tmux")
            return
        update_state(state, last_inject_success=False)
        deliver_desktop(notification, state, "tmux send-keys failed")
    except OSError:
        update_state(state, last_inject_success=False)
        logger.exception("tmux injection raised")
        deliver_desktop(notification, state, "tmux injection exception")


def health_payload(agent: str, port: int, state: dict, delivery_mode: str) -> dict:
    resolved_pane = ""
    if not uses_desktop_notify(agent, delivery_mode):
        resolved_pane = resolve_pane(agent)
        update_state(state, pane=resolved_pane)
    with state["lock"]:
        return {
            "agent": agent,
            "pane": resolved_pane,
            "port": port,
            "enabled": is_enabled(agent),
            "last_ping_at": state.get("last_ping_at"),
            "last_inject_success": state.get("last_inject_success"),
            "last_inject_success_at": state.get("last_inject_success_at"),
            "last_pane_was_idle": state.get("last_pane_was_idle"),
            "delivery_mode": delivery_mode,
            "last_delivery_path": state.get("last_delivery_path"),
        }


def run_test_inject(agent: str, state: dict, delivery_mode: str) -> dict:
    notification = f"[Tether] test ping for {agent} at {now_iso()}"
    resolved_pane = resolve_pane(agent)
    pane_was_idle = pane_is_idle(resolved_pane) if resolved_pane else False
    update_state(state, last_ping_at=now_iso())
    if uses_desktop_notify(agent, delivery_mode):
        injected = deliver_desktop(notification, state, "test inject desktop path")
        update_state(state, last_inject_attempt_at=now_iso(), last_inject_success=injected, last_inject_success_at=now_iso() if injected else None, last_pane_was_idle=True, pane=resolved_pane)
    else:
        inject_when_idle(notification, agent, state)
        with state["lock"]:
            injected = bool(state.get("last_inject_success"))
    return {
        "injected": injected,
        "pane_was_idle": pane_was_idle,
        "pane": resolved_pane,
    }


# ── HTTP handler ───────────────────────────────────────────────────────────────

class PingHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, agent=None, state=None, delivery_mode="auto", **kwargs):
        self.agent = agent
        self.state = state
        self.delivery_mode = delivery_mode
        super().__init__(*args, **kwargs)

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health":
            self._json_response(404, {"error": "not_found"})
            return
        self._json_response(
            200,
            health_payload(self.agent, self.server.server_port, self.state, self.delivery_mode),
        )

    def do_POST(self):
        if self.path == "/test-inject":
            self._json_response(200, run_test_inject(self.agent, self.state, self.delivery_mode))
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
            sender = data.get("from", "unknown")
            handle = data.get("handle", "")
            subject = data.get("subject", "")
            if subject:
                notification = f"[Tether] {sender}: {subject}  Handle: '{handle}'"
            else:
                notification = f"[Tether] From agent: {sender}  Handle: '{handle}'"
            update_state(self.state, last_ping_at=now_iso())

            # Buffer file for observability
            try:
                with open(f"/tmp/tether-ping-{self.agent}.txt", "w") as f:
                    f.write(notification + "\n")
            except Exception:
                pass

            if uses_desktop_notify(self.agent, self.delivery_mode):
                thread = threading.Thread(
                    target=deliver_desktop,
                    args=(notification, self.state, "desktop delivery mode"),
                    daemon=True,
                )
            else:
                thread = threading.Thread(
                    target=inject_when_idle,
                    args=(notification, self.agent, self.state),
                    daemon=True,
                )
            thread.start()
        except Exception:
            pass
        self._json_response(200, {"ok": True})

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Tether ping daemon")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--delivery-mode", choices=("auto", "desktop", "tmux"), default="auto")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not uses_desktop_notify(args.agent, args.delivery_mode):
        startup_pane = resolve_pane(args.agent)
        if startup_pane:
            logger.info("resolved tmux pane on startup", extra={"agent": args.agent, "pane": startup_pane})
        else:
            logger.warning("no tmux pane found on startup", extra={"agent": args.agent})

    state = {
        "lock": threading.Lock(),
        "pane": "",
        "last_ping_at": None,
        "last_inject_attempt_at": None,
        "last_inject_success": None,
        "last_inject_success_at": None,
        "last_pane_was_idle": None,
        "last_inject_pane": None,
        "last_delivery_path": None,
    }

    def handler_factory(*a, **kw):
        return PingHandler(*a, agent=args.agent, state=state, delivery_mode=args.delivery_mode, **kw)

    server = HTTPServer(("localhost", args.port), handler_factory)
    if uses_desktop_notify(args.agent, args.delivery_mode):
        mode = "desktop notify"
    else:
        mode = "tmux inject (dynamic discovery)"
    print(f"Tether ping daemon [{args.agent}] on http://localhost:{args.port} — {mode}")
    print(f'Register: tether_register_ping(agent="{args.agent}", url="http://localhost:{args.port}")')
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
