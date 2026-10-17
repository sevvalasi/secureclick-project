package tr.edu.erdogan.secureclick;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.materialswitch.MaterialSwitch;
import com.google.android.material.textfield.TextInputEditText;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SettingsActivity extends AppCompatActivity {

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private Prefs prefs;
    private TextInputEditText server;
    private MaterialSwitch sms;

    private final ActivityResultLauncher<String[]> smsPermission = registerForActivityResult(
            new ActivityResultContracts.RequestMultiplePermissions(), this::onPermissionResult);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);
        prefs = new Prefs(this);
        MaterialToolbar tb = findViewById(R.id.toolbar);
        tb.setNavigationOnClickListener(v -> finish());

        server = findViewById(R.id.server);
        server.setText(prefs.server());

        MaterialSwitch live = findViewById(R.id.live);
        live.setChecked(prefs.liveChecks());
        live.setOnCheckedChangeListener((b, on) -> prefs.setLiveChecks(on));

        sms = findViewById(R.id.sms);
        sms.setChecked(prefs.smsGuard() && hasSmsPermission());
        sms.setOnCheckedChangeListener((b, on) -> {
            if (!on) {
                prefs.setSmsGuard(false);
            } else if (hasSmsPermission()) {
                prefs.setSmsGuard(true);
            } else {
                List<String> perms = new ArrayList<>();
                perms.add(Manifest.permission.RECEIVE_SMS);
                if (Build.VERSION.SDK_INT >= 33) perms.add(Manifest.permission.POST_NOTIFICATIONS);
                smsPermission.launch(perms.toArray(new String[0]));
            }
        });

        findViewById(R.id.test).setOnClickListener(v -> testConnection());
        findViewById(R.id.defaults).setOnClickListener(v -> {
            // Kullanıcı "Bağlantıları aç" / varsayılan tarayıcı ayarından SecureClick'i seçer
            Intent i = new Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS);
            try {
                startActivity(i);
            } catch (android.content.ActivityNotFoundException e) {
                startActivity(new Intent(Settings.ACTION_SETTINGS));
            }
        });
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (server.getText() != null) prefs.setServer(server.getText().toString());
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdownNow();
    }

    private boolean hasSmsPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.RECEIVE_SMS)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void onPermissionResult(Map<String, Boolean> granted) {
        boolean ok = Boolean.TRUE.equals(granted.get(Manifest.permission.RECEIVE_SMS));
        prefs.setSmsGuard(ok);
        sms.setChecked(ok);
        if (!ok) Toast.makeText(this, R.string.sms_permission_denied, Toast.LENGTH_LONG).show();
    }

    private void testConnection() {
        if (server.getText() != null) prefs.setServer(server.getText().toString());
        server.setText(prefs.server());
        TextView out = findViewById(R.id.testResult);
        out.setText(R.string.analyzing);
        String base = prefs.server();
        io.execute(() -> {
            String msg;
            int color;
            try {
                boolean ready = new ApiClient(base).health();
                msg = getString(ready ? R.string.connection_ok : R.string.connection_no_models);
                color = ready ? R.color.safe : R.color.warn;
            } catch (Exception e) {
                msg = getString(R.string.connection_fail,
                        e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
                color = R.color.danger;
            }
            String m = msg;
            int col = color;
            main.post(() -> {
                out.setText(m);
                out.setTextColor(ContextCompat.getColor(this, col));
            });
        });
    }
}
