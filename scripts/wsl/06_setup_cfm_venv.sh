#!/usr/bin/env bash
# Crea un venv con CICFlowMeter (reimplementacion en Python), separado
# del venv de Ryu porque usa una version de Python distinta (el
# sistema, no la 3.9 de deadsnakes) y no tiene los mismos problemas de
# compatibilidad que Ryu.
set -euo pipefail

REAL_VENV="$HOME/ataque-cfm-venv"

python3 -m venv "$REAL_VENV"
"$REAL_VENV/bin/pip" install --upgrade pip
"$REAL_VENV/bin/pip" install cicflowmeter

echo "OK: entorno virtual de CICFlowMeter listo en $REAL_VENV"
