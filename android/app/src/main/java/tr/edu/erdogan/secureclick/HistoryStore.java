package tr.edu.erdogan.secureclick;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Son analizlerin cihazda tutulan kısa geçmişi (sunucuya gönderilmez). */
public final class HistoryStore {

    private static final int MAX = 30;
    private static final String KEY = "history";
    private final Prefs prefs;

    public static final class Entry {
        public final long time;
        public final String input;
        public final String verdict;
        public final double score;

        Entry(long time, String input, String verdict, double score) {
            this.time = time;
            this.input = input;
            this.verdict = verdict;
            this.score = score;
        }
    }

    public HistoryStore(Context c) {
        prefs = new Prefs(c);
    }

    public synchronized void add(String input, AnalysisResult r) {
        JSONArray arr = load();
        JSONArray out = new JSONArray();
        try {
            JSONObject e = new JSONObject();
            e.put("t", System.currentTimeMillis());
            e.put("in", input.length() > 300 ? input.substring(0, 300) : input);
            e.put("v", r.verdict.name());
            e.put("s", r.score);
            out.put(e);
            for (int i = 0; i < arr.length() && out.length() < MAX; i++) out.put(arr.get(i));
        } catch (JSONException ignored) {
        }
        prefs.raw().edit().putString(KEY, out.toString()).apply();
    }

    public synchronized List<Entry> list() {
        List<Entry> out = new ArrayList<>();
        JSONArray arr = load();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject e = arr.optJSONObject(i);
            if (e != null) {
                out.add(new Entry(e.optLong("t"), e.optString("in"), e.optString("v"), e.optDouble("s")));
            }
        }
        return out;
    }

    public synchronized void clear() {
        prefs.raw().edit().remove(KEY).apply();
    }

    private JSONArray load() {
        try {
            return new JSONArray(prefs.raw().getString(KEY, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }
}
