# SecureClick — Bağlantı Güvenliği Test ve Değerlendirme

SMS, e-posta ve sosyal medya mesajlarındaki bağlantıları **tıklamadan önce** analiz eden, yapay zekâ destekli zararlı bağlantı tespit sistemi.
URL yapısını, alan adı özelliklerini ve **Türkçe mesaj içeriğini** birlikte değerlendirir; statik kara listelerin henüz bilmediği yeni saldırıları yakalamayı hedefler.

> TÜBİTAK 2209-A Üniversite Öğrencileri Araştırma Projeleri · Recep Tayyip Erdoğan Üniversitesi
> Yürütücü: **Şevval Asi** · Araştırmacı: **Tuğba Nur Uygun** · Danışman: **Arş. Gör. Dr. Didem Genç**

## Sonuçlar

> Veri: **25.852 URL** (12.926 zararlı / 12.926 güvenli, 11.958 farklı site). Öneri formundaki sınıf başına 50.000 hedefine yavaş ağ bağlantısı nedeniyle henüz ulaşılamadı; toplayıcılar kaldığı yerden devam eder (bkz. *Veri setini büyütme*).

### URL modelleri — test kümesi (eğitimde görülmemiş siteler)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | 5-kat CV F1 |
|---|---|---|---|---|---|---|
| *Hedef (öneri formu)* | *≥ %90* | *≥ %88* | *≥ %92* | *≥ %90* | *≥ 0,95* | |
| Random Forest | %95,2 | %96,4 | %93,9 | %95,1 | 0,983 | %95,3 ± 1,4 |
| Gradient Boosting | %94,6 | %96,4 | %92,7 | %94,5 | 0,986 | %95,6 ± 1,2 |
| SVM (karakter n-gram) | %93,8 | %94,0 | %93,7 | %93,8 | 0,983 | %94,4 ± 0,9 |
| TF-IDF + Lojistik Regresyon | %93,8 | %94,3 | %93,2 | %93,7 | 0,982 | %94,0 ± 1,6 |
| **SecureClick Topluluk (RF + SVM)** | %96,2 | %97,5 | %95,0 | %96,2 | 0,991 | — |

Topluluk modelinin yanlış alarm oranı (FPR): %2,5. Analiz süresi URL başına ~20 ms (hedef ≤ 2 sn).

### Erken tespit — yeni saldırılar (zamansal deney)

Modeller ve kara liste yalnızca 2026-10-06 öncesindeki saldırıları gördü; test, bu tarihten sonra ortaya çıkan URL'lerle yapıldı.

| Yöntem | Recall | Precision | F1 |
|---|---|---|---|
| Kara liste | %58,0 | %98,8 | %73,1 |
| **SecureClick topluluğu** | **%98,9** | %95,2 | **%97,0** |

Kara listenin kaçırdığı 1.085 yeni zararlı bağlantının 1.057 tanesini SecureClick yakaladı (McNemar p < 0,001).

### Hipotez testi — URL + metin birlikte

Eğitimde kullanılmamış Türkçe senaryo şablonları + test kümesindeki gerçek URL'ler (391 mesaj):

| Yöntem | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Kara liste | %61,1 | %99,1 | %40,8 | %57,8 |
| Yalnızca URL | %76,0 | %74,9 | %94,9 | %83,7 |
| Yalnızca mesaj metni | %73,9 | %77,2 | %85,1 | %81,0 |
| **URL + metin** | **%91,0** | %95,8 | %90,2 | **%92,9** |

McNemar (URL + metin vs. yalnızca URL): b = 82, c = 23, p = 1,5 × 10⁻⁸ → fark anlamlı; **hipotez bu veri setinde desteklendi**. (Senaryolar sentetiktir; pilot testle doğrulanmalıdır.)

### Türkçe metin modeli

TF-IDF (1-2 gram) + Lojistik Regresyon — TurkishSMSCollection test F1: %99,1; eğitimde görülmemiş dolandırıcılık şablonlarında F1: %81,4.

Tüm grafikler (ROC/PR, karışıklık matrisi, özellik önemleri) uygulamanın **Model Performansı** sayfasındadır.


## Özellikler

