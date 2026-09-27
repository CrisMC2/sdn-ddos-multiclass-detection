#!/usr/bin/env bash
# Levanta Ryu + la topologia, genera trafico HTTP normal desde los
# clientes y lo captura en data/raw/normal/normal.pcap
#
# Uso: 04_capture_normal.sh [duracion_s] [salida.pcap]
set -euo pipefail
cd "$(dirname "$0")"

DURATION="${1:-300}"
OUT="${2:-../../data/raw/normal/normal.pcap}"

RYU="$HOME/ataque-ryu-venv/bin/ryu-manager"
if [ ! -x "$RYU" ]; then
    echo "Falta el venv de Ryu. Corre 02_setup_ryu_venv.sh primero." >&2
    exit 1
fi

sudo mn -c > /dev/null 2>&1 || true

echo "*** Arrancando Ryu (simple_switch_13)..."
sudo "$RYU" ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653 > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

cleanup() { sudo kill "$RYU_PID" > /dev/null 2>&1 || true; }
trap cleanup EXIT

echo "*** Generando y capturando trafico normal (${DURATION}s) -> ${OUT}"
sudo python3 ../mininet/capture_normal.py "$DURATION" "$OUT"
