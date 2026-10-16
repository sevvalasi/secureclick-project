from secureclick.features.text_features import extract_text_features, extract_urls, normalize_tr
from secureclick.features.url_features import (extract_url_features, explain_url, group_key,
                                               normalize_url, registered_domain)
from secureclick.live_checks import is_public_host


def test_normalize_url_strips_scheme_www_and_trailing_slash():
    assert normalize_url("https://www.Ornek.com/a/") == "ornek.com/a"
    assert normalize_url("http://ornek.com") == "ornek.com"
    assert normalize_url("ornek.com/") == "ornek.com"


def test_registered_domain_and_group_key():
    assert registered_domain("https://a.b.ornek.com.tr/x") == "ornek.com.tr"
    assert group_key("https://news.bbc.co.uk/x") == "bbc.co.uk"
    # ücretsiz barındırmada her alt alan adı ayrı sahip -> tam host
    assert group_key("https://sahte-banka.jimdofree.com/") == "sahte-banka.jimdofree.com"


def test_ip_port_and_extension_flags():
    f = extract_url_features("http://125.41.8.70:42191/bins/x.arm")
    assert f["has_ip"] == 1 and f["has_port"] == 1 and f["risky_extension"] == 1


def test_brand_mismatch():
    assert extract_url_features("http://garanti-bonus-giris.xyz/login")["brand_mismatch"] == 1
    assert extract_url_features("https://www.garanti.com.tr/kampanyalar")["brand_mismatch"] == 0


def test_shortener_and_free_hosting():
    assert extract_url_features("https://bit.ly/abc")["is_shortener"] == 1
    assert extract_url_features("https://x.web.app/login")["is_free_hosting"] == 1


def test_explain_url_messages_are_turkish():
    msgs = [s["message"] for s in explain_url("http://1.2.3.4/paypal/login")]
    assert any("IP" in m for m in msgs)


def test_extract_urls_from_turkish_sms():
    text = "Kargonuz bekliyor: ptt-takip.xyz/odeme ve https://bit.ly/3xK9pQ2 adresine girin. ali@ornek.com"
    urls = extract_urls(text)
    assert "ptt-takip.xyz/odeme" in urls and "https://bit.ly/3xK9pQ2" in urls
    assert not any("ali@" in u for u in urls)


def test_normalize_tr_handles_dotted_i():
    assert normalize_tr("İSTANBUL'da HESABINIZ") == "istanbul da hesabiniz"


def test_text_features_detect_patterns():
    f = extract_text_features("Hesabınız 24 saat içinde kapatılacak! Hemen şifrenizi doğrulayın.")
    assert f["urgency"] >= 1 and f["threat"] >= 1 and f["credential"] >= 1
    assert f["sentiment"] < 0


def test_ssrf_guard_blocks_private_hosts():
    assert not is_public_host("127.0.0.1")
    assert not is_public_host("192.168.1.1")
    assert not is_public_host("169.254.169.254")
