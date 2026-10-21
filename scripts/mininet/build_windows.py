#!/usr/bin/env python3
"""Construye un dataset POR VENTANA DE TIEMPO para deteccion temprana.

El dataset de flujos (data/processed/<escenario>.csv) clasifica un flujo
cuando ya termino: es deteccion despues del hecho. Para detectar el
ataque MIENTRAS pasa hace falta mirar la red por ventanas de tiempo. Eso
es lo que arma este script: una fila por segundo y por escenario, con lo
que se ve en ese instante.

Fuentes por escenario (en data/metrics/):
  <escenario>_interno.csv  -> sonda del alumno + contadores del portal
                              (siempre existe)
  <escenario>_sdn.csv      -> telemetria OpenFlow del controlador Ryu
                              (existe solo si corriste con flow_monitor_13)

La etiqueta es por ventana: baseline -> BENIGN; cada ataque lleva su
nombre. Un modelo entrenado sobre esto decide "ahora mismo, ¿esto se ve
como un ataque?", que es el paso de clasificar a predecir.

Salida:
  data/processed/ventanas/<escenario>.csv
  data/processed/ventanas/ventanas.csv   (todos juntos, para entrenar)

Corre en la Mac, sin Docker:
  python3 scripts/mininet/build_windows.py
"""
import csv
import json
import math
import os

from paths import metrics_dir, processed_dir, raw_dir

SCENARIOS = ('baseline', 'synflood', 'httpflood', 'slowloris', 'icmpflood')

# Columnas de referencia (NO son features: el entrenamiento las descarta).
REF_FIELDS = ['timestamp', 'elapsed_s', 'scenario', 'run']

# Features que salen de la sonda y los contadores del portal.
# core_flows sale de la tabla OpenFlow del switch core: es un dato SDN, y por
# eso lleva el prefijo sdn_ (los grupos de features se arman por prefijo).
# benign_real_tx_* (la interfaz del navegador del operador) ya no entra: sin
# nadie navegando solo es ruido de la interfaz y no distingue nada.
PROBE_FIELDS = [
    'server_rx_pps', 'server_rx_bps', 'server_conns', 'sdn_core_flows',
    'probe_latency_ms', 'http_ok',
]

# Features derivadas del tiempo (cambio y suavizado).
DERIVED_FIELDS = [
    'sdn_core_flows_delta', 'rx_pps_delta', 'rx_pps_roll3', 'conns_roll3',
]

# Features de la vista SDN del controlador (0 si no hay _sdn.csv).
# Las *_icmp / *_tcp son la clave para separar icmpflood de synflood: el
# protocolo solo se ve en la telemetria del controlador, no en los
# contadores del portal (que ven igual los dos floods).
SDN_FIELDS = [
    'sdn_flows_total', 'sdn_src_total', 'sdn_delta_pkts', 'sdn_delta_bytes',
    'sdn_src_entropy', 'sdn_src_entropy_norm', 'sdn_max_src_share',
    'sdn_mean_pkts_per_flow',
    'sdn_pkts_icmp', 'sdn_pkts_tcp', 'sdn_frac_icmp', 'sdn_frac_tcp',
    # Suavizado (rolling max de los ultimos SDN_ROLL s): el controlador
    # muestrea cada ~2 s, asi que la senal de protocolo sale a rafagas y
    # queda en 0 en la mayoria de las ventanas. El rolling max la hace
    # persistir mientras dura el episodio, que es lo que importa para
    # detectar. Es memoria corta (no mira todo el escenario), asi que
    # sigue siendo defendible como deteccion en linea.
    'sdn_pkts_icmp_roll', 'sdn_frac_icmp_roll',
]

# Ventana (en segundos) del rolling max de la senal de protocolo.
SDN_ROLL = 10

FEATURE_FIELDS = PROBE_FIELDS + DERIVED_FIELDS + SDN_FIELDS
ALL_FIELDS = REF_FIELDS + FEATURE_FIELDS + ['Label']


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_rows(path):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        return []
    with open(path, newline='') as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------
# Vista SDN: de contadores acumulados por flujo a features por instante.
# --------------------------------------------------------------------------

