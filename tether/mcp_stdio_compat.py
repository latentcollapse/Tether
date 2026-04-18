"""Compatibility stdio transport for MCP in this local environment."""

from __future__ import annotations

import asyncio
import sys
import threading
from contextlib import asynccontextmanager

import anyio
import anyio.lowlevel
import mcp.types as types
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.shared.message import SessionMessage


@asynccontextmanager
async def compat_stdio_server():
    """Replacement for `mcp.server.stdio.stdio_server()` using thread-backed IO."""
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(16)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(16)

    loop = asyncio.get_running_loop()
    stop_event = threading.Event()

    async def _close_read_stream() -> None:
        await read_stream_writer.aclose()

    async def _forward_payload(payload: SessionMessage | Exception) -> None:
        await read_stream_writer.send(payload)

    def stdin_reader_thread() -> None:
        while not stop_event.is_set():
            line = sys.stdin.buffer.readline()
            if not line:
                loop.call_soon_threadsafe(asyncio.create_task, _close_read_stream())
                break
            try:
                message = types.JSONRPCMessage.model_validate_json(line.decode("utf-8"))
                payload: SessionMessage | Exception = SessionMessage(message)
            except Exception as exc:  # pragma: no cover
                payload = exc
            loop.call_soon_threadsafe(asyncio.create_task, _forward_payload(payload))

    async def stdout_writer() -> None:
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    payload = session_message.message.model_dump_json(
                        by_alias=True,
                        exclude_none=True,
                    )
                    sys.stdout.write(payload + "\n")
                    sys.stdout.flush()
        except anyio.ClosedResourceError:  # pragma: no cover
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        reader = threading.Thread(target=stdin_reader_thread, daemon=True)
        reader.start()
        tg.start_soon(stdout_writer)
        try:
            yield read_stream, write_stream
        finally:
            stop_event.set()
            reader.join(timeout=0.2)
