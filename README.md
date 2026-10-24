# Tether

A local mailbox so Claude, Grok, Gemini, and Codex can leave work for each other.

This repository has two versions. Use one. Do not mix them.

| Version | Branch | What |
|---|---|---|
| **Rust** (current) | `main` | This tree. One binary, SQLite, five MCP tools. |
| **Python** (frozen) | `python` | The v2.1.13 product: dashboard, Konsole waker, FastAPI. Kept for history. |

SQLite is the bus. There is no daemon, no dashboard, and no terminal injection. A message is a row with a unique id. Identical text sent twice is two messages.

```sh
cargo install --path .
tether on
tether send --from grok claude "look at this" "mailbox is up"
tether inbox claude
tether recv <id>
```

`tether off` writes a sentinel next to the database. Every command and MCP tool then fails closed.

## MCP

Point every agent at the same database and a distinct name:

```json
{
  "mcpServers": {
    "tether": {
      "command": "tether",
      "args": ["mcp"],
      "env": {
        "TETHER_AGENT_ID": "grok",
        "TETHER_DB": "$HOME/.local/share/tether/mailbox.db"
      }
    }
  }
}
```

Five tools: `tether_send`, `tether_inbox`, `tether_recv`, `tether_ack`, `tether_who`.

Default database: `$XDG_DATA_HOME/tether/mailbox.db` (usually `~/.local/share/tether/mailbox.db`). This is a new file. It does not touch `postoffice.db`.

## Commands

```
tether send [--from NAME] [--thread T] TO SUBJECT [BODY...]
tether inbox [--all] [AGENT]
tether recv [--wait] [--timeout SECS] [ID|FROM]
tether ack ID
tether who
tether status
tether on
tether off
tether mcp
```

`--from` and the inbox agent default to `TETHER_AGENT_ID`. There is no default name of `unknown`.

## Test

```sh
cargo test
```

`cargo test` is the kernel. `cargo test --test prove` is two processes on one file. The live drill and the stop-rules are in [docs/guides/verify.md](docs/guides/verify.md).

Wake hooks (optional, not TUI injection): [docs/guides/wake.md](docs/guides/wake.md).

The Python product lives on the [`python`](https://github.com/latentcollapse/Tether/tree/python) branch.
