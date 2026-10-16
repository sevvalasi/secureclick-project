"""SecureClick analiz motoru: URL + metin + canlı sinyalleri birleştirip karar verir.

Karar akışı (Şekil 1 — SecureClick Akış Şeması):
  Giriş (mesaj ve/veya URL)
    -> Ön işleme & özellik çıkarımı (URL analizi, Türkçe NLP)
    -> Yapay zekâ sınıflandırma (RF + SVM topluluğu, metin modeli)
    -> Karar mekanizması (füzyon + canlı sinyaller) -> Güvenli / Şüpheli / Zararlı
    -> Kullanıcıya anlık bildirim
"""
from __future__ import annotations

import csv
import json
import time
from functools import cached_property
from pathlib import Path

import joblib

from secureclick.features.text_features import explain_text, extract_text_features, extract_urls
from secureclick.features.url_features import (FREE_HOSTING, OFFICIAL_DOMAINS, SHORTENERS, explain_url,
                                               extract_url_features, normalize_url,
                                               registered_domain)
from secureclick.live_checks import live_signals, run_live_checks

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

LEVEL_BONUS = {"high": 0.15, "medium": 0.06, "low": 0.02}
REPUTATION_TOP_N = 10_000


def fuse(u: float, t: float | None, cfg: dict) -> float:
    """URL skoru (u) ile metin skorunu (t) birleştirir. Kural doğrulama kümesinde seçilir."""
    if t is None:
        return u
    mode = cfg.get("mode", "weighted")
    if mode == "max":
        return max(u, t)
    if mode == "noisy_or":
        return 1 - (1 - u) * (1 - t)
    a = cfg.get("alpha", 0.75)
    return a * u + (1 - a) * t


def _load_json(p: Path, default: dict) -> dict:
    return json.loads(p.read_text()) if p.exists() else default


