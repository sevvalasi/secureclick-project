"""Ağ erişimi gerektiren (canlı) bağlantı kontrolleri.

  * Yönlendirme zinciri  : kısaltılmış/gizli yönlendirmelerin gerçek hedefi
  * SSL sertifikası      : geçerlilik, düzenleyen, kalan gün
  * Alan adı yaşı (WHOIS): yeni kayıtlı alan adları kimlik avında çok yaygındır

Güvenlik: Sunucu kullanıcının verdiği adrese istek attığından SSRF'e karşı korunur;
özel/yerel/ayrılmış IP'lere çözümlenen hostlara hiçbir istek gönderilmez. Sayfa içeriği
indirilmez/çalıştırılmaz; yalnızca HTTP başlıkları okunur.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from urllib.parse import urljoin, urlsplit

import requests

UA = {"User-Agent": "Mozilla/5.0 (SecureClick link scanner)"}
HOP_TIMEOUT = 2.0
MAX_HOPS = 6
_pool = ThreadPoolExecutor(max_workers=16)


def _with_scheme(url: str) -> str:
    return url if "://" in url else "http://" + url


def is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            return False
    return True


def follow_redirects(url: str) -> dict:
    chain, current = [], _with_scheme(url)
    for _ in range(MAX_HOPS):
        host = urlsplit(current).hostname or ""
        if not is_public_host(host):
            return {"chain": chain, "final_url": current, "hops": len(chain),
                    "error": "Host çözümlenemedi veya özel/yerel bir adrese işaret ediyor."}
        try:
            r = requests.head(current, headers=UA, timeout=HOP_TIMEOUT, allow_redirects=False)
            if r.status_code in (405, 403, 501):
                r = requests.get(current, headers=UA, timeout=HOP_TIMEOUT, allow_redirects=False, stream=True)
                r.close()
        except requests.RequestException as e:
            return {"chain": chain, "final_url": current, "hops": len(chain), "error": type(e).__name__}
        chain.append({"url": current, "status": r.status_code})
        loc = r.headers.get("Location")
        if r.is_redirect and loc:
            current = urljoin(current, loc)
            continue
        return {"chain": chain, "final_url": current, "hops": len(chain) - 1, "status": r.status_code}
    return {"chain": chain, "final_url": current, "hops": len(chain), "error": "Çok fazla yönlendirme"}


def ssl_info(host: str) -> dict:
    if not is_public_host(host):
        return {"valid": False, "error": "Host çözümlenemedi"}
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=HOP_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                cert = s.getpeercert()
    except ssl.SSLCertVerificationError as e:
        return {"valid": False, "error": f"Sertifika doğrulanamadı: {e.verify_message}"}
    except (OSError, ssl.SSLError) as e:
        return {"valid": False, "error": f"HTTPS bağlantısı kurulamadı ({type(e).__name__})"}
    not_after = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
    not_before = dt.datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
    issuer = dict(x[0] for x in cert.get("issuer", ()))
    return {"valid": True, "issuer": issuer.get("organizationName") or issuer.get("commonName"),
            "days_left": (not_after - dt.datetime.utcnow()).days,
            "age_days": (dt.datetime.utcnow() - not_before).days}


def domain_age(domain: str) -> dict:
    try:
        import whois  # python-whois
        w = whois.whois(domain)
        created = w.creation_date
        if isinstance(created, list):
            created = min(c for c in created if c)
        if not created:
            return {"age_days": None, "error": "Kayıt tarihi bulunamadı"}
        if created.tzinfo:
            created = created.replace(tzinfo=None)
        return {"age_days": (dt.datetime.utcnow() - created).days, "created": created.date().isoformat(),
                "registrar": w.registrar}
    except Exception as e:  # WHOIS sunucuları sık sık hata verir / hız sınırlar
        return {"age_days": None, "error": type(e).__name__}


def run_live_checks(url: str, registered: str, budget: float = 3.0) -> dict:
    """Üç kontrolü paralel çalıştırır; süre bütçesini aşan kontrol 'timeout' döner."""
    host = (urlsplit(_with_scheme(url)).hostname or "").lower()
    jobs = {
        "redirects": _pool.submit(follow_redirects, url),
        "ssl": _pool.submit(ssl_info, host),
    }
    try:
        ipaddress.ip_address(registered)  # IP adreslerinin WHOIS alan adı kaydı yoktur
    except ValueError:
        jobs["whois"] = _pool.submit(domain_age, registered)
    out = {}
    deadline = dt.datetime.now() + dt.timedelta(seconds=budget)
    for k, fut in jobs.items():
        remaining = max((deadline - dt.datetime.now()).total_seconds(), 0.05)
        try:
            out[k] = fut.result(timeout=remaining)
        except FutTimeout:
            out[k] = {"error": "timeout"}
    return out


def live_signals(live: dict) -> list[dict]:
    sig = []
    r, s, w = live.get("redirects", {}), live.get("ssl", {}), live.get("whois", {})
    if r.get("hops", 0) >= 2:
        sig.append({"level": "medium", "message": f"{r['hops']} kez yönlendiriliyor; son hedef: {r.get('final_url')}"})
    if s and not s.get("valid") and s.get("error") != "timeout":
        sig.append({"level": "medium", "message": f"Geçerli SSL sertifikası yok ({s.get('error')})."})
    elif s.get("valid") and s.get("age_days", 999) < 7:
        sig.append({"level": "low", "message": f"SSL sertifikası çok yeni ({s['age_days']} günlük)."})
    age = w.get("age_days")
    if age is not None and age < 30:
        sig.append({"level": "high", "message": f"Alan adı yalnızca {age} gün önce kaydedilmiş."})
    elif age is not None and age < 180:
        sig.append({"level": "medium", "message": f"Alan adı yeni ({age} günlük)."})
    return sig
