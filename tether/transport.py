"""Transport layer for Tether - abstract export/import across different backends."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Protocol


class Transport(Protocol):
    """Abstract transport for Tether message passing."""
    
    def send(self, handle: str, data: bytes) -> None:
        """Send a handle + data to the transport."""
        ...
    
    def receive(self, handle: str) -> bytes | None:
        """Receive data for a handle, or None if not found."""
        ...
    
    def list_pending(self) -> list[str]:
        """List all handles waiting to be received."""
        ...


class SQLiteTransport:
    """Transport using shared SQLite database as message queue."""
    
    def __init__(self, db_path: str = "tether.db", queue_table: str = "tether_queue"):
        import sqlite3
        self.db_path = db_path
        self.queue_table = queue_table
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_queue()
    
    def _init_queue(self):
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.queue_table} (
                handle TEXT PRIMARY KEY,
                data BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()
    
    def send(self, handle: str, data: bytes) -> None:
        """Queue a message for pickup."""
        self._conn.execute(
            f"INSERT OR REPLACE INTO {self.queue_table} (handle, data) VALUES (?, ?)",
            (handle, data)
        )
        self._conn.commit()
    
    def receive(self, handle: str) -> bytes | None:
        """Receive and remove a queued message."""
        cursor = self._conn.execute(
            f"SELECT data FROM {self.queue_table} WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()
        if row:
            self._conn.execute(
                f"DELETE FROM {self.queue_table} WHERE handle = ?",
                (handle,)
            )
            self._conn.commit()
            return row[0]
        return None
    
    def list_pending(self) -> list[str]:
        """List all queued message handles."""
        cursor = self._conn.execute(f"SELECT handle FROM {self.queue_table}")
        return [row[0] for row in cursor]
    
    def close(self):
        self._conn.close()


class MemoryTransport:
    """In-memory transport for testing or single-process use."""
    
    def __init__(self):
        self._queue: Dict[str, bytes] = {}
    
    def send(self, handle: str, data: bytes) -> None:
        self._queue[handle] = data
    
    def receive(self, handle: str) -> bytes | None:
        return self._queue.pop(handle, None)
    
    def list_pending(self) -> list[str]:
        return list(self._queue.keys())


class ClipboardTransport:
    """Transport that uses clipboard for copy/paste transfer.
    
    Useful for manual LLM-to-LLM transfer when you can't share a DB.
    """
    def __init__(self):
        self._pending: Dict[str, bytes] = {}
    
    def send(self, handle: str, data: bytes) -> None:
        """Store locally and print handle - user copies manually."""
        self._pending[handle] = data
        print(f"Handle ready: {handle}")
        print(f"Copy this handle and send to recipient")
    
    def receive(self, handle: str) -> bytes | None:
        return self._pending.pop(handle, None)
    
    def list_pending(self) -> list[str]:
        return list(self._pending.keys())


def create_transport(backend: str = "sqlite", **kwargs) -> Transport:
    """Factory to create transport by name."""
    backends = {
        "sqlite": SQLiteTransport,
        "memory": MemoryTransport,
        "clipboard": ClipboardTransport,
    }
    if backend not in backends:
        raise ValueError(f"Unknown transport: {backend}. Choose: {list(backends.keys())}")
    return backends[backend](**kwargs)
