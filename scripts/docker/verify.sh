#!/usr/bin/env bash
# Prueba de caminos: alumno -> portal, infectado -> portal, C2 -> infectado.
set -euo pipefail
cd "$(dirname "$0")"

RYU=/opt/ryu-venv/bin/ryu-manager

mn -c > /dev/null 2>&1 || true

"$RYU" ryu.app.simple_switch_13 --ofp-tcp-listen-port 6653 > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 3

cleanup() { kill "$RYU_PID" > /dev/null 2>&1 || true; }
trap cleanup EXIT

python3 ../mininet/topo.py test
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo "OK: el alumno, el infectado y el C2 llegan a donde tienen que llegar."
else
    echo "FALLO: algun camino no responde. Revisa /tmp/ryu.log" >&2
    cat /tmp/ryu.log >&2 || true
fi

exit "$STATUS"
