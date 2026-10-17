package tr.edu.erdogan.secureclick;

import android.content.ComponentName;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.google.android.material.button.MaterialButton;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * "Tıklamadan önce" koruması: SecureClick varsayılan bağlantı açıcı yapıldığında, kullanıcının
 * herhangi bir uygulamada dokunduğu http/https bağlantısı önce burada analiz edilir. Kullanıcı
 * sonucu gördükten sonra bağlantıyı başka bir tarayıcıda açmayı seçebilir.
 */
public class LinkCheckActivity extends AppCompatActivity {

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private Uri target;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_link_check);
        setFinishOnTouchOutside(false);

        target = getIntent().getData();
        if (target == null) {
            finish();
            return;
        }
        String url = target.toString();
        ((TextView) findViewById(R.id.url)).setText(url);
        MaterialButton open = findViewById(R.id.open);
        findViewById(R.id.close).setOnClickListener(v -> finish());
        open.setOnClickListener(v -> openElsewhere());

        LinearLayout result = findViewById(R.id.result);
        View progress = findViewById(R.id.progress);
        Analyzer analyzer = new Analyzer(this);
        io.execute(() -> {
            AnalysisResult r = analyzer.analyze("", url);
            new HistoryStore(this).add(url, r);
            main.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                progress.setVisibility(View.GONE);
                new ResultRenderer(this).render(result, r, true);
                open.setEnabled(true);
                if (r.verdict == AnalysisResult.Verdict.MALICIOUS) {
                    // Zararlı bağlantıda açma düğmesi ikincil ve kırmızı olur
                    open.setText(R.string.open_anyway);
                    open.setBackgroundTintList(ColorStateList.valueOf(
                            ContextCompat.getColor(this, R.color.danger_bg)));
                    open.setTextColor(ContextCompat.getColor(this, R.color.danger));
                }
            });
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
    }

    /** Bağlantıyı SecureClick dışındaki bir uygulamada (tarayıcı) açar; kendi kendine döngüyü önler. */
    private void openElsewhere() {
        Intent view = new Intent(Intent.ACTION_VIEW, target).addCategory(Intent.CATEGORY_BROWSABLE);
        Intent chooser = Intent.createChooser(view, null);
        chooser.putExtra(Intent.EXTRA_EXCLUDE_COMPONENTS, new ComponentName[]{
                new ComponentName(this, LinkCheckActivity.class)});
        try {
            startActivity(chooser);
            finish();
        } catch (android.content.ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_browser, Toast.LENGTH_LONG).show();
        }
    }
}
