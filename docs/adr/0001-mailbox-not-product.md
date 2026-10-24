# 0001 — mailbox, not a product

## Decision

Tether is a local SQLite mailbox with a CLI and an MCP stdio adapter.

There is no long-running daemon, HTTP server, dashboard, Konsole/PTY injector, job board, identity lattice, custom encoding, or content-addressed message id.

## Why

The Python tree grew those surfaces around a three-call contract (`send` / `inbox` / `recv`) until the bus was unusable. A payload digest is a good name for a blob and a bad name for an intent: two deliberate sends of the same text must remain two rows.

SQLite WAL already coordinates multiple CLI processes on one machine. A daemon would exist to own a socket for wake-up. Wake-up is not the record; agents poll the inbox.

## Consequences

- `tether off` is a sentinel file next to the database.
- Blobs, encryption, and terminal wake wait for a demonstrated need.
- The frozen Python tree in `Tether/` is not a dependency.
