# Wake

Tether never types into a terminal. If an idle worker should start when mail arrives, put an executable at:

```
~/.config/tether/wake/<agent>
```

`tether send` writes the row, then spawns that script with the message id. Env:

- `TETHER_AGENT_ID` — the recipient
- `TETHER_DB` — shared mailbox
- `TETHER_MSG_ID` — the row just written
- `TETHER_HOME` — data dir (pid and logs live in `$TETHER_HOME/wake/`)

Stdout/stderr append to `$TETHER_HOME/wake/<agent>.log`. If a worker pid for that agent is still alive, send skips the spawn. Drain the inbox at the end of the script if you want the next mail in the same turn.

Do not install a hook for the agent sitting in the human's tab.

A template is in `tools/wake/worker.sh`. Copy, rename to the agent, point the last line at `claude -p`, `codex exec`, `grok -p`, or whatever one-shot that CLI has.

The waiting side:

```
tether recv --wait --timeout 120 gemini
```
