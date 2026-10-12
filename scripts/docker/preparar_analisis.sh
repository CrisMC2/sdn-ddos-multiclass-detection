#!/usr/bin/env bash
# Deja listo el informe. Sin argumentos no captura: reentrena con los
# CSV que ya estan y escribe notebooks/resultados/informe.txt.
#
# Para volver a capturar los cinco escenarios (120 s) y rehacer el informe:
#   bash scripts/docker/preparar_analisis.sh --capturar
#   bash scripts/docker/preparar_analisis.sh --capturar 120
#
# Durante --capturar, si abres http://127.0.0.1:8080/ cuando el log diga
# "Portal benigno listo", ese trafico entra al dataset. Si no lo abres,
# el informe sale igual, solo con los alumnos emulados.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [ "${1:-}" = "--capturar" ]; then
  DURATION="${2:-120}"
  bash "$ROOT/scripts/docker/run_scenario.sh" all "$DURATION"
  bash "$ROOT/scripts/docker/run_scenario.sh" convert
fi

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

"$PY" "$ROOT/notebooks/analisis_completo.py"
# Cuaderno opcional (mismas cifras):
# "$PY" -m jupyter nbconvert --execute --inplace --ExecutePreprocessor.timeout=600 \
#   "$ROOT/notebooks/deteccion_ddos.ipynb"

echo ""
echo "Listo. Lee este archivo:"
echo "  $ROOT/notebooks/resultados/informe.txt"
echo "La tabla del articulo quedo en paper/tabla_resultados.tex"
