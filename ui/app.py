#!/usr/bin/env python3
"""Interfaz web de Campus-DDoS-SDN: arranca y mira una corrida sin pasar por
la terminal. Llama a Docker directo desde Python (nada de bash en el medio),
asi que no le pasa lo de Git Bash reescribiendo rutas que nos trabo varias
veces al correr esto a mano en Windows.

Uso:
    python ui/app.py
    abre http://127.0.0.1:8765

Fase 1: entorno, lanzar una corrida, verla en vivo, pararla. No toca el
analisis (notebooks/) ni reconstruye la imagen Docker.
"""
import csv
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
MININET_DIR = ROOT / 'scripts' / 'mininet'
DOCKER_DIR = ROOT / 'scripts' / 'docker'
DATA_DIR = ROOT / 'data'
SCENARIOS_FILE = MININET_DIR / 'scenarios.txt'

IMAGE = os.environ.get('IMAGE', 'ataque-sdn')
CONTAINER_NAME = 'ataque-sdn-run'
BENIGN_PORT = int(os.environ.get('BENIGN_PORT', '8080'))
UI_PORT = int(os.environ.get('UI_PORT') or os.environ.get('PORT') or '8765')

app = Flask(__name__, static_folder='static', template_folder='templates')

# --------------------------------------------------------------------------
# Catalogo de escenarios: lo que la interfaz muestra de cada uno. La lista
# valida de nombres sigue siendo scenarios.txt; esto es solo como se
# presentan. Un escenario que no este aqui se muestra con valores genericos,
# asi que agregar uno a scenarios.txt no rompe la UI.
#
# 'intensidad' es el unico parametro que se ofrece para ese ataque (los
# rangos son los que se probaron estables en Open vSwitch: el CLAUDE.md
# avisa que subirlos a niveles de un ataque real tumba el emulador).
# Las frases de 'firma' salen de corridas reales de este banco, no de teoria.
# --------------------------------------------------------------------------
GRUPOS = ('Referencia', 'Volumen', 'Aplicación', 'Cupos de conexión')

