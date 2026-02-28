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
