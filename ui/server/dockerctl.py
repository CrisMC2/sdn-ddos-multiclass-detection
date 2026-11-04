"""Hablar con Docker y con el sistema. Siempre con listas de argumentos (sin
shell ni bash), asi no hay conversion de rutas de Git Bash en Windows."""
import shutil
import socket
import subprocess

from .config import CONTAINER_NAME, IMAGE, ROOT


def run(args, timeout=10):
    """(codigo, stdout, stderr). Nunca lanza: un docker caido devuelve codigo 1."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              errors='replace')
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, '', str(exc)


def docker_ok():
    return run(['docker', 'info'], timeout=8)[0] == 0


def image_ok():
    code, out, _err = run(['docker', 'images', '-q', IMAGE], timeout=8)
    return code == 0 and out.strip() != ''


def container_running():
    code, out, _err = run(['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME], timeout=8)
    return code == 0 and out.strip() == 'true'


def remove_container():
    return run(['docker', 'rm', '-f', CONTAINER_NAME], timeout=15)


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_in_use(port):
    """Hay algo escuchando (a diferencia de port_free, no intenta ocuparlo)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()


def disk_free_gb():
    try:
        return round(shutil.disk_usage(str(ROOT)).free / (1024 ** 3), 1)
    except OSError:
        return None
