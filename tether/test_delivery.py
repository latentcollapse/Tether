from __future__ import annotations

from tether import agent_config, delivery, konsole_driver
from tether.sqlite_runtime import SQLiteRuntime


def _runtime(tmp_path):
    return SQLiteRuntime(db_path=str(tmp_path / "postoffice.db"))


def _target(monkeypatch):
    monkeypatch.setattr(
        delivery,
        "_live_konsole_target",
        lambda *_: {"service": "svc", "session": "/Sessions/7", "pid": "77"},
    )


def test_empty_prompt_is_submitted_and_reported_truthfully(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    _target(monkeypatch)
    monkeypatch.setattr(konsole_driver, "inject_tether_notice", lambda *_args, **_kwargs: (True, "empty"))
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)
    try:
        outcome = delivery.deliver_to_konsole(
            runtime,
            to_agent="cursor",
            from_agent="codex",
            subject="review",
            handle="h&l_messages_empty",
            settle_seconds=0,
            spawn_followup=False,
        )
        assert outcome.status == "delivered"
        assert outcome.submitted is True
        assert runtime.delivery_status(outcome.handle, "cursor")["submitted"] is True
    finally:
        runtime.close()


def test_human_draft_lands_but_never_autosubmits(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    _target(monkeypatch)
    spawned = []
    monkeypatch.setattr(konsole_driver, "inject_tether_notice", lambda *_args, **_kwargs: (True, "draft"))
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)
    monkeypatch.setattr(delivery, "_spawn_followup", lambda **kwargs: spawned.append(kwargs))
    try:
        outcome = delivery.deliver_to_konsole(
            runtime,
            to_agent="cursor",
            from_agent="claude",
            subject="plan",
            handle="h&l_messages_draft",
            settle_seconds=0,
        )
        assert outcome.status == "delivered"
        assert outcome.held is True
        assert outcome.submitted is False
        assert outcome.confirmed is True
        assert spawned and spawned[0]["handle"] == outcome.handle
    finally:
        runtime.close()


def test_http_200_with_rejected_body_is_not_false_delivery(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(delivery, "_live_konsole_target", lambda *_: None)
    monkeypatch.setattr(delivery, "_post_http", lambda *_: {"ok": False, "injected": False})
    monkeypatch.setenv("HOME", str(tmp_path))
    runtime.set_ping_url("cursor", "http://127.0.0.1:1234/deliver")
    try:
        outcome = delivery.notify_message(
            runtime,
            to_agent="cursor",
            from_agent="codex",
            subject="review",
            handle="h&l_messages_rejected",
        )
        assert outcome.status == "queued"
        attempts = runtime.delivery_attempts(outcome.handle, "cursor")
        assert any(row["mechanism"] == "http" and row["outcome"] == "rejected" for row in attempts)
    finally:
        runtime.close()


def test_stale_binding_is_removed_and_live_target_rebound(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    runtime.konsole_bind("cursor", "dead-service", "/Sessions/1")
    live = {
        "service": "live-service",
        "session": "/Sessions/9",
        "ambiguous": False,
        "proc": "cursor",
        "cmdline": "cursor",
        "title": "cursor",
    }
    monkeypatch.setattr(konsole_driver, "available", lambda: True)
    monkeypatch.setattr(konsole_driver, "list_sessions", lambda: [live])
    monkeypatch.setattr(agent_config, "load_agents", lambda: [{"id": "cursor", "command": "cursor"}])
    try:
        assert delivery._live_konsole_target(runtime, "cursor") == live
        binding = runtime.konsole_binding("cursor")
        assert (binding["service"], binding["session"]) == ("live-service", "/Sessions/9")
    finally:
        runtime.close()


def test_delivery_tables_are_additive_and_queryable(tmp_path):
    runtime = _runtime(tmp_path)
    try:
        runtime.delivery_attempt("h&l_messages_a", "codex", "konsole", "injected")
        runtime.delivery_record(
            "h&l_messages_a",
            "codex",
            "notified",
            "konsole",
            prompt_state="busy",
            held=True,
        )
        state = runtime.delivery_status("h&l_messages_a", "codex")
        assert state["status"] == "notified"
        assert state["held"] is True
        assert runtime.delivery_attempts("h&l_messages_a", "codex")[0]["outcome"] == "injected"
    finally:
        runtime.close()


def test_notice_line_is_inert_and_excludes_sender_content():
    line = delivery.notice_line(
        to_agent="cursor",
        from_agent="claude",
        subject="touch /tmp/owned; rm -rf something",
        handle="h&l_messages_deadbeef",
    )
    assert line == "# [Tether] resolve h&l_messages_deadbeef --agent cursor"
    assert "touch" not in line
    assert "claude" not in line