- **Web arayüzü** — mesaj veya bağlantı yapıştır, anında *Güvenli / Şüpheli / Zararlı* kararı ve gerekçeleri
- **URL analizi** — 40 sözcüksel özellik (IP/port, kısaltıcı, ücretsiz barındırma, şüpheli TLD, punycode, marka taklidi, entropi, riskli uzantı…) + karakter n-gram modeli
- **Türkçe NLP** — Türkçe-duyarlı normalizasyon, TF-IDF (1-2 gram), aciliyet / tehdit / ödül / kimlik bilgisi isteme kalıpları, duygu skoru
- **Modeller** — Random Forest, Gradient Boosting, SVM, TF-IDF + Lojistik Regresyon; RF + SVM topluluğu; isteğe bağlı BERTurk
- **Canlı kontroller** (isteğe bağlı) — yönlendirme zinciri, SSL sertifikası, WHOIS alan adı yaşı; SSRF korumalı
- **RESTful API** — Android uygulaması / tarayıcı eklentisi için (`/docs` altında Swagger)
- **Performans panosu** — ROC & PR eğrileri, karışıklık matrisi, zamansal "erken tespit" deneyi, hipotez testi, McNemar

## Hızlı başlangıç

```bash
git clone <repo-adresi> secureclick-web && cd secureclick-web
./run.sh            # venv kurar, modeller yoksa eğitir, sunucuyu başlatır
```

Tarayıcıda **http://localhost:8000** adresini açın.

Adım adım:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m ml.pipeline              # veri indir → veri seti → eğit → değerlendir (tüm hat)
# veya tek tek:
python -m ml.download_data         # PhishTank, URLHaus, OpenPhish, Tranco, TurkishSMSCollection
python -m ml.collect_benign        # güvenli URL'ler: popüler sitelerin site haritaları
python -m ml.build_dataset         # temizleme, normalizasyon, dengeleme, gruplu 80/10/10 bölme
python -m ml.generate_tr_scenarios # Türkçe dolandırıcılık/meşru senaryolar
python -m ml.train_url_models      # RF, GB, SVM, TF-IDF+LR (+ 5 katlı CV, zamansal deney)
python -m ml.train_text_models     # Türkçe mesaj modelleri
python -m ml.evaluate_fusion       # hipotez testi: URL + metin vs yalnızca URL vs kara liste

uvicorn api.main:app --reload      # http://localhost:8000
pytest                             # testler
```

İsteğe bağlı BERTurk: `pip install -r requirements-bert.txt && python -m ml.train_bert` (GPU / Colab önerilir).

## Veri setini büyütme

Güvenli URL toplayıcıları kaldığı yerden devam eder; ağ hızlıyken çalıştırıp hattı yeniden koşun:

```bash
python -m ml.collect_benign --domains 20000 --tr-domains 4000   # site haritaları
python -m ml.collect_benign_cc --target 52000                   # alternatif: Common Crawl indeksi
python -m ml.pipeline --skip-download                           # veri seti → eğitim → raporlar
```

## Proje yapısı

```
secureclick/            Çekirdek paket (eğitim ve API ortak kullanır)
  features/url_features.py    URL normalizasyonu, 40 sözcüksel özellik, açıklamalar
  features/text_features.py   Türkçe normalizasyon, URL çıkarma, NLP kalıpları
  pipelines.py                scikit-learn model tanımları
  evaluation.py               metrikler, eşik seçimi, McNemar testi
  live_checks.py              yönlendirme / SSL / WHOIS (SSRF korumalı)
  predictor.py                karar mekanizması (füzyon + sinyaller)
