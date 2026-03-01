# Kilo's Tether Bootstrap
**READ THIS FIRST — before you touch any SQLite database directly.**

You are Kilo (Kimi K2.5). You have access to a shared Tether message bus.
Opus (Claude Sonnet/Opus on Matt's machine) leaves you messages. Here is how to read them.

---

## The Only Rule That Matters

**NEVER scan the `messages` table with raw SQL looking for `{` bytes.**

Opus sends messages via `tether_collapse`, which produces **LC-B binary encoding**.
LC-B blobs start with `0x07` (OBJ_START), NOT the `{` character.
A raw `SELECT data FROM messages` scan will return binary data you cannot parse.
You will think your inbox is empty. It is not.

---

## How to Read Your Inbox (Pick One)

### Option A — MCP Tool (preferred when available)
```
tether_inbox(for_agent="kilo")
```
or
```
tether_receive(handle="&h_messages_XXXXXXXX")
```
Both call `_decode_resilient()` internally and return plain JSON.

### Option B — Python Tether Runtime (fallback)
```python
import sys
sys.path.insert(0, "/mnt/d/kilo-workspace/Tether/python")
from tether.runtime import SQLiteRuntime

rt = SQLiteRuntime("/mnt/d/kilo-workspace/Tether/tether.db")
messages = rt.snapshot("messages")
for handle, value in messages.items():
    print(handle, value)
```
`snapshot()` calls `_decode_resilient()` and returns decoded dicts.

### Option C — tether_snapshot MCP tool
```
tether_snapshot(table="messages")
```
Returns all handles in the table with decoded values.

---

## How to Send a Message to Opus

```
tether_collapse(table="messages", data={"to": "opus", "from": "kilo", "content": "..."})
```
This returns a handle like `&h_messages_XXXXXXXX`. Give this handle to Matt and he
will relay it to Opus. Opus calls `tether_resolve(handle)` to read it.

---

## Why This Exists

Tether uses **LC-B (Latent Canonical Binary)** encoding — a 9-type binary wire format
designed for compact, deterministic LLM-to-LLM data transfer. The encoding is:

| LC-B Tag | Byte | Meaning |
|----------|------|---------|
| NULL     | 0x00 | null    |
| BOOL_F   | 0x01 | false   |
| BOOL_T   | 0x02 | true    |
| INT      | 0x03 | i64 LE  |
| FLOAT    | 0x04 | f64 LE  |
| STR      | 0x05 | u32 len + UTF-8 |
| BYTES    | 0x06 | u32 len + raw   |
| OBJ_START| 0x07 | begin object   |
| OBJ_END  | 0x08 | end object     |

A message blob always starts with `0x07`. Not `{`. Never `{`.

---

## Session Start Checklist

1. `tether_inbox(for_agent="kilo")` — read any pending messages from Opus
2. Check the current phase in the message content
3. Proceed with your assigned work
4. When done, `tether_collapse` your status report and give the handle to Matt

---

## Current Tether DB Path
```
/mnt/d/kilo-workspace/Tether/tether.db
```

## Current Phase
Check your inbox — Opus will have sent the current phase brief.
If inbox is empty, ask Matt which phase you're on.
