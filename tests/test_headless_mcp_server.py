import asyncio
import json
from pathlib import Path

import pytest

from tether import headless_mcp as mcp_server
from tether.runtime import TetherLiteRuntime


@pytest.fixture(autouse=True)
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    monkeypatch.setattr(mcp_server, "runtime", TetherLiteRuntime(tmp_path))


def test_list_tools_exposes_required_surface() -> None:
    tools = asyncio.run(mcp_server.list_tools())

    assert {tool.name for tool in tools} == {
        "tether_send",
        "tether_inbox",
        "tether_receive",
        "tether_close",
        "tether_generate_keypair",
        "tether_collapse_encrypted",
        "tether_resolve_encrypted",
        "tether_collapse_blob",
        "tether_resolve_blob",
        "tether_collapse_tree",
        "tether_resolve_tree",
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


def test_mcp_encrypted_round_trip() -> None:
    generated = asyncio.run(mcp_server.call_tool("tether_generate_keypair", {}))
    keys = json.loads(generated[0].text)

    collapsed = asyncio.run(
        mcp_server.call_tool(
            "tether_collapse_encrypted",
            {
                "payload": "secret from lite",
                "recipient_pubkey": keys["public_key"],
            },
        )
    )
    handle = json.loads(collapsed[0].text)["handle"]

    resolved = asyncio.run(
        mcp_server.call_tool(
            "tether_resolve_encrypted",
            {
                "handle": handle,
                "private_key": keys["private_key"],
            },
        )
    )

    assert json.loads(resolved[0].text) == {"payload": "secret from lite"}


def test_mcp_blob_round_trip() -> None:
    payload = "aGVsbG8gYmxvYg=="

    collapsed = asyncio.run(
        mcp_server.call_tool(
            "tether_collapse_blob",
            {"bytes_b64": payload, "content_type": "text/plain"},
        )
    )
    handle = json.loads(collapsed[0].text)["handle"]

    resolved = asyncio.run(mcp_server.call_tool("tether_resolve_blob", {"handle": handle}))

    assert json.loads(resolved[0].text) == {
        "bytes_b64": payload,
        "content_type": "text/plain",
    }


def test_mcp_tree_round_trip() -> None:
    collapsed = asyncio.run(
        mcp_server.call_tool(
            "tether_collapse_tree",
            {"handles": ["h&l_inline_one", "h&l_blob_two"]},
        )
    )
    handle = json.loads(collapsed[0].text)["handle"]

    resolved = asyncio.run(mcp_server.call_tool("tether_resolve_tree", {"handle": handle}))

    assert json.loads(resolved[0].text) == {"handles": ["h&l_inline_one", "h&l_blob_two"]}
