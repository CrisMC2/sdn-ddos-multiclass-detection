#!/usr/bin/env python3
"""Campus reducido: modem, core SDN, DMZ con el portal, y un laboratorio
por area academica de la UNCP.

El atacante (C2) esta del lado internet del modem. Los alumnos y las
PCs infectadas estan en los laboratorios. El trafico hacia el portal
cruza el switch de la facultad y el core; no hace falta salir a internet.

Uso (con Ryu ya escuchando en 127.0.0.1:6653):
    python3 topo.py        # CLI de Mininet
    python3 topo.py test   # alumno->portal, infectado->portal, C2->infectado
"""
import os
import subprocess
import sys
import time

from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink

from benign_mix import attach_benign_client, benign_port, stop_benign
from roles import (
    AREAS,
    BENIGN_CLIENT_IP,
    C2_GW,
    C2_IP,
    C2_NAME,
    CORE_SWITCH,
    DMZ_SWITCH,
    MODEM_CAMPUS_IP,
    VICTIM_IP,
    VICTIM_NAME,
    area_of,
    area_switch,
    bots,
    students,
)


class UserspaceOVSSwitch(OVSSwitch):
    """OVS en userspace. Dentro de Docker/WSL no hay modulo de kernel."""

    def __init__(self, *args, **kwargs):
        kwargs['datapath'] = 'user'
        kwargs.setdefault('protocols', 'OpenFlow13')
        super(UserspaceOVSSwitch, self).__init__(*args, **kwargs)

    def start(self, controllers):
        super(UserspaceOVSSwitch, self).start(controllers)
        self.cmd('ovs-vsctl set bridge %s datapath_type=netdev' % self.name)


def _offload_off(host):
    # ethtool suele estar en /usr/sbin, fuera del PATH de un host de Mininet.
    # Sin esto el ping responde y el TCP (el portal) se queda colgado.
    host.cmd(
        'ETH=$(command -v ethtool || echo /usr/sbin/ethtool); '
        'for i in /sys/class/net/*; do '
        '"$ETH" -K "$(basename "$i")" tx off rx off tso off gso off gro off; '
        'done >/tmp/ethtool.log 2>&1 || true'
    )


def _campus_net(host, ip):
    """Una sola red 10.0.0.0/8. 10.1.0.10/16 NO incluye al portal 10.0.0.10."""
    iface = host.defaultIntf().name
    host.cmd('ip addr flush dev %s' % iface)
    host.cmd('ip addr add %s/8 dev %s' % (ip, iface))
    host.cmd('ip link set %s up' % iface)
    host.cmd('ip route replace default via %s' % MODEM_CAMPUS_IP)


