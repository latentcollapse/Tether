"""Tether MCP Server - Model Context Protocol integration for Tether."""

import json
import os
import sys
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
db_path = os.environ.get("TETHER_DB", "tether.db")
runtime = SQLiteRuntime(db_path)


server = Server("tether")


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
        )
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
                tags=arguments.get("tags")
            )
            result = {"handle": handle, "status": "sent", "to": arguments["to"], "subject": arguments["subject"]}
            if ttl_seconds is not None:
                result["ttl_seconds"] = int(ttl_seconds)
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
            # Unread first, then newest
            inbox.sort(key=lambda x: (x["read"], x.get("timestamp", "") or ""), reverse=True)
            inbox.sort(key=lambda x: x["read"])
            return [TextContent(type="text", text=json.dumps({"for_agent": for_agent, "count": len(inbox), "messages": inbox}, indent=2))]

        elif name == "tether_receive":
            msg = runtime.resolve(arguments["handle"], for_agent=arguments.get("for_agent"))
            return [TextContent(type="text", text=json.dumps({"handle": arguments["handle"], "message": msg}, indent=2))]

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
