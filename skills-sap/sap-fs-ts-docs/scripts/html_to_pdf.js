/**
 * HTML → PDF (Chromium tabanlı tarayıcı, page.pdf; A4, arka plan açık).
 *
 * Kullanım:
 *   node html_to_pdf.js <girdi.html> <cikti.pdf> [--sayfa-no] [--yer-imi]
 *   node html_to_pdf.js --check        # playwright-core çözülebiliyor mu (tarayıcı açmaz)
 *
 * İSTEĞE BAĞLI BAYRAKLAR (Z201) — bayraksız çıktı ESKİSİYLE AYNIDIR (aynı page.pdf seçenekleri):
 *   --sayfa-no  her sayfanın alt boşluğuna "Sayfa X / Y" (yalnız METİN; footerTemplate).
 *   --yer-imi   başlık hiyerarşisinden (h1..h6) PDF yer imleri (Playwright `outline`).
 *
 * ⛔ ALTBİLGİ GÖVDEYİ DARALTMAZ: margin değiştirilmez ⇒ sayfa sayısı ve tablo bölünmesi bayraklı/bayraksız AYNI
 *    kalır. Altbilgi kutusunu Chromium margin'e göre DEĞİL, sayfanın ALT KENARINA göre yerleştirir: kutunun alt
 *    kenarı alt kenardan sabit ALTBILGI_ALT_IC_MM içeride, üst kenarı ondan şablon yüksekliği kadar yukarıda
 *    (ölçüm aşağıda, sabitin yanında). Alt boşluk (margin-bottom) bu kutuyu + payı kapsamıyorsa altbilgi gövdenin
 *    ÜSTÜNE basılır (ölçüldü: `@page` 6 mm + sayfa dibine dayanan satır → üst üste) — o yüzden ETKİN alt boşluk
 *    belgeden ÖLÇÜLÜR (sabit varsayılmaz) ve ALTBILGI_ALT_IC_MM + altbilgi yüksekliği + pay ile kıyaslanır; yetmiyorsa
 *    ya da ölçülemiyorsa SESSİZ değil DURDU (çıkış 2; hedefteki eski PDF'e dokunulmaz, uyarı basılır). Tuzaklar:
 *    · CSS `@page { margin: … }` page.pdf'e verilen JS margin'ini SESSİZCE ezer (build_doc_pdf CSS'i `@page`
 *      margin TAŞIR ⇒ etkin boşluk CSS'inkidir).
 *    · footerTemplate zemin boyamaz (yalnız metin/kenarlık) ⇒ altbilgi yalnız metin.
 *    · footerTemplate yazı boyutunu açıkça ister (varsayılan neredeyse görünmez).
 *
 * Ortam değişkenleri:
 *   PLAYWRIGHT_CORE_PATH  playwright-core klasörü (mevcut kuruluma yönlendirme)
 *   PDF_BROWSER_CHANNEL   chrome (varsayılan, sistem Chrome'u) | msedge | chromium (paketli; indirme gerektirir)
 *
 * Çıkış: 0 başarılı · 2 eksik bağımlılık / kullanım hatası / --sayfa-no DURDU · 1 üretim hatası.
 */
"use strict";
const path = require("path");
const fs = require("fs");
const os = require("os");

console.log("KAPSAM (SCOPE): html_to_pdf — HTML'i tarayıcıda açıp A4 PDF yazar; bakılanlar: sayfa yüklenmesi, PDF dosyasının " +
  "oluşması; --sayfa-no: etkin alt boşluk (@page/JS margin) ↔ altbilgi yüksekliği; --yer-imi: PDF'teki yer imi sayısı ↔ " +
  "başlık sayısı. Bakılmayanlar: görsellerin yüklenmesi, bağlantı hedefleri, içerik → verify_doc_html.py.");

const INSTALL = "playwright-core bulunamadı. Kurulum: proje klasöründe `npm install playwright-core` ya da " +
  "PLAYWRIGHT_CORE_PATH ile mevcut bir playwright-core klasörünü göster.";

