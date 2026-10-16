"""Açık kaynak veri setlerini data/raw/ altına indirir.

Kaynaklar:
  - PhishTank   : doğrulanmış, çevrim içi kimlik avı URL'leri
  - URLHaus     : son 30 günde raporlanan zararlı yazılım URL'leri
  - OpenPhish   : ücretsiz kimlik avı akışı
  - Tranco      : en popüler 1M alan adı (güvenli URL toplamak için tohum liste)
  - TurkishSMSCollection (Karasoy & Ballı, 2021): Türkçe spam/normal SMS

Kullanım:  python -m ml.download_data
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

SOURCES = {
    "phishtank.csv": "https://data.phishtank.com/data/online-valid.csv",
    "urlhaus.csv": "https://urlhaus.abuse.ch/downloads/csv_recent/",
    "openphish.txt": "https://openphish.com/feed.txt",
    "turkish_sms.csv": "https://raw.githubusercontent.com/onrkrsy/TurkishSMS-Collection/main/TurkishSMSCollection.csv",
}
TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"
HEADERS = {"User-Agent": "SecureClick-research/1.0 (TUBITAK 2209-A student project)"}


def fetch(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.content


def main(force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        target = RAW / name
        if target.exists() and not force:
            print(f"[=] {name} zaten var, atlanıyor")
            continue
        print(f"[↓] {name} <- {url}")
        target.write_bytes(fetch(url))
        print(f"    {target.stat().st_size / 1e6:.1f} MB")

    tranco = RAW / "tranco.csv"
    if force or not tranco.exists():
        print(f"[↓] tranco.csv <- {TRANCO_URL}")
        with zipfile.ZipFile(io.BytesIO(fetch(TRANCO_URL))) as zf:
            tranco.write_bytes(zf.read(zf.namelist()[0]))
        print(f"    {tranco.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
