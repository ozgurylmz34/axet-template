# -*- coding: utf-8 -*-
"""build_kd_pdf.py: eşleme uygulama, tekrar koşum, eksik görsel, yardım kopyası, Pillow yokluğu,
manifest (biçim B) üretimi ve şema hataları."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest

from _common import call_main, sample, write_png

import build_kd_pdf

HAS_MARKDOWN = importlib.util.find_spec("markdown") is not None
HAS_PIL = importlib.util.find_spec("PIL") is not None


def _load(name):
    with open(sample("kd", name), encoding="utf-8") as fh:
        return fh.read()


class ApplyMapTest(unittest.TestCase):
    def setUp(self):
        self.md = _load("KD-XX-001_Demo.md")
        self.mapping = json.loads(_load("map.json"))

    def test_fence_replaced_and_heading_inserted(self):
        out, missing, images = build_kd_pdf.apply_map(self.md, self.mapping)
        self.assertEqual([], missing)
        self.assertNotIn("[GÖRSEL: Liste ekranı", out)
        self.assertIn("![Şekil 1 — Liste ekranı](screenshots/kd-01-liste.png)", out)
        self.assertEqual(1, out.count("screenshots/kd-02-toplu.png"))
        self.assertNotIn("①", out)
        self.assertEqual(["kd-01-liste.png", "kd-02-toplu.png"], images)

    def test_second_run_is_idempotent(self):
        once, _, _ = build_kd_pdf.apply_map(self.md, self.mapping)
        twice, missing, images = build_kd_pdf.apply_map(once, self.mapping)
        self.assertEqual(once, twice)
        self.assertEqual([], missing)
        self.assertEqual(2, len(set(images)))

    def test_unknown_key_and_heading_reported(self):
        mapping = {"fences": {"Olmayan anahtar": [{"img": "x.png", "caption": "x"}]},
                   "after_heading": {"### 9.9 Yok": [{"img": "y.png", "caption": "y"}]}}
        _, missing, _ = build_kd_pdf.apply_map(self.md, mapping)
        self.assertEqual(["Olmayan anahtar", "### 9.9 Yok"], missing)

    def test_mermaid_fence_untouched(self):
        md = "```mermaid\nflowchart LR\n Liste ekranı --> B\n```\n"
        out, missing, _ = build_kd_pdf.apply_map(md, {"fences": {"Liste ekranı": [{"img": "a.png", "caption": "a"}]}})
        self.assertEqual(md, out)
        self.assertEqual(["Liste ekranı"], missing)


@unittest.skipUnless(HAS_MARKDOWN, "python markdown kurulu değil (python -m pip install markdown)")
class KdMainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.md = os.path.join(self.dir, "KD-XX-001_Demo.md")
        self.map = os.path.join(self.dir, "map.json")
        shutil.copyfile(sample("kd", "KD-XX-001_Demo.md"), self.md)
        shutil.copyfile(sample("kd", "map.json"), self.map)
        self.html = os.path.join(self.dir, "KD-XX-001_Demo.html")

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_build_with_help_copy(self):
        for name in ("kd-01-liste.png", "kd-02-toplu.png"):
            write_png(os.path.join(self.dir, "screenshots", name))
        help_dir = os.path.join(self.dir, "app", "webapp", "help")
        rc, out, err = call_main(build_kd_pdf.main, [self.md, self.html, "--map", self.map, "--write-clean",
                                                    "--help-dir", help_dir])
        self.assertEqual(0, rc, out + err)
        self.assertIn("<img>: 2 | <figure>: 2", out)
        self.assertTrue(os.path.isfile(os.path.join(help_dir, "kullanici-kilavuzu.html")))
        self.assertTrue(os.path.isfile(os.path.join(help_dir, "screenshots", "kd-02-toplu.png")))
        rc2, out2, _ = call_main(build_kd_pdf.main, [self.md, self.html, "--map", self.map])
        self.assertEqual(0, rc2, out2)

    def test_missing_image_exit_1(self):
        write_png(os.path.join(self.dir, "screenshots", "kd-01-liste.png"))
        rc, out, _ = call_main(build_kd_pdf.main, [self.md, self.html, "--map", self.map])
        self.assertEqual(1, rc)
        self.assertIn("görsel dosyası yok: screenshots/kd-02-toplu.png", out)

    def test_bad_map_exit_2(self):
        with open(self.map, "w", encoding="utf-8") as fh:
            fh.write("{bozuk")
        rc, _, err = call_main(build_kd_pdf.main, [self.md, self.html, "--map", self.map])
        self.assertEqual(2, rc)
        self.assertIn("okunamadı", err)

    def test_trim_from(self):
        raw = os.path.join(self.dir, "raw")
        for name in ("kd-01-liste.png", "kd-02-toplu.png"):
            # 2026-09-14: height=120/border=60 koyu alanı 0 piksel yapıyordu (getbbox None → kırpma yok, test FAIL).
            write_png(os.path.join(raw, name), width=200, height=200, border=60)
        rc, out, err = call_main(build_kd_pdf.main, [self.md, self.html, "--map", self.map, "--trim-from", raw])
        if not HAS_PIL:
            self.assertEqual(2, rc)
            self.assertIn("pip install Pillow", err)
            return
        self.assertEqual(0, rc, out + err)
        from PIL import Image
        with Image.open(os.path.join(self.dir, "screenshots", "kd-01-liste.png")) as im:
            self.assertEqual((108, 108), im.size)  # koyu alan 80 px + her yanda 14 px kenar payı


class ManifestToMdTest(unittest.TestCase):
    """Biçim B'nin çekirdeği: manifest → Markdown. Değişmez — araç adım metnini UYDURMAZ."""

    def test_baslik_giris_adim_ve_gorsel_uretilir(self):
        man = {"title": "Kılavuz", "intro": "Giriş.",
               "steps": [{"heading": "Adım bir", "text": "Açıklama.", "img": "a.png", "caption": "Şekil 1"}]}
        md, eksik, images = build_kd_pdf.manifest_to_md(man)
        self.assertEqual([], eksik)
        self.assertEqual(["a.png"], images)
        self.assertIn("# Kılavuz", md)
        self.assertIn("Giriş.", md)
        self.assertIn("## Adım bir", md)
        self.assertIn("![Şekil 1](screenshots/a.png)", md)

    def test_metin_listesi_ayri_paragraf_olur(self):
        man = {"steps": [{"heading": "H", "text": ["Bir.", "", "İki."]}]}
        md, eksik, images = build_kd_pdf.manifest_to_md(man)
        self.assertEqual([], eksik)
        self.assertEqual([], images)
        self.assertIn("Bir.\n\nİki.", md)

    def test_aciklama_yoksa_uydurulmaz_isaretlenir(self):
        man = {"steps": [{"heading": "Metinsiz", "img": "a.png"},
                         {"heading": "Bos metin", "text": "   "}]}
        md, eksik, _ = build_kd_pdf.manifest_to_md(man)
        self.assertEqual(["Metinsiz", "Bos metin"], eksik)
        self.assertEqual(2, md.count(build_kd_pdf.ACIKLAMA_YOK))

    def test_caption_yoksa_baslik_kullanilir(self):
        md, _, _ = build_kd_pdf.manifest_to_md({"steps": [{"heading": "Başlık", "text": "x", "img": "a.png"}]})
        self.assertIn("![Başlık](screenshots/a.png)", md)

    def test_heading_level_uygulanir(self):
        md, _, _ = build_kd_pdf.manifest_to_md({"heading_level": 3, "steps": [{"heading": "H", "text": "x"}]})
        self.assertIn("### H", md)

    def test_sema_ihlalleri_manifest_hatasi(self):
        for man, parca in ((["liste"], "JSON nesnesi"),
                           ({}, "'steps' boş olmayan"),
                           ({"steps": []}, "'steps' boş olmayan"),
                           ({"steps": ["x"]}, "steps[1] bir nesne"),
                           ({"steps": [{"text": "x"}]}, "'heading' zorunlu"),
                           ({"steps": [{"heading": "  "}]}, "'heading' zorunlu"),
                           ({"heading_level": 0, "steps": [{"heading": "H"}]}, "heading_level"),
                           ({"heading_level": True, "steps": [{"heading": "H"}]}, "heading_level"),
                           ({"steps": [{"heading": "H", "img": 5}]}, "'img' boş olmayan")):
            with self.subTest(man=man):
                with self.assertRaises(build_kd_pdf.ManifestHatasi) as ctx:
                    build_kd_pdf.manifest_to_md(man)
                self.assertIn(parca, str(ctx.exception))


