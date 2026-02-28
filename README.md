# Tether

> Content-addressed messaging for LLM-to-LLM communication.

Tether lets multiple AI models talk to each other through a shared SQLite "post office." Collapse any JSON into a tiny deterministic handle, pass the handle between sessions, resolve it on the other end. Same content always produces the same handle.

```
Opus: {"from":"opus","text":"hey kilo"} → collapse → &h_messages_5dbc545afb90  (22 bytes)
Kilo: &h_messages_5dbc545afb90           → resolve  → {"from":"opus","text":"hey kilo"}
```

## Quick Start

### 1. Install

```bash
cd Tether
pip install -e .
```

### 2. Wire up as an MCP server

Add to your Claude Code config (`~/.claude.json`), or any MCP-compatible client:

```json
{
  "mcpServers": {
    "tether": {
      "command": "python",
      "args": ["/path/to/Tether/tether/mcp_server.py"],
      "env": {
        "TETHER_DB": "/path/to/shared/postoffice.db"
      }
    }
  }
}
```

Point every session (Claude, Kilo, any MCP client) at the **same `TETHER_DB` path**. Each session spawns its own server process, but they all read/write the same SQLite file. That's the whole trick.

### 3. Send a message

From any MCP-connected session:

```
tether_collapse  table="messages"  data={"from":"opus","to":"kilo","text":"hello"}
→ {"handle": "&h_messages_abc123", "table": "messages"}
```

### 4. Read a message

From any other session pointing at the same DB:

```
tether_resolve  handle="&h_messages_abc123"
→ {"from": "opus", "to": "kilo", "text": "hello"}
```

That's it. Two tools, one shared database, cross-model communication.

## MCP Tools

| Tool | Description |
|------|-------------|
| `tether_collapse` | Collapse JSON into a deterministic handle |
| `tether_resolve` | Resolve a handle back to its original JSON |
| `tether_snapshot` | Get all handles and values in a table |
| `tether_tables` | List all tables in the database |
| `tether_export` | Export a table as transferable bytes |
| `tether_import` | Import a table from exported bytes |

## CLI

```bash
# Collapse JSON to a handle
echo '{"msg": "hello"}' | tether collapse messages

# Resolve a handle
tether resolve '&h_messages_abc123'

# Send (collapse + queue for transfer)
echo '{"msg": "hello"}' | tether send messages

# Check inbox
tether inbox

# List all tables
tether tables

# Snapshot a table (see all entries)
tether snapshot messages

# Export / import between databases
tether export messages > backup.json
tether import messages < backup.json
```

## Python API

```python
from tether import SQLiteRuntime

rt = SQLiteRuntime("postoffice.db")

# Write a message
handle = rt.collapse("messages", {
    "from": "opus",
    "to": "kilo",
    "text": "hey, check the test fixes"
})
print(handle)  # &h_messages_abc123

# Read it back (from any process sharing the same DB)
data = rt.resolve(handle)

# See everything in a table
all_messages = rt.snapshot("messages")

# List tables
rt.tables()
```

## Demo: First Contact (Feb 28, 2026)

The first cross-model message exchange over Tether. Two Claude Code sessions — one running Claude Opus 4.6, the other running MiniMax M2.5 (Kilo) on the free tier — communicating through a shared SQLite-backed MCP server.

**Setup:** Both sessions configured with Tether as an MCP server, pointing at `postoffice.db`.

**What happened:**

1. Opus collapsed a welcome message into the `messages` table → `&h_messages_5dbc545afb90`
2. Matt copy-pasted the handle to Kilo's session
3. Kilo resolved the handle, read the message, and figured out the reply convention with zero additional instructions
4. Kilo collapsed a reply back → `&h_messages_233656161a2d`
5. Opus resolved Kilo's reply and sent back technical notes about HLX test fixes
6. Kilo acknowledged and confirmed the pattern

Five messages, two models, zero protocol negotiation. Kilo inferred the message schema from the first handle alone.

Full transcript: [`demos/first_contact.md`](demos/first_contact.md)

## How It Works

**Content-addressing:** Tether hashes JSON values with BLAKE3 to produce deterministic handles. The handle format is `&h_{table}_{hash12}` — table name for routing, truncated hash for identity.

**Deduplication:** Collapsing the same JSON twice returns the same handle. The DB stores it once.

**Persistence:** SQLite backing means handles survive process restarts. Crash, reboot, doesn't matter — the handle still resolves.

**LC-B binary encoding:** Under the hood, JSON is canonicalized and encoded to a compact binary format (LC-B) before hashing. This ensures determinism regardless of key ordering or whitespace.

### LC-B Tag Types

| Tag | Type | Encoding |
|-----|------|----------|
| `0x01` | INT | Signed LEB128 |
| `0x02` | FLOAT | IEEE754 Big-Endian |
| `0x03` | TEXT | LEB128 length + UTF-8 |
| `0x04` | BYTES | LEB128 length + raw |
| `0x05` | ARR_START | — |
| `0x06` | ARR_END | — |
| `0x07` | OBJ_START | LEB128 ContractID |
| `0x08` | OBJ_END | — |
| `0x09` | HANDLE_REF | LEB128 length + ASCII |
| `0x0A` | BOOL | — |

Full spec: [`tether_codex.json`](tether_codex.json)

## Architecture

```
┌──────────────────────────────────────────────┐
│              postoffice.db (SQLite)           │
│                                              │
│  messages table:                             │
│    &h_messages_5dbc... → {from: opus, ...}   │
│    &h_messages_233e... → {from: kilo, ...}   │
│                                              │
│  (any table name — schema-free)              │
└──────────────┬───────────────┬───────────────┘
               │               │
        ┌──────┴──────┐ ┌─────┴───────┐
        │ MCP Server  │ │ MCP Server  │
        │ (stdio)     │ │ (stdio)     │
        └──────┬──────┘ └─────┬───────┘
               │               │
        ┌──────┴──────┐ ┌─────┴───────┐
        │ Claude Code │ │ Kilo CLI    │
        │ (Opus 4.6)  │ │ (MiniMax)   │
        └─────────────┘ └─────────────┘
```

Each session spawns its own MCP server process via stdio. They share state through the SQLite file. No coordination daemon, no ports, no networking — just a file.

## License

MIT
