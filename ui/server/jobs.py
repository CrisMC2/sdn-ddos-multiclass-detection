"""La corrida activa. Una a la vez: el contenedor siempre se llama igual, asi
que dos corridas a la vez se pisarian.

start() arranca el contenedor en un hilo que ademas engancha 'docker logs -f'
(de ahi sale la fase) y muestrea 'docker stats' a <run>_docker.csv."""
import subprocess
import threading
import time
from collections import deque

from . import dockerctl, runfiles
from .catalog import scenario_info
from .config import BENIGN_PORT, CONTAINER_NAME, DATA_DIR, DOCKER_DIR, IMAGE, MININET_DIR, ROOT


class JobError(Exception):
    """Algo impide lanzar. 'status' es el codigo HTTP que corresponde."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.activo = False
        self.scenario = None
        self.run_name = None
        self.duration = 0
        self.config = {}
        # inactivo|arrancando|navegando|atacando|verificando|cerrando|listo|error|detenido
        self.fase = 'inactivo'
        self.started_at = None
        self.exit_code = None
        self.logs = deque(maxlen=600)
        self.error = None

    def log(self, line):
        self.logs.append(line.rstrip('\n'))


JOB = Job()

# Frases de los logs de capture_campus.py/topo.py que delatan la fase. Son los
# info() que ya imprime el pipeline, no texto nuevo que haya que mantener aparte.
_FASE_MARCAS = (
    ('Alumnos navegando el portal', 'navegando'),
    ('C2 (c2) ordena el ataque', 'atacando'),
    ('Sonda del alumno:', 'cerrando'),
)


def _stream_logs():
    proc = subprocess.Popen(
        ['docker', 'logs', '-f', CONTAINER_NAME],
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
    """CPU, memoria y red del contenedor, en el mismo formato que escribia
    run_scenario.sh (<run>_docker.csv). Alimenta la seccion de consumo del
    banco del paper."""
    path = DATA_DIR / 'metrics' / ('%s_docker.csv' % run_name)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write('timestamp,cpu,mem,net_io\n')
        while dockerctl.container_running():
            code, out, _err = dockerctl.run(
                ['docker', 'stats', '--no-stream', '--format',
                 '{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}', CONTAINER_NAME], timeout=8)
            line = out.strip()
            if code == 0 and line:
                fh.write('%d,%s\n' % (int(time.time()), line))
                fh.flush()
            time.sleep(1)


def _docker_run_cmd(launch):
    env_vars = {'DATA_DIR': '/ataque/data', 'PYTHONDONTWRITEBYTECODE': '1',
                'BENIGN_PORT': str(BENIGN_PORT)}
    env_vars.update({k: str(v) for k, v in launch.params.items() if v not in (None, '')})
    cmd = ['docker', 'run', '-d', '--name', CONTAINER_NAME, '--privileged']
    for key, val in env_vars.items():
        cmd += ['-e', '%s=%s' % (key, val)]
    cmd += [
        '-p', '127.0.0.1:%d:%d' % (BENIGN_PORT, BENIGN_PORT),
        '-v', '%s:/ataque/data' % (ROOT / 'data'),
        '-v', '%s:/ataque/mininet:ro' % MININET_DIR,
        '-v', '%s:/ataque/scripts:ro' % DOCKER_DIR,
        IMAGE,
        'bash', '/ataque/scripts/capture_campus.sh', launch.scenario, str(launch.duration),
    ]
    return cmd


def _explain_exit(exit_code):
    if exit_code in ('137', '143'):
        # 137 = SIGKILL, 143 = SIGTERM: lo mataron desde fuera (si el usuario
        # hubiera pulsado Detener, la fase seria 'detenido').
        return ('El contenedor se detuvo desde fuera de esta corrida (código %s). '
                'Suele pasar si otra copia de la interfaz, o un comando docker, lo '
                'eliminó; o si Docker se quedó sin memoria.' % exit_code)
    return 'El contenedor terminó con código %s. Revisa el registro.' % exit_code


def _worker(launch):
    JOB.fase = 'verificando' if launch.scenario == 'verify' else 'arrancando'
    JOB.started_at = time.time()
    for sub in ('raw', 'metrics', 'processed'):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)

    dockerctl.remove_container()   # quita uno viejo ya detenido (con el mismo nombre)
    cmd = _docker_run_cmd(launch)
    JOB.log('$ docker run -d --name %s ... %s %s' % (CONTAINER_NAME, launch.scenario, launch.duration))
    code, _out, err = dockerctl.run(cmd, timeout=30)
    if code != 0:
        JOB.fase = 'error'
        JOB.error = 'No se pudo arrancar el contenedor: %s' % err.strip()
        JOB.log(JOB.error)
        JOB.activo = False
        return

    sampler = None
    if launch.scenario != 'verify':
        sampler = threading.Thread(target=_sample_docker_stats, args=(launch.run_name,), daemon=True)
        sampler.start()
    try:
        _stream_logs()
    except Exception as exc:  # no tumbar el hilo por un problema leyendo logs
        JOB.log('(logs cortados: %s)' % exc)
    if sampler:
        sampler.join(timeout=5)

    code, out, _err = dockerctl.run(['docker', 'inspect', '-f', '{{.State.ExitCode}}', CONTAINER_NAME], timeout=10)
    exit_code = out.strip() if code == 0 else '?'
    if launch.scenario == 'verify':
        # Ryu escribe su telemetria tambien al verificar; la prueba de caminos
        # promete no guardar datos, asi que no se deja nada.
        runfiles.remove_metric(launch.run_name, '_sdn.csv')
    JOB.exit_code = exit_code
    if JOB.fase != 'detenido':
        if exit_code == '0':
            JOB.fase = 'listo'
        else:
            JOB.fase = 'error'
            JOB.error = _explain_exit(exit_code)
    JOB.activo = False


def start(launch):
    if not JOB.lock.acquire(blocking=False):
        raise JobError(409, 'Ya hay una corrida en curso.')
    try:
        if JOB.activo:
            raise JobError(409, 'Ya hay una corrida en curso.')
        if not dockerctl.docker_ok():
            raise JobError(503, 'Docker no responde. Abre Docker Desktop y espera a que diga «Engine running».')
        if not dockerctl.image_ok():
            raise JobError(503, 'No existe la imagen %s. Constrúyela con scripts/docker/Dockerfile.' % IMAGE)
        # Arrancar un contenedor nuevo elimina el anterior. Si esta en marcha y
        # no es de esta interfaz (otra copia en otra terminal, un docker run a
        # mano), lanzar interrumpiria esa corrida: mejor negarse y explicarlo.
        if dockerctl.container_running():
            raise JobError(409, 'Ya hay un contenedor «%s» en marcha que no pertenece a esta interfaz: '
                                'otra copia abierta en otra terminal o un comando docker. '
                                'Espera a que termine, o elimínalo desde Entorno si sabes que sobra.' % CONTAINER_NAME)

        JOB.reset()
        JOB.activo = True
        JOB.scenario = launch.scenario
        JOB.run_name = launch.run_name
        JOB.duration = launch.duration
        JOB.config = {
            'onset_s': launch.onset,
            'attacks': launch.attacks,
            'intensities': {k: v for k, v in launch.params.items()
                            if k.endswith(('_PPS', '_CONNS', '_WORKERS'))},
            'students_per_area': launch.params.get('STUDENTS_PER_AREA'),
            'bots_per_area': launch.params.get('BOTS_PER_AREA'),
            'perfil': launch.params.get('ATTACK_PROFILE', 'normal'),
            'carga_variable': launch.params.get('BENIGN_LOAD') == 'variable',
        }
        threading.Thread(target=_worker, args=(launch,), daemon=True).start()
    finally:
        JOB.lock.release()


def stop():
    """Detiene la corrida activa. Devuelve (ok, error)."""
    if not JOB.activo:
        return True, None
    JOB.fase = 'detenido'
    code, _out, err = dockerctl.remove_container()
    JOB.activo = False
    JOB.log('--- detenido por el usuario ---')
    return code == 0, (None if code == 0 else err)


def snapshot():
    """Lo que ve la pagina: estado de la corrida, meta.json y archivos."""
    meta = runfiles.read_meta(JOB.run_name) if JOB.run_name else {}
    is_verify = JOB.scenario == 'verify'
    elapsed = round(time.time() - JOB.started_at, 1) if JOB.started_at else None
    return {
        'activo': JOB.activo,
        'scenario': JOB.scenario,
        'scenario_info': scenario_info(JOB.scenario) if JOB.scenario and not is_verify else None,
        'run_name': JOB.run_name,
        'fase': JOB.fase,
        'duration': JOB.duration,
        'config': JOB.config,
        'elapsed': elapsed,
        'exit_code': JOB.exit_code,
        'error': JOB.error,
        'logs': list(JOB.logs)[-200:],
        'archivos': runfiles.output_files(JOB.run_name) if JOB.run_name and not is_verify else [],
        'meta': {
            'bots': meta.get('bots', []),
            'students': meta.get('students', []),
            'victim': meta.get('victim'),
            'benign_client': meta.get('benign_client'),
            'attack_start_elapsed': meta.get('attack_start_elapsed'),
            'onset_planned_s': meta.get('onset_planned_s'),
            'datapath': meta.get('datapath'),
            'bot_attacks': meta.get('bot_attacks', {}),
            'attack_profile': meta.get('attack_profile'),
            'attack_mode': meta.get('attack_mode'),
            'pulse_on_s': meta.get('pulse_on_s'),
            'pulse_off_s': meta.get('pulse_off_s'),
            'bot_delays_s': meta.get('bot_delays_s', {}),
        },
    }
