"""Donde viven los datos, tanto en el repo (WSL) como en la imagen Docker.

En Docker el codigo queda en /ataque/mininet (un nivel bajo /ataque) y el
volumen del Mac esta en /ataque/data. DATA_DIR gana si esta definido.
"""
import os


def data_dir():
    env = os.environ.get('DATA_DIR')
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, '..', '..'))
    if os.path.isdir(os.path.join(repo, 'scripts')):
        return os.path.join(repo, 'data')
    return os.path.abspath(os.path.join(here, '..', 'data'))


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def raw_dir():
    return ensure(os.path.join(data_dir(), 'raw'))


def metrics_dir():
    return ensure(os.path.join(data_dir(), 'metrics'))


def processed_dir():
    return ensure(os.path.join(data_dir(), 'processed'))
