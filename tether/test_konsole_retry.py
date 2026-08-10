from tether import konsole_driver, konsole_retry


class _Runtime:
    def __init__(self) -> None:
        self.resolved: list[tuple[str, str, str]] = []
        self.deferred: list[tuple[str, str, int]] = []
        self.deliveries = []
        self.due_agents = []

    def konsole_pending_due(self, agent=None):
        self.due_agents.append(agent)
        return [{"handle": "h&l_messages_abc", "agent": "cursor", "line": "notice", "interval_seconds": 30, "attempts": 1, "max_attempts": 3}]

    def is_read(self, _handle, _agent):
        return False

    def konsole_binding(self, _agent):
        return {"service": "svc", "session": "/Sessions/1"}

    def konsole_pending_resolve(self, handle, agent, status):
        self.resolved.append((handle, agent, status))

    def konsole_pending_defer(self, handle, agent, interval):
        self.deferred.append((handle, agent, interval))

    def delivery_record(self, *args, **kwargs):
        self.deliveries.append((args, kwargs))


def _live_target(monkeypatch):
    monkeypatch.setattr(
        "tether.delivery._live_konsole_target",
        lambda _runtime, _agent: {"service": "svc", "session": "/Sessions/1", "pid": "42"},
    )
    monkeypatch.setattr(
        konsole_driver, "session_agent_is_live", lambda *_args, **_kwargs: True
    )


def test_visible_busy_cursor_follow_up_is_deferred_not_submitted(monkeypatch):
    runtime = _Runtime()
    _live_target(monkeypatch)
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "busy")
    monkeypatch.setattr(konsole_driver, "send_line", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not submit while busy")))
    konsole_retry.process_due(runtime)
    assert runtime.deferred == [("h&l_messages_abc", "cursor", 30)]
    assert runtime.resolved == []


def test_retry_pass_scopes_due_query_to_receiver_agent(monkeypatch):
    runtime = _Runtime()
    _live_target(monkeypatch)
    monkeypatch.setattr(runtime, "konsole_pending_due", lambda agent=None: runtime.due_agents.append(agent) or [])
    konsole_retry.process_due(runtime, agent_filter="claude")
    assert runtime.due_agents == ["claude"]


def test_visible_idle_tether_follow_up_is_submitted_once(monkeypatch):
    runtime = _Runtime()
    _live_target(monkeypatch)
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: True)
    states = iter(["empty", "busy"])
    calls = []
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: next(states))
    monkeypatch.setattr(konsole_driver, "send_line", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    monkeypatch.setattr(konsole_retry.time, "sleep", lambda _seconds: None)
    konsole_retry.process_due(runtime)
    assert calls == [(('svc', '/Sessions/1', '\r'), {'submit': False})]
    assert runtime.resolved == [("h&l_messages_abc", "cursor", "delivered")]
    assert runtime.deferred == []


def test_visible_human_draft_is_deferred_not_submitted(monkeypatch):
    runtime = _Runtime()
    _live_target(monkeypatch)
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "draft")
    monkeypatch.setattr(konsole_driver, "send_line", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must preserve a draft")))
    konsole_retry.process_due(runtime)
    assert runtime.deferred == [("h&l_messages_abc", "cursor", 30)]


def test_old_transcript_handle_never_authorizes_bare_enter(monkeypatch):
    runtime = _Runtime()
    _live_target(monkeypatch)
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "screen_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "inject_tether_notice", lambda *_args, **_kwargs: (True, "empty"))
    monkeypatch.setattr(
        konsole_driver,
        "send_line",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not press bare Enter")),
    )
    monkeypatch.setattr(konsole_retry.time, "sleep", lambda _seconds: None)
    konsole_retry.process_due(runtime)
    assert runtime.resolved == [("h&l_messages_abc", "cursor", "delivered")]


def test_restarted_agent_process_never_receives_old_delivery(monkeypatch):
    runtime = _Runtime()
    monkeypatch.setattr(
        runtime,
        "konsole_pending_due",
        lambda agent=None: [{
            "handle": "h&l_messages_abc", "agent": "cursor", "line": "notice",
            "interval_seconds": 30, "attempts": 1, "max_attempts": 3,
            "target_pid": "41",
        }],
    )
    monkeypatch.setattr(
        "tether.delivery._live_konsole_target",
        lambda _runtime, _agent: {"service": "svc", "session": "/Sessions/1", "pid": "42"},
    )
    monkeypatch.setattr(
        konsole_driver,
        "inject_tether_notice",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("replacement process must receive no bytes")
        ),
    )
    konsole_retry.process_due(runtime)
    assert runtime.resolved == [("h&l_messages_abc", "cursor", "target_changed")]
