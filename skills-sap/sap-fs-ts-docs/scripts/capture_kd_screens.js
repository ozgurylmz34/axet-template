/**
 * KD ekran görüntüsü çekici — yapılandırma dosyasıyla adım adım (UI5 mock sunucu + temiz model verisi).
 *
 * Kullanım:
 *   node capture_kd_screens.js <config.json>            # çekimi yapar
 *   node capture_kd_screens.js <config.json> --dry-run  # yapılandırmayı doğrular, tarayıcı açmaz
 *
 * Yapılandırma:
 *   { "url": "...?sap-ui-language=tr", "out_dir": "docs/screenshots",
 *     "viewport": {"width":1680,"height":1050}, "device_scale_factor": 2, "locale": "tr-TR",
 *     "channel": "chrome", "expect_port": 8080,
 *     "steps": [ {"do":"goto","url":"..."}, {"do":"wait_ui5","ms":1500}, {"do":"wait","ms":800} | {"do":"wait","selector":"..."},
 *                {"do":"click","selector":"..."}, {"do":"eval","script":"..."},
 *                {"do":"set_model","view_pattern":"Create","model":"viewModel","data":{...} | "data_file":"x.json","merge":true},
 *                {"do":"assert_no_busy","timeout":10000},
 *                {"do":"assert_text","text":"Siparişler","selector":"..."},   // selector yoksa tüm sayfa
 *                {"do":"assert_in_viewport","selector":"...","partial":false},
 *                {"do":"shot","name":"kd-01.png","selector":"...","full_page":false,"optional":false} ] }
 * Göreli yollar (out_dir, data_file) yapılandırma dosyasının klasörüne göre çözülür.
 * Kanal: cfg.channel → PDF_BROWSER_CHANNEL → "chrome" (sistem Chrome'u; tarayıcı İNDİRİLMEZ). "chromium" = paketli.
 *
 * Doğrulama adımları (tutmazsa adım FAIL, zorunlu adımda koşu durur → çıkış 1):
 *   assert_no_busy     UI5 meşgul göstergesi açık değil. `timeout` (vars. 10000 ms) içinde kapanmazsa FAIL.
 *                      Bakılanlar (openui5 kaynağından): global BusyIndicator — modül yüklüyse `bOpenRequested`
 *                      (gecikmeli gösterim bekliyor) ya da `oPopup.isOpen()`, ek olarak görünür #sapUiBusyIndicator;
 *                      yerel — Element.registry'de `getBusy()` true ve DOM'u görünür kontrol + görünür
 *                      `.sapUiLocalBusyIndicator` blok katmanı; freestyle sap.m — açık sap.m.BusyDialog (iç Dialog
 *                      'sapMBusyDialog' sınıfı + isOpen(), ya da görünür .sapMBusyDialog) ve görünür
 *                      .sapMBusyIndicator kontrolü. `.sapUiLocalBusy` sınıfına BAKILMAZ: UI5 unblock
 *                      sırasında blok katmanını siler ama ebeveyndeki bu sınıfı silmez (BlockLayerUtils.unblock).
 *   assert_text        `text` görünür metinde (innerText) geçiyor; `selector` verilirse yalnız ilk eşleşen öğede.
 *                      `timeout` (vars. 5000 ms) içinde görünmezse FAIL.
 *   assert_in_viewport `selector`'ın ilk öğesi görünür ve görünüm alanının TAMAMEN içinde (`partial:true` →
 *                      kesişmesi yeter). `timeout` (vars. 5000 ms) içinde öğe yoksa FAIL.
 * Listede çekimler ve doğrulama adımları OK/FAIL satırı alır; ÖZET bu satırları sayar.
 *
 * Çıkış: 0 tüm zorunlu adımlar OK · 1 en az bir zorunlu adım FAIL · 2 yapılandırma hatası / eksik bağımlılık.
 */
"use strict";
const path = require("path");
const fs = require("fs");
const os = require("os");

console.log("KAPSAM (SCOPE): capture_kd_screens — yapılandırmadaki adımları koşar ve her çekimi OK/FAIL listeler. " +
  "Bakılmayanlar: görüntüdeki verinin temizliği (DOC-KD-01), alt ekran kapsamı (DOC-KD-03), görüntü içeriği → elle inceleme.");

const INSTALL = "playwright-core bulunamadı. Kurulum: proje klasöründe `npm install playwright-core` ya da " +
  "PLAYWRIGHT_CORE_PATH ile mevcut bir playwright-core klasörünü göster.";

