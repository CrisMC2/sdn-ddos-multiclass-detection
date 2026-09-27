#!/usr/bin/env bash
# Lanza un ataque y lo captura. Uso: capture_attack.sh <synflood|httpflood|slowloris|icmpflood> [duracion_s] [salida.pcap]
set -euo pipefail
cd "$(dirname "$0")"

ATTACK="${1:?Uso: capture_attack.sh <synflood|httpflood|slowloris|icmpflood> [duracion_s] [salida.pcap]}"
DURATION="${2:-120}"
OUT="${3:-}"
RYU=/opt/ryu-venv/bin/ryu-manager

mn -c > /dev/null 2>&1 || true

"$RYU" ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653 > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

cleanup() { kill "$RYU_PID" > /dev/null 2>&1 || true; }
trap cleanup EXIT

echo "*** Lanzando ataque '$ATTACK' (${DURATION}s)"
if [ -n "$OUT" ]; then
    python3 ../mininet/capture_attack.py "$ATTACK" "$DURATION" "$OUT"
else
    python3 ../mininet/capture_attack.py "$ATTACK" "$DURATION"
fi
