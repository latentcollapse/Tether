from tether import __main__ as cli
from tether import konsole_driver
from tether.sqlite_runtime import SQLiteRuntime


def test_compatibility_wake_only_queues(monkeypatch, tmp_path):
    db_path = str(tmp_path / "postoffice.db")
    monkeypatch.setattr("tether.delivery_worker.ensure_started", lambda _db: None)
    monkeypatch.setattr(
        konsole_driver, "inject_tether_notice",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("compat sender must not inject")),
    )
    assert cli._konsole_wake(
        to_agent="cursor", from_agent="codex", subject="review",
        handle="h&l_messages_queued", db_path=db_path,
    )
    runtime = SQLiteRuntime(db_path=db_path)
    try:
        assert runtime.konsole_pending_get("h&l_messages_queued", "cursor")["status"] == "pending"
    finally:
        runtime.close()
