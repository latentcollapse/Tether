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
            
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_handles_table ON tether_handles(table_name)")
        self._conn.commit()
    
    def _compute_handle_id(self, data: bytes) -> str:
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str, value: Any, ttl_seconds: Optional[int] = None, 
                 owner: Optional[str] = None, tags: Optional[List[str]] = None) -> str:
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
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes, expires_at, owner, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (handle, table, lc_bytes, expires_at, owner, tags_str)
        )
        self._conn.commit()
        return handle
    
    def resolve(self, handle: str, for_agent: Optional[str] = None) -> Any:
        """Resolve a handle. Automatically marks as read if for_agent is provided."""
        if not handle.startswith("h&l_"):
            raise E_HANDLE_INVALID(f"Invalid handle format: {handle}")

        cursor = self._conn.execute(
            "SELECT lc_bytes, expires_at, owner FROM tether_handles WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()
        if not row:
            raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}")

        if row["expires_at"]:
            expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                raise E_HANDLE_EXPIRED(f"Handle expired: {handle}")

        if row["owner"] and for_agent and row["owner"] != for_agent:
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

    def delete(self, handle: str) -> bool:
        self._conn.execute("DELETE FROM tether_reads WHERE handle = ?", (handle,))
        cursor = self._conn.execute("DELETE FROM tether_handles WHERE handle = ?", (handle,))
        self._conn.commit()
        return cursor.rowcount > 0
    
    def close(self):
        self._conn.close()
    
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
