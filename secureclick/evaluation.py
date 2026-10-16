"""Performans metrikleri ve istatistiksel testler (öneri formu, Yöntem §6)."""
from __future__ import annotations

import numpy as np
from scipy.stats import binomtest, chi2
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score, roc_curve)

TARGETS = {"accuracy": 0.90, "precision": 0.88, "recall": 0.92, "f1": 0.90, "roc_auc": 0.95}


def metrics(y_true, y_prob, threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_prob) if len(set(y_true)) > 1 and len(set(y_prob)) > 1 else None,
        "fpr": fp / max(fp + tn, 1),
        "threshold": threshold,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n": int(len(y_true)),
    }
    return {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in out.items()}


def best_threshold(y_true, y_prob, min_recall: float = TARGETS["recall"]) -> float:
    """Doğrulama kümesinde eşik seçimi: recall hedefini tutturanlar içinde F1'i en yüksek olan.

    Zararlı bağlantıyı kaçırmak (FN), güvenli bağlantıyı uyarmaktan (FP) daha maliyetli
    olduğundan önce recall hedefi (≥ %92) aranır; hiçbir eşik bunu sağlamıyorsa en iyi F1.
    """
    p, r, t = precision_recall_curve(y_true, y_prob)
    p, r = p[:-1], r[:-1]
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    ok = r >= min_recall
    idx = np.argmax(np.where(ok, f1, -1)) if ok.any() else np.argmax(f1)
    return float(t[idx])


def curves(y_true, y_prob, points: int = 60) -> dict:
    """Web arayüzündeki grafikler için seyreltilmiş ROC ve PR eğrisi noktaları."""
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    prec, rec, _ = precision_recall_curve(y_true, y_prob)

    def thin(a, b):
        idx = np.unique(np.linspace(0, len(a) - 1, min(points, len(a))).astype(int))
        return [[round(float(a[i]), 4), round(float(b[i]), 4)] for i in idx]

    return {"roc": thin(fpr, tpr), "pr": thin(rec, prec)}


def mcnemar(y_true, pred_a, pred_b) -> dict:
    """İki sınıflandırıcının aynı test örneklerindeki hatalarını karşılaştırır.

    b: A doğru, B yanlış; c: A yanlış, B doğru. Küçük örneklemde kesin binom testi,
    aksi hâlde süreklilik düzeltmeli ki-kare kullanılır.
    """
    y_true, pred_a, pred_b = map(np.asarray, (y_true, pred_a, pred_b))
    a_ok, b_ok = pred_a == y_true, pred_b == y_true
    b = int(np.sum(a_ok & ~b_ok))
    c = int(np.sum(~a_ok & b_ok))
    if b + c == 0:
        return {"b": b, "c": c, "statistic": 0.0, "p_value": 1.0, "method": "none"}
    if b + c < 25:
        p = binomtest(b, b + c, 0.5).pvalue
        return {"b": b, "c": c, "statistic": None, "p_value": float(p), "method": "exact"}
    stat = (abs(b - c) - 1) ** 2 / (b + c)
    return {"b": b, "c": c, "statistic": round(float(stat), 3),
            "p_value": float(chi2.sf(stat, 1)), "method": "chi2_cc"}
