"""SecureClick RESTful API + web arayüzü.

Çalıştırma:  uvicorn api.main:app --reload
Uç noktalar:
  POST /api/analyze   {"message": "...", "url": "...", "live_checks": false}
  GET  /api/metrics   eğitim/değerlendirme raporları
  GET  /api/health    servis ve model durumu
  GET  /docs          otomatik Swagger dokümantasyonu
"""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from secureclick.predictor import SecureClick

ROOT = Path(__file__).resolve().parents[1]
WEB, REPORTS = ROOT / "web", ROOT / "reports"
engine = SecureClick()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine.ready:
        engine.warmup()  # ilk istekte model yükleme gecikmesi olmasın
    yield


app = FastAPI(title="SecureClick API", version="1.0.0", lifespan=lifespan,
              description="Yapay zekâ destekli zararlı bağlantı tespit sistemi (TÜBİTAK 2209-A)")
# Android test uygulaması ve tarayıcı eklentileri için
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


class AnalyzeRequest(BaseModel):
    message: str = Field("", max_length=5000, description="SMS / e-posta / sosyal medya mesajı")
    url: str = Field("", max_length=2048, description="Tek başına kontrol edilecek bağlantı")
    live_checks: bool = Field(False, description="Yönlendirme, SSL ve WHOIS kontrollerini çalıştır")

    @model_validator(mode="after")
    def _non_empty(self):
        if not self.message.strip() and not self.url.strip():
            raise ValueError("'message' veya 'url' alanlarından en az biri dolu olmalı")
        return self


# Basit IP başına hız sınırı: dakikada 30 istek
_hits: dict[str, deque] = defaultdict(deque)
RATE_LIMIT, WINDOW = 30, 60.0


def _rate_limit(ip: str):
    q, now = _hits[ip], time.monotonic()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "Çok fazla istek; lütfen bir dakika sonra tekrar deneyin.")
    q.append(now)


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, request: Request):
    if not engine.ready:
        raise HTTPException(503, "Modeller henüz eğitilmemiş. README'deki eğitim adımlarını çalıştırın.")
    _rate_limit(request.client.host if request.client else "?")
    return engine.analyze(message=req.message, url=req.url, live=req.live_checks)


@app.get("/api/metrics")
def get_metrics():
    out = {}
    for name in ("url_metrics", "text_metrics", "fusion_metrics"):
        p = REPORTS / f"{name}.json"
        out[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return out


@app.get("/api/health")
def health():
    return {"status": "ok", "models_ready": engine.ready, "text_model": engine.text_model is not None,
            "known_threats": len(engine.known_threats) if engine.ready else 0}


app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")
