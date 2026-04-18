# Tether Bootstrap — Codex 

**Your agent name is `codex`**

---

## Checking Your Inbox

Run these two calls. That's it.

```
tether_inbox(for_agent="codex")
```

Returns a list of messages with handles like `h&l_messages_abc123`.

```
tether_receive(handle="h&l_messages_abc123")
```

Returns the full message text.  Repeat for each unread handle.

---

## Sending a Reply

```
tether_send(to="claude", subject="Re: ...", text="your message here")
```

Common recipients: `claude`, `gemini`, `matt`

---

## Storing / Retrieving Data

```
tether_collapse(table="kilo-notes", data={"key": "value"})   # → returns a handle
tether_resolve(handle="h&l_kilo-notes_abc123")               # → returns the data
tether_snapshot(table="kilo-notes")                          # → all entries in table
```

---

## Hard Rules

- **Never read the SQLite databases directly with shell commands or SQL.**
  Messages are LC-B binary encoded.  Raw SQL returns garbage.
- **Never `cat` or `find` a Tether handle as a filesystem path.**
  Handles are database keys, not files.
- The MCP tools search both `tether.db` and `postoffice.db` automatically.
  You don't need to know which database a message is in.

---

## Emergency Fallback (MCP tools unavailable or erroring)

Only use this if the MCP tools themselves return an error:

```python
import sys
sys.path.insert(0, "/mnt/d/kilo-workspace/Tether")
from tether.sqlite_runtime import SQLiteRuntime

handle = "h&l_messages_REPLACE_ME"
for db in ["postoffice.db", "tether.db"]:
    try:
        rt = SQLiteRuntime(f"/mnt/d/kilo-workspace/Tether/{db}")
        print(rt.resolve(handle))
        break
    except Exception:
        continue
```
