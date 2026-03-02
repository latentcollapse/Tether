"""SQLite-backed Tether Runtime for persistent storage."""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from pathlib import Path
from .lc import encode_lc_b, decode_lc_b
from .exceptions import E_HANDLE_INVALID, E_HANDLE_UNRESOLVED, E_LC_BINARY_DECODE, E_HANDLE_EXPIRED, E_ACCESS_DENIED
from .runtime import json_to_contract, contract_to_json, CONTRACT_JSON


def _decode_resilient(lc_bytes: bytes) -> Any:
    """Decode LC-B bytes, falling back to JSON if decoding fails.

    Handles messages written by models that bypass the encoder and store
    raw JSON directly (e.g. via direct SQLite access).
    """
    try:
        contract_value = decode_lc_b(lc_bytes)
        return contract_to_json(contract_value)
    except (E_LC_BINARY_DECODE, Exception):
        # Fall back: try to find JSON in the raw bytes
        try:
            # Strip leading non-JSON bytes until we hit '{' or '['
            for i, b in enumerate(lc_bytes):
                if b in (0x7B, 0x5B):  # '{' or '['
                    return json.loads(lc_bytes[i:].decode("utf-8", errors="replace"))
            # Try the whole thing as JSON string
            return json.loads(lc_bytes.decode("utf-8", errors="replace"))
        except Exception:
            # Last resort: return raw as string
            return lc_bytes.decode("utf-8", errors="replace")


class SQLiteRuntime:
    """
    Tether Runtime with SQLite backing store.
    
    Handles persist across restarts - perfect for long-running LLM sessions.
    
    Example:
        rt = SQLiteRuntime("tether.db")
        
        # Collapsing stores to SQLite
        handle = rt.collapse("messages", {"role": "system", "content": "..."})
        
        # After restart, handles still resolve
        rt2 = SQLiteRuntime("tether.db")
        value = rt2.resolve(handle)  # Works!
    """
    
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
                FOREIGN KEY (table_name) REFERENCES tether_tables(table_name)
            )
        """)
        # Migrate existing DBs that predate these columns
        for col, defn in [("expires_at", "TIMESTAMP NULL"), ("owner", "TEXT NULL")]:
            try:
                self._conn.execute(f"ALTER TABLE tether_handles ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_handles_table
            ON tether_handles(table_name)
        """)
        self._conn.commit()
    
    def _compute_handle_id(self, data: bytes) -> str:
        """Compute deterministic handle ID from content."""
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str, value: Any, ttl_seconds: Optional[int] = None, owner: Optional[str] = None) -> str:
        """
        Collapse a value into a handle in the specified table.
        Persists to SQLite.

        Args:
            ttl_seconds: If set, handle expires this many seconds from now.
            owner: If set, only this agent can resolve the handle via tether_receive.
        """
        # Ensure table exists
        self._conn.execute(
            "INSERT OR IGNORE INTO tether_tables (table_name) VALUES (?)",
            (table,)
        )

        # Convert to contract and encode
        contract_value = json_to_contract(value)
        lc_bytes = encode_lc_b(contract_value)
        handle_id = self._compute_handle_id(lc_bytes)
        handle = f"h&l_{table}_{handle_id}"

        expires_at = None
        if ttl_seconds is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        # Store in SQLite
        self._conn.execute(
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes, expires_at, owner) VALUES (?, ?, ?, ?, ?)",
            (handle, table, lc_bytes, expires_at, owner)
        )
        self._conn.commit()

        return handle
    
    def resolve(self, handle: str, for_agent: Optional[str] = None) -> Any:
        """
        Resolve a handle from SQLite.

        Args:
            for_agent: If provided and the handle has an owner, access is denied
                       unless for_agent matches the owner.
        """
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

        return _decode_resilient(row["lc_bytes"])
    
    def get(self, handle: str, default: Any = None) -> Any:
        """Resolve with default if not found."""
        try:
            return self.resolve(handle)
        except E_HANDLE_UNRESOLVED:
            return default
    
    def snapshot(self, table: str) -> Dict[str, Any]:
        """Get all non-expired handles and values in a table."""
        result = {}
        cursor = self._conn.execute(
            "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ? "
            "AND (expires_at IS NULL OR expires_at > datetime('now'))",
            (table,)
        )
        for row in cursor:
            result[row["handle"]] = _decode_resilient(row["lc_bytes"])
        return result
    
    def tables(self) -> list[str]:
        """List all table names."""
        cursor = self._conn.execute("SELECT table_name FROM tether_tables")
        return [row["table_name"] for row in cursor]
    
    def handles(self, table: str) -> list[str]:
        """List all handles in a table."""
        cursor = self._conn.execute(
            "SELECT handle FROM tether_handles WHERE table_name = ?",
            (table,)
        )
        return [row["handle"] for row in cursor]
    
    def export_table(self, table: str) -> Dict[str, bytes]:
        """Export table as LC-B bytes."""
        result = {}
        cursor = self._conn.execute(
            "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ?",
            (table,)
        )
        for row in cursor:
            result[row["handle"]] = row["lc_bytes"]
        return result
    
    def import_table(self, table: str, data: Dict[str, bytes]):
        """Import table from LC-B bytes."""
        # Ensure table exists
        self._conn.execute(
            "INSERT OR IGNORE INTO tether_tables (table_name) VALUES (?)",
            (table,)
        )
        
        for handle, lc_bytes in data.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes) VALUES (?, ?, ?)",
                (handle, table, lc_bytes)
            )
        self._conn.commit()
    
    def delete(self, handle: str) -> bool:
        """Delete a handle."""
        cursor = self._conn.execute(
            "DELETE FROM tether_handles WHERE handle = ?",
            (handle,)
        )
        self._conn.commit()
        return cursor.rowcount > 0
    
    def close(self):
        """Close database connection."""
        self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
