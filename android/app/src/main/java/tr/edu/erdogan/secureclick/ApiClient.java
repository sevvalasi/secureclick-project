package tr.edu.erdogan.secureclick;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** SecureClick REST API istemcisi (ek kütüphane gerektirmez). */
public final class ApiClient {

    private static final int CONNECT_TIMEOUT_MS = 4000;
    private final String base;

    public ApiClient(String baseUrl) {
        this.base = baseUrl;
    }

    public AnalysisResult analyze(String message, String url, boolean liveChecks) throws IOException {
        JSONObject body = new JSONObject();
        try {
            body.put("message", message == null ? "" : message);
            body.put("url", url == null ? "" : url);
            body.put("live_checks", liveChecks);
        } catch (JSONException e) {
            throw new IOException(e);
        }
        // Canlı kontroller sunucuda ~3 sn sürebilir
        String resp = request("POST", "/api/analyze", body.toString(), liveChecks ? 15000 : 8000);
        try {
            return AnalysisResult.fromJson(new JSONObject(resp));
        } catch (JSONException e) {
            throw new IOException("Sunucu yanıtı çözümlenemedi", e);
        }
    }

    /** Sunucuya erişilebiliyor ve modeller yüklü mü? */
    public boolean health() throws IOException {
        try {
            return new JSONObject(request("GET", "/api/health", null, 4000)).optBoolean("models_ready");
        } catch (JSONException e) {
            throw new IOException(e);
        }
    }

    private String request(String method, String path, String json, int readTimeout) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        try {
            c.setRequestMethod(method);
            c.setConnectTimeout(CONNECT_TIMEOUT_MS);
            c.setReadTimeout(readTimeout);
            c.setRequestProperty("Accept", "application/json");
            if (json != null) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                try (OutputStream os = c.getOutputStream()) {
                    os.write(json.getBytes(StandardCharsets.UTF_8));
                }
            }
            int code = c.getResponseCode();
            InputStream is = code < 400 ? c.getInputStream() : c.getErrorStream();
            String text = is == null ? "" : readAll(is);
            if (code >= 400) {
                throw new ServerException(code, detail(text));
            }
            return text;
        } finally {
            c.disconnect();
        }
    }

    private static String detail(String body) {
        try {
            Object d = new JSONObject(body).opt("detail");
            if (d instanceof String) return (String) d;
        } catch (JSONException ignored) {
        }
        return body;
    }

    private static String readAll(InputStream is) throws IOException {
        try (InputStream in = is) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
            return bos.toString("UTF-8");
        }
    }

    /** Sunucuya ulaşıldı ama hata döndü (ör. 429 hız sınırı, 503 model yok). */
    public static final class ServerException extends IOException {
        public final int code;

        ServerException(int code, String message) {
            super(message);
            this.code = code;
        }
    }
}
