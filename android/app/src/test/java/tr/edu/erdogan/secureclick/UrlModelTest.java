package tr.edu.erdogan.secureclick;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.BeforeClass;
import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

public class UrlModelTest {

    private static String json;
    private static UrlModel model;

    @BeforeClass
    public static void load() throws Exception {
        json = new String(Files.readAllBytes(Paths.get("src/main/assets/url_model.json")), StandardCharsets.UTF_8);
        model = UrlModel.fromJson(json);
    }

    @Test
    public void matchesPythonOnExportedVectors() throws Exception {
        JSONArray vectors = new JSONObject(json).getJSONArray("test_vectors");
        assertTrue(vectors.length() > 0);
        for (int i = 0; i < vectors.length(); i++) {
            JSONObject v = vectors.getJSONObject(i);
            assertEquals(v.getString("url"), v.getDouble("prob"), model.predict(v.getString("url")), 1e-4);
        }
    }

    @Test
    public void normalizeMatchesPython() {
        assertEquals("ornek.com/a", UrlModel.normalize("https://www.Ornek.com/a/"));
        assertEquals("ornek.com", UrlModel.normalize("http://ornek.com"));
        assertEquals("paypal.com", UrlModel.normalize("  'https://WWW.PayPal.com/'  "));
    }

    @Test
    public void murmurMatchesReferenceValues() {
        // sklearn.utils.murmurhash3_32 referans değerleri
        assertEquals(-156908512, UrlModel.murmur3("foo".getBytes(StandardCharsets.UTF_8)));
        assertEquals(0, UrlModel.murmur3(new byte[0]));
    }

    @Test
    public void obviousPhishingScoresHigherThanPopularSite() {
        assertTrue(model.predict("http://paypal.com.account-verify.secure-login.ru/webscr")
                > model.predict("https://www.wikipedia.org/wiki/Istanbul"));
    }
}
