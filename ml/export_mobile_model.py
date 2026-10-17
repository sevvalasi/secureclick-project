"""Android uygulaması için çevrimdışı çalışan hafif URL modeli üretir (öneri formu §5).

Model: karakter 3-5 gram -> HashingVectorizer (2^18 boyut, L2 normalize) -> L1 cezalı
lojistik regresyon. L1 cezası ağırlıkların çoğunu sıfırlar; yalnızca sıfır olmayanlar JSON'a
yazılır. Android tarafı (UrlModel.java) aynı normalizasyonu, n-gram üretimini ve
MurmurHash3 (seed 0) indekslemesini birebir uygular; ek kütüphane gerekmez.

Kullanım:  python -m ml.export_mobile_model
Çıktılar:  android/app/src/main/assets/url_model.json, reports/mobile_metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import LogisticRegression

from secureclick.evaluation import best_threshold, metrics
from secureclick.features.url_features import normalize_url

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "android" / "app" / "src" / "main" / "assets" / "url_model.json"
N_FEATURES = 2 ** 18
NGRAM = (3, 5)


def vectorizer() -> HashingVectorizer:
    return HashingVectorizer(analyzer="char", ngram_range=NGRAM, n_features=N_FEATURES,
                             alternate_sign=False, norm="l2", lowercase=True, dtype=np.float32)


def main():
    df = pd.read_csv(ROOT / "data" / "processed" / "urls.csv")
    df["norm"] = df["url"].map(normalize_url)
    tr, va, te = (df[df.split == s] for s in ("train", "val", "test"))
    hv = vectorizer()
    Xtr, Xva, Xte = (hv.transform(d.norm) for d in (tr, va, te))

    best = None
    for C in (2.0, 8.0, 32.0):
        m = LogisticRegression(l1_ratio=1.0, solver="liblinear", C=C, max_iter=2000).fit(Xtr, tr.label)
        f1 = metrics(va.label, m.predict_proba(Xva)[:, 1])["f1"]
        nnz = int(np.count_nonzero(m.coef_))
        print(f"C={C}: doğrulama F1={f1:.4f}, sıfır olmayan ağırlık={nnz:,}")
        if best is None or f1 > best[1]:
            best = (m, f1, C)
    m, _, C = best
    pv, pt = m.predict_proba(Xva)[:, 1], m.predict_proba(Xte)[:, 1]
    thr = best_threshold(va.label, pv)
    test = metrics(te.label, pt, thr)
    print(f"Seçilen C={C}, eşik={thr:.3f} | TEST " + ", ".join(
        f"{k}={test[k]:.4f}" for k in ("accuracy", "precision", "recall", "f1", "roc_auc")))

    coef = m.coef_[0]
    idx = np.flatnonzero(coef)
    model = {
        "version": 1, "type": "hashed_char_ngram_logreg",
        "n_features": N_FEATURES, "ngram_min": NGRAM[0], "ngram_max": NGRAM[1],
        "intercept": round(float(m.intercept_[0]), 6), "threshold": round(thr, 6),
        "indices": idx.tolist(), "weights": [round(float(w), 5) for w in coef[idx]],
        # Android tarafında birebir uyumu doğrulamak için örnek (url -> olasılık)
        "test_vectors": [{"url": u, "prob": round(float(p), 5)} for u, p in
                         zip(te.url.head(5), m.predict_proba(hv.transform(te.norm.head(5)))[:, 1])],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
    json.dump({"C": C, "threshold": thr, "nonzero_weights": len(idx), "test": test,
               "size_kb": round(OUT.stat().st_size / 1024, 1)},
              open(ROOT / "reports" / "mobile_metrics.json", "w"), indent=2)
    print(f"{len(idx):,} ağırlık, {OUT.stat().st_size / 1024:.0f} KB -> {OUT}")


if __name__ == "__main__":
    main()
