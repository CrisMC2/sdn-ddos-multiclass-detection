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

# En Git Bash/MSYS2 (Windows) los argumentos que parecen rutas Unix
# (p.ej. /ataque/scripts/capture_campus.sh o -e DATA_DIR=/ataque/data) se
# convierten a rutas Windows antes de llegar a docker, y el contenedor no
# encuentra sus scripts ("bash: C:/Program Files/Git/ataque/...: No such
# file or directory"). Esto desactiva esa conversion. Es inocuo en
# macOS/Linux/WSL (ignoran estas variables de MSYS).
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE:-ataque-sdn}"
NAME="ataque-sdn-run"
BENIGN_PORT="${BENIGN_PORT:-8080}"

usage() {
  echo "Uso: bash scripts/docker/run_scenario.sh <verify|baseline|synflood|httpflood|slowloris|icmpflood|all|repeat|convert> [segundos]" >&2
  echo "     repeat <N> [segundos]: N corridas con semilla e intensidades distintas (para media +/- desviacion)" >&2
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

ensure_ovs_kernel_module() {
  # El datapath de kernel de OVS ('system') necesita el modulo 'openvswitch'
  # cargado en el kernel. El contenedor privilegiado comparte el kernel del
  # host, pero no puede hacer modprobe (no tiene /lib/modules). Sin el modulo,
  # topo.py cae a userspace (netdev) y el flood ICMP se congela a los ~8 s.
  #
  # En Windows+Docker Desktop el host es el kernel de WSL2, que YA trae
  # openvswitch.ko (kernels 6.x microsoft-standard-WSL2). Lo cargamos via WSL
  # como root (sin sudo/contrasena); queda visible para los contenedores.
  # En macOS/Linux no hay wsl.exe: no se hace nada y se mantiene el
  # comportamiento previo (si el modulo no esta, OVS usa userspace).
  if command -v wsl.exe >/dev/null 2>&1; then
    local distro="${WSL_OVS_DISTRO:-Ubuntu}"
    if wsl.exe -d "$distro" -u root -- modprobe openvswitch >/dev/null 2>&1; then
      echo "OVS: modulo 'openvswitch' cargado en el kernel de WSL2 (datapath de kernel disponible)."
    else
      echo "OVS: no se pudo cargar 'openvswitch' en WSL2 ($distro); OVS usara userspace (el ICMP puede congelarse)." >&2
    fi
  fi
}
ensure_ovs_kernel_module

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
  local run_name="$scenario"
  [ -n "${RUN_TAG:-}" ] && run_name="${scenario}__${RUN_TAG}"
  local stats="$ROOT/data/metrics/${run_name}_docker.csv"

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
    -e RUN_TAG -e RUN_SEED \
    -e SYN_PPS -e ICMP_PPS -e HTTP_FLOOD_WORKERS -e HTTP_FLOOD_PAUSE \
    -e SLOWLORIS_CONNS -e BROWSE_PAUSE_MIN -e BROWSE_PAUSE_MAX \
    -e SDN_POLL_INTERVAL \
    -e OVS_DATAPATH \
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
  repeat)
    # repeat <N> [segundos]: N corridas de los 5 escenarios. Cada corrida
    # usa una semilla propia e intensidades sorteadas (deterministas por la
    # semilla), y sus archivos llevan sufijo __rNN para no pisarse. Asi el
    # dataset final tiene varias muestras por escenario y se puede reportar
    # media +/- desviacion en vez de un numero de una sola corrida.
    runs="${2:-5}"
    dur="${3:-120}"
    seed_base="${RUN_SEED:-1}"
    for i in $(seq 1 "$runs"); do
      tag="$(printf 'r%02d' "$i")"
      seed=$((seed_base + i))
      export RUN_TAG="$tag"
      export RUN_SEED="$seed"
      export SYN_PPS="$(awk -v s="$seed"       'BEGIN{srand(s); print 10+int(rand()*31)}')"
      export ICMP_PPS="$(awk -v s="$((seed+1))" 'BEGIN{srand(s); print 10+int(rand()*31)}')"
      export HTTP_FLOOD_WORKERS="$(awk -v s="$((seed+2))" 'BEGIN{srand(s); print 3+int(rand()*4)}')"
      export SLOWLORIS_CONNS="$(awk -v s="$((seed+3))"    'BEGIN{srand(s); print 15+int(rand()*16)}')"
      echo "########## corrida $tag (seed=$seed): SYN_PPS=$SYN_PPS ICMP_PPS=$ICMP_PPS HTTP_FLOOD_WORKERS=$HTTP_FLOOD_WORKERS SLOWLORIS_CONNS=$SLOWLORIS_CONNS ##########"
      for s in baseline synflood httpflood slowloris icmpflood; do
        run_one "$s" "$dur"
      done
    done
    echo "Listo: $runs corridas. Ahora pasa los pcap a CSV:"
    echo "  bash scripts/docker/run_scenario.sh convert"
    ;;
  verify|baseline|synflood|httpflood|slowloris|icmpflood)
    run_one "$SCENARIO" "$DURATION"
    ;;
  *)
    usage
    ;;
esac
