from tether import konsole_driver
from tether.konsole_followup import record_result, submit_when_idle


def test_busy_follow_up_waits_then_submits_at_empty_prompt(monkeypatch):
    states = iter(["busy", "empty", "empty", "busy"])
    calls = []
    clock = iter([0.0, 0.0, 1.0, 2.0])
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: next(states))
    monkeypatch.setattr(konsole_driver, "send_line", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    assert submit_when_idle("svc", "/Sessions/1", "h&l_messages_abc", monotonic=lambda: next(clock), sleep=lambda _: None) == "submitted"
    assert calls == [(('svc', '/Sessions/1', '\r'), {'submit': False})]


def test_cr_that_leaves_exact_notice_empty_tries_safe_lf_before_declaring_failure(monkeypatch):
    states = iter(["empty", "empty", "empty", "busy"])
    calls = []
    clock = iter([0.0, 0.0, 1.0])
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: next(states))
    monkeypatch.setattr(konsole_driver, "send_line", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    assert submit_when_idle(
        "svc", "/Sessions/1", "h&l_messages_abc", monotonic=lambda: next(clock), sleep=lambda _: None
    ) == "submitted"
    assert calls == [
        (("svc", "/Sessions/1", "\r"), {"submit": False}),
        (("svc", "/Sessions/1", "\n"), {"submit": False}),
    ]


def test_single_empty_redraw_before_busy_never_submits(monkeypatch):
    states = iter(["empty", "busy"])
    calls = []
    clock = iter([0.0, 0.0, 1.0, 2.0])
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: next(states))
    monkeypatch.setattr(konsole_driver, "send_line", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    assert submit_when_idle(
        "svc", "/Sessions/1", "h&l_messages_abc", timeout_seconds=1.5,
        monotonic=lambda: next(clock), sleep=lambda _: None,
    ) == "timed_out"
    assert calls == []


def test_human_draft_is_never_submitted(monkeypatch):
    calls = []
    clock = iter([0.0, 0.0, 1.0, 2.0])
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "composer_is_tether_owned", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "draft")
    monkeypatch.setattr(konsole_driver, "send_line", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    assert submit_when_idle("svc", "/Sessions/1", "h&l_messages_abc", timeout_seconds=1.5, monotonic=lambda: next(clock), sleep=lambda _: None) == "timed_out"
    assert calls == []


def test_missing_notice_is_never_submitted(monkeypatch):
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "send_line", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not inject a duplicate")))
    assert submit_when_idle(
        "svc", "/Sessions/1", "h&l_messages_abc", timeout_seconds=1.0, initial_visibility_grace_seconds=0.0
    ) == "not_visible"


def test_lost_notice_reinjects_only_after_verified_empty_prompt(monkeypatch):
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "empty")
    calls = []
    monkeypatch.setattr(
        konsole_driver,
        "inject_tether_notice",
        lambda *args: calls.append(args) or (True, "empty"),
    )
    clock = iter([0.0, 0.0])
    assert submit_when_idle(
        "svc",
        "/Sessions/1",
        "h&l_messages_abc",
        expected_line="notice h&l_messages_abc",
        initial_visibility_grace_seconds=0.0,
        monotonic=lambda: next(clock),
        sleep=lambda _: None,
    ) == "submitted"
    assert calls == [("svc", "/Sessions/1", "notice h&l_messages_abc")]


def test_lost_notice_never_reinjects_over_human_draft(monkeypatch):
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: False)
    monkeypatch.setattr(konsole_driver, "prompt_state", lambda *_: "draft")
    monkeypatch.setattr(
        konsole_driver,
        "inject_tether_notice",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not type over draft")),
    )
    clock = iter([0.0, 0.0, 2.0])
    assert submit_when_idle(
        "svc",
        "/Sessions/1",
        "h&l_messages_abc",
        timeout_seconds=1.0,
        expected_line="notice h&l_messages_abc",
        initial_visibility_grace_seconds=0.0,
        monotonic=lambda: next(clock),
        sleep=lambda _: None,
    ) == "timed_out"


def test_read_receipt_stops_waiter_without_typing(monkeypatch):
    calls = []
    monkeypatch.setattr(konsole_driver, "composer_contains", lambda *_: True)
    monkeypatch.setattr(konsole_driver, "send_line", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    assert submit_when_idle(
        "svc",
        "/Sessions/1",
        "h&l_messages_abc",
        is_acknowledged=lambda: True,
    ) == "acknowledged"
    assert calls == []


def test_record_result_only_resolves_after_real_submission(monkeypatch):
    calls = []

    class _Runtime:
        def __init__(self, *, db_path):
            calls.append(("init", db_path))

        def konsole_pending_resolve(self, handle, agent, status):
            calls.append(("resolve", handle, agent, status))

        def konsole_pending_defer(self, handle, agent, interval_seconds):
            calls.append(("defer", handle, agent, interval_seconds))

        def delivery_record(self, *args, **kwargs):
            calls.append(("delivery", args, kwargs))

        def close(self):
            calls.append(("close",))

    monkeypatch.setattr("tether.sqlite_runtime.SQLiteRuntime", _Runtime)
    record_result(db_path="/tmp/tether.db", agent="cursor", handle="h&l_messages_abc", result="submitted")
    record_result(db_path="/tmp/tether.db", agent="cursor", handle="h&l_messages_def", result="acknowledged")
    record_result(db_path="/tmp/tether.db", agent="cursor", handle="h&l_messages_ghi", result="timed_out")
    assert ("resolve", "h&l_messages_abc", "cursor", "delivered") in calls
    assert ("resolve", "h&l_messages_def", "cursor", "delivered") in calls
    assert ("defer", "h&l_messages_ghi", "cursor", 30) in calls
