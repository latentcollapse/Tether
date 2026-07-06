import json
import threading

from tether import ping_daemon


def make_state():
    return {
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


def test_pane_is_idle_accepts_blank_prompt_line(monkeypatch):
    monkeypatch.setattr(
        ping_daemon,
        "capture_pane_lines",
        lambda pane: ["\u203a Write tests for @filename", "  gpt-5.4 high · /mnt/d/Language Projects", ""],
    )
    assert ping_daemon.pane_is_idle("%codex-pane") is True


def test_resolve_pane_finds_matching_agent(monkeypatch):
    monkeypatch.setattr(ping_daemon, "pane_matches_agent", lambda pane, agent: pane == "%codex-pane")

    class Result:
        returncode = 0
        stdout = "%gemini-pane|node|◇  Ready (Language Projects)\n%codex-pane|node|⠙ Language Projects\n"

    monkeypatch.setattr(ping_daemon.subprocess, "run", lambda *args, **kwargs: Result())
    assert ping_daemon.resolve_pane("codex") == "%codex-pane"


def test_inject_when_idle_uses_literal_text_and_enter(monkeypatch):
    commands = []
    state = make_state()

    monkeypatch.setattr(ping_daemon, "is_enabled", lambda agent: True)
    monkeypatch.setattr(ping_daemon, "resolve_pane", lambda agent: "%codex-pane")
    monkeypatch.setattr(ping_daemon, "pane_is_idle", lambda pane: True)
    monkeypatch.setattr(ping_daemon.time, "sleep", lambda _: None)

    def fake_run(cmd, check=False, **kwargs):
        commands.append(cmd)
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(ping_daemon.subprocess, "run", fake_run)
    ping_daemon.inject_when_idle("hello", "codex", state)

    assert ["tmux", "send-keys", "-t", "%codex-pane", "-l", "hello"] in commands
    assert ["tmux", "send-keys", "-t", "%codex-pane", "Enter"] in commands
    assert state["last_inject_success"] is True
    assert state["last_pane_was_idle"] is True
    assert state["last_delivery_path"] == "tmux"


def test_health_and_test_inject_endpoints(monkeypatch):
    state = make_state()
    monkeypatch.setattr(ping_daemon, "resolve_pane", lambda agent: "%codex-pane")
    monkeypatch.setattr(ping_daemon, "pane_is_idle", lambda pane: True)
    monkeypatch.setattr(ping_daemon, "is_enabled", lambda agent: True)

    def fake_inject(notification, agent, state):
        ping_daemon.update_state(
            state,
            pane="%codex-pane",
            last_inject_success=True,
            last_inject_success_at="2026-04-18T06:30:00Z",
            last_pane_was_idle=True,
            last_delivery_path="tmux",
        )

    monkeypatch.setattr(ping_daemon, "inject_when_idle", fake_inject)

    payload = ping_daemon.health_payload("codex", 7704, state, "tmux")
    assert payload["agent"] == "codex"
    assert payload["pane"] == "%codex-pane"
    assert payload["enabled"] is True
    assert payload["port"] == 7704
    assert payload["delivery_mode"] == "tmux"
    assert payload["last_delivery_path"] is None

    payload = ping_daemon.run_test_inject("codex", state, "tmux")
    assert payload == {"injected": True, "pane_was_idle": True, "pane": "%codex-pane"}
    assert state["last_delivery_path"] == "tmux"


def test_delivery_mode_override_forces_tmux(monkeypatch):
    monkeypatch.setattr(ping_daemon, "desktop_notify_agents", lambda: {"claude"})
    assert ping_daemon.uses_desktop_notify("claude", "tmux") is False
    assert ping_daemon.uses_desktop_notify("claude", "desktop") is True
    assert ping_daemon.uses_desktop_notify("claude", "auto") is True


def test_inject_when_no_pane_falls_back_to_prompt_file(monkeypatch):
    state = make_state()
    monkeypatch.setattr(ping_daemon, "is_enabled", lambda agent: True)
    monkeypatch.setattr(ping_daemon, "resolve_pane", lambda agent: "")
    monkeypatch.setattr(ping_daemon.time, "sleep", lambda _: None)
    # Bound the idle-retry deadline to 0 so the no-pane path exits immediately. Without this
    # the loop busy-spins for the full IDLE_RETRY_DEADLINE (600s) in real wall-clock time
    # (sleep is mocked to a noop, so the deadline is the only exit) — the test "hang".
    monkeypatch.setattr(ping_daemon, "IDLE_RETRY_DEADLINE", 0)
    monkeypatch.setattr(ping_daemon, "desktop_notify", lambda notification: False)
    monkeypatch.setattr(ping_daemon, "write_prompt_fallback", lambda notification: True)

    ping_daemon.inject_when_idle("hello", "codex", state)

    assert state["last_inject_success"] is False
    assert state["last_delivery_path"] == "prompt_file"
