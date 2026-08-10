import asyncio
import importlib
import json
from pathlib import Path

import pytest

@pytest.fixture()
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    monkeypatch.setenv("TETHER_DB", str(tmp_path / "tether.db"))
    monkeypatch.setenv("HOME", str(tmp_path))

    from tether import mcp_server

    return importlib.reload(mcp_server)


def test_blob_round_trip(server) -> None:
    payload = "aGVsbG8gZnVsbA=="

    collapsed = asyncio.run(
        server.call_tool(
            "tether_collapse_blob",
            {"bytes_b64": payload, "content_type": "text/plain"},
        )
    )
    handle = json.loads(collapsed[0].text)["handle"]

    resolved = asyncio.run(server.call_tool("tether_resolve_blob", {"handle": handle}))

    assert json.loads(resolved[0].text) == {
        "bytes_b64": payload,
        "content_type": "text/plain",
    }


def test_tree_round_trip(server) -> None:
    collapsed = asyncio.run(
        server.call_tool(
            "tether_collapse_tree",
            {"handles": ["h&l_inline_alpha", "h&l_blob_beta"]},
        )
    )
    handle = json.loads(collapsed[0].text)["handle"]

    resolved = asyncio.run(server.call_tool("tether_resolve_tree", {"handle": handle}))

    assert json.loads(resolved[0].text) == {"handles": ["h&l_inline_alpha", "h&l_blob_beta"]}


def test_send_offers_delivery_without_http_endpoint(server, monkeypatch) -> None:
    monkeypatch.setattr("tether.delivery._live_konsole_target", lambda *_: None)
    sent = asyncio.run(
        server.call_tool(
            "tether_send",
            {
                "to": "cursor",
                "subject": "review request",
                "text": "Please inspect the attached spec.",
                "from_agent": "codex",
            },
        )
    )

    body = json.loads(sent[0].text)
    assert body["status"] == "queued"
    assert body["queued"] is True
    assert body["delivered"] is False
    assert body["to"] == "cursor"


def test_resolve_records_recipient_read_receipt(server) -> None:
    handle = server.runtime.collapse(
        "messages",
        {"from": "claude", "to": "codex", "subject": "audit", "text": "read me"},
        owner="codex",
    )
    server.runtime.konsole_pending_add(
        handle, "codex", "safe notice", interval_seconds=0, target_pid=42
    )
    resolved = asyncio.run(
        server.call_tool("tether_resolve", {"handle": handle, "for_agent": "codex"})
    )
    assert json.loads(resolved[0].text)["subject"] == "audit"
    assert server.runtime.is_read(handle, "codex")
    assert server.runtime.konsole_pending_get(handle, "codex")["status"] == "acked"


def test_resolve_uses_pinned_mcp_agent_identity(server, monkeypatch) -> None:
    monkeypatch.setenv("TETHER_AGENT_ID", "claude")
    handle = server.runtime.collapse(
        "messages",
        {"from": "codex", "to": "claude", "subject": "receipt", "text": "read me"},
        owner="claude",
    )
    asyncio.run(server.call_tool("tether_resolve", {"handle": handle}))
    assert server.runtime.is_read(handle, "claude")
