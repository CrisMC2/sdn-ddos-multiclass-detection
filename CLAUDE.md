# CLAUDE.md

Guía para trabajar en este repositorio. Investigación académica de la UNCP
(Huancayo): un laboratorio reproducible que genera y detecta ataques DDoS
multi-clase contra el portal de un campus emulado con Mininet + Ryu, dentro
de Docker. Pensado para correr en macOS/Linux/Windows con Docker Desktop.

## Qué es (y qué no)

- Es un **banco de pruebas defensivo**: genera tráfico (alumnos navegando +
  PCs comprometidas atacando el mismo portal) para producir un **dataset
  etiquetado** y entrenar/evaluar **detectores** de DDoS.
- El ataque **nunca sale del contenedor**. No se ataca ninguna red real.
- La universidad autorizó el escaneo de sus redes; el resultado es para
  entregar a la institución y una tesis de pregrado.

## Arquitectura y flujo de datos

```
run_scenario.sh  (orquesta Docker, muestrea docker stats)
   └─ capture_campus.sh  (dentro del contenedor: levanta Ryu + corre el escenario)
        └─ flow_monitor_13.py   Ryu: reenvía + recolecta estadísticas OpenFlow
        └─ capture_campus.py    arma la topología, genera tráfico, mide, captura pcap
             ├─ topo.py / roles.py   topología y "quién es quién"
             └─ benign_mix.py        mezcla el navegador del operador como cliente benigno
   └─ pcap_to_csv.py   pcap -> CSV de flujos (CICFlowMeter + agregador ICMP),
                       etiqueta por IP de origen y cruza la telemetría SDN
build_windows.py       arma el dataset POR VENTANA de tiempo (detección temprana)
deteccion_ventanas.py  evalúa el detector por ventana (CV por corrida, ablación)
analisis_completo.py   modelo por FLUJO (RandomForest, holdout de laboratorio)
```

Dos datasets, dos tareas distintas:

1. **Por flujo** (`data/processed/<run>.csv`): una fila por conexión, features
   de CICFlowMeter + columnas `sdn_*` por IP. Clasificación de flujos ya
   terminados. Lo usa `analisis_completo.py`.
2. **Por ventana** (`data/processed/ventanas/`): una fila por segundo, con
   contadores del portal + telemetría SDN agregada (entropía de IPs origen,
   crecimiento de la tabla de flujos, etc.). Detección *mientras pasa*. Lo
   arma `build_windows.py` y lo usa `deteccion_ventanas.py`.

## Topología (resumen)

Modem de borde, switch core SDN, DMZ con el portal (`10.0.0.10`), y un
laboratorio por área académica (5). Cada laboratorio: 4 alumnos + 2 PCs
comprometidas. Atacante C2 fuera del campus (`192.168.9.10`). Todo en
`10.0.0.0/8` salvo el C2. Switches = Open vSwitch en **userspace**
(no hay módulo de kernel en Docker/WSL). Detalle completo en `README.md`.

## Comandos

Desde la raíz, con Docker Desktop abierto:

```bash
bash scripts/docker/run_scenario.sh verify            # comprueba caminos de red
bash scripts/docker/run_scenario.sh baseline 20       # un escenario, 20 s de medición
bash scripts/docker/run_scenario.sh all 120           # baseline + 4 ataques, 120 s c/u
bash scripts/docker/run_scenario.sh repeat 5 120      # 5 corridas con semillas/intensidades distintas
bash scripts/docker/run_scenario.sh convert           # pcaps -> CSV de flujos (incluye SDN)

python3 scripts/mininet/build_windows.py              # arma el dataset por ventana
python3 notebooks/deteccion_ventanas.py               # evalúa el detector por ventana
python3 notebooks/analisis_completo.py                # modelo por flujo + numeros.tex del paper
```

- Escenarios: `baseline`, `synflood`, `httpflood`, `slowloris`, `icmpflood`.
- `repeat N [seg]` corre N veces los 5 escenarios; cada corrida lleva sufijo
  `__rNN` en sus archivos para no pisarse, y sortea las intensidades (semilla
  registrada en el `meta.json`). Es lo que da **media ± desviación**.
- El segundo número es los segundos de medición (default 120); hay ~1 min de
  arranque de red por escenario. `repeat 5 120` ≈ 1.5–2 h.

## Reconstruir la imagen

Solo si cambias el `Dockerfile`. El código de `scripts/mininet` y
`scripts/docker` se **monta** al correr, así que los cambios ahí valen sin
reconstruir:

```bash
docker build -t ataque-sdn -f scripts/docker/Dockerfile .
```

## Convenciones y cosas que es fácil romper

- **Etiqueta por IP, no por archivo**: en `pcap_to_csv.py`, un flujo es
  `BENIGN` salvo que su IP de origen sea una PC comprometida y el escenario
  no sea `baseline`. En baseline todo es `BENIGN` (las comprometidas aún
  navegan). No etiquetar por nombre de archivo.
- **El modelo no usa IP, puertos ni timestamp**: se descartan antes de
  entrenar para que aprenda comportamiento, no identidad de la máquina.
- **Partición honesta**: nunca split aleatorio (las ventanas/flujos vecinos
  están correlacionados). Por flujo: holdout de laboratorio. Por ventana:
  leave-one-run-out si hay ≥2 corridas, si no partición temporal 70/30.
- **Open vSwitch userspace es frágil**: no subir las intensidades a niveles
  de un ataque real de gigabits; el emulador se cae antes. Los rangos de
  `repeat` están elegidos para ser estables.
- **Floods robustos**: SYN e ICMP corren en un bucle con `timeout` que
  relanza el generador cada 5 s (`/tmp/synfloodloop.sh`,
  `/tmp/icmpfloodloop.sh`). SYN usa `hping3`; **ICMP usa `ping` del kernel**,
  no `hping3`: hping3 `--icmp` en OVS userspace manda la ráfaga inicial y su
  socket raw se congela a los ~9 s (el contador del flujo ICMP se plantaba);
  `ping` sostiene el ritmo toda la corrida.
- **Ryu corre en Python 3.9** (venv `/opt/ryu-venv`), separado del Python
  3.12 del resto. `flow_monitor_13.py` solo importa `ryu`/stdlib.
- **No inventar resultados**: los números del paper (`\Fmacro`, tablas) salen
  de `analisis_completo.py` sobre datos reales. Si no hay datos de una
  corrida, no se reportan números: se deja la metodología y se marca pendiente.

## Salidas de una corrida

```
data/raw/<run>.pcap, <run>.meta.json
data/metrics/<run>_interno.csv      sonda del alumno + contadores del portal (por segundo)
data/metrics/<run>_sdn.csv          telemetría OpenFlow del controlador (cada ~1 s, SDN_POLL_INTERVAL)
data/metrics/<run>_docker.csv       CPU/mem/red del contenedor
data/metrics/resumen.csv            una fila por corrida (impacto en el portal)
data/processed/<run>.csv            flujos etiquetados + columnas sdn_*
data/processed/ventanas/            dataset por ventana (lo arma build_windows.py)
data/analisis/<escenario>/          pcap partido benigno/ataque/compartido (cualitativo)
notebooks/resultados/               informes y figuras de los modelos
```
Donde `<run>` es el escenario (`synflood`) o el escenario con sufijo de
corrida (`synflood__r03`).
