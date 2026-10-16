"""Türkçe SMS/e-posta senaryoları üretir (sentetik, etiketli).

Türkiye'de yaygın dolandırıcılık kalıpları (sahte kargo, e-Devlet, HGS cezası, banka
bloke, vergi iadesi, yasa dışı bahis) ve meşru bildirimler şablonlardan üretilir.
Şablonlar kimliğe (template_id) göre eğitim/doğrulama/test olarak ayrılır; böylece model test
sırasında daha önce görmediği kalıplarla sınanır.

Mesajlardaki '{url}' yer tutucusu, değerlendirme sırasında test kümesindeki gerçek
zararlı/güvenli URL'lerle doldurulur (bkz. ml/evaluate_fusion.py).

Kullanım:  python -m ml.generate_tr_scenarios
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "processed" / "tr_scenarios.csv"

FILL = {
    "kargo": ["PTT Kargo", "Yurtiçi Kargo", "Aras Kargo", "MNG Kargo", "Sürat Kargo", "HepsiJet"],
    "banka": ["Garanti BBVA", "Akbank", "Ziraat Bankası", "İş Bankası", "Yapı Kredi", "Halkbank", "VakıfBank", "QNB"],
    "tutar": ["49,90", "127,50", "350", "1.250", "2.480,75", "89", "15,99", "4.999"],
    "saat": ["24", "12", "48", "2", "6"],
    "isim": ["Ayşe", "Mehmet", "Zeynep", "Can", "Elif", "Burak", "Deniz", "Emre", "Selin"],
    "kod": ["TR48291", "AB120934", "PK77821", "TRX5501", "HJ90231"],
    "gun": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"],
    "operator": ["Turkcell", "Vodafone", "Türk Telekom"],
    "magaza": ["Trendyol", "Hepsiburada", "n11", "Amazon", "Getir", "Migros"],
}

# (kategori, şablon). label=1 zararlı, 0 güvenli
PHISHING = [
    ("kargo", "{kargo}: Gönderiniz adres bilgisi eksik olduğu için teslim edilemedi. {saat} saat içinde güncellemezseniz iade edilecektir: {url}"),
    ("kargo", "Sayın müşterimiz, {kod} numaralı paketiniz gümrükte bekliyor. {tutar} TL gümrük ücretini ödemek için hemen tıklayın {url}"),
    ("kargo", "{kargo} bilgilendirme: Kargonuz dağıtım merkezinde. Teslimat için adresinizi onaylayın {url}"),
    ("kargo", "Paketiniz teslim edilemedi! Yeniden teslimat talebi oluşturmak için: {url} - {kargo}"),
    ("edevlet", "e-Devlet: Adınıza {tutar} TL tutarında iade tanımlanmıştır. Almak için kimlik bilgilerinizle giriş yapın {url}"),
    ("edevlet", "T.C. Sosyal Güvenlik Kurumu: Hizmet dökümünüzde eksiklik tespit edildi. Son gün bugün, hemen doğrulayın: {url}"),
    ("edevlet", "Gelir İdaresi: {tutar} TL vergi iadeniz onaylandı. Kart bilgilerinizi girerek iadeyi alabilirsiniz {url}"),
    ("edevlet", "e-Devlet şifreniz {saat} saat içinde iptal edilecektir. Aksi halde hesabınız askıya alınır. Yenilemek için {url}"),
    ("hgs", "HGS: Ödenmemiş {tutar} TL geçiş ihlaliniz bulunmaktadır. Cezanın 10 katına çıkmaması için ödeyin: {url}"),
    ("hgs", "Köprü ve otoyol geçiş borcunuz nedeniyle icra işlemi başlatılacaktır. Ödeme: {url}"),
    ("hgs", "OGS/HGS etiketiniz bloke edildi. Bakiyenizi aktarmak için tıklayınız {url}"),
    ("banka", "{banka}: Kartınızdan şüpheli {tutar} TL işlem yapıldı. Siz yapmadıysanız iptal için: {url}"),
    ("banka", "Değerli müşterimiz, {banka} hesabınız güvenlik nedeniyle askıya alınmıştır. Bilgilerinizi güncelleyin {url}"),
    ("banka", "{banka} internet şubeniz {saat} saat içinde kapatılacak. Doğrulama kodu ile giriş yapınız: {url}"),
    ("banka", "Kredi kartı borcunuz nedeniyle yasal işlem başlatılmıştır. Yapılandırma için hemen {url}"),
    ("banka", "{banka}: {tutar} TL bonus puanınızın süresi bugün doluyor! Kullanmak için {url}"),
    ("odul", "Tebrikler {isim}! {magaza} çekilişinde iPhone kazandınız. Hediyenizi almak için {url}"),
    ("odul", "{operator}: Sadakat programı kapsamında 50 GB hediye internet kazandınız, tanımlamak için {url}"),
    ("odul", "Sayın abonemiz, {tutar} TL fazla ödemeniz iade edilecektir. IBAN bilgilerinizi girin: {url}"),
    ("odul", "Bayrama özel {magaza} {tutar} TL hediye çeki! Sınırlı sayıda, son fırsat {url}"),
    ("bahis", "Deneme bonusu 500 TL! Yatırımsız freespin, hemen üye ol: {url}"),
    ("bahis", "%300 hoşgeldin bonusu ve kayıpsız bahis fırsatı. Yeni giriş adresimiz: {url}"),
    ("bahis", "Casino'da günün kazananı sen ol! Çevrimsiz {tutar} TL bonus: {url}"),
    ("hesap", "Instagram: Hesabınız telif ihlali nedeniyle {saat} saat içinde kapatılacak. İtiraz için {url}"),
    ("hesap", "WhatsApp hesabınız başka bir cihazda açıldı. Siz değilseniz hemen doğrulayın {url}"),
    ("hesap", "Apple Kimliğiniz kilitlendi. Kilidi açmak için bilgilerinizi doğrulayın: {url}"),
    ("hesap", "Netflix: Ödemeniz alınamadı, üyeliğiniz durduruldu. Kart bilgilerinizi güncelleyin {url}"),
    ("tanidik", "Selam {isim} ben, numaram değişti. Şu linkten fotoğraflara bak bi {url}"),
    ("tanidik", "Anne telefonum bozuldu bu yeni numaram, acil para lazım şuradan gönderebilir misin {url}"),
    ("tanidik", "{isim} bu sen misin videoda?? {url}"),
    ("tanidik", "Düğün davetiyemiz hazır, detaylar burada {url} görüşmek üzere"),
    ("tanidik", "Toplantı notlarını paylaştım, bakar mısın {url}"),
    ("is", "İK Departmanı: {gun} gününe kadar maaş bordronuzu onaylamanız gerekmektedir {url}"),
    ("is", "Evden çalışarak günlük {tutar} TL kazanın! Başvuru: {url}"),
    ("is", "Kurumsal e-posta kotanız doldu. Hesabınızın silinmemesi için şifrenizle doğrulayın {url}"),
    ("kargo", "Sayın alıcı, kargonuz için 2. teslimat denemesi başarısız oldu. Yeni teslim tarihi seçin: {url}"),
    ("kargo", "{kargo}: Kargo ücretiniz eksik ödenmiştir. {tutar} TL farkı ödemezseniz gönderiniz imha edilecektir {url}"),
    ("kargo", "Yurt dışından gelen paketiniz için vergi ödemesi bekleniyor. Takip no {kod}: {url}"),
    ("edevlet", "Adınıza kayıtlı hatlarda usulsüzlük tespit edildi. BTK bildirimi için kimliğinizi doğrulayın {url}"),
    ("edevlet", "Emniyet Genel Müdürlüğü: Hakkınızda trafik cezası düzenlenmiştir. İtiraz ve ödeme: {url}"),
    ("edevlet", "Elektrik faturanızdan {tutar} TL iade hakkınız doğmuştur. Başvuru son tarih {gun}: {url}"),
    ("edevlet", "Sağlık Bakanlığı: Aşı kartınızın süresi doldu, yenilemek için TC kimlik numaranızı girin {url}"),
    ("hgs", "Aracınıza ait {tutar} TL köprü cezası 7 gün içinde ödenmezse plakanız trafikten men edilecek {url}"),
    ("banka", "{banka} müşteri hizmetleri: Mobil onay sisteminiz güncellenmeli. Güncellemezseniz kartınız bloke olur {url}"),
    ("banka", "Hesabınıza yetkisiz erişim denemesi tespit edildi. Hesabınızı korumak için onay kodunu girin {url}"),
    ("banka", "{banka}: Size özel %0 faizli {tutar} TL ihtiyaç kredisi onaylandı, hemen kullanmak için {url}"),
    ("banka", "Kartınıza {tutar} TL para iadesi yapılacak. İade için kart numaranızı ve CVV'nizi giriniz {url}"),
    ("odul", "{magaza} yıldönümü çekilişi! Anketi doldurana {tutar} TL hediye çeki. Son 3 saat: {url}"),
    ("odul", "Tebrikler! Numaranız haftanın şanslı abonesi seçildi. Ödülünüzü 24 saat içinde talep edin {url}"),
    ("odul", "{operator} faturanızdan fazla tahsilat yapıldı. {tutar} TL iadeniz için IBAN girin {url}"),
    ("bahis", "Kaçak bahis değil lisanslı casino! İlk yatırıma %200 bonus, hemen kazanmaya başla {url}"),
    ("bahis", "Kripto ile günde {tutar} TL kazanç! Uzman ekibimizle yatırım yapın, kontenjan sınırlı {url}"),
    ("hesap", "Facebook: Sayfanız topluluk kurallarını ihlal ettiği için kaldırılacak. İtiraz formu: {url}"),
    ("hesap", "Microsoft 365 parolanızın süresi bugün doluyor. Aynı parolayı korumak için tıklayın {url}"),
    ("hesap", "Trendyol hesabınızda şüpheli giriş tespit edildi, siparişleriniz iptal edilmeden giriş yapın {url}"),
    ("hesap", "Steam: Arkadaşınız size oyun hediye etti, almak için hesabınıza giriş yapın {url}"),
    ("tanidik", "Kanka şu indirimi gördün mü yarı fiyatına iPhone var, link {url}"),
    ("tanidik", "Hocam ödev dosyasını buraya yükledim, giriş yapıp indirebilirsiniz {url}"),
    ("tanidik", "{isim} acil durum, hastanedeyim kartım çalışmıyor. Buradan yardım edebilir misin {url}"),
    ("is", "Başvurunuz değerlendirildi! Mülakat için kimlik ve banka bilgilerinizi forma girin {url}"),
    ("is", "Fatura ektedir, ödemenin bugün yapılması gerekiyor. Görüntülemek için oturum açın: {url}"),
    ("is", "Muhasebe: Maaş promosyonunuz hesabınıza aktarılacak, banka bilgilerinizi onaylayın {url}"),
]

LEGIT = [
    ("kargo", "{kargo}: {kod} takip numaralı gönderiniz yola çıktı. Takip için {url}"),
    ("kargo", "Siparişiniz {gun} günü teslim edildi. {magaza} ile alışverişiniz için teşekkürler. {url}"),
    ("kargo", "{magaza} siparişiniz hazırlanıyor, tahmini teslimat {gun}. Detaylar: {url}"),
    ("banka", "{banka}: {tutar} TL tutarındaki ödemeniz alınmıştır. Bilgi için {url}"),
    ("banka", "{banka}: Kartınızla yapılan {tutar} TL işlem onaylanmıştır. Siz yapmadıysanız 444 0 333'ü arayın."),
    ("banka", "{banka} mobil uygulamamız yenilendi! Yeni özellikleri keşfedin: {url}"),
    ("banka", "Güvenliğiniz için: {banka} sizden asla SMS ile şifre veya kart bilgisi istemez. {url}"),
    ("banka", "Kartınız geçici olarak bloke edilmiştir. Lütfen şubenizle veya müşteri hizmetleriyle görüşünüz. {banka}"),
    ("edevlet", "e-Devlet Kapısı'na giriş yapıldı. Siz değilseniz şifrenizi turkiye.gov.tr üzerinden değiştirin."),
    ("edevlet", "Randevunuz {gun} günü saat 10:30'da oluşturulmuştur. MHRS üzerinden iptal edebilirsiniz {url}"),
    ("operator", "{operator}: Fatura tutarınız {tutar} TL, son ödeme tarihi {gun}. Detaylar {url}"),
    ("operator", "{operator}: Paketiniz yenilendi. Kalan kullanımınızı uygulamadan görebilirsiniz {url}"),
    ("magaza", "{magaza}'da hafta sonuna özel %20 indirim! Kampanya detayları {url}"),
    ("magaza", "Sepetinizde ürün kaldı, stoklar tükenmeden göz atın {url}"),
    ("kisisel", "{isim} akşam yemeğe geliyor musun? Adres burada {url}"),
    ("kisisel", "Şu haberi okudun mu? {url}"),
    ("kisisel", "Ders notlarını yükledim hocam, link: {url}"),
    ("kisisel", "Yarınki sunum için slaytlara buradan bakabilirsin {url}"),
    ("kisisel", "Toplantı {gun} saat 14:00'te, konum: {url}"),
    ("kisisel", "Konser biletlerini aldım, detaylar burada {url} :)"),
    ("kisisel", "{isim} doğum günün kutlu olsun! Sana bir şarkı buldum {url}"),
    ("kurum", "Üniversitemiz bahar dönemi ders kayıtları {gun} günü başlayacaktır. Duyuru: {url}"),
    ("kurum", "Abonelik bülteni: Bu haftanın öne çıkan içerikleri {url}"),
    ("kurum", "Doğrulama kodunuz 482913. Bu kodu kimseyle paylaşmayın."),
    ("kurum", "Belediyemizin {gun} günü düzenleyeceği etkinliğe davetlisiniz. Program: {url}"),
    ("kargo", "{kargo}: {kod} numaralı gönderiniz dağıtıma çıkmıştır. Kurye bugün 18:00'e kadar adresinizde olacak."),
    ("kargo", "Siparişiniz iade merkezimize ulaştı, ücret iadesi 3-5 iş günü içinde kartınıza yansıyacak. {magaza}"),
    ("kargo", "Teslimat noktanız değişti. Paketinizi {gun} gününe kadar en yakın şubeden alabilirsiniz. Şubeler: {url}"),
    ("banka", "{banka}: {gun} günü 02:00-05:00 arası planlı bakım nedeniyle mobil şube hizmet veremeyecektir."),
    ("banka", "{banka}: Hesap özetiniz hazır. Son ödeme tarihi {gun}, asgari tutar {tutar} TL. Detay mobil uygulamada."),
    ("banka", "{banka}: Maaşınız hesabınıza yatırılmıştır. İyi günlerde harcamanızı dileriz."),
    ("banka", "Dolandırıcılara dikkat! {banka} çalışanları sizden asla şifre istemez. Bilgi: {url}"),
    ("edevlet", "MHRS: {gun} günü Dahiliye randevunuzu unutmayın. Gelemeyecekseniz iptal ediniz."),
    ("edevlet", "Vergi beyannamesi verme süresi {gun} günü sona eriyor. Detaylı bilgi gib.gov.tr'de."),
    ("edevlet", "Nüfus müdürlüğü randevunuz onaylandı. Kimlik kartı başvurusu için belgeler: {url}"),
    ("operator", "{operator}: Yurt dışı paketiniz tanımlandı, iyi yolculuklar! Kullanım detayları {url}"),
    ("operator", "{operator}: Faturanız ödenmiştir, teşekkür ederiz. Fatura detayı: {url}"),
    ("magaza", "{magaza}: Favorilerindeki ürünün fiyatı düştü! Şimdi incele {url}"),
    ("magaza", "{magaza} siparişiniz onaylandı. Sipariş no {kod}. Kargo takip {url}"),
    ("magaza", "Mağazamıza gösterdiğiniz ilgi için teşekkürler. Yeni sezon ürünleri {url}"),
    ("kisisel", "Yarın sabah 9'da kampüste buluşalım mı? Kütüphanenin yeri: {url}"),
    ("kisisel", "Annecim eve gelirken ekmek alır mısın? Bir de şu tarifi denesek {url}"),
    ("kisisel", "{isim} maç kaçta başlıyor? Bilet linkini atıyorum {url}"),
    ("kisisel", "Proje toplantısının kaydı burada, izleyemeyenler için {url}"),
    ("kisisel", "Tatil fotoğraflarını albüme ekledim, sen de eklersin {url}"),
    ("kurum", "Sınav sonuçları açıklandı. Öğrenci bilgi sistemi üzerinden görüntüleyebilirsiniz {url}"),
    ("kurum", "Kütüphaneden aldığınız kitabın iade tarihi {gun}. Süre uzatmak için {url}"),
    ("kurum", "Kan bağışı kampanyamıza katılımınız için teşekkür ederiz. Bir sonraki etkinlik: {url}"),
]

SENDERS = ["", "", "", "[Bilgi] ", "BILGI: ", "Duyuru: ", "Sayın Müşterimiz, "]
CLOSINGS = ["", "", "", " İyi günler.", " Bilgilerinize.", " B001", " SMS almamak için RET yazıp gönderin."]
_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _augment(txt: str, rng: random.Random) -> str:
    """Gerçek SMS'lere benzer küçük varyasyonlar: Türkçe karaktersiz yazım, gönderen etiketi, kapanış."""
    if rng.random() < 0.35:
        txt = txt.translate(_ASCII)
    if rng.random() < 0.3:
        txt = rng.choice(SENDERS) + txt
    if rng.random() < 0.3:
        txt = txt + rng.choice(CLOSINGS)
    if rng.random() < 0.1:
        txt = txt.upper().replace("{URL}", "{url}")
    return txt


