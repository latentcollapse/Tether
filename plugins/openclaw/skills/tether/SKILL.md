---
name: tether
description: Use Tether tools for cross-agent messaging and deterministic handle exchange.
---

# Tether

Use these tools when the task crosses agent or framework boundaries.

OpenClaw users do not need tmux for inbound Tether delivery. Notifications arrive natively through the plugin HTTP route and are injected into the active OpenClaw session.

## When to use which tool

- `tether_send`
  - send a message to another agent
  - use when you already know the recipient and want to hand off work or report completion
- `tether_inbox`
  - inspect pending handles for the current Tether agent
  - use before claiming there is no new work
- `tether_receive`
  - resolve one message handle into the full stored message
  - use after `tether_inbox` or after an inbound `[Tether] ... handle: ...` notification
- `tether_collapse`
  - store structured JSON and get a deterministic handle back
  - use when the payload is too large or too structured to paste inline
- `tether_resolve`
  - resolve a deterministic handle back into JSON
  - use when a message contains a handle instead of the full payload

## Working pattern

1. Check `tether_inbox`
2. Resolve the chosen handle with `tether_receive`
3. Do the work
4. Send back a concise completion note with `tether_send`

## Defaults

- `tether_send` defaults `from_agent` to the plugin-configured agent name
- `tether_inbox` defaults `for_agent` to the plugin-configured agent name
- `tether_receive` defaults `for_agent` to the plugin-configured agent name

## Handle format

Tether handles are deterministic ids such as:

```text
h&l_messages_deadbeef
```

or other table-specific values returned by `tether_collapse`.

Do not mutate handle strings manually.

## Example

Send a handoff:

```json
{
  "to": "claude",
  "subject": "T-053 done",
  "text": "Plugin package is built and validated."
}
```

Resolve an inbound handle:

```json
{
  "handle": "h&l_messages_deadbeef"
}
```
