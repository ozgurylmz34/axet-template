# -*- coding: utf-8 -*-
"""build_doc_pdf.py + verify_doc_html.py + doc_tools.py (tarayıcısız kısımlar)."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from _common import TEMPLATES, call_main, run_py, sample

import build_doc_pdf
import doc_tools
import verify_doc_html as vdh

HAS_MARKDOWN = importlib.util.find_spec("markdown") is not None


class SlugTest(unittest.TestCase):
    def test_slug_tr(self):
        cases = {
            "4-A. Liste ve tablo ekranı özellikleri": "4-a-liste-ve-tablo-ekrani-ozellikleri",
            "Liste / Tablo": "liste--tablo",
            "4.2 Kalem": "42-kalem",
            "Kılavuz": "kilavuz",
            "İŞLEM Günlüğü": "islem-gunlugu",
        }
        for src, exp in cases.items():
            self.assertEqual(exp, build_doc_pdf.slug_tr(src), src)

    def test_diagram_prefix(self):
        self.assertEqual("kd-sd-001", build_doc_pdf.diagram_prefix(os.path.join("x", "KD-SD-001_Ad_Soyad.html")))
        self.assertEqual("diagram", build_doc_pdf.diagram_prefix("___.html"))


@unittest.skipUnless(HAS_MARKDOWN, "python markdown kurulu değil (python -m pip install markdown)")
class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, text):
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def test_templates_build_without_dead_links(self):
        for tpl in ("FS-template.md", "TS-template.md", "KD-template.md"):
            html = os.path.join(self.dir, tpl.replace("-template.md", "-XX-001_Sablon.html"))
            with mock.patch.object(doc_tools, "resolve_cli", return_value=None):
                call_main(build_doc_pdf.main, [os.path.join(TEMPLATES, tpl), html])
            findings, stats = vdh.check_html(html)
            dead = [f for f in findings if f.startswith("ÖLÜ")]
            self.assertEqual([], dead, tpl)
        _, stats = vdh.check_html(os.path.join(self.dir, "KD-XX-001_Sablon.html"))
        self.assertEqual(14, stats["internal_links"])

    def test_also_parts_are_merged(self):
        p1 = self._write("p1.md", "# TS-XX-001\n\n## 1. Bir\n")
        p2 = self._write("p2.md", "## 2. İki bölüm\n")
        html = os.path.join(self.dir, "TS-XX-001_Parca.html")
        rc, out, _ = call_main(build_doc_pdf.main, [p1, html, "Başlık <&>", "--also", p2])
        self.assertEqual(0, rc)
        with open(html, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('id="1-bir"', text)
        self.assertIn('id="2-iki-bolum"', text)
        self.assertIn("<title>Başlık &lt;&amp;&gt;</title>", text)
        self.assertIn("KAPSAM (SCOPE)", out)

    def test_figure_wrap(self):
        md = self._write("f.md", "# Doc\n\n![Şekil 1 — Liste](screenshots/a.png)\n\n*Şekil 1 — Liste*\n")
        html = os.path.join(self.dir, "KD-XX-002_F.html")
        rc, out, _ = call_main(lambda a: build_doc_pdf.build(*a), [md, html])
        self.assertIn("<img>: 1 | <figure>: 1", out)

    def test_mermaid_without_mmdc_is_flagged(self):
        md = self._write("m.md", "# Doc\n\n```mermaid\nflowchart LR\n  A --> B\n```\n")
        html = os.path.join(self.dir, "FS-XX-003_M.html")
        with mock.patch.object(doc_tools, "resolve_cli", return_value=None):
            rc, out, err = call_main(build_doc_pdf.main, [md, html])
        self.assertEqual(0, rc)
        self.assertIn("mmdc bulunamadı", err)
        self.assertIn("1 blok, 0 render", out)
        findings, _ = vdh.check_html(html)
        self.assertTrue(any(f.startswith("HAM MERMAID") for f in findings), findings)

    def test_pdf_without_node_exit_2(self):
        html = self._write("x.html", "<html></html>")
        with mock.patch.object(build_doc_pdf.shutil, "which", return_value=None):
            rc, _, err = call_main(lambda a: build_doc_pdf.to_pdf(*a), [html])
        self.assertEqual(2, rc)
        self.assertIn("node bulunamadı", err)


class MissingDependencyTest(unittest.TestCase):
    def test_markdown_missing_exit_2(self):
        with mock.patch.dict(sys.modules, {"markdown": None}):
            rc, _, err = call_main(lambda a: build_doc_pdf._load_markdown(), [])
        self.assertEqual(2, rc)
        self.assertIn("pip install markdown", err)

    def test_mermaid_render_missing_cli_message(self):
        with mock.patch.object(doc_tools, "resolve_cli", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                doc_tools.render_mermaid("a.mmd", "a.png")
        self.assertIn("npm i -g @mermaid-js/mermaid-cli", str(ctx.exception))

    def test_doc_tools_check_runs(self):
        rc, out, _ = call_main(doc_tools.main, ["check"])
        self.assertEqual(0, rc)
        self.assertIn("python-markdown", out)


class VerifyHtmlTest(unittest.TestCase):
    def test_broken_sample(self):
        findings, stats = vdh.check_html(sample("html", "broken.html"))
        text = "\n".join(findings)
        self.assertIn("#olmayan-bolum", text)
        self.assertNotIn("#eski-cipa", text, "a name çıpası geçerli hedeftir")
        self.assertNotIn("#kd-xx-001", text)
        self.assertIn("HAM MERMAID", text)
        self.assertIn("screenshots/yok.png", text)
        self.assertEqual(1, stats["dead"])
        self.assertEqual(3, stats["internal_links"])

    def test_broken_sample_cli_exit_1(self):
        r = run_py("verify_doc_html.py", sample("html", "broken.html"), "--expect-images", "2")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("GÖRSEL SAYISI: beklenen 2, bulunan 1", r.stdout)
        self.assertIn("KAPSAM (SCOPE)", r.stdout)

    def test_unreadable_exit_2(self):
        r = run_py("verify_doc_html.py", sample("html", "yok.html"))
        self.assertEqual(2, r.returncode)

    def test_pdf_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = os.path.join(tmp, "ok.pdf")
            with open(ok, "wb") as fh:
                fh.write(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Annot /Subtype /Link >> endobj\n")
            f, s = vdh.check_pdf(ok, internal_links=1, min_links=1)
            self.assertEqual([], f)
            self.assertEqual(1, s["link_annotations"])
            self.assertEqual(1, s["pages"])
            comp = os.path.join(tmp, "comp.pdf")
            with open(comp, "wb") as fh:
                fh.write(b"%PDF-1.7\n1 0 obj << /Type /ObjStm >> endobj\n")
            f, s = vdh.check_pdf(comp, internal_links=5)
            self.assertEqual([], f)
            self.assertIn("ÖLÇÜLEMEDİ", s["link_note"])
            nolink = os.path.join(tmp, "nolink.pdf")
            with open(nolink, "wb") as fh:
                fh.write(b"%PDF-1.4\n")
            f, _ = vdh.check_pdf(nolink, internal_links=3)
            self.assertTrue(f)
            f, _ = vdh.check_pdf(os.path.join(tmp, "yok.pdf"), internal_links=0)
            self.assertTrue(f[0].startswith("PDF YOK"))


class YerTutucuTest(unittest.TestCase):
    """Z172: görünür metinde unutulmuş yer tutucu = BULGU; [Açık Konu] = BİLGİ. Tarayıcı iki yönlü kalibre edilir:
    bilinen doğru-pozitif (yer_tutucu.html, şablon ham derlemesi) ve doğru-negatif (temiz_kd.html, eşlenmiş demo KD)."""

    def test_dogru_pozitif_her_kalip_ve_sayi(self):
        findings, stats = vdh.check_html(sample("html", "yer_tutucu.html"))
        metin = "\n".join(findings)
        beklenen = {"[EKRAN GÖRÜNTÜSÜ …]": 2, "[GÖRSEL: …]": 1, "EKRAN GÖRÜNTÜSÜ … eklenecek": 1,
                    "Faz-N'de eklenecek": 1, "[AÇIKLAMA YAZILMADI]": 1, "TODO": 1, "TBD": 1, "FIXME": 1}
        for ad, n in beklenen.items():
            self.assertIn("YER TUTUCU (%s): %d kez" % (ad, n), metin)
        # script/style/yorum/öznitelik içindekiler taranmaz; aynı metin birden çok kalıba uysa da bir kez sayılır
        self.assertEqual(9, stats["placeholder"])
        self.assertEqual(0, stats["acik_konu"])

    def test_her_kalip_ornekte_temsil_ediliyor(self):
        """Kalıp listesine eklenen her öğe doğru-pozitif örnekte en az bir kez yakalanmalı (kalibrasyonsuz kalıp olmaz)."""
        findings, _ = vdh.check_html(sample("html", "yer_tutucu.html"))
        metin = "\n".join(findings)
        for ad, _rx in vdh.YER_TUTUCULAR:
            self.assertIn("YER TUTUCU (%s)" % ad, metin)

    def test_dogru_negatif_temiz_kd_acik_konu_bilgi(self):
        findings, stats = vdh.check_html(sample("html", "temiz_kd.html"))
        self.assertEqual([], findings)
        self.assertEqual(0, stats["placeholder"])
        self.assertEqual(2, stats["acik_konu"])

    def test_cli_bulgu_exit_1_ve_kapsam_listeden(self):
        r = run_py("verify_doc_html.py", sample("html", "yer_tutucu.html"), "--expect-images", "1")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)
        self.assertIn("BULGU: YER TUTUCU ([EKRAN GÖRÜNTÜSÜ …]): 2 kez", r.stdout)
        self.assertIn("yer tutucu 9", r.stdout)
        kapsam = next(ln for ln in r.stdout.splitlines() if ln.startswith("KAPSAM (SCOPE)"))
        for ad, _rx in vdh.YER_TUTUCULAR:
            self.assertIn(ad, kapsam)
        self.assertIn("[Açık Konu]", kapsam)

    def test_cli_acik_konu_bilgi_exit_0(self):
        r = run_py("verify_doc_html.py", sample("html", "temiz_kd.html"), "--expect-images", "1")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("BİLGİ: [Açık Konu] işareti 2 kez", r.stdout)
        self.assertNotIn("BULGU:", r.stdout)

    def test_build_kd_pdf_isareti_ile_esli(self):
        """build_kd_pdf'in eksik açıklama işareti değişirse tarayıcı körleşmesin."""
        import build_kd_pdf
        bulunan, _ = vdh.yer_tutucu_tara(build_kd_pdf.ACIKLAMA_YOK.strip("*"))
        self.assertIn("[AÇIKLAMA YAZILMADI]", bulunan)


