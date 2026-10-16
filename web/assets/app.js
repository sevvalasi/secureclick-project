"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(d) + "%");
const num = (x) => (x == null ? "—" : Number(x).toLocaleString("tr-TR"));

/* ------------------------------------------------------------------ tema */
(() => {
  const root = document.documentElement;
  try { const t = localStorage.getItem("sc-theme"); if (t) root.dataset.theme = t; } catch {}
  $("#themeToggle").addEventListener("click", () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("sc-theme", root.dataset.theme); } catch {}
  });
})();

/* ------------------------------------------------------------------ sayfalar */
function route() {
  const page = (location.hash || "#analiz").slice(1);
  const known = ["analiz", "performans", "hakkinda", "api"];
  const p = known.includes(page) ? page : "analiz";
  $$(".page").forEach((s) => (s.hidden = s.id !== "page-" + p));
  $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === p));
  if (p === "performans") loadMetrics();
  window.scrollTo(0, 0);
}
addEventListener("hashchange", route);

/* ------------------------------------------------------------------ analiz */
const EXAMPLES = [
  "PTT Kargo: Gönderiniz adres bilgisi eksik olduğu için teslim edilemedi. 24 saat içinde güncellemezseniz iade edilecektir: http://ptt-kargotakip-tr.xyz/adres/guncelle",
  "HGS: Ödenmemiş 127,50 TL geçiş ihlaliniz bulunmaktadır. Cezanın 10 katına çıkmaması için hemen ödeyin: https://hgs-odeme-sorgula.online/odeme",
  "Garanti BBVA: 350 TL tutarındaki ödemeniz alınmıştır. Hesap hareketleriniz için https://www.garantibbva.com.tr/kampanyalar",
  "Selam, geçen haftaki fotoğrafları yükledim, buradan bakabilirsin: https://bit.ly/3xK9pQ2",
];
let mode = "message";
$$(".tab").forEach((t) => t.addEventListener("click", () => {
  mode = t.dataset.mode;
  $$(".tab").forEach((x) => { x.classList.toggle("active", x === t); x.setAttribute("aria-selected", x === t); });
  $(".mode-message").hidden = mode !== "message";
  $(".mode-url").hidden = mode !== "url";
  (mode === "message" ? $("#message") : $("#url")).focus();
}));
$$("[data-example]").forEach((b) => b.addEventListener("click", () => {
  $("#message").value = EXAMPLES[+b.dataset.example];
  $("#analyzeForm").requestSubmit();
}));

const VERDICT = {
  safe: { cls: "v-safe", icon: "✅", title: "Güvenli görünüyor", text: "Belirgin bir tehdit işareti bulunamadı. Yine de göndereni tanımıyorsanız dikkatli olun." },
  suspicious: { cls: "v-suspicious", icon: "⚠️", title: "Şüpheli", text: "Bazı risk işaretleri var. Bağlantıya tıklamadan önce göndereni başka bir kanaldan doğrulayın." },
  malicious: { cls: "v-malicious", icon: "⛔", title: "Zararlı olabilir — tıklamayın", text: "Bu bağlantı kimlik avı veya zararlı yazılım bağlantısı özellikleri taşıyor." },
};
const BADGE = { safe: ["b-safe", "Güvenli"], suspicious: ["b-suspicious", "Şüpheli"], malicious: ["b-malicious", "Zararlı"] };

function bar(label, v) {
  return `<div class="bar-row"><span class="lbl">${esc(label)}</span><div class="bar"><i style="width:${(v * 100).toFixed(1)}%"></i></div><span class="val">${pct(v, 0)}</span></div>`;
}
function signalList(sigs) {
  if (!sigs?.length) return `<p class="muted">Belirgin bir risk işareti yok.</p>`;
  return `<ul class="signals">${sigs.map((s) => `<li class="sig-${esc(s.level)}">${esc(s.message)}</li>`).join("")}</ul>`;
}
function liveBlock(live) {
  if (!live) return "";
  const r = live.redirects || {}, s = live.ssl || {}, w = live.whois || {};
  const chain = (r.chain || []).map((h) => `<li>${esc(h.status)} — ${esc(h.url)}</li>`).join("");
  return `<div class="subhead">Canlı kontroller</div>
  <dl class="kv">
    <dt>Son adres</dt><dd>${esc(r.final_url || "—")}${r.error ? ` <span class="error">(${esc(r.error)})</span>` : ""}</dd>
    <dt>Yönlendirme</dt><dd>${r.hops ?? "—"}</dd>
    <dt>SSL</dt><dd>${s.valid ? `Geçerli · ${esc(s.issuer || "")} · ${s.days_left} gün kaldı` : esc(s.error || "—")}</dd>
    <dt>Alan adı yaşı</dt><dd>${w.age_days != null ? `${num(w.age_days)} gün (${esc(w.created)})` : esc(w.error || "—")}</dd>
  </dl>${chain ? `<ol class="chain">${chain}</ol>` : ""}`;
}

