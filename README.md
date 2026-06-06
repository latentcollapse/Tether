# Tether

## Foreword from me, Matt
Tether has single handedly kept a multi-agent novel programming language project coherent. My scatter-brain would've dumpstered something like this a long time ago, but it completely removes the need to keep track of a lot of minor things and your tickets and prompts can be structured by your coordinator model, enabling you to fundamentally work with one, but control an entire team through what's essentially a stripped down JIRA board. It's become a huge part of my workflow and has helped hold my projects together. I hope you all get as good of use out of it as I am.

## What it actually is

Tether is a CLI-to-CLI messaging layer. Any process that can call an MCP tool or run a shell command can send and receive messages. It does not care whether the process is an AI model, a build system, a monitoring script, or a human at a terminal. If it has an MCP server, it can have a Tether inbox.

This makes it fundamentally different from agent-to-agent orchestration frameworks, which are designed for service discovery and RPC between running API servers. Tether is async, persistent, and CLI-native. The canonical use case is coordinating Claude Code, Codex CLI, Gemini/Antigravity CLI, Hermes Agent, and similar tools across a local machine or across machines — but the protocol has no AI dependency.

It is recommended to maintain a standard operating procedure and job board for your project. These are not required, but they make multi-session workflows significantly more reliable.

The autoping feature for autonomous agent wake-up requires tmux. It carries the same cautions as running any AI in full-auto mode.

Tether has two operating modes:

- `TetherLite`: local-first, free forever, no relay required
- `Tether Cloud`: relay-backed delivery across machines

The same handle format, the same MCP tool names, and the same basic workflow apply in both.

## The Mobile Angle *(Planned feature, not yet implemented)*

Once you add a relay (self-hosted or Tether Cloud), Tether becomes a remote control for your local machine. Send a message from your phone, your tablet, or any browser. As long as the machine is on and the agent is running, it lands in the inbox and gets processed. No cloud middleman, no OAuth flow, no vendor dependency. It works like async email for your dev environment.

## What Tether Is Not

- Not an agent-to-agent orchestration framework. Tether does not handle service discovery, capability negotiation, or RPC between running servers.
- Not a compression tool. Handles are deterministic content-addressed pointers, not compressed payloads.
- Not a generic storage service. TetherLite keeps data local; the relay stores encrypted envelopes and routing metadata, not plaintext.
- Not tied to one model vendor. Tether is MCP-native and model-agnostic.

## How It Works

Collapse data into a handle, send the handle, resolve it on the other side.

```text
payload -> collapse -> handle -> send handle -> receive handle -> resolve
```

For local use, resolution happens against the local runtime.

For cross-machine encrypted handoff, the sender encrypts the payload for the recipient, uploads ciphertext to the relay, routes the handle, and the recipient fetches ciphertext and decrypts locally. The relay sees ciphertext and routing metadata, not plaintext.

### Install

```bash
git clone https://github.com/latentcollapse/tether.git
cd tether
pip install .
```

The built dashboard is committed in `tether-dashboard/dist`, so a basic install does not require Node.js or `npm run build`.

### CLI Commands

```bash
tether          # launches dashboard at http://localhost:3000
tether-mcp      # MCP server entry point used by MCP clients
```

If port `3000` is busy, `tether` falls back to the next free localhost port.

### MCP Setup

Add Tether to any MCP-compatible client:

```json
{
  "mcpServers": {
    "tether": {
      "command": "tether-mcp",
      "args": [],
      "env": {
        "TETHER_DB": "~/.local/share/tether/postoffice.db"
      }
    }
  }
}
```

Default `TETHER_DB` locations:

- Linux/Mac: `~/.local/share/tether/postoffice.db`
- Windows: `%APPDATA%\\tether\\postoffice.db`

All agents sharing the same machine should point to the same database file.

### First Message

These are MCP tool calls invoked from inside an AI client such as Claude Code, Codex CLI, or any MCP-compatible process. They are not shell commands.

```text
tether_send to="codex" subject="status" text="What changed?"
tether_inbox for_agent="codex"
tether_receive handle="h&l_messages_..."
```

### Dashboard

```bash
tether
```

That serves the built dashboard locally and opens it in a browser.

## Tether Cloud

Tether Cloud is the planned relay-backed mode for cross-machine coordination.

- hosted or self-hosted relay
- WebSocket push delivery
- agent discovery
- dashboard
- encrypted cross-machine handoff using relay-stored ciphertext envelopes

Upgrade does not change the protocol. It changes the transport.

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

This is not "the relay sees nothing at all." It is "the relay never sees plaintext application payloads."

## Changelog

Version notes live in [changelog/](changelog/).

| Version | Highlights |
|---------|------------|
| `v1.8` | TetherLite storage/runtime work, relay core, tier enforcement, encrypted envelopes |
| `v1.7` | Ping daemon, autoping, and local delivery tooling |
| `v1.6` | Ping registration and push notifications |
| `v1.5` | Shared task board |
| `v1.4` | Tags, read state, ergonomic CLI improvements |
| `v1.0-v1.3` | Base handle/runtime model |

## License

- TetherLite: AGPL v3
- Relay source: AGPL v3
- Hosted service terms: separate from source distribution
