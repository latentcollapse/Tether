from __future__ import annotations

from tether import agent_config, delivery, konsole_driver
from tether.sqlite_runtime import SQLiteRuntime


def _runtime(tmp_path):
    return SQLiteRuntime(db_path=str(tmp_path / "postoffice.db"))


def test_send_only_queues_and_never_writes_prompt(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    started = []
    monkeypatch.setattr("tether.delivery_worker.ensure_started", lambda db: started.append(db))
    monkeypatch.setattr(
        konsole_driver, "inject_tether_notice",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("sender must not inject")),
    )
    try:
        outcome = delivery.deliver_to_konsole(
            runtime, to_agent="cursor", from_agent="codex", subject="review",
            handle="h&l_messages_empty",
        )
        assert outcome.status == "queued"
        assert runtime.konsole_pending_get(outcome.handle, "cursor")["status"] == "pending"
        assert started == [runtime.db_path]
    finally:
        runtime.close()


def test_live_target_is_resolved_fresh_without_binding_cache(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    live = {"service": "live", "session": "/Sessions/9", "ambiguous": False}
    monkeypatch.setattr(konsole_driver, "available", lambda: True)
    monkeypatch.setattr(konsole_driver, "list_sessions", lambda: [live])
    monkeypatch.setattr(agent_config, "load_agents", lambda: [{"id": "cursor", "command": "cursor"}])
    monkeypatch.setattr(konsole_driver, "process_agent", lambda session, registry: "cursor")
    try:
        assert delivery._live_konsole_target(runtime, "cursor") == live
        assert runtime.konsole_binding("cursor") is None
    finally:
        runtime.close()


def test_notice_line_is_inert_and_excludes_sender_content():
    line = delivery.notice_line(
        to_agent="cursor", from_agent="claude",
        subject="touch /tmp/owned; rm -rf something",
        handle="h&l_messages_deadbeef",
    )
    assert line == "# [Tether] resolve h&l_messages_deadbeef --agent cursor"
    assert "touch" not in line
    assert "claude" not in line
