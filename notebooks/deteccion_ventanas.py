#!/usr/bin/env python3
"""Detector POR VENTANA: decide, segundo a segundo, si la red esta bajo
ataque y de que tipo. Es el paso de clasificar flujos terminados a
detectar mientras pasa.

Entrada:
  data/processed/ventanas/ventanas.csv   (lo arma build_windows.py)

Evaluacion honesta, pensada para deteccion temprana y para defender la tesis:

  - VALIDACION CRUZADA POR CORRIDA (leave-one-run-out) cuando hay varias
    corridas: cada corrida se usa una vez como prueba y el resto entrena.
    Se reporta MEDIA +/- DESVIACION, no un numero de una sola corrida.
    Con una sola corrida cae a una particion temporal 70/30.
  - ABLACION DE FEATURES: entrena con solo-red, solo-SDN y todas, para
    ver cuanto aporta de verdad la vista SDN del controlador.
  - COMPARACION DE MODELOS: bosque aleatorio, gradient boosting y
    regresion logistica, como referencia.
  - Metricas operativas: F1 macro, F1 binario (BENIGN vs ATAQUE), tasa de
    falsos positivos sobre benigno y retardo de deteccion (segundos entre
    el inicio real del ataque y la primera alarma).
  - SEPARABILIDAD: un arbol de 3 niveles. Si eso ya da ~1,0 el escenario
    es facil y el F1 alto habla del simulador, no del modelo.
  - BRECHA ENTRENAMIENTO - PRUEBA (sobreajuste clasico).
  - GENERALIZACION A ATAQUES DIFICILES (si hay corridas con perfil, ver
    run_scenario.sh dificil): entrena con 'normal' y prueba cada perfil, y
    deja un perfil entero fuera. Ese es el numero defendible.

Entrada extra (opcional): data/processed/ventanas_dificil/ventanas.csv, o
las carpetas de VENTANAS_EXTRA=dir1,dir2 bajo data/processed/.

Salida:
  notebooks/resultados/ventanas/informe.txt
  notebooks/resultados/ventanas/matriz.png
  notebooks/resultados/ventanas/cv_por_corrida.csv
  notebooks/resultados/ventanas/generalizacion.csv   (si hay perfiles)
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "ventanas" / "ventanas.csv"
OUT = ROOT / "notebooks" / "resultados" / "ventanas"

EXTRA = [
    ROOT / "data" / "processed" / d.strip() / "ventanas.csv"
    for d in os.environ.get("VENTANAS_EXTRA", "ventanas_dificil").split(",") if d.strip()
]
# VENTANAS=dir1,dir2 reemplaza todo lo anterior: evalua solo esos datasets
# (carpetas bajo data/processed/). Sirve para evaluar una campana generada en
# una sola maquina sin mezclarla con otra (la escala de las sdn_* cambia
# entre el datapath de kernel y el de userspace).
if os.environ.get("VENTANAS", "").strip():
    _dirs = [d.strip() for d in os.environ["VENTANAS"].split(",") if d.strip()]
    DATA = ROOT / "data" / "processed" / _dirs[0] / "ventanas.csv"
    EXTRA = [ROOT / "data" / "processed" / d / "ventanas.csv" for d in _dirs[1:]]
    OUT = ROOT / "notebooks" / "resultados" / _dirs[0]

REF_FIELDS = ["timestamp", "elapsed_s", "scenario", "run", "profile"]
TRAIN_FRACTION = 0.70
# Se rellena en main() con las clases que haya: BENIGN primero.
ORDEN = ["BENIGN", "httpflood", "icmpflood", "slowloris", "synflood"]
# Si un arbol de esta profundidad ya da un F1 macro >= UMBRAL_FACIL, las
# clases se separan con un punado de umbrales: el escenario es facil.
PROF_SEPARABILIDAD = 3
UMBRAL_FACIL = 0.98


def _escenarios_base():
    """Escenarios del conjunto base (scenarios.txt sin la marca 'extra'): con
    estos se entrena. Los 'extra' (udpflood, ackflood, slowpost, multivector)
    se guardan como ATAQUES NUNCA VISTOS y solo se usan para probar."""
    path = ROOT / "scripts" / "mininet" / "scenarios.txt"
    base = []
    try:
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "extra" not in ln.split()[1:]:
                base.append(ln.split()[0])
    except OSError:
        pass
    return tuple(base) or ("baseline", "synflood", "httpflood", "slowloris", "icmpflood")


ESCENARIOS_BASE = _escenarios_base()

# --------------------------------------------------------------------------
# Features RELATIVAS: cada volumen comparado con la linea base de la propia
# corrida, en vez del numero absoluto. Un detector con valores absolutos
# aprende "mas de 16 726 B/s es ataque", umbral que depende de cuantos
# alumnos haya en ESE simulador; uno relativo aprende "el trafico subio 3x
# sobre lo normal de esta red", que se traslada a otra red o a otra carga.
#
# Linea base = mediana de las ventanas de calibracion (elapsed_s <= CALIB_S)
# de la misma corrida. Requiere que el ataque arranque despues de CALIB_S
# (todas las corridas tienen ONSET_S = 30). Es causal: solo usa el pasado.
# rel_x = log(1 + x) - log(1 + mediana): 0 = como siempre, +1.1 = 3x mas.
# --------------------------------------------------------------------------
CALIB_S = 20
REL_BASE = [
    "server_rx_pps", "server_rx_bps", "server_conns", "probe_latency_ms",
    "rx_pps_roll3", "conns_roll3", "sdn_core_flows", "sdn_flows_total",
    "sdn_src_total", "sdn_delta_pkts", "sdn_delta_bytes", "sdn_mean_pkts_per_flow",
    "sdn_pkts_tcp", "sdn_pkts_icmp", "sdn_pkts_udp",
    "sdn_pkts_icmp_roll", "sdn_pkts_udp_roll",
]
# Ya son proporciones o 0/1: no dependen de la escala de la red.
SIN_ESCALA = [
    "http_ok", "sdn_src_entropy_norm", "sdn_max_src_share",
    "sdn_frac_icmp", "sdn_frac_tcp", "sdn_frac_udp",
    "sdn_frac_icmp_roll", "sdn_frac_udp_roll",
]
# Conjuntos de features que se comparan en generalizacion y ataques nuevos.
CONJUNTOS = ("todas", "relativas")


def modelos():
    return {
        "bosque": RandomForestClassifier(
            n_estimators=200, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=42),
        "regresion_logistica": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced"),
        ),
    }


# --------------------------------------------------------------------------
# Particiones.
# --------------------------------------------------------------------------

def folds(df: pd.DataFrame):
    """Lista de (train_idx, test_idx, nombre). Con >=2 corridas: deja una
    corrida completa fuera por vez. Con una sola: particion temporal."""
    runs = sorted(df["run"].unique()) if "run" in df.columns else []
    if len(runs) >= 2:
        salida = []
        for holdout in runs:
            tr = sorted(df.index[df["run"] != holdout])
            te = sorted(df.index[df["run"] == holdout])
            # Solo sirve si el entrenamiento tiene mas de una clase.
            if df.loc[tr, "Label"].nunique() > 1 and te:
                salida.append((tr, te, holdout))
        return salida, "leave-one-run-out (%d corridas)" % len(runs)
    # Una sola corrida: primer 70 % de cada escenario entrena, resto prueba.
    tr, te = [], []
    for _s, grupo in df.groupby("scenario", sort=False):
        grupo = grupo.sort_values("timestamp")
        corte = int(len(grupo) * TRAIN_FRACTION)
        tr.extend(grupo.index[:corte])
        te.extend(grupo.index[corte:])
    return [(sorted(tr), sorted(te), "temporal")], "particion temporal 70/30 (1 corrida)"


# --------------------------------------------------------------------------
# Features y grupos para la ablacion.
# --------------------------------------------------------------------------

def feature_cols(df: pd.DataFrame):
    """Features absolutas (las rel_* van en su propio grupo)."""
    return [c for c in df.columns
            if c not in REF_FIELDS + ["Label"] and not c.startswith("rel_")]


def agrega_relativas(df: pd.DataFrame):
    """Agrega rel_<x> para cada x de REL_BASE (ver CALIB_S). Devuelve las
    columnas nuevas."""
    base = [c for c in REL_BASE if c in df.columns]
    nuevas = ["rel_" + c for c in base]
    if not base:
        return []
    X = df[base].apply(pd.to_numeric, errors="coerce").fillna(0).clip(lower=0)
    logx = np.log1p(X)
    rel = pd.DataFrame(0.0, index=df.index, columns=nuevas)
    for _k, g in df.groupby(["run", "scenario"], sort=False):
        calib = g.index[g["elapsed_s"] <= CALIB_S]
        if not len(calib):
            calib = g.sort_values("elapsed_s").index[:10]
        med = logx.loc[calib].median()
        rel.loc[g.index] = (logx.loc[g.index] - med).to_numpy()
    df[nuevas] = rel
    return nuevas


def grupos_de_features(cols):
    sdn = [c for c in cols if c.startswith("sdn_")]
    red = [c for c in cols if not c.startswith("sdn_")]
    g = {"red": red, "todas": cols}
    if sdn:
        g["sdn"] = sdn
    return g


def matriz_numerica(df: pd.DataFrame, cols):
    X = df.reindex(columns=cols).apply(pd.to_numeric, errors="coerce")
    return X.replace([np.inf, -np.inf], np.nan).fillna(0)


# --------------------------------------------------------------------------
# Metricas.
# --------------------------------------------------------------------------

def first_alarm(df_test: pd.DataFrame, yt: pd.Series, pred: pd.Series):
    """Retardo de deteccion por corrida de ataque: segundos entre la primera
    ventana que de verdad es ataque (etiqueta) y la primera ventana, desde
    ahi, que el modelo marca como ataque. None si nunca sono.
    Devuelve {escenario: [retardo por corrida, ...]}."""
    out = {}
    for (_run, scenario), grupo in df_test.groupby(["run", "scenario"], sort=False):
        if scenario == "baseline":
            continue
        g = grupo.sort_values("elapsed_s")
        reales = g.index[yt.loc[g.index] != "BENIGN"]
        if not len(reales):
            continue
        t0 = int(g.loc[reales[0], "elapsed_s"])
        alarmas = [i for i in g.index
                   if int(g.loc[i, "elapsed_s"]) >= t0 and pred.loc[i] != "BENIGN"]
        retardo = int(g.loc[alarmas[0], "elapsed_s"]) - t0 if alarmas else None
        out.setdefault(scenario, []).append(retardo)
    return out


def evalua_fold(df, X, y, tr, te, model):
    # Quita columnas constantes en el entrenamiento de ESTE fold.
    vary = [c for c in X.columns if X.loc[tr, c].nunique() > 1]
    if not vary:
        return None
    model.fit(X.loc[tr, vary], y.loc[tr])
    pred = pd.Series(model.predict(X.loc[te, vary]), index=te)
    macro_train = f1_score(y.loc[tr], model.predict(X.loc[tr, vary]),
                           average="macro", zero_division=0)
    yt = y.loc[te]

    macro = f1_score(yt, pred, average="macro", zero_division=0)
    y_bin = np.where(yt == "BENIGN", "BENIGN", "ATAQUE")
    p_bin = np.where(pred == "BENIGN", "BENIGN", "ATAQUE")
    f1_bin = f1_score(y_bin, p_bin, average="macro", zero_division=0)
    benignas = (yt == "BENIGN").to_numpy()
    n_ben = int(benignas.sum())
    fp = int(((pred.to_numpy() != "BENIGN") & benignas).sum())
    fpr = fp / n_ben if n_ben else 0.0

    recalls = {}
    for clase in ORDEN:
        if (yt == clase).any():
            recalls[clase] = recall_score(yt, pred, labels=[clase], average="macro", zero_division=0)

    alarmas = first_alarm(df.loc[te], yt, pred)
    return {
        "macro": macro, "macro_train": macro_train, "f1_bin": f1_bin, "fpr": fpr,
        "recalls": recalls, "alarmas": alarmas,
        "n_vary": len(vary), "yt": yt, "pred": pred,
    }


def corre_cv(df, y, cols, model_factory, particiones):
    Xm = matriz_numerica(df, cols)
    folds_metricas = []
    for tr, te, _name in particiones:
        res = evalua_fold(df, Xm, y, tr, te, model_factory())
        if res is not None:
            folds_metricas.append(res)
    return folds_metricas


def media_std(valores):
    if not valores:
        return (float("nan"), float("nan"))
    return (float(np.mean(valores)), float(np.std(valores)))


def cargar():
    """ventanas.csv + los datasets extra (ataques dificiles). Las corridas que
    aparezcan en los dos (misma corrida armada dos veces) se quedan una vez."""
    partes = [pd.read_csv(DATA)]
    fuentes = [DATA]
    for path in EXTRA:
        if path.is_file():
            partes.append(pd.read_csv(path))
            fuentes.append(path)
    df = pd.concat(partes, ignore_index=True, sort=False)
    if "profile" not in df.columns:
        df["profile"] = "normal"
    df["profile"] = df["profile"].fillna("normal").astype(str)
    df["run"] = df["run"].astype(str)
    df = df.drop_duplicates(subset=["scenario", "run", "elapsed_s"], keep="last")
    return df.reset_index(drop=True), fuentes


def retardos_txt(lista_alarmas, clases):
    """Media del retardo de deteccion por clase sobre todas las corridas
    probadas, y cuantas corridas nunca dieron la alarma."""
    lineas = []
    for clase in clases:
        vals = [v for a in lista_alarmas for v in a.get(clase, [])]
        if not vals:
            continue
        ok = [v for v in vals if v is not None]
        nunca = len(vals) - len(ok)
        txt = "%.1f +/- %.1f" % media_std(ok) if ok else "-"
        extra = "   (%d de %d corridas sin alarma)" % (nunca, len(vals)) if nunca else ""
        lineas.append("  %-11s %s%s" % (clase, txt, extra))
    return lineas


def evalua_perfil(df, y, cols, tr_mask, te_mask):
    """Entrena con tr_mask y prueba con te_mask (bosque, todas las features)."""
    tr = sorted(df.index[tr_mask])
    te = sorted(df.index[te_mask])
    if not te or y.loc[tr].nunique() < 2:
        return None
    return evalua_fold(df, matriz_numerica(df, cols), y, tr, te, modelos()["bosque"])


def evalua_nuevos(df, df_new, cols):
    """Entrena el bosque con TODO lo conocido (df) y prueba escenarios que
    nunca vio (df_new). Como la clase es nueva, lo que se mide es si da la
    alarma: % de ventanas de ataque marcadas como no-BENIGN."""
    Xtr = matriz_numerica(df, cols)
    vary = [c for c in Xtr.columns if Xtr[c].nunique() > 1]
    model = modelos()["bosque"]
    model.fit(Xtr[vary], df["Label"])
    pred = pd.Series(model.predict(matriz_numerica(df_new, vary)), index=df_new.index)
    filas = []
    for scen, g in df_new.groupby("scenario", sort=False):
        ataque = g["Label"] != "BENIGN"
        p = pred.loc[g.index]
        det = float((p[ataque] != "BENIGN").mean()) if ataque.any() else float("nan")
        fp = float((p[~ataque] != "BENIGN").mean()) if (~ataque).any() else float("nan")
        como = p[ataque].value_counts()
        como = ", ".join("%s %d%%" % (c, round(100 * n / ataque.sum())) for c, n in como.head(2).items())
        alarmas = first_alarm(g, g["Label"], p)
        filas.append({"escenario": scen, "corridas": g["run"].nunique(),
                      "deteccion": det, "fpr": fp, "como": como,
                      "retardos": [v for vs in alarmas.values() for v in vs]})
    return filas


# --------------------------------------------------------------------------
# Informe.
# --------------------------------------------------------------------------

def main():
    global ORDEN
    if not DATA.is_file():
        print("Falta %s. Corre antes:\n  python3 scripts/mininet/build_windows.py" % DATA)
        return
    OUT.mkdir(parents=True, exist_ok=True)

    df_all, fuentes = cargar()
    rel_cols = agrega_relativas(df_all)
    conocido = df_all["scenario"].isin(ESCENARIOS_BASE)
    df_new = df_all[~conocido].reset_index(drop=True)
    df = df_all[conocido].reset_index(drop=True)
    y = df["Label"]
    ORDEN = ["BENIGN"] + sorted(c for c in y.unique() if c != "BENIGN")
    cols = feature_cols(df)
    grupos = grupos_de_features(cols)
    grupos["relativas"] = rel_cols + [c for c in SIN_ESCALA if c in cols]
    grupos["todas+rel"] = cols + rel_cols
    particiones, modo = folds(df)
    n_folds = len(particiones)
    perfiles = sorted(df["profile"].unique(), key=lambda p: (p != "normal", p))

    lineas = [
        "Detector por ventana de tiempo",
        "",
        "Datos: %s" % ", ".join(
            str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f) for f in fuentes),
        "Particion: %s  (%d fold%s)" % (modo, n_folds, "s" if n_folds != 1 else ""),
        "Ventanas: %d  |  features: %d (red %d, sdn %d) + %d relativas"
        % (len(df), len(cols), len(grupos["red"]), len(grupos.get("sdn", [])), len(rel_cols)),
        "Escenarios para entrenar: %s" % ", ".join(ESCENARIOS_BASE),
        "Ataques nunca vistos (solo prueba): %s" % (
            ", ".join(sorted(df_new["scenario"].unique())) if len(df_new) else "ninguno"),
        "Perfiles: %s" % ", ".join(
            "%s (%d corridas)" % (p, df.loc[df.profile == p, "run"].nunique()) for p in perfiles),
        "",
    ]
    calib_mala = df_all[(df_all["elapsed_s"] <= CALIB_S) & (df_all["Label"] != "BENIGN")]
    if len(calib_mala):
        lineas.append("AVISO: %d ventanas de calibracion (primeros %d s) son ataque, en %d"
                      % (len(calib_mala), CALIB_S, calib_mala.groupby(["run", "scenario"]).ngroups))
        lineas.append("corrida(s): su linea base de rel_* esta contaminada. Usa ONSET_S >= %d."
                      % (CALIB_S + 5))
        lineas.append("")
    hay_sdn = bool(df.get("sdn_flows_total", pd.Series([0])).abs().sum()) if "sdn_flows_total" in df else False
    if not hay_sdn:
        lineas.append("AVISO: las columnas sdn_* estan en 0 (datos del controlador")
        lineas.append("viejo). Recaptura con flow_monitor_13 para la ablacion de SDN.")
        lineas.append("")

    # ---- 1) Comparacion de modelos, con todas las features --------------
    lineas.append("== Comparacion de modelos (todas las features) ==")
    lineas.append("Modelo                 F1 macro        F1 binario")
    mejor = None
    for nombre, _m in modelos().items():
        fac = lambda n=nombre: modelos()[n]
        res = corre_cv(df, y, grupos["todas"], fac, particiones)
        macro_m, macro_s = media_std([r["macro"] for r in res])
        bin_m, bin_s = media_std([r["f1_bin"] for r in res])
        lineas.append("%-22s %.3f +/- %.3f   %.3f +/- %.3f"
                      % (nombre, macro_m, macro_s, bin_m, bin_s))
        if mejor is None or macro_m > mejor[1]:
            mejor = (nombre, macro_m)
    lineas.append("")

    # ---- 2) Ablacion de features con el bosque --------------------------
    lineas.append("== Ablacion de features (bosque aleatorio) ==")
    lineas.append("Grupo        F1 macro        aporta")
    base_macro = None
    orden_grupos = [g for g in ("red", "sdn", "todas", "relativas", "todas+rel") if g in grupos]
    macros_grupo = {}
    for g in orden_grupos:
        res = corre_cv(df, y, grupos[g], lambda: modelos()["bosque"], particiones)
        m, s = media_std([r["macro"] for r in res])
        macros_grupo[g] = m
        lineas.append("%-12s %.3f +/- %.3f" % (g, m, s))
    if "red" in macros_grupo and "todas" in macros_grupo:
        delta = macros_grupo["todas"] - macros_grupo["red"]
        lineas.append("")
        lineas.append("Aporte del SDN (todas - red): %+.3f de F1 macro." % delta)
        if not hay_sdn:
            lineas.append("  (0 esperado mientras sdn_* esten en 0)")
    lineas.append("")

    # ---- 3) Reporte detallado con el bosque y todas las features --------
    res_rf = corre_cv(df, y, grupos["todas"], lambda: modelos()["bosque"], particiones)
    macro_m, macro_s = media_std([r["macro"] for r in res_rf])
    bin_m, bin_s = media_std([r["f1_bin"] for r in res_rf])
    fpr_m, fpr_s = media_std([r["fpr"] for r in res_rf])
    lineas.append("== Detalle (bosque aleatorio, todas las features) ==")
    lineas.append("F1 macro:   %.3f +/- %.3f" % (macro_m, macro_s))
    lineas.append("F1 binario: %.3f +/- %.3f" % (bin_m, bin_s))
    lineas.append("Falsos positivos en benigno: %.1f%% +/- %.1f%%" % (100 * fpr_m, 100 * fpr_s))
    lineas.append("")
    lineas.append("Recall por clase (media entre folds):")
    for clase in ORDEN:
        vals = [r["recalls"][clase] for r in res_rf if clase in r["recalls"]]
        if vals:
            m, s = media_std(vals)
            lineas.append("  %-11s %.3f +/- %.3f" % (clase, m, s))
    lineas.append("")
    lineas.append("Retardo de deteccion (s desde el inicio real del ataque):")
    lineas += retardos_txt([r["alarmas"] for r in res_rf], ORDEN[1:])
    tr_m, _tr_s = media_std([r["macro_train"] for r in res_rf])
    lineas.append("")
    lineas.append("Brecha entrenamiento - prueba (sobreajuste clasico):")
    lineas.append("  F1 macro entrenamiento %.3f | prueba %.3f | brecha %+.3f"
                  % (tr_m, macro_m, tr_m - macro_m))
    lineas.append("")

    # ---- 4) Separabilidad: ¿alcanza con un arbol chico? -----------------
    res_arbol = corre_cv(
        df, y, grupos["todas"],
        lambda: DecisionTreeClassifier(max_depth=PROF_SEPARABILIDAD, random_state=42),
        particiones)
    arbol_m, arbol_s = media_std([r["macro"] for r in res_arbol])
    lineas.append("== Separabilidad (arbol de %d niveles, mismas particiones) =="
                  % PROF_SEPARABILIDAD)
    lineas.append("F1 macro: %.3f +/- %.3f" % (arbol_m, arbol_s))
    if arbol_m >= UMBRAL_FACIL:
        lineas.append("  -> Un punado de umbrales ya separa las clases: el escenario es facil.")
    lineas.append("")

    # ---- 5) Generalizacion a ataques dificiles --------------------------
    gen_filas = []
    if len(perfiles) > 1:
        lineas.append("== Generalizacion a ataques dificiles (bosque) ==")
        lineas.append("features: 'todas' = absolutas; 'relativas' = contra la linea base")
        lineas.append("de la propia corrida (rel_*) + proporciones.")
        cab = "%-10s %-10s %6s   %-8s %-10s %-6s  %s" % (
            "perfil", "features", "vent.", "F1 macro", "F1 binario", "FP ben", "recall por clase")
        experimentos = []
        if "normal" in perfiles:
            experimentos.append((
                "A) Entrena SOLO con 'normal', prueba cada perfil (nunca vio ataques asi):",
                "solo_normal", lambda p: df["profile"] == "normal"))
        experimentos.append((
            "B) Deja un perfil entero fuera (entrena con todos los demas):",
            "perfil_fuera", lambda p: df["profile"] != p))
        for titulo, clave, tr_de in experimentos:
            lineas.append(titulo)
            lineas.append(cab)
            alarmas_exp = []
            for p in perfiles:
                if clave == "solo_normal" and p == "normal":
                    continue
                for fs in CONJUNTOS:
                    r = evalua_perfil(df, y, grupos[fs], tr_de(p), df["profile"] == p)
                    if r is None:
                        continue
                    if fs == "todas":
                        alarmas_exp.append(r["alarmas"])
                    rec = " ".join("%s %.2f" % (c[:4], r["recalls"][c]) for c in ORDEN if c in r["recalls"])
                    lineas.append("%-10s %-10s %6d   %.3f    %.3f      %4.1f%%  %s" % (
                        p, fs, len(r["yt"]), r["macro"], r["f1_bin"], 100 * r["fpr"], rec))
                    gen_filas.append({
                        "experimento": clave, "perfil": p, "features": fs, "n_test": len(r["yt"]),
                        "macro": r["macro"], "f1_bin": r["f1_bin"], "fpr": r["fpr"],
                        **{"recall_" + c: v for c, v in r["recalls"].items()},
                    })
            lineas.append("  retardo de deteccion con 'todas' (s):")
            lineas += ["  " + ln for ln in retardos_txt(alarmas_exp, ORDEN[1:])]
            lineas.append("")
        pd.DataFrame(gen_filas).to_csv(OUT / "generalizacion.csv", index=False)

    # ---- 6) Ataques nunca vistos ---------------------------------------
    nuevos = {}
    if len(df_new):
        lineas.append("== Ataques nunca vistos (entrena con todo lo conocido) ==")
        lineas.append("La clase es nueva: se mide si da la alarma (ventana de ataque")
        lineas.append("marcada como cualquier ataque) y como la confunde.")
        lineas.append("%-12s %-10s %4s  %-9s %-7s %-9s %s" % (
            "escenario", "features", "corr", "detecta", "FP ben", "retardo", "lo confunde con"))
        filas_csv = []
        for fs in CONJUNTOS:
            nuevos[fs] = evalua_nuevos(df, df_new, grupos[fs])
            for f in nuevos[fs]:
                ok = [v for v in f["retardos"] if v is not None]
                ret = "%.1f s" % np.mean(ok) if ok else "nunca"
                lineas.append("%-12s %-10s %4d  %6.1f%%   %5.1f%%  %-9s %s" % (
                    f["escenario"], fs, f["corridas"], 100 * f["deteccion"],
                    100 * f["fpr"], ret, f["como"]))
                filas_csv.append({k: v for k, v in f.items() if k != "retardos"} | {"features": fs})
        pd.DataFrame(filas_csv).to_csv(OUT / "ataques_nuevos.csv", index=False)
        lineas.append("")

    # Guarda metricas por fold (para la tesis).
    por_fold = []
    for (tr, te, name), r in zip(particiones, res_rf):
        por_fold.append({
            "fold": name, "n_test": len(te),
            "macro": r["macro"], "f1_bin": r["f1_bin"], "fpr": r["fpr"],
        })
    pd.DataFrame(por_fold).to_csv(OUT / "cv_por_corrida.csv", index=False)

    # Matriz de confusion agregada de todos los folds.
    yt_all = pd.concat([r["yt"] for r in res_rf])
    pred_all = pd.concat([r["pred"] for r in res_rf])
    labels = [c for c in ORDEN if c in set(yt_all) or c in set(pred_all)]
    matriz = confusion_matrix(yt_all, pred_all, labels=labels)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    im = ax.imshow(matriz, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicho")
    ax.set_ylabel("Real")
    ax.set_title("Deteccion por ventana (todos los folds)")
    for i in range(matriz.shape[0]):
        for j in range(matriz.shape[1]):
            ax.text(j, i, str(matriz[i, j]), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(OUT / "matriz.png")
    plt.close(fig)

    # Importancias de un bosque entrenado con todo (solo orientativo).
    rf = modelos()["bosque"]
    X_all = matriz_numerica(df, grupos["todas"])
    vary = [c for c in X_all.columns if X_all[c].nunique() > 1]
    if vary:
        rf.fit(X_all[vary], y)
        imp = pd.Series(rf.feature_importances_, index=vary).sort_values(ascending=False)
        lineas.append("")
        lineas.append("Columnas que mas pesan (bosque sobre todo el dataset):")
        for name, val in imp.head(8).items():
            lineas.append("  %.3f  %s" % (val, name))

    lineas += ["", "Lectura honesta",
               "  F1 macro (corrida fuera) = %.3f +/- %.3f sobre %d fold%s." % (
                   macro_m, macro_s, n_folds, "s" if n_folds != 1 else "")]
    if tr_m - macro_m > 0.05:
        lineas.append("  Brecha de %.3f entre entrenamiento y prueba: hay sobreajuste;"
                      % (tr_m - macro_m))
        lineas.append("  baja max_depth / sube min_samples_leaf del bosque.")
    else:
        lineas.append("  Brecha entrenamiento-prueba de %.3f: no es sobreajuste clasico."
                      % (tr_m - macro_m))
    if arbol_m >= UMBRAL_FACIL:
        lineas.append("  Pero un arbol de %d niveles ya da %.3f: las clases se separan"
                      % (PROF_SEPARABILIDAD, arbol_m))
        lineas.append("  con pocos umbrales y el F1 alto describe al simulador, no al")
        lineas.append("  modelo. Regularizar no lo arregla: hacen falta datos mas dificiles.")
    for fs in CONJUNTOS:
        peor = [f for f in gen_filas if f["experimento"] == "perfil_fuera"
                and f["perfil"] != "normal" and f["features"] == fs]
        if peor:
            f = min(peor, key=lambda d: d["macro"])
            media = np.mean([d["macro"] for d in peor])
            lineas.append("  Perfil dificil fuera del entrenamiento, features '%s': F1 macro" % fs)
            lineas.append("  medio %.3f, peor %.3f ('%s')." % (media, f["macro"], f["perfil"]))
    if gen_filas:
        lineas.append("  Esos son los numeros defendibles para la tesis, no el 0,99.")
    for fs, filas in nuevos.items():
        dets = [f["deteccion"] for f in filas if not np.isnan(f["deteccion"])]
        if dets:
            lineas.append("  Ataques nunca vistos ('%s'): detecta en promedio el %.0f%% de"
                          % (fs, 100 * np.mean(dets)))
            lineas.append("  sus ventanas de ataque.")
    if len(perfiles) == 1:
        lineas.append("  Solo hay corridas de perfil '%s'. Genera ataques dificiles (ver" % perfiles[0])
        lineas.append("  docs/fases_overfitting.md):")
        lineas.append("    bash scripts/docker/run_scenario.sh dificil 2 120")
        lineas.append("    WINDOWS_DIR=ventanas_dificil ONLY_TAGS='...' python3 scripts/mininet/build_windows.py")
    lineas.append("  La ablacion dice cuanto aporta el SDN frente a usar solo la red.")
    (OUT / "informe.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print("\nListo en", OUT)


if __name__ == "__main__":
    main()
