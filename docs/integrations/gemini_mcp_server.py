#!/usr/bin/env python3
"""Gemini MCP Server - Tether integration for Gemini agent."""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Optional, List, Any, Dict

# Ensure tether package is importable
TETHER_PATH = Path(__file__).resolve().parent.parent
if str(TETHER_PATH) not in sys.path:
    sys.path.insert(0, str(TETHER_PATH))

from tether.sqlite_runtime import SQLiteRuntime
from tether.exceptions import TetherError
from mcp.server.fastmcp import FastMCP

# Configuration
TETHER_DB = str(TETHER_PATH / "tether.db")
POSTOFFICE_DB = str(TETHER_PATH / "postoffice.db")

class MultiSQLiteRuntime:
    """A wrapper that checks multiple databases for Tether handles."""
    def __init__(self, db_paths: List[str]):
        self.runtimes = [SQLiteRuntime(p) for p in db_paths if os.path.exists(p)]
        if not self.runtimes:
            # Fallback to creating tether.db if none exist
            self.runtimes = [SQLiteRuntime(TETHER_DB)]

    def _get_primary(self):
        return self.runtimes[0]

    def collapse(self, table: str, value: Any, ttl_seconds: Optional[int] = None, 
                 owner: Optional[str] = None, tags: Optional[List[str]] = None) -> str:
        # Always collapse to the primary (tether.db)
        return self._get_primary().collapse(table, value, ttl_seconds, owner, tags)

    def resolve(self, handle: str, for_agent: Optional[str] = None) -> Any:
        for rt in self.runtimes:
            try:
                return rt.resolve(handle, for_agent)
            except Exception:
                continue
        raise TetherError(f"Handle not found in any database: {handle}")

    def metadata(self, handle: str, for_agent: Optional[str] = None) -> Dict[str, Any]:
        for rt in self.runtimes:
            try:
                return rt.metadata(handle, for_agent)
            except Exception:
                continue
        raise TetherError(f"Handle not found in any database: {handle}")

    def snapshot(self, table: str, tag: Optional[str] = None) -> Dict[str, Any]:
        # Merge snapshots from all databases
        merged = {}
        for rt in self.runtimes:
            try:
                merged.update(rt.snapshot(table, tag))
            except Exception:
                continue
        return merged

    def tables(self) -> List[str]:
        all_tables = set()
        for rt in self.runtimes:
            all_tables.update(rt.tables())
        return list(all_tables)

    def export_table(self, table: str) -> Dict[str, bytes]:
        merged = {}
        for rt in self.runtimes:
            merged.update(rt.export_table(table))
        return merged

    def import_table(self, table: str, data: Dict[str, bytes]):
        self._get_primary().import_table(table, data)

# Initialize runtime
runtime = MultiSQLiteRuntime([TETHER_DB, POSTOFFICE_DB])

# Initialize FastMCP
mcp = FastMCP("gemini")

@mcp.tool()
async def tether_collapse(table: str, data: dict, tags: Optional[List[str]] = None) -> str:
    """Collapse a JSON value into a deterministic handle. Use for data compression."""
    try:
        handle = runtime.collapse(table, data, tags=tags)
        return json.dumps({"handle": handle, "table": table})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_resolve(handle: str, for_agent: Optional[str] = "gemini") -> str:
    """Resolve a Tether handle back to its original JSON value."""
    try:
        value = runtime.resolve(handle, for_agent=for_agent)
        return json.dumps(value, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_send(to: str, subject: str, text: str, from_agent: str = "gemini", 
                      tags: Optional[List[str]] = None, ttl_seconds: Optional[int] = None) -> str:
    """Send a message to another agent (e.g., 'claude', 'kilo', 'matt')."""
    try:
        message_data = {
            "from": from_agent,
            "to": to,
            "subject": subject,
            "text": text,
        }
        handle = runtime.collapse(
            "messages",
            message_data,
            ttl_seconds=ttl_seconds,
            owner=to,
            tags=tags
        )
        return json.dumps({"handle": handle, "status": "sent", "to": to, "subject": subject})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_inbox(for_agent: str = "gemini") -> str:
    """Check inbox for pending messages for a specific agent."""
    try:
        snapshot = runtime.snapshot("messages")
        inbox = []
        for handle, msg in snapshot.items():
            if isinstance(msg, dict) and msg.get("to") == for_agent:
                try:
                    meta = runtime.metadata(handle, for_agent=for_agent)
                    read = meta.get("read", False)
                except Exception:
                    read = False
                text = msg.get("text", "")
                inbox.append({
                    "handle": handle,
                    "from": msg.get("from"),
                    "subject": msg.get("subject"),
                    "timestamp": msg.get("timestamp"),
                    "preview": text[:100] + "..." if len(text) > 100 else text,
                    "read": read,
                })
        inbox.sort(key=lambda x: (not bool(x.get("read")), x.get("timestamp") or ""), reverse=True)
        return json.dumps({"for_agent": for_agent, "count": len(inbox), "messages": inbox}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_receive(handle: str, for_agent: str = "gemini") -> str:
    """Receive and resolve a specific message by handle."""
    try:
        msg = runtime.resolve(handle, for_agent=for_agent)
        return json.dumps({"handle": handle, "message": msg}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_metadata(handle: str) -> str:
    """Get metadata for a handle."""
    try:
        meta = runtime.metadata(handle)
        return json.dumps(meta, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_snapshot(table: str, tag: Optional[str] = None) -> str:
    """Get all handles and values in a table."""
    try:
        snapshot = runtime.snapshot(table, tag=tag)
        return json.dumps(snapshot, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_tables() -> str:
    """List all tables in the runtime."""
    try:
        return json.dumps({"tables": runtime.tables()})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_thread_create(thread_name: str, description: str = "") -> str:
    """Create a new conversation thread."""
    try:
        thread_data = {"name": thread_name, "description": description}
        handle = runtime.collapse("threads", thread_data)
        return json.dumps({"status": "created", "thread": thread_name, "handle": handle})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_thread_send(thread: str, to: str, subject: str, text: str, from_agent: str = "gemini") -> str:
    """Send a message to a specific thread."""
    try:
        message_data = {
            "from": from_agent,
            "to": to,
            "subject": subject,
            "text": text,
            "thread": thread,
        }
        handle = runtime.collapse(thread, message_data)
        return json.dumps({"handle": handle, "status": "sent", "thread": thread, "to": to})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_thread_inbox(thread: str, for_agent: Optional[str] = "gemini") -> str:
    """Get all messages in a specific thread."""
    try:
        snapshot = runtime.snapshot(thread)
        messages = []
        for handle, msg in snapshot.items():
            if isinstance(msg, dict):
                if for_agent and msg.get("to") != for_agent:
                    continue
                text = msg.get("text", "")
                messages.append({
                    "handle": handle,
                    "from": msg.get("from"),
                    "to": msg.get("to"),
                    "subject": msg.get("subject"),
                    "timestamp": msg.get("timestamp"),
                    "preview": text[:100] + "..." if len(text) > 100 else text,
                })
        messages.sort(key=lambda x: x.get("timestamp", "") or "", reverse=True)
        return json.dumps({"thread": thread, "count": len(messages), "messages": messages}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def tether_threads() -> str:
    """List all conversation threads."""
    try:
        snapshot = runtime.snapshot("threads")
        threads = [
            {"handle": h, "name": d.get("name"), "description": d.get("description")}
            for h, d in snapshot.items() if isinstance(d, dict)
        ]
        return json.dumps({"count": len(threads), "threads": threads}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()