def sdn_snapshots(path):
    """Agrupa el _sdn.csv por instante de muestreo y calcula, por cada uno,
    el delta de cada flujo (los contadores solo crecen) para derivar
    entropia de IPs origen, concentracion y ritmo del intervalo."""
    rows = read_rows(path)
    if not rows:
        return {}

    by_ts = {}
    for row in rows:
        ts = int(_num(row.get('timestamp')))
        by_ts.setdefault(ts, []).append(row)

    prev_cum = {}            # (src,dst,proto) -> paquetes acumulados
    prev_cum_bytes = {}
    snapshots = {}
    for ts in sorted(by_ts):
        # Se queda con el conteo mayor por flujo (mismo flujo en 2 switches).
        cur = {}
        for row in by_ts[ts]:
            key = (row.get('src_ip', ''), row.get('dst_ip', ''), row.get('proto', ''))
            pkts = _num(row.get('packets'))
            nbytes = _num(row.get('bytes'))
            best = cur.get(key)
            if best is None or pkts > best[0]:
                cur[key] = (pkts, nbytes)

        per_src = {}
        per_proto = {}           # proto (int) -> paquetes del intervalo
        delta_pkts_total = 0.0
        delta_bytes_total = 0.0
        for key, (pkts, nbytes) in cur.items():
            d_pkts = max(0.0, pkts - prev_cum.get(key, 0.0))
            d_bytes = max(0.0, nbytes - prev_cum_bytes.get(key, 0.0))
            src = key[0]
            per_src[src] = per_src.get(src, 0.0) + d_pkts
            try:
                proto = int(float(key[2]))
            except (TypeError, ValueError):
                proto = -1
            per_proto[proto] = per_proto.get(proto, 0.0) + d_pkts
            delta_pkts_total += d_pkts
            delta_bytes_total += d_bytes
        # No reemplazar: conservar el acumulado por flujo. Si un flujo falta en
        # un muestreo y reaparece, el delta se calcula contra su ultimo valor
        # real (no contra 0), evitando el pico falso al reaparecer.
        for k, v in cur.items():
            prev_cum[k] = v[0]
            prev_cum_bytes[k] = v[1]

        entropy = 0.0
        max_share = 0.0
        if delta_pkts_total > 0:
            for d in per_src.values():
                p = d / delta_pkts_total
                if p > 0:
                    entropy -= p * math.log2(p)
                max_share = max(max_share, p)
        n_src = len(per_src)
        entropy_norm = entropy / math.log2(n_src) if n_src > 1 else 0.0
        n_flows = len(cur)

        pkts_icmp = per_proto.get(1, 0.0)   # proto 1 = ICMP
        pkts_tcp = per_proto.get(6, 0.0)    # proto 6 = TCP
        frac_icmp = pkts_icmp / delta_pkts_total if delta_pkts_total > 0 else 0.0
        frac_tcp = pkts_tcp / delta_pkts_total if delta_pkts_total > 0 else 0.0

        snapshots[ts] = {
            'sdn_flows_total': n_flows,
            'sdn_src_total': n_src,
            'sdn_delta_pkts': round(delta_pkts_total, 1),
            'sdn_delta_bytes': round(delta_bytes_total, 1),
            'sdn_src_entropy': round(entropy, 4),
            'sdn_src_entropy_norm': round(entropy_norm, 4),
            'sdn_max_src_share': round(max_share, 4),
            'sdn_mean_pkts_per_flow': round(delta_pkts_total / n_flows, 1) if n_flows else 0.0,
            'sdn_pkts_icmp': round(pkts_icmp, 1),
            'sdn_pkts_tcp': round(pkts_tcp, 1),
            'sdn_frac_icmp': round(frac_icmp, 4),
            'sdn_frac_tcp': round(frac_tcp, 4),
        }
    return snapshots


def sdn_for(ts, snapshots, sorted_ts):
    """La telemetria SDN mas reciente con instante <= ts. Si todavia no hubo
    ninguna muestra, ceros: nunca se usa una muestra del futuro."""
    if not sorted_ts:
        return {name: 0.0 for name in SDN_FIELDS}
    chosen = None
    for snap_ts in sorted_ts:
        if snap_ts <= ts:
            chosen = snap_ts
        else:
            break
    if chosen is None:
        return {name: 0.0 for name in SDN_FIELDS}
    return snapshots[chosen]


def load_meta(run_name):
    """meta.json de la corrida (data/raw/<corrida>.meta.json), o {}."""
    path = os.path.join(raw_dir(), '%s.meta.json' % run_name)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def label_window(base, elapsed, meta):
    """BENIGN antes del ataque, el nombre del ataque desde que arranca.
    baseline siempre BENIGN. Una corrida vieja, sin el instante de inicio en
    su meta, se etiqueta entera con el escenario (comportamiento anterior)."""
    if base == 'baseline':
        return 'BENIGN'
    start = meta.get('attack_start_elapsed')
    if start is None:
        # Meta nueva (trae onset_planned_s) sin inicio registrado: el ataque
        # nunca arranco, todo fue benigno. Meta vieja: entera con el escenario.
        return 'BENIGN' if 'onset_planned_s' in meta else base
    return base if elapsed >= int(start) else 'BENIGN'


# --------------------------------------------------------------------------
# Ensamblado por escenario.
# --------------------------------------------------------------------------

