#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
/opt/cfm-venv/bin/python3 ../mininet/pcap_to_csv.py
