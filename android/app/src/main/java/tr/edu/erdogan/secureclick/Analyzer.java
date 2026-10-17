package tr.edu.erdogan.secureclick;

import android.content.Context;

import org.json.JSONException;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Önce sunucudaki tam modeli (URL + Türkçe metin füzyonu) dener; sunucuya ulaşılamazsa
 * cihazdaki hafif URL modeline (UrlModel) geçer.
 */
public final class Analyzer {

    private static volatile UrlModel model;

    private static final Set<String> SHORTENERS = new HashSet<>(Arrays.asList(
            "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "cutt.ly", "rebrand.ly",
            "shorturl.at", "tiny.cc", "rb.gy", "t.ly", "s.id", "v.gd", "qrco.de", "ead.me", "q-r.to"));
    private static final Set<String> SUSPICIOUS_TLDS = new HashSet<>(Arrays.asList(
            "zip", "mov", "xyz", "top", "click", "link", "work", "support", "rest", "tk", "ml", "ga", "cf",
            "gq", "icu", "cyou", "buzz", "sbs", "cfd", "online", "site", "live", "shop", "info", "bond", "cam"));
    private static final String[] SUSPICIOUS_WORDS = {
            "login", "signin", "verify", "secure", "account", "update", "confirm", "password", "webscr",
            "giris", "dogrula", "guvenlik", "hesap", "sifre", "odeme", "iade", "ceza", "borc"};
    /** Marka -> resmî alan adı sonekleri (secureclick.features.url_features.OFFICIAL_DOMAINS'in özeti). */
    private static final String[][] BRANDS = {
            {"paypal", "paypal.com"}, {"apple", "apple.com"}, {"icloud", "icloud.com"},
            {"microsoft", "microsoft.com"}, {"netflix", "netflix.com"}, {"instagram", "instagram.com"},
            {"whatsapp", "whatsapp.com"}, {"facebook", "facebook.com"}, {"amazon", "amazon.com"},
            {"garanti", "garantibbva.com.tr"}, {"akbank", "akbank.com"}, {"ziraat", "ziraatbank.com.tr"},
            {"isbank", "isbank.com.tr"}, {"yapikredi", "yapikredi.com.tr"}, {"halkbank", "halkbank.com.tr"},
            {"vakifbank", "vakifbank.com.tr"}, {"ptt", "ptt.gov.tr"}, {"edevlet", "turkiye.gov.tr"},
            {"e-devlet", "turkiye.gov.tr"}, {"hepsiburada", "hepsiburada.com"}, {"trendyol", "trendyol.com"},
            {"turkcell", "turkcell.com.tr"}, {"vodafone", "vodafone.com.tr"}, {"papara", "papara.com"}};
    private static final Pattern IPV4 = Pattern.compile("^\\d{1,3}(\\.\\d{1,3}){3}$");
    private static final Pattern RISKY_EXT = Pattern.compile(
            "(?i).*\\.(exe|apk|sh|bin|scr|bat|cmd|msi|jar|vbs|ps1|zip|rar|7z|iso)$");

    private final Context ctx;
    private final Prefs prefs;

    public Analyzer(Context c) {
        ctx = c.getApplicationContext();
        prefs = new Prefs(ctx);
    }

    /** Arka plan iş parçacığında çağrılmalıdır (ağ erişimi yapar). */
    public AnalysisResult analyze(String message, String url) {
        long t0 = System.nanoTime();
        try {
            return new ApiClient(prefs.server()).analyze(message, url, prefs.liveChecks());
        } catch (IOException e) {
            AnalysisResult r = analyzeOffline(message, url);
            r.elapsedMs = (System.nanoTime() - t0) / 1e6;
            return r;
        }
    }

