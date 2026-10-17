package tr.edu.erdogan.secureclick;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.format.DateUtils;
import android.util.TypedValue;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.progressindicator.LinearProgressIndicator;
import com.google.android.material.textfield.TextInputEditText;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    static final String ACTION_SHOW = "tr.edu.erdogan.secureclick.SHOW";

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    private TextInputEditText input;
    private MaterialButton analyzeBtn;
    private LinearProgressIndicator progress;
    private LinearLayout result, history;
    private ScrollView scroll;
    private ResultRenderer renderer;
    private HistoryStore store;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        MaterialToolbar tb = findViewById(R.id.toolbar);
        tb.inflateMenu(R.menu.main);
        tb.setOnMenuItemClickListener(item -> {
            if (item.getItemId() == R.id.action_settings) {
                startActivity(new Intent(this, SettingsActivity.class));
                return true;
            }
            return false;
        });

        input = findViewById(R.id.input);
        analyzeBtn = findViewById(R.id.analyze);
        progress = findViewById(R.id.progress);
        result = findViewById(R.id.result);
        history = findViewById(R.id.history);
        scroll = findViewById(R.id.scroll);
        renderer = new ResultRenderer(this);
        store = new HistoryStore(this);

        analyzeBtn.setOnClickListener(v -> runAnalysis());
        findViewById(R.id.paste).setOnClickListener(v -> pasteFromClipboard());
        findViewById(R.id.clearHistory).setOnClickListener(v -> {
            store.clear();
            renderHistory();
        });
        Analyzer.model(this);  // cihaz modelini önceden yükle (çevrimdışı mod)
        handleIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderHistory();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
    }

    /** Paylaş menüsü, metin seçimi veya bildirimden gelen metni alıp hemen analiz eder. */
    private void handleIntent(Intent intent) {
        if (intent == null) return;
        CharSequence text = null;
        String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action) || ACTION_SHOW.equals(action)) {
            text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT);
        } else if (Intent.ACTION_PROCESS_TEXT.equals(action)) {
            text = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT);
        }
        if (text != null && text.length() > 0) {
            input.setText(text);
            runAnalysis();
        }
    }

    private void pasteFromClipboard() {
        ClipboardManager cm = getSystemService(ClipboardManager.class);
        ClipData clip = cm == null ? null : cm.getPrimaryClip();
        if (clip != null && clip.getItemCount() > 0) {
            CharSequence t = clip.getItemAt(0).coerceToText(this);
            if (t != null) input.setText(t);
        }
    }

    private void runAnalysis() {
        String text = input.getText() == null ? "" : input.getText().toString().trim();
        if (text.isEmpty()) {
            Toast.makeText(this, R.string.empty_input, Toast.LENGTH_SHORT).show();
            return;
        }
        hideKeyboard();
        setBusy(true);
        // Tek satırlık, boşluksuz giriş bağlantı olarak, diğerleri mesaj olarak gönderilir
        boolean looksLikeUrl = !text.contains(" ") && !text.contains("\n") && text.contains(".");
        String message = looksLikeUrl ? "" : text;
        String url = looksLikeUrl ? text : "";
        Analyzer analyzer = new Analyzer(this);
        io.execute(() -> {
            AnalysisResult r = analyzer.analyze(message, url);
            store.add(text, r);
            main.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                setBusy(false);
                renderer.render(result, r, false);
                renderHistory();
                scroll.post(() -> scroll.smoothScrollTo(0, result.getTop() - 24));
            });
        });
    }

    private void setBusy(boolean busy) {
        progress.setVisibility(busy ? View.VISIBLE : View.GONE);
        analyzeBtn.setEnabled(!busy);
        analyzeBtn.setText(busy ? R.string.analyzing : R.string.analyze);
    }

    private void renderHistory() {
        history.removeAllViews();
        java.util.List<HistoryStore.Entry> items = store.list();
        if (items.isEmpty()) {
            history.addView(line(getString(R.string.no_history), R.color.muted));
            return;
        }
        for (HistoryStore.Entry e : items.subList(0, Math.min(10, items.size()))) {
            int col = "MALICIOUS".equals(e.verdict) ? R.color.danger
                    : "SUSPICIOUS".equals(e.verdict) ? R.color.warn : R.color.safe;
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setPadding(0, dp(8), 0, dp(8));
            row.addView(line("●", col));
            TextView t = line(e.input.replace('\n', ' '), R.color.text);
            t.setSingleLine(true);
            t.setEllipsize(android.text.TextUtils.TruncateAt.END);
            t.setPadding(dp(8), 0, dp(8), 0);
            row.addView(t, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            row.addView(line(DateUtils.getRelativeTimeSpanString(e.time).toString(), R.color.muted));
            row.setOnClickListener(v -> {
                input.setText(e.input);
                runAnalysis();
            });
            history.addView(row);
        }
    }

    private TextView line(String s, int colorRes) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        t.setTextColor(ContextCompat.getColor(this, colorRes));
        return t;
    }

    private void hideKeyboard() {
        InputMethodManager imm = getSystemService(InputMethodManager.class);
        if (imm != null) imm.hideSoftInputFromWindow(input.getWindowToken(), 0);
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