function renderResult(data) {
  const v = VERDICT[data.verdict];
  let html = `<div class="verdict ${v.cls}"><span class="v-icon" aria-hidden="true">${v.icon}</span>
    <div><h2>${v.title}</h2><p>${v.text}</p></div>
    <div class="score"><b>${pct(data.score, 0)}</b><span>risk skoru</span></div></div>`;

  for (const l of data.links) {
    const [bc, bt] = BADGE[l.verdict];
    const ms = l.model_scores;
    html += `<article class="card link-card">
      <div class="link-head"><span class="link-url">${esc(l.url)}</span><span class="badge ${bc}">${bt}</span></div>
      <div class="bars">
        ${bar("Random Forest", ms.random_forest)}
        ${bar("SVM (n-gram)", ms.svm)}
        ${bar("URL topluluğu", ms.ensemble)}
        ${data.text?.score != null ? bar("Mesaj metni (NLP)", data.text.score) : ""}
        ${bar("Nihai skor", l.score)}
      </div>
      <div class="subhead">Bağlantı işaretleri</div>${signalList(l.signals)}
      ${liveBlock(l.live)}
    </article>`;
  }
  if (data.text) {
    html += `<article class="card link-card"><div class="link-head"><b>Mesaj içeriği analizi</b>
      ${data.text.score != null ? `<span class="muted">${pct(data.text.score, 0)} dolandırıcılık olasılığı</span>` : ""}</div>
      ${signalList(data.text.signals)}
      ${!data.links.length ? `<p class="muted">Mesajda bağlantı bulunamadı; değerlendirme yalnızca metne dayanıyor.</p>` : ""}
    </article>`;
  }
  html += `<p class="hint">Analiz süresi: ${data.elapsed_ms} ms</p>`;
  $("#result").innerHTML = html;
}

$("#analyzeForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { message: mode === "message" ? $("#message").value : "", url: mode === "url" ? $("#url").value : "", live_checks: $("#live").checked };
  if (!body.message.trim() && !body.url.trim()) { $("#result").innerHTML = `<div class="card error">Lütfen bir mesaj veya bağlantı girin.</div>`; return; }
  const btn = $("#submitBtn");
  btn.disabled = true; btn.classList.add("loading");
  try {
    const r = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json();
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : (data.detail?.[0]?.msg || "Sunucu hatası"));
    renderResult(data);
    if (innerWidth < 880) $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    $("#result").innerHTML = `<div class="card error">Analiz yapılamadı: ${esc(err.message)}</div>`;
  } finally {
    btn.disabled = false; btn.classList.remove("loading");
  }
});

/* ------------------------------------------------------------------ performans */
const COLORS = ["#2557d6", "#d6452b", "#13804b", "#a75d00", "#7b3fc4", "#0e8a9a"];
let metricsLoaded = false;

