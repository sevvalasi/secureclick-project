# SecureClick — Ekran Görüntüleri

Rapor için hazırlanmış ekran görüntüleri. Web görüntüleri 2x çözünürlüklüdür (1440 px genişlik → 2880 px). Mobil görüntüler Android 15 emülatöründen (Pixel 7, 1080 × 2400) alınmıştır. Görüntülerdeki tüm sonuçlar uygulamanın gerçek çıktısıdır.

Önerilen şekil başlıkları aşağıdadır; rapordaki numaralandırmaya göre uyarlayabilirsiniz.

## Web arayüzü (`web/`)

| Dosya | Önerilen başlık |
|---|---|
| `web_01_ana_sayfa.png` | SecureClick web arayüzü — analiz ekranı |
| `web_02_analiz_sahte_kargo_zararli.png` | Sahte kargo SMS'inin analizi: URL modeli ve Türkçe metin modeli birlikte "zararlı" kararı veriyor |
| `web_03_analiz_banka_bildirimi_guvenli.png` | Meşru banka bildiriminin analizi: resmî alan adı sayesinde "güvenli" |
| `web_04_analiz_arkadas_mesaji_kisaltilmis_baglanti.png` | Masum görünen mesajdaki kısaltılmış bağlantı: metin değil URL modeli tehlikeyi yakalıyor |
| `web_05_analiz_baglantisiz_mesaj_supheli.png` | Bağlantı içermeyen dolandırıcılık mesajı: yalnızca metin analiziyle "şüpheli" |
| `web_06_analiz_marka_taklidi_url.png` | Marka taklidi içeren URL'nin (paypal.com.account-verify…ru) analizi |
| `web_07_analiz_canli_kontroller.png` | Canlı kontroller: yönlendirme zinciri, SSL sertifikası ve WHOIS alan adı yaşı |
| `web_08_performans_tam_sayfa.png` | Model performansı panosu (tam sayfa) |
| `web_08_a_ozet.png` | Veri seti özeti (100.000 URL, 41.247 site) |
| `web_08_b_url_modelleri_tablo.png` | URL modellerinin test kümesi sonuçları ve öneri formundaki hedefler |
| `web_08_c_roc_pr_karisiklik.png` | ROC ve Precision-Recall eğrileri, topluluk modelinin karışıklık matrisi |
| `web_08_d_erken_tespit.png` | Zamansal deney: yeni saldırılarda kara liste ile SecureClick karşılaştırması |
| `web_08_e_hipotez_testi.png` | Hipotez testi: URL + metin füzyonu, yalnızca URL ve kara liste karşılaştırması (McNemar) |
| `web_08_f_ozellik_onemi.png` | Random Forest'a göre en etkili URL özellikleri |
| `web_08_g_kaynak_bazinda.png` | Veri kaynağına göre yakalama ve yanlış alarm oranları |
| `web_08_h_turkce_nlp.png` | Türkçe mesaj (NLP) modellerinin sonuçları |
| `web_09_proje_sayfasi.png` | Proje sayfası: problem, hipotez, mimari ve yöntem |
| `web_10_api_dokumantasyonu.png` | REST API dokümantasyonu |
| `web_11_swagger_api.png` | Otomatik oluşturulan Swagger (OpenAPI) arayüzü |
| `web_12_koyu_tema.png` | Koyu tema |
| `web_13_mobil_tarayici.png` | Web arayüzünün telefon tarayıcısındaki görünümü |

## Android uygulaması (`mobil/`)

| Dosya | Önerilen başlık |
|---|---|
| `m01_ana_ekran.png` | SecureClick Android uygulaması — ana ekran |
| `m02_sahte_kargo_sonuc.png` | "Paylaş → SecureClick" ile gönderilen sahte kargo SMS'inin analizi |
| `m03_sahte_kargo_ayrintilar.png` | Analiz ayrıntıları: model skorları, bağlantı işaretleri ve mesaj içeriği analizi |
| `m04_banka_bildirimi_guvenli.png` | Meşru banka bildirimi: resmî alan adı tanınıyor, "güvenli" |
| `m05_arkadas_mesaji_kisaltilmis_baglanti.png` | Masum görünen mesajdaki kısaltılmış bağlantı "zararlı" olarak işaretleniyor |
| `m06_baglantisiz_mesaj_supheli.png` | Bağlantısız dolandırıcılık mesajı: yalnızca Türkçe metin analiziyle "şüpheli" |
| `m07_baglanti_kontrolu_zararli.png` | "Tıklamadan önce" koruması: dokunulan zararlı bağlantı açılmadan önce analiz ediliyor |
| `m08_baglanti_kontrolu_guvenli.png` | Güvenli bir bağlantının kontrolü ve tarayıcıda açma seçeneği |
| `m09_sms_uyarisi_bildirim.png` | SMS koruması: zararlı bağlantı içeren SMS için anlık uyarı bildirimi |
| `m10_sms_uyarisindan_acilan_analiz.png` | Uyarı bildirimine dokununca açılan SMS analizi |
| `m11_ayarlar.png` | Ayarlar: sunucu adresi ve bağlantı testi, canlı kontroller, SMS ve bağlantı koruması |
| `m12_cevrimdisi_mod.png` | Çevrimdışı mod: sunucuya ulaşılamadığında cihazdaki 60 KB'lık model kullanılıyor |
| `m13_koyu_tema.png` | Koyu tema |
| `m14_uygulama_simgesi.png` | Uygulama simgesi (uygulama listesinde) |

Notlar:
- `m09`'daki SMS, emülatöre `adb emu sms send` ile gönderilmiş gerçek bir test mesajıdır; uygulama bunu Android'in SMS yayınından yakalayıp analiz etmiştir.
- `m09`'daki "Seri konsol etkinleştirildi" bildirimi emülatöre aittir, uygulamayla ilgili değildir.
- Durum çubuğu temiz görünsün diye Android'in sistem kullanıcı arayüzü demo modu kullanılmıştır (saat 10:41, pil dolu).

## Yeniden üretme

Sunucu çalışırken (`./run.sh`) web görüntüleri `puppeteer-core` ile, mobil görüntüler `adb` ile otomatik alınmıştır.
