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
UI_PORT = int(os.environ.get('UI_PORT', '8765'))

app = Flask(__name__, static_folder='static', template_folder='templates')

# --------------------------------------------------------------------------
# Catalogo de escenarios: metadatos para la UI (icono, texto, herramienta).
# La lista valida de nombres sigue siendo scenarios.txt; esto es solo como
# se presentan. Un escenario que no este aqui se muestra con valores
# genericos, asi que agregar uno a scenarios.txt no rompe la UI.
# --------------------------------------------------------------------------
CATALOGO = {
    'baseline': {
        'icono': '🙂', 'nombre': 'Baseline', 'tipo': 'Sin ataque',
        'descripcion': 'Alumnos e infectadas navegan igual. Todo queda BENIGN.',
        'herramienta': 'curl',
    },
    'synflood': {
        'icono': '🌊', 'nombre': 'SYN flood', 'tipo': 'Volumen (TCP)',
        'descripcion': 'Paquetes SYN a medio abrir. Agota la tabla de conexiones.',
        'herramienta': 'hping3 -S',
    },
    'httpflood': {
        'icono': '🧨', 'nombre': 'HTTP flood', 'tipo': 'Aplicacion',
        'descripcion': 'Muchas peticiones HTTP completas a la vez.',
        'herramienta': 'curl en bucle',
    },
    'slowloris': {
        'icono': '🐌', 'nombre': 'Slowloris', 'tipo': 'Agotamiento de cupos',
        'descripcion': 'Cabeceras HTTP enviadas muy despacio. Ocupa conexiones.',
        'herramienta': 'slowhttptest -H',
    },
    'icmpflood': {
        'icono': '📡', 'nombre': 'ICMP flood', 'tipo': 'Volumen',
        'descripcion': 'Inundacion de ping. Agota ancho de banda.',
        'herramienta': 'ping (kernel)',
    },
    'udpflood': {
        'icono': '💦', 'nombre': 'UDP flood', 'tipo': 'Volumen',
        'descripcion': 'Paquetes UDP sin saludo previo.',
        'herramienta': 'hping3 --udp',
    },
    'ackflood': {
        'icono': '🔨', 'nombre': 'ACK flood', 'tipo': 'Volumen (TCP)',
        'descripcion': 'Paquetes ACK sin conexion real detras.',
        'herramienta': 'hping3 -A',
    },
    'slowpost': {
        'icono': '🫗', 'nombre': 'Slow POST (RUDY)', 'tipo': 'Agotamiento de cupos',
        'descripcion': 'POST a /login con el cuerpo goteado byte a byte.',
        'herramienta': 'slowhttptest -B',
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
        'icono': '⚔️', 'nombre': name, 'tipo': '', 'descripcion': '', 'herramienta': '',
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
        'imagen': check_image() if docker_ok else False,
        'puerto_libre': check_port_free(BENIGN_PORT),
        'puerto': BENIGN_PORT,
        'disco_libre_gb': check_disk_free_gb(),
        'contenedor_activo': check_container_running() if docker_ok else False,
        'scenarios': [scenario_info(s) for s in load_scenarios()],
    })


@app.route('/api/limpiar_contenedor', methods=['POST'])
def api_limpiar_contenedor():
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
        self.onset_s = 0
        self.fase = 'inactivo'  # inactivo|arrancando|navegando|atacando|verificando|cerrando|listo|error|detenido
        self.started_at = None
        self.exit_code = None
        self.logs = deque(maxlen=600)
        self.error = None

    def log(self, line):
        self.logs.append(line.rstrip('\n'))


JOB = Job()

# Frases de los logs de capture_campus.py/topo.py que delatan la fase.
# Ver scripts/mininet/capture_campus.py y topo.py: son los info() que ya
# imprime el pipeline, no texto nuevo que haya que mantener aparte.
_FASE_MARCAS = (
    ('Alumnos navegando el portal', 'navegando'),
    ('C2 (c2) ordena el ataque', 'atacando'),
    ('Sonda del alumno:', 'cerrando'),
    ('OK alumno', 'verificando'),
    ('FALLO', 'verificando'),
)


def _tagged(scenario, run_tag):
    return '%s__%s' % (scenario, run_tag) if run_tag else scenario


