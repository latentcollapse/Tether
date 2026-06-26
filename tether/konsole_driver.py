#!/usr/bin/env python3
"""
Tether Konsole driver — native KDE multiplexing over D-Bus.

This is the no-tmux, zero-friction delivery path for KDE. Konsole exposes each
tab as a D-Bus session object with:
  - foregroundProcessId()      what's running in the tab
  - sendText(text)             inject input (this is our "type into the agent")
  - setTitle(role, text)       stamp a tab with an agent id (disambiguates dupes)
  - runCommand(cmd), title()   launch / read

So the model becomes: boot Tether, launch agents in Konsole tabs exactly as
normal, and Tether reaches into Konsole to discover them and autofire tmails.
Nothing extra to type, no tmux, no PTY wrapper.

Targeting precision requires the agent to run directly in the tab (not nested
inside tmux — a tmux client shows up as the foreground process and hides the
real agent). list_sessions() flags that case.

Implemented over the qdbus CLI to avoid a hard python-dbus dependency.
"""
import os
import re
import shutil
import subprocess
import time


def _find_qdbus() -> str | None:
    for cand in ("qdbus6", "qdbus-qt6", "qdbus"):
        path = shutil.which(cand)
        if path:
            return path
    return None


_QDBUS = _find_qdbus()


def available() -> bool:
    return _QDBUS is not None


def _qdbus(*args: str, timeout: float = 5.0) -> str | None:
    if not _QDBUS:
        return None
    try:
        r = subprocess.run([_QDBUS, *args], capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return None
        return r.stdout
    except Exception:
        return None


def konsole_services() -> list[str]:
    """All running Konsole instances (one D-Bus service per Konsole process)."""
    out = _qdbus()
    if not out:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith("org.kde.konsole-")]


def _proc_name(pid: str) -> str:
    if not pid:
        return ""
    try:
        with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _proc_cmdline(pid: str) -> str:
    """Full command line — reveals the agent behind a generic `node` process."""
    if not pid:
        return ""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return ""


_SESSION_RE = re.compile(r"^/Sessions/\d+$")


def list_sessions() -> list[dict]:
    """Every Konsole tab across every window, with its foreground process."""
    sessions: list[dict] = []
    for svc in konsole_services():
        out = _qdbus(svc) or ""
        for line in out.splitlines():
            path = line.strip()
            if not _SESSION_RE.match(path):
                continue
            pid = (_qdbus(svc, path, "org.kde.konsole.Session.foregroundProcessId") or "").strip()
            proc = _proc_name(pid)
            cmdline = _proc_cmdline(pid)
            title = (_qdbus(svc, path, "org.kde.konsole.Session.title", "1") or "").strip()
            sessions.append({
                "service": svc,
                "session": path,
                "pid": pid,
                "proc": proc,
                "cmdline": cmdline,
                "title": title,
                # A tmux client in the foreground hides the real agent → not directly targetable
                "ambiguous": proc.startswith("tmux"),
            })
    return sessions


def guess_agent(session: dict, registry: list[dict]) -> str | None:
    """Best-guess which registered agent a tab is running.

    Matches on WHOLE TOKENS, never loose substrings. A short agent id like "pi"
    must NOT match an unrelated command such as `pipx install ...` — that mis-match
    bound innocent tabs and (via title stamping) created self-reinforcing phantom
    nodes. Tokenization splits on path separators and non-alphanumerics so the agent
    id / command basename has to appear as its own word to count.
    """
    proc = (session.get("proc") or "").lower()
    title = (session.get("title") or "").lower()
    cmdline = (session.get("cmdline") or "").lower()
    title_tokens = set(re.findall(r"[a-z0-9_-]+", title))
    cmd_tokens = set(re.findall(r"[a-z0-9_-]+", cmdline))
    cmd_parts = cmdline.split()
    cmd_exe = os.path.basename(cmd_parts[0]) if cmd_parts else ""

    # 1. Title stamped with the agent id as a whole word (strongest — we set it).
    for a in registry:
        if a["id"].lower() in title_tokens:
            return a["id"]
    # 2. The executable actually being run IS the agent's command (exact basename).
    for a in registry:
        cmd = (a.get("command") or "").strip()
        if not cmd:
            continue
        base = os.path.basename(cmd.split()[0]).lower()
        if base and (base == proc or base == cmd_exe):
            return a["id"]
    # 3. Agent id appears as a whole token in the command line (e.g. node .../codex/cli.js)
    for a in registry:
        aid = a["id"].lower()
        if aid == proc or aid == cmd_exe or aid in cmd_tokens:
            return a["id"]
    return None


def send_line(service: str, session: str, text: str, submit: bool = True) -> bool:
    """Type text into a tab and (optionally) press Enter."""
    if _qdbus(service, session, "org.kde.konsole.Session.sendText", text) is None:
        return False
    if submit:
        time.sleep(0.2)
        # Carriage return mimics the Enter key (tty maps \r → \n via ICRNL)
        _qdbus(service, session, "org.kde.konsole.Session.sendText", "\r")
    return True


def set_title(service: str, session: str, title: str) -> bool:
    """Stamp a tab title with an agent id (role 1 = session/displayed title)."""
    return _qdbus(service, session, "org.kde.konsole.Session.setTitle", "1", title) is not None


def find_session(service: str, session_path: str) -> dict | None:
    for s in list_sessions():
        if s["service"] == service and s["session"] == session_path:
            return s
    return None
