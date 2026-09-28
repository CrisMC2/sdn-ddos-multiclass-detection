#!/usr/bin/env bash
# Ataque desde las PCs infectadas. Uso: capture_attack.sh <synflood|httpflood|slowloris|icmpflood> [segundos]
set -euo pipefail
cd "$(dirname "$0")"
ATTACK="${1:?Uso: capture_attack.sh <synflood|httpflood|slowloris|icmpflood> [segundos]}"
DURATION="${2:-120}"
exec bash ./capture_campus.sh "$ATTACK" "$DURATION"
