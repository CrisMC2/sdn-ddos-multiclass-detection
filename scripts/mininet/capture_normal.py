#!/usr/bin/env python3
"""Levanta la topologia, genera trafico HTTP normal (client1 y client2
pidiendole paginas a "server" en loop con pausas aleatorias) y lo
captura con tcpdump en un pcap separado.

Uso:
    sudo python3 capture_normal.py [duracion_segundos] [salida.pcap]
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topo import build
from mininet.log import setLogLevel, info

DEFAULT_DURATION = 300
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'raw', 'normal', 'normal.pcap'
)
LOOP_TAG = 'ataque_normal_loop'


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DURATION
    out = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.abspath(DEFAULT_OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # tcpdump escribe primero a un tmp en el filesystem nativo de Linux:
    # escribir paquete a paquete directo sobre /mnt/c/... (Windows) es tan
    # lento por el mount 9P que puede llegar a trabar todo el proceso.
    # Al final se copia el pcap ya terminado (una sola escritura grande,
    # rapida) al destino real.
    tmp_out = '/tmp/%s' % os.path.basename(out)

    setLogLevel('info')
    net = build()
    server = net.get('server')
    client1 = net.get('client1')
    client2 = net.get('client2')
    iface = server.defaultIntf().name
    server_ip = server.IP()

    info('*** Capturando en %s (interfaz %s) durante %ss\n' % (tmp_out, iface, duration))
    server.cmd('tcpdump -i %s -w %s &' % (iface, tmp_out))
    time.sleep(1)

    info('*** Generando trafico normal (curl en loop desde client1 y client2)\n')
    for c in (client1, client2):
        # OJO: todo lo que sigue a "#" en bash es un comentario, INCLUIDO
        # un "&" puesto despues -> el loop quedaria corriendo en primer
        # plano y colgaria este cmd() para siempre. El tag va como un
        # ":" (no-op) al principio del cuerpo, y el "&" real al final.
        c.cmd(
            "while true; do : %s; curl -s -o /dev/null http://%s/; "
            "sleep $(awk -v min=0.05 -v max=0.3 'BEGIN{srand(); print min+rand()*(max-min)}'); "
            "done &" % (LOOP_TAG, server_ip)
        )

    time.sleep(duration)

    info('*** Deteniendo trafico y captura\n')
    for c in (client1, client2):
        c.cmd("pkill -f %s 2>/dev/null || true" % LOOP_TAG)
    server.cmd('pkill tcpdump 2>/dev/null || true')
    time.sleep(1)

    net.stop()
    shutil.copyfile(tmp_out, out)
    os.remove(tmp_out)
    info('*** Captura guardada en %s\n' % out)


if __name__ == '__main__':
    main()
