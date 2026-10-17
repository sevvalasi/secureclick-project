package tr.edu.erdogan.secureclick;

import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.core.content.ContextCompat;

import com.google.android.material.card.MaterialCardView;
import com.google.android.material.progressindicator.LinearProgressIndicator;

import java.util.List;
import java.util.Locale;

/** Analiz sonucunu kartlar hâlinde bir LinearLayout'a çizer (ana ekran ve bağlantı penceresi). */
final class ResultRenderer {

    private final Context c;

    ResultRenderer(Context c) {
        this.c = c;
    }

    void render(LinearLayout root, AnalysisResult r, boolean compact) {
        root.removeAllViews();
        root.addView(verdictBanner(r));
        if (r.offline) root.addView(note(c.getString(R.string.offline_note), R.color.warn));

        for (AnalysisResult.Link l : r.links) {
            LinearLayout box = card(root);
            LinearLayout head = row();
            TextView url = text(l.url, 13, R.color.text);
            url.setTypeface(Typeface.MONOSPACE);
            head.addView(url, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            head.addView(badge(l.verdict));
            box.addView(head);
            if (!compact) {
                if (l.randomForest != null && !l.randomForest.isNaN()) box.addView(bar(R.string.model_rf, l.randomForest));
                if (l.svm != null && !l.svm.isNaN()) box.addView(bar(R.string.model_svm, l.svm));
            }
            if (l.ensemble != null && !l.ensemble.isNaN()) box.addView(bar(R.string.model_ensemble, l.ensemble));
            if (!compact && r.textScore != null) box.addView(bar(R.string.model_text, r.textScore));
            box.addView(bar(R.string.model_final, l.score));
            addSignals(box, l.signals);
        }

        if (!compact && (r.textScore != null || !r.textSignals.isEmpty())) {
            LinearLayout box = card(root);
            TextView h = text(c.getString(R.string.text_analysis), 15, R.color.text);
            h.setTypeface(Typeface.DEFAULT_BOLD);
            box.addView(h);
            addSignals(box, r.textSignals);
            if (r.links.isEmpty()) box.addView(note(c.getString(R.string.no_links), R.color.muted));
        }

        String src = c.getString(r.offline ? R.string.source_offline : R.string.source_online);
        TextView foot = text(String.format(Locale.ROOT, c.getString(R.string.elapsed), src, r.elapsedMs), 12, R.color.muted);
        foot.setPadding(0, dp(6), 0, 0);
        root.addView(foot);
    }

    // ------------------------------------------------------------------ parçalar

    private View verdictBanner(AnalysisResult r) {
        int fg, bg, title, desc;
        String icon;
        switch (r.verdict) {
            case MALICIOUS:
                fg = R.color.danger; bg = R.color.danger_bg; title = R.string.verdict_malicious;
                desc = R.string.verdict_malicious_desc; icon = "⛔";
                break;
            case SUSPICIOUS:
                fg = R.color.warn; bg = R.color.warn_bg; title = R.string.verdict_suspicious;
                desc = R.string.verdict_suspicious_desc; icon = "⚠️";
                break;
            default:
                fg = R.color.safe; bg = R.color.safe_bg; title = R.string.verdict_safe;
                desc = R.string.verdict_safe_desc; icon = "✅";
        }
        LinearLayout b = row();
        b.setGravity(Gravity.CENTER_VERTICAL);
        b.setPadding(dp(16), dp(14), dp(16), dp(14));
        b.setBackground(rounded(bg));
        b.addView(text(icon, 26, fg));

        LinearLayout mid = new LinearLayout(c);
        mid.setOrientation(LinearLayout.VERTICAL);
        mid.setPadding(dp(12), 0, dp(8), 0);
        TextView t = text(c.getString(title), 17, fg);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        mid.addView(t);
        mid.addView(text(c.getString(desc), 13, fg));
        b.addView(mid, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));

        LinearLayout sc = new LinearLayout(c);
        sc.setOrientation(LinearLayout.VERTICAL);
        sc.setGravity(Gravity.END);
        TextView pct = text(pct(r.score), 22, fg);
        pct.setTypeface(Typeface.DEFAULT_BOLD);
        sc.addView(pct);
        sc.addView(text(c.getString(R.string.risk_score), 11, fg));
        b.addView(sc);
        b.setContentDescription(c.getString(title) + ", " + pct(r.score));
        return b;
    }