CATALOGO = {
    'baseline': {
        'grupo': 'Referencia', 'icono': 'baseline', 'nombre': 'Sin ataque',
        'descripcion': 'Alumnos e infectadas navegan el portal igual. Es el punto de comparación: todo queda BENIGN.',
        'agota': 'Nada: el portal trabaja en condiciones normales.',
        'firma': 'Paquetes por segundo y latencia estables durante toda la corrida.',
        'herramienta': 'curl',
        'intensidad': None,
    },
    'synflood': {
        'grupo': 'Volumen', 'icono': 'syn', 'nombre': 'SYN flood',
        'descripcion': 'Cada infectada manda paquetes SYN que piden abrir conexiones TCP y nunca las completan.',
        'agota': 'La tabla de conexiones a medio abrir y el ancho de banda del portal.',
        'firma': 'La tasa de paquetes al portal es la más alta de todos los ataques; los flujos son de uno o dos paquetes con bandera SYN.',
        'herramienta': 'hping3 -S -p 80',
        'intensidad': {'env': 'SYN_PPS', 'etiqueta': 'Paquetes SYN por segundo, por PC', 'defecto': 20, 'min': 5, 'max': 60},
    },
    'httpflood': {
        'grupo': 'Aplicación', 'icono': 'http', 'nombre': 'HTTP flood',
        'descripcion': 'Las infectadas piden páginas completas sin pausa, con varios procesos a la vez.',
        'agota': 'La capacidad de la aplicación para atender peticiones.',
        'firma': 'La latencia del portal sube. Son peticiones completas, no paquetes sueltos, por eso la tasa de paquetes no es la más alta.',
        'herramienta': 'curl en bucle',
        'intensidad': {'env': 'HTTP_FLOOD_WORKERS', 'etiqueta': 'Procesos simultáneos, por PC', 'defecto': 4, 'min': 1, 'max': 8},
    },
    'slowloris': {
        'grupo': 'Cupos de conexión', 'icono': 'slow', 'nombre': 'Slowloris',
        'descripcion': 'Abre muchas conexiones y envía las cabeceras HTTP a goteo para que el servidor no las cierre.',
        'agota': 'Los cupos de conexión del portal (30).',
        'firma': 'Pocos paquetes por segundo, pero el portal deja de responder: casi todas las sondas del alumno fallan.',
        'herramienta': 'slowhttptest -H',
        'intensidad': {'env': 'SLOWLORIS_CONNS', 'etiqueta': 'Conexiones abiertas, por PC', 'defecto': 20, 'min': 5, 'max': 40},
    },
    'icmpflood': {
        'grupo': 'Volumen', 'icono': 'icmp', 'nombre': 'ICMP flood',
        'descripcion': 'Inundación de ping hacia el portal.',
        'agota': 'El ancho de banda.',
        'firma': 'Tráfico ICMP: en la telemetría SDN, la fracción de paquetes ICMP pasa de cero a más de la mitad.',
        'herramienta': 'ping (kernel)',
        'intensidad': {'env': 'ICMP_PPS', 'etiqueta': 'Pings por segundo, por PC', 'defecto': 20, 'min': 5, 'max': 60},
    },
    'udpflood': {
        'grupo': 'Volumen', 'icono': 'udp', 'nombre': 'UDP flood',
        'descripcion': 'Datagramas UDP sin saludo previo; el portal responde «puerto inalcanzable» a cada uno.',
        'agota': 'CPU y ancho de banda.',
        'firma': 'Tráfico UDP: en la telemetría SDN, la fracción de paquetes UDP pasa de cero a más de la mitad.',
        'herramienta': 'hping3 --udp -p 80',
        'intensidad': {'env': 'UDP_PPS', 'etiqueta': 'Datagramas por segundo, por PC', 'defecto': 20, 'min': 5, 'max': 60},
    },
    'ackflood': {
        'grupo': 'Volumen', 'icono': 'ack', 'nombre': 'ACK flood',
        'descripcion': 'Paquetes TCP con bandera ACK sin una conexión real detrás; el portal responde RST.',
        'agota': 'La tabla de estado de conexiones y el ancho de banda.',
        'firma': 'Por ventana se parece a un SYN flood: la bandera ACK solo se distingue en los flujos, no en la telemetría SDN.',
        'herramienta': 'hping3 -A -p 80',
        'intensidad': {'env': 'ACK_PPS', 'etiqueta': 'Paquetes ACK por segundo, por PC', 'defecto': 20, 'min': 5, 'max': 60},
    },
    'slowpost': {
        'grupo': 'Cupos de conexión', 'icono': 'post', 'nombre': 'Slow POST (RUDY)',
        'descripcion': 'Envía un POST a /login que anuncia un cuerpo enorme y lo entrega byte a byte.',
        'agota': 'Los cupos de conexión del portal.',
        'firma': 'Las conexiones abiertas se disparan por encima del cupo y el portal empieza a responder 503.',
        'herramienta': 'slowhttptest -B',
        'intensidad': {'env': 'SLOWPOST_CONNS', 'etiqueta': 'Conexiones abiertas, por PC', 'defecto': 20, 'min': 5, 'max': 40},
    },
}


def load_scenarios():
    if not SCENARIOS_FILE.is_file():
        return []
    out = []
    for line in SCENARIOS_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(line)
    return out


def scenario_info(name):
    base = CATALOGO.get(name, {
        'grupo': 'Otros', 'icono': 'generic', 'nombre': name, 'descripcion': '',
        'agota': '', 'firma': '', 'herramienta': '', 'intensidad': None,
    })
    return dict(base, id=name)


# --------------------------------------------------------------------------
# Chequeos de entorno.
# --------------------------------------------------------------------------

def _run(args, timeout=10):
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, '', str(exc)


def check_docker():
    code, _out, _err = _run(['docker', 'info'], timeout=8)
    return code == 0


def check_image():
    code, out, _err = _run(['docker', 'images', '-q', IMAGE], timeout=8)
    return code == 0 and out.strip() != ''


