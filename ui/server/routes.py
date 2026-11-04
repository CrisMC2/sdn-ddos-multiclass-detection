"""Los endpoints /api/*. La logica vive en jobs/launch/dockerctl/runfiles; aqui
solo se traduce entre HTTP y ellas."""
import io
import re
import zipfile

from flask import Blueprint, jsonify, request, send_file

from . import datasets, dockerctl, jobs, runfiles
from .catalog import GRUPOS, attack_ids, load_scenarios, scenario_info
from .config import BENIGN_PORT, DATA_DIR, IMAGE
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
    snap = jobs.snapshot()
    snap['datasets'] = datasets.snapshot()
    return jsonify(snap)


@api.post('/convertir')
def convertir():
    body = request.get_json(force=True, silent=True) or {}
    try:
        datasets.start(body.get('run_name'))
    except jobs.JobError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), exc.status
    return jsonify({'ok': True})


@api.get('/descargar/<run_name>')
def descargar(run_name):
    """ZIP con los CSV de una corrida (flujos y ventanas) y su meta.json, que
    es lo que explica como se etiqueto cada fila."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', run_name):
        return jsonify({'ok': False, 'error': 'Nombre de corrida inválido.'}), 400
    archivos = [
        (DATA_DIR / 'processed' / ('%s.csv' % run_name), 'por_flujo/%s.csv' % run_name),
        (DATA_DIR / 'processed' / 'ventanas' / ('%s.csv' % run_name), 'por_ventana/%s.csv' % run_name),
        (DATA_DIR / 'raw' / ('%s.meta.json' % run_name), '%s.meta.json' % run_name),
    ]
    existentes = [(ruta, nombre) for ruta, nombre in archivos if ruta.is_file()]
    if not any(n.endswith('.csv') for _r, n in existentes):
        return jsonify({'ok': False, 'error': 'Esa corrida todavía no tiene CSV: conviértela primero.'}), 404
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, 'w', zipfile.ZIP_DEFLATED) as zf:
        for ruta, nombre in existentes:
            zf.write(ruta, nombre)
    memoria.seek(0)
    return send_file(memoria, mimetype='application/zip', as_attachment=True,
                     download_name='%s.zip' % run_name)


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
