"""URL tabanlı (sözcüksel) özellik çıkarımı.

Burada yalnızca URL dizgisinin kendisinden hesaplanabilen özellikler vardır. Ağ erişimi
gerektiren sinyaller (alan adı yaşı, SSL, yönlendirme zinciri) `secureclick.live_checks`
içindedir ve tahmin anında ek risk katmanı olarak kullanılır. Böylece eğitim verisi ile
canlı kullanım arasında özellik tutarsızlığı (train/serve skew) oluşmaz.

Esinlenilen çalışmalar: Ma vd. (2009), Sahoo vd. (2019), Le vd. (URLNet, 2020).
"""
from __future__ import annotations

import ipaddress
import math
import re
from collections import Counter
from functools import lru_cache
from urllib.parse import unquote, urlsplit

import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=())  # paketle gelen PSL; ağ erişimi yok

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "cutt.ly",
    "rebrand.ly", "shorturl.at", "tiny.cc", "rb.gy", "t.ly", "s.id", "v.gd", "bl.ink",
    "lnkd.in", "shorte.st", "adf.ly", "bitly.com", "qrco.de", "urlkisalt.com", "kisa.link",
    "u.to", "clck.ru", "tr.im", "x.co", "trib.al", "short.gy", "linktr.ee",
    # QR kod kısaltıcıları (quishing'de yaygın)
    "qrco.de", "ead.me", "q-r.to", "qr.link", "l.ead.me", "qr1.be", "me-qr.com",
}

# Herkesin alt alan adı açabildiği barındırma platformları: kimlik avında sık kullanılır.
FREE_HOSTING = {
    "jimdofree.com", "weebly.com", "wixsite.com", "000webhostapp.com", "firebaseapp.com",
    "web.app", "pages.dev", "vercel.app", "netlify.app", "github.io", "blogspot.com",
    "glitch.me", "herokuapp.com", "repl.co", "replit.dev", "webflow.io", "square.site",
    "godaddysites.com", "mystrikingly.com", "wordpress.com", "sites.google.com",
    "azurewebsites.net", "workers.dev", "ngrok.io", "ngrok-free.app", "duckdns.org",
    "r2.dev", "framer.app", "carrd.co", "gitbook.io", "webcindario.com", "tilda.ws",
    "yolasite.com", "ukit.me", "site123.me", "myshopify.com", "appspot.com", "onrender.com",
    "githubusercontent.com", "wixstudio.com", "notion.site", "dropboxusercontent.com",
}

# İçeriğin sahibini host değil yolun ilk parçasının belirlediği paylaşımlı platformlar
# (ör. raw.githubusercontent.com/<kullanıcı>/..., docs.google.com/forms/d/<id>).
PATH_OWNED = {"githubusercontent.com", "github.com", "google.com", "dropbox.com",
              "dropboxusercontent.com", "googleapis.com", "wixstudio.com", "canva.com",
              "linkedin.com", "facebook.com", "t.me", "discord.gg", "discord.com"} | SHORTENERS

SUSPICIOUS_TLDS = {
    "zip", "mov", "xyz", "top", "click", "link", "work", "support", "rest", "fit", "tk",
    "ml", "ga", "cf", "gq", "icu", "cyou", "buzz", "sbs", "cfd", "monster", "quest",
    "online", "site", "live", "shop", "info", "lol", "bond", "country", "cam", "best",
}

SUSPICIOUS_WORDS = [
    "login", "log-in", "signin", "sign-in", "verify", "verification", "secure", "account",
    "update", "confirm", "password", "banking", "wallet", "webscr", "ebayisapi", "auth",
    "recover", "unlock", "suspend", "billing", "invoice", "payment", "refund", "support",
    # Türkçe
    "giris", "dogrula", "dogrulama", "guvenlik", "hesap", "sifre", "odeme", "iade", "kargo",
    "ceza", "borc", "aidat", "tebligat", "kazandiniz", "hediye", "kampanya", "basvuru",
]

# Taklit edilen markalar (kayıtlı alan adının dışında geçiyorsa şüphelidir)
BRANDS = [
    "paypal", "apple", "icloud", "microsoft", "office365", "outlook", "google", "amazon",
    "netflix", "facebook", "instagram", "whatsapp", "telegram", "binance", "coinbase",
    "metamask", "dhl", "fedex", "ups", "usps", "chase", "wellsfargo", "steam", "roblox",
    # Türkiye
    "garanti", "akbank", "ziraat", "isbank", "yapikredi", "halkbank", "vakifbank",
    "qnb", "enpara", "denizbank", "teb", "kuveytturk", "ptt", "edevlet", "e-devlet", "turkiye",
    "hepsiburada", "trendyol", "n11", "yurtici", "aras", "mng", "turkcell", "vodafone",
    "turktelekom", "sahibinden", "getir", "papara", "ininal", "sgk", "gib", "hgs", "ogs",
]