class SecureClick:
    def __init__(self, models_dir: Path = MODELS):
        self.dir = models_dir
        self.url_cfg = _load_json(models_dir / "url_config.json", {"ensemble_threshold": 0.5})
        self.text_cfg = _load_json(models_dir / "text_config.json", {"threshold": 0.5})
        self.fusion_cfg = _load_json(models_dir / "fusion_config.json",
                                     {"mode": "weighted", "alpha": 0.75, "suspicious": 0.35, "malicious": None})

    # --------------------------------------------------------------- yükleme
    @cached_property
    def rf(self):
        return joblib.load(self.dir / "url_random_forest.joblib")

    @cached_property
    def svm(self):
        return joblib.load(self.dir / "url_svm.joblib")

    @cached_property
    def text_model(self):
        p = self.dir / "text_model.joblib"
        return joblib.load(p) if p.exists() else None

    @cached_property
    def known_threats(self) -> set[str]:
        p = self.dir / "known_threats.txt"
        return set(p.read_text(encoding="utf-8").split()) if p.exists() else set()

    @cached_property
    def popular_domains(self) -> dict[str, int]:
        p = ROOT / "data" / "raw" / "tranco.csv"
        if not p.exists():
            p = self.dir / "tranco_top.csv"
        if not p.exists():
            return {}
        out = {}
        with open(p, encoding="utf-8") as f:
            for rank, dom in csv.reader(f):
                if int(rank) > REPUTATION_TOP_N:
                    break
                out[dom] = int(rank)
        return out

    def warmup(self):
        _ = self.rf, self.svm, self.text_model, self.known_threats, self.popular_domains
        self.score_urls(["ornek.com"])

    @property
    def ready(self) -> bool:
        return (self.dir / "url_random_forest.joblib").exists() and (self.dir / "url_svm.joblib").exists()

    @property
    def malicious_threshold(self) -> float:
        return self.fusion_cfg.get("malicious") or self.url_cfg["ensemble_threshold"]

    # --------------------------------------------------------------- skorlar
    def score_urls(self, urls: list[str]) -> list[dict]:
        p_rf = self.rf.predict_proba(urls)[:, 1]
        p_svm = self.svm.predict_proba(urls)[:, 1]
        return [{"random_forest": float(a), "svm": float(b), "ensemble": float((a + b) / 2)}
                for a, b in zip(p_rf, p_svm)]

    def score_text(self, text: str) -> float | None:
        if not self.text_model or not text.strip():
            return None
        return float(self.text_model.predict_proba([text.replace("\n", " ")])[:, 1][0])

    def _reputation(self, url: str) -> dict | None:
        reg = registered_domain(url)
        if reg in FREE_HOSTING or reg in SHORTENERS:
            return None
        if reg in OFFICIAL_DOMAINS or reg.endswith(".gov.tr"):
            return {"domain": reg, "official": True}
        rank = self.popular_domains.get(reg)
        return {"domain": reg, "rank": rank} if rank else None

    def thresholds(self, with_text: bool) -> tuple[float, float]:
        """(zararlı, şüpheli) eşikleri. Metin yoksa URL topluluğunun kendi eşiği geçerlidir;
        füzyon eşiği yalnızca URL + metin skorları için doğrulama kümesinde ayarlanmıştır."""
        if with_text:
            return self.malicious_threshold, self.fusion_cfg["suspicious"]
        t = self.url_cfg["ensemble_threshold"]
        return t, t * 0.6

    def verdict(self, score: float, with_text: bool = True) -> str:
        mal, sus = self.thresholds(with_text)
        if score >= mal:
            return "malicious"
        if score >= sus:
            return "suspicious"
        return "safe"

    # --------------------------------------------------------------- analiz
    def analyze_url(self, url: str, text_score: float | None = None, live: bool = False) -> dict:
        feats = extract_url_features(url)
        model = self.score_urls([url])[0]
        signals = explain_url(url, feats)
        result = {"url": url, "normalized": normalize_url(url), "registered_domain": registered_domain(url),
                  "model_scores": model, "features": feats}

        known = normalize_url(url) in self.known_threats
        if known:
            signals.insert(0, {"level": "high", "message": "Bu bağlantı açık tehdit listelerinde (PhishTank/URLHaus/OpenPhish) kayıtlı."})

        if live:
            lv = run_live_checks(url, result["registered_domain"])
            result["live"] = lv
            signals += live_signals(lv)
            final = lv.get("redirects", {}).get("final_url")
            if final and normalize_url(final) != normalize_url(url):
                fs = self.score_urls([final])[0]
                result["final_url_scores"] = fs
                if fs["ensemble"] > model["ensemble"]:
                    signals.append({"level": "medium", "message": "Yönlendirilen son adres, ilk adresten daha riskli görünüyor."})

        url_score = max(model["ensemble"], result.get("final_url_scores", {}).get("ensemble", 0))
        score = fuse(url_score, text_score, self.fusion_cfg)
        if live:
            score += sum(LEVEL_BONUS[s["level"]] for s in live_signals(result["live"]))

        rep = self._reputation(url)
        if rep and not known:
            result["reputation"] = rep
            msg = (f"{rep['domain']} kurumun resmî alan adı." if rep.get("official")
                   else f"{rep['domain']} dünyanın en popüler {rep['rank']:,}. sitesi (Tranco).")
            signals.append({"level": "info", "message": msg})
            score *= 0.5  # bilinen, paylaşımsız alan adlarında yanlış alarmı azalt
        if known:
            score = max(score, 0.99)

        score = min(max(score, 0.0), 1.0)
        result.update({"url_score": round(url_score, 4), "score": round(score, 4),
                       "verdict": self.verdict(score, text_score is not None), "signals": signals,
                       "known_threat": known})
        return result

    def analyze(self, message: str = "", url: str = "", live: bool = False) -> dict:
        t0 = time.perf_counter()
        message, url = (message or "").strip(), (url or "").strip()
        urls = ([url] if url else []) + [u for u in extract_urls(message) if u != url]
        text_score = self.score_text(message) if message else None
        text_part = None
        if message:
            tf = extract_text_features(message)
            text_part = {"score": None if text_score is None else round(text_score, 4),
                         "features": tf, "signals": explain_text(message, tf)}

        links = [self.analyze_url(u, text_score, live) for u in urls[:10]]
        severity = {"safe": 0, "suspicious": 1, "malicious": 2}
        if links:
            worst = max(links, key=lambda l: (severity[l["verdict"]], l["score"]))
            score, verdict = worst["score"], worst["verdict"]
        elif text_score is not None:
            # Bağlantısız mesajda doğrudan tıklama riski yok; en fazla 'şüpheli' denir.
            score = text_score
            verdict = "suspicious" if text_score >= self.text_cfg["threshold"] else "safe"
        else:
            score, verdict = 0.0, "safe"
        mal, sus = self.thresholds(text_score is not None)

        return {
            "verdict": verdict, "score": round(score, 4), "links": links, "text": text_part,
            "thresholds": {"malicious": mal, "suspicious": sus},
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
