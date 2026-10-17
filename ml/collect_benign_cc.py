"""Güvenli URL'leri Common Crawl CDX indeksinden toplar (collect_benign.py'ye alternatif/ek).

Common Crawl, web'in herkese açık arşividir. Her Tranco alan adı için son taramada
HTTP 200 dönen HTML sayfalarının URL'leri sorgulanır. Yanıt küçük olduğundan (alan adı
başına ~20 KB) yavaş bağlantılarda site haritası taramasından çok daha verimlidir.

Sonuçlar data/raw/benign_cc.csv dosyasına source='commoncrawl' olarak eklenir
(site haritası toplayıcısıyla aynı anda çalışabilsin diye ayrı dosya).
Kullanım:  python -m ml.collect_benign_cc [--target 50000] [--per-domain 25]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {"User-Agent": "SecureClick-research/1.0 (TUBITAK 2209-A student project)"}


def latest_index() -> str:
    r = requests.get("https://index.commoncrawl.org/collinfo.json", headers=HEADERS, timeout=30)
    return r.json()[0]["cdx-api"]


def query(api: str, domain: str, per_domain: int, rng: random.Random) -> list[str]:
    params = {"url": f"{domain}/*", "output": "json", "limit": 300, "fl": "url",
              "filter": ["status:200", "mime:text/html"], "collapse": "urlkey"}
    for attempt in range(4):
        try:
            r = requests.get(api, params=params, headers=HEADERS, timeout=40)
            if r.status_code == 404:  # alan adı bu taramada yok
                return []
            if r.status_code in (503, 429):
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            urls = [json.loads(line)["url"] for line in r.text.splitlines() if line.strip()]
            urls = [u for u in dict.fromkeys(urls) if "robots.txt" not in u]
            return rng.sample(urls, min(per_domain, len(urls)))
        except (requests.RequestException, ValueError):
            time.sleep(3 * (attempt + 1))
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50_000, help="toplam güvenli URL hedefi")
    ap.add_argument("--per-domain", type=int, default=25)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--tr-share", type=float, default=0.2, help="Türk (.tr) alan adı oranı")
    args = ap.parse_args()

    out = RAW / "benign_cc.csv"
    have, done = 0, set()
    for path in (RAW / "benign_sitemap.csv", out):
        if not path.exists():
            continue
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if r["source"] in ("sitemap", "commoncrawl"):
                have += 1
            if r["source"] in ("commoncrawl", "cc_tried"):
                done.add(r["domain"])
    need = args.target - have
    print(f"Mevcut {have:,} URL; hedefe {max(need, 0):,} kaldı")
    if need <= 0:
        return

    rows = list(csv.reader(open(RAW / "tranco.csv", encoding="utf-8")))
    top = [d for _, d in rows[:60000] if d not in done]
    tr = [d for _, d in rows if d.endswith(".tr") and d not in done][:4000]
    n_dom = need // max(args.per_domain // 2, 1) + 200  # her alan adı ortalama ~yarısı kadar verir
    n_tr = int(n_dom * args.tr_share)
    domains = list(dict.fromkeys(tr[:n_tr] + top[: n_dom - n_tr]))
    random.Random(0).shuffle(domains)

    api = latest_index()
    print(f"İndeks: {api}\n{len(domains)} alan adı sorgulanacak ({args.workers} paralel)")
    new_file = not out.exists()
    got = 0
    with open(out, "a", newline="", encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as pool:
        w = csv.writer(f)
        if new_file:
            w.writerow(["url", "domain", "source"])
        futs = {pool.submit(query, api, d, args.per_domain, random.Random(d)): d for d in domains}
        for i, fut in enumerate(as_completed(futs), 1):
            d = futs[fut]
            urls = fut.result()
            for u in urls:
                w.writerow([u, d, "commoncrawl"])
            w.writerow(["", d, "cc_tried"])
            got += len(urls)
            if i % 50 == 0:
                f.flush()
                print(f"  {i}/{len(domains)} alan adı, +{got:,} URL (toplam {have + got:,})", flush=True)
            if have + got >= args.target:
                print("Hedefe ulaşıldı, kalan sorgular iptal ediliyor")
                for x in futs:
                    x.cancel()
                break
    print(f"Bitti: +{got:,} URL -> {out}")


if __name__ == "__main__":
    main()
