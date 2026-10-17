package tr.edu.erdogan.secureclick;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

/**
 * İsteğe bağlı SMS koruması: bağlantı içeren SMS geldiğinde analiz eder, şüpheli veya
 * zararlıysa anlık bildirim gösterir. Varsayılan olarak kapalıdır; kullanıcı Ayarlar'dan
 * açar ve RECEIVE_SMS iznini verir. Yalnızca bağlantı içeren mesajlar analiz edilir.
 */
public final class SmsReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) return;
        if (!new Prefs(context).smsGuard()) return;

        StringBuilder sb = new StringBuilder();
        for (SmsMessage m : Telephony.Sms.Intents.getMessagesFromIntent(intent)) {
            if (m != null && m.getMessageBody() != null) sb.append(m.getMessageBody());
        }
        String body = sb.toString();
        if (UrlExtractor.extract(body).isEmpty()) return;  // bağlantısız mesajlar hiç gönderilmez

        Context app = context.getApplicationContext();
        PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                AnalysisResult r = new Analyzer(app).analyze(body, "");
                new HistoryStore(app).add(body, r);
                if (r.verdict != AnalysisResult.Verdict.SAFE) {
                    Notifier.alert(app, body, r);
                }
            } finally {
                pending.finish();
            }
        }, "sms-check").start();
    }
}
