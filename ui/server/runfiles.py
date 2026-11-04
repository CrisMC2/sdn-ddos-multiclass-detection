"""Leer lo que una corrida va dejando en data/: meta.json, metricas por segundo
y la lista de archivos generados."""
import csv
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