def _stream_logs(proc_name):
    """Engancha 'docker logs -f' del contenedor y va llenando JOB.logs,
    actualizando la fase segun lo que va diciendo (ver _FASE_MARCAS)."""
    proc = subprocess.Popen(
        ['docker', 'logs', '-f', proc_name],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        JOB.log(line)
        for marca, fase in _FASE_MARCAS:
            if marca in line:
                if JOB.fase not in ('cerrando', 'listo', 'error', 'detenido'):
                    JOB.fase = fase
                break
    proc.wait()


def _run_scenario_thread(scenario, duration, params):
    run_tag = params.get('RUN_TAG') or ''
    run_name = _tagged(scenario, run_tag)
    JOB.scenario = scenario
    JOB.run_name = run_name
    JOB.duration = duration
    JOB.onset_s = int(params.get('ONSET_S') or 0)
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
        JOB.error = 'No se pudo arrancar el contenedor: %s' % err
        JOB.log(JOB.error)
        JOB.activo = False
        return

    try:
        _stream_logs(CONTAINER_NAME)
    except Exception as exc:  # no tumbar el hilo por un problema leyendo logs
        JOB.log('(logs cortados: %s)' % exc)

    code, out, _err = _run(['docker', 'inspect', '-f', '{{.State.ExitCode}}', CONTAINER_NAME], timeout=10)
    exit_code = out.strip() if code == 0 else '?'
    JOB.exit_code = exit_code
    if JOB.fase != 'detenido':
        JOB.fase = 'listo' if exit_code == '0' else 'error'
    JOB.activo = False


@app.route('/api/lanzar', methods=['POST'])
def api_lanzar():
    body = request.get_json(force=True) or {}
    scenario = body.get('scenario')
    scenarios = load_scenarios() + ['verify']
    if scenario not in scenarios:
        return jsonify({'ok': False, 'error': 'Escenario invalido: %r' % scenario}), 400
    try:
        duration = int(body.get('duration') or 20)
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Duracion invalida'}), 400
    duration = max(5, min(duration, 1800))

    if not JOB.lock.acquire(blocking=False):
        return jsonify({'ok': False, 'error': 'Ya hay una corrida en curso'}), 409
    try:
        if JOB.activo:
            return jsonify({'ok': False, 'error': 'Ya hay una corrida en curso'}), 409
        if not check_docker():
            return jsonify({'ok': False, 'error': 'Docker no responde. Abre Docker Desktop.'}), 503
        if not check_image():
            return jsonify({'ok': False, 'error': 'No esta la imagen %s. Construyela con el Dockerfile primero.' % IMAGE}), 503

        JOB.reset()
        JOB.activo = True
        run_tag = (body.get('run_tag') or '').strip() or ('ui%s' % time.strftime('%H%M%S'))
        params = {
            'RUN_TAG': run_tag,
            'RUN_SEED': body.get('seed') or '',
            'ONSET_S': body.get('onset_s') if body.get('onset_s') not in (None, '') else '',
            'MACHINE_TAG': body.get('machine_tag') or '',
            'STUDENTS_PER_AREA': body.get('students_per_area') or '',
            'BOTS_PER_AREA': body.get('bots_per_area') or '',
        }
        for key in (
            'SYN_PPS', 'ICMP_PPS', 'HTTP_FLOOD_WORKERS', 'HTTP_FLOOD_PAUSE',
            'SLOWLORIS_CONNS', 'UDP_PPS', 'ACK_PPS', 'SLOWPOST_CONNS',
        ):
            if body.get(key) not in (None, ''):
                params[key] = body[key]
        thread = threading.Thread(
            target=_run_scenario_thread, args=(scenario, duration, params), daemon=True,
        )
        thread.start()
        return jsonify({'ok': True, 'run_name': _tagged(scenario, run_tag)})
    finally:
        JOB.lock.release()


@app.route('/api/parar', methods=['POST'])
def api_parar():
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


@app.route('/api/status')
def api_status():
    meta = _read_meta(JOB.run_name) if JOB.run_name else {}
    elapsed = None
    if JOB.started_at:
        elapsed = round(time.time() - JOB.started_at, 1)
    return jsonify({
        'activo': JOB.activo,
        'scenario': JOB.scenario,
        'scenario_info': scenario_info(JOB.scenario) if JOB.scenario else None,
        'run_name': JOB.run_name,
        'fase': JOB.fase,
        'duration': JOB.duration,
        'onset_s': JOB.onset_s,
        'elapsed': elapsed,
        'exit_code': JOB.exit_code,
        'error': JOB.error,
        'logs': list(JOB.logs)[-200:],
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
    if not JOB.run_name:
        return jsonify({'rows': []})
    path = DATA_DIR / 'metrics' / ('%s_interno.csv' % JOB.run_name)
    rows = _tail_csv(path, n=int(request.args.get('n', 180)))
    return jsonify({'rows': rows})


@app.route('/')
def index():
    return send_from_directory(app.template_folder, 'index.html')


if __name__ == '__main__':
    print('*** Interfaz en http://127.0.0.1:%d' % UI_PORT)
    app.run(host='127.0.0.1', port=UI_PORT, debug=False, threaded=True)
