"""SQLite-backed Tether Runtime for persistent storage."""

import sqlite3
import json
import logging
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List
from pathlib import Path
from .lc import encode_lc_b, decode_lc_b
from .exceptions import E_HANDLE_INVALID, E_HANDLE_UNRESOLVED, E_LC_BINARY_DECODE, E_HANDLE_EXPIRED, E_ACCESS_DENIED
from .runtime import json_to_contract, contract_to_json, CONTRACT_JSON
from .handles import (
    BLOB_PREFIX,
    INLINE_PREFIX,
    LEGACY_MESSAGES_PREFIX,
    TREE_PREFIX,
    canonical_json,
    digest12,
    kvfold_dir,
    suffix,
)
from .tasks_mixin import TasksMixin
from .board_mixin import BoardMixin

_MISSING = object()


def _decode_resilient(lc_bytes: bytes) -> Any:
    """Decode LC-B bytes, falling back to JSON if decoding fails."""
    try:
        contract_value = decode_lc_b(lc_bytes)
        return contract_to_json(contract_value)
    except (E_LC_BINARY_DECODE, Exception):
        try:
            for i, b in enumerate(lc_bytes):
                if b in (0x7B, 0x5B):  # '{' or '['
                    return json.loads(lc_bytes[i:].decode("utf-8", errors="replace"))
            return json.loads(lc_bytes.decode("utf-8", errors="replace"))
        except Exception:
            return lc_bytes.decode("utf-8", errors="replace")