function lineChart(series, { xLabel, yLabel, diagonal = false }) {
  const W = 360, H = 260, P = { l: 40, r: 10, t: 10, b: 34 };
  const x = (v) => P.l + v * (W - P.l - P.r), y = (v) => H - P.b - v * (H - P.t - P.b);
  let g = "";
  for (let i = 0; i <= 4; i++) {
    const v = i / 4;
    g += `<line class="grid" x1="${x(0)}" x2="${x(1)}" y1="${y(v)}" y2="${y(v)}"/><text x="${P.l - 6}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(2)}</text>`;
    g += `<text x="${x(v)}" y="${H - P.b + 15}" text-anchor="middle">${v.toFixed(2)}</text>`;
  }
  if (diagonal) g += `<line class="axis" stroke-dasharray="4 4" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}"/>`;
  const paths = series.map((s, i) => `<polyline fill="none" stroke="${COLORS[i % COLORS.length]}" stroke-width="2" points="${s.points.map(([a, b]) => `${x(a).toFixed(1)},${y(b).toFixed(1)}`).join(" ")}"/>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)} / ${esc(xLabel)}">${g}
    <line class="axis" x1="${x(0)}" x2="${x(1)}" y1="${y(0)}" y2="${y(0)}"/><line class="axis" x1="${x(0)}" x2="${x(0)}" y1="${y(0)}" y2="${y(1)}"/>
    ${paths}<text x="${(x(0) + x(1)) / 2}" y="${H - 4}" text-anchor="middle">${esc(xLabel)}</text>
    <text transform="translate(11 ${(y(0) + y(1)) / 2}) rotate(-90)" text-anchor="middle">${esc(yLabel)}</text></svg>
    <div class="legend">${series.map((s, i) => `<span><i style="background:${COLORS[i % COLORS.length]}"></i>${esc(s.label)}</span>`).join("")}</div>`;
}

const TARGETS = { accuracy: 0.9, precision: 0.88, recall: 0.92, f1: 0.9, roc_auc: 0.95 };
const mark = (k, v) => (v == null ? "—" : `<span class="${v >= TARGETS[k] ? "ok" : "miss"}">${k === "roc_auc" ? v.toFixed(3) : pct(v)}</span>`);

function cm(c) {
  return `<div class="cm">
    <div class="h"></div><div class="h">Tahmin: güvenli</div><div class="h">Tahmin: zararlı</div>
    <div class="h">Gerçek: güvenli</div><div class="c-ok">${num(c.tn)}<br><small>TN</small></div><div class="c-err">${num(c.fp)}<br><small>FP</small></div>
    <div class="h">Gerçek: zararlı</div><div class="c-err">${num(c.fn)}<br><small>FN</small></div><div class="c-ok">${num(c.tp)}<br><small>TP</small></div></div>`;
}

const pfmt = (p) => (p == null ? "p = —" : p < 0.001 ? "p < 0,001" : "p = " + p.toFixed(3).replace(".", ","));

function ruleName(r) {
  if (!r) return "—";
  if (r.mode === "max") return "en yüksek skor (max)";
  if (r.mode === "noisy_or") return "noisy-OR: 1 − (1 − u)(1 − t)";
  return `ağırlıklı ortalama, α = ${r.alpha}`;
}

function renderMetrics(m) {
  const U = m.url_metrics, T = m.text_metrics, F = m.fusion_metrics;
  if (!U) { $("#perf").innerHTML = `<div class="card">Henüz rapor yok. Modelleri eğitmek için README'deki adımları izleyin.</div>`; return; }
  const L = U.labels, order = ["random_forest", "gradient_boosting", "svm", "tfidf_lr", "ensemble"];
  const d = U.dataset;
  let h = `<div class="stats">
    <div class="stat"><b>${num(d.n_total)}</b><span>toplam URL</span></div>
    <div class="stat"><b>${num(d.per_class.malicious)}</b><span>zararlı (PhishTank, URLHaus, OpenPhish)</span></div>
    <div class="stat"><b>${num(d.per_class.benign)}</b><span>güvenli (Tranco site haritaları)</span></div>
    <div class="stat"><b>${num(d.n_groups)}</b><span>farklı site (grup)</span></div>
    <div class="stat"><b>${pct(U.models.ensemble.test.f1)}</b><span>topluluk F1 (test)</span></div></div>`;

  h += `<div class="card"><h2>URL modelleri — test kümesi</h2><div class="tbl-wrap"><table class="tbl"><thead><tr>
    <th>Model</th><th class="num">Accuracy</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th><th class="num">ROC-AUC</th><th class="num">5-kat CV F1</th><th class="num">ms/URL</th></tr></thead><tbody>
    <tr class="muted"><td>Hedef (öneri formu)</td><td class="num">≥ 90%</td><td class="num">≥ 88%</td><td class="num">≥ 92%</td><td class="num">≥ 90%</td><td class="num">≥ 0.95</td><td></td><td></td></tr>`;
  for (const k of order) {
    const r = U.models[k], t = r.test;
    h += `<tr class="${k === "ensemble" ? "hl" : ""}"><td>${esc(L[k])}</td><td class="num">${mark("accuracy", t.accuracy)}</td><td class="num">${mark("precision", t.precision)}</td>
      <td class="num">${mark("recall", t.recall)}</td><td class="num">${mark("f1", t.f1)}</td><td class="num">${mark("roc_auc", t.roc_auc)}</td>
      <td class="num">${r.cv5 ? `${pct(r.cv5.f1.mean)} ± ${(r.cv5.f1.std * 100).toFixed(1)}` : "—"}</td><td class="num">${r.latency_ms_per_url ?? "—"}</td></tr>`;
  }
  h += `</tbody></table></div><p class="hint">Yeşil: hedef tutturuldu; turuncu: hedefin altında. Eşikler doğrulama kümesinde, recall ≥ %92 koşuluyla F1'i en yüksek yapacak şekilde seçildi.</p></div>`;

  const series = order.map((k) => ({ label: L[k], c: U.models[k].curves })).filter((s) => s.c);
  h += `<div class="charts">
    <div class="card chart"><h3>ROC eğrisi</h3>${lineChart(series.map((s) => ({ label: s.label, points: s.c.roc })), { xLabel: "Yanlış pozitif oranı", yLabel: "Doğru pozitif oranı", diagonal: true })}</div>
    <div class="card chart"><h3>Precision-Recall eğrisi</h3>${lineChart(series.map((s) => ({ label: s.label, points: s.c.pr })), { xLabel: "Recall", yLabel: "Precision" })}</div>
    <div class="card"><h3>Karışıklık matrisi — SecureClick topluluğu</h3>${cm(U.models.ensemble.test.confusion)}
      <p class="hint">Yanlış alarm oranı (FPR): ${pct(U.models.ensemble.test.fpr, 2)}</p></div></div>`;

  // Zamansal deney
  const tp = U.temporal;
  if (tp) {
    const bl = tp.models.blacklist, en = tp.models.ensemble;
    h += `<div class="card"><h2>Erken tespit: yeni saldırılar</h2>
      <p class="muted">Zararlı URL'ler bildirim zamanına göre sıralandı. Modeller ve kara liste yalnızca ${esc(tp.cutoff.slice(0, 16).replace("T", " "))} öncesindeki
      saldırıları gördü; test kümesi bu tarihten <b>sonra</b> ortaya çıkan ${num(tp.n_test)} URL'den oluşuyor.</p>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Yöntem</th><th class="num">Recall (yeni saldırılar)</th><th class="num">Precision</th><th class="num">F1</th></tr></thead><tbody>
      ${Object.entries(tp.models).map(([k, r]) => `<tr class="${k === "ensemble" ? "hl" : ""}"><td>${esc(L[k])}</td><td class="num">${pct(r.recall)}</td><td class="num">${pct(r.precision)}</td><td class="num">${pct(r.f1)}</td></tr>`).join("")}
      </tbody></table></div>
      <div class="callout"><p>Kara listenin kaçırdığı <b>${num(tp.missed_by_blacklist)}</b> yeni zararlı bağlantının <b>${num(tp.of_those_caught_by_ensemble)}</b> tanesini
      (${pct(tp.of_those_caught_by_ensemble / Math.max(tp.missed_by_blacklist, 1))}) SecureClick yakaladı.
      McNemar testi: ${pfmt(tp.mcnemar_ensemble_vs_blacklist.p_value)}.</p></div></div>`;
  }

  // Hipotez
  if (F) {
    const R = F.results, names = { blacklist: "Kara liste", url_only: "Yalnızca URL", text_only: "Yalnızca mesaj metni", fusion: "URL + metin (SecureClick)" };
    const kinds = { consistent: "Tutarlı çiftler", phish_text_benign_url: "Dolandırıcı mesaj + listede olmayan alan adı", benign_text_mal_url: "Masum mesaj + zararlı URL" };
    h += `<div class="card"><h2>Hipotez testi: URL + metin birlikte</h2>
      <p class="muted">Eğitimde hiç kullanılmamış Türkçe senaryo şablonları, test kümesindeki gerçek URL'lerle birleştirildi (${num(F.n_test)} mesaj; füzyon kuralı: ${esc(ruleName(F.fusion_rule))}).</p>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Yöntem</th><th class="num">Accuracy</th><th class="num">Precision</th><th class="num">Recall</th><th class="num">F1</th></tr></thead><tbody>
      ${Object.entries(R).map(([k, r]) => `<tr class="${k === "fusion" ? "hl" : ""}"><td>${names[k]}</td><td class="num">${pct(r.accuracy)}</td><td class="num">${pct(r.precision)}</td><td class="num">${pct(r.recall)}</td><td class="num">${pct(r.f1)}</td></tr>`).join("")}
      </tbody></table></div>
      <h3>Senaryo türüne göre doğruluk</h3><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Senaryo</th><th class="num">n</th><th class="num">Yalnızca URL</th><th class="num">Yalnızca metin</th><th class="num">URL + metin</th></tr></thead><tbody>
      ${Object.entries(F.accuracy_by_kind).map(([k, r]) => `<tr><td>${kinds[k] || esc(k)}</td><td class="num">${r.n}</td><td class="num">${pct(r.url_only)}</td><td class="num">${pct(r.text_only)}</td><td class="num">${pct(r.fusion)}</td></tr>`).join("")}
      </tbody></table></div>
      <div class="callout"><p>McNemar (URL + metin vs. yalnızca URL): b = ${F.mcnemar_fusion_vs_url_only.b}, c = ${F.mcnemar_fusion_vs_url_only.c}, ${pfmt(F.mcnemar_fusion_vs_url_only.p_value)}.
      ${F.mcnemar_fusion_vs_url_only.p_value < 0.05 && R.fusion.f1 > R.url_only.f1 ? "Fark istatistiksel olarak anlamlı; hipotez bu veri setinde desteklendi." : "Fark bu örneklemde istatistiksel olarak anlamlı değil."}</p>
      <p class="hint">Not: Senaryo mesajları sentetiktir; sonuçlar gerçek kullanıcı mesajlarıyla yapılacak pilot testle doğrulanmalıdır.</p></div></div>`;
  }

  // Özellik önemi
  if (U.feature_importance) {
    const top = U.feature_importance.slice(0, 12), max = top[0][1];
    h += `<div class="card"><h2>En etkili URL özellikleri (Random Forest)</h2><div class="fi">${top.map(([k, v]) =>
      `<div class="bar-row"><span class="lbl"><code>${esc(k)}</code></span><div class="bar"><i style="width:${(v / max * 100).toFixed(1)}%"></i></div><span class="val">${(v * 100).toFixed(1)}</span></div>`).join("")}</div></div>`;
  }

  if (U.recall_by_source) {
    h += `<div class="card"><h2>Kaynağa göre sonuçlar (topluluk)</h2><div class="tbl-wrap"><table class="tbl"><thead><tr><th>Kaynak</th><th class="num">Oran</th><th>Anlamı</th></tr></thead><tbody>
      ${Object.entries(U.recall_by_source).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${pct(v)}</td><td class="muted">yakalanan zararlı (recall)</td></tr>`).join("")}
      ${Object.entries(U.fpr_by_source || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${pct(v)}</td><td class="muted">yanlış alarm (FPR)</td></tr>`).join("")}
      </tbody></table></div></div>`;
  }

  if (T) {
    h += `<div class="card"><h2>Türkçe mesaj (NLP) modelleri</h2>
      <p class="muted">TurkishSMSCollection test kümesi (${num(T.dataset.sms)} SMS'in %20'si) ve eğitimde görülmemiş senaryo şablonları.</p>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Model</th><th class="num">SMS F1</th><th class="num">SMS ROC-AUC</th><th class="num">Görülmemiş senaryo F1</th><th class="num">5-kat CV F1</th></tr></thead><tbody>
      ${Object.entries(T.models).map(([k, r]) => `<tr class="${k === T.selected ? "hl" : ""}"><td>${esc(T.labels[k])}</td><td class="num">${pct(r.test_sms.f1)}</td><td class="num">${r.test_sms.roc_auc?.toFixed(3)}</td>
        <td class="num">${pct(r.test_scenarios_unseen_templates.f1)}</td><td class="num">${pct(r.cv5.f1.mean)} ± ${(r.cv5.f1.std * 100).toFixed(1)}</td></tr>`).join("")}
      </tbody></table></div></div>`;
  }
  h += `<p class="hint">Rapor tarihi: ${esc((U.generated_at || "").slice(0, 10))}. Ham JSON: <a href="/api/metrics">/api/metrics</a></p>`;
  $("#perf").innerHTML = h;
}

async function loadMetrics() {
  if (metricsLoaded) return;
  try {
    const r = await fetch("/api/metrics");
    renderMetrics(await r.json());
    metricsLoaded = true;
  } catch (e) {
    $("#perf").innerHTML = `<div class="card error">Raporlar yüklenemedi: ${esc(e.message)}</div>`;
  }
}

route();
