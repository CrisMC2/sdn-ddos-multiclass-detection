#!/usr/bin/env python3
"""Anonimiza pcap Wireshark de estudiantes y extrae flujos BENIGN.

Uso, desde la raiz del repo:
    .venv/bin/python scripts/analysis/ingest_wireshark.py
    .venv/bin/python scripts/analysis/ingest_wireshark.py data/real/wireshark/aula.pcapng

Lee *.pcap / *.pcapng en data/real/wireshark/, remapea IP a 10.6.0.x,
escribe el pcap anonimo en data/real/anonimizado/ y un CSV de flujos
BENIGN en data/processed/hibrido/.

No lanza ataques. Solo procesa archivos ya capturados.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "mininet"))

WIRE = ROOT / "data" / "real" / "wireshark"
ANON = ROOT / "data" / "real" / "anonimizado"
OUT = ROOT / "data" / "processed" / "hibrido"
META_OUT = OUT / "benign_real.meta.json"
REAL_PREFIX = "10.6.0"
REAL_LAB = "10.6"


def _need(msg):
    raise SystemExit(msg)


def list_pcaps(paths):
    found = []
    if paths:
        for p in paths:
            path = Path(p)
            if not path.is_file():
                _need("No existe: %s" % path)
            found.append(path)
        return found
    if not WIRE.is_dir():
        _need("Crea %s y deja ahi los .pcap / .pcapng del encargado." % WIRE)
    for path in sorted(WIRE.iterdir()):
        if path.suffix.lower() in (".pcap", ".pcapng"):
            found.append(path)
    if not found:
        _need(
            "No hay capturas en %s.\n"
            "Copia ahi el .pcap que te dio el encargado y vuelve a correr."
            % WIRE
        )
    return found


def remap_ip(ip, cache):
    if ip in cache:
        return cache[ip]
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    host = 10 + (int(digest[:6], 16) % 200)
    mapped = "%s.%d" % (REAL_PREFIX, host)
    cache[ip] = mapped
    return mapped


def _strip_app_payload(pkt):
    from scapy.all import Raw

    layer = pkt
    while layer is not None:
        nxt = getattr(layer, "payload", None)
        if nxt is None:
            break
        if isinstance(nxt, Raw) or getattr(nxt, "name", "") == "Raw":
            layer.remove_payload()
            break
        layer = nxt


def anonymize(pcap_in: Path, pcap_out: Path):
    try:
        from scapy.all import Ether, IP, PcapWriter, rdpcap
    except ImportError as exc:
        _need("Falta scapy en este Python (%s). Usa el venv del proyecto." % exc)

    packets = rdpcap(str(pcap_in))
    cache = {}
    kept = 0
    writer = PcapWriter(str(pcap_out), sync=True)
    try:
        for pkt in packets:
            if IP not in pkt:
                continue
            new = pkt.copy()
            src = remap_ip(new[IP].src, cache)
            dst = remap_ip(new[IP].dst, cache)
            new[IP].src = src
            new[IP].dst = dst
            if Ether in new:
                new[Ether].src = "02:00:00:00:06:%02x" % (int(src.split(".")[-1]) % 256)
                new[Ether].dst = "02:00:00:00:00:0a"
            _strip_app_payload(new)
            new[IP].chksum = None
            new[IP].len = None
            writer.write(new)
            kept += 1
    finally:
        writer.close()
    return kept, cache


def flows_from_pcap(pcap_path: Path, csv_path: Path):
    from pcap_to_csv import convert_icmp, convert_tcp_udp, read_dicts, write_labeled

    tcp_csv = "/tmp/real_tcp.csv"
    icmp_csv = "/tmp/real_icmp.csv"
    for path in (tcp_csv, icmp_csv):
        if os.path.isfile(path):
            os.remove(path)
    try:
        convert_tcp_udp(str(pcap_path), tcp_csv)
    except Exception as exc:
        print("  CICFlowMeter aviso:", exc)
    try:
        convert_icmp(str(pcap_path), icmp_csv)
    except Exception as exc:
        print("  ICMP aviso:", exc)
    rows = read_dicts(tcp_csv) + read_dicts(icmp_csv)
    meta = {
        "scenario": "benign_real",
        "students": [],
        "bots": [],
        "source": "wireshark",
        "lab": REAL_LAB,
    }
    n = write_labeled(rows, str(csv_path), meta, "BENIGN")
    return n, meta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    pcaps = list_pcaps(args)
    ANON.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    all_rows = []
    map_total = {}
    resumen = []

    for pcap in pcaps:
        anon_path = ANON / (pcap.stem + ".anon.pcap")
        print("*** Anonimizando", pcap.name, "->", anon_path.name)
        kept, cache = anonymize(pcap, anon_path)
        map_total.update(cache)
        print("    paquetes IP:", kept, "hosts remapeados:", len(cache))
        csv_path = OUT / ("benign_real_%s.csv" % pcap.stem)
        n, meta = flows_from_pcap(anon_path, csv_path)
        print("    flujos BENIGN:", n)
        resumen.append({
            "archivo": pcap.name,
            "paquetes_ip": kept,
            "flujos": n,
            "csv": csv_path.name,
        })
        with csv_path.open(newline="") as fh:
            all_rows.extend(list(csv.DictReader(fh)))

    merged = OUT / "benign_real.csv"
    if all_rows:
        header = list(all_rows[0].keys())
        if "Label" not in header:
            header.append("Label")
        with merged.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
            writer.writeheader()
            for row in all_rows:
                item = dict(row)
                item["Label"] = "BENIGN"
                writer.writerow(item)

    meta = {
        "scenario": "benign_real",
        "lab": REAL_LAB,
        "prefix": REAL_PREFIX,
        "archivos": resumen,
        "hosts_anonimos": len(map_total),
        "flujos_total": len(all_rows),
        "nota": "Las IP reales no se publican. El mapa IP no se guarda a proposito.",
    }
    META_OUT.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (ANON / "resumen_anonimizacion.json").write_text(
        json.dumps({"archivos": resumen, "hosts": len(map_total)}, indent=2),
        encoding="utf-8",
    )
    print("\nListo.")
    print("  CSV unido:", merged if all_rows else "(sin flujos)")
    print("  Meta:", META_OUT)
    if not all_rows:
        _need("No se extrajo ningun flujo. Revisa que el pcap tenga trafico IP.")


if __name__ == "__main__":
    main()
