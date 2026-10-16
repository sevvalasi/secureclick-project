"""Güvenli (benign) URL'leri popüler sitelerin herkese açık sitemap'lerinden toplar.

Neden? Tranco yalnızca alan adı verir ("google.com"). Sadece ana sayfaları güvenli sınıf
olarak kullanmak, modelin "kısa URL = güvenli, uzun URL = zararlı" gibi sahte bir kestirme
öğrenmesine yol açar. Sitemap'ler ise site sahibinin yayımladığı gerçek, derin yollu
URL'leri içerir; böylece iki sınıfın URL uzunluk/yol dağılımları birbirine yaklaşır.

Kullanım:  python -m ml.collect_benign [--domains 6000] [--per-domain 25]
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SecureClick-research/1.0)"}
LOC_RE = re.compile(rb"<loc>\s*(.*?)\s*</loc>", re.I | re.S)
TIMEOUT = 6
MAX_BYTES = 40_000      # 25 URL için sitemap'in başı yeterli
DOMAIN_BUDGET = 25       # alan adı başına en fazla süre (sn)


def _get(url: str) -> bytes | None:
    """İlk MAX_BYTES baytı okur; .gz ise kısmi olarak açar (yarım XML regex için yeterli)."""
    try:
        with requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
            if r.status_code != 200:
                return None
            body, deadline = b"", time.monotonic() + TIMEOUT * 2
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) >= MAX_BYTES or time.monotonic() > deadline:
                    break
        if body[:2] == b"\x1f\x8b":
            body = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(body, MAX_BYTES * 8)
        return body
    except Exception:
        return None


def _locs(xml: bytes) -> list[str]:
    out = []
    for m in LOC_RE.findall(xml):
        s = m.decode("utf-8", "ignore").strip()
        s = s.replace("<![CDATA[", "").replace("]]>", "").replace("&amp;", "&")
        if s.startswith("http"):
            out.append(s)
    return out


def sitemap_urls(domain: str, per_domain: int, rng: random.Random) -> list[str]:
    candidates: list[str] = []
    robots = _get(f"https://{domain}/robots.txt")
    if robots:
        for line in robots.decode("utf-8", "ignore").splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    if not candidates:
        candidates = [f"https://{domain}/sitemap.xml"]

    pages: list[str] = []
    start = time.monotonic()
    for sm in candidates[:3]:
        if time.monotonic() - start > DOMAIN_BUDGET:
            break
        body = _get(sm)
        if not body:
            continue
        locs = _locs(body)
        if b"<sitemapindex" in body[:2000].lower():
            # sitemap index: rastgele birkaç alt sitemap'e in
            for child in rng.sample(locs, min(2, len(locs))):
                if time.monotonic() - start > DOMAIN_BUDGET:
                    break
                child_body = _get(child)
                if child_body:
                    pages.extend(_locs(child_body))
        else:
            pages.extend(locs)
        if len(pages) >= per_domain * 4:
            break

    pages = [p for p in dict.fromkeys(pages) if not p.endswith((".xml", ".xml.gz"))]
    return rng.sample(pages, min(per_domain, len(pages)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", type=int, default=6000, help="Tranco'dan alınacak üst alan adı sayısı")
    ap.add_argument("--tr-domains", type=int, default=1500, help="ek olarak alınacak .tr alan adı sayısı")
    ap.add_argument("--per-domain", type=int, default=25)
    ap.add_argument("--workers", type=int, default=48)
    args = ap.parse_args()

    rng = random.Random(42)
    rows = list(csv.reader(open(RAW / "tranco.csv", encoding="utf-8")))
    top = [d for _, d in rows[: args.domains]]
    tr = [d for _, d in rows if d.endswith(".tr") and d not in top][: args.tr_domains]
    domains = top + tr
    print(f"{len(domains)} alan adı taranacak ({len(tr)} tanesi .tr)")

    out_path = RAW / "benign_sitemap.csv"
    done: set[str] = set()
    if out_path.exists():  # kaldığı yerden devam
        done = {r["domain"] for r in csv.DictReader(open(out_path, encoding="utf-8"))
                if r["source"] in ("sitemap", "tried")}
    todo = [d for d in domains if d not in done]
    print(f"{len(done)} alan adı daha önce taranmış, {len(todo)} kaldı")
    found = 0
    new_file = not out_path.exists()
    with open(out_path, "a", newline="", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as pool:
        w = csv.writer(f)
        if new_file:
            w.writerow(["url", "domain", "source"])
            for d in domains:  # ana sayfalar da güvenli sınıfın parçası
                w.writerow([f"https://{d}/", d, "tranco_home"])
        domains = todo
        futures = {pool.submit(sitemap_urls, d, args.per_domain, random.Random(hash(d))): d for d in domains}
        for i, fut in enumerate(as_completed(futures), 1):
            d = futures[fut]
            urls = fut.result()
            found += len(urls)
            for u in urls:
                w.writerow([u, d, "sitemap"])
            w.writerow(["", d, "tried"])  # devam için işaret; veri setine girmez
            if i % 250 == 0:
                print(f"  {i}/{len(domains)} alan adı, {found} sitemap URL'si")
                f.flush()
    print(f"Bitti: {found} sitemap URL'si + {len(domains)} ana sayfa -> {out_path}")


if __name__ == "__main__":
    main()
