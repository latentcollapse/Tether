#!/bin/bash
# Tether ping toggle — enable/disable autonomous pings per agent or globally.
# Usage:
#   bash tether_ping_toggle.sh          # show status for all agents
#   bash tether_ping_toggle.sh on       # enable all
#   bash tether_ping_toggle.sh off      # disable all
#   bash tether_ping_toggle.sh on gemini  # enable just gemini
#   bash tether_ping_toggle.sh off qwen   # disable just qwen

ENABLE_DIR="/tmp"
AGENTS=("gemini" "qwen" "claude")

action="${1:-status}"
target="${2:-all}"

enable_agent() {
    local agent=$1
    touch "$ENABLE_DIR/tether-ping-$agent.enabled"
    echo "[$agent] pings ENABLED"
}

disable_agent() {
    local agent=$1
    rm -f "$ENABLE_DIR/tether-ping-$agent.enabled"
    echo "[$agent] pings DISABLED"
}

show_status() {
    local agent=$1
    if [ -f "$ENABLE_DIR/tether-ping-$agent.enabled" ]; then
        echo "[$agent] ON"
    else
        echo "[$agent] OFF"
    fi
}

if [ "$action" = "on" ]; then
    if [ "$target" = "all" ]; then
        for a in "${AGENTS[@]}"; do enable_agent "$a"; done
    else
        enable_agent "$target"
    fi
elif [ "$action" = "off" ]; then
    if [ "$target" = "all" ]; then
        for a in "${AGENTS[@]}"; do disable_agent "$a"; done
    else
        disable_agent "$target"
    fi
else
    echo "=== Tether Ping Status ==="
    for a in "${AGENTS[@]}"; do show_status "$a"; done
    echo ""
    echo "Usage: $0 [on|off] [agent|all]"
fi
