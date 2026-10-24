# How to know it works

Three proofs. Stop when they pass. Do not grow a test cult around a mailbox.

## 1. Kernel — `cargo test`

In-process: send/inbox/recv, two identical bodies stay two rows, broadcast acks are per-agent, the off sentinel is beside *this* database, MCP dispatch exposes five tools.

This is necessary. It does not prove two agents.

## 2. Two processes, one file — `cargo test --test prove`

The actual product: the `tether` binary, separate OS processes, one SQLite file.

- CLI: grok sends, claude inboxes, claude recvs.
- MCP stdio: real JSON-RPC on stdin/stdout (`initialize`, `tools/list`, `tether_send`, `tether_inbox`).
- Two writers at once against the same WAL file.
- `tether off` makes send exit 2.
- Tool count stays at five. Direct dependencies stay `rusqlite`, `serde`, `serde_json`.

## 3. Live drill (human, once per cutover)

Do not wire Claude/Gemini/Codex until this is boring.

```sh
cd "/mnt/d/Code Projects/tether"
tmp=$(mktemp -d /tmp/tether-drill-XXXX)
export TETHER_DB="$tmp/mailbox.db"
bin=target/debug/tether
cargo build -q

TETHER_AGENT_ID=grok   $bin send claude "drill" "can you see this"
TETHER_AGENT_ID=claude $bin inbox
TETHER_AGENT_ID=claude $bin recv "$(TETHER_AGENT_ID=claude $bin inbox | awk '{print $1; exit}')"
$bin off
TETHER_AGENT_ID=grok   $bin send claude "nope" "must fail"
$bin on
rm -rf "$tmp"
```

A new teammate is connected when those same commands work with their `TETHER_AGENT_ID` and the shared `TETHER_DB`. If that takes more than an env var and `tether mcp`, the crate got heavy.

## What not to test

Ports, dashboards, Konsole injection, message-per-second graphs, crash-injection of WAL. None of those are claims this crate makes. When a claim shows up, add a proof next to it.
