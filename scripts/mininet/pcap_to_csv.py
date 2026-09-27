#!/usr/bin/env python3
"""Convierte los pcap de data/raw/normal y data/raw/attacks a CSV,
agregando una columna Label segun la carpeta/archivo de origen.
Un solo script, compartido por el flujo de WSL y el de Docker (cada
uno lo llama con su propio venv, pero es el mismo codigo).

Para TCP/UDP se usa CICFlowMeter. No se usa su CLI porque main() tiene
un bug: llama a create_sniffer() con los argumentos en el orden
equivocado (sobra un parametro en la firma), asi que el booleano
"verbose" termina en el parametro "fields" y revienta con
    AttributeError: 'bool' object has no attribute 'split'
Aca se llama a create_sniffer() directo, con keywords, evitando el bug.

Para ICMP (p.ej. icmpflood.pcap) CICFlowMeter no sirve: su sniffer
filtra la captura con "ip and (tcp or udp)", asi que un pcap 100% ICMP
le da CERO paquetes y produce un CSV vacio sin avisar. Se usa en su
lugar un agrupador de flujos propio, chico, con scapy: junta paquetes
ICMP entre el mismo par de IPs en un "flujo" mientras no pase mas de
ICMP_IDLE_TIMEOUT segundos sin trafico entre ellos (mismo concepto de
"flujo" que usa CICFlowMeter, pero implementado a mano). Las columnas
se nombran igual que las de CICFlowMeter donde aplica, para que se
puedan concatenar mas adelante sin problema (las columnas TCP-only
quedan NaN en las filas ICMP, y el Pipeline de la Fase 5 ya tiene que
imputar de todas formas).

Uso:
    python3 pcap_to_csv.py
"""
import csv
import os

from cicflowmeter.sniffer import create_sniffer
from scapy.all import rdpcap, IP, ICMP

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE, 'data', 'raw')
OUT_DIR = os.path.join(BASE, 'data', 'processed')

# (carpeta, etiqueta a usar en la columna Label)
SOURCES = [
    (os.path.join(RAW_DIR, 'normal'), 'BENIGN'),
    (os.path.join(RAW_DIR, 'attacks'), None),  # None = usa el nombre del archivo
]

ICMP_IDLE_TIMEOUT = 5.0  # segundos de silencio que cortan un flujo en dos
ICMP_FIELDS = [
    'src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'timestamp',
    'flow_duration', 'flow_byts_s', 'flow_pkts_s',
    'tot_fwd_pkts', 'tot_bwd_pkts', 'totlen_fwd_pkts', 'totlen_bwd_pkts',
]


def convert_tcp_udp(pcap_path, csv_path):
    sniffer, session = create_sniffer(
        input_file=pcap_path,
        input_interface=None,
        output_mode='csv',
        output=csv_path,
        fields=None,
        verbose=False,
    )
    sniffer.start()
    sniffer.join()
    if hasattr(session, '_gc_stop'):
        session._gc_stop.set()
        session._gc_thread.join(timeout=2.0)
    session.flush_flows()


def convert_icmp(pcap_path, csv_path):
    packets = rdpcap(pcap_path)
    open_flows = {}   # key: frozenset({ip1, ip2}) -> flujo en curso
    finished = []

    for pkt in packets:
        if IP not in pkt or ICMP not in pkt:
            continue
        ts = float(pkt.time)
        src, dst = pkt[IP].src, pkt[IP].dst
        size = len(pkt)
        key = frozenset((src, dst))

        f = open_flows.get(key)
        if f is not None and ts - f['last_ts'] > ICMP_IDLE_TIMEOUT:
            finished.append(f)
            f = None
        if f is None:
            f = {
                'orig_src': src, 'dst': dst, 'start_ts': ts, 'last_ts': ts,
                'fwd_pkts': 0, 'bwd_pkts': 0, 'fwd_bytes': 0, 'bwd_bytes': 0,
            }
            open_flows[key] = f

        if src == f['orig_src']:
            f['fwd_pkts'] += 1
            f['fwd_bytes'] += size
        else:
            f['bwd_pkts'] += 1
            f['bwd_bytes'] += size
        f['last_ts'] = ts

    finished.extend(open_flows.values())

    with open(csv_path, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(ICMP_FIELDS)
        for f in finished:
            duration = max(f['last_ts'] - f['start_ts'], 1e-6)
            tot_pkts = f['fwd_pkts'] + f['bwd_pkts']
            tot_bytes = f['fwd_bytes'] + f['bwd_bytes']
            w.writerow([
                f['orig_src'], f['dst'], 0, 0, 1, f['start_ts'],
                duration, tot_bytes / duration, tot_pkts / duration,
                f['fwd_pkts'], f['bwd_pkts'], f['fwd_bytes'], f['bwd_bytes'],
            ])


def add_label_column(csv_path, label):
    with open(csv_path, newline='') as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    header, data = rows[0], rows[1:]
    header.append('Label')
    for row in data:
        row.append(label)
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for folder, fixed_label in SOURCES:
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith('.pcap'):
                continue
            pcap_path = os.path.join(folder, name)
            label = fixed_label if fixed_label else os.path.splitext(name)[0]
            csv_path = os.path.join(OUT_DIR, os.path.splitext(name)[0] + '.csv')

            print('*** Convirtiendo %s -> %s (Label=%s)' % (pcap_path, csv_path, label))
            if label == 'icmpflood':
                convert_icmp(pcap_path, csv_path)
            else:
                convert_tcp_udp(pcap_path, csv_path)
            add_label_column(csv_path, label)
            n = sum(1 for _ in open(csv_path)) - 1
            print('    %d flujos' % max(n, 0))

    print('\nListo. CSVs en %s' % OUT_DIR)


if __name__ == '__main__':
    main()
