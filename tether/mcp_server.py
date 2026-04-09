"""Tether MCP Server - Model Context Protocol integration for Tether."""

import asyncio
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# Ensure tether package is importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tether import SQLiteRuntime
from tether.exceptions import TetherError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from pydantic import AnyUrl
import mcp.server


# Global runtime instance (SQLite-backed for persistence)
# Resolution order: TETHER_DB env var → XDG_DATA_HOME/tether/tether.db → ~/.local/share/tether/tether.db
_default_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "tether"
_default_dir.mkdir(parents=True, exist_ok=True)
db_path = os.environ.get("TETHER_DB", str(_default_dir / "tether.db"))
runtime = SQLiteRuntime(db_path)


server = Server("tether")


def _tmux_inject(session: str, message: str) -> bool:
    """Inject a prompt into a named tmux session. Returns True if session exists."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True
        )
        if result.returncode != 0:
            return False
        subprocess.run(
            ["tmux", "send-keys", "-t", session, message, "Enter"],
            capture_output=True
        )
        return True
    except FileNotFoundError:
        return False  # tmux not installed


async def _fire_ping(url: str, payload: dict):
    """Notify an agent of a new message.

    Strategy (in order):
    1. tmux send-keys into the agent's named session (session name = payload["to"])
       — activates the agent immediately with no polling
    2. HTTP POST to registered URL as fallback (for non-tmux setups)

    Both are best-effort — never fail the send.
    """
    agent = payload.get("to", "")
    sender = payload.get("from", "?")
    subject = payload.get("subject", "?")
    prompt = f"[tether] new message from {sender}: {subject} — check inbox"

    try:
        loop = asyncio.get_running_loop()

        # 1. tmux injection (preferred)
        injected = await loop.run_in_executor(None, lambda: _tmux_inject(agent, prompt))

        # 2. HTTP fallback
        if not injected and url:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=2))
    except Exception:
        pass  # ping is best-effort — never fail the send


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Tether tools."""
    return [
        Tool(
            name="tether_collapse",
            description="Collapse a JSON value into a deterministic handle. Use this to compress data for transfer between LLMs. Supports optional tagging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name to store the value (e.g., 'messages', 'context', 'schemas')"
                    },
                    "data": {
                        "type": "object",
                        "description": "JSON data to collapse into a handle"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization"
                    }
                },
                "required": ["table", "data"]
            }
        ),
        Tool(
            name="tether_resolve",
            description="Resolve a Tether handle back to its original JSON value.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {
                        "type": "string",
                        "description": "Tether handle to resolve (e.g., '&h_messages_abc123')"
                    }
                },
                "required": ["handle"]
            }
        ),
        Tool(
            name="tether_snapshot",
            description="Get all handles and values in a table. Supports optional tag filtering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name to snapshot"
                    },
                    "tag": {
                        "type": "string",
                        "description": "Optional tag to filter by"
                    }
                },
                "required": ["table"]
            }
        ),
        Tool(
            name="tether_metadata",
            description="Get metadata for a handle (creation time, tags, owner).",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {
                        "type": "string",
                        "description": "Handle to inspect"
                    }
                },
                "required": ["handle"]
            }
        ),
        Tool(
            name="tether_tables",
            description="List all tables in the runtime.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="tether_send",
            description="Send a message to another agent. Automatically adds ISO timestamp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient agent name"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Message subject"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message body"
                    },
                    "from_agent": {
                        "type": "string",
                        "description": "Sender name",
                        "default": "kilo"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags"
                    },
                    "ttl_seconds": {
                        "type": "integer",
                        "description": "Optional TTL in seconds. Message expires after this many seconds."
                    }
                },
                "required": ["to", "subject", "text"]
            }
        ),
        Tool(
            name="tether_inbox",
            description="Check inbox for pending messages/notifications for a specific agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "for_agent": {
                        "type": "string",
                        "description": "Agent name to check messages for (e.g., 'kilo', 'opus')"
                    }
                },
                "required": ["for_agent"]
            }
        ),
        Tool(
            name="tether_receive",
            description="Receive and resolve a specific message by handle. Returns the full message content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {
                        "type": "string",
                        "description": "Message handle to receive (e.g., '&h_messages_abc123')"
                    },
                    "for_agent": {
                        "type": "string",
                        "description": "Agent reading this message. Required for owner-locked messages."
                    }
                },
                "required": ["handle"]
            }
        ),
        Tool(
            name="tether_export",
            description="Export a table as transferrable bytes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name to export"}
                },
                "required": ["table"]
            }
        ),
        Tool(
            name="tether_import",
            description="Import a table from exported bytes (for cross-LLM transfer).",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name to import into"},
                    "data": {"type": "object", "description": "Exported table data (handle -> hex bytes)"}
                },
                "required": ["table", "data"]
            }
        ),
        Tool(
            name="tether_thread_create",
            description="Create a new conversation thread for organizing messages by topic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_name": {"type": "string", "description": "Thread name (e.g., 'hlx-dev', 'general')"},
                    "description": {"type": "string", "description": "Optional thread description"}
                },
                "required": ["thread_name"]
            }
        ),
        Tool(
            name="tether_thread_send",
            description="Send a message to a specific thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread": {"type": "string", "description": "Thread name to post to"},
                    "to": {"type": "string", "description": "Recipient agent name"},
                    "subject": {"type": "string", "description": "Message subject"},
                    "text": {"type": "string", "description": "Message body"},
                    "from_agent": {"type": "string", "description": "Sender name (defaults to 'kilo')", "default": "kilo"}
                },
                "required": ["thread", "to", "subject", "text"]
            }
        ),
        Tool(
            name="tether_thread_inbox",
            description="Get all messages in a specific thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread": {"type": "string", "description": "Thread name to read"},
                    "for_agent": {"type": "string", "description": "Optional: filter for specific recipient"}
                },
                "required": ["thread"]
            }
        ),
        Tool(
            name="tether_threads",
            description="List all conversation threads.",
            inputSchema={"type": "object", "properties": {}}
        ),

        # ── Task Board (v1.5) ──────────────────────────────────────────────
        Tool(
            name="tether_task_create",
            description=(
                "Create a shared task on the persistent task board. "
                "All agents (Claude, Gemini, Kilo) can read and update tasks. "
                "Use human-readable IDs like 'hlx-gap1' or 'prism-i64'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Unique task ID (slug, e.g. 'hlx-gap1')"},
                    "title": {"type": "string", "description": "Short task title"},
                    "description": {"type": "string", "description": "Full task description"},
                    "priority": {"type": "string", "description": "p0, p1, p2, or p3", "default": "p1"},
                    "assignee": {"type": "string", "description": "Agent or person assigned (e.g. 'gemini', 'claude', 'matt')", "default": "unassigned"},
                    "created_by": {"type": "string", "description": "Who created this task"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"}
                },
                "required": ["id", "title"]
            }
        ),
        Tool(
            name="tether_task_update",
            description="Update a task's status, priority, assignee, or description. Any agent can update any task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Task ID to update"},
                    "status": {"type": "string", "description": "open, in_progress, blocked, done"},
                    "priority": {"type": "string", "description": "p0, p1, p2, or p3"},
                    "assignee": {"type": "string", "description": "New assignee"},
                    "description": {"type": "string", "description": "Updated description"},
                    "title": {"type": "string", "description": "Updated title"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Updated tags"}
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="tether_task_list",
            description="List tasks from the shared board. Filter by status, assignee, or priority.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (open, in_progress, blocked, done)"},
                    "assignee": {"type": "string", "description": "Filter by assignee"},
                    "priority": {"type": "string", "description": "Filter by priority (p0, p1, p2, p3)"}
                }
            }
        ),
        Tool(
            name="tether_task_get",
            description="Get a single task by ID, including full comment history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Task ID"}
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="tether_task_comment",
            description="Append a comment or progress note to a task. Visible to all agents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Task ID"},
                    "author": {"type": "string", "description": "Your agent name (e.g. 'claude', 'gemini')"},
                    "text": {"type": "string", "description": "Comment text"}
                },
                "required": ["id", "author", "text"]
            }
        ),

        # ── Ping Endpoints (v1.6) ─────────────────────────────────────────
        Tool(
            name="tether_register_ping",
            description=(
                "Register a ping endpoint so this agent is notified the moment a message arrives. "
                "On send, Tether fires a lightweight HTTP POST to the URL with event/to/from/subject/handle. "
                "Set enabled=false to register but keep ping off initially."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent name to register (e.g. 'qwen', 'codex', 'claude')"},
                    "url": {"type": "string", "description": "HTTP endpoint to POST to when a message arrives"},
                    "enabled": {"type": "boolean", "description": "Whether to enable pinging immediately (default true)", "default": True}
                },
                "required": ["agent", "url"]
            }
        ),
        Tool(
            name="tether_ping_toggle",
            description=(
                "Hotswap ping on or off for an agent without changing the registered URL. "
                "Takes effect immediately — no server restart needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent name"},
                    "enabled": {"type": "boolean", "description": "true to enable, false to disable"}
                },
                "required": ["agent", "enabled"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "tether_collapse":
            handle = runtime.collapse(
                arguments["table"], 
                arguments["data"], 
                tags=arguments.get("tags")
            )
            return [TextContent(
                type="text",
                text=json.dumps({"handle": handle, "table": arguments["table"]})
            )]
        
        elif name == "tether_resolve":
            value = runtime.resolve(arguments["handle"])
            return [TextContent(
                type="text",
                text=json.dumps(value, indent=2)
            )]
        
        elif name == "tether_snapshot":
            snapshot = runtime.snapshot(arguments["table"], tag=arguments.get("tag"))
            return [TextContent(
                type="text",
                text=json.dumps(snapshot, indent=2, default=str)
            )]
            
        elif name == "tether_metadata":
            meta = runtime.metadata(arguments["handle"])
            return [TextContent(
                type="text",
                text=json.dumps(meta, indent=2)
            )]
        
        elif name == "tether_tables":
            tables = runtime.tables()
            return [TextContent(
                type="text",
                text=json.dumps({"tables": tables})
            )]
        
        elif name == "tether_send":
            message_data = {
                "from": arguments.get("from_agent", "kilo"),
                "to": arguments["to"],
                "subject": arguments["subject"],
                "text": arguments["text"],
            }
            ttl_seconds = arguments.get("ttl_seconds")
            handle = runtime.collapse(
                "messages",
                message_data,
                ttl_seconds=int(ttl_seconds) if ttl_seconds is not None else None,
                owner=arguments["to"],
                tags=arguments.get("tags"),
                sender=arguments.get("from_agent")
            )
            result = {"handle": handle, "status": "sent", "to": arguments["to"], "subject": arguments["subject"]}
            if ttl_seconds is not None:
                result["ttl_seconds"] = int(ttl_seconds)
            ping_url = runtime.get_ping_url(arguments["to"])
            if ping_url:
                asyncio.create_task(_fire_ping(ping_url, {
                    "event": "tether_message",
                    "to": arguments["to"],
                    "from": arguments.get("from_agent", "unknown"),
                    "subject": arguments["subject"],
                    "handle": handle,
                }))
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "tether_inbox":
            for_agent = arguments["for_agent"]
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
            # Unread first, then newest — fully defensive against None in any field
            inbox.sort(key=lambda x: (not bool(x.get("read")), x.get("timestamp") or ""), reverse=True)
            return [TextContent(type="text", text=json.dumps({"for_agent": for_agent, "count": len(inbox), "messages": inbox}, indent=2))]

        elif name == "tether_receive":
            msg = runtime.resolve(arguments["handle"], for_agent=arguments.get("for_agent"))
            body = msg.pop("text", "") if isinstance(msg, dict) else ""
            result = [TextContent(type="text", text=json.dumps({"handle": arguments["handle"], "message": msg}, indent=2))]
            if body:
                result.append(TextContent(type="text", text=body))
            return result

        elif name == "tether_export":
            exported = runtime.export_table(arguments["table"])
            hex_data = {k: v.hex() for k, v in exported.items()}
            return [TextContent(type="text", text=json.dumps({"table": arguments["table"], "handles": hex_data}))]

        elif name == "tether_import":
            data = {k: bytes.fromhex(v) for k, v in arguments["data"].items()}
            runtime.import_table(arguments["table"], data)
            return [TextContent(type="text", text=json.dumps({"status": "imported", "table": arguments["table"], "handles": len(data)}))]

        elif name == "tether_thread_create":
            thread_data = {"name": arguments["thread_name"], "description": arguments.get("description", "")}
            handle = runtime.collapse("threads", thread_data)
            return [TextContent(type="text", text=json.dumps({"status": "created", "thread": arguments["thread_name"], "handle": handle}))]

        elif name == "tether_thread_send":
            message_data = {
                "from": arguments.get("from_agent", "kilo"),
                "to": arguments["to"],
                "subject": arguments["subject"],
                "text": arguments["text"],
                "thread": arguments["thread"],
            }
            handle = runtime.collapse(arguments["thread"], message_data)
            return [TextContent(type="text", text=json.dumps({"handle": handle, "status": "sent", "thread": arguments["thread"], "to": arguments["to"]}))]

        elif name == "tether_thread_inbox":
            snapshot = runtime.snapshot(arguments["thread"])
            messages = []
            for handle, msg in snapshot.items():
                if isinstance(msg, dict):
                    if arguments.get("for_agent") and msg.get("to") != arguments["for_agent"]:
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
            return [TextContent(type="text", text=json.dumps({"thread": arguments["thread"], "count": len(messages), "messages": messages}, indent=2))]

        elif name == "tether_threads":
            snapshot = runtime.snapshot("threads")
            threads = [
                {"handle": h, "name": d.get("name"), "description": d.get("description")}
                for h, d in snapshot.items() if isinstance(d, dict)
            ]
            return [TextContent(type="text", text=json.dumps({"count": len(threads), "threads": threads}, indent=2))]

        # ── Task Board (v1.5) ──────────────────────────────────────────────
        elif name == "tether_task_create":
            task = runtime.task_create(
                id=arguments["id"],
                title=arguments["title"],
                description=arguments.get("description", ""),
                priority=arguments.get("priority", "p1"),
                assignee=arguments.get("assignee", "unassigned"),
                created_by=arguments.get("created_by", "unknown"),
                tags=arguments.get("tags"),
            )
            return [TextContent(type="text", text=json.dumps({"status": "created", "task": task}, indent=2))]

        elif name == "tether_task_update":
            task = runtime.task_update(
                id=arguments["id"],
                status=arguments.get("status"),
                priority=arguments.get("priority"),
                assignee=arguments.get("assignee"),
                description=arguments.get("description"),
                title=arguments.get("title"),
                tags=arguments.get("tags"),
            )
            return [TextContent(type="text", text=json.dumps({"status": "updated", "task": task}, indent=2))]

        elif name == "tether_task_list":
            tasks = runtime.task_list(
                status=arguments.get("status"),
                assignee=arguments.get("assignee"),
                priority=arguments.get("priority"),
            )
            return [TextContent(type="text", text=json.dumps({"count": len(tasks), "tasks": tasks}, indent=2))]

        elif name == "tether_task_get":
            task = runtime.task_get(arguments["id"])
            return [TextContent(type="text", text=json.dumps(task, indent=2))]

        elif name == "tether_task_comment":
            task = runtime.task_comment(
                id=arguments["id"],
                author=arguments["author"],
                text=arguments["text"],
            )
            return [TextContent(type="text", text=json.dumps({"status": "commented", "task": task}, indent=2))]

        elif name == "tether_register_ping":
            runtime.set_ping_url(
                arguments["agent"],
                arguments["url"],
                enabled=arguments.get("enabled", True)
            )
            status = runtime.get_ping_status(arguments["agent"])
            return [TextContent(type="text", text=json.dumps({"status": "registered", "ping": status}))]

        elif name == "tether_ping_toggle":
            runtime.set_ping_enabled(arguments["agent"], arguments["enabled"])
            status = runtime.get_ping_status(arguments["agent"])
            if status is None:
                return [TextContent(type="text", text=json.dumps({"error": "no ping endpoint registered for this agent"}))]
            return [TextContent(type="text", text=json.dumps({"status": "updated", "ping": status}))]

        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except TetherError as e:
        return [TextContent(type="text", text=json.dumps({"error": type(e).__name__, "message": str(e)}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": "InternalError", "message": str(e)}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