def check_port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def check_disk_free_gb():
    try:
        return round(shutil.disk_usage(str(ROOT)).free / (1024 ** 3), 1)
    except OSError:
        return None


def check_container_running():
    code, out, _err = _run(
        ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME], timeout=8
    )
    return code == 0 and out.strip() == 'true'


@app.route('/api/env')
def api_env():
    docker_ok = check_docker()
    return jsonify({
        'docker': docker_ok,
        'imagen': check_image() if docker_ok else None,
        'imagen_nombre': IMAGE,
        'puerto_libre': check_port_free(BENIGN_PORT),
        'puerto': BENIGN_PORT,
        'disco_libre_gb': check_disk_free_gb(),
        'contenedor_activo': check_container_running() if docker_ok else False,
        'grupos': list(GRUPOS),
        'scenarios': [scenario_info(s) for s in load_scenarios()],
    })


@app.route('/api/limpiar_contenedor', methods=['POST'])
def api_limpiar_contenedor():
    if JOB.activo:
        return jsonify({'ok': False, 'error': 'Hay una corrida en curso: detenla primero.'}), 409
    _run(['docker', 'rm', '-f', CONTAINER_NAME], timeout=15)
    return jsonify({'ok': True})


# --------------------------------------------------------------------------
# El trabajo activo: una corrida a la vez (el contenedor siempre se llama
# igual, asi que dos corridas a la vez se pisarian).
# --------------------------------------------------------------------------

class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.activo = False
        self.scenario = None
        self.run_name = None
        self.duration = 0
        self.onset_s = None
        # inactivo|arrancando|navegando|atacando|verificando|cerrando|listo|error|detenido
        self.fase = 'inactivo'
        self.started_at = None
        self.exit_code = None
        self.logs = deque(maxlen=600)
        self.error = None

    def log(self, line):
        self.logs.append(line.rstrip('\n'))


JOB = Job()

# Frases de los logs de capture_campus.py/topo.py que delatan la fase.
# Son los info() que ya imprime el pipeline, no texto nuevo que haya que
# mantener aparte.
_FASE_MARCAS = (
    ('Alumnos navegando el portal', 'navegando'),
    ('C2 (c2) ordena el ataque', 'atacando'),
    ('Sonda del alumno:', 'cerrando'),
)


def _tagged(scenario, run_tag):
    return '%s__%s' % (scenario, run_tag) if run_tag else scenario


def _stream_logs(proc_name):
    """Engancha 'docker logs -f' del contenedor y va llenando JOB.logs,
    actualizando la fase segun lo que va diciendo (ver _FASE_MARCAS)."""
    proc = subprocess.Popen(
        ['docker', 'logs', '-f', proc_name],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, errors='replace',
    )
    for line in proc.stdout:
        JOB.log(line)
        if JOB.scenario == 'verify':
            continue
        for marca, fase in _FASE_MARCAS:
            if marca in line:
                if JOB.fase not in ('cerrando', 'listo', 'error', 'detenido'):
                    JOB.fase = fase
                break
    proc.wait()


def _sample_docker_stats(run_name):
    """CPU, memoria y red del contenedor, una fila por segundo, en el mismo
    formato que escribia run_scenario.sh (<run>_docker.csv). Alimenta la
    seccion de consumo del banco del paper."""
    path = DATA_DIR / 'metrics' / ('%s_docker.csv' % run_name)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('timestamp,cpu,mem,net_io\n')
        while check_container_running():
            code, out, _err = _run(
                ['docker', 'stats', '--no-stream', '--format',
                 '{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}', CONTAINER_NAME], timeout=8)
            line = out.strip()
            if code == 0 and line:
                fh.write('%d,%s\n' % (int(time.time()), line))
                fh.flush()
            time.sleep(1)


