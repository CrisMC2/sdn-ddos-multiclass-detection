#!/usr/bin/env bash
# El contenedor no tiene systemd (PID 1 no es systemd), asi que Open
# vSwitch no se puede arrancar con "service"/"systemctl" como en una
# VM normal. Se levantan ovsdb-server y ovs-vswitchd a mano, una sola
# vez por contenedor.
set -e

mkdir -p /etc/openvswitch /var/run/openvswitch

# Intenta cargar el modulo de kernel de OVS. Si el kernel del host (la VM de
# Docker Desktop) lo trae, el datapath de kernel queda disponible y evita el
# atasco del datapath userspace con floods sostenidos. Si no esta, no pasa
# nada: topo.py detecta su ausencia y cae a userspace.
modprobe openvswitch 2>/dev/null || true
if [ -d /sys/module/openvswitch ]; then
    echo "entrypoint: modulo openvswitch disponible -> datapath de kernel"
else
    echo "entrypoint: sin modulo openvswitch -> datapath userspace (netdev)"
fi

if [ ! -S /var/run/openvswitch/db.sock ]; then
    if [ ! -f /etc/openvswitch/conf.db ]; then
        ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
    fi
    ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
        --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
        --pidfile --detach --log-file
    ovs-vsctl --no-wait init
    # Sin modulo de kernel se usa el datapath userspace, que se atasca con
    # trafico sostenido. Mas hilos de handler/revalidator lo mitigan (no lo
    # eliminan). Se fija en la DB antes de arrancar vswitchd.
    ovs-vsctl --no-wait set Open_vSwitch . \
        other_config:n-handler-threads=4 \
        other_config:n-revalidator-threads=2 2>/dev/null || true
    ovs-vswitchd --pidfile --detach --log-file
fi

export DATA_DIR="${DATA_DIR:-/ataque/data}"
export PYTHONDONTWRITEBYTECODE=1

exec "$@"
