FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Paquetes base + Python 3.9 (Ryu no funciona con Python 3.12: usa
# distutils, que fue removido). Ver README.md para el detalle de cada
# fix aplicado en esta imagen.
RUN echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        mininet openvswitch-switch openvswitch-common \
        hping3 slowhttptest tcpdump tshark curl \
        git software-properties-common ca-certificates \
        python3 python3-pip python3-venv \
        ethtool iproute2 iputils-ping \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.9 python3.9-venv python3.9-distutils \
    && rm -rf /var/lib/apt/lists/*

# --- Ryu: setuptools moderno rompe su instalacion (usa
# easy_install, removido) y eventlet moderno rompe su import
# (ALREADY_HANDLED, removido). Se fijan versiones compatibles y se
# desactiva el build isolation de pip para que respete el setuptools
# fijado en vez de bajarse uno nuevo. ---
RUN python3.9 -m venv /opt/ryu-venv \
    && /opt/ryu-venv/bin/pip install --upgrade pip \
    && /opt/ryu-venv/bin/pip install "setuptools==57.5.0" wheel pbr \
    && /opt/ryu-venv/bin/pip install --no-build-isolation ryu \
    && /opt/ryu-venv/bin/pip install "eventlet==0.30.2"

# --- CICFlowMeter (reimplementacion en Python) ---
RUN python3 -m venv /opt/cfm-venv \
    && /opt/cfm-venv/bin/pip install --upgrade pip \
    && /opt/cfm-venv/bin/pip install cicflowmeter

COPY scripts/mininet/ /ataque/mininet/
COPY scripts/docker/verify.sh scripts/docker/capture_normal.sh scripts/docker/capture_attack.sh scripts/docker/pcap_to_csv.sh /ataque/scripts/
COPY scripts/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /ataque/scripts/*.sh

WORKDIR /ataque
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
