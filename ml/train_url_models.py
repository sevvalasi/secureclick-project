"""URL sınıflandırma modellerini eğitir, karşılaştırır ve raporlar.

Deney 1 — Ana değerlendirme (öneri formu §4, §6)
    * Sınırlı Grid Search (doğrulama kümesinde F1'e göre)
    * Eğitim kümesinde 5 katlı, gruplu çapraz doğrulama
    * Doğrulama kümesinde eşik optimizasyonu (Precision-Recall eğrisi)
    * Test kümesinde Accuracy / Precision / Recall / F1 / ROC-AUC, karışıklık matrisi
    * Modeller arası McNemar testi

Deney 2 — Zamansal değerlendirme ("yeni saldırıları erken tespit")
    Zararlı URL'ler bildirim zamanına göre sıralanır; ilk %80 ile eğitilir, sonraki %20
    (henüz hiçbir listede görülmemiş "yeni" saldırılar) ile test edilir. Kara liste
    temel çizgisi = eğitim döneminde görülmüş zararlı URL ve alan adları.

Kullanım:  python -m ml.train_url_models [--skip-cv] [--quick]
Çıktılar:  models/url_*.joblib, reports/url_metrics.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from secureclick.evaluation import best_threshold, curves, mcnemar, metrics
from secureclick.features.url_features import FEATURE_NAMES, registered_domain
from secureclick.pipelines import URL_MODEL_LABELS, URL_MODELS

ROOT = Path(__file__).resolve().parents[1]
DATA, MODELS, REPORTS = ROOT / "data" / "processed", ROOT / "models", ROOT / "reports"


def proba(model, X) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


class Blacklist:
    """Statik kara liste: bilinen zararlı URL'ler ve alan adları üzerinden birebir eşleşme."""

    def fit(self, urls, labels):
        mal = [u for u, y in zip(urls, labels) if y == 1]
        self.urls = set(mal)
        self.domains = {registered_domain(u) for u in mal}
        return self

    def predict_proba(self, X):
        p = np.array([1.0 if (u in self.urls or registered_domain(u) in self.domains) else 0.0 for u in X])
        return np.c_[1 - p, p]


def grid_search(name, train, val, quick=False):
    factory, grid = URL_MODELS[name]
    combos = [dict(zip(grid, v)) for v in itertools.product(*grid.values())]
    if quick:
        combos = combos[:1]
    best, best_f1, tried = None, -1, []
    for params in combos:
        t0 = time.time()
        m = factory(**params).fit(train.url, train.label)
        p = proba(m, val.url)
        f1 = metrics(val.label, p)["f1"]
        tried.append({"params": params, "val_f1": f1, "seconds": round(time.time() - t0, 1)})
        print(f"    {params} -> doğrulama F1={f1:.4f} ({time.time() - t0:.0f} sn)")
        if f1 > best_f1:
            best, best_f1, best_params = m, f1, params
    return best, best_params, tried


def cross_validate(name, params, train, k=5):
    factory, _ = URL_MODELS[name]
    cv = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=42)
    scores = []
    for tr_idx, te_idx in cv.split(train, train.label, train.group):
        tr, te = train.iloc[tr_idx], train.iloc[te_idx]
        m = factory(**params).fit(tr.url, tr.label)
        r = metrics(te.label, proba(m, te.url))
        scores.append({"f1": r["f1"], "roc_auc": r["roc_auc"], "accuracy": r["accuracy"]})
    df = pd.DataFrame(scores)
    return {c: {"mean": round(df[c].mean(), 4), "std": round(df[c].std(), 4)} for c in df.columns}


