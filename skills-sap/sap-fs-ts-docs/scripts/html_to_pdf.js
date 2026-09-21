/**
 * HTML → PDF (Chromium tabanlı tarayıcı, page.pdf; A4, arka plan açık).
 *
 * Kullanım:
 *   node html_to_pdf.js <girdi.html> <cikti.pdf>
 *   node html_to_pdf.js --check        # playwright-core çözülebiliyor mu (tarayıcı açmaz)
 *
 * Ortam değişkenleri:
 *   PLAYWRIGHT_CORE_PATH  playwright-core klasörü (mevcut kuruluma yönlendirme)
 *   PDF_BROWSER_CHANNEL   chrome (varsayılan, sistem Chrome'u) | msedge | chromium (paketli; indirme gerektirir)
 *
 * Çıkış: 0 başarılı · 2 eksik bağımlılık / kullanım hatası · 1 üretim hatası.
 */
"use strict";
const path = require("path");
const fs = require("fs");
const os = require("os");

console.log("KAPSAM (SCOPE): html_to_pdf — HTML'i tarayıcıda açıp A4 PDF yazar; bakılanlar: sayfa yüklenmesi, PDF dosyasının " +
  "oluşması. Bakılmayanlar: görsellerin yüklenmesi, bağlantı hedefleri, içerik → verify_doc_html.py.");

const INSTALL = "playwright-core bulunamadı. Kurulum: proje klasöründe `npm install playwright-core` ya da " +
  "PLAYWRIGHT_CORE_PATH ile mevcut bir playwright-core klasörünü göster.";

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

async function main(argv) {
  if (argv[0] === "--check") {
    const p = resolvePlaywrightCore();
    if (!p) { console.error("HATA: " + INSTALL); return 2; }
    console.log("playwright-core: " + p);
    return 0;
  }
  if (argv.length < 2) {
    console.error("kullanım: node html_to_pdf.js <girdi.html> <cikti.pdf>");
    return 2;
  }
  const IN = path.resolve(argv[0]);
  const OUT = path.resolve(argv[1]);
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
  try {
    const page = await (await browser.newContext()).newPage();
    await page.goto(fileUrl, { waitUntil: "networkidle", timeout: 60000 });
    await page.emulateMedia({ media: "screen" });
    await page.pdf({ path: OUT, format: "A4", printBackground: true,
      margin: { top: "14mm", bottom: "16mm", left: "12mm", right: "12mm" } });
    console.log("PDF OK: " + OUT + " (" + fs.statSync(OUT).size + " bayt)");
    return 0;
  } finally {
    await browser.close();
  }
}

main(process.argv.slice(2)).then(code => process.exit(code)).catch(e => { console.error("HATA:", e); process.exit(1); });
