#!/usr/bin/env bash
# start-agents.sh — launch all agents in named tmux sessions
# Usage: ./start-agents.sh [--attach <name>]
#
# Creates (or reuses) tmux sessions: claude, codex, qwen
# Each session starts its agent CLI in the Language Projects working directory.
# Tether pings use tmux send-keys to inject prompts automatically.

set -e

WORKDIR="/mnt/d/Language Projects"

start_session() {
    local name="$1"
    local cmd="$2"

    if tmux has-session -t "$name" 2>/dev/null; then
        echo "  [$name] session already running — skipping"
    else
        tmux new-session -d -s "$name" -c "$WORKDIR" "$cmd"
        echo "  [$name] started"
    fi
}

echo "Starting agent sessions..."
start_session "claude" "claude"
start_session "codex"  "codex"
start_session "qwen"   "qwen"

echo ""
echo "All sessions up. To attach:"
echo "  tmux attach -t claude"
echo "  tmux attach -t codex"
echo "  tmux attach -t qwen"
echo ""
echo "To detach from any session: Ctrl+B, D"
echo "To list sessions:           tmux ls"

# Optional: attach immediately if --attach <name> passed
if [[ "$1" == "--attach" && -n "$2" ]]; then
    tmux attach -t "$2"
fi
