#!/usr/bin/env bash
# Procesa capturas Wireshark reales + ataques de simulacion y deja el
# informe hibrido listo para analizar.
#
# Antes:
#   1. Copia los .pcap / .pcapng del encargado a data/real/wireshark/
#   2. Asegurate de tener data/processed/*.csv de la simulacion
#      (bash scripts/docker/run_scenario.sh convert)
#
# Uso:
#   bash scripts/docker/preparar_hibrido.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

WIRE="$ROOT/data/real/wireshark"
shopt -s nullglob
PCAPS=("$WIRE"/*.pcap "$WIRE"/*.pcapng)
shopt -u nullglob

if [ "${#PCAPS[@]}" -eq 0 ]; then
  echo "No hay capturas en $WIRE"
  echo "Copia ahi el .pcap que te dio el encargado y vuelve a correr."
  echo "Mientras tanto se actualiza solo el analisis de simulacion."
  "$PY" "$ROOT/notebooks/analisis_completo.py"
  echo ""
  echo "Lee: $ROOT/notebooks/resultados/informe.txt"
  exit 0
fi

echo "=== 1) Anonimizar Wireshark y extraer flujos BENIGN ==="
"$PY" "$ROOT/scripts/analysis/ingest_wireshark.py"

echo "=== 2) Armar dataset hibrido ==="
"$PY" "$ROOT/scripts/analysis/build_hybrid_dataset.py"

echo "=== 3) Entrenar y escribir informes ==="
"$PY" "$ROOT/notebooks/analisis_completo.py"

echo ""
echo "Listo. Lee en este orden:"
echo "  $ROOT/notebooks/resultados/informe.txt"
echo "  $ROOT/notebooks/resultados/informe_hibrido.txt"
echo "  $ROOT/notebooks/resultados/comparacion.txt"
echo "Documento para el encargado:"
echo "  $ROOT/docs/documento_encargado.docx"
