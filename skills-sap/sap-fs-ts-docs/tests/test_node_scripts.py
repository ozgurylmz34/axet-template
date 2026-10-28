# -*- coding: utf-8 -*-
"""Node script'leri: sözdizimi, yapılandırma doğrulaması (tarayıcısız), kullanım hataları; isteğe bağlı uçtan uca PDF."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _common import BROWSER_TESTS, SCRIPTS, TEMPLATES, node_path, run_node, run_py, sample


@unittest.skipUnless(node_path(), "node bulunamadı")
class NodeScriptsTest(unittest.TestCase):
    def test_syntax(self):
        for js in ("html_to_pdf.js", "capture_kd_screens.js"):
            r = subprocess.run([node_path(), "--check", os.path.join(os.path.dirname(__file__), "..", "scripts", js)],
                               capture_output=True, text=True)
            self.assertEqual(0, r.returncode, js + r.stderr)

    def test_capture_dry_run_ok(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_ok.json"), "--dry-run")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("7 adım, 2 çekim", r.stdout)
        self.assertIn("KAPSAM (SCOPE)", r.stdout)

    def test_capture_bad_config_exit_2(self):
        r = run_node("capture_kd_screens.js", sample("capture", "config_bad.json"), "--dry-run")
        self.assertEqual(2, r.returncode)
        for part in (".png uzantılı", "bilinmeyen do=teleport", "data_file yok", "aynı çekim adı"):
            self.assertIn(part, r.stderr)

    def test_capture_usage_exit_2(self):
        self.assertEqual(2, run_node("capture_kd_screens.js").returncode)

    def test_html_to_pdf_usage_and_missing_input(self):
        self.assertEqual(2, run_node("html_to_pdf.js").returncode)
        r = run_node("html_to_pdf.js", sample("html", "yok.html"), "yok.pdf")
        self.assertEqual(2, r.returncode)
        self.assertIn("girdi yok", r.stderr)

    def test_html_to_pdf_bilinmeyen_bayrak_yol_sanilmaz(self):
        """Z201: bilinmeyen bayrak sessizce yok sayılmaz / dosya yolu sanılmaz — tarayıcı açılmadan çıkış 2."""
        r = run_node("html_to_pdf.js", sample("html", "yok.html"), "yok.pdf", "--sayfano")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("bilinmeyen bayrak: --sayfano", r.stderr)
        r2 = run_node("html_to_pdf.js", sample("html", "yok.html"), "--sayfa-no")   # bayrak konum sayısına girmez
        self.assertEqual(2, r2.returncode)
        self.assertIn("kullanım:", r2.stderr)

    def test_html_to_pdf_check_reports_state(self):
        r = run_node("html_to_pdf.js", "--check")
        self.assertIn(r.returncode, (0, 2))
        self.assertTrue("playwright-core:" in r.stdout or "npm install playwright-core" in r.stderr)

    def test_playwright_missing_message(self):
        env = dict(os.environ, APPDATA=os.devnull, USERPROFILE=os.devnull, HOME=os.devnull, npm_config_prefix="",
                   NODE_PATH="", PLAYWRIGHT_CORE_PATH="")
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "a.html")
            with open(html, "w", encoding="utf-8") as fh:
                fh.write("<html></html>")
            r = subprocess.run([node_path(), os.path.join(os.path.dirname(__file__), "..", "scripts", "html_to_pdf.js"),
                                html, os.path.join(tmp, "a.pdf")], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env, cwd=tmp)
        if r.returncode == 0:
            self.skipTest("playwright-core bu ortamda başka yoldan çözüldü; eksik bağımlılık simüle edilemedi")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("npm install playwright-core", r.stderr)


@unittest.skipUnless(BROWSER_TESTS, "tarayıcı testi kapalı (SAP_FS_TS_DOCS_BROWSER_TESTS=1 ile açılır)")
@unittest.skipUnless(importlib.util.find_spec("markdown"), "python markdown kurulu değil")
class BrowserPdfTest(unittest.TestCase):
    def test_kd_template_pdf_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "KD-XX-001_Sablon.html")
            pdf = os.path.join(tmp, "KD-XX-001_Sablon.pdf")
            r = run_py("build_doc_pdf.py", os.path.join(TEMPLATES, "KD-template.md"), html, "--pdf-out", pdf, timeout=300)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            v = run_py("verify_doc_html.py", html, "--pdf", pdf, "--min-pdf-links", "14")
            # Şablon ham derlenir → `[GÖRSEL: …]` yer tutucuları BULGU'dur (Z172, çıkış 1). Bu testin ölçtüğü PDF
            # bağlantılarıdır: yer tutucu dışında bulgu olmamalı.
            self.assertIn(v.returncode, (0, 1), v.stdout + v.stderr)
            bulgular = [ln for ln in v.stdout.splitlines() if ln.startswith("BULGU:")]
            self.assertEqual([], [b for b in bulgular if not b.startswith("BULGU: YER TUTUCU")], v.stdout)
            self.assertIn("bağlantı ek açıklaması 14", v.stdout)


def _pdf_olcer():
    """PDF'i ÜRETEN araçtan bağımsız okuyucu: PyMuPDF (metin + yer imi) ya da pdftotext (yalnız metin)."""
    if importlib.util.find_spec("pymupdf"):
        import pymupdf

        def oku(yol):
            with pymupdf.open(yol) as d:   # açık kalırsa Windows'ta geçici klasör silinemez
                return [p.get_text() for p in d], len(d.get_toc())
        return oku
    if shutil.which("pdftotext"):
        def oku(yol):
            r = subprocess.run(["pdftotext", "-enc", "UTF-8", yol, "-"], capture_output=True)
            return r.stdout.decode("utf-8").split("\f")[:-1], None
        return oku
    return None