const BILINEN_BAYRAK = new Set(["--sayfa-no", "--yer-imi"]);
const KULLANIM = "kullanım: node html_to_pdf.js <girdi.html> <cikti.pdf> [--sayfa-no] [--yer-imi]  |  node html_to_pdf.js --check";

// Altbilgi şablonu: Chromium `pageNumber`/`totalPages` sınıflarını doldurur. Yalnız metin; font boyutu AÇIK.
const ALTBILGI_HTML =
  '<div style="width:100%;font-family:\'Segoe UI\',Arial,sans-serif;font-size:8pt;color:#5a6b7b;' +
  'text-align:right;padding:0 12mm;box-sizing:border-box;">' +
  'Sayfa <span class="pageNumber"></span> / <span class="totalPages"></span></div>';
// Altbilgi ile gövde arasında en az bu kadar boşluk kalmalı (mm). Altbilginin KENDİ yüksekliği ölçülür; bu ek paydır.
const ALTBILGI_PAY_MM = 2;
// Chromium altbilgi kutusunun ALT kenarının sayfanın alt kenarına uzaklığı (mm). ÖLÇÜLDÜ (2026-10-19, playwright-core
// 1.64, `chrome` ve `msedge` kanalı, A4): şablona 1px üst/alt kenarlık konup PDF'teki çizgiler okundu (PyMuPDF
// get_drawings) — kutu alt kenarı 5.25 mm'de; `@page` margin-bottom 12 / 40 mm, JS margin 30 mm ve şablon yazı boyutu
// 8 / 16 pt'de DEĞİŞMEDİ; üst kenar = 5.25 + sayfa içinde ölçülen şablon yüksekliği (4.50 → 9.75 mm, 7.94 → 13.19 mm).
// 0.05 mm yukarı yuvarlandı. Tarayıcı sürümü bu yerleşimi değiştirirse onu yakalayan tek ölçüm
// SayfaNoYerImiTest.test_sayfa_no_altbilgi_govdeye_binmez'dir ve YALNIZ `SAP_FS_TS_DOCS_BROWSER_TESTS=1` + PyMuPDF
// kuruluyken koşar (CI'da koşmaz). O da yalnız gövdeye BİNMEYE dönüşen kaymayı görür: eşiğin 0.3 mm üstünde ölçer,
// ALTBILGI_PAY_MM (2 mm) içinde kalan kayma yakalanmaz.
const ALTBILGI_ALT_IC_MM = 5.3;
// JS margin'i (bayraksız yolla AYNI değerler; @page yoksa etkin boşluk budur).
const JS_MARGIN = { top: "14mm", bottom: "16mm", left: "12mm", right: "12mm" };
const JS_ALT_MM = 16;

// Viewport'a bağlı medya özellikleri (min-/max-/device-/aralık sözdizimi dahil — alt dizge eşleşir).
const VIEWPORT_OZELLIK_RE = /(?:width|height|aspect-ratio|orientation|resolution|pixel-ratio)/i;

function resolvePlaywrightCore() {
  const cands = [];
  if (process.env.PLAYWRIGHT_CORE_PATH) cands.push(process.env.PLAYWRIGHT_CORE_PATH);
  const npmRoots = [];
  if (process.env.APPDATA) npmRoots.push(path.join(process.env.APPDATA, "npm", "node_modules"));
  npmRoots.push(path.join(os.homedir(), "AppData", "Roaming", "npm", "node_modules"));
  if (process.env.npm_config_prefix) {
    npmRoots.push(path.join(process.env.npm_config_prefix, "node_modules"));
    npmRoots.push(path.join(process.env.npm_config_prefix, "lib", "node_modules"));
  }
  for (const r of npmRoots) {
    cands.push(path.join(r, "playwright-core"));
    cands.push(path.join(r, "@playwright", "cli", "node_modules", "playwright-core"));
    cands.push(path.join(r, "playwright", "node_modules", "playwright-core"));
  }
  for (const c of cands) {
    if (c && fs.existsSync(path.join(c, "package.json"))) return c;
  }
  for (const name of ["playwright-core", "playwright"]) {
    try { return path.dirname(require.resolve(name + "/package.json")); } catch (e) { /* sıradaki */ }
  }
  return null;
}

