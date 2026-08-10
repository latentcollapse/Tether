from tether import konsole_driver
from tether.delivery_worker import is_delivery_authority, process_once, run
from tether.sqlite_runtime import SQLiteRuntime


def _runtime(tmp_path):
    return SQLiteRuntime(db_path=str(tmp_path / "postoffice.db"))


def _queue(runtime, handle, agent):
    runtime.konsole_pending_add(handle, agent)


def test_busy_recipient_receives_zero_bytes(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    _queue(runtime, "h&l_messages_busy", "claude")
    monkeypatch.setattr(
        "tether.delivery._live_konsole_target",
        lambda *_: {"service": "svc", "session": "/Sessions/1", "pid": "42"},
    )
    monkeypatch.setattr(konsole_driver, "session_agent_is_live", lambda *_a, **_k: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "busy")
    calls = []
    monkeypatch.setattr(konsole_driver, "send_line", lambda *a, **k: calls.append((a, k)) or True)
    try:
        assert process_once(runtime)["waiting"] == 1
        assert calls == []
        assert runtime.konsole_pending_get("h&l_messages_busy", "claude")["status"] == "pending"
    finally:
        runtime.close()


def test_idle_recipient_gets_one_atomic_inert_line(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    _queue(runtime, "h&l_messages_idle", "claude")
    monkeypatch.setattr(
        "tether.delivery._live_konsole_target",
        lambda *_: {"service": "svc", "session": "/Sessions/1", "pid": "42"},
    )
    monkeypatch.setattr(konsole_driver, "session_agent_is_live", lambda *_a, **_k: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "empty")
    monkeypatch.setattr(konsole_driver.time, "sleep", lambda *_: None)
    calls = []
    monkeypatch.setattr(
        konsole_driver, "send_line",
        lambda service, session, text, submit=False: calls.append(text) or True,
    )
    try:
        assert process_once(runtime)["delivered"] == 1
        assert calls == ["# [Tether] resolve h&l_messages_idle --agent claude\r"]
        assert runtime.konsole_pending_get("h&l_messages_idle", "claude")["status"] == "delivered"
    finally:
        runtime.close()


def test_tick_attempts_only_oldest_handle_per_recipient(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    _queue(runtime, "h&l_messages_01", "claude")
    _queue(runtime, "h&l_messages_02", "claude")
    _queue(runtime, "h&l_messages_03", "cursor")
    monkeypatch.setattr(
        "tether.delivery._live_konsole_target",
        lambda _runtime, agent: {"service": "svc", "session": agent, "pid": "42"},
    )
    observed = []
    monkeypatch.setattr(
        konsole_driver, "inject_tether_notice",
        lambda _s, session, line, **_k: observed.append((session, line)) or (False, "busy"),
    )
    try:
        process_once(runtime)
        assert [agent for agent, _line in observed] == ["claude", "cursor"]
        assert all("h&l_messages_02" not in line for _agent, line in observed)
    finally:
        runtime.close()


def test_kill_switch_prevents_target_resolution_and_writes(monkeypatch, tmp_path):
    runtime = _runtime(tmp_path)
    _queue(runtime, "h&l_messages_pause", "claude")
    runtime.delivery_set_paused(True, "incident")
    monkeypatch.setattr(
        "tether.delivery._live_konsole_target",
        lambda *_: (_ for _ in ()).throw(AssertionError("paused dispatcher must do nothing")),
    )
    try:
        assert process_once(runtime) == {"delivered": 0, "waiting": 0, "missing": 0}
    finally:
        runtime.close()


def test_temporary_database_cannot_own_live_delivery(monkeypatch, tmp_path):
    monkeypatch.delenv("TETHER_DELIVERY_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    temporary = str(tmp_path / "pytest.db")
    assert not is_delivery_authority(temporary)
    assert run(temporary, poll_seconds=0) == 2


def test_nondefault_authority_requires_explicit_opt_in(monkeypatch, tmp_path):
    authority = str(tmp_path / "private" / "postoffice.db")
    monkeypatch.setenv("TETHER_DELIVERY_DB", authority)
    assert is_delivery_authority(authority)
