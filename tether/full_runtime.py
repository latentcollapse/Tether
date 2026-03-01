"""Tether Runtime with integrated transport - the full package."""

import json
from typing import Any, Dict, Optional
from .lc import encode_lc_b, decode_lc_b
from .exceptions import (
    TetherError, 
    E_HANDLE_INVALID, 
    E_HANDLE_UNRESOLVED,
    E_LC_PARSE,
    E_TRANSPORT_ERROR
)
from .transport import Transport, SQLiteTransport, MemoryTransport, create_transport
from .runtime import json_to_contract, contract_to_json, CONTRACT_JSON


class TetherRuntime:
    """
    Full-featured Tether Runtime with storage + transport.
    
    Example:
        rt = TetherRuntime()  # Uses SQLite by default
        
        # Store and send
        rt.send("messages", {"role": "system", "content": "You are helpful."})
        
        # Or just store
        handle = rt.collapse("messages", {"role": "user", "content": "Hello"})
        
        # Receive
        message = rt.receive(handle)
        
        # List pending
        pending = rt.inbox()
    """
    
    def __init__(
        self, 
        db_path: str = "tether.db",
        transport: Transport | None = None
    ):
        self.db_path = db_path
        self._transport = transport or SQLiteTransport(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize main storage schema."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_tables (
                table_name TEXT PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tether_handles (
                handle TEXT PRIMARY KEY,
                table_name TEXT NOT NULL,
                lc_bytes BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_handles_table 
            ON tether_handles(table_name)
        """)
        conn.commit()
    
    def _get_conn(self):
        """Get SQLite connection from transport if it's SQLite."""
        if hasattr(self._transport, '_conn'):
            return self._transport._conn
        raise E_TRANSPORT_ERROR("Transport must be SQLite-backed for storage")
    
    def _compute_handle_id(self, data: bytes) -> str:
        """Compute deterministic handle ID from content."""
        import hashlib
        try:
            import blake3
            return blake3.blake3(data).hexdigest()[:12]
        except ImportError:
            return hashlib.blake2b(data, digest_size=6).hexdigest()
    
    def collapse(self, table: str, value: Any) -> str:
        """
        Collapse a value into a handle in storage.
        
        Args:
            table: Table name (e.g., 'messages', 'context')
            value: JSON-compatible Python value
            
        Returns:
            Handle string like &h_messages_abc123
            
        Raises:
            E_LC_PARSE: If value can't be encoded
        """
        conn = self._get_conn()
        
        # Ensure table exists
        conn.execute(
            "INSERT OR IGNORE INTO tether_tables (table_name) VALUES (?)",
            (table,)
        )
        
        # Convert to contract and encode
        try:
            contract_value = json_to_contract(value)
            lc_bytes = encode_lc_b(contract_value)
        except Exception as e:
            raise E_LC_PARSE(f"Failed to encode value: {e}")
        
        handle_id = self._compute_handle_id(lc_bytes)
        handle = f"h&l_{table}_{handle_id}"
        
        # Store
        conn.execute(
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes) VALUES (?, ?, ?)",
            (handle, table, lc_bytes)
        )
        conn.commit()
        
        return handle
    
    def send(self, table: str, value: Any) -> str:
        """
        Collapse and queue for send in one step.
        
        Shorthand for collapse() + queue for transfer.
        
        Args:
            table: Table to store in
            value: Value to send
            
        Returns:
            Handle that recipient can resolve
        """
        handle = self.collapse(table, value)
        
        # Get the LC bytes and queue for transport
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT lc_bytes FROM tether_handles WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()
        if row:
            self._transport.send(handle, row[0])
        
        return handle
    
    def receive(self, handle: str) -> Any:
        """
        Receive and resolve a handle in one step.
        
        Combines transport receive + storage resolve.
        
        Args:
            handle: Handle to receive
            
        Returns:
            Original value
            
        Raises:
            E_HANDLE_UNRESOLVED: Handle not found
        """
        # First try transport queue
        data = self._transport.receive(handle)
        if data is None:
            # Try storage directly
            return self.resolve(handle)
        
        # Store and resolve
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes) VALUES (?, ?, ?)",
            (handle, "received", data)
        )
        conn.commit()
        
        return self.resolve(handle)
    
    def resolve(self, handle: str) -> Any:
        """Resolve a handle to its value."""
        if not handle.startswith("h&l_"):
            raise E_HANDLE_INVALID(f"Invalid handle format: {handle}")
        
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT lc_bytes FROM tether_handles WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise E_HANDLE_UNRESOLVED(f"Handle not found: {handle}")
        
        contract_value = decode_lc_b(row[0])
        return contract_to_json(contract_value)
    
    def get(self, handle: str, default: Any = None) -> Any:
        """Resolve with default if not found."""
        try:
            return self.resolve(handle)
        except E_HANDLE_UNRESOLVED:
            return default
    
    def inbox(self) -> list[str]:
        """List all pending handles in transport queue."""
        return self._transport.list_pending()
    
    def tables(self) -> list[str]:
        """List all table names."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT table_name FROM tether_tables")
        return [row[0] for row in cursor]
    
    def handles(self, table: str) -> list[str]:
        """List all handles in a table."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT handle FROM tether_handles WHERE table_name = ?",
            (table,)
        )
        return [row[0] for row in cursor]
    
    def snapshot(self, table: str) -> Dict[str, Any]:
        """Get all handles and values in a table."""
        result = {}
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ?",
            (table,)
        )
        for row in cursor:
            contract_value = decode_lc_b(row[1])
            result[row[0]] = contract_to_json(contract_value)
        return result
    
    def export_table(self, table: str) -> Dict[str, bytes]:
        """Export table as LC-B bytes."""
        result = {}
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT handle, lc_bytes FROM tether_handles WHERE table_name = ?",
            (table,)
        )
        for row in cursor:
            result[row[0]] = row[1]
        return result
    
    def import_table(self, table: str, data: Dict[str, bytes]):
        """Import table from LC-B bytes."""
        conn = self._get_conn()
        
        # Ensure table exists
        conn.execute(
            "INSERT OR IGNORE INTO tether_tables (table_name) VALUES (?)",
            (table,)
        )
        
        for handle, lc_bytes in data.items():
            conn.execute(
                "INSERT OR REPLACE INTO tether_handles (handle, table_name, lc_bytes) VALUES (?, ?, ?)",
                (handle, table, lc_bytes)
            )
        conn.commit()
    
    def close(self):
        """Close the runtime."""
        if hasattr(self._transport, 'close'):
            self._transport.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Backwards compatibility
Runtime = TetherRuntime
