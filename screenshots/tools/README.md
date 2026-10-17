# Ekran görüntüsü araçları

**Web** (sunucu `localhost:8000` üzerinde çalışırken):

```bash
cd screenshots/tools
npm i puppeteer-core@23.11.1
node web.js ../web
```

**Android** (emülatör veya USB ile bağlı telefon, uygulama kurulu):

```bash
source screenshots/tools/adbkit.sh
demo_on                      # temiz durum çubuğu
share_text "Mesaj metni…"    # Paylaş → SecureClick ile analiz
wait_text "risk skoru" 30
shot m02_ornek               # screenshots/mobil/m02_ornek.png
```
