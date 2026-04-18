#!/bin/bash
# Run once at session start to wire autonomous Tether pings.
#
# Delivery model:
#   claude  — desktop notify + ~/.tether_notify (no tmux, safe for Claude Code)
#   others  — tmux send-keys injection after idle detection
#
# Usage: bash tether_session_init.sh
set -e

DAEMON="/mnt/d/Language Projects/Tether/tether/ping_daemon.py"

# Claude: no --pane needed
touch /tmp/tether-ping-claude.enabled
echo "Starting ping daemon for claude on port 7703 (desktop notify)..."
nohup python3 "$DAEMON" --agent claude --port 7703 > /tmp/tether-daemon-claude.log 2>&1 &
echo $! > /tmp/tether-daemon-claude.pid

# Terminal agents: agent:pane:port
TERMINAL_AGENTS=("codex:%4:7704" "gemini:%5:7702" "qwen:%6:7701")

for spec in "${TERMINAL_AGENTS[@]}"; do
    IFS=: read -r agent pane port <<< "$spec"
    touch "/tmp/tether-ping-$agent.enabled"
    echo "Starting ping daemon for $agent on port $port (tmux pane $pane)..."
    nohup python3 "$DAEMON" --agent "$agent" --pane "$pane" --port "$port" > "/tmp/tether-daemon-$agent.log" 2>&1 &
    echo $! > "/tmp/tether-daemon-$agent.pid"
done

echo "All daemons started."
echo "Toggle pings: bash tether_ping_toggle.sh [on|off] [agent|all]"
