# SecureClick Android

SecureClick'in Android istemcisi (Java, minSdk 26 / Android 8.0+). Mesajlardaki ve tıklanan bağlantıları **açılmadan önce** kontrol eder.

## Özellikler

| Özellik | Nasıl çalışır |
|---|---|
| **Analiz ekranı** | Mesajı veya bağlantıyı yapıştırın; Güvenli / Şüpheli / Zararlı kararı, model skorları ve gerekçeler |
| **Bağlantı koruması** | SecureClick'i varsayılan bağlantı açıcı yapın (Ayarlar → *Varsayılan uygulama ayarlarını aç*). Herhangi bir uygulamada dokunduğunuz bağlantı önce SecureClick penceresinde analiz edilir; sonra isterseniz tarayıcıda açarsınız |
| **Paylaş / metin seçimi** | WhatsApp, e-posta vb. uygulamalarda metni seçip *Paylaş → SecureClick* veya seçim menüsünde *SecureClick ile kontrol et* |
| **SMS koruması** (isteğe bağlı) | Bağlantı içeren SMS geldiğinde otomatik kontrol, şüpheliyse anlık bildirim. Varsayılan kapalı; açınca SMS alma izni istenir |
| **Çevrimdışı mod** | Sunucuya ulaşılamazsa cihazdaki 60 KB'lık URL modeli (`assets/url_model.json`) kullanılır |
| **Geçmiş** | Son 30 analiz yalnızca cihazda tutulur |

## Mimari

```
Uygulama ──HTTP──▶ SecureClick API (/api/analyze)      tam model: RF + SVM + Türkçe metin füzyonu
   │
   └─ sunucu yoksa ─▶ UrlModel (cihazda)               karakter 3-5 gram hashing + L1 lojistik regresyon
```

Cihaz modeli `python -m ml.export_mobile_model` ile üretilir. `UrlModel.java`, scikit-learn'deki normalizasyon, n-gram ve MurmurHash3 hesaplarını birebir uygular: 2.005 test URL'sinde Python ile en büyük fark 9 × 10⁻⁸, karar farkı 0.

| Cihaz modeli (test kümesi) | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| Hashing + L1 LR (60 KB) | %94,6 | %94,6 | %94,6 | %94,6 | 0,990 |

## Derleme

**Android Studio:** *File → Open* ile bu `android/` klasörünü açın, ▶ ile çalıştırın.

**Komut satırı:**

```bash
cd android
./gradlew assembleDebug          # APK: app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest      # birim testleri
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Sunucuya bağlanma

1. Bilgisayarda sunucuyu başlatın: `./run.sh` (0.0.0.0:8000 üzerinden dinler).
2. **Emülatör:** varsayılan adres `http://10.0.2.2:8000` doğrudan çalışır.
3. **Gerçek telefon:** telefonu bilgisayarla aynı Wi-Fi ağına bağlayın. Bilgisayarın yerel IP'sini bulun (macOS: `ipconfig getifaddr en0`). Uygulamada *Ayarlar → Sunucu adresi* alanına örneğin `http://192.168.1.20:8000` girin ve *Bağlantıyı test et*'e dokunun.

> Prototip yerel ağda şifresiz HTTP kullanır (`res/xml/network_security_config.xml`). Sunucu internete açılacaksa HTTPS kullanın ve bu izni kaldırın.

## Gizlilik

- Analiz için gönderilen metin sunucuda saklanmaz; geçmiş yalnızca cihazdadır.
- SMS korumasında yalnızca **bağlantı içeren** mesajlar analiz edilir.
- Çevrimdışı modda hiçbir veri cihazdan çıkmaz.