@unittest.skipUnless(BROWSER_TESTS, "tarayıcı testi kapalı (SAP_FS_TS_DOCS_BROWSER_TESTS=1 ile açılır)")
@unittest.skipUnless(importlib.util.find_spec("markdown"), "python markdown kurulu değil")
class SayfaNoYerImiTest(unittest.TestCase):
    """Z201 kapanış ölçütü, gerçek giriş noktasından (build_doc_pdf.py --pdf): bayraksız PDF eski yapıda (sayfa sayısı
    + metin bayraklıyla altbilgi dışında aynı) · --sayfa-no ile her sayfada 'Sayfa i / N' · yer imi sayısı = başlık."""

    def setUp(self):
        self.oku = _pdf_olcer()
        if not self.oku:
            self.skipTest("PDF okuyucu yok (python -m pip install pymupdf ya da pdftotext)")
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _uret(self, ad, *bayrak):
        html = os.path.join(self.tmp.name, ad + ".html")
        pdf = os.path.join(self.tmp.name, ad + ".pdf")
        r = run_py("build_doc_pdf.py", os.path.join(TEMPLATES, "FS-template.md"), html, "--pdf-out", pdf, *bayrak,
                   timeout=300)
        return r, html, pdf

    def test_sayfa_no_ve_yer_imi_uctan_uca(self):
        r0, _, pdf0 = self._uret("bayraksiz")
        self.assertEqual(0, r0.returncode, r0.stdout + r0.stderr)
        r1, html1, pdf1 = self._uret("bayrakli", "--sayfa-no", "--yer-imi")
        self.assertEqual(0, r1.returncode, r1.stdout + r1.stderr)
        sayfa0, _ = self.oku(pdf0)
        sayfa1, yer_imi = self.oku(pdf1)
        n = len(sayfa0)
        self.assertGreater(n, 1)
        self.assertEqual(n, len(sayfa1), "altbilgi gövdeyi daraltmamalı: sayfa sayısı aynı kalmalı")
        self.assertFalse(any("Sayfa 1 / " in s for s in sayfa0), "bayraksız PDF'te altbilgi olmamalı")
        for i, s in enumerate(sayfa1, 1):
            self.assertIn("Sayfa %d / %d" % (i, n), s)
        norm = lambda s: re.sub(r"\s+", " ", re.sub(r"Sayfa \d+ / \d+", "", s)).strip()
        self.assertEqual([norm(s) for s in sayfa0], [norm(s) for s in sayfa1], "gövde metni altbilgi dışında aynı olmalı")
        with open(html1, encoding="utf-8") as fh:
            baslik = len(re.findall(r"<h[1-6][\s>]", fh.read()))
        self.assertIn("YER-IMI PDF: %d yer imi / %d baslik" % (baslik, baslik), r1.stdout)
        if yer_imi is None:
            self.skipTest("bağımsız yer imi sayımı için PyMuPDF gerekli (araç satırı yukarıda doğrulandı)")
        self.assertEqual(baslik, yer_imi)

    def test_sayfa_no_dar_alt_boslukta_durdu_pdf_yazilmaz(self):
        d = self.tmp.name
        dar = os.path.join(d, "dar.html")
        with open(dar, "w", encoding="utf-8") as fh:
            fh.write("<html><head><style>@page { margin: 10mm 10mm 3mm 10mm; }</style></head><body><h1>X</h1></body></html>")
        r = run_node("html_to_pdf.js", dar, os.path.join(d, "dar.pdf"), "--sayfa-no")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("[DURDU] --sayfa-no: etkin alt bosluk 3.00mm", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(d, "dar.pdf")))
        # kontrol: aynı belge bayraksız üretilir (DURDU yalnız bayrağın kendi koşulu)
        self.assertEqual(0, run_node("html_to_pdf.js", dar, os.path.join(d, "dar2.pdf")).returncode)

    def test_sayfa_no_okunamayan_stil_sayfasi_durdu(self):
        d = self.tmp.name
        with open(os.path.join(d, "dis.css"), "w", encoding="utf-8") as fh:
            fh.write("@page { margin-bottom: 3mm; }")
        dis = os.path.join(d, "dis.html")
        with open(dis, "w", encoding="utf-8") as fh:
            fh.write('<html><head><link rel="stylesheet" href="dis.css"></head><body><h1>X</h1></body></html>')
        r = run_node("html_to_pdf.js", dis, os.path.join(d, "dis.pdf"), "--sayfa-no")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("stil sayfasi okunamadi", r.stderr)
        # kontrol: aynı kural <style> içinde → ölçülür (DURDU okunamama yüzünden, margin yüzünden değil sınıfı ayrı)
        ic = os.path.join(d, "ic.html")
        with open(ic, "w", encoding="utf-8") as fh:
            fh.write("<html><head><style>@page { margin-bottom: 20mm; }</style></head><body><h1>X</h1></body></html>")
        r2 = run_node("html_to_pdf.js", ic, os.path.join(d, "ic.pdf"), "--sayfa-no")
        self.assertEqual(0, r2.returncode, r2.stdout + r2.stderr)
        self.assertIn("etkin alt bosluk 20.0mm (css-@page)", r2.stdout)

    def _dibe_dayanan(self, ad, alt_mm, ek_css=""):
        """Son satırı gövde alanının DİBİNE dayanan tek sayfalık belge (flex sütun; alan yüksekliği = sayfa alanı)."""
        yol = os.path.join(self.tmp.name, ad + ".html")
        with open(yol, "w", encoding="utf-8") as fh:
            fh.write("<html><head><meta charset='utf-8'><style>" + ek_css + " @page { margin: 10mm 10mm %smm 10mm } "
                     "html,body{margin:0;height:100%%} body{display:flex;flex-direction:column;justify-content:flex-end}"
                     "</style></head><body><div style='font-size:12pt;line-height:12pt;text-align:right;"
                     "padding-right:10mm'>gjpqy SON SATIR gjpqy</div></body></html>" % alt_mm)
        return yol, os.path.join(self.tmp.name, ad + ".pdf")

    def test_sayfa_no_altbilgi_govdeye_binmez(self):
        """F1 (bug gate 2026-10-19): Chromium altbilgiyi sayfanın ALT KENARINA göre sabit yere basar; eşik o yerleşimden
        türer. Eşiğin hemen üstünde gövdenin son satırı altbilgiye BİNMEZ (PDF'ten ölçülür), hemen altında DURDU."""
        if not importlib.util.find_spec("pymupdf"):
            self.skipTest("çakışma ölçümü için PyMuPDF gerekli")
        import pymupdf
        h, p = self._dibe_dayanan("olcum", 30)
        r = run_node("html_to_pdf.js", h, p, "--sayfa-no")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        gerek = float(re.search(r"gereken ([\d.]+)mm", r.stdout).group(1))
        # altbilgi yüksekliği belgenin CSS'inden yalıtık ölçülür: !important'lı div kuralı ölçümü küçültmemeli
        h2, p2 = self._dibe_dayanan("dusman", 30, "div{line-height:.3 !important;font-size:3pt !important}")
        r2 = run_node("html_to_pdf.js", h2, p2, "--sayfa-no")
        self.assertEqual(0, r2.returncode, r2.stdout + r2.stderr)
        self.assertEqual(re.search(r"altbilgi ([\d.]+)mm", r.stdout).group(1),
                         re.search(r"altbilgi ([\d.]+)mm", r2.stdout).group(1), "altbilgi ölçümü belge CSS'inden etkilendi")
        ust = round(gerek + 0.3, 1)
        h, p = self._dibe_dayanan("ust", ust)
        r = run_node("html_to_pdf.js", h, p, "--sayfa-no")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        mm = 72 / 25.4
        with pymupdf.open(p) as d:
            self.assertEqual(1, d.page_count)
            sayfa = d[0]
            altbilgi, son = sayfa.search_for("Sayfa 1 / 1")[0], sayfa.search_for("SON SATIR")[0]
            alan_dibi = sayfa.rect.height - ust * mm
            # kalibrasyon: son satır gerçekten alanın dibinde (yoksa çakışma ölçümü boş geçer)
            self.assertLess(alan_dibi - son.y1, 3 * mm, "son satır alanın dibine dayanmıyor")
            self.assertLessEqual(son.y1, altbilgi.y0, "altbilgi gövdenin son satırına biniyor")
        h, p = self._dibe_dayanan("alt", round(gerek - 0.5, 1))
        r = run_node("html_to_pdf.js", h, p, "--sayfa-no")
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("[DURDU]", r.stderr)
        # inceleme vakası (6 mm alt boşluk — eski eşik 6.0 mm'de geçiyordu, altbilgi gövdeye biniyordu)
        h, p = self._dibe_dayanan("alti", 6)
        self.assertEqual(2, run_node("html_to_pdf.js", h, p, "--sayfa-no").returncode)


