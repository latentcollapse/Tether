#!/usr/bin/env bash
set -euo pipefail

agent="${1:-codex}"
port="${2:-7704}"
buffer="/tmp/tether-ping-${agent}.txt"

rm -f "$buffer"

curl -fsS \
  -X POST "http://localhost:${port}" \
  -H 'Content-Type: application/json' \
  -d "{\"from\":\"autoping-smoke\",\"handle\":\"h&l_messages_test\"}" >/dev/null

for _ in 1 2 3 4 5 6; do
  if [[ -s "$buffer" ]]; then
    echo "ok: $buffer"
    exit 0
  fi
  sleep 0.5
done

echo "buffer not written within 3s: $buffer" >&2
exit 1
