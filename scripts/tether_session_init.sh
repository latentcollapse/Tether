#!/bin/bash
# Run once at session start to wire autonomous Tether pings.
# No tmux required — notifications fire via desktop notify-send + ~/.tether_notify.
# Usage: bash tether_session_init.sh
set -e

DAEMON="/mnt/d/Language Projects/Tether/tether/ping_daemon.py"

# agent:port
AGENTS=("claude:7703" "codex:7704" "gemini:7702" "qwen:7701")

for spec in "${AGENTS[@]}"; do
    IFS=: read -r agent port <<< "$spec"
    touch "/tmp/tether-ping-$agent.enabled"
    echo "Starting ping daemon for $agent on port $port..."
    nohup python3 "$DAEMON" --agent "$agent" --port "$port" > "/tmp/tether-daemon-$agent.log" 2>&1 &
    echo $! > "/tmp/tether-daemon-$agent.pid"
done

echo "All daemons started."
echo "Toggle pings: bash tether_ping_toggle.sh [on|off] [agent|all]"