def _run_scenario_thread(scenario, duration, params):
    run_name = _tagged(scenario, params.get('RUN_TAG') or '')
    JOB.scenario = scenario
    JOB.run_name = run_name
    JOB.duration = duration
    onset = params.get('ONSET_S')
    JOB.onset_s = int(onset) if onset not in (None, '') else None
    JOB.fase = 'verificando' if scenario == 'verify' else 'arrancando'
    JOB.started_at = time.time()

    (DATA_DIR / 'raw').mkdir(parents=True, exist_ok=True)
    (DATA_DIR / 'metrics').mkdir(parents=True, exist_ok=True)
    (DATA_DIR / 'processed').mkdir(parents=True, exist_ok=True)

    _run(['docker', 'rm', '-f', CONTAINER_NAME], timeout=15)

    # Variables fijas de esta corrida + las que vinieron del formulario
    # (params ya trae solo las que el usuario puso, ver api_lanzar).
    env_vars = {
        'DATA_DIR': '/ataque/data',
        'PYTHONDONTWRITEBYTECODE': '1',
        'BENIGN_PORT': str(BENIGN_PORT),
    }
    for key, val in params.items():
        if val not in (None, ''):
            env_vars[key] = str(val)

    cmd = ['docker', 'run', '-d', '--name', CONTAINER_NAME, '--privileged']
    for key, val in env_vars.items():
        cmd += ['-e', '%s=%s' % (key, val)]
    cmd += [
        '-p', '127.0.0.1:%d:%d' % (BENIGN_PORT, BENIGN_PORT),
        '-v', '%s:/ataque/data' % (ROOT / 'data'),
        '-v', '%s:/ataque/mininet:ro' % MININET_DIR,
        '-v', '%s:/ataque/scripts:ro' % DOCKER_DIR,
        IMAGE,
        'bash', '/ataque/scripts/capture_campus.sh', scenario, str(duration),
    ]

    JOB.log('$ docker run -d --name %s ... %s %s' % (CONTAINER_NAME, scenario, duration))
    code, _out, err = _run(cmd, timeout=30)
    if code != 0:
        JOB.fase = 'error'
        JOB.error = 'No se pudo arrancar el contenedor: %s' % err.strip()
        JOB.log(JOB.error)
        JOB.activo = False
        return

    sampler = None
    if scenario != 'verify':
        sampler = threading.Thread(target=_sample_docker_stats, args=(run_name,), daemon=True)
        sampler.start()

    try:
        _stream_logs(CONTAINER_NAME)
    except Exception as exc:  # no tumbar el hilo por un problema leyendo logs
        JOB.log('(logs cortados: %s)' % exc)
    if sampler:
        sampler.join(timeout=5)

    code, out, _err = _run(['docker', 'inspect', '-f', '{{.State.ExitCode}}', CONTAINER_NAME], timeout=10)
    exit_code = out.strip() if code == 0 else '?'
    if scenario == 'verify':
        # Ryu escribe su telemetria tambien al verificar; la prueba de caminos
        # promete no guardar datos, asi que no se deja nada.
        try:
            (DATA_DIR / 'metrics' / ('%s_sdn.csv' % run_name)).unlink()
        except OSError:
            pass
    JOB.exit_code = exit_code
    if JOB.fase != 'detenido':
        if exit_code == '0':
            JOB.fase = 'listo'
        else:
            JOB.fase = 'error'
            if exit_code in ('137', '143'):
                # 137 = SIGKILL, 143 = SIGTERM: lo mataron desde fuera (si el
                # usuario hubiera pulsado Detener, la fase seria 'detenido').
                JOB.error = ('El contenedor se detuvo desde fuera de esta corrida (código %s). '
                             'Suele pasar si otra copia de la interfaz, o un comando docker, '
                             'lo eliminó; o si Docker se quedó sin memoria.' % exit_code)
            else:
                JOB.error = 'El contenedor terminó con código %s. Revisa el registro.' % exit_code
    JOB.activo = False


def _int_field(body, key, lo, hi, default=None):
    """Entero acotado a [lo, hi]. Vacio -> default. Invalido -> ValueError."""
    raw = body.get(key)
    if raw in (None, ''):
        return default
    try:
        val = int(float(raw))
    except (TypeError, ValueError):
        raise ValueError('«%s» no es un número válido.' % key)
    return max(lo, min(hi, val))