def build():
    net = Mininet(
        controller=RemoteController,
        switch=UserspaceOVSSwitch,
        link=TCLink,
        autoSetMacs=True,
    )

    info('*** Controlador Ryu en 127.0.0.1:6653\n')
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** Switches: core, DMZ y un laboratorio por area\n')
    core = net.addSwitch(CORE_SWITCH)
    dmz = net.addSwitch(DMZ_SWITCH)
    area_sw = {}
    for key, _prefix, title in AREAS:
        info('    laboratorio %s (%s) en %s\n' % (key, title, area_switch(key)))
        area_sw[key] = net.addSwitch(area_switch(key))

    modem = net.addHost('modem', ip='%s/8' % MODEM_CAMPUS_IP)
    c2 = net.addHost(C2_NAME, ip='%s/24' % C2_IP, defaultRoute='via %s' % C2_GW)
    www = net.addHost(
        VICTIM_NAME, ip='%s/8' % VICTIM_IP, defaultRoute='via %s' % MODEM_CAMPUS_IP
    )

    # eth0 del modem mira al campus; eth1 (el segundo enlace) mira a internet.
    net.addLink(modem, core)
    net.addLink(c2, modem)
    net.addLink(core, dmz)
    net.addLink(dmz, www)

    hosts = [modem, c2, www]
    campus_ips = {VICTIM_NAME: VICTIM_IP}
    for name, ip in list(students()) + list(bots()):
        host = net.addHost(
            name, ip='%s/8' % ip, defaultRoute='via %s' % MODEM_CAMPUS_IP
        )
        net.addLink(area_sw[area_of(name)], host)
        hosts.append(host)
        campus_ips[name] = ip

    for key in area_sw:
        net.addLink(core, area_sw[key])

    net.build()
    c0.start()
    for sw in [core, dmz] + [area_sw[k] for k, _p, _t in AREAS]:
        sw.start([c0])

    info('*** Modem: reenvio entre internet (%s) y el campus (%s)\n' % (C2_GW, MODEM_CAMPUS_IP))
    modem.cmd('ip addr add %s/24 dev modem-eth1' % C2_GW)
    modem.cmd('ip link set modem-eth1 up')
    for name, ip in campus_ips.items():
        _campus_net(net.get(name), ip)
    # Reenvio por interfaz: con solo ip_forward el paquete que entra por
    # internet a veces sigue viendo la red del campus como inalcanzable.
    for knob in (
        '/proc/sys/net/ipv4/ip_forward',
        '/proc/sys/net/ipv4/conf/all/forwarding',
        '/proc/sys/net/ipv4/conf/default/forwarding',
        '/proc/sys/net/ipv4/conf/modem-eth0/forwarding',
        '/proc/sys/net/ipv4/conf/modem-eth1/forwarding',
    ):
        modem.cmd('echo 1 > %s 2>/dev/null || true' % knob)
    for iface in ('all', 'default', 'modem-eth0', 'modem-eth1'):
        modem.cmd('echo 0 > /proc/sys/net/ipv4/conf/%s/rp_filter 2>/dev/null || true' % iface)
        modem.cmd('echo 1 > /proc/sys/net/ipv4/conf/%s/proxy_arp 2>/dev/null || true' % iface)

    for host in hosts:
        _offload_off(host)

    web = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webserver.py')
    info('*** Portal en %s (%s:80)\n' % (VICTIM_NAME, VICTIM_IP))
    www.cmd('echo starting > /tmp/www.log; python3 %s 80 >> /tmp/www.log 2>&1 &' % web)

    ok, detail = attach_benign_client(dmz)
    if ok:
        info('*** Portal benigno listo: %s\n' % detail)
        info('*** Tu navegador sale como %s y se mezcla con el campus. El ataque no sale de esta red.\n' % BENIGN_CLIENT_IP)
    else:
        info('*** Sin entrada para tu navegador (%s). El escenario sigue con los alumnos emulados.\n' % detail)
    return net


def _ping_ok(host, dst):
    out = host.cmd('ping -c 3 -W 2 %s' % dst)
    bad = (
        ('0 received' in out)
        or ('100% packet loss' in out)
        or ('unreachable' in out.lower())
        or (not out.strip())
    )
    return (not bad), out


def test_campus(net):
    time.sleep(2)
    www_ip = net.get(VICTIM_NAME).IP()
    bot_name, bot_ip = next(bots())
    checks = (
        ('alumno -> portal', net.get('salud-u1'), www_ip),
        ('infectado -> portal', net.get(bot_name), www_ip),
        ('C2 -> infectado', net.get(C2_NAME), bot_ip),
    )
    failed = 0
    for label, src, dst in checks:
        ok, out = _ping_ok(src, dst)
        if ok:
            info('OK %s\n' % label)
        else:
            failed += 1
            info('FALLO %s\n%s\n' % (label, out))

    code = net.get('salud-u1').cmd(
        'curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://' + www_ip + '/'
    ).strip()
    if code == '200':
        info('OK alumno abre el portal (HTTP %s)\n' % code)
    else:
        failed += 1
        info('FALLO alumno abre el portal (HTTP %r)\n' % code)
        if os.path.isfile('/tmp/www.log'):
            info(open('/tmp/www.log').read())

    browser = ''
    try:
        browser = subprocess.check_output(
            [
                'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                '--max-time', '5', 'http://127.0.0.1:%d/' % benign_port(),
            ],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        browser = ''
    if browser == '200':
        info('OK navegador externo abre el portal (HTTP %s)\n' % browser)
    else:
        failed += 1
        info('FALLO navegador externo abre el portal (HTTP %r)\n' % browser)

    if failed:
        info('--- alumno ---\n')
        info(net.get('salud-u1').cmd('ip -4 addr; ip -4 route'))
        info('--- modem ---\n')
        info(net.get('modem').cmd(
            'echo forward=$(cat /proc/sys/net/ipv4/ip_forward); '
            'ip -4 route; ip route get 10.1.0.20 from %s iif modem-eth1' % C2_IP
        ))
        if os.path.isfile('/tmp/www.log'):
            info(open('/tmp/www.log').read())
    return failed


def main():
    setLogLevel('info')
    net = build()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'test':
            failed = test_campus(net)
            sys.exit(1 if failed else 0)
        CLI(net)
    finally:
        stop_benign()
        net.stop()


if __name__ == '__main__':
    main()
