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


def process_agent(session: dict, registry: list[dict]) -> str | None:
    """Identify an agent from the tab's *live foreground process* only.

    Konsole titles and persisted bindings are routing hints, not identity.  A tab
    survives when an agent crashes and its shell resumes, so accepting a stamped
    title here turns a stale tab into an arbitrary-input target.  Matches use whole
    process tokens and registered executable names only.
    """
    proc = (session.get("proc") or "").lower()
    cmdline = (session.get("cmdline") or "").lower()
    cmd_tokens = set(re.findall(r"[a-z0-9_-]+", cmdline))
    cmd_parts = cmdline.split()
    cmd_exe = os.path.basename(cmd_parts[0]) if cmd_parts else ""

    # The executable actually being run IS the registered command.
    for a in registry:
        cmd = (a.get("command") or "").strip()
        if not cmd:
            continue
        base = os.path.basename(cmd.split()[0]).lower()
        if base and (base == proc or base == cmd_exe):
            return a["id"]
    # Node/python launchers expose the agent as a whole command-line token/path.
    for a in registry:
        if not (a.get("command") or "").strip():
            continue
        aid = a["id"].lower()
        if aid == proc or aid == cmd_exe or aid in cmd_tokens:
            return a["id"]
    return None


def guess_agent(session: dict, registry: list[dict]) -> str | None:
    """Compatibility alias for strict live-process identification."""
    return process_agent(session, registry)


def session_agent_is_live(
    service: str,
    session: str,
    agent: str,
    *,
    expected_pid: str | int | None = None,
    registry: list[dict] | None = None,
) -> bool:
    """Re-read Konsole and prove that this exact tab still runs ``agent``.

    This check belongs immediately before every D-Bus write.  A prior binding,
    title, prompt shape, or successful check earlier in a delivery is not proof:
    the foreground process can exit between any two observations.
    """
    if not agent:
        return False
    if registry is None:
        from tether.agent_config import load_agents

        registry = load_agents()
    for live in list_sessions():
        if live.get("service") != service or live.get("session") != session:
            continue
        if live.get("ambiguous") or process_agent(live, registry) != agent:
            return False
        if expected_pid is not None and str(live.get("pid") or "") != str(expected_pid):
            return False
        return True
    return False


def send_line(service: str, session: str, text: str, submit: bool = True) -> bool:
    """Type text into a tab and (optionally) press Enter."""
    if _qdbus(service, session, "org.kde.konsole.Session.sendText", text) is None:
        return False
    if submit:
        time.sleep(0.2)
        # Carriage return mimics the Enter key (tty maps \r → \n via ICRNL)
        _qdbus(service, session, "org.kde.konsole.Session.sendText", "\r")
    return True