@unittest.skipUnless(HAS_MARKDOWN, "python markdown kurulu değil (python -m pip install markdown)")
class YerTutucuUretimHattiTest(unittest.TestCase):
    """Gerçek üretim hattından geçen HTML ile kalibrasyon (elle yazılmış örnek değil)."""

    def test_sablon_ham_derleme_gorsel_yer_tutuculari_bulgu(self):
        with open(os.path.join(TEMPLATES, "KD-template.md"), encoding="utf-8") as fh:
            beklenen = fh.read().count("[GÖRSEL:")
        self.assertGreater(beklenen, 0)
        with tempfile.TemporaryDirectory() as tmp:
            html = os.path.join(tmp, "KD-XX-001_Sablon.html")
            with mock.patch.object(doc_tools, "resolve_cli", return_value=None):
                call_main(build_doc_pdf.main, [os.path.join(TEMPLATES, "KD-template.md"), html])
            findings, _ = vdh.check_html(html)
        self.assertIn("YER TUTUCU ([GÖRSEL: …]): %d kez" % beklenen, "\n".join(findings))

    def test_eslenmis_demo_kd_temiz_eksik_aciklama_bulgu(self):
        import build_kd_pdf
        with open(sample("kd", "KD-XX-001_Demo.md"), encoding="utf-8") as fh:
            md = fh.read()
        with open(sample("kd", "map.json"), encoding="utf-8") as fh:
            esleme = json.load(fh)
        temiz, eksik, _ = build_kd_pdf.apply_map(md, esleme)
        self.assertEqual([], eksik)
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "k.md")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(temiz + "\n## 6. Adım\n" + build_kd_pdf.ACIKLAMA_YOK + "\n")
            html = os.path.join(tmp, "KD-XX-001_Demo.html")
            call_main(lambda a: build_doc_pdf.build(*a), [src, html])
            findings, stats = vdh.check_html(html)
        self.assertEqual(1, stats["placeholder"], findings)
        self.assertIn("YER TUTUCU ([AÇIKLAMA YAZILMADI]): 1 kez", "\n".join(findings))


if __name__ == "__main__":
    unittest.main()
