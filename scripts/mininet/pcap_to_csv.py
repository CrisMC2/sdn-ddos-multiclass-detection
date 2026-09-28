#!/usr/bin/env python3
"""Convierte los pcap de data/raw a CSV con columna Label.

Si junto al pcap hay un <nombre>.meta.json del campus, la etiqueta sale
de la IP de origen: las PCs infectadas llevan el nombre del ataque y el
resto (alumnos, portal) queda BENIGN. En baseline tambien las infectadas
son BENIGN, porque en ese escenario solo navegan.

Sin meta, se conserva el criterio viejo: carpeta normal -> BENIGN, si no
el nombre del archivo.

TCP/UDP: CICFlowMeter, llamado por funcion (su CLI tiene los argumentos
al reves). ICMP: agrupador propio, porque CICFlowMeter filtra solo
tcp/udp. Un pcap mixto (alumnos en HTTP e infectados en ICMP) junta las
dos salidas.
"""
import csv
import json
import os

from cicflowmeter.sniffer import create_sniffer
from scapy.all import ICMP, IP, rdpcap

from paths import processed_dir, raw_dir

ICMP_IDLE_TIMEOUT = 5.0
ICMP_FIELDS = [
    'src_ip', 'dst_ip', 'src_port', 'dst_port', 'protocol', 'timestamp',
    'flow_duration', 'flow_byts_s', 'flow_pkts_s',
    'tot_fwd_pkts', 'tot_bwd_pkts', 'totlen_fwd_pkts', 'totlen_bwd_pkts',
]
SRC_KEYS = ('src_ip', 'Src IP', 'srcip')


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
    open_flows = {}
    finished = []

    for pkt in packets:
        if IP not in pkt or ICMP not in pkt:
            continue
        ts = float(pkt.time)
        src, dst = pkt[IP].src, pkt[IP].dst
        size = len(pkt)
        key = frozenset((src, dst))

        flow = open_flows.get(key)
        if flow is not None and ts - flow['last_ts'] > ICMP_IDLE_TIMEOUT:
            finished.append(flow)
            flow = None
        if flow is None:
            flow = {
                'orig_src': src, 'dst': dst, 'start_ts': ts, 'last_ts': ts,
                'fwd_pkts': 0, 'bwd_pkts': 0, 'fwd_bytes': 0, 'bwd_bytes': 0,
            }
            open_flows[key] = flow

        if src == flow['orig_src']:
            flow['fwd_pkts'] += 1
            flow['fwd_bytes'] += size
        else:
            flow['bwd_pkts'] += 1
            flow['bwd_bytes'] += size
        flow['last_ts'] = ts

    finished.extend(open_flows.values())

    with open(csv_path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=ICMP_FIELDS)
        writer.writeheader()
        for flow in finished:
            duration = max(flow['last_ts'] - flow['start_ts'], 1e-6)
            tot_pkts = flow['fwd_pkts'] + flow['bwd_pkts']
            tot_bytes = flow['fwd_bytes'] + flow['bwd_bytes']
            writer.writerow({
                'src_ip': flow['orig_src'],
                'dst_ip': flow['dst'],
                'src_port': 0,
                'dst_port': 0,
                'protocol': 1,
                'timestamp': flow['start_ts'],
                'flow_duration': duration,
                'flow_byts_s': tot_bytes / duration,
                'flow_pkts_s': tot_pkts / duration,
                'tot_fwd_pkts': flow['fwd_pkts'],
                'tot_bwd_pkts': flow['bwd_pkts'],
                'totlen_fwd_pkts': flow['fwd_bytes'],
                'totlen_bwd_pkts': flow['bwd_bytes'],
            })


def load_meta(pcap_path):
    meta_path = os.path.splitext(pcap_path)[0] + '.meta.json'
    if not os.path.isfile(meta_path):
        return None
    with open(meta_path) as fh:
        return json.load(fh)


def fallback_label(pcap_path, raw):
    rel = os.path.relpath(pcap_path, raw)
    top = rel.split(os.sep)[0]
    if top == 'normal':
        return 'BENIGN'
    return os.path.splitext(os.path.basename(pcap_path))[0]


def label_for(src, meta, fallback):
    if not meta:
        return fallback
    bots = set(meta.get('bots') or [])
    scenario = meta.get('scenario') or fallback
    if src in bots and scenario != 'baseline':
        return scenario
    return 'BENIGN'


def src_of(row):
    for key in SRC_KEYS:
        if row.get(key):
            return row[key]
    return ''


def read_dicts(path):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return []
    with open(path, newline='') as fh:
        return list(csv.DictReader(fh))


def write_labeled(rows, out_path, meta, fallback):
    header = []
    for row in rows:
        for key in row:
            if key not in header and key != 'Label':
                header.append(key)
    header.append('Label')
    with open(out_path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            item = dict(row)
            item['Label'] = label_for(src_of(row), meta, fallback)
            writer.writerow(item)
    return max(len(rows), 0)


def iter_pcaps(raw):
    found = []
    if not os.path.isdir(raw):
        return found
    for dirpath, _dirs, files in os.walk(raw):
        for name in files:
            if name.endswith('.pcap'):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def convert_one(pcap_path, raw, out_dir):
    fallback = fallback_label(pcap_path, raw)
    meta = load_meta(pcap_path)
    label_name = (meta or {}).get('scenario') or fallback
    csv_path = os.path.join(out_dir, os.path.splitext(os.path.basename(pcap_path))[0] + '.csv')
    tcp_csv = '/tmp/cfm_tcp.csv'
    icmp_csv = '/tmp/cfm_icmp.csv'
    for path in (tcp_csv, icmp_csv):
        if os.path.isfile(path):
            os.remove(path)

    print('*** Convirtiendo %s -> %s' % (pcap_path, csv_path))
    try:
        convert_tcp_udp(pcap_path, tcp_csv)
    except Exception as exc:
        print('    CICFlowMeter no extrajo TCP/UDP (%s)' % exc)
    try:
        convert_icmp(pcap_path, icmp_csv)
    except Exception as exc:
        print('    Agrupador ICMP fallo (%s)' % exc)

    rows = read_dicts(tcp_csv) + read_dicts(icmp_csv)
    n = write_labeled(rows, csv_path, meta, label_name if not meta else fallback)
    print('    %d flujos (escenario %s)' % (n, label_name))


def main():
    raw = raw_dir()
    out_dir = processed_dir()
    pcaps = iter_pcaps(raw)
    if not pcaps:
        print('No hay pcap en %s' % raw)
        return
    for pcap_path in pcaps:
        convert_one(pcap_path, raw, out_dir)
    print('\nListo. CSVs en %s' % out_dir)


if __name__ == '__main__':
    main()
