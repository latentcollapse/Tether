"""Characterization tests for SQLiteRuntime — the canonical data layer.

These pin the *behavior* (the public contracts), not the internal structure, so they
stay green through the upcoming sqlite_runtime.py split: they assert what the runtime
DOES (round-trips, the board lifecycle, presence, id issuance, persistence), never how
its code is arranged. If a refactor changes any of these outcomes, that's a real
regression and these tests catch it.
"""

from pathlib import Path
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from tether import SQLiteRuntime


@pytest.fixture()
def rt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SQLiteRuntime:
    """A fresh runtime on a throwaway DB. The fresh DB exercises the construct-time
    schema init (incl. the smart-board tables) — a virgin DB must be fully usable."""
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    monkeypatch.setattr(SQLiteRuntime, "_fire_ping_sync", lambda *_args, **_kwargs: None)
    return SQLiteRuntime(db_path=str(tmp_path / "tether.db"))


# ── handles: collapse/resolve round-trips ────────────────────────────────────

def test_inline_handle_round_trips(rt: SQLiteRuntime) -> None:
    handle = rt.collapse("notes", {"a": 1, "b": "two"})
    assert handle.startswith("h&l_")
    resolved = rt.resolve(handle)
    # collapse auto-stamps a `timestamp` onto stored dicts; the payload round-trips intact.
    assert resolved["a"] == 1 and resolved["b"] == "two"
    assert "timestamp" in resolved


def test_blob_and_tree_round_trip(rt: SQLiteRuntime) -> None:
    blob = rt.collapse_blob(b"payload", "application/octet-stream")
    tree = rt.collapse_tree([blob])
    assert rt.resolve(blob) == b"payload"
    assert rt.resolve(tree) == [b"payload"]


def test_collapse_registers_table(rt: SQLiteRuntime) -> None:
    rt.collapse("widgets", {"x": 1})
    assert "widgets" in rt.tables()
    assert len(rt.handles("widgets")) == 1


def test_delete_removes_handle(rt: SQLiteRuntime) -> None:
    handle = rt.collapse("ephemeral", {"gone": "soon"})
    assert rt.delete(handle) is True
    with pytest.raises(Exception):
        rt.resolve(handle)


# ── smart board: the full ticket lifecycle ───────────────────────────────────

def test_board_propose_then_query(rt: SQLiteRuntime) -> None:
    handle = rt.board_propose("core", "local", "Fix the thing", "details", "claude")
    assert handle.startswith("h&l_board_")
    proposed = rt.board_query(status="proposed")
    assert any(t["title"] == "Fix the thing" for t in proposed)


def test_board_accept_issues_sequential_ids(rt: SQLiteRuntime) -> None:
    """Accepting a proposed ticket assigns a real CATEGORY-N id, counting up per category."""
    h1 = rt.board_propose("core", "local", "first", "d", "claude")
    h2 = rt.board_propose("core", "local", "second", "d", "claude")
    assert rt.board_accept(h1, "matt") == "CORE-1"
    assert rt.board_accept(h2, "matt") == "CORE-2"
    # different category -> independent counter
    h3 = rt.board_propose("ui", "local", "ui ticket", "d", "claude")
    assert rt.board_accept(h3, "matt") == "UI-1"


def test_board_full_lifecycle(rt: SQLiteRuntime) -> None:
    """propose -> accept -> claim -> flag -> finalize, with status transitions verified."""
    handle = rt.board_propose("core", "local", "lifecycle", "d", "claude")
    ticket_id = rt.board_accept(handle, "matt")

    assert _status(rt, ticket_id) == "open"
    assert rt.board_claim(ticket_id, "codex") is True
    assert _status(rt, ticket_id) == "active"
    assert rt.board_flag(ticket_id, "codex", "did the work") is True
    assert _status(rt, ticket_id) == "ready"

    # finalize moves the ticket to "done" (the row stays as history; it's also archived
    # to the changelog, which is why board_finalize returns a changelog handle).
    rt.board_finalize(ticket_id, "matt")
    assert _status(rt, ticket_id) == "done"