def prompt_state(service: str, session: str) -> str:
    """Classify the visible agent input as ``empty``, ``draft``, ``busy``, or ``unknown``.

    Konsole exposes text but not an input-buffer API.  The three supported agent
    TUIs do expose stable empty-prompt placeholders, though.  We only auto-submit
    a Tether wake when we can positively identify one of those placeholders.  An
    unrecognised screen is deliberately treated as ``unknown``: the notice is
    inserted but never submitted, which protects anything Matt is already typing.

    This is a transport policy, not message acknowledgement.  The message itself
    remains durable in SQLite and the recipient must resolve its handle to ACK it.
    """
    screen = get_displayed_text(service, session)
    if not screen:
        return "unknown"

    # Agent activity does not make the composer unsafe.  An empty follow-up box
    # while an agent is working is precisely where a tmail should be submitted:
    # the TUI queues it behind the current turn.  Only text actually present in
    # the composer is a draft and blocks delivery.

    # Work from the bottom: terminal output can contain old prompts above the
    # current one.  Strip only terminal padding; do not collapse the actual draft.
    for raw in reversed(screen.splitlines()[-80:]):
        line = raw.strip()
        if not line:
            continue

        # Cursor Agent: an empty composer is rendered as this placeholder.  A
        # visible follow-up draft replaces the placeholder after the arrow.
        if line.startswith("→"):
            suffix = line[1:].strip()
            suffix = re.sub(r"\s+ctrl\+[a-z].*$", "", suffix, flags=re.IGNORECASE).strip()
            # Cursor 1.8 can render an idle composer as a bare arrow while its
            # follow-up notice and status footer occupy the following lines.
            # That is an empty input buffer and is safe to submit.  Restrict
            # recognition to a line *starting* with the composer marker: arrow
            # glyphs also occur in old transcript text such as CORE-33→CORE-34.
            if suffix == "":
                return "empty"
            if suffix == "Add a follow-up":
                return "empty"
            # A prior delivery can be left in Cursor's composer when an
            # earlier screen classification was conservative.  It is not a
            # Matt-authored draft: the durable notice has a fixed prefix, so
            # the next delivery may safely submit the accumulated notices and
            # wake the idle agent.  Do not use a loose "Tether" match here;
            # a human may legitimately type that word into a real draft.
            if suffix.startswith("[Tether] New message from "):
                return "empty"
            if suffix.startswith("# [Tether] resolve "):
                return "empty"
            if suffix:
                return "draft"

        # Codex CLI's empty composer has a stable placeholder.  Its user text
        # appears after the same leading glyph.
        if line.startswith("›"):
            suffix = line[1:].strip()
            if suffix in {
                "Find and fix a bug in @filename",
                "Run /review on my current changes",
            }:
                return "empty"
            if suffix:
                return "draft"

        # Claude Code shows a bare ❯ when the prompt is empty.  It also renders
        # placeholder hints after the same glyph that are NOT a Matt-authored
        # draft: "Press up to edit queued messages" appears whenever text was
        # injected while a turn was running.  Reading those as a draft is what
        # made Claude Code deliveries type-but-never-submit — the notice lands,
        # is classified as human typing, and is protected forever.  Treat the
        # known placeholders as an empty composer; anything else is a real draft.
        if line.startswith("❯"):
            # NBSP separates the glyph from Claude Code's placeholder text.
            suffix = line[1:].replace("\xa0", " ").strip()
            if not suffix:
                return "empty"
            low = suffix.lower()
            if low.startswith("press up to edit queued message"):
                return "empty"
            if low.startswith("try \"") or low.startswith("ask claude"):
                return "empty"
            if suffix.startswith("[Tether] New message from "):
                return "empty"
            if suffix.startswith("[Tether from "):
                return "empty"
            if suffix.startswith("# [Tether] resolve "):
                return "empty"
            return "draft"

        # Pi coding agent: prompt line begins with > or shows openrouter model bar
        if line.startswith(">") or "openrouter/" in line or "Ask it how to use or extend Pi" in line:
            suffix = line[1:].strip() if line.startswith(">") else line.strip()
            if not suffix or "openrouter/" in line or "Ask it" in line:
                return "empty"
            return "draft"

        # Kilo coding agent: shows Kilo Gateway or ctrl+p commands at bottom
        if "Kilo Gateway" in line or "ctrl+p commands" in line:
            return "empty"

    return "unknown"


def agent_accepts_delivery_now(service: str, session: str, agent: str) -> bool:
    """Whether this TUI can safely *submit* its current empty composer now."""
    screen = get_displayed_text(service, session)
    low = screen.lower()
    # Codex explicitly supports Tab-to-queue during an active turn. Cursor and
    # Claude do not expose a reliably injectable active-turn submit key through
    # Konsole D-Bus, so wait for their turn to finish rather than leaving text.
    if agent == "cursor" and "ctrl+c to stop" in low:
        return False
    if agent == "claude" and "esc to interrupt" in low:
        return False
    return prompt_state(service, session) == "empty"


def inject_tether_notice(
    service: str,
    session: str,
    text: str,
    *,
    expected_agent: str,
    expected_pid: str | int | None = None,
) -> tuple[bool, str]:
    """Submit one inert notice only when the recipient is positively idle.

    Busy, drafted, and unknown composers receive *zero bytes*.  This is the
    transport's central safety invariant: sender-controlled input must never be
    appended to a human draft or typed into a shell while identity is uncertain.
    """
    if not session_agent_is_live(
        service, session, expected_agent, expected_pid=expected_pid
    ):
        return False, "wrong_target"
    state = prompt_state(service, session)
    if state != "empty":
        return False, state

    # Observe a stable empty prompt twice before placing the inert line.
    time.sleep(0.12)
    if not session_agent_is_live(
        service, session, expected_agent, expected_pid=expected_pid
    ):
        return False, "wrong_target"
    second_state = prompt_state(service, session)
    if second_state != "empty":
        return False, second_state
    if not send_line(service, session, text, submit=False):
        return False, "send_failed"
    time.sleep(0.12)
    handle = next((part for part in text.split() if part.startswith("h&l_")), "")
    if not handle or not composer_is_tether_owned(service, session, handle):
        return False, "ownership_lost"
    return submit_owned_tether_notice(
        service,
        session,
        handle,
        expected_agent=expected_agent,
        expected_pid=expected_pid,
    )


