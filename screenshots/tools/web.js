// SecureClick web arayüzü ekran görüntüleri (rapor için)
const puppeteer = require("puppeteer-core");
const path = require("path");
const fs = require("fs");

const OUT = process.argv[2];
const BASE = "http://localhost:8000";
// Yalnızca # değişince sayfa yeniden yüklenmez; her adımda temiz sayfa için sorgu parametresi ekle
const at = (hash) => `${BASE}/?r=${Date.now()}#${hash}`;
fs.mkdirSync(OUT, { recursive: true });

const MSG = {
  kargo: "PTT Kargo: Gönderiniz adres bilgisi eksik olduğu için teslim edilemedi. 24 saat içinde güncellemezseniz iade edilecektir: http://ptt-kargotakip-tr.xyz/adres/guncelle",
  banka: "Garanti BBVA: 350 TL tutarındaki ödemeniz alınmıştır. Hesap hareketleriniz için https://www.garantibbva.com.tr/kampanyalar",
  arkadas: "Selam, geçen haftaki fotoğrafları yükledim, buradan bakabilirsin: https://bit.ly/3xK9pQ2",
  odul: "Tebrikler! Numaranız haftanın şanslı abonesi seçildi. Ödülünüzü 24 saat içinde talep edin, IBAN bilgilerinizi gönderin.",
};

async function shot(page, name, opts = {}) {
  const file = path.join(OUT, name);
  if (opts.el) {
    const el = await page.$(opts.el);
    await el.screenshot({ path: file });
  } else {
    await page.screenshot({ path: file, fullPage: !!opts.full });
  }
  console.log("✓", name);
}

async function analyze(page, { message = "", url = "", live = false }) {
  await page.goto(at("analiz"), { waitUntil: "networkidle0" });
  if (url) {
    await page.click('.tab[data-mode="url"]');
    await page.type("#url", url);
  } else {
    await page.$eval("#message", (el, v) => (el.value = v), message);
  }
  if (live) await page.click(".switch");
  await page.click("#submitBtn");
  await page.waitForFunction(
    () => !document.querySelector("#submitBtn").disabled && document.querySelector("#result .verdict"),
    { timeout: 30000 });
  await new Promise((r) => setTimeout(r, 300));
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: "new",
    args: ["--hide-scrollbars", "--force-color-profile=srgb"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);

  // 1) Ana sayfa (boş)
  await page.goto(at("analiz"), { waitUntil: "networkidle0" });
  await shot(page, "web_01_ana_sayfa.png");

  // 2-5) Analiz sonuçları
  await analyze(page, { message: MSG.kargo });
  await shot(page, "web_02_analiz_sahte_kargo_zararli.png", { full: true });
  await analyze(page, { message: MSG.banka });
  await shot(page, "web_03_analiz_banka_bildirimi_guvenli.png", { full: true });
  await analyze(page, { message: MSG.arkadas });
  await shot(page, "web_04_analiz_arkadas_mesaji_kisaltilmis_baglanti.png", { full: true });
  await analyze(page, { message: MSG.odul });
  await shot(page, "web_05_analiz_baglantisiz_mesaj_supheli.png", { full: true });
  await analyze(page, { url: "http://paypal.com.account-verify.secure-login.ru/webscr" });
  await shot(page, "web_06_analiz_marka_taklidi_url.png", { full: true });
  await analyze(page, { url: "https://www.wikipedia.org/", live: true });
  await shot(page, "web_07_analiz_canli_kontroller.png", { full: true });

  // 8) Model performansı panosu — bölüm bölüm
  await page.goto(at("performans"), { waitUntil: "networkidle0" });
  await page.waitForSelector("#perf .stats");
  await shot(page, "web_08_performans_tam_sayfa.png", { full: true });
  const cards = await page.$$("#perf > *");
  const names = ["ozet", "url_modelleri_tablo", "roc_pr_karisiklik", "erken_tespit", "hipotez_testi",
                 "ozellik_onemi", "kaynak_bazinda", "turkce_nlp"];
  for (let i = 0; i < Math.min(cards.length, names.length); i++) {
    const file = `web_08_${String.fromCharCode(97 + i)}_${names[i]}.png`;
    await cards[i].screenshot({ path: path.join(OUT, file) });
    console.log("✓", file);
  }

  // 9) Proje ve API sayfaları, Swagger
  await page.goto(at("hakkinda"), { waitUntil: "networkidle0" });
  await shot(page, "web_09_proje_sayfasi.png", { full: true });
  await page.goto(at("api"), { waitUntil: "networkidle0" });
  await shot(page, "web_10_api_dokumantasyonu.png", { full: true });
  await page.goto(BASE + "/docs", { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.waitForSelector(".swagger-ui .opblock", { timeout: 180000 });
  await new Promise((r) => setTimeout(r, 1500));
  await shot(page, "web_11_swagger_api.png");

  // 12) Koyu tema
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);
  await analyze(page, { message: MSG.kargo });
  await shot(page, "web_12_koyu_tema.png", { full: true });

  // 13) Telefon tarayıcısında web arayüzü
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
  await analyze(page, { message: MSG.kargo });
  await shot(page, "web_13_mobil_tarayici.png", { full: true });

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
