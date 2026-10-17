package tr.edu.erdogan.secureclick;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** /api/analyze yanıtının (veya çevrimdışı analizin) uygulama içi karşılığı. */
public final class AnalysisResult {

    public enum Verdict {
        SAFE, SUSPICIOUS, MALICIOUS;

        static Verdict parse(String s) {
            switch (s) {
                case "malicious": return MALICIOUS;
                case "suspicious": return SUSPICIOUS;
                default: return SAFE;
            }
        }

        int severity() {
            return ordinal();
        }
    }

    public static final class Signal {
        public final String level;    // high | medium | low | info
        public final String message;

        public Signal(String level, String message) {
            this.level = level;
            this.message = message;
        }
    }

    public static final class Link {
        public String url;
        public Verdict verdict;
        public double score;
        public Double randomForest, svm, ensemble;  // çevrimdışı modda yalnızca ensemble dolu
        public final List<Signal> signals = new ArrayList<>();
    }

    public Verdict verdict = Verdict.SAFE;
    public double score;
    public final List<Link> links = new ArrayList<>();
    public Double textScore;
    public final List<Signal> textSignals = new ArrayList<>();
    public double elapsedMs;
    /** Sonuç sunucudaki tam modelden mi, cihazdaki hafif modelden mi geldi? */
    public boolean offline;

    static AnalysisResult fromJson(JSONObject o) throws JSONException {
        AnalysisResult r = new AnalysisResult();
        r.verdict = Verdict.parse(o.getString("verdict"));
        r.score = o.getDouble("score");
        r.elapsedMs = o.optDouble("elapsed_ms", 0);
        JSONArray links = o.optJSONArray("links");
        if (links != null) {
            for (int i = 0; i < links.length(); i++) {
                JSONObject l = links.getJSONObject(i);
                Link link = new Link();
                link.url = l.getString("url");
                link.verdict = Verdict.parse(l.getString("verdict"));
                link.score = l.getDouble("score");
                JSONObject ms = l.optJSONObject("model_scores");
                if (ms != null) {
                    link.randomForest = ms.optDouble("random_forest");
                    link.svm = ms.optDouble("svm");
                    link.ensemble = ms.optDouble("ensemble");
                }
                parseSignals(l.optJSONArray("signals"), link.signals);
                r.links.add(link);
            }
        }
        JSONObject text = o.optJSONObject("text");
        if (text != null) {
            if (!text.isNull("score")) r.textScore = text.getDouble("score");
            parseSignals(text.optJSONArray("signals"), r.textSignals);
        }
        return r;
    }

    private static void parseSignals(JSONArray arr, List<Signal> out) throws JSONException {
        if (arr == null) return;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject s = arr.getJSONObject(i);
            out.add(new Signal(s.optString("level", "low"), s.getString("message")));
        }
    }
}
