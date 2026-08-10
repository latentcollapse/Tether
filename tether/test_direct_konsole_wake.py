"""Direct CLI Konsole wake durability and human-draft safety."""

from __future__ import annotations

from tether import __main__ as cli
from tether import agent_config, delivery, konsole_driver
from tether.sqlite_runtime import SQLiteRuntime


def _stub_target(monkeypatch, *, state: str) -> None:
    monkeypatch.setattr(konsole_driver, "available", lambda: True)
    monkeypatch.setattr(
        konsole_driver,
        "list_sessions",
        lambda: [{"service": "svc", "session": "/Sessions/1", "ambiguous": False, "pid": "42"}],
    )
    monkeypatch.setattr(agent_config, "load_agents", lambda: [{"id": "cursor", "command": "agent"}])
    monkeypatch.setattr(konsole_driver, "process_agent", lambda *_: "cursor")
    monkeypatch.setattr(konsole_driver, "inject_tether_notice", lambda *_args, **_kwargs: (True, state))
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: state == "draft")
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)


def test_busy_direct_wake_persists_exact_handle_and_spawns_waiter(monkeypatch, tmp_path):
    _stub_target(monkeypatch, state="busy")
    calls = []
    monkeypatch.setattr(delivery, "_spawn_followup", lambda **kwargs: calls.append(kwargs))
    db_path = str(tmp_path / "postoffice.db")

    assert cli._konsole_wake(
        to_agent="cursor",
        from_agent="codex",
        subject="tree review",
        handle="h&l_messages_busy",
        db_path=db_path,
    )

    runtime = SQLiteRuntime(db_path=db_path)
    try:
        rows = runtime._conn.execute(
            "SELECT handle, status FROM tether_konsole_pending ORDER BY handle"
        ).fetchall()
    finally:
        runtime.close()
    assert [(row["handle"], row["status"]) for row in rows] == [("h&l_messages_busy", "pending")]
    assert calls == [
        {
            "service": "svc",
            "session": "/Sessions/1",
            "handle": "h&l_messages_busy",
            "agent": "cursor",
            "db_path": db_path,
            "target_pid": "42",
        }
    ]


def test_direct_wake_holds_human_draft_without_submitting(monkeypatch, tmp_path):
    _stub_target(monkeypatch, state="draft")
    calls = []
    monkeypatch.setattr(delivery, "_spawn_followup", lambda **kwargs: calls.append(kwargs))
    db_path = str(tmp_path / "postoffice.db")

    assert cli._konsole_wake(
        to_agent="cursor",
        from_agent="codex",
        subject="tree review",
        handle="h&l_messages_draft",
        db_path=db_path,
    )

    runtime = SQLiteRuntime(db_path=db_path)
    try:
        outcome = runtime.delivery_status("h&l_messages_draft", "cursor")
        assert outcome["held"] is True
        assert outcome["submitted"] is False
    finally:
        runtime.close()
    assert len(calls) == 1


def test_direct_wake_notice_resolves_with_recipient_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(konsole_driver, "available", lambda: True)
    monkeypatch.setattr(
        konsole_driver,
        "list_sessions",
        lambda: [{"service": "svc", "session": "/Sessions/1", "ambiguous": False, "pid": "42"}],
    )
    monkeypatch.setattr(agent_config, "load_agents", lambda: [{"id": "cursor", "command": "agent"}])
    monkeypatch.setattr(konsole_driver, "process_agent", lambda *_: "cursor")
    notices: list[str] = []

    def inject(_service, _session, line, **_kwargs):
        notices.append(line)
        return True, "empty"

    monkeypatch.setattr(konsole_driver, "inject_tether_notice", inject)
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)

    assert cli._konsole_wake(
        to_agent="cursor",
        from_agent="codex",
        subject="tree review",
        handle="h&l_messages_receipt",
        db_path=str(tmp_path / "postoffice.db"),
    )
    assert notices == [
        "# [Tether] resolve h&l_messages_receipt --agent cursor"
    ]
