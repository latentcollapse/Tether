"""SQLite storage for relay metadata and routing state."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RelayDB:
    """SQLite-backed relay metadata store."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.init_schema()

    def init_schema(self) -> None:
        """Create relay tables if needed."""
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    api_key_hash TEXT NOT NULL,
                    tier TEXT NOT NULL DEFAULT 'free',
                    created_at TEXT NOT NULL,
                    last_seen TEXT,
                    online INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS queued_handles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handle TEXT NOT NULL,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    ticket_id TEXT,
                    tags TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    delivered_at TEXT,
                    status TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            self._conn.close()

    def create_agent(self, name: str, description: str | None, api_key_hash: str) -> dict[str, Any]:
        """Create an agent registry row."""
        agent_id = f"agent_{uuid.uuid4().hex}"
        now = utc_now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agents
                (agent_id, name, description, api_key_hash, tier, created_at, last_seen, online)
                VALUES (?, ?, ?, ?, 'free', ?, ?, 0)
                """,
                (agent_id, name, description, api_key_hash, now, now),
            )
            self._conn.commit()
        return {"agent_id": agent_id, "name": name, "description": description}

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Fetch an agent by id."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None

    def get_agent_by_key_hashes(self) -> list[dict[str, Any]]:
        """Return agents with key hashes for authentication."""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM agents").fetchall()
        return [dict(row) for row in rows]

    def list_agents(self) -> list[dict[str, Any]]:
        """List registered agents."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT agent_id, name, online, last_seen FROM agents ORDER BY name, agent_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_agent(self, agent_id: str) -> None:
        """Delete an agent and queued handles addressed to it."""
        with self._lock:
            self._conn.execute("DELETE FROM queued_handles WHERE to_agent = ? OR from_agent = ?", (agent_id, agent_id))
            self._conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            self._conn.commit()

    def set_online(self, agent_id: str, online: bool) -> None:
        """Update online status and last_seen."""
        with self._lock:
            self._conn.execute(
                "UPDATE agents SET online = ?, last_seen = ? WHERE agent_id = ?",
                (1 if online else 0, utc_now(), agent_id),
            )
            self._conn.commit()

    def queue_handle(
        self,
        handle: str,
        from_agent: str,
        to_agent: str,
        subject: str,
        ticket_id: str | None,
        tags: list[str],
        status: str,
    ) -> int:
        """Create a queued handle row."""
        now = utc_now()
        delivered_at = now if status == "delivered" else None
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO queued_handles
                (handle, from_agent, to_agent, subject, ticket_id, tags, queued_at, delivered_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (handle, from_agent, to_agent, subject, ticket_id, json.dumps(tags), now, delivered_at, status),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def mark_delivered(self, row_id: int) -> None:
        """Mark a queued handle delivered."""
        with self._lock:
            self._conn.execute(
                "UPDATE queued_handles SET status = 'delivered', delivered_at = ? WHERE id = ?",
                (utc_now(), row_id),
            )
            self._conn.commit()

    def pending_for_agent(self, agent_id: str) -> list[dict[str, Any]]:
        """Return queued handles waiting for an agent."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM queued_handles WHERE to_agent = ? AND status = 'queued' ORDER BY id",
                (agent_id,),
            ).fetchall()
        return [self._decode_handle_row(row) for row in rows]

    def handle_status(self, handle: str) -> str | None:
        """Return latest known status for a handle."""
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM queued_handles WHERE handle = ? ORDER BY id DESC LIMIT 1",
                (handle,),
            ).fetchone()
        return str(row["status"]) if row else None

    def _decode_handle_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        tags = data.get("tags") or "[]"
        data["tags"] = json.loads(tags)
        return data
