package tr.edu.erdogan.secureclick;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;

public class UrlExtractorTest {

    @Test
    public void extractsSchemedAndBareLinks() {
        List<String> urls = UrlExtractor.extract(
                "Kargonuz bekliyor: ptt-takip.xyz/odeme ve https://bit.ly/3xK9pQ2 adresine girin. ali@ornek.com");
        assertTrue(urls.contains("ptt-takip.xyz/odeme"));
        assertTrue(urls.contains("https://bit.ly/3xK9pQ2"));
        assertEquals(2, urls.size());
    }

    @Test
    public void stripsTrailingPunctuation() {
        assertEquals("https://ornek.com/a", UrlExtractor.extract("Bak: https://ornek.com/a.").get(0));
    }

    @Test
    public void noLinks() {
        assertTrue(UrlExtractor.extract("Akşam yemeğe geliyor musun?").isEmpty());
    }
}
