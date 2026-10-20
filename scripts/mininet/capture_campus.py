#!/usr/bin/env python3
"""Corre un escenario del campus y guarda pcap + metricas.

baseline: alumnos y PCs infectadas navegan el portal (nadie ataca).
synflood, httpflood, slowloris, icmpflood: los alumnos siguen navegando
y las PCs infectadas atacan el mismo portal.

Si abres http://127.0.0.1:8080/ durante la medicion, ese trafico entra
como cliente benigno real y queda mezclado en la misma captura.

Uso (con Ryu ya en 127.0.0.1:6653):
    python3 capture_campus.py <escenario> [segundos] [salida.pcap]
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import time

from mininet.log import setLogLevel, info

from benign_mix import BENIGN_IFACE, iface_counter, split_capture, stop_benign
from paths import metrics_dir, raw_dir
from roles import (
    BENIGN_CLIENT_IP,
    BROWSE_PAUSE_MAX,
    BROWSE_PAUSE_MIN,
    C2_NAME,
    CORE_SWITCH,
    HTTP_FLOOD_PAUSE,
    HTTP_FLOOD_WORKERS,
    ICMP_PPS,
    PAGES,
    SCENARIOS,
    SLOWLORIS_CONNS,
    SYN_PPS,
    VICTIM_IP,
    VICTIM_NAME,
    bots,
    run_config,
    students,
    tagged,
)
from topo import build

PROBE = 'salud-u1'


def _write_script(path, body):
    with open(path, 'w') as fh:
        fh.write(body)
    os.chmod(path, 0o755)


def _install_scripts(victim):
    pages = ' '.join(PAGES)
    _write_script('/tmp/browse.sh', '''#!/bin/sh
while true; do
  : campus_browse
  page=$(awk -v seed="$RANDOM" 'BEGIN{srand(seed); n=split("%s", p, " "); print p[int(rand()*n)+1]}')
  curl -s -o /dev/null --max-time 3 "http://%s${page}"
  sleep $(awk -v min=%s -v max=%s -v seed="$RANDOM" 'BEGIN{srand(seed); print min+rand()*(max-min)}')
done
''' % (pages, victim, BROWSE_PAUSE_MIN, BROWSE_PAUSE_MAX))
    _write_script('/tmp/httpflood.sh', '''#!/bin/sh
while true; do
  : httpflood
  curl -s -o /dev/null --max-time 2 "http://%s/"
  sleep %s
done
''' % (victim, HTTP_FLOOD_PAUSE))


def _hping_flag(pps):
    return '-i u%d' % int(1000000 / pps)


def start_browse(host):
    host.cmd('sh /tmp/browse.sh > /tmp/%s.browse.log 2>&1 &' % host.name)


def start_attack(host, scenario, victim, duration):
    if scenario == 'synflood':
        host.cmd(
            'hping3 -S -p 80 %s %s > /tmp/%s.attack.log 2>&1 &'
            % (_hping_flag(SYN_PPS), victim, host.name)
        )
    elif scenario == 'httpflood':
        # Un solo curl por PC no llena el cupo: cada una abre varios a la vez.
        for worker in range(HTTP_FLOOD_WORKERS):
            host.cmd(
                'sh /tmp/httpflood.sh > /tmp/%s.attack.%d.log 2>&1 &'
                % (host.name, worker)
            )
    elif scenario == 'slowloris':
        host.cmd(
            'slowhttptest -c %d -H -i 10 -r 20 -t GET -u http://%s/ -x 24 -p 3 -l %d '
            '> /tmp/%s.attack.log 2>&1 &'
            % (SLOWLORIS_CONNS, victim, duration + 15, host.name)
        )
    elif scenario == 'icmpflood':
        host.cmd(
            'hping3 --icmp %s %s > /tmp/%s.attack.log 2>&1 &'
            % (_hping_flag(ICMP_PPS), victim, host.name)
        )


def stop_host(host):
    host.cmd('pkill -f browse.sh 2>/dev/null || true')
    host.cmd('pkill -f httpflood.sh 2>/dev/null || true')
    host.cmd('pkill -f hping3 2>/dev/null || true')
    host.cmd('pkill -f slowhttptest 2>/dev/null || true')


def _counter(host, iface, name):
    raw = host.cmd('cat /sys/class/net/%s/statistics/%s 2>/dev/null' % (iface, name)).strip()
    try:
        return int(raw)
    except ValueError:
        return None


def _core_flows():
    try:
        out = subprocess.check_output(
            ['ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', CORE_SWITCH],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return ''
    return sum(1 for line in out.splitlines() if 'n_packets' in line)


def _probe(host, victim):
    raw = host.cmd(
        'curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time 3 http://'
        + victim + '/'
    ).strip().split()
    code = raw[0] if raw else '000'
    try:
        latency_ms = '%.1f' % (float(raw[1]) * 1000.0)
    except (IndexError, ValueError):
        latency_ms = ''
        if code == '%{http_code}':
            code = '000'
    return code, latency_ms


def _conns(host):
    raw = host.cmd("ss -Htn 2>/dev/null | grep -c ':80' || true").strip()
    try:
        return int(raw)
    except ValueError:
        return ''


def _percentile(values, p):
    if not values:
        return ''
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
    return '%.1f' % ordered[idx]


def _upsert_resumen(path, row):
    header = [
        'scenario', 'duration_s', 'samples', 'http_200', 'http_fail',
        'latency_ms_avg', 'latency_ms_p95',         'server_rx_pps_avg', 'core_flows_max', 'benign_real_pps_avg',
    ]
    rows = []
    if os.path.isfile(path):
        with open(path, newline='') as fh:
            for old in csv.DictReader(fh):
                if old.get('scenario') != row['scenario']:
                    rows.append(old)
    rows.append(row)
    with open(path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SCENARIOS:
        print('Uso: python3 capture_campus.py <%s> [segundos] [salida.pcap]' % '|'.join(SCENARIOS))
        raise SystemExit(1)

    scenario = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    name = tagged(scenario)
    out = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.join(raw_dir(), '%s.pcap' % name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    metrics_path = os.path.join(metrics_dir(), '%s_interno.csv' % name)
    meta_path = os.path.splitext(out)[0] + '.meta.json'
    tmp_out = '/tmp/%s.pcap' % name

    meta = {
        'scenario': scenario,
        'victim': VICTIM_IP,
        'students': [ip for _name, ip in students()],
        'bots': [ip for _name, ip in bots()],
        'benign_client': BENIGN_CLIENT_IP,
        'pages': list(PAGES),
    }
    meta.update(run_config())
    with open(meta_path, 'w') as fh:
        json.dump(meta, fh, indent=2)

    setLogLevel('info')
    info('*** Escenario %s durante %ss\n' % (scenario, duration))
    info('    alumnos=%d infectados=%d portal=%s\n' % (
        len(meta['students']), len(meta['bots']), VICTIM_IP))

    net = None
    try:
        net = build()
        www = net.get(VICTIM_NAME)
        probe = net.get(PROBE)
        iface = www.defaultIntf().name
        _install_scripts(VICTIM_IP)
        time.sleep(1)

        skip_pcap = _skip_pcap()
        if skip_pcap:
            info('*** SKIP_PCAP: sin captura de pcap (solo metricas + SDN, mas rapido)\n')
        else:
            info('*** Captura en %s\n' % out)
            www.cmd('tcpdump -i %s -w %s >/tmp/tcpdump.log 2>&1 &' % (iface, tmp_out))
            time.sleep(1)

        info('*** Alumnos navegando el portal (inicio, login, notas, aula, biblioteca)\n')
        for name, _ip in students():
            start_browse(net.get(name))

        if scenario == 'baseline':
            info('*** PCs infectadas tambien navegan: todavia no hay ataque\n')
            for name, _ip in bots():
                start_browse(net.get(name))
        else:
            info('*** C2 (%s) ordena el ataque a las PCs infectadas\n' % C2_NAME)
            c2 = net.get(C2_NAME)
            for _name, ip in bots():
                c2.cmd('ping -c 1 -W 1 %s >/dev/null 2>&1 &' % ip)
            time.sleep(2)
            info('*** Ataque %s desde %d PCs hacia %s\n' % (scenario, len(meta['bots']), VICTIM_IP))
            for name, _ip in bots():
                start_attack(net.get(name), scenario, VICTIM_IP, duration)

        header = [
            'timestamp', 'elapsed_s', 'probe_http_code', 'probe_latency_ms',
            'server_rx_pps', 'server_rx_bps', 'server_conns', 'core_flows',
            'benign_real_tx_pps', 'benign_real_tx_bps',
        ]
        prev_pkts = _counter(www, iface, 'rx_packets')
        prev_bytes = _counter(www, iface, 'rx_bytes')
        prev_benign_pkts = iface_counter(BENIGN_IFACE, 'tx_packets')
        prev_benign_bytes = iface_counter(BENIGN_IFACE, 'tx_bytes')
        prev_t = time.time()
        latencies = []
        ok_n = 0
        fail_n = 0
        pps_values = []
        benign_pps_values = []
        flow_values = []

        with open(metrics_path, 'w', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            deadline = time.time() + duration
            elapsed = 0
            while time.time() < deadline:
                elapsed += 1
                sample_started = time.time()
                now = sample_started
                dt = max(now - prev_t, 0.001)
                pkts = _counter(www, iface, 'rx_packets')
                nbytes = _counter(www, iface, 'rx_bytes')
                if pkts is None or prev_pkts is None:
                    pps = ''
                    bps = ''
                else:
                    pps = '%.1f' % ((pkts - prev_pkts) / dt)
                    bps = '%.1f' % ((nbytes - prev_bytes) / dt)
                    pps_values.append(float(pps))
                benign_pkts = iface_counter(BENIGN_IFACE, 'tx_packets')
                benign_bytes = iface_counter(BENIGN_IFACE, 'tx_bytes')
                if benign_pkts is None or prev_benign_pkts is None:
                    benign_pps = ''
                    benign_bps = ''
                else:
                    benign_pps = '%.1f' % ((benign_pkts - prev_benign_pkts) / dt)
                    benign_bps = '%.1f' % ((benign_bytes - prev_benign_bytes) / dt)
                    benign_pps_values.append(float(benign_pps))
                prev_pkts, prev_bytes, prev_t = pkts, nbytes, now
                prev_benign_pkts, prev_benign_bytes = benign_pkts, benign_bytes

                code, latency_ms = _probe(probe, VICTIM_IP)
                if code == '200':
                    ok_n += 1
                    if latency_ms:
                        latencies.append(float(latency_ms))
                else:
                    fail_n += 1
                flows = _core_flows()
                if flows != '':
                    flow_values.append(flows)
                writer.writerow([
                    int(now), elapsed, code, latency_ms, pps, bps,
                    _conns(www), flows, benign_pps, benign_bps,
                ])
                fh.flush()
                remain = 1.0 - (time.time() - sample_started)
                if remain > 0:
                    time.sleep(min(remain, max(0.0, deadline - time.time())))

        samples = ok_n + fail_n
        avg_latency = ('%.1f' % (sum(latencies) / len(latencies))) if latencies else ''
        avg_pps = ('%.1f' % (sum(pps_values) / len(pps_values))) if pps_values else ''
        row = {
            'scenario': name,
            'duration_s': duration,
            'samples': samples,
            'http_200': ok_n,
            'http_fail': fail_n,
            'latency_ms_avg': avg_latency,
            'latency_ms_p95': _percentile(latencies, 0.95),
            'server_rx_pps_avg': avg_pps,
            'core_flows_max': max(flow_values) if flow_values else '',
            'benign_real_pps_avg': (
                '%.1f' % (sum(benign_pps_values) / len(benign_pps_values))
                if benign_pps_values else ''
            ),
        }
        resumen = os.path.join(metrics_dir(), 'resumen.csv')
        _upsert_resumen(resumen, row)
        info('*** Sonda del alumno: %d OK, %d fallos, latencia media %s ms\n' % (
            ok_n, fail_n, avg_latency or '-'))
        info('*** Metricas: %s\n' % metrics_path)
        info('*** Resumen: %s\n' % resumen)
        if ok_n == 0 and os.path.isfile('/tmp/www.log'):
            info('*** El portal no respondio 200. Log:\n')
            info(open('/tmp/www.log').read())
    finally:
        if net is not None:
            for name, _ip in list(students()) + list(bots()):
                stop_host(net.get(name))
            net.get(VICTIM_NAME).cmd('pkill tcpdump 2>/dev/null || true')
            time.sleep(1)
            stop_benign()
            net.stop()
        if os.path.isfile(tmp_out):
            shutil.copyfile(tmp_out, out)
            os.remove(tmp_out)
            info('*** Pcap: %s\n' % out)
            try:
                analysis, report = split_capture(out, meta, metrics_path)
                info('*** Analisis: %s\n' % analysis)
                info(report + '\n')
            except OSError as exc:
                info('*** No se pudo partir la captura: %s\n' % exc)
        else:
            info('*** No quedo pcap en %s\n' % tmp_out)


if __name__ == '__main__':
    main()
