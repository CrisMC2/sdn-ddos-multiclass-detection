"""Los endpoints /api/*. La logica vive en jobs/launch/dockerctl/runfiles; aqui
solo se traduce entre HTTP y ellas."""
from flask import Blueprint, jsonify, request

from . import dockerctl, jobs, runfiles
from .catalog import GRUPOS, attack_ids, load_scenarios, scenario_info
from .config import BENIGN_PORT, IMAGE
from .launch import LaunchError, parse

api = Blueprint('api', __name__, url_prefix='/api')


@api.get('/env')
def env():
    docker = dockerctl.docker_ok()
    return jsonify({
        'docker': docker,
        'imagen': dockerctl.image_ok() if docker else None,
        'imagen_nombre': IMAGE,
        'puerto_libre': dockerctl.port_free(BENIGN_PORT),
        'puerto': BENIGN_PORT,
        'disco_libre_gb': dockerctl.disk_free_gb(),
        'contenedor_activo': dockerctl.container_running() if docker else False,
        'grupos': list(GRUPOS),
        'ataques': attack_ids(),
        'scenarios': [scenario_info(s) for s in load_scenarios()],
    })


@api.post('/limpiar_contenedor')
def limpiar_contenedor():
    if jobs.JOB.activo:
        return jsonify({'ok': False, 'error': 'Hay una corrida en curso: detenla primero.'}), 409
    dockerctl.remove_container()
    return jsonify({'ok': True})


@api.post('/lanzar')
def lanzar():
    body = request.get_json(force=True, silent=True) or {}
    try:
        launch = parse(body)
        jobs.start(launch)
    except LaunchError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except jobs.JobError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), exc.status
    return jsonify({'ok': True, 'run_name': launch.run_name})


@api.post('/parar')
def parar():
    ok, error = jobs.stop()
    return jsonify({'ok': ok, 'error': error})


@api.get('/status')
def status():
    return jsonify(jobs.snapshot())


@api.get('/metrics')
def metrics():
    job = jobs.JOB
    if not job.run_name or job.scenario == 'verify':
        return jsonify({'rows': []})
    try:
        n = max(1, min(int(request.args.get('n', 400)), 2000))
    except ValueError:
        n = 400
    return jsonify({'rows': runfiles.metrics_rows(job.run_name, n=n)})