def submit_owned_tether_notice(
    service: str,
    session: str,
    handle: str,
    *,
    expected_agent: str,
    expected_pid: str | int | None = None,
) -> tuple[bool, str]:
    """Submit an exact Tether-owned composer using the TUI's live key binding."""
    if not session_agent_is_live(
        service, session, expected_agent, expected_pid=expected_pid
    ):
        return False, "wrong_target"
    if not composer_is_tether_owned(service, session, handle):
        return False, "not_owned"

    screen = get_displayed_text(service, session)
    # Codex uses Tab to queue a follow-up while a turn is active. Enter merely
    # leaves the text in its composer. Other supported TUIs submit with Enter.
    submit_key = "\t" if expected_agent == "codex" and "tab to queue message" in screen.lower() else "\r"
    if not send_line(service, session, submit_key, submit=False):
        return False, "submit_failed"
    time.sleep(0.25)
    if composer_contains(service, session, handle):
        return False, "not_submitted"
    return True, "empty"


def set_title(service: str, session: str, title: str) -> bool:
    """Stamp a tab title with an agent id (role 1 = session/displayed title)."""
    return _qdbus(service, session, "org.kde.konsole.Session.setTitle", "1", title) is not None


def get_displayed_text(service: str, session: str, timeout: float = 5.0) -> str:
    """Read the visible viewport text of a tab (Konsole getAllDisplayedText).

    Viewport only — scrolled-off history is not included — which is exactly right for
    confirming a JUST-injected line: right after injection the line sits at the bottom
    of the viewport, so this sees it. Returns "" if the read fails."""
    out = _qdbus(service, session, "org.kde.konsole.Session.getAllDisplayedText", "true", timeout=timeout)
    return out or ""


_COMPOSER_MARKERS = ("→", "›", "❯", ">")


def current_composer_text(service: str, session: str) -> str | None:
    """Return text owned by the *current* visible prompt, if recognizable.

    This is deliberately narrower than :func:`screen_contains`.  A handle in
    prior transcript output proves only that it was once painted; it does not
    prove that Tether owns the current input buffer and therefore must never be
    used as permission to press Enter.
    """
    screen = get_displayed_text(service, session)
    if not screen:
        return None
    lines = screen.splitlines()[-100:]
    marker_index = None
    first = ""
    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index].strip()
        if stripped.startswith(_COMPOSER_MARKERS):
            marker_index = index
            first = stripped[1:].replace("\xa0", " ").strip()
            break
    if marker_index is None:
        return None

    # A wrapped composer begins on the marker line.  Only collect continuation
    # text when that line already contains input; a bare marker followed by a
    # Tether-looking transcript/status line is not sufficient proof of input
    # ownership.
    if not first:
        return ""
    pieces = [first]
    footer = re.compile(
        r"^(?:Auto\b|Working\b|Running\b|Thinking\b|Reading\b|Editing\b|"
        r"Grepping\b|Searching\b|Planning\b|Building\b|Testing\b|Compacting\b|"
        r"\d+\s+(?:task|agent|background terminal)\b|"
        r".*(?:bypass permissions|shift\+tab to cycle|esc to interrupt|\? for shortcuts).*)",
        re.IGNORECASE,
    )
    for raw in lines[marker_index + 1 :]:
        stripped = raw.strip()
        is_separator = bool(stripped) and set(stripped) <= {
            "─", "━", "-", "=", "▄", "▀", "▁", "▔",
        }
        if (
            not stripped
            or stripped.startswith(_COMPOSER_MARKERS)
            or is_separator
            or footer.search(stripped)
        ):
            break
        pieces.append(stripped)
    return " ".join(pieces)


def composer_contains(service: str, session: str, needle: str) -> bool:
    """Whether ``needle`` belongs to the current prompt input buffer."""
    if not needle:
        return False
    composer = current_composer_text(service, session)
    return composer is not None and needle in composer


def composer_is_tether_owned(service: str, session: str, handle: str) -> bool:
    """True only when the current prompt consists of a Tether notice.

    A notice appended after Matt's own draft still contains the handle, but its
    composer starts with human text and is therefore never auto-submitted.
    """
    composer = current_composer_text(service, session)
    if not composer or handle not in composer:
        return False
    # Full-match the inert wake.  Merely mentioning Tether is not
    # enough: a user may type after a held notice, and that mixed composer must
    # remain under human control.
    pattern = r"^# \[Tether\] resolve " + re.escape(handle) + r" --agent [A-Za-z0-9_-]+$"
    return re.fullmatch(pattern, " ".join(composer.split())) is not None


def screen_contains(service: str, session: str, needle: str) -> bool:
    """Whether `needle` is currently visible in the tab's viewport. This is the delivery
    confirmation signal: inject a line, then check the handle landed on screen. If it did,
    delivery succeeded and the retry loop can stop — no need to wait for an ACK the agent
    may be unable to give (MCP down, rate-limited, mid-task)."""
    if not needle:
        return False
    return needle in get_displayed_text(service, session)


def find_session(service: str, session_path: str) -> dict | None:
    for s in list_sessions():
        if s["service"] == service and s["session"] == session_path:
            return s
    return None
