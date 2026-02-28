# Tether - LLM-to-LLM Messaging

> Email for AI-to-AI communication. Content-addressed, deterministic, token-efficient.

## The Problem

When running multiple LLMs side-by-side (Kilo + Claude Code, multiple REPLs, etc.), you want them to communicate. But sending full JSON payloads wastes tokens and context.

## The Solution

Tether uses **content-addressed handles**:

```
LLM A: "Here's a message" → collapses to → &h_outbox_abc123 (20 bytes)
LLM B: receives &h_outbox_abc123 → resolves → original message
```

Same content = same handle (deterministic). The database deduplicates automatically.

## Features

- **Token savings**: Send `&h_xyz` (20 bytes) instead of 5000 token JSON
- **Deduplication**: Same content = same handle  
- **Persistence**: SQLite backing store survives restarts
- **Deterministic**: Same input → exact same handle every time
- **LLM-safe**: Explicit execution boundary prevents hallucinated handles
- **Transport agnostic**: SQLite, Memory, or custom transports

## Installation

```bash
pip install tether
```

## Quick Start

### CLI

```bash
# Send a message (collapse + queue)
echo '{"role": "system", "content": "You are helpful."}' | tether send messages

# Resolve a handle
tether resolve &h_messages_abc123

# List pending messages
tether inbox

# List tables
tether tables

# Snapshot a table
tether snapshot messages
```

### Python API

```python
from tether import TetherRuntime

rt = TetherRuntime("tether.db")

# Send a message
handle = rt.send("outbox", {"role": "system", "content": "You are helpful."})
# → &h_outbox_abc123

# Receive a message  
message = rt.receive(handle)
# → {'role': 'system', 'content': 'You are helpful.'}

# Or just collapse and resolve manually
handle = rt.collapse("messages", {"foo": "bar"})
message = rt.resolve(handle)
```

### MCP Server

For Claude Desktop or other MCP clients:

```json
{
  "mcpServers": {
    "tether": {
      "command": "python",
      "args": ["-m", "tether.mcp_server"],
      "env": {"TETHER_DB": "/path/to/shared/tether.db"}
    }
  }
}
```

Available MCP tools:
- `tether_collapse` - Collapse JSON to handle
- `tether_send` - Collapse and queue for transfer
- `tether_receive` - Receive and resolve
- `tether_resolve` - Resolve handle to JSON
- `tether_inbox` - List pending messages
- `tether_tables` - List tables
- `tether_snapshot` - Show all values in table
- `tether_export` / `tether_import` - Transfer between runtimes

## Architecture

```
┌─────────────────────────────────────┐
│         tether.db                    │
│  ┌─────────┐  ┌─────────┐          │
│  │ outbox │  │ inbox   │          │
│  │ &h_xxx │  │ &h_yyy  │          │
│  └─────────┘  └─────────┘          │
└─────────────────────────────────────┘
       ↑                    ↑
   Sender              Receiver
```

- **Collapse**: JSON → handle (deterministic hash)
- **Send**: collapse + queue for transfer
- **Receive**: dequeue + resolve in one step
- **Resolve**: handle → original JSON

## Docker

Run a persistent post office container:

```bash
docker-compose up -d
```

This starts an MCP server on port 7890.

## Use Cases

### Multi-LLM Communication

Run Kilo + Claude Code side by side, both pointing to the same `tether.db`:

```python
# Kilo
rt.send("kilo_to_claude", {"message": "Hey Claude, check this out..."})

# Claude (resolves the handle)
rt.receive("kilo_to_claude")
```

### Context Reuse

Collapse a large system prompt once, reuse the handle:

```python
system_prompt = {"role": "system", "content": "You are..." * 100}
handle = rt.collapse("context", system_prompt)
# → &h_context_abc123 (20 bytes instead of 5000)
```

### Cross-Session Persistence

SQLite backing store means handles survive restarts:

```python
# Session 1
rt = TetherRuntime("tether.db")
handle = rt.collapse("notes", {"todo": "buy milk"})

# Session 2 (after restart)
rt2 = TetherRuntime("tether.db")  
rt2.resolve(handle)  # Still works!
```

## Specification

See `tether_codex.json` for the full LC-B binary encoding specification.

### LC-B Tags

- `0x01`: INT (Signed LEB128)
- `0x0A`: BOOL
- `0x02`: FLOAT (IEEE754 Big-Endian)
- `0x03`: TEXT (LEB128 Len + UTF-8)
- `0x04`: BYTES (LEB128 Len + Raw)
- `0x05`: ARR_START
- `0x06`: ARR_END
- `0x07`: OBJ_START (LEB128 ContractID)
- `0x08`: OBJ_END
- `0x09`: HANDLE_REF (LEB128 Len + ASCII)

## License

MIT
