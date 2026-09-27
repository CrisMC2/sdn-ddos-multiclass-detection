#!/usr/bin/env bash
# Convierte data/raw/*.pcap a data/processed/*.csv, etiquetados.
set -euo pipefail
cd "$(dirname "$0")"

CFM="$HOME/ataque-cfm-venv/bin/python3"
if [ ! -x "$CFM" ]; then
    echo "Falta el venv de CICFlowMeter. Corre 06_setup_cfm_venv.sh primero." >&2
    exit 1
fi

"$CFM" ../mininet/pcap_to_csv.py