const STEP_RULES = {
  goto: s => typeof s.url === "string" || "goto: url gerekli",
  wait_ui5: () => true,
  wait: s => (typeof s.ms === "number" || typeof s.selector === "string") || "wait: ms ya da selector gerekli",
  click: s => typeof s.selector === "string" || "click: selector gerekli",
  eval: s => typeof s.script === "string" || "eval: script gerekli",
  set_model: s => (typeof s.view_pattern === "string" && (s.data !== undefined || typeof s.data_file === "string"))
    || "set_model: view_pattern ve data ya da data_file gerekli",
  shot: s => (typeof s.name === "string" && /\.png$/i.test(s.name)) || "shot: .png uzantılı name gerekli",
  assert_no_busy: s => (s.timeout === undefined || (typeof s.timeout === "number" && s.timeout > 0))
    || "assert_no_busy: timeout pozitif sayı olmalı",
  assert_text: s => (typeof s.text === "string" && s.text.trim() !== ""
    && (s.selector === undefined || typeof s.selector === "string"))
    || "assert_text: boş olmayan text gerekli (selector isteğe bağlı, metin)",
  assert_in_viewport: s => (typeof s.selector === "string" && s.selector !== "")
    || "assert_in_viewport: selector gerekli",
};

const ASSERT_STEPS = new Set(["assert_no_busy", "assert_text", "assert_in_viewport"]);

// Tarayıcıda koşar: UI5 meşgul durumunun ayrıntısı. null → UI5 yok.
function busyProbe() {
  const core = window.sap && sap.ui && sap.ui.core;
  if (!core || !core.Element || !core.Element.registry) return null;
  const visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
  const out = { global: [], local: [] };
  const BI = (sap.ui.require && sap.ui.require("sap/ui/core/BusyIndicator")) || core.BusyIndicator;
  if (BI) {
    if (BI.bOpenRequested) out.global.push("BusyIndicator gösterim bekliyor");
    if (BI.oPopup && typeof BI.oPopup.isOpen === "function" && BI.oPopup.isOpen()) out.global.push("BusyIndicator açık");
  }
  if (visible(document.getElementById("sapUiBusyIndicator"))) out.global.push("#sapUiBusyIndicator görünür");
  core.Element.registry.filter(e => typeof e.getBusy === "function" && e.getBusy() &&
    typeof e.getDomRef === "function" && visible(e.getDomRef())).forEach(e => out.local.push(e.getId()));
  document.querySelectorAll(".sapUiLocalBusyIndicator").forEach(el => {
    if (visible(el)) out.local.push("blok katmanı " + (el.id || (el.parentElement && el.parentElement.id) || "(adsız)"));
  });
  // Freestyle sap.m: BusyDialog iç Dialog'u 'sapMBusyDialog' sınıfı taşır (sap/m/BusyDialog.js) → açık Dialog;
  // sap.m.BusyIndicator kontrolü '.sapMBusyIndicator' kökünü çizer (sap/m/BusyIndicatorRenderer.js) → görünürse dönüyor.
  core.Element.registry.filter(e => typeof e.isA === "function" && e.isA("sap.m.Dialog") &&
    typeof e.hasStyleClass === "function" && e.hasStyleClass("sapMBusyDialog") &&
    typeof e.isOpen === "function" && e.isOpen()).forEach(e => out.global.push("BusyDialog açık " + e.getId()));
  document.querySelectorAll(".sapMBusyDialog").forEach(el => {
    if (visible(el) && !out.global.some(g => g === "BusyDialog açık " + el.id)) {
      out.global.push("BusyDialog görünür " + (el.id || "(adsız)"));
    }
  });
  document.querySelectorAll(".sapMBusyIndicator").forEach(el => {
    if (visible(el) && !el.closest(".sapMBusyDialog")) out.local.push("sap.m.BusyIndicator " + (el.id || "(adsız)"));
  });
  return out;
}

function resolvePlaywrightCore() {
  const cands = [];
  if (process.env.PLAYWRIGHT_CORE_PATH) cands.push(process.env.PLAYWRIGHT_CORE_PATH);
  const roots = [];
  if (process.env.APPDATA) roots.push(path.join(process.env.APPDATA, "npm", "node_modules"));
  roots.push(path.join(os.homedir(), "AppData", "Roaming", "npm", "node_modules"));
  if (process.env.npm_config_prefix) {
    roots.push(path.join(process.env.npm_config_prefix, "node_modules"));
    roots.push(path.join(process.env.npm_config_prefix, "lib", "node_modules"));
  }
  for (const r of roots) {
    cands.push(path.join(r, "playwright-core"));
    cands.push(path.join(r, "@playwright", "cli", "node_modules", "playwright-core"));
    cands.push(path.join(r, "playwright", "node_modules", "playwright-core"));
  }
  for (const c of cands) if (c && fs.existsSync(path.join(c, "package.json"))) return c;
  for (const name of ["playwright-core", "playwright"]) {
    try { return path.dirname(require.resolve(name + "/package.json")); } catch (e) { /* sıradaki */ }
  }
  return null;
}

