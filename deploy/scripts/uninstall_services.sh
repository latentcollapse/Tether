#!/usr/bin/env bash
set -euo pipefail

DST_DIR="$HOME/.config/systemd/user"
SERVICES=(
  tether-ping-claude.service
  tether-ping-codex.service
  tether-ping-gemini.service
  tether-ping-qwen.service
)
AGENTS=(claude codex gemini qwen)

for service in "${SERVICES[@]}"; do
  systemctl --user disable --now "$service" 2>/dev/null || true
  rm -f "$DST_DIR/$service"
done

systemctl --user daemon-reload
systemctl --user reset-failed || true

for agent in "${AGENTS[@]}"; do
  rm -f "/tmp/tether-ping-$agent.enabled" "/tmp/tether-daemon-$agent.pid"
done
