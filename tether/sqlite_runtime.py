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


class SQLiteRuntime:
    """Tether Runtime with SQLite backing store."""
    
    def __init__(self, db_path: str = "tether.db"):
        self.db_path = db_path
        self._kvfold_dir = kvfold_dir(Path("kvfold"))
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

        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_handles_table ON tether_handles(table_name)")
        self._conn.commit()
        self._init_tasks_db()
        self._init_smart_board_db()

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

    def _init_smart_board_db(self):
        """Initialize smart board tables (v2.0)."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS counters (
                category TEXT PRIMARY KEY,
                next INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                tier TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                owner TEXT,
                batch TEXT,
                principle TEXT,  -- JSON list
                bible_ref TEXT,  -- JSON list
                gate TEXT,
                blocks TEXT,      -- JSON list
                blocked_by TEXT,  -- JSON list
                work_done TEXT,
                implementers TEXT -- JSON list
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS changelog (
                id TEXT,
                category TEXT,
                tier TEXT,
                title TEXT,
                description TEXT,
                work_done TEXT,
                handle TEXT,
                summary TEXT,
                completed_by TEXT,
                completed_at TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS whiteboard (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

        # Seed default whiteboard if empty
        cursor = self._conn.execute("SELECT COUNT(*) FROM whiteboard")
        if cursor.fetchone()[0] == 0:
            default_content = """# 💡 Tether Whiteboard

Welcome to your team scratchpad! Use this space to collaborate, draft code, or coordinate tasks.

### Features:
1. **Auto-Save**: Everything you type here auto-saves and syncs in real-time.
2. **Ticket Synthesis**: Highlight any selection of text on this board and click **"Synthesize Ticket"** to instantly propose a new Debt (D) ticket.

