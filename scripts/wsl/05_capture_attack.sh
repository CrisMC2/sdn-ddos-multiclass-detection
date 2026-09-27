#!/usr/bin/env bash
# Levanta Ryu + la topologia, lanza un ataque desde attacker1 y lo
# captura en data/raw/attacks/<tipo>.pcap (separado del trafico normal).
#
# Uso: 05_capture_attack.sh <synflood|httpflood|slowloris|icmpflood> [duracion_s] [salida.pcap]
set -euo pipefail
cd "$(dirname "$0")"

ATTACK="${1:?Uso: 05_capture_attack.sh <synflood|httpflood|slowloris|icmpflood> [duracion_s] [salida.pcap]}"
DURATION="${2:-120}"
OUT="${3:-}"

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

echo "*** Lanzando ataque '$ATTACK' (${DURATION}s)"
if [ -n "$OUT" ]; then
    sudo python3 ../mininet/capture_attack.py "$ATTACK" "$DURATION" "$OUT"
else
    sudo python3 ../mininet/capture_attack.py "$ATTACK" "$DURATION"
fi
