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
            description="Collapse a JSON value into a deterministic handle. Use this to compress data for transfer between LLMs.",
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
            description="Get all handles and values in a table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name to snapshot"
                    }
                },
                "required": ["table"]
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
            name="tether_export",
            description="Export a table as transferrable bytes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name to export"
                    }
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
                    "table": {
                        "type": "string",
                        "description": "Table name to import into"
                    },
                    "data": {
                        "type": "object",
                        "description": "Exported table data (handle -> hex bytes)"
                    }
                },
                "required": ["table", "data"]
            }
        ),
        Tool(
            name="tether_send",
            description="Send a message to another agent. Convenience wrapper that handles message formatting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient agent name (e.g., 'opus', 'kilo', 'claude')"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Message subject/topic"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message body content"
                    },
                    "from_agent": {
                        "type": "string",
                        "description": "Sender agent name (defaults to 'kilo')",
                        "default": "kilo"
                    },
                    "ttl_seconds": {
                        "type": "integer",
                        "description": "Optional TTL in seconds. Message expires and becomes unresolvable after this many seconds."
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
                        "description": "Agent reading this message. Required for owner-locked messages — access denied if it doesn't match the recipient."
                    }
                },
                "required": ["handle"]
            }
        ),
        Tool(
            name="tether_thread_create",
            description="Create a new conversation thread for organizing messages by topic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_name": {
                        "type": "string",
                        "description": "Thread name (e.g., 'hlx-dev', 'tether-dev', 'general')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional thread description"
                    }
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
                    "thread": {
                        "type": "string",
                        "description": "Thread name to post to"
                    },
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
                        "description": "Sender name (defaults to 'kilo')",
                        "default": "kilo"
                    }
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
                    "thread": {
                        "type": "string",
                        "description": "Thread name to read"
                    },
                    "for_agent": {
                        "type": "string",
                        "description": "Optional: filter for specific recipient"
                    }
                },
                "required": ["thread"]
            }
        ),
        Tool(
            name="tether_threads",
            description="List all conversation threads.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "tether_collapse":
            handle = runtime.collapse(arguments["table"], arguments["data"])
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
            snapshot = runtime.snapshot(arguments["table"])
            return [TextContent(
                type="text",
                text=json.dumps(snapshot, indent=2, default=str)
            )]
        
        elif name == "tether_tables":
            tables = runtime.tables()
            return [TextContent(
                type="text",
                text=json.dumps({"tables": tables})
            )]
        
        elif name == "tether_export":
            exported = runtime.export_table(arguments["table"])
            hex_data = {k: v.hex() for k, v in exported.items()}
            return [TextContent(
                type="text",
                text=json.dumps({"table": arguments["table"], "handles": hex_data})
            )]
        
        elif name == "tether_import":
            data = {k: bytes.fromhex(v) for k, v in arguments["data"].items()}
            runtime.import_table(arguments["table"], data)
            return [TextContent(
                type="text",
                text=json.dumps({"status": "imported", "table": arguments["table"], "handles": len(data)})
            )]
        
        elif name == "tether_send":
            # Convenience wrapper: format message and collapse
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
                owner=arguments["to"],  # P.O. Box: only the recipient can resolve
            )
            result = {
                "handle": handle,
                "status": "sent",
                "to": arguments["to"],
                "subject": arguments["subject"],
            }
            if ttl_seconds is not None:
                result["ttl_seconds"] = int(ttl_seconds)
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "tether_inbox":
            # Get all messages and filter for this agent
            snapshot = runtime.snapshot("messages")
            inbox = []
            for handle, msg in snapshot.items():
                if isinstance(msg, dict) and msg.get("to") == arguments["for_agent"]:
                    inbox.append({
                        "handle": handle,
                        "from": msg.get("from"),
                        "subject": msg.get("subject"),
                        "timestamp": msg.get("timestamp"),
                        "preview": msg.get("text", "")[:100] + "..." if len(msg.get("text", "")) > 100 else msg.get("text", "")
                    })
            # Sort by timestamp (newest first) if available
            inbox.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "for_agent": arguments["for_agent"],
                    "count": len(inbox),
                    "messages": inbox
                }, indent=2)
            )]
        
        elif name == "tether_receive":
            # Resolve handle — enforce ownership if for_agent is provided
            msg = runtime.resolve(arguments["handle"], for_agent=arguments.get("for_agent"))
            return [TextContent(
                type="text",
                text=json.dumps({
                    "handle": arguments["handle"],
                    "message": msg
                }, indent=2)
            )]
        
        elif name == "tether_thread_create":
            # Create a thread by storing metadata in threads table
            thread_data = {
                "name": arguments["thread_name"],
                "description": arguments.get("description", ""),
                "created_at": None,  # Will be set by runtime
            }
            handle = runtime.collapse("threads", thread_data)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "created",
                    "thread": arguments["thread_name"],
                    "handle": handle
                })
            )]
        
        elif name == "tether_thread_send":
            # Send message to a specific thread
            message_data = {
                "from": arguments.get("from_agent", "kilo"),
                "to": arguments["to"],
                "subject": arguments["subject"],
                "text": arguments["text"],
                "thread": arguments["thread"],
            }
            handle = runtime.collapse(arguments["thread"], message_data)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "handle": handle,
                    "status": "sent",
                    "thread": arguments["thread"],
                    "to": arguments["to"],
                    "subject": arguments["subject"]
                })
            )]
        
        elif name == "tether_thread_inbox":
            # Get all messages in a thread, optionally filtered by recipient
            snapshot = runtime.snapshot(arguments["thread"])
            messages = []
            for handle, msg in snapshot.items():
                if isinstance(msg, dict):
                    # If for_agent specified, filter
                    if arguments.get("for_agent") and msg.get("to") != arguments["for_agent"]:
                        continue
                    messages.append({
                        "handle": handle,
                        "from": msg.get("from"),
                        "to": msg.get("to"),
                        "subject": msg.get("subject"),
                        "timestamp": msg.get("timestamp"),
                        "preview": msg.get("text", "")[:100] + "..." if len(msg.get("text", "")) > 100 else msg.get("text", "")
                    })
            # Sort by timestamp
            messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "thread": arguments["thread"],
                    "count": len(messages),
                    "messages": messages
                }, indent=2)
            )]
        
        elif name == "tether_threads":
            # List all threads
            snapshot = runtime.snapshot("threads")
            threads = []
            for handle, data in snapshot.items():
                if isinstance(data, dict):
                    threads.append({
                        "handle": handle,
                        "name": data.get("name"),
                        "description": data.get("description")
                    })
            return [TextContent(
                type="text",
                text=json.dumps({
                    "count": len(threads),
                    "threads": threads
                }, indent=2)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except TetherError as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": type(e).__name__, "message": str(e)})
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "InternalError", "message": str(e)})
        )]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
