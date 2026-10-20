#!/usr/bin/env bash
# Levanta Ryu y corre un escenario del campus, o solo la prueba de caminos.
# Uso: capture_campus.sh <verify|baseline|synflood|httpflood|slowloris|icmpflood> [segundos]
set -euo pipefail
cd "$(dirname "$0")"

SCENARIO="${1:?Uso: capture_campus.sh <verify|baseline|synflood|httpflood|slowloris|icmpflood> [segundos]}"
DURATION="${2:-120}"
export DATA_DIR="${DATA_DIR:-/ataque/data}"
export PYTHONDONTWRITEBYTECODE=1

RYU=/opt/ryu-venv/bin/ryu-manager
MONITOR=/ataque/mininet/flow_monitor_13.py
mn -c > /dev/null 2>&1 || true

# La app recolecta estadisticas OpenFlow y las guarda por corrida, para
# que pcap_to_csv.py las cruce con las conexiones. verify no las necesita.
# RUN_TAG (si viene) separa las corridas: synflood_sdn.csv -> synflood__r03_sdn.csv
if [ -n "${RUN_TAG:-}" ]; then
  RUN_NAME="${SCENARIO}__${RUN_TAG}"
else
  RUN_NAME="${SCENARIO}"
fi
export SDN_FLOWS_CSV="${DATA_DIR}/metrics/${RUN_NAME}_sdn.csv"
export SDN_POLL_INTERVAL="${SDN_POLL_INTERVAL:-1}"
mkdir -p "${DATA_DIR}/metrics"

echo "*** Arrancando Ryu (flow_monitor_13, con telemetria SDN)"
"$RYU" "$MONITOR" --ofp-tcp-listen-port 6653 > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 4

cleanup() { kill "$RYU_PID" > /dev/null 2>&1 || true; }
trap cleanup EXIT

if [ "$SCENARIO" = "verify" ]; then
  python3 ../mininet/topo.py test
else
  python3 ../mininet/capture_campus.py "$SCENARIO" "$DURATION"
fi
