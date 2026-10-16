"""Mesaj metni (SMS / e-posta / sosyal medya) için Türkçe NLP özellikleri."""
from __future__ import annotations

import re

_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})
_TR_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")

URL_RE = re.compile(
    r"""(?xi)
    \b(
      (?:https?://|www\.)[^\s<>"'()]+                       # şemalı veya www.
      |
      (?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+            # şemasız: alan.tld/yol
      (?:com|net|org|info|biz|xyz|top|site|online|live|shop|link|click|ly|gl|co|me|io|app|
         tr|com\.tr|gov\.tr|ru|cn|tk|ml|ga|cf|gq|icu|cc|to|in|us|eu|de|uk|vip|pro|club)
      (?:/[^\s<>"'()]*)?
    )
    """
)

# "hemen tıklayın", "hesabınız kapatılacak" vb. (ASCII'ye indirgenmiş biçimde)
URGENCY_PATTERNS = [
    r"hemen", r"acil", r"son gun", r"son \d+ saat", r"24 saat", r"bugun icinde",
    r"derhal", r"simdi tikla", r"tiklayin", r"tiklayiniz", r"linke tikla", r"son firsat",
    r"sinirli sure", r"gecikmeden", r"aksi (halde|takdirde)",
]
THREAT_PATTERNS = [
    r"kapatila", r"askiya", r"bloke", r"iptal edil", r"dondurul", r"engellen", r"ceza",
    r"icra", r"haciz", r"yasal islem", r"borcunuz", r"odenmemis", r"gecikme", r"suspend",
    r"tebligat", r"sorusturma", r"mahkeme",
]
LURE_PATTERNS = [
    r"kazandiniz", r"kazandin", r"hediye", r"odul", r"ikramiye", r"bedava", r"ucretsiz",
    r"bonus", r"cekilis", r"tebrikler", r"\bpara iadesi", r"iade", r"indirim", r"kampanya",
    r"freespin", r"bahis", r"casino", r"deneme bonusu",
]
CREDENTIAL_PATTERNS = [
    r"sifre", r"parola", r"tc kimlik", r"kimlik no", r"kart bilgi", r"kart numara", r"cvv",
    r"dogrulama kodu", r"onay kodu", r"giris yap", r"bilgilerinizi guncelle", r"hesap bilgi",
    r"iban", r"e-?devlet",
]
IMPERSONATION_PATTERNS = [
    r"\bptt\b", r"kargo", r"yurtici", r"aras kargo", r"mng", r"gonderiniz", r"paketiniz",
    r"e-?devlet", r"\bsgk\b", r"\bgib\b", r"vergi", r"\bhgs\b", r"\bogs\b", r"banka",
    r"garanti", r"akbank", r"ziraat", r"is bankasi", r"yapi kredi", r"halkbank", r"vakifbank",
    r"turkcell", r"vodafone", r"turk telekom", r"emniyet", r"jandarma",
]

POSITIVE_WORDS = ["tebrik", "kazan", "hediye", "firsat", "mutlu", "harika", "ucretsiz",
                  "bedava", "indirim", "odul", "sevgi", "tesekkur", "guzel"]
NEGATIVE_WORDS = ["kapat", "iptal", "ceza", "borc", "sorun", "hata", "askiya", "bloke",
                  "uyari", "gecikme", "icra", "haciz", "tehlike", "risk", "maalesef"]

TEXT_FEATURE_NAMES = [
    "msg_len", "n_words", "n_urls", "n_digits", "upper_ratio", "n_exclaim",
    "urgency", "threat", "lure", "credential", "impersonation", "sentiment",
    "has_phone", "has_amount",
]


def normalize_tr(text: str) -> str:
    """Türkçe-duyarlı küçük harf + ASCII'ye indirgeme + noktalama temizliği (öneri formu)."""
    t = text.translate(_TR_LOWER).lower().translate(_TR_ASCII)
    t = URL_RE.sub(" urltoken ", t)
    t = re.sub(r"\d+", " 0 ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _ascii_lower(text: str) -> str:
    return text.translate(_TR_LOWER).lower().translate(_TR_ASCII)


def extract_urls(text: str) -> list[str]:
    urls = []
    for m in URL_RE.finditer(text):
        u = m.group(1).rstrip(".,;:!?)]}")
        if "@" in u.split("/")[0] and not u.lower().startswith("http"):
            continue  # e-posta adresi
        urls.append(u)
    return list(dict.fromkeys(urls))


def _count(patterns: list[str], text: str) -> int:
    return sum(bool(re.search(p, text)) for p in patterns)


def extract_text_features(text: str) -> dict[str, float]:
    a = _ascii_lower(text)
    words = a.split()
    letters = [c for c in text if c.isalpha()]
    pos = sum(w in a for w in POSITIVE_WORDS)
    neg = sum(w in a for w in NEGATIVE_WORDS)
    return {
        "msg_len": len(text),
        "n_words": len(words),
        "n_urls": len(extract_urls(text)),
        "n_digits": sum(c.isdigit() for c in text),
        "upper_ratio": sum(c.isupper() for c in letters) / max(len(letters), 1),
        "n_exclaim": text.count("!"),
        "urgency": _count(URGENCY_PATTERNS, a),
        "threat": _count(THREAT_PATTERNS, a),
        "lure": _count(LURE_PATTERNS, a),
        "credential": _count(CREDENTIAL_PATTERNS, a),
        "impersonation": _count(IMPERSONATION_PATTERNS, a),
        # -1 (tamamen olumsuz) ... +1 (tamamen olumlu); 0 = nötr
        "sentiment": (pos - neg) / max(pos + neg, 1),
        "has_phone": int(bool(re.search(r"(\+?90|0)?\s?5\d{2}\s?\d{3}\s?\d{2}\s?\d{2}", text))),
        "has_amount": int(bool(re.search(r"\d+[.,]?\d*\s?(tl|₺|try|lira|usd|\$|eur|€)", a))),
    }


def explain_text(text: str, feats: dict[str, float] | None = None) -> list[dict]:
    f = feats or extract_text_features(text)
    out = []
    if f["credential"]:
        out.append({"level": "high", "message": "Mesaj şifre, kart veya kimlik bilgisi istiyor."})
    if f["threat"]:
        out.append({"level": "high", "message": "Tehdit/ceza ifadesi var (hesap kapatma, icra, bloke vb.)."})
    if f["urgency"]:
        out.append({"level": "medium", "message": "Aciliyet baskısı kuruluyor ('hemen', '24 saat' vb.)."})
    if f["lure"]:
        out.append({"level": "medium", "message": "Ödül/hediye/iade vaadiyle cezbetme girişimi."})
    if f["impersonation"]:
        out.append({"level": "medium", "message": "Kurum adı geçiyor (kargo, banka, e-Devlet vb.); gönderen doğrulanmalı."})
    if f["sentiment"] <= -0.5 and (f["threat"] or f["urgency"]):
        out.append({"level": "low", "message": "Mesajın genel tonu olumsuz ve baskı içeriyor."})
    return out
