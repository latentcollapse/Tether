# Tether OpenClaw Plugin

This plugin gives OpenClaw a first-class Tether transport surface:

- inbound Tether delivery that wakes an OpenClaw session without polling
- outbound Tether tools backed by the local `tether/mcp_server.py`
- content-addressed handle exchange instead of raw session transcript copying
- a clean bridge to non-OpenClaw agents such as Claude Code, Codex CLI, and Gemini

This is not just an `mcporter` wrapper. `mcporter` can call MCP tools, but it does not solve inbound delivery, autonomous wake, cross-framework routing, or OpenClaw session injection.

## What it registers

- HTTP ingress:
  - primary plugin route: `/plugins/tether/notify`
  - hooks-compatible alias: `/hooks/tether` when OpenClaw's core hooks path is not already `/hooks`
  - health route: `/plugins/tether/health`
- agent tools:
  - `tether_send`
  - `tether_inbox`
  - `tether_receive`
  - `tether_collapse`
  - `tether_resolve`

Inbound payload shape matches Tether's ping path:

```json
{
  "from": "claude",
  "handle": "h&l_messages_deadbeef",
  "subject": "T-053 done"
}
```

The plugin injects:

```text
[Tether] From claude: T-053 done — handle: h&l_messages_deadbeef
```

## Install

1. Load the plugin directory with OpenClaw, for example under `plugins.load.paths`.
2. Ensure Python 3 is available.
3. Ensure the Python environment that runs the helper has the `mcp` package installed.
4. Point the plugin at your Tether DB and MCP server path.

Minimal config:

```json
{
  "plugins": {
    "allow": ["tether"],
    "load": {
      "paths": ["/mnt/d/Language Projects/Tether/openclaw-plugin"]
    },
    "entries": {
      "tether": {
        "enabled": true,
        "config": {
          "agent": "openclaw",
          "sessionKey": "hook:tether",
          "lane": "tether"
        }
      }
    }
  }
}
```

## Environment

The plugin uses these environment variables:

- `TETHER_DB`
  - required in practice
  - path to the Tether SQLite database
- `TETHER_NOTIFY_PORT`
  - default: `7705`
  - used to build the callback URL when `plugins.entries.tether.config.notifyUrl` is unset
  - this is the OpenClaw gateway HTTP port, not a separate plugin listener
- `TETHER_MCP_PATH`
  - optional override for `tether/mcp_server.py`
  - auto-detected relative to the plugin when unset

Example shell env:

```bash
export TETHER_DB="/mnt/d/Language Projects/Tether/postoffice.db"
export TETHER_NOTIFY_PORT="7705"
export TETHER_MCP_PATH="/mnt/d/Language Projects/Tether/tether/mcp_server.py"
```

The plugin also accepts the same values directly under `plugins.entries.tether.config` as `dbPath`, `notifyUrl`, and `mcpPath`.

## Callback registration

On plugin load, it calls `tether_register_ping(agent=..., url=...)` against the local Tether MCP server.

URL selection order:

1. `plugins.entries.tether.config.notifyUrl`
2. `TETHER_NOTIFY_URL`
3. `http://127.0.0.1:${TETHER_NOTIFY_PORT}${notifyPath}`

Primary path selection:

- if OpenClaw core hooks already own `/hooks`, the plugin registers `/plugins/tether/notify`
- otherwise it prefers `/hooks/tether`

## Hook Mapping Snippet

If you want a bearer-authenticated OpenClaw core hooks route in front of the same message shape, use this config. This is an alternative ingress path, not the plugin-owned callback route.

```json
{
  "hooks": {
    "enabled": true,
    "path": "/hooks",
    "token": "replace-me",
    "mappings": [
      {
        "id": "tether",
        "match": { "path": "tether" },
        "action": "agent",
        "wakeMode": "now",
        "sessionKey": "hook:tether",
        "messageTemplate": "[Tether] From {{payload.from}}: {{payload.subject}} — handle: {{payload.handle}}"
      }
    ]
  }
}
```

Send the token as:

```http
Authorization: Bearer replace-me
```

## Why this is more than mcporter

`mcporter` solves outbound MCP invocation. It does not solve:

- inbound delivery into an active OpenClaw session
- autonomous wake on new Tether mail
- cross-framework coordination between OpenClaw and non-OpenClaw agents
- deterministic content-addressed handles with storage/retrieval semantics already shared by Tether

This plugin gives OpenClaw both halves of the transport:

- outbound tool calls over MCP stdio
- inbound message delivery over HTTP into gateway session routing

## Validation

Useful checks once loaded:

- `GET /plugins/tether/health`
- run `tether_send` from an OpenClaw session
- verify `tether_inbox` and `tether_receive` default to the configured plugin agent name
- verify a Tether ping POST injects into the most recently active session or the configured fallback session key