# Markaların resmî kayıtlı alan adları; bunların dışında marka adı geçen host şüphelidir.
OFFICIAL_DOMAINS = {
    "paypal.com", "apple.com", "icloud.com", "microsoft.com", "office.com", "office365.com", "live.com",
    "outlook.com", "google.com", "amazon.com", "amazon.com.tr", "netflix.com", "facebook.com",
    "instagram.com", "whatsapp.com", "telegram.org", "binance.com", "binance.tr", "coinbase.com",
    "metamask.io", "dhl.com", "dhl.com.tr", "fedex.com", "ups.com", "usps.com", "chase.com",
    "wellsfargo.com", "steampowered.com", "steamcommunity.com", "roblox.com",
    "garantibbva.com.tr", "garanti.com.tr", "akbank.com", "ziraatbank.com.tr", "ziraat.com.tr",
    "isbank.com.tr", "yapikredi.com.tr", "halkbank.com.tr", "vakifbank.com.tr", "qnb.com.tr",
    "enpara.com", "denizbank.com", "teb.com.tr", "kuveytturk.com.tr", "ptt.gov.tr", "pttbank.com.tr",
    "turkiye.gov.tr", "hepsiburada.com", "trendyol.com", "n11.com", "yurticikargo.com",
    "araskargo.com.tr", "mngkargo.com.tr", "turkcell.com.tr", "vodafone.com.tr", "vodafone.com",
    "turktelekom.com.tr", "sahibinden.com", "getir.com", "papara.com", "ininal.com",
}

RISKY_EXTENSIONS = (".exe", ".apk", ".sh", ".bin", ".scr", ".bat", ".cmd", ".msi", ".jar",
                    ".vbs", ".ps1", ".dll", ".zip", ".rar", ".7z", ".iso", ".arm", ".mips",
                    ".x86", ".mpsl", ".m68k", ".ppc", ".i686")

FEATURE_NAMES = [
    "url_len", "host_len", "path_len", "query_len", "n_dots", "n_hyphens", "n_underscores",
    "n_slashes", "n_at", "n_question", "n_equals", "n_ampersand", "n_percent", "n_tilde",
    "n_digits", "digit_ratio", "upper_ratio", "n_subdomains", "host_digits", "host_hyphens",
    "has_ip", "has_port", "is_shortener", "is_free_hosting", "suspicious_tld", "tld_len",
    "has_punycode", "host_entropy", "url_entropy", "n_suspicious_words", "brand_mismatch",
    "path_depth", "risky_extension", "double_slash_in_path", "longest_token", "n_tokens",
    "has_email_in_url", "n_params", "has_hex_encoding", "registered_domain_len",
]

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def normalize_url(url: str) -> str:
    """Protokol önekini ve sondaki '/' karakterini standartlaştırır (öneri formu, 2. adım).

    'https://www.Ornek.com/a/' -> 'ornek.com/a'. Protokol bilgisi atılır; aksi hâlde veri
    kaynaklarının farklı şema dağılımları (ör. URLHaus'ta çoğunlukla http) model tarafından
    kestirme olarak öğrenilir.
    """
    u = url.strip().strip('"\'<>')
    u = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", u)
    host, sep, rest = u.partition("/")
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    u = host + sep + rest
    return u.rstrip("/")


def _with_scheme(url: str) -> str:
    return url if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url) else "http://" + url


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        # onaltılık / tamsayı biçimli IP (ör. 0x7f000001)
        return bool(re.fullmatch(r"(0x[0-9a-f]+|\d{8,10})", host))


@lru_cache(maxsize=65536)
def split_host(host: str) -> tuple[str, str, str]:
    """(subdomain, domain, suffix) döndürür."""
    ext = _extract(host)
    return ext.subdomain, ext.domain, ext.suffix


def registered_domain(url: str) -> str:
    host = (urlsplit(_with_scheme(url.strip())).hostname or "").lower()
    if _is_ip(host):
        return host
    sub, dom, suf = split_host(host)
    return f"{dom}.{suf}" if suf else dom


def group_key(url: str) -> str:
    """Train/test ayrımında sızıntıyı önlemek için gruplama anahtarı.

    Aynı sitenin URL'leri hem eğitimde hem testte bulunursa model siteyi ezberler ve
    başarı yapay olarak şişer. Bu yüzden kayıtlı alan adına göre gruplanır; ücretsiz
    barındırma platformlarında ise her alt alan adı farklı bir sahibe ait olduğundan
    tam host kullanılır.
    """
    parts = urlsplit(_with_scheme(url.strip()))
    host = (parts.hostname or "").lower().removeprefix("www.")
    rd = registered_domain(url)
    if rd in PATH_OWNED:
        seg = [p for p in (parts.path or "").split("/") if p]
        depth = 3 if rd == "google.com" else 1  # docs.google.com/forms/d/<id>
        return "/".join([host] + [x.lower() for x in seg[:depth]])
    return host if rd in FREE_HOSTING else rd


