#!/bin/bash
# Pin a Tether agent to a specific tmux pane ID.
# Writes to both persistent config and the /tmp session override.
#
# Usage: tether_set_pin.sh <agent> <pane_id>
# Example: tether_set_pin.sh codex %1
set -e

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <agent> <pane_id>"
    echo "Example: $0 codex %1"
    exit 1
fi

AGENT="$1"
PANE="$2"
PINS_DIR="$HOME/.config/tether"
PINS_FILE="$PINS_DIR/pane_pins.json"

mkdir -p "$PINS_DIR"

# Read existing pins, update the entry for this agent
if [[ -f "$PINS_FILE" ]]; then
    python3 -c "
import json, sys
with open('$PINS_FILE') as f:
    pins = json.load(f)
pins['$AGENT'] = '$PANE'
with open('$PINS_FILE', 'w') as f:
    json.dump(pins, f, indent=2)
    f.write('\n')
"
else
    python3 -c "
import json
with open('$PINS_FILE', 'w') as f:
    json.dump({'$AGENT': '$PANE'}, f, indent=2)
    f.write('\n')
"
fi

# Also write the /tmp session override so it takes effect immediately
echo "$PANE" > "/tmp/tether-pane-$AGENT"

echo "Pinned $AGENT -> $PANE (persistent + session)"
