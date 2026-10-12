#!/usr/bin/env python3
"""Arma el dataset hibrido: BENIGN real (Wireshark) + ataques de simulacion.

Uso:
    .venv/bin/python scripts/analysis/build_hybrid_dataset.py

Salida:
    data/processed/hibrido/dataset_hibrido.csv
    data/processed/hibrido/resumen_clases.csv
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = PROC / "hibrido"
ATTACKS = ("synflood", "httpflood", "slowloris", "icmpflood")
# Baseline sintetico: opcional, se incluye para no perder el alumno emulado.
INCLUDE_SYNTHETIC_BENIGN = True


def read_rows(path: Path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    fuentes = []

    real = OUT / "benign_real.csv"
    if real.is_file():
        chunk = read_rows(real)
        for row in chunk:
            row = dict(row)
            row["Label"] = "BENIGN"
            row["fuente"] = "wireshark"
            rows.append(row)
        fuentes.append(("wireshark_benign", len(chunk)))
    else:
        print("Aviso: no esta %s. El hibrido saldra solo con simulacion." % real)

    if INCLUDE_SYNTHETIC_BENIGN:
        base = PROC / "baseline.csv"
        if base.is_file():
            chunk = read_rows(base)
            for row in chunk:
                row = dict(row)
                row["Label"] = "BENIGN"
                row["fuente"] = "simulacion_baseline"
                rows.append(row)
            fuentes.append(("simulacion_baseline", len(chunk)))

    for name in ATTACKS:
        path = PROC / ("%s.csv" % name)
        if not path.is_file():
            print("Aviso: falta", path)
            continue
        chunk = read_rows(path)
        # Solo filas de ataque: el BENIGN del archivo de ataque ya esta
        # en baseline o se deja fuera para no mezclar dos veces.
        attack_rows = [r for r in chunk if r.get("Label") == name]
        for row in attack_rows:
            row = dict(row)
            row["fuente"] = "simulacion_ataque"
            rows.append(row)
        fuentes.append((name, len(attack_rows)))

    if not rows:
        raise SystemExit("No hay filas. Corre convert y/o ingest_wireshark primero.")

    # Union de columnas
    header = []
    for row in rows:
        for key in row:
            if key not in header:
                header.append(key)
    if "Label" not in header:
        header.append("Label")
    if "fuente" not in header:
        header.append("fuente")

    out = OUT / "dataset_hibrido.csv"
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(r.get("Label", "") for r in rows)
    resumen = OUT / "resumen_clases.csv"
    with resumen.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Label", "flujos"])
        for label, n in sorted(counts.items()):
            writer.writerow([label, n])

    print("Dataset hibrido:", out)
    print("Filas:", len(rows))
    for name, n in fuentes:
        print("  %s: %d" % (name, n))
    print("Por clase:")
    for label, n in sorted(counts.items()):
        print("  %s: %d" % (label, n))


if __name__ == "__main__":
    main()
