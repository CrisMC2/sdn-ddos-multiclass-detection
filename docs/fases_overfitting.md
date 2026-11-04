# Del F1 0,999 a un número defendible

## El problema

El detector por ventana saca F1 macro 0,999. **No es sobreajuste clásico**: la
brecha entre entrenamiento y prueba es 0,001. El problema es que el escenario es
demasiado fácil. Un árbol de solo 3 niveles ya saca 0,995, porque con la
intensidad fija de siempre cada clase se separa con 2 o 3 umbrales (por ejemplo,
`server_rx_bps > 16 726`). El modelo aprende los números del simulador, no la
forma del ataque. Por eso regularizar no lo arregla: hacen falta datos más
difíciles y una evaluación que los use.

## Qué se hizo (rama `feature/intensidades`)

| Fase | Qué | Dónde |
|---|---|---|
| 1 | Ataques difíciles: perfiles `bajo`, `sigiloso`, `pulsos`, `rampa`, más carga de alumnos variable | `scripts/mininet/roles.py` (`PERFILES`), `capture_campus.py` |
| 2 | Features relativas `rel_*`: cada volumen contra la línea base de la propia corrida (primeros 20 s) | `notebooks/deteccion_ventanas.py` |
| 3 | Ataques nunca vistos: udpflood, ackflood, slowpost y multivector se apartan del entrenamiento y solo se usan para probar | `notebooks/deteccion_ventanas.py` |
| — | Interfaz: selector «Forma del ataque» y «Carga de alumnos variable» | `ui/` |

Bugs previos corregidos de paso:

- **Tráfico de alumnos idéntico.** En el contenedor `/bin/sh` es `dash`, donde
  `$RANDOM` no existe. Todos los alumnos pedían la misma página con la misma
  pausa, así que el BENIGN era artificialmente regular. Ahora la semilla sale de
  `/dev/urandom`.
- **Telemetría SDN vacía sin el módulo `openvswitch`** (Mac, o Windows si falla
  el `modprobe`). El monitor ahora usa `ovs-appctl` como respaldo.

El informe nuevo trae:

- **Separabilidad:** cuánto da un árbol de 3 niveles.
- **Brecha** entre entrenamiento y prueba.
- **Generalización:** (A) entrenar solo con `normal` y probar cada perfil difícil;
  (B) dejar un perfil entero fuera. En los dos casos se comparan features
  absolutas con relativas.
- **Ataques nunca vistos:** % de ventanas de ataque que dan la alarma, y con qué
  clase los confunde.
- **Retardo de detección**, medido desde el inicio real del ataque.

Verificado con las 10 corridas actuales: si la red de prueba tiene 1,6 veces más
tráfico (prueba sintética), las features absolutas caen a F1 0,463 y las
relativas se mantienen en 0,999.

## Cómo correrlo (en la PC con Windows, NO en Mac)

En Mac, Docker Desktop no tiene el módulo `openvswitch` y OVS usa el datapath de
userspace: es más lento y las columnas `sdn_*` salen en otra escala. Todo el
dataset tiene que salir de **la misma máquina** que generó `r01..r10`, o de otra
PC con Windows y WSL2.

Requisitos: Docker Desktop abierto («Engine running»), la imagen `ataque-sdn`
construida, y Python con `pip install -r notebooks/requirements.txt`. Si en
Windows `python3` no existe, usa `python` en su lugar.

Desde **Git Bash**, en la raíz del repo:

```bash
git fetch && git checkout feature/intensidades

# 1) Ataques difíciles: 5 perfiles x 5 escenarios x 2 rondas = 50 corridas (~2 h)
PERFILES="normal bajo sigiloso pulsos rampa" bash scripts/docker/run_scenario.sh dificil 2 120

# 2) Ataques nunca vistos: 4 escenarios x 2 perfiles x 2 rondas = 16 corridas (~40 min)
ESCENARIOS="udpflood ackflood slowpost multivector" PERFILES="normal bajo" \
  bash scripts/docker/run_scenario.sh dificil 2 120

# 3) Dataset por ventana, solo con esas corridas
WINDOWS_DIR=ventanas_dificil ONLY_TAGS='^(normal|bajo|sigiloso|pulsos|rampa)[0-9]' \
  python3 scripts/mininet/build_windows.py

# 4) Evaluación (~10-15 min con todas las corridas)
python3 notebooks/deteccion_ventanas.py
```

- **Si se corta o falla una corrida:** vuelve a lanzar **el mismo comando**. Se
  saltan las corridas que ya terminaron y se repiten solo las que faltan. Una
  corrida que falla no detiene la campaña: se borran sus archivos y sigue.
- No hace falta reconstruir la imagen: los scripts se montan desde el repo.
- No abras `http://127.0.0.1:8080` durante la campaña: ese tráfico entra como
  benigno real y ensucia las corridas.

### Qué devolver

```bash
git add data/processed/ventanas_dificil notebooks/resultados/ventanas
git commit -m "Campana de ataques dificiles y resultados"
git push
```

Con eso se escribe la última fase: la sección de resultados del paper con los
números de `informe.txt`, `generalizacion.csv` y `ataques_nuevos.csv`.

## Cómo leer el resultado

- **Generalización B, perfil difícil fuera:** ese F1 es el número honesto para la
  tesis. Lo esperable es que baje bastante de 0,999, sobre todo en `sigiloso`.
- **Relativas mejor que absolutas en A/B:** confirma que el modelo con absolutas
  dependía de la escala del simulador. Las relativas son la propuesta.
- **Ataques nunca vistos:** si el % de detección es alto aunque los confunda con
  otra clase, el detector sirve como alarma de anomalía aunque no conozca el ataque.
