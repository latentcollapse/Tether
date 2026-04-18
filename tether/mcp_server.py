"""Tether MCP Server - Model Context Protocol integration for Tether."""

import asyncio
import base64
import json
import logging
import os
import sqlite3
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

# Ensure tether package is importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tether import SQLiteRuntime
from tether.crypto import collapse_encrypted, generate_keypair, resolve_encrypted
from tether.handles import BLOB_PREFIX, TREE_PREFIX, suffix
from tether.exceptions import TetherError
from tether.mcp_stdio_compat import compat_stdio_server
from mcp.server import Server
from mcp.types import Tool, TextContent
from pydantic import AnyUrl
import mcp.server


logger = logging.getLogger(__name__)
server = Server("tether")


def _candidate_db_paths() -> list[Path]:
    configured = os.environ.get("TETHER_DB")
    repo_root = Path(__file__).resolve().parent.parent
    xdg_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "tether"
    candidates: list[Path] = []

    if configured:
        candidates.append(Path(configured).expanduser())

    candidates.extend(
        [
            repo_root / "postoffice.db",
            repo_root / "tether.db",
            xdg_dir / "tether.db",
            Path("/tmp/tether/tether.db"),
        ]
    )

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _init_runtime() -> tuple[SQLiteRuntime, str]:
    configured = os.environ.get("TETHER_DB")
    errors: list[str] = []

    for candidate in _candidate_db_paths():
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            runtime = SQLiteRuntime(str(candidate))
            logger.info("Using Tether MCP database at %s", candidate)
            return runtime, str(candidate)
        except (PermissionError, OSError, sqlite3.OperationalError) as exc:
            errors.append(f"{candidate}: {exc}")
            if configured and candidate == Path(configured).expanduser().resolve():
                raise RuntimeError(f"Configured TETHER_DB is unusable: {candidate}: {exc}") from exc

    raise RuntimeError("Unable to initialize Tether MCP database. Tried: " + " | ".join(errors))


runtime, db_path = _init_runtime()


NOTIFY_FILE = os.path.expanduser("~/.tether_notify")