class SQLiteRuntime(TasksMixin, BoardMixin):
    """Tether Runtime with SQLite backing store."""
    
    def __init__(self, db_path: str = "tether.db"):
        self.db_path = db_path
        self._kvfold_dir = kvfold_dir(Path("kvfold"))
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Wait up to 5s for a competing writer instead of raising "database is
        # locked" immediately — the dashboard server runs concurrent per-request
        # runtimes plus the konsole retry loop against the same file.
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def _init_schema(self):
        """Single schema-init entry point: every mixin's table init runs here, once.
        Centralizing it kills the "defined-but-never-called _init_*_db" bug class that
        had silently broken fresh-DB board and task ops. Each init is idempotent
        (CREATE IF NOT EXISTS), so this is a no-op on existing DBs. New mixin with a
        schema? Add its _init_*_db call here — one place, can't be forgotten."""
        self._init_db()              # core + handles tables (this class for now)
        self._init_tasks_db()        # TasksMixin
        self._init_smart_board_db()  # BoardMixin
    
    def _init_db(self):
        """Initialize SQLite schema."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_tables (
                table_name TEXT PRIMARY KEY
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_handles (
                handle TEXT PRIMARY KEY,
                table_name TEXT NOT NULL,
                lc_bytes BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                owner TEXT NULL,
                tags TEXT NULL,
                sender TEXT NULL,
                status TEXT DEFAULT 'open',
                ticket_id TEXT NULL,
                FOREIGN KEY (table_name) REFERENCES tether_tables(table_name)
            )
        """)
        # Tracking read status per agent (since multiple agents might share a DB)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_reads (
                handle TEXT,
                agent TEXT,
                read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (handle, agent)
            )
        """)

        # Migration for tags
        try:
            self._conn.execute("ALTER TABLE tether_handles ADD COLUMN tags TEXT NULL")
        except sqlite3.OperationalError:
            pass

        # Migration for sender
        try:
            self._conn.execute("ALTER TABLE tether_handles ADD COLUMN sender TEXT NULL")
        except sqlite3.OperationalError:
            pass

        # Migration for status (T-001)
        try:
            self._conn.execute("ALTER TABLE tether_handles ADD COLUMN status TEXT DEFAULT 'open'")
        except sqlite3.OperationalError:
            pass

        # Migration for ticket_id (T-001)
        try:
            self._conn.execute("ALTER TABLE tether_handles ADD COLUMN ticket_id TEXT NULL")
        except sqlite3.OperationalError:
            pass

        # Ping endpoints (v1.6)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_ping_endpoints (
                agent TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_channels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_channel_members (
                channel_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                PRIMARY KEY (channel_id, agent),
                FOREIGN KEY (channel_id) REFERENCES tether_channels(id)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_channel_messages (
                id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                body TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                thread_id TEXT NULL,
                FOREIGN KEY (channel_id) REFERENCES tether_channels(id)
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chan_msgs_id ON tether_channel_messages(channel_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chan_members_agent ON tether_channel_members(agent)")

        # Multiplexer presence + routes (v2.0)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_presence (
                agent       TEXT PRIMARY KEY,
                status      TEXT NOT NULL DEFAULT 'offline',
                pid         INTEGER,
                ping_port   INTEGER,
                last_heartbeat TEXT,
                registered_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_routes (
                id          TEXT PRIMARY KEY,
                from_agent  TEXT NOT NULL,
                to_agent    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'active',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_routes_agents ON tether_routes(from_agent, to_agent)")

        # Konsole D-Bus bindings (v2.0) — agent id → live Konsole tab
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_konsole_bindings (
                agent       TEXT PRIMARY KEY,
                service     TEXT NOT NULL,
                session     TEXT NOT NULL,
                bound_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Konsole delivery ACK+retry queue (v2.1) — at-least-once notification.
        # D-Bus sendText is fire-and-forget (returns ok before the agent's TUI
        # has ingested the keystroke), so a single inject is a lossy datagram that
        # races the TUI's redraw loop. Each injected handle-line is registered here
        # and re-nudged on an interval until the recipient ACKs by reading the
        # handle (a row in tether_reads, written when it runs tether_receive),
        # or until attempts are exhausted. Idempotent: the handle is
        # content-addressed, so a duplicate nudge after a read is a harmless no-op.
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_konsole_pending (
                handle          TEXT NOT NULL,
                agent           TEXT NOT NULL,
                line            TEXT NOT NULL,
                attempts        INTEGER NOT NULL DEFAULT 0,
                max_attempts    INTEGER NOT NULL DEFAULT 8,
                interval_seconds INTEGER NOT NULL DEFAULT 20,
                next_attempt_at TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (handle, agent)
            )
        """)
        self._conn.commit()


    # _init_tasks_db moved to tasks_mixin.py (TasksMixin); still called from __init__.

    # ── Board (smart board + changelog + whiteboard) → extracted to board_mixin.py (BoardMixin) ──
    
    def _compute_handle_id(self, data: bytes) -> str:
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str | Any, value: Any = _MISSING, ttl_seconds: Optional[int] = None,
                 owner: Optional[str] = None, tags: Optional[List[str]] = None,
                 sender: Optional[str] = None, ticket_id: Optional[str] = None) -> str:
        """Collapse a value into a handle."""
        if value is _MISSING:
            return self.collapse_inline(table)

        table = str(table)
        self._conn.execute("INSERT OR IGNORE INTO tether_tables (table_name) VALUES (?)", (table,))

        if isinstance(value, dict) and "timestamp" not in value:
            value = value.copy()
            value["timestamp"] = datetime.now(timezone.utc).isoformat()

        contract_value = json_to_contract(value)
        lc_bytes = encode_lc_b(contract_value)
        handle_id = self._compute_handle_id(lc_bytes)
        handle = f"h&l_{table}_{handle_id}"

        expires_at = None
        if ttl_seconds is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        tags_str = ",".join(tags) if tags else None

        self._conn.execute(
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes, expires_at, owner, tags, sender, status, ticket_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (handle, table, lc_bytes, expires_at, owner, tags_str, sender, ticket_id)
        )
        self._conn.commit()
        return handle

    def collapse_inline(self, value: str | dict[str, Any]) -> str:
        """Collapse a small JSON-serializable value into an inline handle."""
        lc_bytes = canonical_json(value)
        handle = f"{INLINE_PREFIX}{digest12(lc_bytes)}"
        self._conn.execute("INSERT OR IGNORE INTO tether_tables (table_name) VALUES ('inline')")
        self._conn.execute(
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes) VALUES (?, 'inline', ?)",
            (handle, lc_bytes),
        )
        self._conn.commit()
        return handle

    def collapse_blob(self, data: bytes, content_type: str) -> str:
        """Collapse binary data into KVFold and return a blob handle."""
        digest = digest12(data)
        handle = f"{BLOB_PREFIX}{digest}"
        (self._kvfold_dir / digest).write_bytes(data)
        (self._kvfold_dir / f"{digest}.toml").write_text(
            f"handle = {json.dumps(handle)}\ncontent_type = {json.dumps(content_type)}\n",
            encoding="utf-8",
        )
        return handle

    def collapse_tree(self, handles: List[str]) -> str:
        """Collapse an ordered list of handles into KVFold and return a tree handle."""
        data = canonical_json(handles)
        digest = digest12(data)
        handle = f"{TREE_PREFIX}{digest}"
        (self._kvfold_dir / digest).write_bytes(data)
        return handle
    
    def resolve(self, handle: str, for_agent: Optional[str] = None) -> Any:
        """Resolve a handle. Automatically marks as read if for_agent is provided."""
        if not handle.startswith("h&l_"):
            raise E_HANDLE_INVALID(f"Invalid handle format: {handle}")

        if handle.startswith(INLINE_PREFIX):
            cursor = self._conn.execute(
                "SELECT lc_bytes FROM tether_handles WHERE handle = ? AND table_name = 'inline'",
                (handle,),
            )
            row = cursor.fetchone()
            if not row:
                raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}")
            return json.loads(bytes(row["lc_bytes"]).decode("utf-8"))

        if handle.startswith(BLOB_PREFIX):
            return (self._kvfold_dir / suffix(handle, BLOB_PREFIX)).read_bytes()

        if handle.startswith(TREE_PREFIX):
            raw = (self._kvfold_dir / suffix(handle, TREE_PREFIX)).read_bytes()
            handles = json.loads(raw.decode("utf-8"))
            if not isinstance(handles, list):
                raise ValueError(f"tree handle does not contain a list: {handle}")
            return [self.resolve(str(child)) for child in handles]

        if not handle.startswith(LEGACY_MESSAGES_PREFIX):
            cursor = self._conn.execute("SELECT 1 FROM tether_handles WHERE handle = ?", (handle,))
            if cursor.fetchone() is None:
                raise ValueError(f"unknown handle prefix: {handle}")

        cursor = self._conn.execute(
            "SELECT lc_bytes, expires_at, owner, sender FROM tether_handles WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()
        if not row:
            raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}")

        if row["expires_at"]:
            expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                raise E_HANDLE_EXPIRED(f"Handle expired: {handle}")

        if row["owner"] and for_agent:
            is_recipient = row["owner"] == for_agent
            is_sender = row["sender"] and row["sender"] == for_agent
            if not is_recipient and not is_sender:
                raise E_ACCESS_DENIED(f"Handle belongs to '{row['owner']}', not '{for_agent}'")

        # Mark as read
        if for_agent:
            self.mark_read(handle, for_agent)

        return _decode_resilient(row["lc_bytes"])

    def mark_read(self, handle: str, agent: str):
        """Mark a handle as read by an agent."""
        self._conn.execute(
            "INSERT OR IGNORE INTO tether_reads (handle, agent) VALUES (?, ?)",
            (handle, agent)
        )
        self._conn.commit()

    def close_handle(self, handle: Optional[str] = None, ticket_id: Optional[str] = None, 
                     status: str = 'completed', reason: Optional[str] = None):
        """Update the status of a handle or all open handles for a ticket (T-001/T-002)."""
        if handle:
            self._conn.execute(
                "UPDATE tether_handles SET status = ? WHERE handle = ?",
                (status, handle)
            )
        elif ticket_id:
            self._conn.execute(
                "UPDATE tether_handles SET status = ? WHERE ticket_id = ? AND status = 'open'",
                (status, ticket_id)
            )
        self._conn.commit()

    def auto_stale_messages(self, agent: str):
        """Mark unread messages older than 48h as stale (T-001)."""
        self._conn.execute("""
            UPDATE tether_handles 
            SET status = 'stale' 
            WHERE table_name = 'messages' 
              AND owner = ? 
              AND status = 'open' 
              AND created_at < datetime('now', '-48 hours')
              AND handle NOT IN (SELECT handle FROM tether_reads WHERE agent = ?)
        """, (agent, agent))
        self._conn.commit()

    def metadata(self, handle: str, for_agent: Optional[str] = None) -> Dict[str, Any]:
        """Get metadata for a handle, including read status."""
        cursor = self._conn.execute(
            "SELECT h.table_name, h.created_at, h.expires_at, h.owner, h.tags, h.status, h.ticket_id, r.read_at "
            "FROM tether_handles h "
            "LEFT JOIN tether_reads r ON h.handle = r.handle AND r.agent = ? "
            "WHERE h.handle = ?",
            (for_agent, handle)
        )
        row = cursor.fetchone()
        if not row:
            raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}")
        
        return {
            "handle": handle,
            "table": row["table_name"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "owner": row["owner"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "status": row["status"],
            "ticket_id": row["ticket_id"],
            "read": row["read_at"] is not None,
            "read_at": row["read_at"]
        }
    
    def snapshot(self, table: str, tag: Optional[str] = None, include_closed: bool = True) -> Dict[str, Any]:
        """Get all non-expired handles and values in a table."""
        query = "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ? AND (expires_at IS NULL OR expires_at > datetime('now'))"
        params = [table]
        
        if not include_closed:
            query += " AND status = 'open'"

        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")
            
        result = {}
        cursor = self._conn.execute(query, params)
        for row in cursor:
            result[row["handle"]] = _decode_resilient(row["lc_bytes"])
        return result
    
    def tables(self) -> list[str]:
        cursor = self._conn.execute("SELECT table_name FROM tether_tables")
        return [row["table_name"] for row in cursor]
    
    def handles(self, table: str) -> list[str]:
        cursor = self._conn.execute("SELECT handle FROM tether_handles WHERE table_name = ?", (table,))
        return [row["handle"] for row in cursor]
    
    def export_table(self, table: str) -> Dict[str, bytes]:
        """Export table as raw LC-B bytes for cross-LLM transfer."""
        result = {}
        cursor = self._conn.execute(
            "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ?", (table,)
        )
        for row in cursor:
            result[row["handle"]] = row["lc_bytes"]
        return result

    def import_table(self, table: str, data: Dict[str, bytes]):
        """Import table from raw LC-B bytes."""
        self._conn.execute(
            "INSERT OR IGNORE INTO tether_tables (table_name) VALUES (?)", (table,)
        )
        for handle, lc_bytes in data.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes) VALUES (?, ?, ?)",
                (handle, table, lc_bytes)
            )
        self._conn.commit()

    # ── Tasks → extracted to tasks_mixin.py (TasksMixin) ─────────────────────────

    # ── Ping Endpoints (v1.6) ─────────────────────────────────────────────────

    def set_ping_url(self, agent: str, url: str, enabled: bool = True):
        """Register or update a ping endpoint for an agent."""
        self._conn.execute(
            "INSERT INTO tether_ping_endpoints (agent, url, enabled) VALUES (?, ?, ?) "
            "ON CONFLICT(agent) DO UPDATE SET url=excluded.url, enabled=excluded.enabled",
            (agent, url, 1 if enabled else 0)
        )
        self._conn.commit()

    def get_ping_url(self, agent: str) -> Optional[str]:
        """Return the ping URL for an agent if registered and enabled, else None."""
        row = self._conn.execute(
            "SELECT url FROM tether_ping_endpoints WHERE agent = ? AND enabled = 1",
            (agent,)
        ).fetchone()
        return row[0] if row else None

    def set_ping_enabled(self, agent: str, enabled: bool):
        """Toggle ping on/off for an agent without changing the URL."""
        self._conn.execute(
            "UPDATE tether_ping_endpoints SET enabled = ? WHERE agent = ?",
            (1 if enabled else 0, agent)
        )
        self._conn.commit()

    def get_ping_status(self, agent: str) -> Optional[dict]:
        """Return ping registration status for an agent."""
        row = self._conn.execute(
            "SELECT url, enabled FROM tether_ping_endpoints WHERE agent = ?",
            (agent,)
        ).fetchone()
        return {"agent": agent, "url": row[0], "enabled": bool(row[1])} if row else None

    # ── Multiplexer Presence + Routes (v2.0) ─────────────────────────────────

    def presence_register(self, agent: str, pid: int | None = None, ping_port: int | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO tether_presence (agent, status, pid, ping_port, last_heartbeat, registered_at) "
            "VALUES (?, 'online', ?, ?, ?, ?) "
            "ON CONFLICT(agent) DO UPDATE SET status='online', pid=excluded.pid, "
            "ping_port=excluded.ping_port, last_heartbeat=excluded.last_heartbeat",
            (agent, pid, ping_port, now, now),
        )
        self._conn.commit()

    def presence_heartbeat(self, agent: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE tether_presence SET last_heartbeat=?, status='online' WHERE agent=?",
            (now, agent),
        )
        self._conn.commit()

    def presence_offline(self, agent: str) -> None:
        self._conn.execute(
            "UPDATE tether_presence SET status='offline', pid=NULL WHERE agent=?",
            (agent,),
        )
        self._conn.commit()

    def presence_list(self, stale_seconds: int = 15) -> list[dict]:
        rows = self._conn.execute(
            "SELECT agent, status, pid, ping_port, last_heartbeat, registered_at FROM tether_presence"
        ).fetchall()
        now = datetime.now(timezone.utc)
        result = []
        for row in rows:
            hb = row["last_heartbeat"]
            live = False
            if hb and row["status"] == "online":
                try:
                    from datetime import datetime as _dt
                    hb_dt = _dt.fromisoformat(hb.replace("Z", "+00:00"))
                    if hb_dt.tzinfo is None:
                        from datetime import timezone as _tz
                        hb_dt = hb_dt.replace(tzinfo=_tz.utc)
                    live = (now - hb_dt).total_seconds() < stale_seconds
                except Exception as e:
                    # Malformed heartbeat timestamp — leave `live` at its default (offline).
                    # debug, not warning: this is a per-row hot path; avoid log spam.
                    logging.getLogger(__name__).debug("bad heartbeat ts for %s: %s", row["agent"], e)
            result.append({
                "agent": row["agent"],
                "status": "online" if live else "offline",
                "pid": row["pid"],
                "ping_port": row["ping_port"],
                "last_heartbeat": hb,
                "registered_at": row["registered_at"],
            })
        return result

    def route_create(self, from_agent: str, to_agent: str) -> str:
        import hashlib
        route_id = "route_" + hashlib.sha1(f"{from_agent}:{to_agent}".encode()).hexdigest()[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO tether_routes (id, from_agent, to_agent, status, created_at) VALUES (?, ?, ?, 'active', ?) "
            "ON CONFLICT(id) DO UPDATE SET status='active'",
            (route_id, from_agent, to_agent, now),
        )
        self._conn.commit()
        return route_id

    def route_delete(self, route_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM tether_routes WHERE id=?", (route_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def route_list(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, from_agent, to_agent, status, created_at FROM tether_routes ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def konsole_bind(self, agent: str, service: str, session: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO tether_konsole_bindings (agent, service, session, bound_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(agent) DO UPDATE SET service=excluded.service, session=excluded.session, bound_at=excluded.bound_at",
            (agent, service, session, now),
        )
        self._conn.commit()

    def konsole_unbind(self, agent: str) -> None:
        self._conn.execute("DELETE FROM tether_konsole_bindings WHERE agent=?", (agent,))
        self._conn.commit()

    def konsole_binding(self, agent: str) -> dict | None:
        row = self._conn.execute(
            "SELECT agent, service, session, bound_at FROM tether_konsole_bindings WHERE agent=?",
            (agent,),
        ).fetchone()
        return dict(row) if row else None

    def konsole_bindings(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT agent, service, session, bound_at FROM tether_konsole_bindings"
        ).fetchall()
        return [dict(r) for r in rows]

    def konsole_unbind_all(self) -> None:
        """Drop every konsole binding — used on dashboard startup before re-binding
        from live Konsole state (stale bindings point at closed tabs / dead PIDs)."""
        self._conn.execute("DELETE FROM tether_konsole_bindings")
        self._conn.commit()

    def clear_ping_endpoints(self) -> None:
        """Wipe all ping endpoints. On a fresh dashboard launch every prior URL points
        at a reaped daemon, so we clear and let autowire + agent_servers re-register."""
        self._conn.execute("DELETE FROM tether_ping_endpoints")
        self._conn.commit()

    def presence_all_offline(self) -> None:
        """Mark every agent offline — a soft fresh-slate baseline (keeps the rows)."""
        self._conn.execute("UPDATE tether_presence SET status='offline', pid=NULL")
        self._conn.commit()

    def presence_clear(self) -> None:
        """Delete all presence rows — the hard fresh-slate on dashboard startup. The
        reconcile loop re-adds live Konsole agents and heartbeating SDK agents re-register
        themselves, so the table ends up containing only what is actually live (no stale
        pi/kilo nodes leaking into the Network Graph)."""
        self._conn.execute("DELETE FROM tether_presence")
        self._conn.commit()

    # ── Konsole delivery ACK+retry queue (v2.1) ───────────────────────────────

    def is_read(self, handle: str, agent: str) -> bool:
        """Has `agent` read `handle`? This is the delivery ACK signal — a row lands
        in tether_reads when the agent resolves the handle via tether_receive."""
        row = self._conn.execute(
            "SELECT 1 FROM tether_reads WHERE handle=? AND agent=?", (handle, agent)
        ).fetchone()
        return row is not None

    def konsole_pending_add(self, handle: str, agent: str, line: str,
                            max_attempts: int = 3, interval_seconds: int = 30) -> None:
        """Register a delivery for confirm-and-retry. attempts=1 because the caller injects
        once immediately; the loop takes over after `interval_seconds`. Delivery is normally
        confirmed by reading the handle back off the agent's screen (see konsole_retry), so
        `max_attempts` is only a safety BACKSTOP for a pathological never-landing inject —
        not the primary stop. Re-registering the same (handle, agent) resets it to pending."""
        now = datetime.now(timezone.utc)
        next_at = (now + timedelta(seconds=interval_seconds)).isoformat()
        self._conn.execute(
            "INSERT INTO tether_konsole_pending "
            "(handle, agent, line, attempts, max_attempts, interval_seconds, next_attempt_at, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, 'pending', ?, ?) "
            "ON CONFLICT(handle, agent) DO UPDATE SET "
            "line=excluded.line, attempts=1, max_attempts=excluded.max_attempts, "
            "interval_seconds=excluded.interval_seconds, next_attempt_at=excluded.next_attempt_at, "
            "status='pending', updated_at=excluded.updated_at",
            (handle, agent, line, max_attempts, interval_seconds, next_at,
             now.isoformat(), now.isoformat()),
        )
        self._conn.commit()

    def konsole_pending_due(self) -> list[dict]:
        """Pending deliveries whose next attempt is due."""
        now = datetime.now(timezone.utc).isoformat()
        rows = self._conn.execute(
            "SELECT handle, agent, line, attempts, max_attempts, interval_seconds, next_attempt_at "
            "FROM tether_konsole_pending WHERE status='pending' AND next_attempt_at <= ?",
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]

    def konsole_pending_mark_attempt(self, handle: str, agent: str, interval_seconds: int) -> None:
        """Record a re-injection: bump attempts, schedule the next nudge."""
        now = datetime.now(timezone.utc)
        next_at = (now + timedelta(seconds=interval_seconds)).isoformat()
        self._conn.execute(
            "UPDATE tether_konsole_pending SET attempts=attempts+1, next_attempt_at=?, updated_at=? "
            "WHERE handle=? AND agent=?",
            (next_at, now.isoformat(), handle, agent),
        )
        self._conn.commit()

    def konsole_pending_resolve(self, handle: str, agent: str, status: str) -> None:
        """Close out a delivery: 'acked' (recipient read it) or 'exhausted' (gave up)."""
        self._conn.execute(
            "UPDATE tether_konsole_pending SET status=?, updated_at=? WHERE handle=? AND agent=?",
            (status, datetime.now(timezone.utc).isoformat(), handle, agent),
        )
        self._conn.commit()

    # ── Smart Board (v2.0) ────────────────────────────────────────────────────













    def _check_and_ping_unblocked(self, resolved_ticket_id: str):
        cur = self._conn.execute("SELECT * FROM tickets WHERE status != 'done'")
        for row in cur.fetchall():
            blocked_by = json.loads(row["blocked_by"]) if row["blocked_by"] else []
            if resolved_ticket_id in blocked_by:
                still_blocked = False
                for other_id in blocked_by:
                    if other_id == resolved_ticket_id:
                        continue
                    chk_cur = self._conn.execute("SELECT status FROM tickets WHERE id = ?", (other_id,))
                    chk_row = chk_cur.fetchone()
                    if not chk_row or chk_row["status"] != "done":
                        still_blocked = True
                        break
                if not still_blocked:
                    owner = row["owner"]
                    if owner and owner != "unassigned":
                        self._send_unblock_ping(owner, row["id"])

    def _send_unblock_ping(self, agent: str, ticket_id: str):
        self._fire_ping_sync(
            agent=agent,
            sender="board",
            subject=f"UNBLOCKED: Ticket {ticket_id} is now ready (dependency resolved)",
            handle=""
        )

    def _fire_ping_sync(self, agent: str, sender: str, subject: str, handle: str = ""):
        url = self.get_ping_url(agent)
        if not url:
            return
            
        import urllib.request
        import threading
        payload = {
            "from": sender,
            "to": agent,
            "subject": subject,
            "handle": handle
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            def run_req():
                try:
                    with urllib.request.urlopen(req, timeout=2) as response:
                        response.read()
                except Exception:
                    pass
            threading.Thread(target=run_req, daemon=True).start()
        except Exception:
            pass

    # ── End Ping Endpoints ────────────────────────────────────────────────────

    def delete(self, handle: str) -> bool:
        self._conn.execute("DELETE FROM tether_reads WHERE handle = ?", (handle,))
        cursor = self._conn.execute("DELETE FROM tether_handles WHERE handle = ?", (handle,))
        self._conn.commit()
        return cursor.rowcount > 0



    # ── Channel Management (v2.0) ─────────────────────────────────────────────

    def channel_create(self, name: str, description: str, members: List[str] = None) -> str:
        """Create a new channel with initial members."""
        channel_id = f"chan_{name}_{int(datetime.now(timezone.utc).timestamp())}"
        self._conn.execute(
            "INSERT INTO tether_channels (id, name, description) VALUES (?, ?, ?)",
            (channel_id, name, description)
        )
        
        # Add initial members (defaults to matt_dev if none specified)
        initial_members = members or ['matt_dev']
        for agent in initial_members:
            self._conn.execute(
                "INSERT OR IGNORE INTO tether_channel_members (channel_id, agent) VALUES (?, ?)",
                (channel_id, agent)
            )
        
        self._conn.commit()
        return channel_id

    def channel_join(self, channel_id: str, agent: str) -> bool:
        """Add an agent to a channel."""
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO tether_channel_members (channel_id, agent) VALUES (?, ?)",
            (channel_id, agent)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def channel_leave(self, channel_id: str, agent: str) -> bool:
        """Remove an agent from a channel."""
        cursor = self._conn.execute(
            "DELETE FROM tether_channel_members WHERE channel_id = ? AND agent = ?",
            (channel_id, agent)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def channel_send_message(self, channel_id: str, sender: str, body: str, thread_id: Optional[str] = None) -> str:
        """Send a message to a channel."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate handle ID for the message
        msg_data = f"{sender}:{body}:{timestamp}:{channel_id}:{thread_id or ''}"
        import hashlib
        handle_id = hashlib.blake2b(msg_data.encode(), digest_size=6).hexdigest()
        handle = f"h&l_chan_{handle_id}"

        # Store the message
        self._conn.execute(
            "INSERT INTO tether_channel_messages (id, channel_id, sender, body, timestamp, thread_id) VALUES (?, ?, ?, ?, ?, ?)",
            (handle, channel_id, sender, body, timestamp, thread_id)
        )
        self._conn.commit()
        
        return handle

    def channel_get_messages(self, channel_id: str, limit: int = 100, offset: int = 0) -> List[dict]:
        """Get messages for a channel with pagination."""
        cursor = self._conn.execute(
            """
            SELECT id, sender, body, timestamp, thread_id
            FROM tether_channel_messages
            WHERE channel_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (channel_id, limit, offset)
        )
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "id": row["id"],
                "sender": row["sender"],
                "body": row["body"],
                "timestamp": row["timestamp"],
                "thread_id": row["thread_id"]
            })
        return messages

    def channel_list(self) -> List[dict]:
        """Get all channels with their member counts."""
        cursor = self._conn.execute(
            """
            SELECT c.id, c.name, c.description, c.created_at,
                   COUNT(m.agent) as member_count
            FROM tether_channels c
            LEFT JOIN tether_channel_members m ON c.id = m.channel_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )
        
        channels = []
        for row in cursor.fetchall():
            channels.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "created_at": row["created_at"],
                "member_count": row["member_count"]
            })
        return channels

    # ── End Channel Management ────────────────────────────────────────────────
    
    def close(self):
        self._conn.close()
    
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
