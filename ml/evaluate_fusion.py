"""Hipotez testi: "Bağlantı metni + URL yapısı birlikte" vs. "yalnızca URL" vs. "kara liste".

Değerlendirme kümesi: Türkçe senaryo mesajları (ml/generate_tr_scenarios.py) + gerçek URL'ler.
  * %70 tutarlı çiftler      : dolandırıcılık mesajı + zararlı URL, meşru mesaj + güvenli URL
  * %15 zor vaka (A)         : dolandırıcılık mesajı + güvenli listeden URL
                               (ele geçirilmiş meşru site / henüz bilinmeyen alan adı senaryosu)
  * %15 zor vaka (B)         : masum görünen mesaj + zararlı URL (ele geçirilmiş tanıdık hesabı)
  Etiket: mesaj dolandırıcılık amaçlıysa VEYA URL zararlıysa 1.

Füzyon ağırlığı (alpha) ve eşikler 'val' şablonları + doğrulama URL'leri üzerinde seçilir;
raporlanan sonuçlar 'test' şablonları + test URL'leri üzerindedir (hiçbiri eğitimde görülmedi).

Kullanım:  python -m ml.evaluate_fusion
Çıktılar:  models/fusion_config.json, models/known_threats.txt, reports/fusion_metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.train_url_models import Blacklist
from secureclick.evaluation import best_threshold, mcnemar, metrics
from secureclick.predictor import SecureClick, fuse

ROOT = Path(__file__).resolve().parents[1]
DATA, MODELS, REPORTS = ROOT / "data" / "processed", ROOT / "models", ROOT / "reports"


def make_pairs(scen: pd.DataFrame, urls: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    mal, ben = urls[urls.label == 1].url.to_numpy(), urls[urls.label == 0].url.to_numpy()
    rows = []
    for _, s in scen.iterrows():
        r = rng.random()
        if r < 0.70:
            u_lab = s.label
        elif r < 0.85:
            u_lab = 0 if s.label == 1 else None  # A: sadece dolandırıcılık mesajları için
        else:
            u_lab = 1 if s.label == 0 else None  # B: sadece meşru mesajlar için
        if u_lab is None:
            u_lab = s.label
        url = rng.choice(mal if u_lab == 1 else ben)
        kind = "consistent" if u_lab == s.label else ("phish_text_benign_url" if s.label == 1 else "benign_text_mal_url")
        rows.append({"text": s.text.replace("{url}", url), "url": url, "text_label": s.label,
                     "url_label": u_lab, "label": int(s.label or u_lab), "kind": kind})
    return pd.DataFrame(rows)


def main():
    sc = SecureClick()
    scen = pd.read_csv(DATA / "tr_scenarios.csv")
    urls = pd.read_csv(DATA / "urls.csv")
    # Ayar: metin modelinin eğitimde görmediği doğrulama şablonları + doğrulama URL'leri
    tune = make_pairs(scen[scen.split == "val"], urls[urls.split == "val"], seed=1)
    test = make_pairs(scen[scen.split == "test"], urls[urls.split == "test"], seed=2)

    def scores(df):
        u = np.array([s["ensemble"] for s in sc.score_urls(df.url.tolist())])
        t = np.array([sc.score_text(x) for x in df.text])
        return u, t

    u_tune, t_tune = scores(tune)
    candidates = [{"mode": "weighted", "alpha": float(a)} for a in np.round(np.arange(0.3, 1.0, 0.05), 2)]
    candidates += [{"mode": "max"}, {"mode": "noisy_or"}]
    tried, best = [], None
    for cfg in candidates:
        f = np.array([fuse(a, b, cfg) for a, b in zip(u_tune, t_tune)])
        thr = best_threshold(tune.label, f)
        f1 = metrics(tune.label, f, thr)["f1"]
        tried.append({**cfg, "tune_f1": f1})
        if best is None or f1 > best[2]:
            best = (cfg, thr, f1)
    fcfg, thr_fusion, _ = best
    thr_url = best_threshold(tune.label, u_tune)
    thr_text = best_threshold(tune.label, t_tune)
    print(f"Seçilen füzyon kuralı={fcfg}, eşik={thr_fusion:.3f}")

    u, t = scores(test)
    fusion = np.array([fuse(a, b, fcfg) for a, b in zip(u, t)])
    bl = Blacklist().fit(urls[urls.split != "test"].url.tolist(), urls[urls.split != "test"].label.tolist())
    p_bl = bl.predict_proba(test.url)[:, 1]
    y = test.label.to_numpy()

    res = {
        "blacklist": metrics(y, p_bl),
        "url_only": metrics(y, u, thr_url),
        "text_only": metrics(y, t, thr_text),
        "fusion": metrics(y, fusion, thr_fusion),
    }
    by_kind = {}
    for kind in test.kind.unique():
        m = (test.kind == kind).to_numpy()
        by_kind[kind] = {name: round(float(((p >= th).astype(int)[m] == y[m]).mean()), 4)
                         for name, p, th in (("url_only", u, thr_url), ("text_only", t, thr_text),
                                             ("fusion", fusion, thr_fusion))}
        by_kind[kind]["n"] = int(m.sum())
    report = {
        "fusion_rule": fcfg, "alpha": fcfg.get("alpha"), "candidates": tried, "thresholds": {"fusion": thr_fusion, "url_only": thr_url, "text_only": thr_text},
        "n_test": len(test), "n_tune": len(tune), "results": res, "accuracy_by_kind": by_kind,
        "mcnemar_fusion_vs_url_only": mcnemar(y, (fusion >= thr_fusion).astype(int), (u >= thr_url).astype(int)),
        "mcnemar_fusion_vs_blacklist": mcnemar(y, (fusion >= thr_fusion).astype(int), (p_bl >= 0.5).astype(int)),
        "examples": test.sample(8, random_state=0)[["text", "label", "kind"]].to_dict("records"),
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    for k, r in res.items():
        print(f"  {k:<10} acc={r['accuracy']:.4f} prec={r['precision']:.4f} rec={r['recall']:.4f} f1={r['f1']:.4f}")
    print("  McNemar (füzyon vs yalnız URL):", report["mcnemar_fusion_vs_url_only"])

    # Ürün tarafı yapılandırması: zararlı eşiği = füzyon eşiği, şüpheli = onun ~%60'ı
    json.dump({**fcfg, "malicious": round(thr_fusion, 4), "suspicious": round(thr_fusion * 0.6, 4)},
              open(MODELS / "fusion_config.json", "w"), indent=2)
    # Bilinen tehdit listesi (kara liste katmanı) — tüm ham zararlı URL'ler
    mal = urls[urls.label == 1].norm.dropna().unique()
    (MODELS / "known_threats.txt").write_text("\n".join(mal), encoding="utf-8")
    # İtibar katmanı için Tranco ilk 10.000 (repoda ham veri olmadan da çalışsın)
    tranco = ROOT / "data" / "raw" / "tranco.csv"
    if tranco.exists():
        with open(tranco, encoding="utf-8") as src:
            (MODELS / "tranco_top.csv").write_text("".join(next(src) for _ in range(10_000)), encoding="utf-8")
    json.dump(report, open(REPORTS / "fusion_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Rapor -> {REPORTS / 'fusion_metrics.json'}")


if __name__ == "__main__":
    main()
