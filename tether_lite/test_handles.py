from pathlib import Path

import pytest

from tether_lite.runtime import TetherLiteRuntime


def test_inline_handle_round_trip(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)

    handle = rt.collapse({"kind": "inline", "n": 3})

    assert handle.startswith("h&l_inline_")
    assert rt.resolve(handle) == {"kind": "inline", "n": 3}


def test_blob_handle_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    rt = TetherLiteRuntime(tmp_path)

    handle = rt.collapse_blob(b"\x00blob", "application/octet-stream")

    assert handle.startswith("h&l_blob_")
    assert rt.resolve(handle) == b"\x00blob"


def test_tree_handle_resolves_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    rt = TetherLiteRuntime(tmp_path)
    inline = rt.collapse("hello")
    blob = rt.collapse_blob(b"world", "text/plain")

    tree = rt.collapse_tree([inline, blob])

    assert tree.startswith("h&l_tree_")
    assert rt.resolve(tree) == ["hello", b"world"]


def test_legacy_message_handle_still_resolves(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)
    handle = rt.send("claude", "codex", "legacy", "body")

    resolved = rt.resolve(handle)

    assert handle.startswith("h&l_messages_")
    assert resolved["message"]["subject"] == "legacy"
    assert resolved["text"] == "body"


def test_unknown_handle_prefix_raises_value_error(tmp_path: Path) -> None:
    rt = TetherLiteRuntime(tmp_path)

    with pytest.raises(ValueError):
        rt.resolve("h&l_unknown_abc123")
