#!/usr/bin/env bash
# Cuando el encargado te entregue el escaneo / captura Wireshark:
#
#   1. Copia el .pcap o .pcapng a data/real/wireshark/
#   2. Corre:
#        bash usar_datos_reales.sh
#
# Eso anonimiza, mezcla con los ataques de la simulacion, entrena
# el modelo y deja el informe listo. El ataque NO toca la red real.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

WIRE="$ROOT/data/real/wireshark"
mkdir -p "$WIRE"

# Si pasaste archivos como argumentos, copialos a la carpeta.
if [ "$#" -gt 0 ]; then
  for f in "$@"; do
    if [ ! -f "$f" ]; then
      echo "No existe: $f" >&2
      exit 1
    fi
    cp -f "$f" "$WIRE/"
    echo "Copiado: $f -> $WIRE/"
  done
fi

shopt -s nullglob
PCAPS=("$WIRE"/*.pcap "$WIRE"/*.pcapng)
shopt -u nullglob

if [ "${#PCAPS[@]}" -eq 0 ]; then
  echo "No hay capturas en:"
  echo "  $WIRE"
  echo ""
  echo "Ejemplos:"
  echo "  bash usar_datos_reales.sh ~/Descargas/alumnos.pcapng"
  echo "  # o copia el archivo a data/real/wireshark/ y vuelve a correr"
  exit 1
fi

echo "Capturas encontradas:"
for f in "${PCAPS[@]}"; do echo "  - $(basename "$f")"; done
echo ""

# Asegurar que existan los CSV de ataque de la simulacion.
NEED_CONVERT=0
for s in baseline synflood httpflood slowloris icmpflood; do
  if [ ! -f "$ROOT/data/processed/${s}.csv" ]; then
    NEED_CONVERT=1
  fi
done
if [ "$NEED_CONVERT" -eq 1 ]; then
  echo "Faltan CSV de la simulacion. Convirtiendo pcap existentes..."
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    bash "$ROOT/scripts/docker/run_scenario.sh" convert
  else
    echo "Abre Docker Desktop y corre: bash scripts/docker/run_scenario.sh convert" >&2
    exit 1
  fi
fi

bash "$ROOT/scripts/docker/preparar_hibrido.sh"

echo ""
echo "=============================="
echo "Listo. Abre estos archivos:"
echo "  notebooks/resultados/informe_hibrido.txt"
echo "  notebooks/resultados/comparacion.txt"
echo "  notebooks/resultados/informe.txt"
echo "=============================="
