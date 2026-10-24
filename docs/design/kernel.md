# Kernel

Two tables.

```sql
messages (id, ts, from_agent, to_agent, thread, subject, body)
acks     (id, agent, acked_at)   -- primary key (id, agent)
```

`to_agent` is a name, or `*` for everyone. An inbox for `grok` is rows addressed to `grok` or `*` that `grok` has not acked. `recv` returns the body and acks. Two agents ack a broadcast independently.

Ids are timestamp-ordered hex, unique per send. The body is not hashed.

The process is one binary. `tether mcp` speaks newline-delimited JSON-RPC on stdio. Everything else is a subcommand against the same crate.
