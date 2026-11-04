"""Leer lo que una corrida va dejando en data/: meta.json, metricas por segundo
y la lista de archivos generados."""
import csv
import re
import json

from .config import DATA_DIR


def read_meta(run_name):
    path = DATA_DIR / 'raw' / ('%s.meta.json' % run_name)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def tail_csv(path, n=120):
    if not path.is_file():
        return []
    try:
        with open(path, newline='', encoding='utf-8', errors='replace') as fh:
            rows = list(csv.DictReader(fh))
        return rows[-n:]
    except (OSError, csv.Error):
        return []


def metrics_rows(run_name, n=400):
    return tail_csv(DATA_DIR / 'metrics' / ('%s_interno.csv' % run_name), n=n)


def output_files(run_name):
    """Lo que dejo la corrida en disco, para mostrarlo al terminar."""
    candidatos = (
        DATA_DIR / 'raw' / ('%s.pcap' % run_name),
        DATA_DIR / 'raw' / ('%s.meta.json' % run_name),
        DATA_DIR / 'metrics' / ('%s_interno.csv' % run_name),
        DATA_DIR / 'metrics' / ('%s_sdn.csv' % run_name),
        DATA_DIR / 'metrics' / ('%s_docker.csv' % run_name),
    )
    return [{'nombre': p.name, 'carpeta': 'data/%s' % p.parent.name, 'bytes': p.stat().st_size}
            for p in candidatos if p.is_file()]


def remove_metric(run_name, suffix):
    try:
        (DATA_DIR / 'metrics' / ('%s%s' % (run_name, suffix))).unlink()
    except OSError:
        pass


_UNIDADES_MIB = {'kib': 1 / 1024, 'kb': 1 / 1024, 'mib': 1.0, 'mb': 1.0, 'gib': 1024.0, 'gb': 1024.0, 'b': 1 / (1024 * 1024)}


def _a_mib(texto):
    """'43.18MiB' / '1.2GiB' -> MiB (float) o None."""
    m = re.match(r'\s*([\d.]+)\s*([A-Za-z]+)', texto or '')
    if not m:
        return None
    factor = _UNIDADES_MIB.get(m.group(2).lower())
    return float(m.group(1)) * factor if factor is not None else None


def resource_rows(run_name, t0, t_max=None):
    """CPU y memoria del contenedor (docker stats, ~1 muestra cada 3 s) con el
    tiempo en segundos desde t0 (inicio de la medicion), para alinearlo con las
    demas graficas. Se descarta lo anterior a t0 (arranque de la red) y lo
    posterior a t_max (apagado de la red): no son parte de la medicion."""
    path = DATA_DIR / 'metrics' / ('%s_docker.csv' % run_name)
    if not path.is_file() or t0 is None:
        return []
    out = []
    try:
        with open(path, newline='', encoding='utf-8', errors='replace') as fh:
            for r in csv.DictReader(fh):
                try:
                    t = float(r['timestamp']) - t0
                    cpu = float((r.get('cpu') or '').strip().rstrip('%'))
                except (KeyError, ValueError):
                    continue
                mem = _a_mib((r.get('mem') or '').split('/')[0])
                if t >= 0 and (t_max is None or t <= t_max) and mem is not None:
                    out.append({'t': round(t, 1), 'cpu': cpu, 'mem': round(mem, 1)})
    except (OSError, csv.Error):
        return []
    return out
