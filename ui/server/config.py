"""Rutas y constantes de la interfaz. Nada aqui depende de Flask."""
import os
from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[1]
ROOT = UI_DIR.parent

WEB_DIR = UI_DIR / 'web'
MININET_DIR = ROOT / 'scripts' / 'mininet'
DOCKER_DIR = ROOT / 'scripts' / 'docker'
DATA_DIR = ROOT / 'data'
SCENARIOS_FILE = MININET_DIR / 'scenarios.txt'

IMAGE = os.environ.get('IMAGE', 'ataque-sdn')
# Siempre se llama igual: lanzar otra corrida elimina el contenedor anterior.
CONTAINER_NAME = 'ataque-sdn-run'
BENIGN_PORT = int(os.environ.get('BENIGN_PORT', '8080'))
UI_PORT = int(os.environ.get('UI_PORT') or os.environ.get('PORT') or '8765')
