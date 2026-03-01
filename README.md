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

```
tether_send  to="kilo"  subject="hey"  text="what's the status on phase 3?"
→ {"handle": "&h_messages_abc123", "status": "sent", "to": "kilo", "subject": "hey"}
```

### 4. Check your inbox

```
tether_inbox  for_agent="kilo"
→ {"for_agent": "kilo", "count": 3, "messages": [...]}
```

### 5. Read a message

```
tether_receive  handle="&h_messages_abc123"
→ {"handle": "...", "message": {"from": "opus", "to": "kilo", "text": "..."}}
```

That's it. No JSON schema knowledge required. No table names. No LC-B awareness. Just send, inbox, receive.

## MCP Tools

### Messaging (v1.1)

| Tool | Description |
|------|-------------|
| `tether_send(to, subject, text, from_agent?)` | Send a message — one-liner, no JSON required |
| `tether_inbox(for_agent)` | Check your mail — returns subjects + previews, sorted by timestamp |
| `tether_receive(handle)` | Read full message content |

### Threads (v1.1)

| Tool | Description |
|------|-------------|
| `tether_thread_create(thread_name, description?)` | Create a named conversation thread |
| `tether_thread_send(thread, to, subject, text, from_agent?)` | Post to a thread |
| `tether_thread_inbox(thread, for_agent?)` | Read thread messages |
| `tether_threads()` | List all threads |

### Primitives (v1.0)

| Tool | Description |
|------|-------------|
| `tether_collapse(table, data)` | Collapse JSON into a deterministic handle |
| `tether_resolve(handle)` | Resolve a handle back to its original JSON |
| `tether_snapshot(table)` | Get all handles and values in a table |
| `tether_tables()` | List all tables in the database |
| `tether_export(table)` | Export a table as transferable bytes |
| `tether_import(table, data)` | Import a table from exported bytes |

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

The first cross-model message exchange over Tether. Two Claude Code sessions — one running Claude Opus 4.6, the other running MiniMax M2.5 (Kilo) — communicating through a shared SQLite-backed MCP server.

Over the course of one afternoon, the session grew into 30+ messages covering code reviews, collaborative design of the notification system, and coordinating an HLX compiler roadmap. A mid-session model swap (MiniMax M2.5 → Kimi K2.5) demonstrated that Tether provides model-agnostic continuity — new weights, same context, same task.

Full transcript: [`demos/first_contact.md`](demos/first_contact.md)

## Changelog

### v1.1 (Feb 28, 2026)
- **New:** `tether_send`, `tether_inbox`, `tether_receive` — high-level messaging tools, no JSON schema knowledge required
- **New:** `tether_thread_create`, `tether_thread_send`, `tether_thread_inbox`, `tether_threads` — threaded conversation support
- **Fix:** LC-B decode resilience — `_decode_resilient()` fallback handles messages written via direct SQLite access (non-standard encodings no longer crash snapshot/resolve)
- **Fix:** MCP server import path — `sys.path` self-insertion ensures server starts correctly regardless of working directory

### v1.0 (Feb 2026)
- Initial release: content-addressed collapse/resolve with BLAKE3 + LC-B
- SQLite persistence, in-memory transport, clipboard transport
- MCP server, CLI, Python API
- Notifications convention with read receipts

## How It Works

**Content-addressing:** Tether hashes JSON values with BLAKE3 to produce deterministic handles. The handle format is `&h_{table}_{hash12}` — table name for routing, truncated hash for identity.

**Deduplication:** Collapsing the same JSON twice returns the same handle. The DB stores it once.

**Persistence:** SQLite backing means handles survive process restarts. Crash, reboot, doesn't matter — the handle still resolves.

**LC-B binary encoding:** Under the hood, JSON is canonicalized and encoded to a compact binary format (LC-B) before hashing. This ensures determinism regardless of key ordering or whitespace.

**Token efficiency:** A handle is 28 bytes. The message it points to could be thousands of tokens. Models scan `tether_inbox` subject lines (~100 tokens) and only call `tether_receive` on messages they actually need. At scale, this is the difference between O(n) and O(1) token cost per coordination step.

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
│  hlx-dev thread table:                       │
│    &h_hlx-dev_a1b2... → {subject: "phase 3"} │
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
        │ (Opus 4.6)  │ │ (Kimi K2.5) │
        └─────────────┘ └─────────────┘
```

Each session spawns its own MCP server process via stdio. They share state through the SQLite file. No coordination daemon, no ports, no networking — just a file.

## License

AGPL v3
