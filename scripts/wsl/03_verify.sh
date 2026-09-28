#!/usr/bin/env bash
# Levanta Ryu (simple_switch_13, solo para probar conectividad L2),
# arranca la topologia y corre pingall. Deja todo apagado al terminar.
set -euo pipefail
cd "$(dirname "$0")"

RYU="../ryu/venv/bin/ryu-manager"
if [ ! -x "$RYU" ]; then
    echo "Falta el venv de Ryu. Corre 02_setup_ryu_venv.sh primero." >&2
    exit 1
fi

echo "*** Limpiando estado previo de Mininet..."
sudo mn -c > /dev/null 2>&1 || true

echo "*** Arrancando Ryu (simple_switch_13) en background..."
sudo "$RYU" ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653 > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

cleanup() {
    sudo kill "$RYU_PID" > /dev/null 2>&1 || true
}
trap cleanup EXIT

echo "*** Arrancando topologia y corriendo pingall..."
sudo python3 ../mininet/topo.py test
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo "OK: el alumno, el infectado y el C2 llegan a donde tienen que llegar."
else
    echo "FALLO: algun camino no responde. Revisa /tmp/ryu.log" >&2
fi

exit "$STATUS"
