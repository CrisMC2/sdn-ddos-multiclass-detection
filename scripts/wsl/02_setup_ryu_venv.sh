#!/usr/bin/env bash
# Crea un venv aislado con Python 3.9 (o 3.8) e instala Ryu ahi dentro,
# sin tocar el Python del sistema.
#
# El venv se crea en el filesystem nativo de Linux (~/ataque-ryu-venv) y
# no dentro de /mnt/c/..., porque escribir los miles de archivos chicos
# de un venv/pip sobre el mount 9P de Windows es extremadamente lento
# (a veces cuelga). Dejamos un symlink en ryu/venv para que desde la
# carpeta del proyecto se vea y se use igual.
set -euo pipefail

PYBIN="$(command -v python3.9 || command -v python3.8 || true)"
if [ -z "$PYBIN" ]; then
    echo "No se encontro python3.9 ni python3.8. Corre 01_install_packages.sh primero." >&2
    exit 1
fi

REAL_VENV="$HOME/ataque-ryu-venv"
PROJECT_RYU_DIR="$(cd "$(dirname "$0")/../ryu" && pwd)"

"$PYBIN" -m venv "$REAL_VENV"
"$REAL_VENV/bin/pip" install --upgrade pip
# Ryu (sin mantenimiento) instala via un hook de setup.py que usa
# setuptools.command.easy_install, removido en setuptools modernos.
# Se fija una version vieja de setuptools que todavia lo trae, y se
# desactiva el build isolation de pip para que use ESA version en vez
# de bajarse un setuptools nuevo para el build (que es lo que hace por
# default con PEP 517).
"$REAL_VENV/bin/pip" install "setuptools==57.5.0" wheel pbr
"$REAL_VENV/bin/pip" install --no-build-isolation ryu
# El eventlet mas nuevo removio ALREADY_HANDLED de eventlet.wsgi, que
# ryu 4.34 todavia importa. Se fija una version vieja compatible.
"$REAL_VENV/bin/pip" install "eventlet==0.30.2"

ln -sfn "$REAL_VENV" "$PROJECT_RYU_DIR/venv"

echo "OK: entorno virtual de Ryu listo en $REAL_VENV (symlink en ryu/venv), usando $PYBIN"
