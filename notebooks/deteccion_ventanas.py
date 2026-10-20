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
    falsos positivos sobre benigno y tiempo hasta la primera alarma.

Salida:
  notebooks/resultados/ventanas/informe.txt
  notebooks/resultados/ventanas/matriz.png
  notebooks/resultados/ventanas/cv_por_corrida.csv
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "ventanas" / "ventanas.csv"
OUT = ROOT / "notebooks" / "resultados" / "ventanas"

REF_FIELDS = ["timestamp", "elapsed_s", "scenario", "run"]
TRAIN_FRACTION = 0.70
ORDEN = ["BENIGN", "httpflood", "icmpflood", "slowloris", "synflood"]


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
    return [c for c in df.columns if c not in REF_FIELDS + ["Label"]]


def grupos_de_features(cols):
    sdn = [c for c in cols if c.startswith("sdn_")]
    red = [c for c in cols if not c.startswith("sdn_")]
    g = {"red": red, "todas": cols}
    if sdn:
        g["sdn"] = sdn
    return g


def matriz_numerica(df: pd.DataFrame, cols):
    X = df[cols].apply(pd.to_numeric, errors="coerce")
    return X.replace([np.inf, -np.inf], np.nan).fillna(0)


# --------------------------------------------------------------------------
# Metricas.
# --------------------------------------------------------------------------

def first_alarm(df_test: pd.DataFrame, pred: pd.Series):
    """Por cada ataque, segundos entre el inicio del escenario (en la
    prueba) y la primera ventana marcada como ataque."""
    out = {}
    for scenario, grupo in df_test.groupby("scenario", sort=False):
        if scenario == "BENIGN" or scenario == "baseline":
            continue
        g = grupo.sort_values("elapsed_s")
        base = int(g["elapsed_s"].iloc[0])
        alarma = None
        for idx in g.index:
            if pred.loc[idx] != "BENIGN":
                alarma = int(g.loc[idx, "elapsed_s"]) - base
                break
        out[scenario] = alarma
    return out


def evalua_fold(df, X, y, tr, te, model):
    # Quita columnas constantes en el entrenamiento de ESTE fold.
    vary = [c for c in X.columns if X.loc[tr, c].nunique() > 1]
    if not vary:
        return None
    model.fit(X.loc[tr, vary], y.loc[tr])
    pred = pd.Series(model.predict(X.loc[te, vary]), index=te)
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

    alarmas = first_alarm(df.loc[te], pred)
    return {
        "macro": macro, "f1_bin": f1_bin, "fpr": fpr,
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


# --------------------------------------------------------------------------
# Informe.
# --------------------------------------------------------------------------

def main():
    if not DATA.is_file():
        print("Falta %s. Corre antes:\n  python3 scripts/mininet/build_windows.py" % DATA)
        return
    OUT.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA)
    y = df["Label"]
    cols = feature_cols(df)
    grupos = grupos_de_features(cols)
    particiones, modo = folds(df)
    n_folds = len(particiones)

    lineas = [
        "Detector por ventana de tiempo",
        "",
        "Particion: %s  (%d fold%s)" % (modo, n_folds, "s" if n_folds != 1 else ""),
        "Ventanas: %d  |  features: %d (red %d, sdn %d)"
        % (len(df), len(cols), len(grupos["red"]), len(grupos.get("sdn", []))),
        "",
    ]
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
    orden_grupos = [g for g in ("red", "sdn", "todas") if g in grupos]
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
    lineas.append("Tiempo hasta la primera alarma (media entre folds, s):")
    for clase in ORDEN:
        if clase == "BENIGN":
            continue
        vals = [r["alarmas"][clase] for r in res_rf
                if clase in r["alarmas"] and r["alarmas"][clase] is not None]
        if vals:
            m, s = media_std(vals)
            lineas.append("  %-11s %.1f +/- %.1f" % (clase, m, s))
        elif any(clase in r["alarmas"] for r in res_rf):
            lineas.append("  %-11s nunca sono la alarma" % clase)

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

    lineas += [
        "",
        "Lectura honesta",
        "  F1 macro = %.3f +/- %.3f sobre %d fold%s." % (
            macro_m, macro_s, n_folds, "s" if n_folds != 1 else ""),
        "  Con 1 sola corrida la desviacion es 0 y el numero es optimista:",
        "  repite varias (run_scenario.sh repeat N) para que sea defendible.",
        "  La ablacion dice cuanto aporta el SDN frente a usar solo la red.",
    ]
    (OUT / "informe.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print("\nListo en", OUT)


if __name__ == "__main__":
    main()
