"""Ham kaynakları birleştirip temizlenmiş, dengeli ve bölünmüş URL veri setini üretir.

Adımlar (öneri formu, Yöntem §2):
  1. Veri temizleme      : boş/geçersiz/tekrarlayan kayıtların atılması
  2. URL normalizasyonu  : şema ve 'www.' önekinin, sondaki '/'in standartlaştırılması
  3. Çakışma temizliği   : hem zararlı hem güvenli listede geçen URL'lerin atılması
  4. Dengeleme           : sınıf başına en fazla N örnek (varsayılan 50.000)
  5. Bölme               : %80 eğitim / %10 doğrulama / %10 test, katmanlı (stratified)
                           ve alan adına göre gruplu (aynı site iki kümede birden olmaz)

Çıktı: data/processed/urls.csv  (url, norm, label, source, timestamp, group, split)
Kullanım:  python -m ml.build_dataset [--per-class 50000]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from secureclick.features.url_features import group_key, normalize_url

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"


def load_malicious() -> pd.DataFrame:
    pt = pd.read_csv(RAW / "phishtank.csv", usecols=["url", "submission_time", "verified"])
    pt = pt[pt.verified == "yes"].rename(columns={"submission_time": "timestamp"})
    pt["source"] = "phishtank"

    uh = pd.read_csv(RAW / "urlhaus.csv", comment="#", header=None,
                     names=["id", "dateadded", "url", "url_status", "last_online", "threat",
                            "tags", "urlhaus_link", "reporter"])
    uh = uh.rename(columns={"dateadded": "timestamp"})
    uh["source"] = "urlhaus"

    op = pd.read_csv(RAW / "openphish.txt", header=None, names=["url"])
    op["timestamp"] = pd.Timestamp.now(tz="UTC").isoformat()
    op["source"] = "openphish"

    df = pd.concat([d[["url", "timestamp", "source"]] for d in (pt, uh, op)], ignore_index=True)
    df["label"] = 1
    return df


def load_benign() -> pd.DataFrame:
    files = [RAW / "benign_sitemap.csv", RAW / "benign_cc.csv"]
    df = pd.concat([pd.read_csv(f, usecols=["url", "domain", "source"]) for f in files if f.exists()],
                   ignore_index=True)
    homes = pd.DataFrame({"url": "https://" + df["domain"].dropna().drop_duplicates() + "/", "source": "home"})
    df = df[df["source"].isin(["sitemap", "commoncrawl"])]
    df = pd.concat([df[["url", "source"]], homes], ignore_index=True)
    df["source"] = "tranco_" + df["source"]
    df["timestamp"] = pd.NaT
    df["label"] = 0
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["url"]).copy()
    df["url"] = df["url"].astype(str).str.strip()
    df = df[df["url"].str.len().between(4, 2000)]
    df = df[~df["url"].str.contains(r"\s", regex=True)]
    df["norm"] = df["url"].map(normalize_url)
    df = df[df["norm"].str.contains(r"\.", regex=True) | df["norm"].str.contains(r"^\d", regex=True)]
    return df.drop_duplicates(subset=["norm", "label"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    mal, ben = clean(load_malicious()), clean(load_benign())
    print(f"Temizlik sonrası: {len(mal):,} zararlı, {len(ben):,} güvenli")

    conflict = set(mal["norm"]) & set(ben["norm"])
    if conflict:
        print(f"Her iki listede de geçen {len(conflict)} URL atılıyor")
        mal, ben = mal[~mal["norm"].isin(conflict)], ben[~ben["norm"].isin(conflict)]

    n = min(args.per_class, len(mal), len(ben))
    rng = np.random.default_rng(args.seed)
    # Zararlı sınıfta kaynakları dengeli tut: OpenPhish'in hepsi, kalan PhishTank/URLHaus'tan
    # yarı yarıya (mümkün olduğunca).
    op = mal[mal.source == "openphish"]
    rest = n - len(op)
    pt, uh = mal[mal.source == "phishtank"], mal[mal.source == "urlhaus"]
    n_uh = min(len(uh), rest // 2)
    n_pt = min(len(pt), rest - n_uh)
    n_uh = min(len(uh), rest - n_pt)
    mal = pd.concat([op, pt.sample(n_pt, random_state=args.seed), uh.sample(n_uh, random_state=args.seed)])
    # Ana sayfalar güvenli sınıfın en fazla %10'u olsun; aksi hâlde "kısa URL = güvenli"
    # kestirmesi geri gelir.
    homes, deep = ben[ben.source == "tranco_home"], ben[ben.source != "tranco_home"]
    n_deep = min(len(deep), int(len(mal) * 0.90))
    n_home = min(len(homes), n_deep // 9)  # ana sayfa ≤ güvenli sınıfın %10'u
    ben = pd.concat([homes.sample(n_home, random_state=args.seed), deep.sample(n_deep, random_state=args.seed)])
    if len(ben) < len(mal):
        print(f"Uyarı: yeterli güvenli URL yok; zararlı sınıf {len(ben):,} örneğe indiriliyor")
        mal = mal.sample(len(ben), random_state=args.seed)

    df = pd.concat([mal, ben], ignore_index=True).sample(frac=1, random_state=args.seed)
    df["group"] = df["url"].map(group_key)

    # Katmanlı + gruplu bölme: 10 kat -> 8 eğitim, 1 doğrulama, 1 test
    sgkf = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=args.seed)
    fold = np.empty(len(df), dtype=int)
    for k, (_, idx) in enumerate(sgkf.split(df, df["label"], df["group"])):
        fold[idx] = k
    df["split"] = np.select([fold == 8, fold == 9], ["val", "test"], "train")

    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["url", "norm", "label", "source", "timestamp", "group", "split"]
    df[cols].to_csv(OUT / "urls.csv", index=False)

    print(f"\nToplam {len(df):,} URL -> {OUT / 'urls.csv'}")
    print(pd.crosstab(df["split"], df["label"], margins=True).rename(columns={0: "güvenli", 1: "zararlı"}))
    print("\nKaynaklar:\n", df["source"].value_counts().to_string())
    print(f"\nFarklı grup (site) sayısı: {df['group'].nunique():,}")


if __name__ == "__main__":
    main()