    private LinearLayout card(LinearLayout root) {
        MaterialCardView card = new MaterialCardView(c);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(10);
        card.setLayoutParams(lp);
        card.setRadius(dp(14));
        card.setCardElevation(0);
        card.setStrokeWidth(dp(1));
        card.setStrokeColor(ContextCompat.getColor(c, R.color.surface2));
        card.setCardBackgroundColor(ContextCompat.getColor(c, R.color.surface));
        LinearLayout inner = new LinearLayout(c);
        inner.setOrientation(LinearLayout.VERTICAL);
        inner.setPadding(dp(14), dp(12), dp(14), dp(12));
        card.addView(inner);
        root.addView(card);
        return inner;
    }

    private View badge(AnalysisResult.Verdict v) {
        int fg = v == AnalysisResult.Verdict.MALICIOUS ? R.color.danger
                : v == AnalysisResult.Verdict.SUSPICIOUS ? R.color.warn : R.color.safe;
        int bg = v == AnalysisResult.Verdict.MALICIOUS ? R.color.danger_bg
                : v == AnalysisResult.Verdict.SUSPICIOUS ? R.color.warn_bg : R.color.safe_bg;
        String label = v == AnalysisResult.Verdict.MALICIOUS ? "ZARARLI"
                : v == AnalysisResult.Verdict.SUSPICIOUS ? "ŞÜPHELİ" : "GÜVENLİ";
        TextView t = text(label, 11, fg);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(dp(8), dp(3), dp(8), dp(3));
        t.setBackground(rounded(bg));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMarginStart(dp(8));
        t.setLayoutParams(lp);
        return t;
    }

    private View bar(int labelRes, double v) {
        LinearLayout r = row();
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(0, dp(6), 0, 0);
        TextView l = text(c.getString(labelRes), 12, R.color.muted);
        r.addView(l, new LinearLayout.LayoutParams(dp(118), LinearLayout.LayoutParams.WRAP_CONTENT));
        LinearProgressIndicator p = new LinearProgressIndicator(c);
        p.setMax(1000);
        p.setProgressCompat((int) Math.round(v * 1000), false);
        p.setTrackCornerRadius(dp(4));
        p.setTrackThickness(dp(6));
        r.addView(p, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        TextView val = text(pct(v), 12, R.color.text);
        val.setGravity(Gravity.END);
        r.addView(val, new LinearLayout.LayoutParams(dp(44), LinearLayout.LayoutParams.WRAP_CONTENT));
        return r;
    }

    private void addSignals(LinearLayout box, List<AnalysisResult.Signal> signals) {
        if (signals.isEmpty()) {
            box.addView(note(c.getString(R.string.no_signals), R.color.muted));
            return;
        }
        for (AnalysisResult.Signal s : signals) {
            int col;
            switch (s.level) {
                case "high": col = R.color.danger; break;
                case "medium": col = R.color.warn; break;
                case "info": col = R.color.safe; break;
                default: col = R.color.muted;
            }
            LinearLayout r = row();
            r.setPadding(0, dp(8), 0, 0);
            r.addView(text("●", 12, col));
            TextView m = text(s.message, 13, R.color.text);
            m.setPadding(dp(8), 0, 0, 0);
            r.addView(m, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            box.addView(r);
        }
    }

    private TextView note(String s, int color) {
        TextView t = text(s, 13, color);
        t.setPadding(0, dp(8), 0, 0);
        return t;
    }

    private LinearLayout row() {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        return l;
    }

    private TextView text(String s, int sp, int colorRes) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(ContextCompat.getColor(c, colorRes));
        return t;
    }

    private GradientDrawable rounded(int colorRes) {
        GradientDrawable d = new GradientDrawable();
        d.setCornerRadius(dp(14));
        d.setColor(ContextCompat.getColor(c, colorRes));
        return d;
    }

    private static String pct(double v) {
        return Math.round(v * 100) + "%";
    }

    private int dp(int v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }
}