def test_board_author_creates_open_ticket_directly(rt: SQLiteRuntime) -> None:
    ticket_id = rt.board_author("tooling", "blue", "Authored", "d", "matt")
    assert ticket_id == "TOOLING-1"
    assert _status(rt, ticket_id) == "open"


def test_board_dormant_and_revive(rt: SQLiteRuntime) -> None:
    ticket_id = rt.board_author("core", "local", "sleeper", "d", "matt")
    assert rt.board_dormant(ticket_id, "matt") is True
    assert _status(rt, ticket_id) == "dormant"
    assert rt.board_revive(ticket_id, "matt") is True
    assert _status(rt, ticket_id) == "open"


def test_board_query_filters(rt: SQLiteRuntime) -> None:
    rt.board_author("core", "local", "core-open", "d", "matt")
    ui = rt.board_author("ui", "blue", "ui-open", "d", "matt")
    rt.board_claim(ui, "codex")
    assert {t["title"] for t in rt.board_query(category="CORE")} == {"core-open"}
    assert {t["title"] for t in rt.board_query(status="active")} == {"ui-open"}


def test_board_survives_reopen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tickets persist across runtime instances (SQLite is the source of truth)."""
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    db = str(tmp_path / "tether.db")
    rt1 = SQLiteRuntime(db_path=db)
    tid = rt1.board_author("core", "local", "persistent", "d", "matt")
    rt1.close()

    rt2 = SQLiteRuntime(db_path=db)
    assert tid in {t["id"] for t in rt2.board_query()}


# ── presence ─────────────────────────────────────────────────────────────────

def test_presence_register_list_offline(rt: SQLiteRuntime) -> None:
    rt.presence_register("claude", pid=123, ping_port=9000)
    online = {p["agent"] for p in rt.presence_list() if p["status"] == "online"}
    assert "claude" in online

    rt.presence_offline("claude")
    online_after = {p["agent"] for p in rt.presence_list() if p["status"] == "online"}
    assert "claude" not in online_after


# ── ping endpoints ───────────────────────────────────────────────────────────

def test_ping_url_set_get_and_toggle(rt: SQLiteRuntime) -> None:
    rt.set_ping_url("codex", "http://localhost:9000", enabled=True)
    assert rt.get_ping_url("codex") == "http://localhost:9000"
    rt.set_ping_enabled("codex", False)
    # disabled endpoint should not be handed out as a live ping target
    assert rt.get_ping_url("codex") is None


def test_konsole_pending_defer_preserves_initial_attempt(rt: SQLiteRuntime) -> None:
    rt.konsole_pending_add(
        "h&l_messages_defer", "cursor", "notice", interval_seconds=90, target_pid=42
    )
    before = rt._conn.execute(
        "SELECT attempts, status FROM tether_konsole_pending WHERE handle=? AND agent=?",
        ("h&l_messages_defer", "cursor"),
    ).fetchone()
    rt.konsole_pending_defer("h&l_messages_defer", "cursor", interval_seconds=0)
    after = rt._conn.execute(
        "SELECT attempts, status FROM tether_konsole_pending WHERE handle=? AND agent=?",
        ("h&l_messages_defer", "cursor"),
    ).fetchone()
    assert before["attempts"] == after["attempts"] == 1
    assert after["status"] == "pending"


def test_konsole_terminal_delivery_has_no_retry_schedule(rt: SQLiteRuntime) -> None:
    handle = "h&l_messages_terminal"
    rt.konsole_pending_add(handle, "cursor", "notice", interval_seconds=0, target_pid=42)
    assert rt.konsole_pending_due()[0]["target_pid"] == "42"
    rt.konsole_pending_resolve(handle, "cursor", "delivered")
    row = rt.konsole_pending_get(handle, "cursor")
    assert row["status"] == "delivered"
    assert row["next_attempt_at"] is None
    assert row["attempts"] == row["max_attempts"]
    assert rt.konsole_pending_due() == []


def test_legacy_pending_migration_is_concurrency_safe(tmp_path: Path) -> None:
    db_path = str(tmp_path / "legacy.db")
    connection = sqlite3.connect(db_path)
    connection.execute("""
        CREATE TABLE tether_konsole_pending (
            handle TEXT NOT NULL, agent TEXT NOT NULL, line TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 8,
            interval_seconds INTEGER NOT NULL DEFAULT 20, next_attempt_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY (handle, agent)
        )
    """)
    connection.execute(
        "INSERT INTO tether_konsole_pending VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("h&l_messages_legacy", "cursor", "old", 1, 3, 30,
         "2026-08-08T00:00:00+00:00", "pending", "now", "now"),
    )
    connection.commit()
    connection.close()

    def open_and_close(_index: int) -> None:
        runtime = SQLiteRuntime(db_path=db_path)
        runtime.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(open_and_close, range(2)))

    runtime = SQLiteRuntime(db_path=db_path)
    try:
        row = runtime.konsole_pending_get("h&l_messages_legacy", "cursor")
        assert row["status"] == "target_changed"
        assert row["next_attempt_at"] is None
        assert row["attempts"] == row["max_attempts"]
        assert row["line"] == (
            "# [Tether] resolve h&l_messages_legacy --agent cursor"
        )
        assert runtime.konsole_pending_due() == []
    finally:
        runtime.close()


def test_existing_legacy_lines_are_sanitized_even_when_terminal(tmp_path: Path) -> None:
    db_path = str(tmp_path / "legacy-lines.db")
    runtime = SQLiteRuntime(db_path=db_path)
    runtime._conn.execute(
        "INSERT INTO tether_konsole_pending "
        "(handle, agent, line, attempts, max_attempts, interval_seconds, "
        "next_attempt_at, status, target_pid, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, 3, 30, NULL, 'delivered', NULL, datetime('now'), datetime('now'))",
        (
            "h&l_messages_oldline",
            "claude",
            "[Tether] New message from attacker: touch /tmp/owned",
        ),
    )
    runtime._conn.commit()
    runtime.close()

    migrated = SQLiteRuntime(db_path=db_path)
    try:
        row = migrated.konsole_pending_get("h&l_messages_oldline", "claude")
        assert row["line"] == (
            "# [Tether] resolve h&l_messages_oldline --agent claude"
        )
        assert row["attempts"] == row["max_attempts"] == 3
        assert row["next_attempt_at"] is None
    finally:
        migrated.close()


def test_pending_unsubmitted_delivery_is_reconciled_to_notified(tmp_path: Path) -> None:
    db_path = str(tmp_path / "delivery-state.db")
    runtime = SQLiteRuntime(db_path=db_path)
    handle = "h&l_messages_held"
    runtime.konsole_pending_add(
        handle,
        "claude",
        "# [Tether] resolve h&l_messages_held --agent claude",
        target_pid=42,
    )
    runtime.delivery_record(
        handle,
        "claude",
        "delivered",
        "konsole",
        submitted=False,
        confirmed=True,
        held=True,
    )
    runtime.close()

    reconciled = SQLiteRuntime(db_path=db_path)
    try:
        assert reconciled.delivery_status(handle, "claude")["status"] == "notified"
        assert reconciled.konsole_pending_get(handle, "claude")["status"] == "pending"
    finally:
        reconciled.close()


# ── tasks ────────────────────────────────────────────────────────────────────

def test_task_create_update_get(rt: SQLiteRuntime) -> None:
    rt.task_create("T-1", "Title", "desc")
    assert rt.task_get("T-1")["status"] == "open"
    rt.task_update("T-1", status="done")
    assert rt.task_get("T-1")["status"] == "done"


# ── helpers ──────────────────────────────────────────────────────────────────

def _status(rt: SQLiteRuntime, ticket_id: str) -> str:
    row = rt._conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return row["status"] if row else "<missing>"
