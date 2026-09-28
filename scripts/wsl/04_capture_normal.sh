#!/usr/bin/env bash
# Baseline del campus: alumnos (y las PCs aun no usadas para atacar)
# navegan el portal. Uso: 04_capture_normal.sh [duracion_s]
set -euo pipefail
cd "$(dirname "$0")"

DURATION="${1:-120}"

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

echo "*** Baseline del campus (${DURATION}s)"
sudo python3 ../mininet/capture_campus.py baseline "$DURATION"
