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

# A terminal TUI can consume Enter before Konsole repaints its viewport.  In
# particular, Antigravity accepted the key while its old prompt remained visible
# for longer than the former 250 ms single check.  Keep polling briefly so a
# successful submission is not mistaken for an unsent notice and duplicated.
_SUBMIT_CONFIRM_POLLS = 20
# Post-inject ownership confirmation. A running TUI repaints continuously
# (spinners); a single getAllDisplayedText read can race the repaint and miss
# text that WAS just injected — observed 2026-08-23 as three consecutive
# "ownership_lost" failures against Claude Code mid-turn, each stranding the
# notice in the composer where the next injection concatenated onto it.
# Poll instead of single-shot, mirroring _SUBMIT_CONFIRM_POLLS.
_OWNERSHIP_CONFIRM_POLLS = 10
_OWNERSHIP_CONFIRM_INTERVAL_SECONDS = 0.15
_SUBMIT_CONFIRM_INTERVAL_SECONDS = 0.15
_COMPOSER_SETTLE_SECONDS = 0.4
_TETHER_WAKE_RE = re.compile(
    r"# \[Tether\] resolve h&l_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+ "
    r"--agent [A-Za-z0-9_-]+"
)


def _is_tether_wake(text: str) -> bool:
    """Whether text is exactly the inert prompt line owned by Tether."""
    return _TETHER_WAKE_RE.fullmatch(text) is not None


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
        if aid == "pi" and ("coding-agent" in cmd_tokens or "pi-mono" in cmdline):
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


_MODAL_DIALOG_RE = re.compile(
    r"esc to (?:cancel|close|dismiss|exit|go back|return)", re.IGNORECASE
)


def _screen_is_modal_dialog(screen: str) -> bool:
    """True when the viewport bottom shows a modal dialog, not the agent composer.

    Modal overlays (Claude Code /feedback, confirmation prompts, ...) replace the
    composer with their own input box.  Two failure modes observed 2026-08-23:
    prompt_state then matched a STALE transcript prompt line above the overlay
    (classifying the screen "empty" while Matt's dialog draft was live), and
    current_composer_text's separator-box heuristic read the dialog box itself
    as the composer — so the waker typed notices INTO the dialog.  Both are
    fixed by failing closed: a dialog screen is "unknown"/None and delivery
    simply waits.  Detection is anchored to the last few non-empty lines so
    transcript text that merely mentions e.g. "Esc to cancel" cannot trigger it.
    """
    bottom = [ln.strip() for ln in screen.splitlines()[-12:] if ln.strip()]
    return any(_MODAL_DIALOG_RE.search(ln) for ln in bottom)


