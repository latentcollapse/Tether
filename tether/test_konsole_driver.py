from tether import konsole_driver


def _state(monkeypatch, screen: str) -> str:
    monkeypatch.setattr(konsole_driver, "get_displayed_text", lambda *_: screen)
    return konsole_driver.prompt_state("org.kde.konsole-test", "/Sessions/1")


def test_prompt_state_recognises_empty_cursor_composer(monkeypatch):
    assert _state(monkeypatch, "output\n  → Add a follow-up  ctrl+c to stop\n") == "empty"


def test_prompt_state_recognises_bare_idle_cursor_composer(monkeypatch):
    screen = (
        "finished output\n"
        "  CORE-33→CORE-34 shipped\n"
        "  →\n"
        "  [Tether] New message from codex: review ready\n"
        "  1 task\n"
        "  Auto · 85%\n"
    )
    assert _state(monkeypatch, screen) == "empty"


def test_prompt_state_preserves_cursor_draft(monkeypatch):
    assert _state(monkeypatch, "output\n  → Please do not submit this yet\n") == "draft"


def test_prompt_state_marks_live_cursor_turn_busy_even_with_empty_follow_up(monkeypatch):
    screen = "output\n  ⠠⠜ Working  12.1k tokens\n  → Add a follow-up  ctrl+c to stop\n"
    assert _state(monkeypatch, screen) == "busy"


def test_prompt_state_marks_live_cursor_tool_activity_busy(monkeypatch):
    screen = "output\n  ⠰⠰ Grepping  7.58k tokens\n  → Add a follow-up  ctrl+c to stop\n"
    assert _state(monkeypatch, screen) == "busy"


def test_prompt_state_marks_claude_spinner_footer_busy(monkeypatch):
    screen = (
        "✢ Nucleating… (39s · ↓ 10 tokens)\n"
        "────────────────────────\n"
        "❯ \n"
        "⏵⏵ bypass permissions on · esc to interrupt · ← 1 agent\n"
    )
    assert _state(monkeypatch, screen) == "busy"


def test_prompt_state_recovers_idle_cursor_after_prior_tether_notice(monkeypatch):
    screen = (
        "output\n"
        "  → [Tether] New message from codex: CORE-26 ready for claim "
        "— run `tether inbox --agent cursor`\n"
    )
    assert _state(monkeypatch, screen) == "empty"


def test_prompt_state_does_not_confuse_human_tether_mention_with_notice(monkeypatch):
    assert _state(monkeypatch, "output\n  → Please review Tether before submitting\n") == "draft"


def test_transcript_handle_does_not_claim_current_composer(monkeypatch):
    screen = (
        "[Tether] New message from claude — h&l_messages_old\n"
        "agent response complete\n"
        "  → Add a follow-up  ctrl+c to stop\n"
    )
    monkeypatch.setattr(konsole_driver, "get_displayed_text", lambda *_: screen)
    assert not konsole_driver.composer_contains("svc", "/Sessions/1", "h&l_messages_old")
    assert not konsole_driver.composer_is_tether_owned("svc", "/Sessions/1", "h&l_messages_old")


def test_mixed_human_draft_contains_notice_but_is_not_tether_owned(monkeypatch):
    handle = "h&l_messages_new"
    screen = f"  → Keep my draft [Tether] New message from claude — {handle}\n"
    monkeypatch.setattr(konsole_driver, "get_displayed_text", lambda *_: screen)
    assert konsole_driver.composer_contains("svc", "/Sessions/1", handle)
    assert not konsole_driver.composer_is_tether_owned("svc", "/Sessions/1", handle)


def test_claude_footer_is_not_part_of_tether_composer(monkeypatch):
    handle = "h&l_messages_claude"
    notice = (
        f"[Tether] New message from codex: review — run `tether resolve '{handle}' --agent claude`"
    )
    screen = (
        f"❯ {notice}\n"
        "────────────────────────────────────\n"
        "⏵⏵ bypass permissions on (shift+tab to cycle)\n"
    )
    monkeypatch.setattr(konsole_driver, "get_displayed_text", lambda *_: screen)
    assert konsole_driver.current_composer_text("svc", "/Sessions/1") == notice
    assert konsole_driver.composer_is_tether_owned("svc", "/Sessions/1", handle)


def test_prompt_state_recognises_codex_and_claude_empty_prompts(monkeypatch):
    assert _state(monkeypatch, "› Find and fix a bug in @filename\n") == "empty"
    assert _state(monkeypatch, "❯ \n") == "empty"


def test_unknown_prompt_never_autosubmits(monkeypatch):
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "unknown")
    calls = []
    monkeypatch.setattr(
        konsole_driver,
        "send_line",
        lambda service, session, text, submit: calls.append((service, session, text, submit)) or True,
    )
    ok, state = konsole_driver.inject_tether_notice("svc", "/Sessions/1", "notice")
    assert (ok, state) == (True, "unknown")
    assert calls == [("svc", "/Sessions/1", "notice", False)]


def test_empty_prompt_autosubmits(monkeypatch):
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "empty")
    monkeypatch.setattr(konsole_driver, "current_composer_text", lambda *_: "notice")
    monkeypatch.setattr(konsole_driver.time, "sleep", lambda *_: None)
    calls = []
    monkeypatch.setattr(
        konsole_driver,
        "send_line",
        lambda service, session, text, submit: calls.append((service, session, text, submit)) or True,
    )
    ok, state = konsole_driver.inject_tether_notice("svc", "/Sessions/1", "notice")
    assert (ok, state) == (True, "empty")
    assert calls == [
        ("svc", "/Sessions/1", "notice", False),
        ("svc", "/Sessions/1", "\r", False),
    ]


def test_empty_check_does_not_submit_if_human_types_during_injection(monkeypatch):
    states = iter(["empty", "draft"])
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: next(states))
    monkeypatch.setattr(
        konsole_driver,
        "current_composer_text",
        lambda *_: "notice plus Matt's new draft",
    )
    monkeypatch.setattr(konsole_driver.time, "sleep", lambda *_: None)
    calls = []
    monkeypatch.setattr(
        konsole_driver,
        "send_line",
        lambda service, session, text, submit: calls.append((text, submit)) or True,
    )
    ok, state = konsole_driver.inject_tether_notice("svc", "/Sessions/1", "notice")
    assert (ok, state) == (True, "draft")
    assert calls == [("notice", False)]
