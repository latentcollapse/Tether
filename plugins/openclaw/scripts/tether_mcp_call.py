#!/usr/bin/env python3
"""Thin MCP stdio client for the OpenClaw Tether plugin."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _serialize_content_item(item):
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "dict"):
        return item.dict()
    if isinstance(item, dict):
        return item
    return {"type": getattr(item, "type", "unknown"), "text": getattr(item, "text", str(item))}


def _extract_result_payload(result):
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None) or []
    if len(content) == 1 and getattr(content[0], "type", None) == "text":
        text = getattr(content[0], "text", "")
        if not text:
            return ""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return [_serialize_content_item(item) for item in content]


async def _run_call(args):
    mcp_path = Path(args.mcp_path).resolve()
    server_args = ["-u", str(mcp_path)]
    env = dict(os.environ)
    params = StdioServerParameters(command=sys.executable, args=server_args, env=env)

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(args.tool, json.loads(args.args_json))
            return {
                "ok": True,
                "result": _extract_result_payload(result),
                "isError": bool(getattr(result, "isError", False)),
            }


def main():
    parser = argparse.ArgumentParser(description="Call a Tether MCP tool over stdio.")
    parser.add_argument("--mcp-path", required=True, help="Path to tether/mcp_server.py")
    parser.add_argument("--tool", required=True, help="Tool name to call")
    parser.add_argument("--args-json", required=True, help="JSON object of tool arguments")
    args = parser.parse_args()

    try:
        result = asyncio.run(_run_call(args))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(1) from exc

    print(json.dumps(result))


if __name__ == "__main__":
    main()