def extract_url_features(url: str) -> dict[str, float]:
    raw = url.strip()
    parts = urlsplit(_with_scheme(raw))
    try:
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        host, port = (parts.netloc.split("@")[-1].split(":")[0].lower(), None)
    host = host.removeprefix("www.")
    path, query = parts.path or "", parts.query or ""
    norm = normalize_url(raw)
    decoded = unquote(norm)

    is_ip = _is_ip(host)
    sub, dom, suf = ("", host, "") if is_ip else split_host(host)
    reg = f"{dom}.{suf}" if suf else dom
    tokens = _TOKEN_RE.findall(norm)
    lower = decoded.lower()
    host_tokens = set(_TOKEN_RE.findall(host))
    brand_in_host = any((b in host if len(b) >= 5 else b in host_tokens) for b in BRANDS)
    official = reg in OFFICIAL_DOMAINS or suf.endswith("gov.tr") or dom in BRANDS

    letters = sum(ch.isalpha() for ch in norm)
    digits = sum(ch.isdigit() for ch in norm)

    f = {
        "url_len": len(norm),
        "host_len": len(host),
        "path_len": len(path.rstrip("/")),
        "query_len": len(query),
        "n_dots": norm.count("."),
        "n_hyphens": norm.count("-"),
        "n_underscores": norm.count("_"),
        "n_slashes": norm.count("/"),
        "n_at": raw.count("@"),
        "n_question": norm.count("?"),
        "n_equals": norm.count("="),
        "n_ampersand": norm.count("&"),
        "n_percent": norm.count("%"),
        "n_tilde": norm.count("~"),
        "n_digits": digits,
        "digit_ratio": digits / max(len(norm), 1),
        "upper_ratio": sum(ch.isupper() for ch in path + query) / max(letters, 1),
        "n_subdomains": 0 if is_ip or not sub else sub.count(".") + 1,
        "host_digits": sum(ch.isdigit() for ch in host),
        "host_hyphens": host.count("-"),
        "has_ip": int(is_ip),
        "has_port": int(port is not None),
        "is_shortener": int(reg in SHORTENERS or host in SHORTENERS),
        "is_free_hosting": int(reg in FREE_HOSTING or host.endswith("sites.google.com")),
        "suspicious_tld": int(suf.split(".")[-1] in SUSPICIOUS_TLDS) if suf else 0,
        "tld_len": len(suf),
        "has_punycode": int("xn--" in host),
        "host_entropy": _entropy(host),
        "url_entropy": _entropy(norm),
        "n_suspicious_words": sum(w in lower for w in SUSPICIOUS_WORDS),
        "brand_mismatch": int(brand_in_host and not official),
        "path_depth": len([p for p in path.split("/") if p]),
        "risky_extension": int(path.lower().endswith(RISKY_EXTENSIONS)),
        "double_slash_in_path": int("//" in path),
        "longest_token": max((len(t) for t in tokens), default=0),
        "n_tokens": len(tokens),
        "has_email_in_url": int(bool(_EMAIL_RE.search(decoded))),
        "n_params": len([q for q in query.split("&") if q]),
        "has_hex_encoding": int(bool(re.search(r"%[0-9a-fA-F]{2}", norm))),
        "registered_domain_len": len(reg),
    }
    return f


def explain_url(url: str, feats: dict[str, float] | None = None) -> list[dict]:
    """Kullanıcıya gösterilecek, insan tarafından okunabilir risk işaretleri."""
    f = feats or extract_url_features(url)
    out: list[dict] = []

    def add(level: str, msg: str):
        out.append({"level": level, "message": msg})

    if f["has_ip"]:
        add("high", "Alan adı yerine doğrudan IP adresi kullanılıyor.")
    if f["brand_mismatch"]:
        add("high", "Bilinen bir marka adı geçiyor ama alan adı o markaya ait değil.")
    if f["risky_extension"]:
        add("high", "Bağlantı çalıştırılabilir/arşiv dosyasına işaret ediyor.")
    if f["has_punycode"]:
        add("high", "Punycode (xn--) alan adı: benzer görünen karakterlerle taklit olabilir.")
    if f["n_at"]:
        add("high", "URL içinde '@' karakteri var; tarayıcı '@' öncesini yok sayar.")
    if f["is_shortener"]:
        add("medium", "URL kısaltma servisi kullanılıyor; gerçek hedef gizleniyor.")
    if f["is_free_hosting"]:
        add("medium", "Herkesin site açabildiği ücretsiz barındırma platformu.")
    if f["suspicious_tld"]:
        add("medium", "Kötüye kullanımı sık görülen bir üst düzey alan adı (TLD).")
    if f["has_port"]:
        add("medium", "Standart dışı port numarası kullanılıyor.")
    if f["n_subdomains"] >= 3:
        add("medium", f"Çok sayıda alt alan adı ({int(f['n_subdomains'])}).")
    if f["n_suspicious_words"] >= 2:
        add("medium", "URL'de 'giriş/doğrula/hesap/şifre' gibi kimlik avı kelimeleri var.")
    if f["url_len"] > 100:
        add("low", f"URL alışılmadık derecede uzun ({int(f['url_len'])} karakter).")
    if f["double_slash_in_path"]:
        add("low", "Yolda '//' var; gizli yönlendirme olabilir.")
    return out
