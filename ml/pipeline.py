"""Tüm hattı sırayla çalıştırır: veri indirme -> güvenli URL toplama -> veri seti ->
senaryolar -> URL modelleri -> metin modelleri -> füzyon/hipotez değerlendirmesi.

Kullanım:  python -m ml.pipeline [--skip-download] [--skip-cv] [--quick]
"""
from __future__ import annotations

import subprocess
import sys

STEPS = [
    ("download", ["-m", "ml.download_data"]),
    ("benign", ["-m", "ml.collect_benign"]),
    ("benign_cc", ["-m", "ml.collect_benign_cc"]),
    ("dataset", ["-m", "ml.build_dataset"]),
    ("scenarios", ["-m", "ml.generate_tr_scenarios"]),
    ("url", ["-m", "ml.train_url_models"]),
    ("text", ["-m", "ml.train_text_models"]),
    ("fusion", ["-m", "ml.evaluate_fusion"]),
]


def main():
    args = sys.argv[1:]
    skip = {"download", "benign", "benign_cc"} if "--skip-download" in args else set()
    for name, cmd in STEPS:
        if name in skip:
            continue
        if name == "url":
            cmd = cmd + [a for a in args if a in ("--skip-cv", "--quick")]
        print(f"\n===== {name} =====", flush=True)
        subprocess.run([sys.executable, "-u", *cmd], check=True)


if __name__ == "__main__":
    main()