/** Belgenin ETKİN alt boşluğunu (mm) ve altbilginin yüksekliğini (mm) ölçer.
 *  Kaynak: belgedeki `@page` kuralı (varsa JS margin'ini ezer) — yoksa JS margin'i.
 *  · Bu betik `emulateMedia("screen")` ile basar ⇒ `@media print { @page {…} }` UYGULANMAZ, `@media screen|all`
 *    UYGULANIR. Medya TÜRÜ `matchMedia` ile, `@supports` `CSS.supports` ile süzülür; `@layer` gibi koşulsuz gruplara
 *    girilir. Sözde sayfa (`@page :first|:left|:right|<ad>`) yalnız bazı sayfalara uygulanır ⇒ altbilgi HER sayfaya
 *    sığmalı ⇒ tabanla birlikte EN KÜÇÜĞÜ alınır.
 *  · VIEWPORT'A BAĞLI MEDYA SORGUSU = MUHAFAZAKÂR: Chromium baskıda width/height/orientation… sorgularını sayfa
 *    kutusuna göre değerlendirir, `matchMedia` ise ekran viewport'una göre cevap verir (ölçüldü: yanlış cevap ⇒ sessiz
 *    kırpma). Böyle bir grubun içindeki HER `@page` en küçüğe katılır; margin'i yetmezse DURDU. Belirsizlik iç gruplara
 *    yayılır.
 *  · OKUNAMAYAN STİL SAYFASI / `@import` = DURDU: `file://` belgeden gelen dış sayfanın `cssRules`'ı `SecurityError`
 *    atar ⇒ içindeki `@page` görülemez. Okunamayan her kaynak sayılır, `--sayfa-no` DURDU verir. Var olmayan dosyaya
 *    bağlantı da aynı hatayı atar (ayırt edilemez; yüksek sesli yön). `data:` URL'li `@import` okunur.
 *  · `document.adoptedStyleSheets` aynı mantıkla gezilir (iz öneki `adopted>`; seçicisiz `@page`'i tabanı ezmez, en
 *    küçüğe katılır). Shadow root'lar TARANMAZ (kapsam satırında yazılır).
 *  SINIR (bilinçli, yüksek sesli yön = sahte DURDU, sessiz kırpma değil): viewport sorgusu baskıdaki sonucundan
 *  bağımsız en küçüğe katılır; stil sayfası kümesi (title / alternate) seçimi modellenmez; okunamayan sayfa margin'i
 *  yetse de DURDU verir; `@page` içi `@bottom-*` kutuları ve özgüllük/!important modellenmez (düz `@page`'lerde belge
 *  sırasındaki SON değer alınır). Çare: `@page`'i sorgudan çıkar, stili `<style>` içine göm ya da bayraksız üret. */
