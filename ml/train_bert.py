"""İSTEĞE BAĞLI — BERTurk ile Türkçe mesaj sınıflandırıcısı ince ayarı (öneri formu §4.2).

Kurulum:   pip install -r requirements-bert.txt
Çalıştırma: python -m ml.train_bert [--epochs 3] [--model dbmdz/bert-base-turkish-cased]

Veri ve bölmeler ml/train_text_models.py ile aynıdır, böylece sonuçlar TF-IDF modelleriyle
doğrudan (McNemar dahil) karşılaştırılabilir. Erken durdurma doğrulama F1'ine göre yapılır.
Apple Silicon'da 'mps', NVIDIA'da 'cuda' otomatik kullanılır; CPU'da 1 epoch ~20-40 dk sürebilir.
Google Colab (ücretsiz GPU) üzerinde çalıştırmak önerilir.

Çıktılar: models/bert/ (model + tokenizer), reports/bert_metrics.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.train_text_models import load_sms
from secureclick.evaluation import best_threshold, metrics

ROOT = Path(__file__).resolve().parents[1]


def main():
    import torch
    from datasets import Dataset
    from sklearn.model_selection import train_test_split
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, EarlyStoppingCallback,
                              Trainer, TrainingArguments)

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dbmdz/bert-base-turkish-cased")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=128)
    args = ap.parse_args()

    sms = load_sms()
    sc = pd.read_csv(ROOT / "data" / "processed" / "tr_scenarios.csv")
    sc["text"] = sc["text"].str.replace("{url}", "[URL]", regex=False)
    sms_tr, sms_te = train_test_split(sms, test_size=0.2, stratify=sms.label, random_state=42)
    sms_tr, sms_va = train_test_split(sms_tr, test_size=0.125, stratify=sms_tr.label, random_state=42)
    train = pd.concat([sms_tr, sc[sc.split == "train"][["text", "label"]]], ignore_index=True)
    sc_test = sc[sc.split == "test"]

    tok = AutoTokenizer.from_pretrained(args.model)
    enc = lambda df: Dataset.from_pandas(df[["text", "label"]].reset_index(drop=True)).map(
        lambda b: tok(b["text"], truncation=True, max_length=args.max_len), batched=True)
    ds_tr, ds_va = enc(train), enc(sms_va)

    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)

    def compute(eval_pred):
        logits, labels = eval_pred
        p = torch.softmax(torch.tensor(logits), -1)[:, 1].numpy()
        return {"f1": metrics(labels, p)["f1"]}

    out_dir = ROOT / "models" / "bert"
    trainer = Trainer(
        model=model,
        args=TrainingArguments(output_dir=str(out_dir / "ckpt"), num_train_epochs=args.epochs,
                               per_device_train_batch_size=args.batch, per_device_eval_batch_size=64,
                               learning_rate=2e-5, weight_decay=0.01, warmup_ratio=0.1,
                               eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
                               metric_for_best_model="f1", save_total_limit=1, report_to=[], seed=42),
        train_dataset=ds_tr, eval_dataset=ds_va, processing_class=tok, compute_metrics=compute,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=1)],  # aşırı öğrenmeyi önle
    )
    trainer.train()

    def predict(df):
        logits = trainer.predict(enc(df)).predictions
        return torch.softmax(torch.tensor(logits), -1)[:, 1].numpy()

    pv = predict(sms_va)
    thr = best_threshold(sms_va.label, pv, min_recall=0.9)
    report = {"model": args.model, "threshold": thr,
              "test_sms": metrics(sms_te.label, predict(sms_te), thr),
              "test_scenarios_unseen_templates": metrics(sc_test.label, predict(sc_test), thr)}
    trainer.save_model(str(out_dir))
    tok.save_pretrained(str(out_dir))
    json.dump(report, open(ROOT / "reports" / "bert_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
