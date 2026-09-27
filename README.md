# Deteccion de DDoS con SDN (Mininet + Ryu + ML)

Entorno: WSL2, distro `Ubuntu` (24.04) ya existente en esta maquina.
OVS corre en modo **userspace** (`datapath_type=netdev`) para evitar el
modulo de kernel, que es la principal fuente de problemas de OVS dentro
de WSL2. Ryu corre en un venv con Python 3.9 porque no soporta Python
3.12 (usa `distutils`, removido en esa version).

## Estructura

Separado en dos: **todo el codigo** bajo `scripts/`, **todos los
datos** bajo `data/`.

```
scripts/
  mininet/                codigo compartido por WSL y Docker, sin nada especifico de ninguno
    topo.py                   topologia: server + 2 clientes + 2 atacantes + switch OVS
    capture_normal.py         genera y captura trafico normal
    capture_attack.py         lanza un ataque y lo captura
    pcap_to_csv.py            convierte data/raw/*.pcap a data/processed/*.csv, etiquetados

  wsl/                    scripts para correr todo nativo en WSL (Ubuntu)
    01_install_packages.sh    instala mininet, ovs, hping3, slowhttptest, tcpdump...
    02_setup_ryu_venv.sh      crea ~/ataque-ryu-venv (symlink ryu/venv) e instala ryu
    03_verify.sh              smoke test: levanta ryu + topo.py + pingall
    04_capture_normal.sh      wrapper de mininet/capture_normal.py (levanta ryu antes)
    05_capture_attack.sh      wrapper de mininet/capture_attack.py (levanta ryu antes)
    06_setup_cfm_venv.sh      crea ~/ataque-cfm-venv e instala CICFlowMeter
    07_pcap_to_csv.sh         wrapper de mininet/pcap_to_csv.py

  docker/                 imagen para correr todo sin instalar nada (ver mas abajo)
    Dockerfile
    entrypoint.sh             arranca ovsdb-server/ovs-vswitchd a mano (no hay systemd en el contenedor)
    verify.sh, capture_normal.sh, capture_attack.sh, pcap_to_csv.sh
                               mismos 4 wrappers que wsl/03-07, con las rutas fijas de la imagen

  ryu/                    symlink al venv de ryu (wsl) + espacio para apps propias (Fase 6)

data/
  raw/normal/               pcaps de trafico legitimo
  raw/attacks/               pcaps de trafico malicioso (uno por tipo de ataque)
  processed/                  csv de salida de pcap_to_csv.py, uno por captura, con columna Label

notebooks/                preprocesamiento + entrenamiento (Fase 5)
```

## Problemas que aparecieron y como quedaron resueltos

- **Venv de Ryu no puede vivir en `/mnt/c/...`**: escribir miles de
  archivos chicos sobre el mount 9P de Windows es carisimo en I/O (a
  veces cuelga el proceso). El venv real vive en `~/ataque-ryu-venv`
  (filesystem nativo de Linux); `scripts/ryu/venv` es solo un symlink.
- **Ryu no instala/corre con herramientas modernas**: su `setup.py`
  usa `setuptools.command.easy_install` (removido en `setuptools`
  nuevos) y su codigo importa `eventlet.wsgi.ALREADY_HANDLED` (removido
  en `eventlet` nuevos). Quedaron fijados `setuptools==57.5.0`
  (con `pip install --no-build-isolation`) y `eventlet==0.30.2`.
- **`service apache2 start` no sirve dentro de un host de Mininet**:
  eso le pide al systemd del sistema (namespace de red raiz) que
  arranque el proceso, y queda escuchando fuera del namespace del host
  `server` -> nunca le responde a los clientes. Se reemplazo por
  `python3 -m http.server 80`, lanzado directo desde `host.cmd()` para
  que quede corriendo en el namespace correcto.
- **TCP se colgaba (ping andaba bien, curl no)**: bug conocido de
  Mininet/OVS con *checksum offload* en las interfaces virtuales; el
  kernel descarta en silencio segmentos TCP con checksum invalido
  calculado "por hardware" que en realidad no existe. Se desactiva con
  `ethtool -K <iface> tx off rx off tso off gso off gro off` para
  todos los hosts, en `topo.py`.