def prompt_state(service: str, session: str) -> str:
    """Classify the visible agent input as ``empty``, ``draft``, or ``unknown``.

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
    if _screen_is_modal_dialog(screen):
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
            if suffix.startswith("# [Tether] resolve ") and _is_tether_wake(suffix):
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
            if _is_tether_wake(suffix):
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
            if suffix.startswith("# [Tether] resolve ") and _is_tether_wake(suffix):
                return "empty"
            return "draft"

        # Antigravity/Gemini and Pi coding agent: prompt line begins with >.
        if line.startswith(">") or "openrouter/" in line or "Ask it how to use or extend Pi" in line:
            suffix = line[1:].strip() if line.startswith(">") else line.strip()
            if not suffix or "openrouter/" in line or "Ask it" in line:
                return "empty"
            if _is_tether_wake(suffix):
                return "empty"
            return "draft"

        # Kilo coding agent: shows Kilo Gateway or ctrl+p commands at bottom
        if "Kilo Gateway" in line or "ctrl+p commands" in line:
            return "empty"

    return "unknown"


def agent_accepts_delivery_now(service: str, session: str, agent: str) -> bool:
    """Whether the current composer is empty enough for automatic submission.

    An active turn is not a human draft.  Claude and Cursor both provide a
    follow-up composer while working, and submitting a Tether wake there is the
    supported way to queue the next instruction.  Only visible user text blocks
    Enter.
    """
    return prompt_state(service, session) == "empty"


def inject_tether_notice(
    service: str,
    session: str,
    text: str,
    *,
    expected_agent: str,
    expected_pid: str | int | None = None,
) -> tuple[bool, str]:
    """Place one inert notice and submit it unless a human draft is visible.

    A supported agent may be working while its follow-up composer is empty; that
    remains safe to submit.  A visible draft is different: append a marked
    notice without Enter, so the person sees it and keeps control of submission.
    Unknown screens remain fail-closed because Konsole has no input-buffer API.
    """
    if not session_agent_is_live(
        service, session, expected_agent, expected_pid=expected_pid
    ):
        return False, "wrong_target"
    state = prompt_state(service, session)
    if state not in {"empty", "draft"}:
        return False, state

    if state == "empty":
        # Observe an empty prompt twice before taking responsibility for Enter.
        time.sleep(0.12)
        if not session_agent_is_live(
            service, session, expected_agent, expected_pid=expected_pid
        ):
            return False, "wrong_target"
        state = prompt_state(service, session)
        if state not in {"empty", "draft"}:
            return False, state

    if not session_agent_is_live(
        service, session, expected_agent, expected_pid=expected_pid
    ):
        return False, "wrong_target"
    # A leading space keeps a held notice distinct from the human's last word
    # without synthesising a newline, which some TUIs interpret as submission.
    notice = text if state == "empty" else f" {text}"
    if state == "empty":
        # The state gate says empty, but verify against the actual composer:
        # a stranded notice from a previous failed pass may still sit there
        # (observed 2026-08-23: prompt_state's prefix match classified a
        # concatenated notice pile as "empty" and each new pass appended
        # another copy — up to 40).  Submit a PURE stranded notice so the
        # recipient still receives it, then deliver into the clean composer;
        # anything else in the composer is a misclassified draft — fail closed.
        existing = " ".join((current_composer_text(service, session) or "").split())
        if existing:
            if _TETHER_WAKE_RE.fullmatch(existing):
                existing_handle = next(
                    (p for p in existing.split() if p.startswith("h&l_")), ""
                )
                if not send_line(service, session, "\r", submit=False):
                    return False, "send_failed"
                for _ in range(_SUBMIT_CONFIRM_POLLS):
                    if not current_composer_text(service, session):
                        break
                    time.sleep(_SUBMIT_CONFIRM_INTERVAL_SECONDS)
                else:
                    return False, "composer_busy"
                if existing_handle and existing_handle == handle:
                    # The stranded notice IS this message — a retry after a
                    # submit-confirm timeout falsely marked it failed. It is
                    # now submitted; typing again would double-send it
                    # (observed 2026-08-23: two identical resolves of the same
                    # handle). Exactly-once means stop here.
                    return True, "resubmitted"
            else:
                return False, "composer_busy"
    if not send_line(service, session, notice, submit=False):
        return False, "send_failed"
    handle = next((part for part in text.split() if part.startswith("h&l_")), "")
    if not handle or not _wait_composer_contains(service, session, handle):
        return False, "ownership_lost"
    if state == "draft":
        return True, "draft"
    time.sleep(0.12)
    if not _wait_tether_owned(service, session, handle):
        # A human began typing between insertion and Enter.  The notice landed,
        # but its submission now belongs to that human rather than Tether.
        if prompt_state(service, session) == "draft" and composer_contains(service, session, handle):
            return True, "draft"
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

    # Konsole can paint the inserted text before the TUI has finished consuming
    # it.  Recheck after a short measured settle before pressing Enter: this
    # avoids losing Gemini's submit byte and also gives a human draft a chance to
    # revoke Tether ownership.
    time.sleep(_COMPOSER_SETTLE_SECONDS)
    if not session_agent_is_live(
        service, session, expected_agent, expected_pid=expected_pid
    ):
        return False, "wrong_target"
    if not _wait_tether_owned(service, session, handle):
        return False, "not_owned"

    screen = get_displayed_text(service, session)
    # Codex uses Tab to queue a follow-up while a turn is active. Enter merely
    # leaves the text in its composer. Other supported TUIs submit with Enter.
    submit_key = "\t" if expected_agent == "codex" and "tab to queue message" in screen.lower() else "\r"
    if not send_line(service, session, submit_key, submit=False):
        return False, "submit_failed"
    for _ in range(_SUBMIT_CONFIRM_POLLS):
        if not composer_contains(service, session, handle):
            return True, "empty"
        time.sleep(_SUBMIT_CONFIRM_INTERVAL_SECONDS)
    return False, "not_submitted"


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
    if _screen_is_modal_dialog(screen):
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
        sep_indices = [
            i for i, ln in enumerate(lines)
            if ln.strip() and set(ln.strip()) <= {"─", "━", "-", "=", "▄", "▀", "▁", "▔"}
        ]
        if len(sep_indices) >= 2:
            top_sep = sep_indices[-2]
            bot_sep = sep_indices[-1]
            if bot_sep > top_sep:
                box_lines = [lines[i].strip() for i in range(top_sep + 1, bot_sep) if lines[i].strip()]
                if box_lines:
                    return " ".join(box_lines)
                return ""
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


def _wait_composer_contains(service: str, session: str, needle: str) -> bool:
    """Poll composer_contains briefly — a live TUI repaint can hide just-typed text."""
    for i in range(_OWNERSHIP_CONFIRM_POLLS):
        if composer_contains(service, session, needle):
            return True
        time.sleep(_OWNERSHIP_CONFIRM_INTERVAL_SECONDS)
    return False


def _wait_tether_owned(service: str, session: str, handle: str) -> bool:
    """Poll composer_is_tether_owned; contains-but-not-owned fails fast (human text)."""
    for i in range(_OWNERSHIP_CONFIRM_POLLS):
        if composer_is_tether_owned(service, session, handle):
            return True
        composer = current_composer_text(service, session)
        if composer is not None and handle in composer:
            return False  # visible but not a pure notice — genuinely not ours
        time.sleep(_OWNERSHIP_CONFIRM_INTERVAL_SECONDS)
    return False


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