def build_run(run_name, base, run_id):
    interno = read_rows(os.path.join(metrics_dir(), '%s_interno.csv' % run_name))
    if not interno:
        return []
    snapshots = sdn_snapshots(os.path.join(metrics_dir(), '%s_sdn.csv' % run_name))
    sorted_ts = sorted(snapshots)
    meta = load_meta(run_name)

    out = []
    pps_history = []
    conns_history = []
    icmp_pkts_history = []
    icmp_frac_history = []
    prev_core = None
    prev_pps = None
    for row in interno:
        # La primera muestra de cada corrida sale vacia (los contadores del
        # portal arrancan en ese instante, rx_pps = 0): no es una ventana real.
        if int(_num(row.get('elapsed_s'))) <= 1:
            continue
        ts = int(_num(row.get('timestamp')))
        rx_pps = _num(row.get('server_rx_pps'))
        conns = _num(row.get('server_conns'))
        core = _num(row.get('core_flows'))
        code = (row.get('probe_http_code') or '').strip()
        elapsed = int(_num(row.get('elapsed_s')))

        pps_history.append(rx_pps)
        conns_history.append(conns)
        roll_pps = sum(pps_history[-3:]) / len(pps_history[-3:])
        roll_conns = sum(conns_history[-3:]) / len(conns_history[-3:])

        record = {
            'timestamp': ts,
            'elapsed_s': int(_num(row.get('elapsed_s'))),
            'scenario': base,
            'run': run_id,
            'server_rx_pps': rx_pps,
            'server_rx_bps': _num(row.get('server_rx_bps')),
            'server_conns': conns,
            'sdn_core_flows': core,
            'probe_latency_ms': _num(row.get('probe_latency_ms')),
            'http_ok': 1 if code == '200' else 0,
            'sdn_core_flows_delta': 0.0 if prev_core is None else core - prev_core,
            'rx_pps_delta': 0.0 if prev_pps is None else rx_pps - prev_pps,
            'rx_pps_roll3': round(roll_pps, 1),
            'conns_roll3': round(roll_conns, 1),
            'Label': label_window(base, elapsed, meta),
        }
        record.update(sdn_for(ts, snapshots, sorted_ts))
        # Suavizado de la senal de protocolo (rolling max de SDN_ROLL s).
        icmp_pkts_history.append(record.get('sdn_pkts_icmp', 0.0))
        icmp_frac_history.append(record.get('sdn_frac_icmp', 0.0))
        record['sdn_pkts_icmp_roll'] = round(max(icmp_pkts_history[-SDN_ROLL:]), 1)
        record['sdn_frac_icmp_roll'] = round(max(icmp_frac_history[-SDN_ROLL:]), 4)
        out.append(record)
        prev_core = core
        prev_pps = rx_pps
    return out


def write_csv(path, rows):
    with open(path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=ALL_FIELDS, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def discover_runs():
    """Cada <nombre>_interno.csv es una corrida. El nombre puede ser el
    escenario ('synflood') o el escenario con sufijo de corrida
    ('synflood__r03'). El escenario base es lo que va antes de '__'."""
    folder = metrics_dir()
    runs = []
    if not os.path.isdir(folder):
        return runs
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith('_interno.csv'):
            continue
        run_name = fname[:-len('_interno.csv')]
        parts = run_name.split('__', 1)
        base = parts[0]
        run_id = parts[1] if len(parts) > 1 else 'base'
        if base in SCENARIOS:
            runs.append((run_name, base, run_id))
    return runs


def main():
    # WINDOWS_DIR permite escribir un dataset nuevo sin pisar el anterior.
    out_dir = os.path.join(processed_dir(), os.environ.get('WINDOWS_DIR', 'ventanas'))
    os.makedirs(out_dir, exist_ok=True)

    runs = discover_runs()
    if not runs:
        print('No habia *_interno.csv en %s. Corre antes un escenario.' % metrics_dir())
        return

    combined = []
    sdn_seen = False
    n_runs = len({rid for _n, _b, rid in runs})
    print('*** %d archivos de escenario, %d corridas distintas' % (len(runs), n_runs))
    for run_name, base, run_id in runs:
        rows = build_run(run_name, base, run_id)
        if not rows:
            continue
        if any(r['sdn_flows_total'] for r in rows):
            sdn_seen = True
        write_csv(os.path.join(out_dir, '%s.csv' % run_name), rows)
        n_attack = sum(1 for r in rows if r['Label'] != 'BENIGN')
        print('    %-20s %3d ventanas (%d BENIGN, %d %s)'
              % (run_name, len(rows), len(rows) - n_attack, n_attack,
                 'ataque' if n_attack else '-'))
        combined.extend(rows)

    if not combined:
        print('No habia metricas en %s. Corre antes un escenario.' % metrics_dir())
        return

    write_csv(os.path.join(out_dir, 'ventanas.csv'), combined)
    print('\n%d ventanas en total -> %s' % (len(combined), os.path.join(out_dir, 'ventanas.csv')))
    if not sdn_seen:
        print('Nota: ninguna ventana trae telemetria SDN (columnas sdn_* en 0).')
        print('      Vuelve a correr los escenarios con el controlador nuevo')
        print('      (flow_monitor_13) y estas columnas se llenan solas.')


if __name__ == '__main__':
    main()
