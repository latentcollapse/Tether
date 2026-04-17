from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tether_lite.runtime import CLOSED, MessageNotFound, TetherLiteRuntime


def test_send_inbox_receive_close_round_trip(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)

    handle = rt.send(
        from_agent="claude",
        to="codex",
        subject="T-010",
        text="build lite store",
        ticket_id="T-010",
        tags=["tether", "red"],
    )

    messages = rt.inbox("codex")
    assert [msg["handle"] for msg in messages] == [handle]
    assert messages[0]["ticket_id"] == "T-010"

    received = rt.receive(handle, for_agent="codex")
    assert received["message"]["from"] == "claude"
    assert received["message"]["status"] == "read"
    assert received["text"] == "build lite store"
    assert rt.inbox("codex") == []

    assert rt.close(handle=handle) == 1
    assert rt.receive(handle)["message"]["status"] == CLOSED


def test_close_by_ticket_only_closes_open_messages(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)
    first = rt.send("claude", "codex", "one", "body", ticket_id="T-010")
    second = rt.send("claude", "codex", "two", "body", ticket_id="T-010")
    rt.receive(first, for_agent="codex")

    assert rt.close(ticket_id="T-010") == 1

    assert rt.receive(first)["message"]["status"] == "read"
    assert rt.receive(second)["message"]["status"] == CLOSED


def test_inbox_marks_old_open_messages_stale(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path, stale_hours=1)
    handle = rt.send("claude", "codex", "old", "body")
    path = rt.messages_dir / f"{handle}.toml"
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    lines = path.read_text(encoding="utf-8").splitlines()
    updated = [f'created_at = "{old_time}"' if line.startswith("created_at = ") else line for line in lines]
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    assert rt.inbox("codex") == []
    assert rt.receive(handle)["message"]["status"] == "stale"


def test_missing_message_raises(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)

    with pytest.raises(MessageNotFound):
        rt.receive("h&l_messages_missing")


def test_invalid_close_arguments_raise(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)

    with pytest.raises(ValueError):
        rt.close()

    with pytest.raises(ValueError):
        rt.close(handle="h&l_messages_missing", status="done")
