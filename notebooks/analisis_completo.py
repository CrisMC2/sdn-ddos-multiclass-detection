#!/usr/bin/env python3
"""Analisis ML completo: simulacion sola y, si existe, dataset hibrido.

Escribe:
  notebooks/resultados/informe.txt
  notebooks/resultados/informe_hibrido.txt   (si hay hibrido)
  notebooks/resultados/comparacion.txt
  paper/numeros.tex y tablas
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
HIBRIDO = PROC / "hibrido" / "dataset_hibrido.csv"
METRICS = ROOT / "data" / "metrics" / "resumen.csv"
OUT = ROOT / "notebooks" / "resultados"
PAPER = ROOT / "paper"
OUT.mkdir(parents=True, exist_ok=True)

LABS = {
    "10.1": "Salud",
    "10.2": "Ingenierias",
    "10.3": "Administracion",
    "10.4": "Sociales",
    "10.5": "Agrarias",
    "10.6": "Wireshark_real",
}
HOLDOUT = "10.5"
IDENTIDAD = ["src_ip", "dst_ip", "src_port", "dst_port", "timestamp", "fuente"]
ORDEN = ["BENIGN", "httpflood", "icmpflood", "slowloris", "synflood"]


def lab_of(ip: str) -> str:
    if not isinstance(ip, str):
        return ""
    parts = ip.split(".")
    if len(parts) >= 2 and parts[0] == "10":
        return "%s.%s" % (parts[0], parts[1])
    return ""


def load_simulacion() -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in sorted(PROC.glob("*.csv"))]
    raw = pd.concat(frames, ignore_index=True)
    raw["lab"] = raw["src_ip"].map(lab_of)
    raw["fuente"] = "simulacion"
    return raw[raw["lab"].isin(LABS)].copy()


def load_hibrido() -> pd.DataFrame | None:
    if not HIBRIDO.is_file():
        return None
    raw = pd.read_csv(HIBRIDO)
    raw["lab"] = raw["src_ip"].map(lab_of)
    if "fuente" not in raw.columns:
        raw["fuente"] = "hibrido"
    return raw[raw["lab"].isin(LABS) | (raw["Label"] == "BENIGN")].copy()


def features_xy(df: pd.DataFrame):
    trabajo = df.copy()
    cols = [c for c in trabajo.columns if c not in IDENTIDAD + ["Label", "lab"]]
    X = trabajo[cols].apply(pd.to_numeric, errors="coerce")
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    y = trabajo["Label"]
    lab = trabajo["lab"]
    return X, y, lab


def train_eval(df: pd.DataFrame, holdout: str, tag: str):
    X, y, lab = features_xy(df)
    # Si el holdout no tiene filas (p.ej. solo wireshark), usa 20% estratificado.
    if holdout and (lab == holdout).any() and (lab != holdout).any():
        entrenar = lab != holdout
        probar = lab == holdout
        modo = "holdout_%s" % holdout
    else:
        from sklearn.model_selection import train_test_split

        idx = np.arange(len(df))
        tr, te = train_test_split(idx, test_size=0.2, random_state=42, stratify=y)
        entrenar = np.zeros(len(df), dtype=bool)
        probar = np.zeros(len(df), dtype=bool)
        entrenar[tr] = True
        probar[te] = True
        modo = "split_20"

    X_train, X_test = X.loc[entrenar], X.loc[probar]
    y_train, y_test = y.loc[entrenar], y.loc[probar]
    vary = [c for c in X_train.columns if X_train[c].nunique() > 1]
    X_train, X_test = X_train[vary], X_test[vary]

    modelo = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    modelo.fit(X_train, y_train)
    pred = modelo.predict(X_test)
    macro = f1_score(y_test, pred, average="macro", zero_division=0)
    reporte = pd.DataFrame(
        classification_report(y_test, pred, zero_division=0, output_dict=True)
    ).T
    reporte.to_csv(OUT / ("reporte_%s.csv" % tag))

    labels = [c for c in ORDEN if c in set(y_test) or c in set(pred)]
    matriz = confusion_matrix(y_test, pred, labels=labels)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(matriz, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicho")
    ax.set_ylabel("Real")
    ax.set_title("Matriz %s (%s)" % (tag, modo))
    for i in range(matriz.shape[0]):
        for j in range(matriz.shape[1]):
            ax.text(j, i, str(matriz[i, j]), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(OUT / ("matriz_%s.png" % tag))
    plt.close(fig)

    # Binario
    y_bin_test = np.where(y_test == "BENIGN", "BENIGN", "ATAQUE")
    pred_bin = np.where(pred == "BENIGN", "BENIGN", "ATAQUE")
    f1_bin = f1_score(y_bin_test, pred_bin, average="macro", zero_division=0)

    return {
        "tag": tag,
        "modo": modo,
        "macro": float(macro),
        "f1_bin": float(f1_bin),
        "n_train": int(entrenar.sum() if hasattr(entrenar, "sum") else sum(entrenar)),
        "n_test": int(probar.sum() if hasattr(probar, "sum") else sum(probar)),
        "reporte": reporte,
        "y_test": y_test,
        "pred": pred,
        "importancias": pd.Series(modelo.feature_importances_, index=vary).sort_values(
            ascending=False
        ),
    }


def juicio_flujo(row):
    if float(row["support"]) < 30:
        return "hay muy pocos flujos para afirmarlo"
    if float(row["precision"]) >= 0.85 and float(row["recall"]) >= 0.85:
        return "se distingue bien"
    if float(row["f1-score"]) >= 0.6:
        return "se distingue en parte"
    return "no queda bien separado"


def pagina_map():
    if not METRICS.is_file():
        return {}
    resumen = pd.read_csv(METRICS)
    base = resumen.loc[resumen["scenario"] == "baseline"]
    out = {"BENIGN": "es el trafico de referencia"}
    if base.empty:
        return out
    b = base.iloc[0]
    for _, fila in resumen.iterrows():
        nombre = fila["scenario"]
        if nombre == "baseline":
            continue
        samples = float(fila["samples"] or 0)
        ok = float(fila["http_200"] or 0) / samples if samples else 0
        notas = []
        if ok < 0.5:
            notas.append("la pagina deja de abrir")
        elif float(fila["latency_ms_avg"] or 0) > float(b["latency_ms_avg"] or 0) * 1.2:
            notas.append("la pagina tarda mas")
        if float(fila["server_rx_pps_avg"] or 0) > float(b["server_rx_pps_avg"] or 0) * 1.5:
            notas.append("suben los paquetes al portal")
        out[nombre] = "; ".join(notas) if notas else "la pagina sigue parecida al baseline"
    return out


def write_informe(path: Path, result: dict, titulo: str, extras: list[str] | None = None):
    paginas = pagina_map()
    rep = result["reporte"]
    lineas = [
        titulo,
        "",
        "Modelo: bosque aleatorio (sin IP, sin puertos, sin timestamp).",
        "Particion: %s" % result["modo"],
        "Entrena: %d flujos. Prueba: %d flujos." % (result["n_train"], result["n_test"]),
        "F1 macro: %.3f" % result["macro"],
        "F1 binario (BENIGN vs ATAQUE): %.3f" % result["f1_bin"],
        "",
        "Clase        Precision  Recall  F1     Flujos  En el flujo | En la pagina",
    ]
    filas_det = []
    for clase in ORDEN:
        if clase not in rep.index:
            continue
        row = rep.loc[clase]
        flujo = juicio_flujo(row)
        pagina = paginas.get(clase, "sin sonda")
        lineas.append(
            "%-12s %8.3f  %6.3f  %5.3f  %6.0f  %s | %s"
            % (
                clase,
                float(row["precision"]),
                float(row["recall"]),
                float(row["f1-score"]),
                float(row["support"]),
                flujo,
                pagina,
            )
        )
        filas_det.append({
            "clase": clase,
            "precision": float(row["precision"]),
            "recall": float(row["recall"]),
            "f1-score": float(row["f1-score"]),
            "support": float(row["support"]),
            "en_el_flujo": flujo,
            "en_la_pagina": pagina,
        })
    pd.DataFrame(filas_det).to_csv(OUT / ("que_se_detecta_%s.csv" % result["tag"]), index=False)

    lineas.extend(["", "Columnas que mas pesan:"])
    for name, val in result["importancias"].head(8).items():
        lineas.append("  %.3f  %s" % (val, name))

    lineas.extend([
        "",
        "Que se puede afirmar",
        "  Las clases con 'se distingue bien' y support >= 30 son defendibles.",
        "  El detector no usa la IP: distingue comportamiento de flujo.",
        "",
        "Que no se puede afirmar",
        "  icmpflood si el support es bajo.",
        "  Deteccion en vivo dentro de Ryu (esto clasifica flujos ya capturados).",
    ])
    if extras:
        lineas.extend([""] + extras)
    path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return filas_det


def write_paper_bits(filas, macro):
    PAPER.mkdir(parents=True, exist_ok=True)
    (PAPER / "numeros.tex").write_text(
        "\\newcommand{\\Fmacro}{%.3f}\n\\newcommand{\\FmacroEs}{%s}\n"
        % (macro, ("%.3f" % macro).replace(".", ",")),
        encoding="utf-8",
    )
    body = [
        "\\begin{table}[t]",
        "\\centering",
        "\\small",
        "\\caption{Detecci\\'on (bosque aleatorio). F1 macro \\FmacroEs.}",
        "\\label{tbl:deteccion}",
        "\\begin{tabular}{lrrrrl}",
        "\\hline",
        "Clase & Prec. & Recall & F1 & Flujos & En el flujo \\\\",
        "\\hline",
    ]
    for row in filas:
        body.append(
            "%s & %s & %s & %s & %.0f & %s \\\\"
            % (
                row["clase"],
                ("%.3f" % row["precision"]).replace(".", ","),
                ("%.3f" % row["recall"]).replace(".", ","),
                ("%.3f" % row["f1-score"]).replace(".", ","),
                row["support"],
                row["en_el_flujo"].replace("_", "\\_"),
            )
        )
    body += ["\\hline", "\\end{tabular}", "\\end{table}", ""]
    (PAPER / "tabla_resultados.tex").write_text("\n".join(body), encoding="utf-8")


def main():
    print("=== 1) Simulacion sola ===")
    sim = load_simulacion()
    r_sim = train_eval(sim, HOLDOUT, "simulacion")
    filas = write_informe(
        OUT / "informe.txt",
        r_sim,
        "Informe de analisis — solo simulacion",
        extras=[
            "Mejoras siguientes (con permiso Wireshark):",
            "  1. Poner los .pcap del encargado en data/real/wireshark/",
            "  2. bash scripts/docker/preparar_hibrido.sh",
            "  3. Leer notebooks/resultados/informe_hibrido.txt",
            "  4. Comparar F1 simulación vs hibrido en comparacion.txt",
        ],
    )
    write_paper_bits(filas, r_sim["macro"])
    # Compatibilidad con informe.py / cuaderno anterior
    r_sim["reporte"].to_csv(OUT / "reporte_clases.csv")
    pd.DataFrame(filas).rename(columns={"clase": ""}).to_csv(OUT / "que_se_detecta.csv", index=False)

    print("F1 simulación:", round(r_sim["macro"], 3))

    print("=== 2) Hibrido (si hay Wireshark) ===")
    hib = load_hibrido()
    if hib is None or hib.empty:
        (OUT / "informe_hibrido.txt").write_text(
            "Aun no hay dataset hibrido.\n"
            "Copia los pcap Wireshark a data/real/wireshark/ y corre:\n"
            "  bash scripts/docker/preparar_hibrido.sh\n",
            encoding="utf-8",
        )
        (OUT / "comparacion.txt").write_text(
            "Comparacion\n\n"
            "Simulacion sola: F1 macro %.3f\n"
            "Hibrido: pendiente (sin pcap Wireshark).\n" % r_sim["macro"],
            encoding="utf-8",
        )
        print("Hibrido pendiente (sin pcap).")
        return

    # Holdout: prueba en Agrarias si hay; si el BENIGN real es 10.6,
    # tambien reportamos recall sobre ese laboratorio.
    r_hib = train_eval(hib, HOLDOUT, "hibrido")
    write_informe(
        OUT / "informe_hibrido.txt",
        r_hib,
        "Informe de analisis — hibrido (Wireshark + ataques simulados)",
        extras=[
            "BENIGN incluye trafico real anonimizado (prefijo 10.6) y/o baseline.",
            "Los ataques siguen siendo solo de la simulacion Docker.",
        ],
    )

    # Prueba especifica sobre flujos Wireshark si existen
    real = hib[hib["lab"] == "10.6"]
    extra = ""
    if len(real) >= 20:
        X, y, lab = features_xy(hib)
        # Reentrenar sin 10.6 y probar solo 10.6
        r_real = train_eval(hib, "10.6", "wireshark_holdout")
        extra = "Holdout Wireshark (10.6): F1 macro %.3f\n" % r_real["macro"]
        write_informe(
            OUT / "informe_wireshark_holdout.txt",
            r_real,
            "Prueba solo sobre trafico Wireshark anonimizado (lab 10.6)",
        )

    (OUT / "comparacion.txt").write_text(
        "Comparacion\n\n"
        "Simulacion sola: F1 macro %.3f (modo %s)\n"
        "Hibrido:         F1 macro %.3f (modo %s)\n"
        "%s"
        "\nLectura\n"
        "  Si el F1 hibrido se mantiene cerca del de simulacion, el patron\n"
        "  del ataque no depende solo de las cinco paginas falsas.\n"
        "  Si baja mucho, el detector memorizaba el alumno sintetico.\n"
        % (
            r_sim["macro"],
            r_sim["modo"],
            r_hib["macro"],
            r_hib["modo"],
            extra,
        ),
        encoding="utf-8",
    )
    print("F1 hibrido:", round(r_hib["macro"], 3))
    print("Listo en", OUT)


if __name__ == "__main__":
    main()
