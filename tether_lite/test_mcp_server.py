import asyncio
import json
from pathlib import Path

import pytest

from tether_lite import mcp_server
from tether_lite.runtime import TetherLiteRuntime


@pytest.fixture(autouse=True)
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "runtime", TetherLiteRuntime(tmp_path))


def test_list_tools_exposes_required_surface() -> None:
    tools = asyncio.run(mcp_server.list_tools())

    assert {tool.name for tool in tools} == {
        "tether_send",
        "tether_inbox",
        "tether_receive",
        "tether_close",
    }


def test_mcp_round_trip() -> None:
    sent = asyncio.run(mcp_server.call_tool(
        "tether_send",
        {
            "from_agent": "claude",
            "to": "codex",
            "subject": "T-010",
            "text": "hello from lite",
            "ticket_id": "T-010",
            "tags": ["tether"],
        },
    ))
    handle = json.loads(sent[0].text)["handle"]

    inbox = asyncio.run(mcp_server.call_tool("tether_inbox", {"for_agent": "codex"}))
    inbox_data = json.loads(inbox[0].text)
    assert inbox_data["count"] == 1
    assert inbox_data["messages"][0]["handle"] == handle

    received = asyncio.run(mcp_server.call_tool("tether_receive", {"handle": handle, "for_agent": "codex"}))
    assert json.loads(received[0].text)["message"]["status"] == "read"
    assert received[1].text == "hello from lite"

    closed = asyncio.run(mcp_server.call_tool("tether_close", {"handle": handle}))
    assert json.loads(closed[0].text)["updated"] == 1


def test_mcp_errors_are_structured() -> None:
    result = asyncio.run(mcp_server.call_tool("tether_receive", {"handle": "h&l_messages_missing"}))

    data = json.loads(result[0].text)
    assert data["error"] == "MessageNotFound"