function loadConfig(cfgPath) {
  let cfg;
  try { cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8").replace(/^﻿/, "")); }
  catch (e) { return { errors: ["yapılandırma okunamadı: " + e.message] }; }
  const errors = [];
  if (typeof cfg.url !== "string") errors.push("url gerekli");
  if (!Array.isArray(cfg.steps) || cfg.steps.length === 0) errors.push("steps boş olamaz");
  const base = path.dirname(path.resolve(cfgPath));
  (cfg.steps || []).forEach((s, i) => {
    const rule = STEP_RULES[s && s.do];
    if (!rule) { errors.push("adım " + (i + 1) + ": bilinmeyen do=" + (s && s.do)); return; }
    const r = rule(s);
    if (r !== true) errors.push("adım " + (i + 1) + ": " + r);
    if (s.do === "set_model" && s.data_file && !fs.existsSync(path.resolve(base, s.data_file)))
      errors.push("adım " + (i + 1) + ": data_file yok: " + s.data_file);
  });
  const names = (cfg.steps || []).filter(s => s && s.do === "shot").map(s => s.name);
  const dup = names.filter((n, i) => names.indexOf(n) !== i);
  if (dup.length) errors.push("aynı çekim adı birden çok kez: " + [...new Set(dup)].join(", "));
  return { cfg, base, errors };
}

async function runStep(page, s, base, outDir, cfg) {
  switch (s.do) {
    case "goto":
      await page.goto(s.url, { waitUntil: "load", timeout: s.timeout || 60000 });
      return;
    case "wait_ui5":
      await page.waitForFunction(() => !!(window.sap && sap.ui && sap.ui.core && sap.ui.core.Element &&
        sap.ui.core.Element.registry), null, { timeout: s.timeout || 60000 });
      await page.waitForTimeout(s.ms || 1500);
      return;
    case "wait":
      if (s.selector) await page.waitForSelector(s.selector, { timeout: s.timeout || 30000 });
      else await page.waitForTimeout(s.ms);
      return;
    case "click":
      await page.locator(s.selector).first().click({ timeout: s.timeout || 30000 });
      return;
    case "eval":
      await page.evaluate(s.script);
      return;
    case "set_model": {
      const data = s.data !== undefined ? s.data : JSON.parse(fs.readFileSync(path.resolve(base, s.data_file), "utf8"));
      const n = await page.evaluate(({ pattern, model, data, merge }) => {
        const rx = new RegExp(pattern);
        const views = sap.ui.core.Element.registry.filter(e => e.isA && e.isA("sap.ui.core.mvc.View") &&
          rx.test(e.getViewName ? e.getViewName() : e.getId()));
        let hit = 0;
        views.forEach(v => { const m = v.getModel(model || undefined); if (m && m.setData) { m.setData(data, merge); hit++; } });
        return hit;
      }, { pattern: s.view_pattern, model: s.model || null, data, merge: s.merge !== false });
      if (!n) throw new Error("set_model: desen/model eşleşmedi (" + s.view_pattern + " / " + (s.model || "varsayılan") + ")");
      await page.waitForTimeout(s.ms || 500);
      return;
    }
    case "assert_no_busy": {
      const limit = s.timeout || 10000;
      const until = Date.now() + limit;
      let last;
      for (;;) {
        last = await page.evaluate(busyProbe);
        if (last === null) throw new Error("assert_no_busy: UI5 yüklü değil (sap.ui.core.Element.registry yok)");
        if (!last.global.length && !last.local.length) return;
        if (Date.now() >= until) break;
        await page.waitForTimeout(200);
      }
      const more = last.local.length > 5 ? " …(+" + (last.local.length - 5) + ")" : "";
      throw new Error("assert_no_busy: " + limit + " ms içinde meşgul gösterge kapanmadı — " +
        [...last.global, ...last.local.slice(0, 5)].join("; ") + more);
    }
    case "assert_text": {
      const limit = s.timeout || 5000;
      try {
        await page.waitForFunction(({ text, selector }) => {
          const el = selector ? document.querySelector(selector) : document.body;
          return !!el && (el.innerText || "").includes(text);
        }, { text: s.text, selector: s.selector || null }, { timeout: limit, polling: 200 });
      } catch (e) {
        throw new Error("assert_text: \"" + s.text + "\" " + (s.selector ? "'" + s.selector + "' içinde " : "sayfada ") +
          limit + " ms içinde görünmedi");
      }
      return;
    }
    case "assert_in_viewport": {
      const loc = page.locator(s.selector).first();
      try { await loc.waitFor({ state: "attached", timeout: s.timeout || 5000 }); }
      catch (e) { throw new Error("assert_in_viewport: öğe yok: " + s.selector); }
      const r = await loc.evaluate((el, partial) => {
        const b = el.getBoundingClientRect();
        const W = window.innerWidth, H = window.innerHeight;
        const vis = el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden" &&
          b.width > 0 && b.height > 0;
        const full = b.top >= 0 && b.left >= 0 && b.bottom <= H && b.right <= W;
        const inter = b.bottom > 0 && b.right > 0 && b.top < H && b.left < W;
        return { vis, ok: vis && (partial ? inter : full),
          box: [b.left, b.top, b.right, b.bottom].map(Math.round).join(","), vp: W + "x" + H };
      }, !!s.partial);
      if (!r.ok) {
        const why = r.vis ? (s.partial ? " görünüm alanıyla kesişmiyor" : " görünüm alanının tamamen içinde değil")
          : " görünür değil";
        throw new Error("assert_in_viewport: " + s.selector + why + " (kutu " + r.box + ", görünüm " + r.vp + ")");
      }
      return;
    }
    case "shot": {
      if (cfg.expect_port) {
        const port = await page.evaluate(() => location.port);
        if (String(port) !== String(cfg.expect_port)) throw new Error("sekme başka porta kaymış: " + port);
      }
      const file = path.join(outDir, s.name);
      if (s.selector) await page.locator(s.selector).first().screenshot({ path: file, timeout: s.timeout || 30000 });
      else await page.screenshot({ path: file, fullPage: !!s.full_page });
      return;
    }
    default:
      throw new Error("bilinmeyen adım: " + s.do);
  }
}

async function main(argv) {
  if (!argv[0]) { console.error("kullanım: node capture_kd_screens.js <config.json> [--dry-run]"); return 2; }
  const { cfg, base, errors } = loadConfig(argv[0]);
  if (errors.length) { errors.forEach(e => console.error("HATA: " + e)); return 2; }
  const shots = cfg.steps.filter(s => s.do === "shot").length;
  const asserts = cfg.steps.filter(s => ASSERT_STEPS.has(s.do)).length;
  if (argv.includes("--dry-run")) {
    console.log("YAPILANDIRMA OK: " + cfg.steps.length + " adım, " + shots + " çekim" +
      (asserts ? ", " + asserts + " doğrulama" : "") + " (tarayıcı açılmadı)");
    return 0;
  }
  const pw = resolvePlaywrightCore();
  if (!pw) { console.error("HATA: " + INSTALL); return 2; }
  const { chromium } = require(pw);
  const outDir = path.resolve(base, cfg.out_dir || "screenshots");
  fs.mkdirSync(outDir, { recursive: true });
  const channel = cfg.channel || process.env.PDF_BROWSER_CHANNEL || "chrome";
  let browser;
  try {
    browser = await chromium.launch({ channel: channel === "chromium" ? undefined : channel, headless: true });
  } catch (e) {
    console.error("HATA: tarayıcı başlatılamadı (kanal " + channel + "): " + e.message);
    return 2;
  }
  const results = [];
  try {
    const ctx = await browser.newContext({ viewport: cfg.viewport || { width: 1680, height: 1050 },
      locale: cfg.locale || "tr-TR", deviceScaleFactor: cfg.device_scale_factor || 2 });
    const page = await ctx.newPage();
    await page.goto(cfg.url, { waitUntil: "load", timeout: 60000 });
    for (let i = 0; i < cfg.steps.length; i++) {
      const s = cfg.steps[i];
      const label = (i + 1) + ". " + s.do + (s.name ? " " + s.name : "");
      try {
        await runStep(page, s, base, outDir, cfg);
        if (s.do === "shot" || ASSERT_STEPS.has(s.do)) results.push({ label, ok: true });
      } catch (e) {
        const msg = String(e.message || e).split("\n")[0];
        results.push({ label, ok: false, optional: !!s.optional, msg });
        if (!s.optional && s.do !== "shot") break;
      }
    }
  } finally {
    await browser.close();
  }
  results.forEach(r => console.log((r.ok ? "OK   " : (r.optional ? "SKIP " : "FAIL ")) + r.label + (r.msg ? " — " + r.msg : "")));
  const fails = results.filter(r => !r.ok && !r.optional).length;
  console.log("ÖZET: " + results.filter(r => r.ok).length + " OK, " + fails + " FAIL → " + outDir);
  return fails ? 1 : 0;
}

main(process.argv.slice(2)).then(c => process.exit(c)).catch(e => { console.error("HATA:", e); process.exit(1); });
