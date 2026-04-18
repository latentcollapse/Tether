import asyncio
import importlib
import json
from pathlib import Path

import pytest

@pytest.fixture()
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    monkeypatch.setenv("TETHER_DB", str(tmp_path / "tether.db"))

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
