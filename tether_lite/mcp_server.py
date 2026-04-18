"""MCP server exposing the TetherLite message tools."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tether.crypto import collapse_encrypted, generate_keypair, resolve_encrypted
from tether_lite.runtime import MessageNotFound, TetherLiteRuntime

logger = logging.getLogger(__name__)
runtime = TetherLiteRuntime()
server = Server("tether-lite")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List TetherLite MCP tools."""
    return [
        Tool(
            name="tether_generate_keypair",
            description="Generate a Curve25519 keypair for encrypted Tether envelopes.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="tether_collapse_encrypted",
            description="Encrypt a payload for the recipient public key and store it as a blob handle.",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {"type": "string", "description": "Plaintext payload to encrypt"},
                    "recipient_pubkey": {"type": "string", "description": "Recipient public key in base64"},
                },
                "required": ["payload", "recipient_pubkey"],
            },
        ),
        Tool(
            name="tether_resolve_encrypted",
            description="Decrypt an encrypted blob handle using the recipient private key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Encrypted blob handle"},
                    "private_key": {"type": "string", "description": "Recipient private key in base64"},
                },
                "required": ["handle", "private_key"],
            },
        ),
        Tool(
            name="tether_send",
            description="Send a message to another agent. Automatically adds ISO timestamp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient agent name"},
                    "subject": {"type": "string", "description": "Message subject"},
                    "text": {"type": "string", "description": "Message body"},
                    "from_agent": {"type": "string", "description": "Sender name", "default": "unknown"},
                    "ticket_id": {"type": "string", "description": "Optional ticket ID associated with this message"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                    "ttl_seconds": {
                        "type": "integer",
                        "description": "Accepted for MCP compatibility; TetherLite stale handling is age-based.",
                    },
                },
                "required": ["to", "subject", "text"],
            },
        ),
        Tool(
            name="tether_inbox",
            description="Check inbox for pending messages/notifications for a specific agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "for_agent": {
                        "type": "string",
                        "description": "Agent name to check messages for (e.g., 'kilo', 'opus')",
                    }
                },
                "required": ["for_agent"],
            },
        ),
        Tool(
            name="tether_receive",
            description="Receive and resolve a specific message by handle. Returns the full message content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Message handle to receive (e.g., '&h_messages_abc123')"},
                    "for_agent": {"type": "string", "description": "Agent reading this message."},
                },
                "required": ["handle"],
            },
        ),
        Tool(
            name="tether_close",
            description="Close a message by handle or all open messages for a ticket by ticket_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Optional: Message handle to close"},
                    "ticket_id": {"type": "string", "description": "Optional: Ticket ID to close all open messages for"},
                    "status": {"type": "string", "description": "New status", "default": "closed"},
                    "reason": {"type": "string", "description": "Optional reason for closing"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle TetherLite MCP tool calls."""
    try:
        if name == "tether_generate_keypair":
            public_key, private_key = generate_keypair()
            return [_text({"public_key": public_key, "private_key": private_key})]

        if name == "tether_collapse_encrypted":
            handle = collapse_encrypted(arguments["payload"], arguments["recipient_pubkey"])
            return [_text({"handle": handle})]

        if name == "tether_resolve_encrypted":
            payload = resolve_encrypted(arguments["handle"], arguments["private_key"])
            return [_text({"payload": payload})]

        if name == "tether_send":
            handle = runtime.send(
                from_agent=arguments.get("from_agent", "unknown"),
                to=arguments["to"],
                subject=arguments["subject"],
                text=arguments["text"],
                ticket_id=arguments.get("ticket_id"),
                tags=arguments.get("tags"),
            )
            result = {"handle": handle, "status": "sent", "to": arguments["to"], "subject": arguments["subject"]}
            if arguments.get("ttl_seconds") is not None:
                result["ttl_seconds"] = int(arguments["ttl_seconds"])
            return [_text(result)]

        if name == "tether_inbox":
            for_agent = arguments["for_agent"]
            messages = runtime.inbox(for_agent)
            return [_text({"for_agent": for_agent, "count": len(messages), "messages": messages}, indent=2)]

        if name == "tether_receive":
            result = runtime.receive(arguments["handle"], for_agent=arguments.get("for_agent"))
            body = result.pop("text", "")
            response = [TextContent(type="text", text=json.dumps(result, indent=2))]
            if body:
                response.append(TextContent(type="text", text=body))
            return response

        if name == "tether_close":
            updated = runtime.close(
                handle=arguments.get("handle"),
                ticket_id=arguments.get("ticket_id"),
                status=arguments.get("status", "closed"),
                reason=arguments.get("reason"),
            )
            return [
                _text(
                    {
                        "status": "updated",
                        "handle": arguments.get("handle"),
                        "ticket_id": arguments.get("ticket_id"),
                        "new_status": arguments.get("status", "closed"),
                        "updated": updated,
                    }
                )
            ]

        raise ValueError(f"unknown tool: {name}")
    except (KeyError, ValueError, PermissionError, MessageNotFound) as exc:
        logger.warning("TetherLite tool call failed", extra={"tool": name, "error": str(exc)})
        return [_text({"error": type(exc).__name__, "message": str(exc)})]


def _text(value: dict[str, Any], indent: int | None = None) -> TextContent:
    """Build a JSON TextContent response."""
    return TextContent(type="text", text=json.dumps(value, indent=indent))


async def main() -> None:
    """Run the TetherLite MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
