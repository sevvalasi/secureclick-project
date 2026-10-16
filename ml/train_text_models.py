"""Türkçe mesaj metni sınıflandırıcılarını eğitir (TF-IDF + LR, SVM).

Veri:
  * TurkishSMSCollection (Karasoy & Ballı, 2021): 2.536 spam / 2.215 normal SMS
  * Sentetik Türkçe kimlik avı/meşru senaryolar (ml/generate_tr_scenarios.py) —
    yalnızca 'train' şablonları eğitime girer; 'test' şablonları ayrı raporlanır.

Not: Spam ≠ kimlik avı; ancak spam SMS'lerin büyük bölümü aynı ikna kalıplarını
(aciliyet, ödül, bağlantıya yönlendirme) taşır. Sentetik senaryolar bu boşluğu
Türkiye'ye özgü dolandırıcılık kalıplarıyla tamamlar.

Kullanım:  python -m ml.train_text_models
Çıktılar:  models/text_model.joblib, reports/text_metrics.json
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split

from secureclick.evaluation import best_threshold, curves, mcnemar, metrics
from secureclick.pipelines import TEXT_MODELS

ROOT = Path(__file__).resolve().parents[1]
RAW, DATA = ROOT / "data" / "raw", ROOT / "data" / "processed"
MODELS, REPORTS = ROOT / "models", ROOT / "reports"
LABELS = {"text_tfidf_lr": "TF-IDF (1-2 gram) + Lojistik Regresyon", "text_svm": "TF-IDF + SVM"}


def load_sms() -> pd.DataFrame:
    df = pd.read_csv(RAW / "turkish_sms.csv", sep=";", encoding="utf-8")
    df = df.rename(columns={"Message": "text"}).dropna(subset=["text"])
    df["label"] = (df["Group"] == 1).astype(int)  # 1 = Spam
    df["source"] = "turkish_sms"
    return df[["text", "label", "source"]].drop_duplicates("text")


def main():
    sms = load_sms()
    sc = pd.read_csv(DATA / "tr_scenarios.csv")
    sc["source"] = "scenario"
    sc["text"] = sc["text"].str.replace("{url}", "urltoken", regex=False)
    sc_train, sc_val, sc_test = (sc[sc.split == k] for k in ("train", "val", "test"))

    sms_tr, sms_te = train_test_split(sms, test_size=0.2, stratify=sms.label, random_state=42)
    sms_tr, sms_va = train_test_split(sms_tr, test_size=0.125, stratify=sms_tr.label, random_state=42)
    train = pd.concat([sms_tr, sc_train[["text", "label", "source"]]], ignore_index=True)
    val = pd.concat([sms_va, sc_val[["text", "label", "source"]]], ignore_index=True)
    # SMS koleksiyonunda reklam mesajları da "spam" etiketli; spam ≠ kimlik avı. İki kaynağa
    # toplamda eşit ağırlık verilir ki model meşru kampanya/bildirim ile dolandırıcılığı ayırsın.
    w_sc = len(sms_tr) / max(len(sc_train), 1)
    weights = np.where(train.source == "scenario", w_sc, 1.0)
    print(f"Eğitim {len(train)} | doğrulama {len(val)} (SMS + senaryo) | SMS test {len(sms_te)} | senaryo test {len(sc_test)}")

    report = {"scenario_weight": round(w_sc, 2), "dataset": {"sms": len(sms), "sms_spam": int(sms.label.sum()), "scenarios": len(sc),
                          "scenario_test_templates": int(sc_test.template_id.nunique())},
              "models": {}, "labels": LABELS}
    def val_score(m):
        # SMS ve senaryo doğrulama kümelerinin F1 ortalaması: iki alanda da iyi olmalı
        f_sms = metrics(sms_va.label, m.predict_proba(sms_va.text)[:, 1])["f1"]
        f_sc = metrics(sc_val.label, m.predict_proba(sc_val.text)[:, 1])["f1"]
        return (f_sms + f_sc) / 2

    best_name, best_f1, preds = None, -1, {}
    for name, (factory, grid) in TEXT_MODELS.items():
        print(f"\n[{LABELS[name]}]")
        best, bf1 = None, -1
        for vals in itertools.product(*grid.values()):
            params = dict(zip(grid, vals))
            m = factory(**params).fit(train.text, train.label, clf__sample_weight=weights)
            f1 = val_score(m)
            print(f"    {params} -> doğrulama F1={f1:.4f}")
            if f1 > bf1:
                best, bf1, bparams = m, f1, params

        # 5 katlı çapraz doğrulama (eğitim kümesi)
        cv = []
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=42).split(train, train.label):
            m = factory(**bparams).fit(train.text.iloc[tr], train.label.iloc[tr], clf__sample_weight=weights[tr])
            cv.append(metrics(train.label.iloc[te], m.predict_proba(train.text.iloc[te])[:, 1])["f1"])
        cv = pd.Series(cv)

        pv = best.predict_proba(val.text)[:, 1]
        thr = best_threshold(val.label, pv, min_recall=0.9)
        pt = best.predict_proba(sms_te.text)[:, 1]
        ps = best.predict_proba(sc_test.text)[:, 1]
        report["models"][name] = {
            "params": bparams, "threshold": thr, "val_score": round(bf1, 4),
            "cv5": {"f1": {"mean": round(cv.mean(), 4), "std": round(cv.std(), 4)}},
            "test_sms": metrics(sms_te.label, pt, thr), "curves": curves(sms_te.label, pt),
            "test_scenarios_unseen_templates": metrics(sc_test.label, ps, thr),
        }
        preds[name] = (pt >= thr).astype(int)
        r = report["models"][name]
        print(f"    CV F1={cv.mean():.4f}±{cv.std():.4f} | SMS test F1={r['test_sms']['f1']:.4f} "
              f"| görülmemiş senaryo F1={r['test_scenarios_unseen_templates']['f1']:.4f}")
        if bf1 > best_f1:  # seçim doğrulama skoruna göre (test kümesine bakılmaz)
            best_name, best_f1, best_model, best_thr = name, bf1, best, thr

    names = list(preds)
    report["mcnemar"] = mcnemar(sms_te.label.to_numpy(), preds[names[0]], preds[names[1]])
    report["selected"] = best_name
    MODELS.mkdir(exist_ok=True)
    joblib.dump(best_model, MODELS / "text_model.joblib", compress=3)
    json.dump({"model": best_name, "threshold": best_thr}, open(MODELS / "text_config.json", "w"), indent=2)
    report["generated_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    json.dump(report, open(REPORTS / "text_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nSeçilen model: {LABELS[best_name]} -> models/text_model.joblib")


if __name__ == "__main__":
    main()
