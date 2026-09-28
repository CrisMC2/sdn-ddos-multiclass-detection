#!/usr/bin/env bash
# El contenedor no tiene systemd (PID 1 no es systemd), asi que Open
# vSwitch no se puede arrancar con "service"/"systemctl" como en una
# VM normal. Se levantan ovsdb-server y ovs-vswitchd a mano, una sola
# vez por contenedor.
set -e

mkdir -p /etc/openvswitch /var/run/openvswitch

if [ ! -S /var/run/openvswitch/db.sock ]; then
    if [ ! -f /etc/openvswitch/conf.db ]; then
        ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
    fi
    ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
        --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
        --pidfile --detach --log-file
    ovs-vsctl --no-wait init
    ovs-vswitchd --pidfile --detach --log-file
fi

export DATA_DIR="${DATA_DIR:-/ataque/data}"
export PYTHONDONTWRITEBYTECODE=1

exec "$@"
