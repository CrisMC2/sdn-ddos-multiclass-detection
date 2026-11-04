"""Convertir una corrida a los dos datasets de entrenamiento:
  - por flujo   data/processed/<run>.csv            (pcap -> CICFlowMeter, en Docker)
  - por ventana data/processed/ventanas/<run>.csv   (metricas + telemetria SDN)

Solo procesa la corrida pedida (ONLY_RUNS), no los demas pcap de data/raw:
reconvertirlos todos tarda decenas de minutos. Un trabajo a la vez, y no
mientras hay una simulacion en marcha (competirian por CPU)."""
import csv
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter, deque

from . import dockerctl
from .config import DATA_DIR, IMAGE, MININET_DIR
from .jobs import JOB, JobError

CONVERT_CONTAINER = 'ataque-sdn-convert'


class Convert:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.activo = False
        self.run_name = None
        self.fase = 'inactivo'     # inactivo|flujos|ventanas|listo|error
        self.logs = deque(maxlen=120)
        self.error = None
        self.started_at = None
        self.resultado = None


CONV = Convert()


def _conteo(path):
    if not path.is_file():
        return None
    try:
        with open(path, newline='', encoding='utf-8', errors='replace') as fh:
            c = Counter(r.get('Label', '?') for r in csv.DictReader(fh))
    except (OSError, csv.Error):
        return None
    return {'total': sum(c.values()), 'por_clase': dict(c.most_common())}


def resultado(run_name):
    """Lo que hay en disco de esa corrida, aunque se haya generado antes."""
    flujos = _conteo(DATA_DIR / 'processed' / ('%s.csv' % run_name))
    ventanas = _conteo(DATA_DIR / 'processed' / 'ventanas' / ('%s.csv' % run_name))
    return {'run_name': run_name, 'flujos': flujos, 'ventanas': ventanas}


def _worker(run_name):
    try:
        CONV.fase = 'flujos'
        dockerctl.run(['docker', 'rm', '-f', CONVERT_CONTAINER], timeout=15)
        cmd = ['docker', 'run', '--rm', '--name', CONVERT_CONTAINER, '--entrypoint', 'bash',
               '-e', 'DATA_DIR=/ataque/data', '-e', 'PYTHONDONTWRITEBYTECODE=1',
               '-e', 'ONLY_RUNS=%s' % run_name,
               '-v', '%s:/ataque/data' % DATA_DIR, '-v', '%s:/ataque/mininet:ro' % MININET_DIR,
               IMAGE, '/ataque/scripts/pcap_to_csv.sh']
        proc = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=900)
        for line in (proc.stdout + proc.stderr).splitlines()[-40:]:
            if line.startswith(('***', '    ')):
                CONV.logs.append(line.rstrip())
        if proc.returncode != 0:
            raise RuntimeError('La conversión de flujos terminó con código %d.' % proc.returncode)

        CONV.fase = 'ventanas'
        env = dict(os.environ, ONLY_RUNS=run_name, DATA_DIR=str(DATA_DIR))
        proc = subprocess.run([sys.executable, str(MININET_DIR / 'build_windows.py')], cwd=str(MININET_DIR),
                              env=env, capture_output=True, text=True, errors='replace', timeout=300)
        for line in (proc.stdout + proc.stderr).splitlines()[-10:]:
            CONV.logs.append(line.rstrip())
        if proc.returncode != 0:
            raise RuntimeError('Armar las ventanas terminó con código %d.' % proc.returncode)
        CONV.resultado = resultado(run_name)
        CONV.fase = 'listo'
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        CONV.fase = 'error'
        CONV.error = str(exc)
    finally:
        CONV.activo = False


def start(run_name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', run_name or ''):
        raise JobError(400, 'Nombre de corrida inválido.')
    if not (DATA_DIR / 'raw' / ('%s.pcap' % run_name)).is_file():
        raise JobError(404, 'Esa corrida no tiene captura (.pcap): no hay nada que convertir.')
    if JOB.activo:
        raise JobError(409, 'Hay una simulación en curso: espera a que termine para convertir.')
    if not dockerctl.docker_ok() or not dockerctl.image_ok():
        raise JobError(503, 'Docker o la imagen no están disponibles. Revisa el Entorno.')
    if not CONV.lock.acquire(blocking=False):
        raise JobError(409, 'Ya hay una conversión en curso.')
    try:
        if CONV.activo:
            raise JobError(409, 'Ya hay una conversión en curso.')
        CONV.reset()
        CONV.activo = True
        CONV.run_name = run_name
        CONV.started_at = time.time()
        threading.Thread(target=_worker, args=(run_name,), daemon=True).start()
    finally:
        CONV.lock.release()


def snapshot():
    res = CONV.resultado
    if not CONV.activo and CONV.run_name is None and JOB.run_name and JOB.scenario != 'verify':
        res = resultado(JOB.run_name)   # ya convertida antes: se muestra sin volver a pedir
        if not (res['flujos'] or res['ventanas']):
            res = None
    return {
        'activo': CONV.activo, 'run_name': CONV.run_name, 'fase': CONV.fase, 'error': CONV.error,
        'logs': list(CONV.logs), 'resultado': res,
        'elapsed': round(time.time() - CONV.started_at, 1) if CONV.started_at else None,
    }