@unittest.skipUnless(HAS_MARKDOWN, "python markdown kurulu değil (python -m pip install markdown)")
class ManifestMainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.html = os.path.join(self.dir, "KD.html")
        self.man = os.path.join(self.dir, "man.json")
        write_png(os.path.join(self.dir, "screenshots", "kd-01.png"))

    def tearDown(self):
        self.tmp.cleanup()

    def _yaz(self, man):
        with open(self.man, "w", encoding="utf-8") as fh:
            json.dump(man, fh, ensure_ascii=False)
        return self.man

    def test_manifest_build_ve_write_md(self):
        self._yaz({"title": "Kılavuz", "steps": [{"heading": "Adım", "text": "Açıklama.", "img": "kd-01.png"}]})
        out_md = os.path.join(self.dir, "KD.md")
        rc, out, err = call_main(build_kd_pdf.main, [self.html, "--manifest", self.man, "--write-md", out_md])
        self.assertEqual(0, rc, out + err)
        self.assertIn("<img>: 1 | <figure>: 1", out)
        self.assertTrue(os.path.isfile(self.html))
        with open(out_md, encoding="utf-8") as fh:
            self.assertIn("## Adım", fh.read())
        # başlık manifest'ten alınır (--title verilmedi)
        with open(self.html, encoding="utf-8") as fh:
            self.assertIn("Kılavuz", fh.read())

    def test_eksik_aciklama_cikis_1(self):
        self._yaz({"steps": [{"heading": "Metinsiz", "img": "kd-01.png"}]})
        rc, out, _ = call_main(build_kd_pdf.main, [self.html, "--manifest", self.man])
        self.assertEqual(1, rc)
        self.assertIn("açıklaması yazılmamış: Metinsiz", out)

    def test_eksik_gorsel_cikis_1(self):
        self._yaz({"steps": [{"heading": "Adım", "text": "x", "img": "yok.png"}]})
        rc, out, _ = call_main(build_kd_pdf.main, [self.html, "--manifest", self.man])
        self.assertEqual(1, rc)
        self.assertIn("görsel dosyası yok: screenshots/yok.png", out)

    def test_bozuk_manifest_cikis_2(self):
        with open(self.man, "w", encoding="utf-8") as fh:
            fh.write("{bozuk")
        rc, _, err = call_main(build_kd_pdf.main, [self.html, "--manifest", self.man])
        self.assertEqual(2, rc)
        self.assertIn("okunamadı", err)

    def test_sema_hatasi_cikis_2(self):
        self._yaz({"steps": []})
        rc, _, err = call_main(build_kd_pdf.main, [self.html, "--manifest", self.man])
        self.assertEqual(2, rc)
        self.assertIn("'steps' boş olmayan", err)

    def test_iki_bicim_birlikte_reddedilir(self):
        self._yaz({"steps": [{"heading": "H", "text": "x"}]})
        md = os.path.join(self.dir, "KD-kaynak.md")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# x\n")
        rc, _, err = call_main(build_kd_pdf.main, [md, self.html, "--manifest", self.man])
        self.assertEqual(2, rc)
        self.assertIn("biçim A ve B ayrıdır", err)

    def test_bicim_verilmezse_reddedilir(self):
        rc, _, err = call_main(build_kd_pdf.main, [self.html])
        self.assertEqual(2, rc)
        self.assertIn("biçim B", err)

    def test_write_md_manifestsiz_reddedilir(self):
        md = os.path.join(self.dir, "KD-kaynak.md")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# x\n")
        mp = os.path.join(self.dir, "map.json")
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        rc, _, err = call_main(build_kd_pdf.main, [md, self.html, "--map", mp, "--write-md", md])
        self.assertEqual(2, rc)
        self.assertIn("--write-md yalnız --manifest", err)

    def test_write_clean_manifestle_reddedilir(self):
        self._yaz({"steps": [{"heading": "H", "text": "x"}]})
        rc, _, err = call_main(build_kd_pdf.main, [self.html, "--manifest", self.man, "--write-clean"])
        self.assertEqual(2, rc)
        self.assertIn("--write-clean biçim A içindir", err)



if __name__ == "__main__":
    unittest.main()
