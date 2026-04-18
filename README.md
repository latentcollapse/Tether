# Tether

> Coordination infrastructure for multi-agent AI systems.

AI agents have no shared coordination layer. Tether is the protocol and runtime for persistent, verified, cross-machine context passing over MCP. This is the tool you use to coordinate Claude Code, Codex CLI, Gemini CLI, OpenClaw, and more. It is recommended to write a standard operating procedure and job board/debt ledger for your projects already, but these are paramount to the workflow operating efficiently.

Tether has two operating modes:

- `TetherLite`: local-first, free forever, no relay required
- `Tether Cloud`: relay-backed delivery when agents need to communicate across machines

The same handle format, the same MCP tool names, and the same basic workflow apply in both.

## What Tether Is Not

- Not a compression tool. Handles are deterministic pointers, not compressed payloads.
- Not a generic storage service. TetherLite stores local data on your machine; relay-backed cross-machine delivery stores routing metadata and encrypted ciphertext envelopes, not plaintext.
- Not tied to one model vendor. Tether is MCP-native and LLM-agnostic.

## How It Works

Collapse data into a handle, send the handle, resolve it on the other side.

```text
payload -> collapse -> handle -> send handle -> receive handle -> resolve
```

For local use, resolution happens against the local runtime.

For cross-machine encrypted handoff, the sender encrypts the payload for the recipient, uploads ciphertext to the relay, routes the handle, and the recipient fetches ciphertext and decrypts locally. The relay sees ciphertext and routing metadata, not plaintext.

## TetherLite

TetherLite is the permanent free tier:

- local storage
- unlimited agents
- unlimited messages
- no relay dependency
- AGPL v3

### Install

```bash
cd Tether
pip install -e .
```

### MCP Setup

Add Tether to any MCP-compatible client:

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

For the TOML-backed local runtime, point tools at `tether_lite` instead of the SQLite runtime where appropriate.

### First Message

```text
tether_send to="codex" subject="status" text="What changed?"
tether_inbox for_agent="codex"
tether_receive handle="h&l_messages_..."
```

### Dashboard

```bash
python -m tether_lite dashboard
```

That serves the built dashboard locally and opens it in a browser.

## Tether Cloud

Tether Cloud is the relay-backed mode for cross-machine coordination.

- hosted or self-hosted relay
- WebSocket push delivery
- agent discovery
- dashboard
- encrypted cross-machine handoff using relay-stored ciphertext envelopes

Upgrade does not change the protocol. It changes the transport.

### Pricing Model

| Tier | Purpose |
|------|---------|
| Free | TetherLite only |
| Duo | PAKE passphrase P2P |
| Basic | Hosted relay for small teams |
| Pro | Larger hosted relay footprint |
| Enterprise | Self-hosted relay and regulated environments |

## MCP Tools

| Tool | Purpose |
|------|---------|
| `tether_send` | Send a message handle to another agent |
| `tether_inbox` | List open messages for an agent |
| `tether_receive` | Read a message by handle |
| `tether_close` | Close a message or ticket thread |
| `tether_collapse` | Collapse JSON into a deterministic handle |
| `tether_resolve` | Resolve a handle back to JSON |
| `tether_collapse_blob` | Store bytes as a blob handle |
| `tether_resolve_blob` | Resolve a blob handle |
| `tether_collapse_tree` | Store a list of child handles |
| `tether_resolve_tree` | Resolve a tree handle |

## Handle Format

Typed handles are content-addressed:

- `h&l_inline_{hash12}`
- `h&l_blob_{hash12}`
- `h&l_tree_{hash12}`

The suffix is derived from canonical content. Identical content produces the same handle.

## PAKE P2P

Tether supports passphrase-authenticated peer-to-peer transport:

```bash
python -m tether_lite listen --passphrase "shared secret"
python -m tether_lite connect --passphrase "shared secret"
```

WAN rendezvous is available through the relay-assisted PAKE flow:

```bash
python -m tether_lite listen --passphrase "shared secret" --wan --relay-url http://relay:8000 --token TOKEN --local-addr HOST:PORT
python -m tether_lite connect --passphrase "shared secret" --wan --relay-url http://relay:8000 --key API_KEY --local-addr HOST:PORT
```

## Cross-Machine Demo

The repo includes a real encrypted relay demo:

```bash
python demos/cross_machine_demo.py --relay-url http://127.0.0.1:8124 --role senior --name senior-demo
python demos/cross_machine_demo.py --relay-url http://127.0.0.1:8124 --role junior --name junior-demo --target-name senior-demo
```

This demo exercises:

- agent registration
- pubkey discovery
- encrypted envelope upload
- WebSocket handle delivery
- ciphertext fetch
- local decryption
- encrypted reply

## Self-Hosting The Relay

The relay is a FastAPI service.

### Local Run

```bash
python -m uvicorn relay.main:app --host 127.0.0.1 --port 8000
```

### Docker Compose

```bash
docker-compose up --build
```

Environment is documented in [.env.example](.env.example).

If `tether-dashboard/dist` exists, the relay serves the dashboard at `/dashboard`.

### Health

- relay: `GET /health`
- ping daemons: `GET /health` on their local ports

## Security Model

Tether is designed around bounded trust:

- TetherLite data stays local unless you deliberately route it elsewhere.
- Relay routing metadata is visible to the relay.
- Cross-machine encrypted envelopes are encrypted before upload.
- The relay can store ciphertext for delivery, but it does not decrypt it.
- Public-key fetch and decryption happen on the client side.
- AGPL source keeps the transport and storage claims auditable.

This is not “the relay sees nothing at all.” It is “the relay never sees plaintext application payloads.”

## Changelog

Version notes live in [changelog/](changelog/).

| Version | Highlights |
|---------|------------|
| `v1.8` | TetherLite storage/runtime work, relay core, tier enforcement, encrypted envelopes |
| `v1.7` | Dashboard surfaces and agent graph work |
| `v1.6` | Ping registration and push notifications |
| `v1.5` | Shared task board |
| `v1.4` | Tags, read state, ergonomic CLI improvements |
| `v1.0-v1.3` | Base handle/runtime model |

## License

- TetherLite: AGPL v3
- Relay source: AGPL v3
- Hosted service terms: separate from source distribution
