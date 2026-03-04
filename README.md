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

## MCP Tools

### Messaging (v1.4+)

| Tool | Description |
|------|-------------|
| `tether_send(to, subject, text, from_agent?, tags?, ttl_seconds?)` | Send a message. Automatically adds `timestamp`. Supports optional tags. |
| `tether_inbox(for_agent)` | Check your mail — returns subjects + previews, sorted by timestamp. Highlights unread messages. |
| `tether_receive(handle, for_agent?)` | Read full message content. Marks as **read** for the specified agent. |
| `tether_metadata(handle)` | Get handle provenance (creation time, tags, owner, read status). |

### Primitives (v1.0+)

| Tool | Description |
|------|-------------|
| `tether_collapse(table, data, tags?)` | Collapse JSON into a deterministic handle. Supports tagging. |
| `tether_resolve(handle, agent?)` | Resolve a handle back to its original JSON. |
| `tether_snapshot(table, tag?)` | Get all handles and values in a table. Optional tag filter. |
| `tether_tables()` | List all tables in the database |
| `tether_export(table)` | Export a table as transferable bytes |
| `tether_import(table, data)` | Import a table from exported bytes |

## CLI

Tether includes an ergonomic CLI for human interaction. Use the `tether` command:

```bash
# Organized view of messages (Unread ● vs Read ○)
tether inbox messages

# Filter inbox by tag
tether inbox messages --tag task

# Resolve a handle and mark as read
tether resolve 'h&l_messages_abc123' --agent human

# Inspect handle provenance
tether metadata 'h&l_messages_abc123'

# List all tables and handle counts
tether tables
```

## Python API

```python
from tether import SQLiteRuntime
from tether.exceptions import E_HANDLE_EXPIRED, E_ACCESS_DENIED

rt = SQLiteRuntime("postoffice.db")

# Write a tagged message
handle = rt.collapse("messages", {
    "from": "opus",
    "to": "kilo",
    "text": "hey, check the test fixes"
}, tags=["urgent", "hlx"], owner="kilo")

# Read it back (automatically marks as read)
data = rt.resolve(handle, for_agent="kilo")

# Check metadata
meta = rt.metadata(handle, for_agent="kilo")
print(meta['read']) # True
```

## Changelog

Full patch notes for each version live in [`changelog/`](changelog/).

| Version | Date | Highlights |
|---------|------|------------|
| [v1.4](changelog/v1.4.md) | Mar 4, 2026 | Tagging, read/unread status tracking, auto-timestamps, ergonomic CLI overhaul |
| [v1.3](changelog/v1.3.md) | Mar 2, 2026 | TTL expiry, P.O. Box ownership (`owner=to`), `E_HANDLE_EXPIRED` / `E_ACCESS_DENIED` |
| [v1.2](changelog/v1.2.md) | Mar 1, 2026 | **Breaking:** handle prefix `&h_` → `h&l_` |
| [v1.1](changelog/v1.1.md) | Feb 28, 2026 | High-level messaging (`tether_send/inbox/receive`), threads |
| [v1.0](changelog/v1.0.md) | Feb 2026 | Initial release: collapse/resolve, SQLite, MCP, CLI |

## License

AGPL v3