async function altBoslukOlc(page, jsAltMm) {
  return await page.evaluate(([jsAlt, html, reKaynak]) => {
    const viewportRe = new RegExp(reKaynak, "i");
    const pxToMm = px => px * 25.4 / 96;
    const uzunlukMm = deger => {
      const d = document.createElement("div");
      d.style.cssText = "position:absolute;visibility:hidden;height:" + deger;
      document.body.appendChild(d);
      const h = d.getBoundingClientRect().height;
      d.remove();
      return pxToMm(h);
    };
    let sorgu = 0, viewportSay = 0;
    const okunamayan = [];
    // evet | hayir | belirsiz  (belirsiz = viewport'a bağlı: baskıdaki sonucu buradan bilinemez)
    const medyaKarar = m => {
      if (!m || !m.mediaText) return "evet";
      sorgu++;
      if (viewportRe.test(m.mediaText)) { viewportSay++; return "belirsiz"; }
      return window.matchMedia(m.mediaText).matches ? "evet" : "hayir";
    };
    const etiket = (ad, k, metin) => ad + (k === "belirsiz" ? "~" : "") + "(" + metin + ")>";
    let tabanAlt = null, kaynak = "js-margin";
    const sozde = [];
    const gez = (kurallar, iz, belirsiz) => {
      for (const r of Array.from(kurallar || [])) {
        if (r.type === 6 /* PAGE_RULE */ && r.style) {
          const mb = r.style.getPropertyValue("margin-bottom");
          if (!mb) continue;
          const sec = (r.selectorText || "").trim();
          if (sec || belirsiz) { sozde.push({ mm: uzunlukMm(mb), iz: iz + "@page" + (sec ? " " + sec : "") }); }
          else { tabanAlt = uzunlukMm(mb); kaynak = "css-" + iz + "@page"; }
        } else if (r.type === 4 /* MEDIA_RULE */) {
          const k = medyaKarar(r.media);
          if (k !== "hayir") gez(r.cssRules, iz + etiket("@media", k, r.media.mediaText), belirsiz || k === "belirsiz");
        } else if (r.type === 12 /* SUPPORTS_RULE */) {
          let ok = false;
          try { ok = CSS.supports(r.conditionText); } catch (e) { ok = false; }
          if (ok) gez(r.cssRules, iz + "@supports>", belirsiz);
        } else if (r.type === 3 /* IMPORT_RULE */) {
          const k = medyaKarar(r.media);
          if (k !== "hayir" && r.styleSheet) {
            try { gez(r.styleSheet.cssRules, iz + (k === "evet" ? "@import>" : etiket("@import", k, r.media.mediaText)),
                      belirsiz || k === "belirsiz"); }
            catch (e) { okunamayan.push("@import " + (r.href || "?")); }
          }
        } else if (r.cssRules) {
          gez(r.cssRules, iz, belirsiz);   // @layer vb. koşulsuz grup
        }
      }
    };
    const adopted = Array.from(document.adoptedStyleSheets || []);
    const yuzey = Array.from(document.styleSheets).map(ss => ["", ss]).concat(adopted.map(ss => ["adopted>", ss]));
    for (const [onek, ss] of yuzey) {
      if (ss.disabled) continue;
      const k = medyaKarar(ss.media);   // <style media="print"> ekran emülasyonunda uygulanmaz
      if (k === "hayir") continue;
      let kurallar;
      try { kurallar = ss.cssRules; }
      catch (e) { okunamayan.push(ss.href || "<style>"); continue; }
      gez(kurallar, onek + (k === "evet" ? "" : etiket("<style media=", k, ss.media.mediaText)),
          k === "belirsiz" || onek === "adopted>");
    }
    let etkin = tabanAlt === null ? jsAlt : tabanAlt;
    for (const s of sozde) {
      if (s.mm < etkin) { etkin = s.mm; kaynak = "css-" + s.iz; }
    }
    const k = document.createElement("div");
    // Chromium şablonu belgenin CSS'ini GÖRMEYEN ayrı sayfada çizer (satır yüksekliği `normal`). Ölçüm de belgeden
    // yalıtılır: şablon shadow root içinde (belge seçicileri içeri işlemez) ve kabuk `:host{all:initial !important}`
    // ile sıfırlanır (önemli bildirimlerde gölge ağacının kuralı belgeninkini YENER ⇒ belgedeki `div{… !important}`
    // kabuğa da işleyemez, miras yolu kapanır). ÖLÇÜLDÜ: yalıtımsız ölçümde `body,div{line-height:.3 !important}`
    // yüksekliği 4.0 → 0.8 mm gösteriyordu (sahte geçiş).
    const golge = k.attachShadow({ mode: "open" });
    golge.innerHTML = "<style>:host{all:initial !important;display:block !important;position:absolute !important;" +
                      "visibility:hidden !important;left:0 !important;top:0 !important;width:180mm !important}</style>" + html;
    document.body.appendChild(k);
    const altbilgi = pxToMm(k.getBoundingClientRect().height);
    k.remove();
    return { etkinMm: etkin, kaynak, altbilgiMm: altbilgi, medya: { sorgu, viewport: viewportSay }, okunamayan,
             adopted: adopted.length };
  }, [jsAltMm, ALTBILGI_HTML, VIEWPORT_OZELLIK_RE.source]);
}

