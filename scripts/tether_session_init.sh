#!/bin/bash
# Run once at session start to wire autonomous Tether pings.
#
# Delivery model:
#   claude/codex/gemini/qwen  — tmux send-keys injection after idle detection
#   desktop-only agents       — pass --delivery-mode desktop explicitly
#
# Usage: bash tether_session_init.sh
# Prefer: bash scripts/install_services.sh
set -e

DAEMON="/mnt/d/Language Projects/Tether/tether/ping_daemon.py"

# Terminal agents: agent:port
TERMINAL_AGENTS=("claude:7703" "codex:7704" "gemini:7702" "qwen:7701")

for spec in "${TERMINAL_AGENTS[@]}"; do
    IFS=: read -r agent port <<< "$spec"
    touch "/tmp/tether-ping-$agent.enabled"
    echo "Starting ping daemon for $agent on port $port (dynamic tmux discovery)..."
    nohup python3 "$DAEMON" --agent "$agent" --delivery-mode tmux --port "$port" > "/tmp/tether-daemon-$agent.log" 2>&1 &
    echo $! > "/tmp/tether-daemon-$agent.pid"
done

echo "All daemons started."
echo "Toggle pings: bash tether_ping_toggle.sh [on|off] [agent|all]"
