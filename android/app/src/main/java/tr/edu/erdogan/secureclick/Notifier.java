package tr.edu.erdogan.secureclick;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

/** Zararlı/şüpheli bağlantı içeren mesajlar için anlık uyarı bildirimi. */
public final class Notifier {

    private static final String CHANNEL = "alerts";

    private Notifier() {
    }

    static void ensureChannel(Context c) {
        NotificationChannel ch = new NotificationChannel(CHANNEL,
                c.getString(R.string.channel_alerts), NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription(c.getString(R.string.channel_alerts_desc));
        c.getSystemService(NotificationManager.class).createNotificationChannel(ch);
    }

    public static void alert(Context c, String message, AnalysisResult r) {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(c,
                Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        ensureChannel(c);
        boolean bad = r.verdict == AnalysisResult.Verdict.MALICIOUS;
        String title = c.getString(bad ? R.string.notif_malicious : R.string.notif_suspicious);
        String link = r.links.isEmpty() ? "" : r.links.get(0).url;

        Intent open = new Intent(c, MainActivity.class)
                .setAction(MainActivity.ACTION_SHOW)
                .putExtra(Intent.EXTRA_TEXT, message)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(c, message.hashCode(), open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        NotificationCompat.Builder b = new NotificationCompat.Builder(c, CHANNEL)
                .setSmallIcon(R.drawable.ic_shield)
                .setContentTitle(title)
                .setContentText(c.getString(R.string.notif_body, link))
                .setStyle(new NotificationCompat.BigTextStyle()
                        .bigText(c.getString(R.string.notif_body, link)))
                .setColor(ContextCompat.getColor(c, bad ? R.color.danger : R.color.warn))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                // Android bildirimdeki URL için otomatik "Bağlantıyı aç" düğmesi ekler; zararlı
                // bağlantı uyarısında bu tehlikelidir, kapatılır.
                .setAllowSystemGeneratedContextualActions(false)
                .setContentIntent(pi);
        try {
            NotificationManagerCompat.from(c).notify(message.hashCode(), b.build());
        } catch (SecurityException ignored) {
            // izin bu arada geri alınmış olabilir
        }
    }
}
