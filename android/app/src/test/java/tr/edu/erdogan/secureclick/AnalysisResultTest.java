package tr.edu.erdogan.secureclick;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import org.json.JSONObject;
import org.junit.Test;

public class AnalysisResultTest {

    @Test
    public void parsesApiResponse() throws Exception {
        String body = "{\"verdict\":\"malicious\",\"score\":0.97,\"elapsed_ms\":18.4,"
                + "\"links\":[{\"url\":\"http://x.xyz\",\"verdict\":\"malicious\",\"score\":0.97,"
                + "\"model_scores\":{\"random_forest\":0.95,\"svm\":0.99,\"ensemble\":0.97},"
                + "\"signals\":[{\"level\":\"high\",\"message\":\"m\"}]}],"
                + "\"text\":{\"score\":null,\"signals\":[]}}";
        AnalysisResult r = AnalysisResult.fromJson(new JSONObject(body));
        assertEquals(AnalysisResult.Verdict.MALICIOUS, r.verdict);
        assertEquals(1, r.links.size());
        assertEquals(0.99, r.links.get(0).svm, 1e-9);
        assertEquals("high", r.links.get(0).signals.get(0).level);
        assertEquals(null, r.textScore);
        assertFalse(r.offline);
    }
}
