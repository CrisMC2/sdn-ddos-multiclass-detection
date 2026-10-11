#!/usr/bin/env bash
# Corre un escenario en Docker Desktop (macOS, Linux o Windows) y, en
# paralelo, anota CPU, memoria y red del contenedor.
#
# Uso, desde la raiz del repo:
#   bash scripts/docker/run_scenario.sh verify
#   bash scripts/docker/run_scenario.sh baseline 20
#   bash scripts/docker/run_scenario.sh httpflood 20
#   bash scripts/docker/run_scenario.sh convert
#   bash scripts/docker/run_scenario.sh all 20
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE:-ataque-sdn}"
NAME="ataque-sdn-run"
BENIGN_PORT="${BENIGN_PORT:-8080}"

usage() {
  echo "Uso: bash scripts/docker/run_scenario.sh <verify|baseline|synflood|httpflood|slowloris|icmpflood|all|convert> [segundos]" >&2
  exit 1
}

SCENARIO="${1:-}"
DURATION="${2:-120}"
[ -n "$SCENARIO" ] || usage

if ! command -v docker >/dev/null 2>&1; then
  echo "No esta el comando docker. Abre Docker Desktop y vuelve a correr esto." >&2
  exit 1
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "No esta la imagen $IMAGE. Construyendola; la primera vez tarda varios minutos."
  docker build -t "$IMAGE" -f "$ROOT/scripts/docker/Dockerfile" "$ROOT"
fi

cleanup() {
  if [ -n "${SAMPLER_PID:-}" ]; then
    kill "$SAMPLER_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "${LOG_PID:-}" ]; then
    kill "$LOG_PID" >/dev/null 2>&1 || true
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap 'cleanup; exit 130' INT TERM

run_convert() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker run --rm --name "$NAME" --entrypoint bash \
    -e DATA_DIR=/ataque/data \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -v "$ROOT/data:/ataque/data" \
    -v "$ROOT/scripts/mininet:/ataque/mininet:ro" \
    "$IMAGE" \
    /ataque/scripts/pcap_to_csv.sh
}

run_one() {
  local scenario="$1"
  local duration="$2"
  local stats="$ROOT/data/metrics/${scenario}_docker.csv"

  docker rm -f "$NAME" >/dev/null 2>&1 || true
  mkdir -p "$ROOT/data/raw" "$ROOT/data/metrics" "$ROOT/data/processed"

  if [ "$scenario" != "verify" ]; then
    echo "timestamp,cpu,mem,net_io" > "$stats"
  fi

  echo "=== $scenario (${duration}s) ==="
  echo "Trafico benigno: cuando el log diga 'Portal benigno listo', abre http://127.0.0.1:${BENIGN_PORT}/"
  echo "Eso se mezcla con los alumnos. El ataque queda dentro de Docker, contra el portal emulado."
  docker run -d --name "$NAME" --privileged \
    -e DATA_DIR=/ataque/data \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e BENIGN_PORT="$BENIGN_PORT" \
    -p "127.0.0.1:${BENIGN_PORT}:${BENIGN_PORT}" \
    -v "$ROOT/data:/ataque/data" \
    -v "$ROOT/scripts/mininet:/ataque/mininet:ro" \
    -v "$ROOT/scripts/docker:/ataque/scripts:ro" \
    "$IMAGE" \
    bash /ataque/scripts/capture_campus.sh "$scenario" "$duration" >/dev/null

  LOG_PID=""
  docker logs -f "$NAME" &
  LOG_PID=$!

  SAMPLER_PID=""
  if [ "$scenario" != "verify" ]; then
    (
      while docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null | grep -qx true; do
        ts="$(date +%s)"
        line="$(docker stats --no-stream --format '{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}' "$NAME" 2>/dev/null || true)"
        if [ -n "$line" ]; then
          echo "$ts,$line" >> "$stats"
        fi
        sleep 1
      done
    ) &
    SAMPLER_PID=$!
  fi

  local status
  status="$(docker wait "$NAME")"
  if [ -n "$SAMPLER_PID" ]; then
    wait "$SAMPLER_PID" || true
    SAMPLER_PID=""
  fi
  if [ -n "$LOG_PID" ]; then
    kill "$LOG_PID" >/dev/null 2>&1 || true
    sleep 0.2
    kill -9 "$LOG_PID" >/dev/null 2>&1 || true
    wait "$LOG_PID" 2>/dev/null || true
    LOG_PID=""
  fi
  echo "----- logs ($scenario) -----"
  docker logs "$NAME" || true
  docker rm "$NAME" >/dev/null 2>&1 || true
  if [ "$scenario" != "verify" ]; then
    share="$ROOT/data/analisis/${scenario}/compartido"
    mkdir -p "$share"
    cp "$stats" "$share/docker.csv"
    echo "Analisis: $ROOT/data/analisis/${scenario}/"
    echo "  benigno/   trafico de alumnos y de tu navegador"
    echo "  ataque/    trafico de las PCs infectadas"
    echo "  compartido/  reparto.csv, por_ip.csv, reparto.txt, sonda.csv"
  fi
  if [ "$status" != "0" ]; then
    echo "FALLO $scenario (codigo $status)" >&2
    exit "$status"
  fi
  if [ "$scenario" != "verify" ]; then
    echo "Metricas del contenedor: $stats"
  fi
}

case "$SCENARIO" in
  convert)
    run_convert
    ;;
  all)
    for s in baseline synflood httpflood slowloris icmpflood; do
      run_one "$s" "$DURATION"
    done
    ;;
  verify|baseline|synflood|httpflood|slowloris|icmpflood)
    run_one "$SCENARIO" "$DURATION"
    ;;
  *)
    usage
    ;;
esac
