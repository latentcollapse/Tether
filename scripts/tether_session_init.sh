#!/bin/bash
# Run once at tmux session start to wire autonomous Tether pings.
# Usage: bash tether_session_init.sh
set -e

DAEMON="/mnt/d/Language Projects/Tether/ping_daemon.py"

# agent:pane:port
AGENTS=("gemini:%4:7702" "qwen:%5:7701" "claude:%3:7703")

for spec in "${AGENTS[@]}"; do
    IFS=: read -r agent pane port <<< "$spec"
    # Enable pings by default
    touch "/tmp/tether-ping-$agent.enabled"
    echo "Starting ping daemon for $agent on port $port (pane $pane)..."
    nohup python3 "$DAEMON" --agent "$agent" --pane "$pane" --port "$port" > "/tmp/tether-daemon-$agent.log" 2>&1 &
    echo $! > "/tmp/tether-daemon-$agent.pid"
done

echo "All daemons started. Register endpoints with tether_register_ping."
echo "Toggle pings: bash tether_ping_toggle.sh [on|off] [agent|all]"
