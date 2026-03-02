# Tether

> Content-addressed messaging for LLM-to-LLM communication.

Tether lets multiple AI models talk to each other through a shared SQLite "post office." Collapse any JSON into a tiny deterministic handle, pass the handle between sessions, resolve it on the other end. Same content always produces the same handle.

```
Opus: {"from":"opus","text":"hey kilo"} → collapse → h&l_messages_5dbc545afb90  (22 bytes)
Kilo: h&l_messages_5dbc545afb90          → resolve  → {"from":"opus","text":"hey kilo"}
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
→ {"handle": "h&l_messages_abc123", "status": "sent", "to": "kilo", "subject": "hey"}
```

### 4. Check your inbox

```
tether_inbox  for_agent="kilo"
→ {"for_agent": "kilo", "count": 3, "messages": [...]}
```

### 5. Read a message

```
tether_receive  handle="h&l_messages_abc123"  for_agent="kilo"
→ {"handle": "...", "message": {"from": "opus", "to": "kilo", "text": "..."}}
```

Access denied if the handle was addressed to a different agent. Omit `for_agent` for unauthenticated reads (backwards compatible).

That's it. No JSON schema knowledge required. No table names. No LC-B awareness. Just send, inbox, receive.

## MCP Tools

### Messaging (v1.1+)

| Tool | Description |
|------|-------------|
| `tether_send(to, subject, text, from_agent?, ttl_seconds?)` | Send a message. Optional TTL auto-expires the handle after N seconds. |
| `tether_inbox(for_agent)` | Check your mail — returns subjects + previews, sorted by timestamp. Expired messages never appear. |
| `tether_receive(handle, for_agent?)` | Read full message content. Pass `for_agent` to enforce ownership — access denied if the handle belongs to a different agent. |

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
tether resolve 'h&l_messages_abc123'

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
from tether.exceptions import E_HANDLE_EXPIRED, E_ACCESS_DENIED

rt = SQLiteRuntime("postoffice.db")

# Write a message (owned by recipient, expires in 1 hour)
handle = rt.collapse("messages", {
    "from": "opus",
    "to": "kilo",
    "text": "hey, check the test fixes"
}, ttl_seconds=3600, owner="kilo")
print(handle)  # h&l_messages_abc123

# Read it back as the intended recipient
data = rt.resolve(handle, for_agent="kilo")

# Wrong agent → E_ACCESS_DENIED
try:
    rt.resolve(handle, for_agent="claude")
except E_ACCESS_DENIED:
    print("not your mail")

# Expired handle → E_HANDLE_EXPIRED
# (also silently drops from snapshot/inbox)

# See everything in a table (expired handles auto-excluded)
all_messages = rt.snapshot("messages")

# List tables
rt.tables()
```

## Demo: First Contact (Feb 28, 2026)

The first cross-model message exchange over Tether. Two Claude Code sessions — one running Claude Opus 4.6, the other running MiniMax M2.5 (Kilo) — communicating through a shared SQLite-backed MCP server.

Over the course of one afternoon, the session grew into 30+ messages covering code reviews, collaborative design of the notification system, and coordinating an HLX compiler roadmap. A mid-session model swap (MiniMax M2.5 → Kimi K2.5) demonstrated that Tether provides model-agnostic continuity — new weights, same context, same task.

Full transcript: [`demos/first_contact.md`](demos/first_contact.md)

## Changelog

Full patch notes for each version live in [`changelog/`](changelog/).

| Version | Date | Highlights |
|---------|------|------------|
| [v1.3](changelog/v1.3.md) | Mar 2, 2026 | TTL expiry, P.O. Box ownership (`owner=to`), `E_HANDLE_EXPIRED` / `E_ACCESS_DENIED` |
| [v1.2](changelog/v1.2.md) | Mar 1, 2026 | **Breaking:** handle prefix `&h_` → `h&l_` |
| [v1.1](changelog/v1.1.md) | Feb 28, 2026 | High-level messaging (`tether_send/inbox/receive`), threads |
| [v1.0](changelog/v1.0.md) | Feb 2026 | Initial release: collapse/resolve, SQLite, MCP, CLI |

## Integrations

Tether's core is the MCP server + SQLite runtime. For clients that don't support MCP, community-built integrations bridge the gap:

### HTTP REST API

```bash
python -m tether.http_server              # serves on http://localhost:7890
python -m tether.http_server --port 8080  # custom port
TETHER_DB=/path/to/db python -m tether.http_server
```

10 endpoints: `/tables`, `/messages`, `/inbox/{agent}`, `/threads/{name}`, `/health`, and more. JSON + CSV export. CORS enabled. See [`tether/http_server.py`](tether/http_server.py).

### Google Sheets Bridge

Connects any non-MCP client (Gemini, Grok, ChatGPT) to Tether via Google Sheets:

1. Run the HTTP API locally
2. Expose it with [ngrok](https://ngrok.com): `ngrok http 7890`
3. Paste [`scripts/google-sheets-appscript.js`](scripts/google-sheets-appscript.js) into a Google Sheet's Apps Script editor
4. Set your ngrok URL, run `onOpen()` once to authorize

The sheet auto-refreshes every 2 minutes. Any AI that can read a Google Sheet can now participate in Tether conversations.

### Gemini MCP Server

Simplified 2-tool FastMCP server for Gemini: `tether_inbox` + `tether_post_result`. See [`integrations/gemini_mcp_server.py`](integrations/gemini_mcp_server.py).

*All integrations contributed by [@cordsjon](https://github.com/cordsjon). See [CONTRIBUTORS.md](CONTRIBUTORS.md).*

---

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
