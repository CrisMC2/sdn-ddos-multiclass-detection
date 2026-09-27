#!/usr/bin/env python3
"""Topologia base: 1 servidor web, 2 clientes normales, 2 atacantes,
todos colgados de un switch OVS (datapath userspace) apuntando a un
controlador Ryu remoto en 127.0.0.1:6653.

Uso:
    sudo python3 topo.py           # abre la CLI de Mininet
    sudo python3 topo.py test      # corre pingall no interactivo y sale
"""
import sys

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class UserspaceOVSSwitch(OVSSwitch):
    """OVSSwitch forzado a datapath_type=netdev (userspace).

    Evita depender del modulo de kernel de OVS, que es la fuente mas
    comun de problemas dentro de WSL2.
    """

    def start(self, controllers):
        super().start(controllers)
        self.cmd('ovs-vsctl set bridge %s datapath_type=netdev' % self.name)


def build():
    net = Mininet(
        controller=RemoteController,
        switch=UserspaceOVSSwitch,
        link=TCLink,
        autoSetMacs=True,
    )

    info('*** Agregando controlador Ryu remoto\n')
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('*** Agregando switch\n')
    s1 = net.addSwitch('s1')

    info('*** Agregando hosts\n')
    server = net.addHost('server', ip='10.0.0.1/24')
    client1 = net.addHost('client1', ip='10.0.0.2/24')
    client2 = net.addHost('client2', ip='10.0.0.3/24')
    attacker1 = net.addHost('attacker1', ip='10.0.0.4/24')
    attacker2 = net.addHost('attacker2', ip='10.0.0.5/24')

    for h in (server, client1, client2, attacker1, attacker2):
        net.addLink(h, s1)

    net.build()
    c0.start()
    s1.start([c0])

    info('*** Desactivando checksum offload en las interfaces (bug conocido\n'
         '    de Mininet/OVS: TCP se cuelga porque el kernel descarta\n'
         '    segmentos con checksum invalido calculado por hardware que\n'
         '    no existe; ICMP no se ve afectado porque no valida checksum\n'
         '    del mismo modo)\n')
    for h in (server, client1, client2, attacker1, attacker2):
        h.cmd('ethtool -K %s tx off rx off tso off gso off gro off 2>/dev/null' % h.defaultIntf().name)

    info('*** Levantando servidor web en "server"\n')
    # No se usa "service apache2 start" / systemd: eso le pide al systemd
    # del sistema (que vive en el namespace de red raiz) que arranque el
    # proceso, y el apache resultante queda escuchando fuera del
    # namespace de "server" -> nunca responde a los clientes. Lanzando
    # el proceso directo desde este cmd() queda corriendo DENTRO del
    # namespace de red de "server", que es lo que hace falta.
    server.cmd('python3 -m http.server 80 --directory /var/www/html > /tmp/server_http.log 2>&1 &')

    return net


def main():
    setLogLevel('info')
    net = build()

    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        result = net.pingAll()
        net.stop()
        sys.exit(1 if result > 0 else 0)  # pingAll devuelve % de paquetes perdidos

    CLI(net)
    net.stop()


if __name__ == '__main__':
    main()