/** Üretilen PDF'teki yer imi sayısı — `Outlines` sözlüğünün `/Count`'u (ham bayttan).
 *  Döner: sayı · Outlines yok ve sıkıştırılmış nesne akışı da yok → 0 · ölçülemedi → null (`/ObjStm` varsa sözlük
 *  akışın içinde olabilir; ölçüldü: Chromium/Skia ObjStm yazmıyor, `/Type /Outlines … /Count N` düz metinde). */
function pdfYerImiSayisi(yol) {
  const ham = fs.readFileSync(yol).toString("latin1");
  const m = /<<((?:(?!<<|>>)[\s\S])*?\/Type\s*\/Outlines\b(?:(?!<<|>>)[\s\S])*?)>>/.exec(ham);
  if (m) {
    const c = /\/Count\s+(-?\d+)/.exec(m[1]);
    return c ? Math.abs(parseInt(c[1], 10)) : 0;
  }
  return /\/ObjStm\b/.test(ham) ? null : 0;
}

/** Yer imi BAŞLIK METNİ için hazırlık (yalnız --yer-imi).
 *  Ölçüldü: Chromium yer imi başlığını YERLEŞİM metninden üretir; birden çok satıra kayan başlıkta kayma noktasındaki
 *  boşluk düşer ("Şık Doküman" → "ŞıkDoküman"); `aria-label` bunu değiştirmez. `white-space:pre-wrap` satır sonu
 *  boşluğunu "asılı" tutar ⇒ boşluk metne girer, kırılma noktaları aynı kalır. pre-wrap baştaki boşluğu / kaynak içi
 *  satır sonunu görünür kılabileceği için her başlıkta boşluk-dışı karakterlerin konumu iki genişlikte önce/sonra
 *  ölçülür; değişen başlıkta geri alınır (o başlığın yer iminde boşluk düşebilir — sayısı basılır, gövde korunur). */
async function basliklariHazirla(page) {
  return await page.evaluate(() => {
    const kutular = el => {
      const s = [];
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      const r = document.createRange();
      for (let n = w.nextNode(); n; n = w.nextNode()) {
        for (let i = 0; i < n.data.length; i++) {
          if (/\s/.test(n.data[i])) continue;
          r.setStart(n, i); r.setEnd(n, i + 1);
          const x = r.getBoundingClientRect();
          s.push(Math.round(x.top) + "," + Math.round(x.left));
        }
      }
      return Math.round(el.getBoundingClientRect().height) + "|" + s.join(";");
    };
    const kok = document.documentElement;
    const eskiGenislik = kok.style.width;
    const olc = el => {
      const s = [];
      for (const g of ["", "120mm"]) { kok.style.width = g; s.push(kutular(el)); }
      kok.style.width = eskiGenislik;
      return s.join("|");
    };
    let toplam = 0, uygulanan = 0, geri = 0;
    for (const h of document.querySelectorAll("h1,h2,h3,h4,h5,h6")) {
      toplam++;
      const once = olc(h);
      const eski = h.style.whiteSpace;
      h.style.whiteSpace = "pre-wrap";
      if (olc(h) === once) { uygulanan++; } else { h.style.whiteSpace = eski; geri++; }
    }
    return { toplam, uygulanan, geri };
  });
}