ml/                     Veri toplama, eğitim ve değerlendirme betikleri
api/main.py             FastAPI: /api/analyze, /api/metrics, /api/health + web arayüzü
web/                    Arayüz (bağımlılıksız HTML/CSS/JS, açık/koyu tema)
reports/                Eğitim/değerlendirme raporları (JSON) — panoda gösterilir
models/                 Eğitilmiş modeller (git'e eklenmez; hat ile üretilir)
tests/                  pytest testleri
```

## API

```bash
curl -X POST http://localhost:8000/api/analyze -H "Content-Type: application/json" \
  -d '{"message": "Kargonuz teslim edilemedi: http://ptt-kargo-takip.xyz/tr", "live_checks": false}'
```

| Alan | Tür | Açıklama |
|---|---|---|
| `message` | string | Mesaj metni; içindeki bağlantılar otomatik çıkarılır |
| `url` | string | Tek bağlantı |
| `live_checks` | bool | Yönlendirme, SSL, WHOIS kontrolleri |

Yanıt: `verdict` (`safe`/`suspicious`/`malicious`), `score`, bağlantı başına model skorları ve gerekçeler, metin analizi.

## Yöntem notları

- **Gruplu bölme.** Güvenli URL'ler site başına birden çok sayfa içerdiğinden rastgele bölme, modelin siteleri ezberlemesine ve başarının şişmesine yol açar. Bölme kayıtlı alan adına göre gruplu yapılır (ücretsiz barındırma platformlarında tam host'a göre).
- **Derin yollu güvenli URL'ler.** Tranco yalnızca alan adı verir; sadece ana sayfaları güvenli sınıf yapmak "kısa URL = güvenli" kestirmesini öğretir. Bu yüzden güvenli URL'ler sitelerin kendi yayımladığı site haritalarından alınır.
- **Protokol normalizasyonu.** URLHaus'taki URL'lerin çoğu `http://` olduğundan şema bilgisi modele verilmez.
- **Canlı özellikler modelde değil.** Alan adı yaşı, SSL ve yönlendirme sayısı ağ erişimi gerektirir ve veri setindeki eski kimlik avı sitelerinin çoğu kapanmıştır; bunlarla eğitmek eğitim/kullanım tutarsızlığı yaratır. Bu sinyaller tahmin anında ayrı risk katmanı olarak eklenir.
- **Eşik seçimi.** Zararlı bağlantıyı kaçırmak yanlış alarmdan daha maliyetli olduğundan eşik doğrulama kümesinde *recall ≥ %92* koşuluyla F1'i en yükseltecek şekilde seçilir.
- **Ürün katmanları (metriklere dahil değil).** Arayüzde ek olarak (1) açık tehdit listelerinde birebir eşleşme ve (2) Tranco ilk 10.000 alan adı için yanlış alarm azaltma uygulanır. Raporlanan model metrikleri bu katmanlar olmadan hesaplanır.

## Sınırlılıklar

- Türkçe senaryo mesajları sentetiktir; füzyon sonuçları gönüllü katılımcılarla yapılacak pilot testle doğrulanmalıdır.
- TurkishSMSCollection spam/normal etiketlidir; spam ile kimlik avı birebir aynı değildir.
- Güvenli sınıf popüler sitelerden oluşur; az bilinen meşru sitelerde yanlış alarm oranı daha yüksek olabilir.
- Dosya, görsel ve video içerikleri kapsam dışıdır.

## Etik

Yalnızca açık kaynak veriler kullanılır; analiz edilen mesajlar saklanmaz; canlı kontrollerde sayfa içeriği indirilmez ve özel ağ adreslerine istek gönderilmez. Sistem yalnızca savunma amaçlıdır.

## Veri kaynakları ve kaynakça

- [PhishTank](https://phishtank.org), [URLHaus](https://urlhaus.abuse.ch), [OpenPhish](https://openphish.com), [Tranco](https://tranco-list.eu)
- Karasoy, O., & Ballı, S. (2021). *Spam SMS Detection for Turkish Language with Deep Text Analysis and Deep Learning Methods.* Arab J Sci Eng. — [TurkishSMSCollection](https://github.com/onrkrsy/TurkishSMS-Collection)
- Ma, J., Saul, L. K., Savage, S., & Voelker, G. M. (2009). *Beyond Blacklists: Learning to Detect Malicious Web Sites from Suspicious URLs.* KDD.
- Le, H., Pham, Q., Sahoo, D., & Hoi, S. C. H. (2018). *URLNet: Learning a URL Representation with Deep Learning for Malicious URL Detection.* arXiv:1802.03162.
- Sahoo, D., Liu, C., & Hoi, S. C. H. (2017). *Malicious URL Detection using Machine Learning: A Survey.* arXiv:1701.07179.
- Marchal, S., François, J., State, R., & Engel, T. (2014). *PhishStorm: Detecting Phishing With Streaming Analytics.* IEEE TNSM.
- Schweter, S. (2020). *BERTurk — BERT models for Turkish.* Zenodo.
