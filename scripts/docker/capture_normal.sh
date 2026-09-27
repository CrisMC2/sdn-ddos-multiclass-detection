#!/usr/bin/env bash
# Genera y captura trafico HTTP normal. Uso: capture_normal.sh [duracion_s] [salida.pcap]
set -euo pipefail
cd "$(dirname "$0")"

DURATION="${1:-300}"
OUT="${2:-../data/raw/normal/normal.pcap}"
RYU=/opt/ryu-venv/bin/ryu-manager

mn -c > /dev/null 2>&1 || true

"$RYU" ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653 > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

cleanup() { kill "$RYU_PID" > /dev/null 2>&1 || true; }
trap cleanup EXIT

echo "*** Generando y capturando trafico normal (${DURATION}s) -> ${OUT}"
python3 ../mininet/capture_normal.py "$DURATION" "$OUT"