async function main(argv) {
  if (argv[0] === "--check") {
    const p = resolvePlaywrightCore();
    if (!p) { console.error("HATA: " + INSTALL); return 2; }
    console.log("playwright-core: " + p);
    return 0;
  }
  // Bilinmeyen bayrak YOL sanılmaz (sessiz yanlış dosya yerine kullanım hatası).
  const bayrak = new Set(argv.filter(a => a.startsWith("--")));
  const konum = argv.filter(a => !a.startsWith("--"));
  for (const b of bayrak) {
    if (!BILINEN_BAYRAK.has(b)) {
      console.error("HATA: bilinmeyen bayrak: " + b + " (bilinen: " + [...BILINEN_BAYRAK].join(" ") + ")\n" + KULLANIM);
      return 2;
    }
  }
  if (konum.length !== 2) {
    console.error(KULLANIM);
    return 2;
  }
  const IN = path.resolve(konum[0]);
  const OUT = path.resolve(konum[1]);
  if (!fs.existsSync(IN)) { console.error("HATA: girdi yok: " + IN); return 2; }
  const pw = resolvePlaywrightCore();
  if (!pw) { console.error("HATA: " + INSTALL); return 2; }
  const { chromium } = require(pw);
  const channel = process.env.PDF_BROWSER_CHANNEL || "chrome";
  const fileUrl = "file:///" + IN.split(path.sep).join("/");
  let browser;
  try {
    browser = await chromium.launch({ channel: channel === "chromium" ? undefined : channel, headless: true, args: ["--no-sandbox"] });
  } catch (e) {
    console.error("HATA: tarayıcı başlatılamadı (kanal " + channel + "). Chrome kurulu olmalı ya da PDF_BROWSER_CHANNEL ile kurulu bir kanal (ör. msedge) seçilmeli.\n" + e.message);
    return 2;
  }
  let yerImi = null;
  try {
    const page = await (await browser.newContext()).newPage();
    await page.goto(fileUrl, { waitUntil: "networkidle", timeout: 60000 });
    await page.emulateMedia({ media: "screen" });
    // ⛔ Bayraksız seçenek nesnesi eskisiyle BİREBİR (bayraksız çıktı değişmez).
    const opts = { path: OUT, format: "A4", printBackground: true, margin: JS_MARGIN };
    if (bayrak.has("--sayfa-no")) {
      const o = await altBoslukOlc(page, JS_ALT_MM);
      // Altbilgi kutusunun üst kenarı alt kenardan ALTBILGI_ALT_IC_MM + şablon yüksekliği kadar yukarıdadır; gövde
      // alanı (margin-bottom) bunun + payın ALTINA inmemeli.
      const gerek = ALTBILGI_ALT_IC_MM + o.altbilgiMm + ALTBILGI_PAY_MM;
      const okn = o.okunamayan.length;
      // DURDU'da PDF yazılmaz; hedefte önceki koşumdan kalan PDF SİLİNMEZ ama sessiz de kalmaz (eski çıktı yeni sanılmasın).
      const oncekiPdf = () => {
        if (fs.existsSync(OUT)) console.error("UYARI: hedefte onceki PDF duruyor, bu kosumda yazilmadi: " + OUT);
      };
      // KAPSAM: "(muhafazakar)" yalnız viewport sorgusu VARKEN ve okunamayan kaynak YOKKEN basılır.
      console.log("ALTBILGI: etkin alt bosluk " + o.etkinMm.toFixed(1) + "mm (" + o.kaynak + "), gereken " +
                  gerek.toFixed(1) + "mm = alt ic bosluk " + ALTBILGI_ALT_IC_MM + "mm + altbilgi " + o.altbilgiMm.toFixed(1) +
                  "mm + pay " + ALTBILGI_PAY_MM + "mm | medya " + o.medya.sorgu + " sorgu, " +
                  o.medya.viewport + " viewport'a bagli" + (o.medya.viewport > 0 && okn === 0 ? " (muhafazakar)" : "") +
                  " | okunamayan stil sayfasi/import " + okn + " | adoptedStyleSheets " + o.adopted +
                  " | shadow root TARANMADI");
      if (okn > 0) {
        console.error("[DURDU] --sayfa-no: stil sayfasi okunamadi (" + okn + " kaynak: " + o.okunamayan.slice(0, 3).join(", ") +
                      (okn > 3 ? ", …" : "") + "), @page margin'i OLCULEMEDI (okunamayan sayfa baskida @page margin'ini " +
                      "degistirebilir, altbilgi govdenin ustune basilabilirdi). Stili <style> icine gom ya da bayraksiz uret.");
        oncekiPdf();
        return 2;
      }
      if (!(o.etkinMm >= gerek)) {
        const vp = o.kaynak.includes("~(") ? " Kaynak VIEWPORT'A BAGLI medya sorgusu (muhafazakar): baskida uygulanip " +
                   "uygulanmadigi ekran viewport'undan bilinemez, en kucuk deger alindi." : "";
        // İki ondalık: tek ondalıkta 11.26 < 11.30 "11.3mm < 11.3mm" diye çelişkili okunurdu.
        console.error("[DURDU] --sayfa-no: etkin alt bosluk " + o.etkinMm.toFixed(2) + "mm < gereken " + gerek.toFixed(2) +
                      "mm (" + o.kaynak + ")." + vp + " Altbilgi govdenin ustune basilirdi; govdeyi daraltmamak icin margin " +
                      "degistirilmez. Belgenin @page margin-bottom degerini buyut ya da bayraksiz uret.");
        oncekiPdf();
        return 2;
      }
      opts.displayHeaderFooter = true;
      opts.headerTemplate = "<span></span>";   // boş üst bilgi (varsayılan tarih/başlık basılmasın)
      opts.footerTemplate = ALTBILGI_HTML;
    }
    if (bayrak.has("--yer-imi")) {
      yerImi = await basliklariHazirla(page);
      console.log("YER-IMI: " + yerImi.toplam + " baslik; satir-kaydirma boslugu korundu: " + yerImi.uygulanan +
                  ", geri alindi (yerlesim degisirdi): " + yerImi.geri);
      opts.outline = true;   // başlıklardan PDF yer imi (etiketli PDF ister)
      opts.tagged = true;
    }
    await page.pdf(opts);
  } finally {
    await browser.close();
  }
  if (yerImi) {
    // Üretim SONRASI denetim: "outline: true" vermek yer imi üretildiğinin kanıtı değil — PDF'in kendisinden sayılır.
    // Uyarıdır, çıkış kodunu değiştirmez.
    const n = pdfYerImiSayisi(OUT);
    if (n === null) {
      console.error("UYARI --yer-imi: OLCULEMEDI — PDF sikistirilmis nesne akisi (ObjStm) tasiyor, yer imi sayisi okunamadi");
    } else {
      console.log("YER-IMI PDF: " + n + " yer imi / " + yerImi.toplam + " baslik");
      if (n === 0 && yerImi.toplam > 0) {
        console.error("UYARI --yer-imi: PDF'te YER IMI YOK (" + yerImi.toplam + " baslik vardi) — tarayici/Playwright " +
                      "surumu outline desteklemiyor olabilir");
      } else if (n !== yerImi.toplam) {
        console.error("UYARI --yer-imi: yer imi sayisi (" + n + ") baslik sayisindan (" + yerImi.toplam + ") farkli — " +
                      "bos/gizli baslik ya da kapali dal olabilir, PDF'i kontrol et");
      }
    }
  }
  console.log("PDF OK: " + OUT + " (" + fs.statSync(OUT).size + " bayt)");
  return 0;
}

main(process.argv.slice(2)).then(code => process.exit(code)).catch(e => { console.error("HATA:", e); process.exit(1); });
