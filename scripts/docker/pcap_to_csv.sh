#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export DATA_DIR="${DATA_DIR:-/ataque/data}"
export PYTHONDONTWRITEBYTECODE=1
exec /opt/cfm-venv/bin/python3 ../mininet/pcap_to_csv.py
