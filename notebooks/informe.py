#!/usr/bin/env python3
"""Escribe el informe que se lee y la tabla que entra al articulo.

No entrena nada. Lee notebooks/resultados/que_se_detecta.csv, el reporte
del modelo y data/metrics/resumen.csv. Esos archivos los deja el cuaderno.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTADOS = ROOT / "notebooks" / "resultados"
PAPER = ROOT / "paper"
DETECCION = RESULTADOS / "que_se_detecta.csv"
REPORTE = RESULTADOS / "reporte_clases.csv"
RESUMEN = ROOT / "data" / "metrics" / "resumen.csv"

PAGINA_EN = {
    "es el tráfico de referencia": "reference traffic",
    "es el trafico de referencia": "reference traffic",
    "la pagina tarda mas; suben los paquetes al portal": "the page slows down; packet rate rises",
    "suben los paquetes al portal": "packet rate at the portal rises",
    "la pagina deja de abrir": "the page stops opening",
}
FLUJO_EN = {
    "se distingue bien": "separated",
    "se distingue en parte": "partly separated",
    "hay muy pocos flujos para afirmarlo": "too few flows to claim",
    "no queda bien separado": "not separated",
}


def read_csv(path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def f1_macro():
    with REPORTE.open(newline="") as fh:
        reader = csv.reader(fh)
        next(reader)
        for cells in reader:
            if cells and cells[0].strip() == "macro avg":
                return cells[3]
    raise SystemExit("No esta el F1 macro en %s. Corre el cuaderno." % REPORTE)


def tex_escape(text):
    return (
        text.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def num(value):
    return "%.3f" % float(value)


def comma(value):
    return num(value).replace(".", ",")


def main():
    if not DETECCION.is_file():
        raise SystemExit(
            "Falta %s. Primero corre el cuaderno de deteccion." % DETECCION
        )
    macro = f1_macro()
    resumen = read_csv(RESUMEN) if RESUMEN.is_file() else []
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    PAPER.mkdir(parents=True, exist_ok=True)

    # La primera columna del CSV no tiene nombre: es la clase.
    with DETECCION.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        registros = []
        for cells in reader:
            item = dict(zip(header, cells))
            item["clase"] = cells[0]
            registros.append(item)

    lineas = [
        "Informe para analizar",
        "",
        "Esto sale de las capturas ya convertidas en data/processed.",
        "Tu navegador (10.9.0.1) no esta en ese entrenamiento.",
        "Para meterlo hay que recapturar: bash scripts/docker/preparar_analisis.sh --capturar",
        "",
        "Como se probo",
        "  Modelo: bosque aleatorio, clases equilibradas.",
        "  No usa IP, puertos ni marca de tiempo.",
        "  Entrena: Salud, Ingenierias, Administracion, Sociales.",
        "  Prueba: Ciencias Agrarias.",
        "  F1 macro: %s." % num(macro),
        "",
        "Clase        Precision  Recall  F1     Flujos  En el flujo | En la pagina",
    ]
    for row in registros:
        lineas.append(
            "%-12s %8s  %6s  %5s  %6.0f  %s | %s"
            % (
                row["clase"],
                num(row["precision"]),
                num(row["recall"]),
                num(row["f1-score"]),
                float(row["support"]),
                row["en_el_flujo"],
                row["en_la_pagina"],
            )
        )
    lineas.extend([
        "",
        "Sonda del portal (tasas, no conteos). El baseline de esta tabla dura 30 s; los ataques, 120 s.",
    ])
    if resumen:
        lineas.append("Escenario   Abrio  Latencia_ms  Paquetes/s")
        for row in resumen:
            samples = float(row["samples"] or 0)
            ok = float(row["http_200"] or 0) / samples if samples else 0
            lineas.append(
                "%-10s  %5.0f%%  %11s  %10s"
                % (
                    row["scenario"],
                    100 * ok,
                    row["latency_ms_avg"],
                    row["server_rx_pps_avg"],
                )
            )
    lineas.extend([
        "",
        "Que se puede afirmar",
        "  BENIGN, httpflood, slowloris y synflood se separan en un laboratorio no visto.",
        "  Slowloris es el que deja la pagina sin abrir.",
        "  HTTP flood no la tumba: la vuelve mas lenta y sube los paquetes.",
        "  SYN flood e ICMP flood suben los paquetes y la pagina sigue respondiendo.",
        "",
        "Que no se puede afirmar",
        "  icmpflood: en la prueba hay 2 flujos. El acierto no alcanza.",
        "  El modelo no vio tu navegador. Esta lectura es del alumno emulado.",
        "  No es deteccion en vivo dentro de Ryu. Clasifica flujos ya capturados.",
        "",
        "Figuras: notebooks/resultados/matriz.png, matriz_binaria.png, importancia.png",
    ])
    informe = RESULTADOS / "informe.txt"
    informe.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    (PAPER / "numeros.tex").write_text(
        "\\newcommand{\\Fmacro}{%s}\n\\newcommand{\\FmacroEs}{%s}\n" % (num(macro), comma(macro)),
        encoding="utf-8",
    )

    def tabla(path, titulo, pagina, flujo, caption):
        body = [
            "\\begin{table}[t]",
            "\\centering",
            "\\small",
            "\\caption{%s}" % caption,
            "\\label{tbl:deteccion}",
            "\\begin{tabular}{lrrrrl}",
            "\\hline",
            "Clase & Prec. & Recall & F1 & Flujos & %s \\\\" % flujo,
            "\\hline",
        ]
        for row in registros:
            lectura = row["en_el_flujo"]
            if path.name.endswith("_en.tex"):
                lectura = FLUJO_EN.get(lectura, lectura)
                efecto = PAGINA_EN.get(row["en_la_pagina"], row["en_la_pagina"])
                prec, rec, f1 = num(row["precision"]), num(row["recall"]), num(row["f1-score"])
            else:
                efecto = row["en_la_pagina"]
                prec, rec, f1 = comma(row["precision"]), comma(row["recall"]), comma(row["f1-score"])
            body.append(
                "%s & %s & %s & %s & %.0f & %s \\\\"
                % (tex_escape(row["clase"]), prec, rec, f1, float(row["support"]), tex_escape(lectura))
            )
        body.extend([
            "\\hline",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ])
        # efecto is unused in the compact table; the prose carries the page effect.
        del titulo, pagina, efecto
        path.write_text("\n".join(body), encoding="utf-8")

    tabla(
        PAPER / "tabla_resultados.tex",
        "es",
        "pagina",
        "En el flujo",
        "Detecci\\'on en Ciencias Agrarias, laboratorio excluido del entrenamiento. F1 macro \\FmacroEs.",
    )
    tabla(
        PAPER / "tabla_resultados_en.tex",
        "en",
        "page",
        "On the flow",
        "Detection on Ciencias Agrarias, the laboratory held out of training. Macro F1 \\Fmacro.",
    )

    frases = []
    for row in registros:
        if row["clase"] == "BENIGN":
            continue
        frases.append("%s: %s" % (row["clase"], row["en_la_pagina"]))
    (PAPER / "frase_es.tex").write_text(
        "En la sonda del portal, " + "; ".join(frases) + ".\n",
        encoding="utf-8",
    )
    frases_en = []
    for row in registros:
        if row["clase"] == "BENIGN":
            continue
        frases_en.append("%s: %s" % (row["clase"], PAGINA_EN.get(row["en_la_pagina"], row["en_la_pagina"])))
    (PAPER / "frase_en.tex").write_text(
        "On the portal probe, " + "; ".join(frases_en) + ".\n",
        encoding="utf-8",
    )
    print(informe)


if __name__ == "__main__":
    main()