    public AnalysisResult analyzeOffline(String message, String url) {
        UrlModel m = model(ctx);
        AnalysisResult r = new AnalysisResult();
        r.offline = true;
        List<String> urls = new java.util.ArrayList<>();
        if (url != null && !url.trim().isEmpty()) urls.add(url.trim());
        if (message != null) {
            for (String u : UrlExtractor.extract(message)) if (!urls.contains(u)) urls.add(u);
        }
        float thr = m.threshold();
        for (String u : urls) {
            AnalysisResult.Link link = new AnalysisResult.Link();
            link.url = u;
            link.ensemble = (double) m.predict(u);
            link.score = link.ensemble;
            link.verdict = link.score >= thr ? AnalysisResult.Verdict.MALICIOUS
                    : link.score >= thr * 0.6 ? AnalysisResult.Verdict.SUSPICIOUS
                    : AnalysisResult.Verdict.SAFE;
            addHeuristics(u, link);
            r.links.add(link);
            if (link.verdict.severity() > r.verdict.severity()
                    || (link.verdict == r.verdict && link.score > r.score)) {
                r.verdict = link.verdict;
                r.score = link.score;
            }
        }
        return r;
    }

    private static void addHeuristics(String url, AnalysisResult.Link link) {
        String withScheme = url.matches("(?i)^[a-z][a-z0-9+.-]*://.*") ? url : "http://" + url;
        String host = "";
        int port = -1;
        String path = "";
        try {
            URI uri = new URI(withScheme.replace(" ", "%20"));
            host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(Locale.ROOT);
            port = uri.getPort();
            path = uri.getPath() == null ? "" : uri.getPath();
        } catch (Exception ignored) {
        }
        if (host.startsWith("www.")) host = host.substring(4);
        if (IPV4.matcher(host).matches()) add(link, "high", "Alan adı yerine doğrudan IP adresi kullanılıyor.");
        if (url.contains("@")) add(link, "high", "URL içinde '@' karakteri var; tarayıcı '@' öncesini yok sayar.");
        if (host.contains("xn--")) add(link, "high", "Punycode (xn--) alan adı: benzer görünen karakterlerle taklit olabilir.");
        if (RISKY_EXT.matcher(path).matches()) add(link, "high", "Bağlantı çalıştırılabilir/arşiv dosyasına işaret ediyor.");
        if (SHORTENERS.contains(host)) add(link, "medium", "URL kısaltma servisi kullanılıyor; gerçek hedef gizleniyor.");
        if (port > 0 && port != 80 && port != 443) add(link, "medium", "Standart dışı port numarası kullanılıyor.");
        if (!IPV4.matcher(host).matches()) {
            for (String[] b : BRANDS) {
                boolean inHost = b[0].length() >= 5 ? host.contains(b[0])
                        : Arrays.asList(host.split("[^a-z0-9]+")).contains(b[0]);
                if (inHost && !(host.equals(b[1]) || host.endsWith("." + b[1]) || host.endsWith(".gov.tr"))) {
                    add(link, "high", "Bilinen bir marka adı geçiyor ama alan adı o markaya ait değil.");
                    break;
                }
            }
            String tld = host.substring(host.lastIndexOf('.') + 1);
            if (SUSPICIOUS_TLDS.contains(tld)) add(link, "medium", "Kötüye kullanımı sık görülen bir üst düzey alan adı (TLD).");
            int dots = host.length() - host.replace(".", "").length();
            if (dots >= 4) add(link, "medium", "Çok sayıda alt alan adı (" + (dots - 1) + ").");
        }
        String lower = url.toLowerCase(Locale.ROOT);
        int words = 0;
        for (String w : SUSPICIOUS_WORDS) if (lower.contains(w)) words++;
        if (words >= 2) add(link, "medium", "URL'de 'giriş/doğrula/hesap/şifre' gibi kimlik avı kelimeleri var.");
        if (url.length() > 100) add(link, "low", "URL alışılmadık derecede uzun (" + url.length() + " karakter).");
    }

    private static void add(AnalysisResult.Link link, String level, String msg) {
        link.signals.add(new AnalysisResult.Signal(level, msg));
    }

    static UrlModel model(Context c) {
        if (model == null) {
            synchronized (Analyzer.class) {
                if (model == null) model = loadModel(c);
            }
        }
        return model;
    }

    private static UrlModel loadModel(Context c) {
        try (InputStream is = c.getAssets().open("url_model.json")) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = is.read(buf)) > 0) bos.write(buf, 0, n);
            return UrlModel.fromJson(bos.toString("UTF-8"));
        } catch (IOException | JSONException e) {
            throw new IllegalStateException("Cihaz modeli yüklenemedi", e);
        }
    }
}