- **Escribir el pcap en vivo a `/mnt/c/...` tambien cuelga**: mismo
  problema de I/O que con el venv. `tcpdump` escribe primero a
  `/tmp/*.pcap` (Linux nativo) y el script copia el archivo ya
  terminado a `data/raw/` al final.
- **Los loops de trafico se colgaban**: un `# tag` puesto al final del
  comando de background se comia el `&` (en bash, todo lo que sigue a
  `#` es comentario), asi que el loop corria en primer plano para
  siempre. El tag ahora va como un `:` (no-op) al principio del loop.
- **`hping3 --flood` sin limite genera archivos enormes**: ~20 MB/s de
  pcap. Una corrida de 60s como default del plan puede pasar el GB;
  tenerlo en cuenta para el espacio en disco al capturar ataques largos.
- **Dataset desbalanceado**: la primera corrida dio 311 flujos BENIGN
  vs. 49,927 de synflood (1:160) porque `--flood` manda a la maxima
  velocidad posible y `--rand-source` crea un flujo nuevo por paquete,
  mientras que el trafico normal son requests espaciadas. Se ajusto:
  `synflood`/`icmpflood` usan `-i u10000` (100 paquetes/s, en vez de
  sin limite), `httpflood` tiene una pausa de 25ms entre requests, y el
  trafico normal bajo el rango de pausa (antes 0.2-1.5s, ahora
  0.05-0.3s) y subio su duracion default (120s -> 300s). Sigue sin ser
  1:1 (slowloris es bajo volumen *a proposito*, es su firma de ataque)
  asi que en la Fase 5 igual hay que usar `class_weight='balanced'` o
  resampling, no alcanza con capturar mas.
- **CICFlowMeter no puede procesar ICMP**: su sniffer filtra la
  captura con `ip and (tcp or udp)`, asi que un pcap de `icmpflood`
  (que es 100% ICMP) le da CERO paquetes y produce un CSV vacio sin
  avisar del error. `pcap_to_csv.py` detecta el archivo `icmpflood` y
  usa un agrupador de flujos propio (con scapy) en vez de CICFlowMeter
  para ese caso.
- **CLI de `cicflowmeter` roto**: su `main()` llama a `create_sniffer()`
  con los argumentos en el orden equivocado (sobra un parametro en la
  firma de la funcion), asi que el booleano `verbose` termina en el
  parametro `fields` y revienta con
  `AttributeError: 'bool' object has no attribute 'split'`.
  `pcap_to_csv.py` llama a `create_sniffer()` directo, con keywords,
  evitando el bug del CLI.

## Requisito previo: sudo sin password dentro de WSL

Mininet necesita privilegios de root en **cada** ejecucion (no solo para
instalar). Para poder automatizar esto hace falta sudo sin contrasena
para tu usuario dentro de la distro `Ubuntu`. Corre esto una sola vez,
en una terminal de WSL (te va a pedir tu contrasena de WSL, normal):

```bash
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/90-$USER-nopasswd
sudo chmod 0440 /etc/sudoers.d/90-$USER-nopasswd
```

Esto es exactamente lo que trae por defecto la VM oficial de Mininet;
al estar aislado dentro de WSL no expone nada fuera de esa distro.

## Orden de ejecucion (WSL nativo)

**IMPORTANTE**: los comandos `wsl -d Ubuntu -- bash scripts/wsl/...`
de abajo asumen que tu terminal de PowerShell/CMD esta parada en la
carpeta de este proyecto (`cd` hasta aca primero). WSL traduce
automaticamente el directorio actual de Windows al equivalente
`/mnt/c/...` adentro de la distro, asi que las rutas quedan relativas
y el proyecto funciona sin importar el usuario de Windows ni donde
este copiado.

```bash
wsl -d Ubuntu -- bash scripts/wsl/01_install_packages.sh
wsl -d Ubuntu -- bash scripts/wsl/02_setup_ryu_venv.sh
wsl -d Ubuntu -- bash scripts/wsl/03_verify.sh
```

