#!/usr/bin/env bash
# Smoke test: levanta Ryu + la topologia y corre pingall.
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
    echo "OK: pingall sin perdidas. Entorno verificado."
else
    echo "FALLO: hubo perdidas en pingall. Revisa /tmp/ryu.log" >&2
fi

exit "$STATUS"
