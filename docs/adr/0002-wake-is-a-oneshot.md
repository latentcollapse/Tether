# 0002 — wake is a one-shot process

## Decision

A send may spawn `~/.config/tether/wake/<agent>` if that file is executable and no worker for that agent is already running. The worker is a detached process. It is not a TUI injector, not a Konsole D-Bus client, and not a long-running daemon.

`tether recv --wait` polls the mailbox. The waiting agent sees a tool result. The human does not see a second terminal.

## Why

The previous product typed into a live composer. That required prompt-state detection, draft safety, KDE D-Bus, and a ping loop. The mailbox was already the record. Wake only needs to start a turn.

## Consequences

- No hook means no wake. Grok (the human's pair) should not have a hook.
- One pid file per agent. A live worker skips further spawns; unread mail waits in SQLite.
- Spawn failure prints a warning and does not fail the send.
- Broadcast `*` does not wake anyone.
