#!/usr/bin/env bash
# SecureClick web sunucusunu başlatır: http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
if [ ! -f models/url_random_forest.joblib ]; then
  echo "Modeller bulunamadı; eğitim hattı çalıştırılıyor (ilk seferde uzun sürebilir)…"
  .venv/bin/python -m ml.pipeline
fi
exec .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