def _fill(tpl: str, rng: random.Random) -> str:
    out = tpl
    for key, vals in FILL.items():
        while "{" + key + "}" in out:
            out = out.replace("{" + key + "}", rng.choice(vals), 1)
    return out


def main(per_template: int = 12, test_ratio: float = 0.3, val_ratio: float = 0.2, seed: int = 7) -> None:
    rng = random.Random(seed)
    rows = []
    for label, pool, prefix in ((1, PHISHING, "P"), (0, LEGIT, "L")):
        ids = list(range(len(pool)))
        rng.shuffle(ids)
        n_test = max(1, round(len(ids) * test_ratio))
        n_val = max(1, round(len(ids) * val_ratio))
        test_ids, val_ids = set(ids[:n_test]), set(ids[n_test:n_test + n_val])
        for i, (cat, tpl) in enumerate(pool):
            split = "test" if i in test_ids else ("val" if i in val_ids else "train")
            seen = set()
            for _ in range(per_template * 3):
                txt = _augment(_fill(tpl, rng), rng)
                if txt in seen:
                    continue
                seen.add(txt)
                rows.append({"text": txt, "label": label, "category": cat,
                             "template_id": f"{prefix}{i:02d}", "split": split})
                if len(seen) >= per_template:
                    break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["text", "label", "category", "template_id", "split"])
        w.writeheader()
        w.writerows(rows)
    n = {k: sum(r["split"] == k for r in rows) for k in ("train", "val", "test")}
    print(f"{len(rows)} senaryo yazıldı ({n['train']} eğitim, {n['val']} doğrulama, {n['test']} test) -> {OUT}")


if __name__ == "__main__":
    main()
