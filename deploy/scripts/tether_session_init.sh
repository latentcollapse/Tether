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

# Name tmux sessions so the MCP server's primary injection path works.
# The MCP server does `tmux has-session -t <agent>` — requires named sessions.
# Without this, delivery falls back to the HTTP daemon path only (janky).
echo "Naming tmux sessions..."
tmux rename-session -t 0 claude 2>/dev/null && echo "  session 0 -> claude" || echo "  session claude already named or missing"
tmux rename-session -t 1 codex  2>/dev/null && echo "  session 1 -> codex"  || echo "  session codex already named or missing"
tmux rename-session -t 2 gemini 2>/dev/null && echo "  session 2 -> gemini" || echo "  session gemini already named or missing"

# Pin pane IDs — written to persistent config (survives reboots) and /tmp (session override)
PINS_DIR="$HOME/.config/tether"
PINS_FILE="$PINS_DIR/pane_pins.json"
mkdir -p "$PINS_DIR"
cat > "$PINS_FILE" <<'EOF'
{
  "claude": "%0",
  "codex": "%1",
  "gemini": "%2"
}
EOF
echo "  pane pins saved to $PINS_FILE"

echo "%0" > /tmp/tether-pane-claude
echo "%1" > /tmp/tether-pane-codex
echo "%2" > /tmp/tether-pane-gemini

# Terminal agents: agent:port
TERMINAL_AGENTS=("claude:7703" "codex:7704" "gemini:7702" "qwen:7701" "deepseek:7705")

for spec in "${TERMINAL_AGENTS[@]}"; do
    IFS=: read -r agent port <<< "$spec"
    touch "/tmp/tether-ping-$agent.enabled"
    echo "Starting ping daemon for $agent on port $port..."
    nohup python3 "$DAEMON" --agent "$agent" --delivery-mode tmux --port "$port" > "/tmp/tether-daemon-$agent.log" 2>&1 &
    echo $! > "/tmp/tether-daemon-$agent.pid"
done

echo "All daemons started."
echo "Toggle pings: bash tether_ping_toggle.sh [on|off] [agent|all]"
