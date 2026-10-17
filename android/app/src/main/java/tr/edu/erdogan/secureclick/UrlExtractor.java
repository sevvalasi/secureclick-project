package tr.edu.erdogan.secureclick;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Mesaj metninden bağlantıları çıkarır (secureclick.features.text_features.extract_urls ile uyumlu). */
public final class UrlExtractor {

    private static final Pattern URL = Pattern.compile(
            "(?i)\\b((?:https?://|www\\.)[^\\s<>\"'()]+"
                    + "|(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+"
                    + "(?:com|net|org|info|biz|xyz|top|site|online|live|shop|link|click|ly|gl|co|me|io|app|"
                    + "tr|com\\.tr|gov\\.tr|ru|cn|tk|ml|ga|cf|gq|icu|cc|to|in|us|eu|de|uk|vip|pro|club)"
                    + "(?:/[^\\s<>\"'()]*)?)");

    private UrlExtractor() {
    }

    public static List<String> extract(String text) {
        Set<String> out = new LinkedHashSet<>();
        Matcher m = URL.matcher(text);
        while (m.find()) {
            String u = m.group(1).replaceAll("[.,;:!?)\\]}]+$", "");
            String hostPart = u.split("/", 2)[0];
            if (hostPart.contains("@") && !u.toLowerCase(Locale.ROOT).startsWith("http")) {
                continue;  // e-posta adresi
            }
            // e-posta adresinin alan adı kısmını bağlantı sanma
            int start = m.start(1);
            if (start > 0 && text.charAt(start - 1) == '@') {
                continue;
            }
            out.add(u);
        }
        return new ArrayList<>(out);
    }
}
