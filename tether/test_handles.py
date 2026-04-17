from pathlib import Path

import pytest

from tether import Runtime, SQLiteRuntime


def test_runtime_inline_blob_and_tree_handles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    rt = Runtime()

    inline = rt.collapse({"kind": "inline"})
    blob = rt.collapse_blob(b"payload", "application/octet-stream")
    tree = rt.collapse_tree([inline, blob])

    assert inline.startswith("h&l_inline_")
    assert blob.startswith("h&l_blob_")
    assert tree.startswith("h&l_tree_")
    assert rt.resolve(inline) == {"kind": "inline"}
    assert rt.resolve(blob) == b"payload"
    assert rt.resolve(tree) == [{"kind": "inline"}, b"payload"]


def test_sqlite_inline_handle_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    rt = SQLiteRuntime(str(tmp_path / "tether.db"))

    handle = rt.collapse({"small": "value"})

    assert handle.startswith("h&l_inline_")
    assert rt.resolve(handle) == {"small": "value"}


def test_sqlite_blob_handle_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    rt = SQLiteRuntime(str(tmp_path / "tether.db"))

    handle = rt.collapse_blob(b"\x01\x02", "application/octet-stream")

    assert handle.startswith("h&l_blob_")
    assert rt.resolve(handle) == b"\x01\x02"


def test_sqlite_tree_handle_resolves_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    rt = SQLiteRuntime(str(tmp_path / "tether.db"))
    inline = rt.collapse("inline text")
    blob = rt.collapse_blob(b"blob text", "text/plain")

    tree = rt.collapse_tree([inline, blob])

    assert tree.startswith("h&l_tree_")
    assert rt.resolve(tree) == ["inline text", b"blob text"]


def test_sqlite_legacy_message_handle_still_resolves(tmp_path: Path) -> None:
    rt = SQLiteRuntime(str(tmp_path / "tether.db"))
    handle = rt.collapse("messages", {"from": "claude", "to": "codex", "text": "legacy"})

    resolved = rt.resolve(handle)

    assert handle.startswith("h&l_messages_")
    assert resolved["text"] == "legacy"


def test_sqlite_unknown_handle_prefix_raises_value_error(tmp_path: Path) -> None:
    rt = SQLiteRuntime(str(tmp_path / "tether.db"))

    with pytest.raises(ValueError):
        rt.resolve("h&l_unknown_abc123")