_SAHTE_PLAYWRIGHT = r"""
// Sahte playwright-core: tarayıcı açmaz; page.pdf seçeneklerini, evaluate sayısını ve sayfa başına çağrıları JSON'a
// yazar. SAHTE_HATA: "pdf" -> page.pdf dosya YAZMADAN atar · "close" -> PDF yazıldıktan SONRA browser.close atar ·
// "launch" -> tarayıcı başlatılamaz.
const fs = require("fs");
const kayit = process.env.SAHTE_KAYIT;
const hata = process.env.SAHTE_HATA || "";
const olcum = JSON.parse(process.env.SAHTE_OLCUM || "null");
const durum = { pdf: null, evaluate: 0, sayfalar: [] };
const yaz = () => fs.writeFileSync(kayit, JSON.stringify(durum));
const yeniSayfa = () => {
  const iz = { goto: 0, setContent: 0, evaluate: [], close: 0 };
  durum.sayfalar.push(iz);
  return {
    goto: async () => { iz.goto++; }, emulateMedia: async () => {},
    setContent: async () => { iz.setContent++; yaz(); }, close: async () => { iz.close++; yaz(); },
    evaluate: async (fn, arg) => { durum.evaluate++;
      const tur = arg === undefined ? "baslik" : typeof arg === "string" ? "altbilgi" : "alt-bosluk";
      iz.evaluate.push(tur); yaz();
      if (tur === "baslik") return { toplam: 0, uygulanan: 0, geri: 0 };
      if (tur === "altbilgi") return olcum.altbilgiMm;
      const o = Object.assign({}, olcum); delete o.altbilgiMm; return o; },
    pdf: async (o) => { if (hata === "pdf") throw new Error("sahte pdf hatasi");
      durum.pdf = o; yaz(); fs.writeFileSync(o.path, "%PDF-1.4 sahte"); },
  };
};
module.exports = { chromium: { launch: async () => {
  if (hata === "launch") throw new Error("sahte launch hatasi");
  return { newContext: async () => ({ newPage: async () => yeniSayfa() }),
           close: async () => { if (hata === "close") throw new Error("sahte close hatasi"); } }; } } };
"""