-- Tether coordination layer"""
            self._conn.execute("INSERT INTO whiteboard (id, content) VALUES ('main', ?)", (default_content,))
            self._conn.commit()
    
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

    # ── Smart Board (v2.0) ────────────────────────────────────────────────────

    def sync_board_projection(self):
        """Reconstruct tickets and changelog tables from the 'board' event log."""
        cursor = self._conn.execute(
            "SELECT handle, lc_bytes, created_at, sender FROM tether_handles WHERE table_name = 'board'"
        )
        events = []
        for row in cursor.fetchall():
            handle_str = row["handle"]
            try:
                from .lc import decode_lc_b
                from .runtime import contract_to_json
                contract_val = decode_lc_b(row["lc_bytes"])
                event_data = contract_to_json(contract_val)
            except Exception:
                try:
                    event_data = json.loads(row["lc_bytes"].decode("utf-8"))
                except Exception:
                    continue
            
            event_data["handle"] = handle_str
            if "timestamp" not in event_data:
                event_data["timestamp"] = row["created_at"]
            if "actor" not in event_data:
                event_data["actor"] = row["sender"] or "unknown"
            events.append(event_data)
            
        events.sort(key=lambda x: x.get("timestamp", ""))
        
        tickets_map = {}
        changelog_list = []
        
        for ev in events:
            ev_type = ev.get("type")
            ticket_id = ev.get("ticket_id")
            actor = ev.get("actor", "unknown")
            timestamp = ev.get("timestamp")
            
            if ev_type == "propose":
                prop_id = ev.get("handle")
                ticket_data = ev.get("ticket", {}).copy()
                ticket_data.update({
                    "id": prop_id,
                    "status": "proposed",
                    "implementers": [],
                    "work_done": "",
                    "owner": ""
                })
                tickets_map[prop_id] = ticket_data
                
            elif ev_type == "accept":
                prop_id = ev.get("proposed_id")
                real_id = ev.get("ticket_id")
                if prop_id in tickets_map:
                    ticket_data = tickets_map.pop(prop_id)
                    tier = ev.get("tier") or ticket_data.get("tier", "blue")
                    if tier in ["grey", "green"]:
                        tier = "blue"
                    ticket_data.update({
                        "id": real_id,
                        "status": "open",
                        "tier": tier
                    })
                    tickets_map[real_id] = ticket_data
                else:
                    ticket_data = ev.get("ticket", {}).copy()
                    tier = ticket_data.get("tier", "blue")
                    if tier in ["grey", "green"]:
                        tier = "blue"
                    ticket_data.update({
                        "id": real_id,
                        "status": "open",
                        "tier": tier,
                        "implementers": [],
                        "work_done": "",
                        "owner": ""
                    })
                    tickets_map[real_id] = ticket_data
                    
            elif ev_type == "create":
                ticket_data = ev.get("ticket", {}).copy()
                initial_status = ticket_data.get("status", "open")
                tier = ticket_data.get("tier", "blue")
                if tier in ["grey", "green"]:
                    tier = "blue"
                ticket_data.update({
                    "id": ticket_id,
                    "status": initial_status,
                    "tier": tier,
                    "implementers": [],
                    "work_done": "",
                    "owner": ""
                })
                tickets_map[ticket_id] = ticket_data
                
            elif ev_type == "claim":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    t["status"] = "active"
                    t["owner"] = actor
                    impls = t.get("implementers", [])
                    if actor not in impls:
                        impls.append(actor)
                    t["implementers"] = impls
                    
            elif ev_type == "flag":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    t["status"] = "ready"
                    t["work_done"] = ev.get("work_done", "")
                    impls = t.get("implementers", [])
                    if actor not in impls:
                        impls.append(actor)
                    t["implementers"] = impls
                    
            elif ev_type == "finalize":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    if t.get("category", "").upper() != "S":
                        t["status"] = "done"
                        tier = t.get("tier", "blue")
                        if tier in ["grey", "green"]:
                            tier = "blue"
                        changelog_list.append({
                            "id": ticket_id,
                            "category": t.get("category", ""),
                            "tier": tier,
                            "title": t.get("title", ""),
                            "description": t.get("description", ""),
                            "work_done": t.get("work_done", ""),
                            "handle": ev.get("changelog_handle", ""),
                            "summary": f"Completed {ticket_id}",
                            "completed_by": actor,
                            "completed_at": timestamp
                        })
            elif ev_type == "dormant":
                if ticket_id in tickets_map:
                    tickets_map[ticket_id]["status"] = "dormant"
            elif ev_type == "revive":
                if ticket_id in tickets_map:
                    tickets_map[ticket_id]["status"] = "open"
            elif ev_type == "update":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    t.update(ev.get("fields", {}))
                    
        self._conn.execute("DELETE FROM tickets")
        self._conn.execute("DELETE FROM changelog")
        
        for tid, t in tickets_map.items():
            tier = t.get("tier", "blue")
            if tier in ["grey", "green"]:
                tier = "blue"
            self._conn.execute(
                """
                INSERT INTO tickets (id, category, tier, title, description, status, owner, batch, principle, bible_ref, gate, blocks, blocked_by, work_done, implementers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    t.get("category", ""),
                    tier,
                    t.get("title", ""),
                    t.get("description", ""),
                    t.get("status", "open"),
                    t.get("owner", ""),
                    t.get("batch", ""),
                    json.dumps(t.get("principle", [])),
                    json.dumps(t.get("bible_ref", [])),
                    t.get("gate", ""),
                    json.dumps(t.get("blocks", [])),
                    json.dumps(t.get("blocked_by", [])),
                    t.get("work_done", ""),
                    json.dumps(t.get("implementers", []))
                )
            )
            
        for c in changelog_list:
            self._conn.execute(
                """
                INSERT INTO changelog (id, category, tier, title, description, work_done, handle, summary, completed_by, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c["id"],
                    c["category"],
                    c["tier"],
                    c["title"],
                    c["description"],
                    c["work_done"],
                    c["handle"],
                    c["summary"],
                    c["completed_by"],
                    c["completed_at"]
                )
            )
        self._conn.commit()

    def board_query(self, category=None, tier=None, status=None, owner=None, batch=None, sort="newest"):
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if tier:
            query += " AND tier = ?"
            params.append(tier)
        if status:
            query += " AND status = ?"
            params.append(status)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if batch:
            query += " AND batch = ?"
            params.append(batch)
            
        if sort == "newest":
            query += " ORDER BY id DESC"
        elif sort == "oldest":
            query += " ORDER BY id ASC"
            
        cur = self._conn.execute(query, params)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["principle"] = json.loads(d["principle"]) if d["principle"] else []
            d["bible_ref"] = json.loads(d["bible_ref"]) if d["bible_ref"] else []
            d["blocks"] = json.loads(d["blocks"]) if d["blocks"] else []
            d["blocked_by"] = json.loads(d["blocked_by"]) if d["blocked_by"] else []
            d["implementers"] = json.loads(d["implementers"]) if d["implementers"] else []
            rows.append(d)
        return rows

    def board_changelog_query(self, query_str=None):
        query = "SELECT * FROM changelog WHERE 1=1"
        params = []
        if query_str:
            query += " AND (id LIKE ? OR title LIKE ? OR description LIKE ?)"
            lk = f"%{query_str}%"
            params.extend([lk, lk, lk])
        query += " ORDER BY completed_at DESC"
        cur = self._conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def board_propose(self, category: str, tier: str, title: str, description: str, actor: str) -> str:
        event_data = {
            "type": "propose",
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticket": {
                "category": category.upper(),
                "tier": tier,
                "title": title,
                "description": description,
                "status": "proposed"
            }
        }
        handle = self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return handle

    def board_accept(self, proposed_id: str, actor: str, tier: Optional[str] = None) -> str:
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (proposed_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Proposed ticket not found: {proposed_id}")
        if row["status"] != "proposed":
            raise ValueError(f"Ticket is not in proposed state: {row['status']}")
            
        category = row["category"]
        real_id = self._issue_next_id(category)
        
        event_data = {
            "type": "accept",
            "proposed_id": proposed_id,
            "ticket_id": real_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier": tier or row["tier"]
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return real_id

    def board_author(self, category: str, tier: str, title: str, description: str, actor: str,
                     batch: Optional[str] = None, principle: Optional[List[str]] = None,
                     bible_ref: Optional[List[str]] = None, gate: Optional[str] = None,
                     blocks: Optional[List[str]] = None, blocked_by: Optional[List[str]] = None,
                     status: str = "open") -> str:
         real_id = self._issue_next_id(category)
         ticket = {
             "category": category.upper(),
             "tier": tier,
             "title": title,
             "description": description,
             "status": status,
             "batch": batch or "",
             "principle": principle or [],
             "bible_ref": bible_ref or [],
             "gate": gate or "",
             "blocks": blocks or [],
             "blocked_by": blocked_by or []
         }
         event_data = {
             "type": "create",
             "ticket_id": real_id,
             "actor": actor,
             "timestamp": datetime.now(timezone.utc).isoformat(),
             "ticket": ticket
         }
         self.collapse("board", event_data, sender=actor)
         self.sync_board_projection()
         return real_id

    def _issue_next_id(self, category: str) -> str:
        category = category.upper()
        self._conn.execute("INSERT OR IGNORE INTO counters (category, next) VALUES (?, 1)", (category,))
        self._conn.execute("UPDATE counters SET next = next + 1 WHERE category = ?", (category,))
        cur = self._conn.execute("SELECT next - 1 FROM counters WHERE category = ?", (category,))
        num = cur.fetchone()[0]
        return f"{category}-{num}"

    def board_claim(self, ticket_id: str, actor: str) -> bool:
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        if row["status"] != "open":
            raise ValueError(f"Ticket {ticket_id} is not open (status: {row['status']})")
            
        event_data = {
            "type": "claim",
            "ticket_id": ticket_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return True

    def board_flag(self, ticket_id: str, actor: str, work_done: str) -> bool:
        if not work_done.strip():
            raise ValueError("work_done cannot be empty")
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        if row["status"] != "active":
            raise ValueError(f"Ticket {ticket_id} is not active (status: {row['status']})")
            
        event_data = {
            "type": "flag",
            "ticket_id": ticket_id,
            "actor": actor,
            "work_done": work_done,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        flag_handle = self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        
        for admin in ["claude", "matt"]:
            self._fire_ping_sync(
                agent=admin,
                sender=actor,
                subject=f"TICKET READY: {ticket_id} — {row['title']}",
                handle=flag_handle
            )
        return True

    def board_finalize(self, ticket_id: str, actor: str) -> str:
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        if row["category"].upper() == "S":
            raise ValueError("Standing Order (category S) tickets have no finalize path.")
        if row["status"] != "ready":
            raise ValueError(f"Ticket {ticket_id} is not ready (status: {row['status']})")
            
        implementers = json.loads(row["implementers"]) if row["implementers"] else []
        if actor in implementers:
            raise ValueError(f"Separation of duties: actor '{actor}' is an implementer of '{ticket_id}' and cannot finalize it.")
            
        work_done = row["work_done"]
        if not work_done or not work_done.strip():
            raise ValueError(f"Cannot finalize: work_done is empty for {ticket_id}")
            
        events_cursor = self._conn.execute(
            "SELECT handle, lc_bytes, created_at, sender FROM tether_handles WHERE table_name = 'board'"
        )
        lineage = []
        for r in events_cursor.fetchall():
            try:
                from .lc import decode_lc_b
                from .runtime import contract_to_json
                contract_val = decode_lc_b(r["lc_bytes"])
                ev = contract_to_json(contract_val)
            except Exception:
                try:
                    ev = json.loads(r["lc_bytes"].decode("utf-8"))
                except Exception:
                    continue
            if ev.get("ticket_id") == ticket_id or ev.get("proposed_id") == ticket_id or ev.get("handle") == r["handle"]:
                ev["handle"] = r["handle"]
                lineage.append(ev)
                
        changelog_handle = self.collapse("changelog_proofs", {"lineage": lineage}, sender=actor)
        
        event_data = {
            "type": "finalize",
            "ticket_id": ticket_id,
            "actor": actor,
            "changelog_handle": changelog_handle,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        
        self._check_and_ping_unblocked(ticket_id)
        return changelog_handle

    def board_dormant(self, ticket_id: str, actor: str) -> bool:
        if actor not in ["claude", "matt"]:
            raise ValueError("Only admins can mark tickets as dormant.")
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        event_data = {
            "type": "dormant",
            "ticket_id": ticket_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return True

    def board_revive(self, ticket_id: str, actor: str) -> bool:
        if actor not in ["claude", "matt"]:
            raise ValueError("Only admins can revive tickets.")
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        event_data = {
            "type": "revive",
            "ticket_id": ticket_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return True

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

    def get_whiteboard(self) -> str:
        cursor = self._conn.execute("SELECT content FROM whiteboard WHERE id = 'main'")
        row = cursor.fetchone()
        if row:
            return row[0]
        return ""

    def update_whiteboard(self, content: str):
        self._conn.execute("""
            INSERT INTO whiteboard (id, content) VALUES ('main', ?)
            ON CONFLICT(id) DO UPDATE SET content = excluded.content, updated_at = CURRENT_TIMESTAMP
        """, (content,))
        self._conn.commit()
    
    def close(self):
        self._conn.close()
    
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