@app.route('/api/lanzar', methods=['POST'])
def api_lanzar():
    body = request.get_json(force=True, silent=True) or {}
    scenario = body.get('scenario')
    if scenario not in load_scenarios() + ['verify']:
        return jsonify({'ok': False, 'error': 'Escenario inválido: %r' % scenario}), 400

    try:
        duration = _int_field(body, 'duration', 5, 1800, 20)
        onset = _int_field(body, 'onset_s', 0, 1800, None)
        students = _int_field(body, 'students_per_area', 1, 9, None)
        bots = _int_field(body, 'bots_per_area', 1, 9, None)
        seed = _int_field(body, 'seed', 0, 10 ** 9, None)
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    # roles.onset_for ignora el inicio pedido si quedan menos de 10 s de
    # ataque y lo cambia por duration//4 sin avisar. Mejor rechazarlo aqui
    # que dejar que la corrida no haga lo que se pidio.
    if scenario not in ('baseline', 'verify') and onset and duration < onset + 10:
        return jsonify({
            'ok': False,
            'error': 'Con %d s de duración el ataque no puede arrancar en el segundo %d: '
                     'tienen que quedar al menos 10 s de ataque.' % (duration, onset),
        }), 400

    run_tag = (body.get('run_tag') or '').strip()
    if run_tag and not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', run_tag):
        return jsonify({
            'ok': False,
            'error': 'La etiqueta solo admite letras, números, guion y guion bajo (máximo 24).',
        }), 400
    if not run_tag:
        run_tag = 'ui%s' % time.strftime('%H%M%S')  # no pisa las corridas r01..rNN

    params = {'RUN_TAG': run_tag}
    if onset is not None:
        params['ONSET_S'] = onset
    if students is not None:
        params['STUDENTS_PER_AREA'] = students
    if bots is not None:
        params['BOTS_PER_AREA'] = bots
    if seed is not None:
        params['RUN_SEED'] = seed

    inten = scenario_info(scenario).get('intensidad')
    if inten:
        try:
            val = _int_field(body, inten['env'], inten['min'], inten['max'], None)
        except ValueError as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400
        if val is not None:
            params[inten['env']] = val

    if not JOB.lock.acquire(blocking=False):
        return jsonify({'ok': False, 'error': 'Ya hay una corrida en curso.'}), 409
    try:
        if JOB.activo:
            return jsonify({'ok': False, 'error': 'Ya hay una corrida en curso.'}), 409
        if not check_docker():
            return jsonify({'ok': False, 'error': 'Docker no responde. Abre Docker Desktop y espera a que diga «Engine running».'}), 503
        if not check_image():
            return jsonify({'ok': False, 'error': 'No existe la imagen %s. Constrúyela con scripts/docker/Dockerfile.' % IMAGE}), 503
        # El contenedor se llama siempre igual y arrancar uno nuevo elimina el
        # anterior. Si esta en marcha y no es de esta interfaz (otra copia en
        # otra terminal, un docker run a mano), lanzar interrumpiria esa
        # corrida: mejor negarse y explicarlo.
        if check_container_running():
            return jsonify({
                'ok': False,
                'error': 'Ya hay un contenedor «%s» en marcha que no pertenece a esta interfaz: '
                         'otra copia abierta en otra terminal o un comando docker. '
                         'Espera a que termine, o elimínalo desde Entorno si sabes que sobra.' % CONTAINER_NAME,
            }), 409

        JOB.reset()
        JOB.activo = True
        thread = threading.Thread(
            target=_run_scenario_thread, args=(scenario, duration, params), daemon=True,
        )
        thread.start()
        return jsonify({'ok': True, 'run_name': _tagged(scenario, run_tag)})
    finally:
        JOB.lock.release()


@app.route('/api/parar', methods=['POST'])
def api_parar():
    if not JOB.activo:
        return jsonify({'ok': True, 'error': None})
    JOB.fase = 'detenido'
    code, _out, err = _run(['docker', 'rm', '-f', CONTAINER_NAME], timeout=15)
    JOB.activo = False
    JOB.log('--- detenido por el usuario ---')
    return jsonify({'ok': code == 0, 'error': None if code == 0 else err})


