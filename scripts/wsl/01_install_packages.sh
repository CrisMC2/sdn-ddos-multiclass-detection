#!/usr/bin/env bash
# Instala Mininet, Open vSwitch, herramientas de trafico/ataque y un Python
# viejo (3.9) para poder instalar Ryu (Ryu no funciona en Python 3.12: usa
# distutils, que Python 3.12 elimino).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# tshark pregunta interactivamente si usuarios no-root pueden capturar
# paquetes; lo dejamos en "no" (siempre lo vamos a correr con sudo) para
# que apt no se quede esperando input.
echo "wireshark-common wireshark-common/install-setuid boolean false" | sudo debconf-set-selections

sudo apt update
sudo apt install -y \
    mininet openvswitch-switch openvswitch-common \
    hping3 slowhttptest apache2 apache2-utils tcpdump tshark \
    git curl software-properties-common \
    python3-pip python3-venv

# Ryu necesita Python <= 3.9 (distutils). Ubuntu 24.04 trae 3.12 por
# defecto, asi que agregamos deadsnakes para tener una version compatible
# solo para el venv de Ryu (no toca el Python del sistema).
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.9 python3.9-venv python3.9-distutils \
    || sudo apt install -y python3.8 python3.8-venv python3.8-distutils

echo "OK: paquetes base instalados"