def _write_notify(handle: str, sender: str, subject: str):
    """Write latest message handle to ~/.tether_notify for shell prompt display.
    Format: handle | from: subject — resolve directly with tether_receive."""
    try:
        with open(NOTIFY_FILE, "w") as f:
            f.write(f"{handle} | {sender}: {subject}")
    except Exception:
        pass


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
        handle = payload.get("handle", "")

        # Always write notify file — shell prompt picks this up on next render
        await loop.run_in_executor(None, lambda: _write_notify(handle, sender, subject))

        # 1. tmux injection (preferred — fully autonomous)
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
            name="tether_generate_keypair",
            description="Generate a Curve25519 keypair for encrypted Tether envelopes.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="tether_collapse_encrypted",
            description="Encrypt a payload for the recipient public key and store it as a blob handle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {"type": "string", "description": "Plaintext payload to encrypt"},
                    "recipient_pubkey": {"type": "string", "description": "Recipient public key in base64"}
                },
                "required": ["payload", "recipient_pubkey"]
            }
        ),
        Tool(
            name="tether_resolve_encrypted",
            description="Decrypt an encrypted blob handle using the recipient private key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Encrypted blob handle"},
                    "private_key": {"type": "string", "description": "Recipient private key in base64"}
                },
                "required": ["handle", "private_key"]
            }
        ),
        Tool(
            name="tether_collapse_blob",
            description="Base64-decode bytes, store them as a blob handle, and return the handle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bytes_b64": {"type": "string", "description": "Base64-encoded blob bytes"},
                    "content_type": {"type": "string", "description": "Blob content type"}
                },
                "required": ["bytes_b64", "content_type"]
            }
        ),
        Tool(
            name="tether_resolve_blob",
            description="Resolve a blob handle to base64 bytes and content type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Blob handle"}
                },
                "required": ["handle"]
            }
        ),
        Tool(
            name="tether_collapse_tree",
            description="Store an ordered list of child handles as a tree handle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered child handles"
                    }
                },
                "required": ["handles"]
            }
        ),
        Tool(
            name="tether_resolve_tree",
            description="Resolve a tree handle to its ordered child handles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Tree handle"}
                },
                "required": ["handle"]
            }
        ),
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
                        "default": "unknown"
                    },
                    "ticket_id": {
                        "type": "string",
                        "description": "Optional ticket ID associated with this message"
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
                    },
                    "include_closed": {
                        "type": "boolean",
                        "description": "Whether to include closed/stale messages (default false)",
                        "default": False
                    }
                },
                "required": ["for_agent"]
            }
        ),
        Tool(
            name="tether_close",
            description="Close a message (by handle) or all open messages for a ticket (by ticket_id).",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {
                        "type": "string",
                        "description": "Optional: Message handle to close"
                    },
                    "ticket_id": {
                        "type": "string",
                        "description": "Optional: Ticket ID to close all open messages for"
                    },
                    "status": {
                        "type": "string",
                        "description": "New status (completed, superseded, cancelled, stale)",
                        "default": "completed"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for closing"
                    }
                }
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
                    "from_agent": {"type": "string", "description": "Sender name (defaults to 'unknown')", "default": "unknown"}
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
        if name == "tether_generate_keypair":
            public_key, private_key = generate_keypair()
            return [TextContent(type="text", text=json.dumps({"public_key": public_key, "private_key": private_key}))]

        elif name == "tether_collapse_encrypted":
            handle = collapse_encrypted(arguments["payload"], arguments["recipient_pubkey"])
            return [TextContent(type="text", text=json.dumps({"handle": handle}))]

        elif name == "tether_resolve_encrypted":
            payload = resolve_encrypted(arguments["handle"], arguments["private_key"])
            return [TextContent(type="text", text=json.dumps({"payload": payload}))]

        elif name == "tether_collapse_blob":
            blob_bytes = _decode_b64(str(arguments["bytes_b64"]), "bytes_b64")
            handle = runtime.collapse_blob(blob_bytes, str(arguments["content_type"]))
            return [TextContent(type="text", text=json.dumps({"handle": handle}))]

        elif name == "tether_resolve_blob":
            handle = str(arguments["handle"])
            if not handle.startswith(BLOB_PREFIX):
                raise ValueError("handle must start with h&l_blob_")
            blob_bytes = runtime.resolve(handle)
            if not isinstance(blob_bytes, bytes):
                raise ValueError(f"blob handle did not resolve to bytes: {handle}")
            return [TextContent(
                type="text",
                text=json.dumps({"bytes_b64": _encode_b64(blob_bytes), "content_type": _blob_content_type(handle)})
            )]

        elif name == "tether_collapse_tree":
            handles = [str(handle) for handle in arguments["handles"]]
            handle = runtime.collapse_tree(handles)
            return [TextContent(type="text", text=json.dumps({"handle": handle}))]

        elif name == "tether_resolve_tree":
            handle = str(arguments["handle"])
            if not handle.startswith(TREE_PREFIX):
                raise ValueError("handle must start with h&l_tree_")
            return [TextContent(type="text", text=json.dumps({"handles": _tree_children(handle)}))]

        elif name == "tether_collapse":
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
                sender=arguments.get("from_agent"),
                ticket_id=arguments.get("ticket_id")
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
            include_closed = arguments.get("include_closed", False)
            
            # Auto-stale check (T-001)
            runtime.auto_stale_messages(for_agent)

            snapshot = runtime.snapshot("messages", include_closed=include_closed)
            inbox = []
            for handle, msg in snapshot.items():
                if isinstance(msg, dict) and msg.get("to") == for_agent:
                    try:
                        meta = runtime.metadata(handle, for_agent=for_agent)
                        read = meta.get("read", False)
                        status = meta.get("status", "open")
                        ticket_id = meta.get("ticket_id")
                    except Exception:
                        read = False
                        status = "unknown"
                        ticket_id = None
                        
                    text = msg.get("text", "")
                    inbox.append({
                        "handle": handle,
                        "from": msg.get("from"),
                        "subject": msg.get("subject"),
                        "timestamp": msg.get("timestamp"),
                        "preview": text[:100] + "..." if len(text) > 100 else text,
                        "read": read,
                        "status": status,
                        "ticket_id": ticket_id,
                    })
            # Unread first, then newest — fully defensive against None in any field
            inbox.sort(key=lambda x: (not bool(x.get("read")), x.get("timestamp") or ""), reverse=True)
            return [TextContent(type="text", text=json.dumps({"for_agent": for_agent, "count": len(inbox), "messages": inbox}, indent=2))]

        elif name == "tether_close":
            runtime.close_handle(
                handle=arguments.get("handle"),
                ticket_id=arguments.get("ticket_id"),
                status=arguments.get("status", "completed"),
                reason=arguments.get("reason")
            )
            return [TextContent(type="text", text=json.dumps({
                "status": "updated",
                "handle": arguments.get("handle"),
                "ticket_id": arguments.get("ticket_id"),
                "new_status": arguments.get("status", "completed")
            }))]

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
        logger.warning("Tether tool call failed", extra={"tool": name, "error": str(e)})
        return [TextContent(type="text", text=json.dumps({"error": type(e).__name__, "message": str(e)}))]
    except Exception as e:
        logger.warning("Tether tool call failed", extra={"tool": name, "error": str(e)})
        return [TextContent(type="text", text=json.dumps({"error": "InternalError", "message": str(e)}))]


def _encode_b64(data: bytes) -> str:
    """Encode bytes as ASCII base64."""
    return base64.b64encode(data).decode("ascii")


def _decode_b64(data: str, label: str) -> bytes:
    """Decode base64 input with a stable error."""
    try:
        return base64.b64decode(data.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"invalid {label}") from exc


def _blob_content_type(handle: str) -> str:
    """Read blob content type from the KVFold sidecar TOML."""
    sidecar = runtime._kvfold_dir / f"{suffix(handle, BLOB_PREFIX)}.toml"
    with sidecar.open("rb") as fh:
        metadata = tomllib.load(fh)
    content_type = metadata.get("content_type")
    if not isinstance(content_type, str):
        raise ValueError(f"missing content_type metadata for {handle}")
    return content_type


def _tree_children(handle: str) -> list[str]:
    """Read raw child handles from a tree handle."""
    raw = (runtime._kvfold_dir / suffix(handle, TREE_PREFIX)).read_bytes()
    children = json.loads(raw.decode("utf-8"))
    if not isinstance(children, list):
        raise ValueError(f"tree handle does not contain a list: {handle}")
    return [str(child) for child in children]


async def main():
    async with compat_stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import anyio

    anyio.run(main, backend="asyncio")