# --------------------------------------------------------------------------
# Estado y metricas en vivo.
# --------------------------------------------------------------------------

def _read_meta(run_name):
    path = DATA_DIR / 'raw' / ('%s.meta.json' % run_name)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _tail_csv(path, n=120):
    if not path.is_file():
        return []
    try:
        with open(path, newline='', encoding='utf-8', errors='replace') as fh:
            rows = list(csv.DictReader(fh))
        return rows[-n:]
    except (OSError, csv.Error):
        return []


def _archivos(run_name):
    """Lo que dejo la corrida en disco, para mostrarlo al terminar."""
    candidatos = (
        DATA_DIR / 'raw' / ('%s.pcap' % run_name),
        DATA_DIR / 'raw' / ('%s.meta.json' % run_name),
        DATA_DIR / 'metrics' / ('%s_interno.csv' % run_name),
        DATA_DIR / 'metrics' / ('%s_sdn.csv' % run_name),
        DATA_DIR / 'metrics' / ('%s_docker.csv' % run_name),
    )
    out = []
    for path in candidatos:
        if path.is_file():
            out.append({
                'nombre': path.name,
                'carpeta': 'data/%s' % path.parent.name,
                'bytes': path.stat().st_size,
            })
    return out


@app.route('/api/status')
def api_status():
    meta = _read_meta(JOB.run_name) if JOB.run_name else {}
    elapsed = round(time.time() - JOB.started_at, 1) if JOB.started_at else None
    return jsonify({
        'activo': JOB.activo,
        'scenario': JOB.scenario,
        'scenario_info': scenario_info(JOB.scenario) if JOB.scenario and JOB.scenario != 'verify' else None,
        'run_name': JOB.run_name,
        'fase': JOB.fase,
        'duration': JOB.duration,
        'onset_s': JOB.onset_s,
        'elapsed': elapsed,
        'exit_code': JOB.exit_code,
        'error': JOB.error,
        'logs': list(JOB.logs)[-200:],
        'archivos': _archivos(JOB.run_name) if JOB.run_name and JOB.scenario != 'verify' else [],
        'meta': {
            'bots': meta.get('bots', []),
            'students': meta.get('students', []),
            'victim': meta.get('victim'),
            'benign_client': meta.get('benign_client'),
            'attack_start_elapsed': meta.get('attack_start_elapsed'),
            'onset_planned_s': meta.get('onset_planned_s'),
            'datapath': meta.get('datapath'),
        },
    })


@app.route('/api/metrics')
def api_metrics():
    if not JOB.run_name or JOB.scenario == 'verify':
        return jsonify({'rows': []})
    try:
        n = max(1, min(int(request.args.get('n', 400)), 2000))
    except ValueError:
        n = 400
    path = DATA_DIR / 'metrics' / ('%s_interno.csv' % JOB.run_name)
    return jsonify({'rows': _tail_csv(path, n=n)})


@app.route('/')
def index():
    resp = send_from_directory(app.template_folder, 'index.html')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.after_request
def no_cache_static(resp):
    # Servidor local de desarrollo: que un cambio de JS/CSS se vea al
    # recargar, sin pelear con la cache del navegador.
    if request.path.startswith('/static/'):
        resp.headers['Cache-Control'] = 'no-store'
    return resp


def _port_in_use(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()


if __name__ == '__main__':
    # En Windows dos servidores pueden compartir un puerto sin error, y el
    # navegador acaba hablando con la copia vieja sin que nadie se entere.
    if _port_in_use(UI_PORT):
        print('*** El puerto %d ya esta en uso: probablemente hay otra copia de la '
              'interfaz abierta en otra terminal.' % UI_PORT)
        print('    Cierrala (Ctrl+C en esa terminal) o usa otro puerto: '
              'set UI_PORT=8800 && python ui/app.py')
        raise SystemExit(1)
    print('*** Interfaz en http://127.0.0.1:%d' % UI_PORT)
    app.run(host='127.0.0.1', port=UI_PORT, debug=False, threaded=True)
