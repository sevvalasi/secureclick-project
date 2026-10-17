package tr.edu.erdogan.secureclick;

import android.content.Context;
import android.content.SharedPreferences;

/** Uygulama ayarları (cihazda yerel olarak saklanır). */
public final class Prefs {

    private static final String FILE = "secureclick";
    private final SharedPreferences sp;

    public Prefs(Context c) {
        sp = c.getApplicationContext().getSharedPreferences(FILE, Context.MODE_PRIVATE);
    }

    public String server() {
        return sp.getString("server", BuildConfig.DEFAULT_SERVER);
    }

    public void setServer(String url) {
        String u = url.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        if (!u.isEmpty() && !u.matches("(?i)^https?://.*")) u = "http://" + u;
        sp.edit().putString("server", u.isEmpty() ? BuildConfig.DEFAULT_SERVER : u).apply();
    }

    public boolean liveChecks() {
        return sp.getBoolean("live_checks", false);
    }

    public void setLiveChecks(boolean v) {
        sp.edit().putBoolean("live_checks", v).apply();
    }

    public boolean smsGuard() {
        return sp.getBoolean("sms_guard", false);
    }

    public void setSmsGuard(boolean v) {
        sp.edit().putBoolean("sms_guard", v).apply();
    }

    SharedPreferences raw() {
        return sp;
    }
}