Si `03_verify.sh` termina en "OK: pingall sin perdidas", el entorno
(Fase 0 y Fase 1 del plan) esta listo.

Para generar y capturar trafico real (Fase 3):

```bash
# Trafico normal (300s por defecto) -> data/raw/normal/normal.pcap
wsl -d Ubuntu -- bash scripts/wsl/04_capture_normal.sh 300

# Ataques (120s por defecto cada uno) -> data/raw/attacks/<tipo>.pcap
wsl -d Ubuntu -- bash scripts/wsl/05_capture_attack.sh synflood 120
wsl -d Ubuntu -- bash scripts/wsl/05_capture_attack.sh httpflood 120
wsl -d Ubuntu -- bash scripts/wsl/05_capture_attack.sh slowloris 120
wsl -d Ubuntu -- bash scripts/wsl/05_capture_attack.sh icmpflood 120
```

Cada corrida levanta su propia topologia desde cero y la apaga al
terminar, asi que las capturas quedan completamente separadas (regla
de oro del plan: nunca mezclar normal y ataque en el mismo pcap).

Para convertir los pcap a CSV (Fase 4, primera vez crea el venv):

```bash
wsl -d Ubuntu -- bash scripts/wsl/06_setup_cfm_venv.sh
wsl -d Ubuntu -- bash scripts/wsl/07_pcap_to_csv.sh
```

## Compartir el proyecto con companeros (Docker)

Para que otra persona lo corra "de una" sin repetir todos los fixes de
arriba (que son de Mininet/OVS/Ryu en general, no de esta maquina en
particular), hay una imagen Docker en `scripts/docker/` con todo ya
resuelto y las versiones fijadas. Funciona igual en Windows, Mac o
Linux (necesita Docker Desktop instalado y corriendo).

Desde la carpeta del proyecto:

```bash
docker build -t ataque-sdn -f scripts/docker/Dockerfile .

docker run --privileged --rm -it \
  -v "$(pwd)/data:/ataque/data" \
  ataque-sdn
```

Eso abre una terminal dentro del contenedor, con `data/` conectada a
la carpeta real del proyecto (todo lo que se genere ahi queda tambien
en la maquina de afuera). Adentro:

```bash
./scripts/verify.sh
./scripts/capture_normal.sh 300
./scripts/capture_attack.sh synflood 120
./scripts/capture_attack.sh httpflood 120
./scripts/capture_attack.sh slowloris 120
./scripts/capture_attack.sh icmpflood 120
./scripts/pcap_to_csv.sh
```

`--privileged` es necesario porque Mininet crea namespaces de red y
Open vSwitch necesita acceso a nivel de kernel para eso; no hace falta
ninguna configuracion extra (Ryu, el venv de CICFlowMeter, todos los
paquetes) porque ya viene horneado en la imagen desde el build.

## Fases (resumen)

0. Entorno: WSL2 + Ubuntu, o Docker (este repo). (`scripts/wsl/01-03`, o `scripts/docker/`)
1. Paquetes: Mininet, OVS, Ryu, hping3, slowhttptest, tcpdump. (`scripts/wsl/01`, `scripts/wsl/02`)
2. Topologia Mininet: server + clientes + atacantes + switch OVS. (`scripts/mininet/topo.py`)
3. Captura de trafico normal y de 4 tipos de ataque (synflood, httpflood,
   slowloris, icmpflood), por separado, a `data/raw/normal` y `data/raw/attacks`.
   (`scripts/wsl/04`, `scripts/wsl/05`)
4. Conversion pcap -> CSV, etiquetado por captura, a `data/processed`.
   (`scripts/wsl/06`, `scripts/wsl/07`)
5. Preprocesamiento + entrenamiento (`notebooks/`), Pipeline de sklearn, sin
   fuga de datos, con manejo de clases desbalanceadas.
6. (Opcional) Deteccion en vivo con una app Ryu propia (`scripts/ryu/`) que
   lea estadisticas OpenFlow y clasifique en tiempo real.
