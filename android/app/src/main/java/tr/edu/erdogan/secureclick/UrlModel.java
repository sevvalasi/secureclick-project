package tr.edu.erdogan.secureclick;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Cihaz üzerinde (çevrimdışı) çalışan hafif URL modeli.
 *
 * ml/export_mobile_model.py ile eğitilen modelin birebir Java karşılığıdır:
 * normalize_url -> küçük harf -> karakter 3-5 gram -> MurmurHash3 (seed 0) ile 2^18 boyuta
 * indeksleme -> L2 normalizasyon -> lojistik regresyon. Android bağımlılığı yoktur (yalnızca
 * org.json); bu sayede JDK ile doğrudan test edilebilir.
 */
public final class UrlModel {

    private static final Pattern SCHEME = Pattern.compile("^[a-zA-Z][a-zA-Z0-9+.-]*://");
    private static final Pattern MULTI_WS = Pattern.compile("\\s\\s+");

    private final int nFeatures;
    private final int ngramMin;
    private final int ngramMax;
    private final float intercept;
    private final float threshold;
    private final Map<Integer, Float> weights;

    public UrlModel(int nFeatures, int ngramMin, int ngramMax, float intercept, float threshold,
                    int[] indices, float[] values) {
        this.nFeatures = nFeatures;
        this.ngramMin = ngramMin;
        this.ngramMax = ngramMax;
        this.intercept = intercept;
        this.threshold = threshold;
        this.weights = new HashMap<>(indices.length * 2);
        for (int i = 0; i < indices.length; i++) {
            weights.put(indices[i], values[i]);
        }
    }

    /** assets/url_model.json içeriğinden modeli oluşturur. */
    public static UrlModel fromJson(String json) throws JSONException {
        JSONObject o = new JSONObject(json);
        JSONArray idx = o.getJSONArray("indices");
        JSONArray w = o.getJSONArray("weights");
        int[] indices = new int[idx.length()];
        float[] weights = new float[w.length()];
        for (int i = 0; i < indices.length; i++) {
            indices[i] = idx.getInt(i);
            weights[i] = (float) w.getDouble(i);
        }
        return new UrlModel(o.getInt("n_features"), o.getInt("ngram_min"), o.getInt("ngram_max"),
                (float) o.getDouble("intercept"), (float) o.getDouble("threshold"), indices, weights);
    }

    public float threshold() {
        return threshold;
    }

    /** secureclick.features.url_features.normalize_url ile aynı. */
    public static String normalize(String url) {
        String u = url.strip();
        u = stripChars(u, "\"'<>");
        u = SCHEME.matcher(u).replaceFirst("");
        int slash = u.indexOf('/');
        String host = slash < 0 ? u : u.substring(0, slash);
        String rest = slash < 0 ? "" : u.substring(slash);
        host = host.toLowerCase(Locale.ROOT);
        if (host.startsWith("www.")) {
            host = host.substring(4);
        }
        u = host + rest;
        int end = u.length();
        while (end > 0 && u.charAt(end - 1) == '/') {
            end--;
        }
        return u.substring(0, end);
    }

    private static String stripChars(String s, String chars) {
        int start = 0, end = s.length();
        while (start < end && chars.indexOf(s.charAt(start)) >= 0) start++;
        while (end > start && chars.indexOf(s.charAt(end - 1)) >= 0) end--;
        return s.substring(start, end);
    }

    /** Zararlı olma olasılığı (0-1). */
    public float predict(String url) {
        String doc = normalize(url).toLowerCase(Locale.ROOT);
        doc = MULTI_WS.matcher(doc).replaceAll(" ");
        int[] cps = doc.codePoints().toArray();

        // scikit-learn HashingVectorizer(analyzer="char", alternate_sign=False, norm="l2")
        Map<Integer, Integer> counts = new HashMap<>();
        for (int n = ngramMin; n <= Math.min(ngramMax, cps.length); n++) {
            for (int i = 0; i + n <= cps.length; i++) {
                String gram = new String(cps, i, n);
                int idx = index(murmur3(gram.getBytes(StandardCharsets.UTF_8)));
                counts.merge(idx, 1, Integer::sum);
            }
        }
        double norm = 0;
        for (int c : counts.values()) norm += (double) c * c;
        norm = Math.sqrt(norm);
        if (norm == 0) return sigmoid(intercept);

        double z = intercept;
        for (Map.Entry<Integer, Integer> e : counts.entrySet()) {
            Float w = weights.get(e.getKey());
            if (w != null) z += w * (e.getValue() / norm);
        }
        return sigmoid(z);
    }

    private int index(int h) {
        if (h == Integer.MIN_VALUE) {
            return (int) (2147483648L % nFeatures);  // sklearn: abs(-2^31) % n
        }
        return Math.abs(h) % nFeatures;
    }

    private static float sigmoid(double z) {
        return (float) (1.0 / (1.0 + Math.exp(-z)));
    }

    /** MurmurHash3 x86 32-bit, seed 0 (sklearn.utils.murmurhash3_32 ile aynı). */
    static int murmur3(byte[] data) {
        final int c1 = 0xcc9e2d51, c2 = 0x1b873593;
        int h1 = 0;
        int len = data.length;
        int nblocks = len / 4;
        for (int i = 0; i < nblocks; i++) {
            int k1 = (data[4 * i] & 0xff) | ((data[4 * i + 1] & 0xff) << 8)
                    | ((data[4 * i + 2] & 0xff) << 16) | ((data[4 * i + 3] & 0xff) << 24);
            k1 *= c1;
            k1 = Integer.rotateLeft(k1, 15);
            k1 *= c2;
            h1 ^= k1;
            h1 = Integer.rotateLeft(h1, 13);
            h1 = h1 * 5 + 0xe6546b64;
        }
        int k1 = 0;
        int tail = nblocks * 4;
        switch (len & 3) {
            case 3: k1 ^= (data[tail + 2] & 0xff) << 16;
            case 2: k1 ^= (data[tail + 1] & 0xff) << 8;
            case 1: k1 ^= (data[tail] & 0xff);
                k1 *= c1;
                k1 = Integer.rotateLeft(k1, 15);
                k1 *= c2;
                h1 ^= k1;
            default:
        }
        h1 ^= len;
        h1 ^= h1 >>> 16;
        h1 *= 0x85ebca6b;
        h1 ^= h1 >>> 13;
        h1 *= 0xc2b2ae35;
        h1 ^= h1 >>> 16;
        return h1;
    }
}
