"""SQLite-backed Tether Runtime for persistent storage."""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List
from pathlib import Path
from .lc import encode_lc_b, decode_lc_b
from .exceptions import E_HANDLE_INVALID, E_HANDLE_UNRESOLVED, E_LC_BINARY_DECODE, E_HANDLE_EXPIRED, E_ACCESS_DENIED
from .runtime import json_to_contract, contract_to_json, CONTRACT_JSON


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


class SQLiteRuntime:
    """Tether Runtime with SQLite backing store."""
    
    def __init__(self, db_path: str = "tether.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
    
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

        # Ping endpoints (v1.6)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_ping_endpoints (
                agent TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
        """)

        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_handles_table ON tether_handles(table_name)")
        self._conn.commit()
        self._init_tasks_db()

    def _init_tasks_db(self):
        """Initialize shared task board tables (v1.5)."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'p1',
                assignee TEXT DEFAULT 'unassigned',
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                tags TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tether_tasks(id)
            )
        """)
        self._conn.commit()
    
    def _compute_handle_id(self, data: bytes) -> str:
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str, value: Any, ttl_seconds: Optional[int] = None,
                 owner: Optional[str] = None, tags: Optional[List[str]] = None,
                 sender: Optional[str] = None) -> str:
        """Collapse a value into a handle."""
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
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes, expires_at, owner, tags, sender) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (handle, table, lc_bytes, expires_at, owner, tags_str, sender)
        )
        self._conn.commit()
        return handle
    
    def resolve(self, handle: str, for_agent: Optional[str] = None) -> Any:
        """Resolve a handle. Automatically marks as read if for_agent is provided."""
        if not handle.startswith("h&l_"):
            raise E_HANDLE_INVALID(f"Invalid handle format: {handle}")

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

    def metadata(self, handle: str, for_agent: Optional[str] = None) -> Dict[str, Any]:
        """Get metadata for a handle, including read status."""
        cursor = self._conn.execute(
            "SELECT h.table_name, h.created_at, h.expires_at, h.owner, h.tags, r.read_at "
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
            "read": row["read_at"] is not None,
            "read_at": row["read_at"]
        }
    
    def snapshot(self, table: str, tag: Optional[str] = None) -> Dict[str, Any]:
        """Get all non-expired handles and values in a table."""
        query = "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ? AND (expires_at IS NULL OR expires_at > datetime('now'))"
        params = [table]
        
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

    # ── Task Board (v1.5) ─────────────────────────────────────────────────────

    def task_create(self, id: str, title: str, description: str = '',
                    priority: str = 'p1', assignee: str = 'unassigned',
                    created_by: str = 'unknown', tags: Optional[List[str]] = None) -> dict:
        """Create a new task. Raises ValueError if id already exists."""
        now = datetime.now(timezone.utc).isoformat()
        tags_str = ','.join(tags) if tags else ''
        self._conn.execute(
            "INSERT INTO tether_tasks "
            "(id, title, description, status, priority, assignee, created_by, created_at, updated_at, tags) "
            "VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)",
            (id, title, description, priority, assignee, created_by, now, now, tags_str)
        )
        self._conn.commit()
        return self.task_get(id)

    def task_update(self, id: str, status: Optional[str] = None,
                    priority: Optional[str] = None, assignee: Optional[str] = None,
                    description: Optional[str] = None, title: Optional[str] = None,
                    tags: Optional[List[str]] = None) -> dict:
        """Update mutable fields on a task."""
        allowed = {'status': status, 'priority': priority, 'assignee': assignee,
                   'description': description, 'title': title}
        updates = {k: v for k, v in allowed.items() if v is not None}
        if tags is not None:
            updates['tags'] = ','.join(tags)
        if not updates:
            return self.task_get(id)
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        self._conn.execute(
            f"UPDATE tether_tasks SET {set_clause} WHERE id = ?",
            list(updates.values()) + [id]
        )
        self._conn.commit()
        return self.task_get(id)

    def task_list(self, status: Optional[str] = None, assignee: Optional[str] = None,
                  priority: Optional[str] = None) -> List[dict]:
        """List tasks with optional filters. Returns summary rows (no comments)."""
        query = "SELECT * FROM tether_tasks WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"; params.append(status)
        if assignee:
            query += " AND assignee = ?"; params.append(assignee)
        if priority:
            query += " AND priority = ?"; params.append(priority)
        query += " ORDER BY priority ASC, created_at ASC"
        tasks = []
        for row in self._conn.execute(query, params):
            t = dict(row)
            t['tags'] = [x for x in t['tags'].split(',') if x] if t['tags'] else []
            tasks.append(t)
        return tasks

    def task_get(self, id: str) -> dict:
        """Get a single task with full comment history."""
        cursor = self._conn.execute("SELECT * FROM tether_tasks WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Task not found: {id}")
        task = dict(row)
        task['tags'] = [x for x in task['tags'].split(',') if x] if task['tags'] else []
        comments_cursor = self._conn.execute(
            "SELECT author, text, created_at FROM tether_task_comments "
            "WHERE task_id = ? ORDER BY created_at ASC", (id,)
        )
        task['comments'] = [dict(c) for c in comments_cursor]
        return task

    def task_comment(self, id: str, author: str, text: str) -> dict:
        """Append a comment to a task. Bumps updated_at on the task."""
        self.task_get(id)  # raises if not found
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO tether_task_comments (task_id, author, text, created_at) VALUES (?, ?, ?, ?)",
            (id, author, text, now)
        )
        self._conn.execute("UPDATE tether_tasks SET updated_at = ? WHERE id = ?", (now, id))
        self._conn.commit()
        return self.task_get(id)

    # ── End Task Board ────────────────────────────────────────────────────────

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

    # ── End Ping Endpoints ────────────────────────────────────────────────────

    def delete(self, handle: str) -> bool:
        self._conn.execute("DELETE FROM tether_reads WHERE handle = ?", (handle,))
        cursor = self._conn.execute("DELETE FROM tether_handles WHERE handle = ?", (handle,))
        self._conn.commit()
        return cursor.rowcount > 0
    
    def close(self):
        self._conn.close()
    
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
