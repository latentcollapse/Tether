#!/usr/bin/env bash
set -euo pipefail

ROOT="/mnt/d/Language Projects/Tether"
SRC_DIR="$ROOT/systemd"
DST_DIR="$HOME/.config/systemd/user"
SERVICES=(
  tether-ping-claude.service
  tether-ping-codex.service
  tether-ping-gemini.service
  tether-ping-qwen.service
)

mkdir -p "$DST_DIR"

for service in "${SERVICES[@]}"; do
  install -m 644 "$SRC_DIR/$service" "$DST_DIR/$service"
done

systemctl --user daemon-reload

for service in "${SERVICES[@]}"; do
  systemctl --user enable --now "$service"
done

for service in "${SERVICES[@]}"; do
  systemctl --user --no-pager --full status "$service" || true
done