def temporal_experiment(df, best_params) -> dict:
    mal = df[df.label == 1].copy()
    mal["ts"] = pd.to_datetime(mal["timestamp"], utc=True, errors="coerce", format="mixed")
    mal = mal.dropna(subset=["ts"]).sort_values("ts")
    cut = mal["ts"].quantile(0.8)
    mal_old, mal_new = mal[mal.ts <= cut], mal[mal.ts > cut]
    ben = df[df.label == 0]
    ben_train, ben_test = ben[ben.split != "test"], ben[ben.split == "test"]
    # Yeni saldırılardan kara listede birebir bulunanları da test kümesinde tutuyoruz;
    # gerçek hayatta da tekrar eden saldırılar olur.
    train = pd.concat([mal_old, ben_train.sample(min(len(ben_train), len(mal_old)), random_state=0)])
    test = pd.concat([mal_new, ben_test.sample(min(len(ben_test), len(mal_new)), random_state=0)])
    print(f"  kesim zamanı {cut:%Y-%m-%d %H:%M}, eğitim {len(train):,}, test {len(test):,}")

    out = {"cutoff": cut.isoformat(), "n_train": len(train), "n_test": len(test), "models": {}}
    bl = Blacklist().fit(train.url.tolist(), train.label.tolist())
    p_bl = proba(bl, test.url)
    out["models"]["blacklist"] = metrics(test.label, p_bl)
    preds = {"blacklist": p_bl >= 0.5}
    probs = {}
    for name in ("random_forest", "svm"):
        factory, _ = URL_MODELS[name]
        m = factory(**best_params[name]).fit(train.url, train.label)
        probs[name] = proba(m, test.url)
    probs["ensemble"] = (probs["random_forest"] + probs["svm"]) / 2
    for name, p in probs.items():
        out["models"][name] = metrics(test.label, p)
        preds[name] = p >= 0.5
    y = test.label.to_numpy()
    newly = (y == 1) & ~preds["blacklist"]
    out["missed_by_blacklist"] = int(newly.sum())
    out["of_those_caught_by_ensemble"] = int((newly & preds["ensemble"]).sum())
    out["mcnemar_ensemble_vs_blacklist"] = mcnemar(y, preds["ensemble"].astype(int), preds["blacklist"].astype(int))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-cv", action="store_true")
    ap.add_argument("--quick", action="store_true", help="grid search yerine ilk parametre seti")
    args = ap.parse_args()

    df = pd.read_csv(DATA / "urls.csv")
    train, val, test = (df[df.split == s].reset_index(drop=True) for s in ("train", "val", "test"))
    print(f"Eğitim {len(train):,} | doğrulama {len(val):,} | test {len(test):,}")
    MODELS.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)

    report = {"dataset": {
        "n_total": len(df), "n_train": len(train), "n_val": len(val), "n_test": len(test),
        "per_class": df.label.value_counts().rename({0: "benign", 1: "malicious"}).to_dict(),
        "sources": df.source.value_counts().to_dict(), "n_groups": int(df.group.nunique()),
    }, "models": {}, "labels": URL_MODEL_LABELS}

    fitted, probs_val, probs_test, best_params = {}, {}, {}, {}
    for name in URL_MODELS:
        print(f"\n[{URL_MODEL_LABELS[name]}] grid search")
        model, params, tried = grid_search(name, train, val, args.quick)
        best_params[name] = params
        pv, t0 = proba(model, val.url), time.time()
        pt = proba(model, test.url)
        latency_ms = (time.time() - t0) / len(test) * 1000
        thr = best_threshold(val.label, pv)
        entry = {
            "params": params, "grid": tried, "threshold": thr,
            "val": metrics(val.label, pv, thr), "test": metrics(test.label, pt, thr),
            "test_at_0.5": metrics(test.label, pt), "curves": curves(test.label, pt),
            "latency_ms_per_url": round(latency_ms, 3),
        }
        if not args.skip_cv:
            print("    5 katlı çapraz doğrulama…")
            entry["cv5"] = cross_validate(name, params, train)
            print(f"    CV F1 = {entry['cv5']['f1']['mean']:.4f} ± {entry['cv5']['f1']['std']:.4f}")
        print(f"    TEST (eşik {thr:.3f}): " + ", ".join(
            f"{k}={entry['test'][k]:.4f}" for k in ("accuracy", "precision", "recall", "f1", "roc_auc")))
        report["models"][name] = entry
        fitted[name], probs_val[name], probs_test[name] = model, pv, pt
        joblib.dump(model, MODELS / f"url_{name}.joblib", compress=3)

    # Topluluk: RF (el yapımı özellikler) + SVM (karakter n-gram) olasılık ortalaması
    pv = (probs_val["random_forest"] + probs_val["svm"]) / 2
    pt = (probs_test["random_forest"] + probs_test["svm"]) / 2
    thr = best_threshold(val.label, pv)
    report["models"]["ensemble"] = {
        "params": {"members": ["random_forest", "svm"], "weights": [0.5, 0.5]}, "threshold": thr,
        "val": metrics(val.label, pv, thr), "test": metrics(test.label, pt, thr),
        "test_at_0.5": metrics(test.label, pt), "curves": curves(test.label, pt),
    }
    probs_test["ensemble"] = pt
    print(f"\n[Topluluk] TEST: " + ", ".join(
        f"{k}={report['models']['ensemble']['test'][k]:.4f}" for k in ("accuracy", "precision", "recall", "f1", "roc_auc")))

    # Kara liste temel çizgisi (ana bölmede; gruplu bölme nedeniyle test alan adları
    # eğitimde hiç görülmediğinden kara liste burada neredeyse hiç yakalayamaz)
    bl = Blacklist().fit(train.url.tolist(), train.label.tolist())
    probs_test["blacklist"] = proba(bl, test.url)
    report["models"]["blacklist"] = {"threshold": 0.5, "test": metrics(test.label, probs_test["blacklist"])}

    # McNemar: topluluk vs. diğerleri
    y = test.label.to_numpy()
    preds = {n: (probs_test[n] >= report["models"][n]["threshold"]).astype(int) for n in probs_test}
    report["mcnemar"] = {f"ensemble_vs_{n}": mcnemar(y, preds["ensemble"], preds[n])
                         for n in preds if n != "ensemble"}

    # Özellik önemleri (Random Forest)
    rf = fitted["random_forest"].steps[-1][1]
    imp = sorted(zip(FEATURE_NAMES, rf.feature_importances_), key=lambda x: -x[1])
    report["feature_importance"] = [[k, round(float(v), 4)] for k, v in imp]

    # Kaynak bazında test recall'u (hangi tür tehditte iyiyiz?)
    report["recall_by_source"] = {
        s: round(float((preds["ensemble"][(test.source == s).to_numpy()] == 1).mean()), 4)
        for s in test[test.label == 1].source.unique()
    }
    report["fpr_by_source"] = {
        s: round(float((preds["ensemble"][(test.source == s).to_numpy()] == 1).mean()), 4)
        for s in test[test.label == 0].source.unique()
    }

    print("\n[Zamansal deney] eski saldırılarla eğit, yeni saldırılarla test et")
    report["temporal"] = temporal_experiment(df, best_params)
    for n, r in report["temporal"]["models"].items():
        print(f"    {URL_MODEL_LABELS[n]:<32} recall={r['recall']:.4f} precision={r['precision']:.4f} f1={r['f1']:.4f}")

    json.dump({"ensemble_threshold": thr, "members": ["random_forest", "svm"]},
              open(MODELS / "url_config.json", "w"), indent=2)
    report["generated_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    json.dump(report, open(REPORTS / "url_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nRapor -> {REPORTS / 'url_metrics.json'}")


if __name__ == "__main__":
    main()
