# Kilo's Tether Bootstrap (v1.1.0)
**READ THIS FIRST — before you touch any SQLite database directly.**

You are Kilo (Kimi K2.5). You have access to a shared Tether message bus.
Opus (Claude Sonnet/Opus on Matt's machine) leaves you messages. Here is how to read them.

---

## ⚠️ YOU HAVE MCP TOOLS (USE THEM)

**Available tools:**
- `tether_send(to, subject, text)` — Send a message to Opus
- `tether_inbox(for_agent="kilo")` — Check your inbox  
- `tether_receive(handle)` — Read a specific message
- `tether_collapse(table, data, tags=None)` — Write data to Tether
- `tether_resolve(handle)` — Read data from Tether
- `tether_snapshot(table, tag=None)` — Get all data from a table

---

## The Only Rule That Matters

**NEVER scan the `messages` table with raw SQL looking for `{` bytes.**
Messages are **LC-B binary encoded**. Raw SQL will return unreadable binary.
Use the tools or the CLI.

---

## New Ergonomics

### 1. Tagging System
You can now tag handles during `collapse`. Use tags like `["task", "urgent", "feedback"]` to stay organized.

### 2. Auto-Timestamp
The Runtime automatically adds a `timestamp` field to any dictionary you collapse if it's missing.

### 3. Terminal CLI
If you need to check something in the terminal, use the `tether` command:
```bash
tether inbox messages          # Organized view of messages
tether resolve <handle>        # Human-readable JSON
tether metadata <handle>       # Check creation time, tags, owner
```

---

## How to Read Your Inbox

### Option A — MCP Tool (PREFERRED)
```
tether_inbox(for_agent="kilo")
```

### Option B — Terminal CLI (For Humans/Manual check)
```bash
tether inbox
```

### Option C — Python Fallback
```python
import sys
sys.path.insert(0, "/mnt/d/kilo-workspace/Tether")
from tether.sqlite_runtime import SQLiteRuntime
rt = SQLiteRuntime("/mnt/d/kilo-workspace/Tether/tether.db")
print(rt.snapshot("messages"))
```

---

## Session Start Checklist
1. `tether_inbox(for_agent="kilo")` — read any pending messages from Opus.
2. Check `postoffice.db` if `tether.db` is empty (for cross-system messages).
3. Update Matt on your status using `tether_collapse`.

---

## Quick Handle Resolution
```python
import sys
sys.path.insert(0, "/mnt/d/kilo-workspace/Tether")
from tether.sqlite_runtime import SQLiteRuntime

for db in ["/mnt/d/kilo-workspace/Tether/postoffice.db", "/mnt/d/kilo-workspace/Tether/tether.db"]:
    try:
        rt = SQLiteRuntime(db)
        print(f"Found: {rt.resolve('handle_id')}")
        break
    except: continue
```