@unittest.skipUnless(node_path(), "node bulunamadı")
class SahteTarayiciTest(unittest.TestCase):
    """Tarayıcısız (CI'da koşar): GERÇEK html_to_pdf.js, sahte playwright-core ile (PLAYWRIGHT_CORE_PATH). page.pdf
    seçenek nesnesi ve --sayfa-no eşik/DURDU mantığı ölçülür; yerleşimin gerçekliği tarayıcılı SayfaNoYerImiTest'tedir."""

    # Taban 9fe98c8 html_to_pdf.js'in page.pdf çağrısı (path hariç) — bayraksız seçenek bununla BİREBİR kalmalı.
    TABAN_SECENEK = {"format": "A4", "printBackground": True,
                     "margin": {"top": "14mm", "bottom": "16mm", "left": "12mm", "right": "12mm"}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.pw = os.path.join(d, "sahte-pw")
        os.makedirs(self.pw)
        with open(os.path.join(self.pw, "package.json"), "w", encoding="utf-8") as fh:
            fh.write('{"name": "playwright-core", "main": "index.js"}')
        with open(os.path.join(self.pw, "index.js"), "w", encoding="utf-8") as fh:
            fh.write(_SAHTE_PLAYWRIGHT)
        self.html = os.path.join(d, "a.html")
        with open(self.html, "w", encoding="utf-8") as fh:
            fh.write("<html></html>")
        self.pdf = os.path.join(d, "a.pdf")
        self.kayit = os.path.join(d, "kayit.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _kos(self, *bayrak, olcum=None, hata=""):
        if os.path.exists(self.kayit):
            os.remove(self.kayit)
        env = dict(os.environ, PLAYWRIGHT_CORE_PATH=self.pw, SAHTE_KAYIT=self.kayit, SAHTE_OLCUM=json.dumps(olcum),
                   SAHTE_HATA=hata)
        r = subprocess.run([node_path(), os.path.join(SCRIPTS, "html_to_pdf.js"), self.html, self.pdf, *bayrak],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
        kayit = None
        if os.path.exists(self.kayit):
            with open(self.kayit, encoding="utf-8") as fh:
                kayit = json.load(fh)
        return r, kayit

    @staticmethod
    def _olcum(etkin, altbilgi=4.0, okunamayan=()):
        return {"etkinMm": etkin, "kaynak": "css-@page", "altbilgiMm": altbilgi, "medya": {"sorgu": 0, "viewport": 0},
                "okunamayan": list(okunamayan), "adopted": 0}

    def test_KONTROL_bayraksiz_page_pdf_secenegi_tabanla_birebir(self):
        r, kayit = self._kos()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        secenek = dict(kayit["pdf"])
        self.assertEqual(os.path.abspath(self.pdf), os.path.abspath(secenek.pop("path")))
        self.assertEqual(self.TABAN_SECENEK, secenek)
        self.assertEqual(0, kayit["evaluate"], "bayraksız yolda belge ölçülmemeli/değiştirilmemeli")

    def test_sayfa_no_esik_alt_ic_bosluk_dahil(self):
        """Eşik = alt iç boşluk + altbilgi + pay. 'altbilgi + pay' (eski hesap, 6 mm) yetmez: 9 mm'de DURDU."""
        r, kayit = self._kos("--sayfa-no", olcum=self._olcum(9.0))
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIn("[DURDU]", r.stderr)
        self.assertIsNone(kayit["pdf"])
        m = re.search(r"gereken ([\d.]+)mm = alt ic bosluk ([\d.]+)mm \+ altbilgi 4\.0mm \(ayri sayfada\) \+ pay 2mm", r.stdout)
        self.assertTrue(m, r.stdout)
        gerek = float(m.group(1))
        self.assertAlmostEqual(gerek, float(m.group(2)) + 4.0 + 2, places=1)
        r2, kayit2 = self._kos("--sayfa-no", olcum=self._olcum(gerek + 0.1))
        self.assertEqual(0, r2.returncode, r2.stdout + r2.stderr)
        self.assertTrue(kayit2["pdf"]["displayHeaderFooter"])
        self.assertIn('Sayfa <span class="pageNumber"></span>', kayit2["pdf"]["footerTemplate"])
        secenek = {k: v for k, v in kayit2["pdf"].items()
                   if k not in ("path", "displayHeaderFooter", "headerTemplate", "footerTemplate")}
        self.assertEqual(self.TABAN_SECENEK, secenek, "--sayfa-no gövde margin'ini değiştirmemeli")

    def test_sayfa_no_esik_siniri_iki_ondalik(self):
        """Sınır vakası: eşiğin 0.1 mm altı DURDU (eşiğe tolerans eklenmemeli); mesaj iki ondalıkla çelişkisiz okunur."""
        r, _ = self._kos("--sayfa-no", olcum=self._olcum(30.0))
        gerek = float(re.search(r"gereken ([\d.]+)mm", r.stdout).group(1))
        r, kayit = self._kos("--sayfa-no", olcum=self._olcum(round(gerek - 0.1, 2)))
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertIsNone(kayit["pdf"])
        self.assertIn("[DURDU] --sayfa-no: etkin alt bosluk %.2fmm < gereken %.2fmm" % (gerek - 0.1, gerek), r.stderr)

    def test_durdu_onceki_pdf_silinmez_uyari_basar(self):
        """Ö3: DURDU'da (dar margin · okunamayan stil sayfası) hedefteki eski PDF silinmez, sessiz de kalmaz."""
        with open(self.pdf, "w", encoding="utf-8") as fh:
            fh.write("%PDF eski")
        for olcum in (self._olcum(3.0), self._olcum(30.0, okunamayan=["dis.css"])):
            r, _ = self._kos("--sayfa-no", olcum=olcum)
            self.assertEqual(2, r.returncode, r.stdout + r.stderr)
            self.assertIn("UYARI: hedefte onceki PDF duruyor, bu kosumda yazilmadi: ", r.stderr)
            with open(self.pdf, encoding="utf-8") as fh:
                self.assertEqual("%PDF eski", fh.read())

    def test_KONTROL_durdu_onceki_pdf_yoksa_uyari_yok(self):
        r, _ = self._kos("--sayfa-no", olcum=self._olcum(3.0))
        self.assertEqual(2, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("onceki PDF", r.stderr)
        self.assertFalse(os.path.exists(self.pdf))

    def test_altbilgi_ayri_bos_sayfada_olculur(self):
        """Altbilgi yüksekliği belgenin sayfasında DEĞİL, setContent ile açılan ayrı boş sayfada ölçülür (belge CSS'i
        — ata zoom/display:none dahil — ona ulaşamaz). Belge sayfasında yalnız alt boşluk ölçümü koşar."""
        r, kayit = self._kos("--sayfa-no", olcum=self._olcum(30.0))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        belge, *diger = kayit["sayfalar"]
        self.assertEqual((1, ["alt-bosluk"]), (belge["goto"], belge["evaluate"]))
        self.assertEqual(1, len(diger), kayit["sayfalar"])
        self.assertEqual({"goto": 0, "setContent": 1, "evaluate": ["altbilgi"], "close": 1}, diger[0])
        self.assertIn("altbilgi 4.0mm (ayri sayfada)", r.stdout)

    def test_hata_yolunda_onceki_pdf_silinmez_uyari_basar(self):
        """PDF yazılmadan çıkılan HATA yolları (page.pdf hatası exit 1 · tarayıcı başlatılamadı exit 2) da hedefteki
        eski PDF'i silmez ve sessiz kalmaz — DURDU dalıyla aynı uyarı."""
        with open(self.pdf, "w", encoding="utf-8") as fh:
            fh.write("%PDF eski")
        for hata, rc, bayrak in (("pdf", 1, ("--sayfa-no",)), ("pdf", 1, ()), ("launch", 2, ())):
            r, _ = self._kos(*bayrak, olcum=self._olcum(30.0), hata=hata)
            self.assertEqual(rc, r.returncode, (hata, bayrak, r.stdout + r.stderr))
            self.assertIn("sahte " + hata + " hatasi", r.stderr)
            self.assertIn("UYARI: hedefte onceki PDF duruyor, bu kosumda yazilmadi: ", r.stderr, (hata, bayrak))
            with open(self.pdf, encoding="utf-8") as fh:
                self.assertEqual("%PDF eski", fh.read())

    def test_KONTROL_hata_yolunda_uyari_yalniz_yazilmadiysa(self):
        """Doğru-negatif: hedef yokken hata → uyarı yok · PDF YAZILDIKTAN sonra gelen hata (browser.close) → exit 1
        ama uyarı yok (dosya bu koşunun çıktısıdır)."""
        r, _ = self._kos("--sayfa-no", olcum=self._olcum(30.0), hata="pdf")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertNotIn("onceki PDF", r.stderr)
        self.assertFalse(os.path.exists(self.pdf))
        with open(self.pdf, "w", encoding="utf-8") as fh:
            fh.write("%PDF eski")
        r, kayit = self._kos("--sayfa-no", olcum=self._olcum(30.0), hata="close")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("sahte close hatasi", r.stderr)
        self.assertNotIn("onceki PDF", r.stderr)
        self.assertIsNotNone(kayit["pdf"])
        with open(self.pdf, encoding="utf-8") as fh:
            self.assertEqual("%PDF-1.4 sahte", fh.read())


@unittest.skipUnless(BROWSER_TESTS, "tarayıcı testi kapalı (SAP_FS_TS_DOCS_BROWSER_TESTS=1 ile açılır)")
@unittest.skipUnless(node_path(), "node bulunamadı")
class SayfaNoOlcumYalitimTest(unittest.TestCase):
    """--sayfa-no ölçümleri belgenin CSS'inden yalıtık (kaynak çekirdek Issue #360 vektörleri P12b · P13e · P13f ve
    kardeşleri). Gerçek tarayıcı, gerçek html_to_pdf.js; hüküm aracın ALTBILGI satırı + çıkış kodu."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _kos(self, ad, alt, css=""):
        html = os.path.join(self.tmp.name, ad + ".html")
        with open(html, "w", encoding="utf-8") as fh:
            fh.write("<html><head><meta charset='utf-8'><style>@page{margin:10mm 10mm %s 10mm} %s</style></head>"
                     "<body><div>gövde</div></body></html>" % (alt, css))
        r = run_node("html_to_pdf.js", html, os.path.join(self.tmp.name, ad + ".pdf"), "--sayfa-no")
        m = re.search(r"etkin alt bosluk ([\d.]+)mm .*altbilgi ([\d.]+)mm", r.stdout)
        self.assertTrue(m, r.stdout + r.stderr)
        return r, float(m.group(1)), float(m.group(2))

    def test_uzunluk_olcumu_belge_cssinden_yalitik(self):
        r, etkin, _ = self._kos("kontrol", "20mm")
        self.assertEqual((0, 20.0), (r.returncode, etkin), r.stdout + r.stderr)   # kontrol: düz belge
        # (beklenen etkin mm = baskıdaki değer, beklenen rc) — baskıda @page uzunluğu KÖKE göre çözülür
        vakalar = {
            # ölçüm elemanını KÜÇÜLTEN belge kuralı — eski düz div 0.3 mm sanıp SAHTE DURDU veriyordu
            "kucultme": ("20mm", "div{max-height:1px !important}", 20.0, 0),
            # ŞİŞİREN kural — eski düz div 6 mm'yi daha büyük sanıp SESSİZ geçiyordu (baskıda altbilgi biner)
            "sisirme": ("6mm", "div{padding:20px !important}", 6.0, 2),
            # P13e: 2em KÖKÜN yazı boyutuna göre (30px → 15.9 mm); eski gövdeye göre 5.3 mm sanıp sahte DURDU
            "em_kok": ("2em", "html{font-size:30px} body{font-size:10px}", 15.9, 0),
            # P13f: 3lh KÖKÜN satır yüksekliğiyle (6.3 mm); font-size-yalnız miras 14.3 mm sanıp sessiz geçerdi
            "lh_kok": ("3lh", "html{line-height:0.5}", 6.3, 2),
        }
        for ad, (alt, css, beklenen, rc) in vakalar.items():
            r, etkin, _ = self._kos(ad, alt, css)
            self.assertEqual((rc, beklenen), (r.returncode, etkin), (ad, r.stdout + r.stderr))

    def test_altbilgi_olcumu_belge_cssinden_yalitik(self):
        r, _, taban = self._kos("kontrol", "20mm")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertTrue(3.5 <= taban <= 4.5, taban)   # kontrol: 8 pt şablon ≈ 4 mm
        # P12b (eski: belge içinde 42.3 mm → sahte DURDU) · ata zoom ve display:none (belge içi gölge kökü de
        # etkiler: 0.8 / 0 mm → sessiz geçiş yönü). Ayrı sayfada üçü de tabanla AYNI.
        for ad, css in (("p12b", "div{font-size:40pt !important;line-height:3 !important}"),
                        ("zoom", "html{zoom:0.2}"), ("gizli", "*{display:none !important}")):
            r, _, altbilgi = self._kos(ad, "20mm", css)
            self.assertEqual(taban, altbilgi, (ad, r.stdout + r.stderr))
            if ad == "p12b":
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
