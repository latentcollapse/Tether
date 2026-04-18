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
        self._conn.execute("PRAGMA foreign_keys = ON")
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
                    tier TEXT NOT NULL DEFAULT 'teams',
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
                CREATE TABLE IF NOT EXISTS keys (
                    key_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES agents(agent_id) ON DELETE CASCADE,
                    key_hash TEXT NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                """
            )
            columns = {
                str(row["name"])
                for row in self._conn.execute("PRAGMA table_info(agents)").fetchall()
            }
            if "tier" not in columns:
                self._conn.execute("ALTER TABLE agents ADD COLUMN tier TEXT NOT NULL DEFAULT 'teams'")
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
                VALUES (?, ?, ?, ?, 'teams', ?, ?, 0)
                """,
                (agent_id, name, description, api_key_hash, now, now),
            )
            self._conn.commit()
        return {"agent_id": agent_id, "name": name, "description": description, "tier": "teams"}

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

    def get_active_key_hashes(self) -> list[dict[str, Any]]:
        """Return active managed key hashes with agent metadata."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT keys.key_id, keys.agent_id, keys.key_hash, agents.name
                FROM keys
                JOIN agents ON agents.agent_id = keys.agent_id
                WHERE keys.revoked_at IS NULL
                ORDER BY keys.created_at, keys.key_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_agents(self) -> list[dict[str, Any]]:
        """List registered agents."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT agent_id, name, online, last_seen, tier FROM agents ORDER BY name, agent_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def count_agents(self) -> int:
        """Return the number of registered relay agents."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS count FROM agents").fetchone()
        return int(row["count"])

    def set_agent_tier(self, agent_id: str, tier: str) -> None:
        """Set an agent's subscription tier."""
        with self._lock:
            self._conn.execute("UPDATE agents SET tier = ? WHERE agent_id = ?", (tier, agent_id))
            self._conn.commit()

    def get_agent_tier(self, agent_id: str) -> str | None:
        """Return an agent's subscription tier."""
        with self._lock:
            row = self._conn.execute("SELECT tier FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return str(row["tier"]) if row else None

    def delete_agent(self, agent_id: str) -> None:
        """Delete an agent and queued handles addressed to it."""
        with self._lock:
            self._conn.execute("DELETE FROM queued_handles WHERE to_agent = ? OR from_agent = ?", (agent_id, agent_id))
            self._conn.execute("DELETE FROM keys WHERE agent_id = ?", (agent_id,))
            self._conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            self._conn.commit()

    def create_key(self, agent_id: str, label: str | None, key_hash: str) -> dict[str, Any]:
        """Create a managed API key row."""
        key_id = str(uuid.uuid4())
        created_at = utc_now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO keys (key_id, agent_id, key_hash, label, created_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (key_id, agent_id, key_hash, label, created_at),
            )
            self._conn.commit()
        return {
            "key_id": key_id,
            "agent_id": agent_id,
            "label": label,
            "created_at": created_at,
            "revoked_at": None,
        }

    def get_key(self, key_id: str) -> dict[str, Any] | None:
        """Fetch a managed API key row."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM keys WHERE key_id = ?", (key_id,)).fetchone()
        return dict(row) if row else None

    def list_keys_for_agent(self, agent_id: str) -> list[dict[str, Any]]:
        """List managed API keys for an agent."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT key_id, agent_id, label, created_at, revoked_at
                FROM keys
                WHERE agent_id = ?
                ORDER BY created_at, key_id
                """,
                (agent_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke_key(self, key_id: str) -> None:
        """Revoke a managed API key."""
        with self._lock:
            self._conn.execute(
                "UPDATE keys SET revoked_at = COALESCE(revoked_at, ?) WHERE key_id = ?",
                (utc_now(), key_id),
            )
            self._conn.commit()

    def rotate_key(self, key_id: str, new_key_hash: str) -> dict[str, Any] | None:
        """Atomically revoke an existing key and create its replacement."""
        new_key_id = str(uuid.uuid4())
        now = utc_now()
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                old = self._conn.execute("SELECT * FROM keys WHERE key_id = ?", (key_id,)).fetchone()
                if old is None or old["revoked_at"] is not None:
                    self._conn.rollback()
                    return None
                self._conn.execute("UPDATE keys SET revoked_at = ? WHERE key_id = ?", (now, key_id))
                self._conn.execute(
                    """
                    INSERT INTO keys (key_id, agent_id, key_hash, label, created_at, revoked_at)
                    VALUES (?, ?, ?, ?, ?, NULL)
                    """,
                    (new_key_id, old["agent_id"], new_key_hash, old["label"], now),
                )
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
        return {
            "key_id": new_key_id,
            "agent_id": old["agent_id"],
            "label": old["label"],
            "created_at": now,
            "revoked_at": None,
        }

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
