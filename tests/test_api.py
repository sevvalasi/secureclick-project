import pytest
from fastapi.testclient import TestClient

from api.main import app, engine

client = TestClient(app)
needs_models = pytest.mark.skipif(not engine.ready, reason="modeller eğitilmemiş")


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "SecureClick" in r.text


def test_empty_request_rejected():
    assert client.post("/api/analyze", json={"message": "", "url": ""}).status_code == 422


@needs_models
def test_obvious_phishing_is_flagged():
    r = client.post("/api/analyze", json={
        "message": "PTT Kargo: Gönderiniz teslim edilemedi, 24 saat içinde adresinizi güncelleyin: "
                   "http://ptt-kargo-teslimat-guncelle.xyz/tr/adres/giris"})
    body = r.json()
    assert r.status_code == 200
    assert body["verdict"] in ("suspicious", "malicious")
    assert body["links"][0]["url"].startswith("http://ptt-kargo")


@needs_models
def test_popular_site_is_safe():
    body = client.post("/api/analyze", json={"url": "https://www.wikipedia.org/"}).json()
    assert body["verdict"] == "safe"


@needs_models
def test_message_without_link_is_text_only():
    body = client.post("/api/analyze", json={"message": "Akşam yemeğe geliyor musun?"}).json()
    assert body["links"] == [] and body["verdict"] == "safe"
