#!/bin/sh
# Copy to ~/.config/tether/wake/<agent> and make executable.
# This process is the turn. It is not a Konsole injector.
set -e
: "${TETHER_AGENT_ID:?}"
home="${TETHER_HOME:-$HOME/.local/share/tether}"
mkdir -p "$home/wake"
lock="$home/wake/$TETHER_AGENT_ID.lock"
exec 9>"$lock"
flock -n 9 || exit 0

# Drain this message, do the work, reply, then check for more.
# Replace the next line with the real one-shot for this agent, e.g.:
#   exec claude -p "Tether mail id $TETHER_MSG_ID. tether recv, do the work, tether send the result, exit."
#   exec grok -p "..."
#   exec codex exec "..."
printf '%s\n' "wake $TETHER_AGENT_ID $TETHER_MSG_ID" >&2
exit 0
