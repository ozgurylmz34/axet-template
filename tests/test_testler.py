# -*- coding: utf-8 -*-
"""testler.py (`%testler`, Z162) — güncellemeden AYRI, kullanıcı isteğiyle test takımı koşumu.

Sahte bir klon kurulur: `guncelle/harita.json` (iki takım + kapsanan bir `-k` eşi), kök takımı
(`tests/run_tests.py` → `scripts/ornek.py`'yi sınayan tek test) ve bir skill takımı. Her takım
koşunca bir İZ dosyası yazar ⇒ "hangi takım gerçekten koştu" çıktıdan değil diskten okunur.

Kapanış ölçütü ② (IS-LISTESI Z162): mutasyonla kırılan BİLİNEN bir testte araç kırmızı testin
adını, kaynak dosyayı + yayın kalemini ve dört giderme seçeneğini gösterir; kontrol grubu aynı
klonun mutasyonsuz hâlidir (yeşil, borç kapanır).

KAPSAM — bakılmayan: gerçek template takımlarının içeriği (CI'nın işi) · BelowNormal önceliğinin
işletim sistemine gerçekten uygulandığı (yalnız bayrağın üretildiği ölçülür) · `--hepsi`'nin
gerçek klondaki süresi.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from _helpers import GeciciTest  # önce: scripts/ yolunu ekler
import doctor
import testler

KOK_RUNNER = '''import pathlib, sys, unittest
kok = pathlib.Path(__file__).resolve().parent.parent
with open(kok / "IZ.txt", "a", encoding="utf-8") as fh:
    fh.write("kok " + " ".join(sys.argv[1:]) + "\\n")
sys.path.insert(0, str(kok / "scripts"))
s = unittest.defaultTestLoader.discover(str(kok / "tests"), top_level_dir=str(kok / "tests"))
r = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(s)
print(f"SONUÇ: {r.testsRun} test · {len(r.failures) + len(r.errors)} failure")
sys.exit(0 if r.wasSuccessful() else 1)
'''
KOK_TEST = '''import unittest
import ornek

class OrnekTest(unittest.TestCase):
    def test_topla(self):
        self.assertEqual(ornek.topla(2, 2), 4)
'''
SKILL_RUNNER = '''import pathlib, sys
kok = pathlib.Path(__file__).resolve().parents[3]
with open(kok / "IZ.txt", "a", encoding="utf-8") as fh:
    fh.write("x\\n")
print("SONUÇ: 1 test · 0 failure")
'''
HARITA = {"surum": 1, "siniflar": [
    {"sinif": "bakim-script-kok", "test": [
        {"komut": "python tests/run_tests.py", "cwd": ".", "on_kosul": None},
        {"komut": "python tests/run_tests.py -k ornek", "cwd": ".", "on_kosul": None}]},
    {"sinif": "skill-x", "test": [
        {"komut": "python skills/x/tests/run_tests.py", "cwd": ".", "on_kosul": None}]},
]}
PLAN = {"yeni_etiket": "v9.9.9", "kalemler": [
    {"id": "9.9.9-01", "dosyalar": [{"yol": "scripts/ornek.py", "vaka": "V4t"}]}]}


class TestlerTemel(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.k = self.tmp / "klon"
        for yol, icerik in {
            "guncelle/harita.json": json.dumps(HARITA, ensure_ascii=False),
            "tests/run_tests.py": KOK_RUNNER,
            "tests/test_ornek.py": KOK_TEST,
            "scripts/ornek.py": "def topla(a, b):\n    return a + b\n",
            "skills/x/tests/run_tests.py": SKILL_RUNNER,
        }.items():
            h = self.k / yol
            h.parent.mkdir(parents=True, exist_ok=True)
            h.write_text(icerik, encoding="utf-8")
        self.d = self.k / ".axet-guncelleme"

    def kos(self, *args: str) -> subprocess.CompletedProcess:
        return self.calistir("testler.py", "--klon", str(self.k), *args, timeout=600)

    def borc_yaz(self, takimlar: list[dict]) -> None:
        self.d.mkdir(parents=True, exist_ok=True)
        (self.d / "test-borcu.json").write_text(json.dumps(
            {"surum": 1, "ilk_kayit": "2026-01-01T00:00:00+03:00", "etiket": "v9.9.9",
             "neden": "test", "takimlar": takimlar}, ensure_ascii=False), encoding="utf-8")
        (self.d / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")

    def kok_borcu(self) -> None:
        self.borc_yaz([{"ad": "kok", "komut": "python tests/run_tests.py", "cwd": ".",
                        "kaynak_yollar": ["scripts/ornek.py"]}])

    def iz(self) -> list[str]:
        h = self.k / "IZ.txt"
        return h.read_text(encoding="utf-8").split() if h.exists() else []

    def borc(self) -> dict | None:
        h = self.d / "test-borcu.json"
        return json.loads(h.read_text(encoding="utf-8")) if h.exists() else None


class KullanimTest(TestlerTemel):
    def test_liste_KOSMAZ_takimlari_ve_borcu_gosterir(self):
        self.kok_borcu()
        r = self.kos("--liste")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        for ad in ("kok", "kok:ornek", "x"):
            self.assertIn(ad, r.stdout)
        satir = [s for s in r.stdout.splitlines() if s.startswith("kok ")][0]
        self.assertIn("evet", satir)
        self.assertIn("Borç: 1 takım", r.stdout)
        self.assertEqual(self.iz(), [], "--liste takım KOŞTU")

    def test_borc_yokken_varsayilan_hicbir_sey_KOSMAZ_0(self):
        r = self.kos()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("TEST BORCU: yok", r.stdout)
        self.assertEqual(self.iz(), [])
        self.assertFalse((self.d / testler.RAPOR_MD).exists())

    def test_bilinmeyen_takim_2_ve_hicbir_sey_KOSMAZ(self):
        r = self.kos("--takim", "yok-boyle")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("bilinmeyen takım", r.stderr)
        self.assertEqual(self.iz(), [])

    def test_hepsi_ile_takim_birlikte_2(self):
        self.assertEqual(self.kos("--hepsi", "--takim", "x").returncode, 2)

    def test_takim_yalniz_SECILENI_kosar(self):
        r = self.kos("--takim", "x")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.iz(), ["x"])
        self.assertIn("[1/1] x", r.stdout)
        self.assertIn("Tahmini süre", r.stdout)

    def test_hepsi_kapsanan_filtreli_esi_AYIKLAR(self):
        r = self.kos("--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(sorted(self.iz()), ["kok", "x"], "kok:ornek filtresiz eşi varken koşmamalı")
        sureler = json.loads((self.d / testler.SURE_DOSYASI).read_text(encoding="utf-8"))
        self.assertIn(".::python tests/run_tests.py", sureler)


class BorcOdemeTest(TestlerTemel):
    def test_KONTROL_yesil_borc_KAPANIR_ve_rapor_yazilir(self):
        self.kok_borcu()
        r = self.kos()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.iz(), ["kok"], "yalnız borçtaki takım koşmalı")
        self.assertIsNone(self.borc(), "yeşil koşumdan sonra borç silinmeliydi")
        rapor = (self.d / testler.RAPOR_MD).read_text(encoding="utf-8")
        self.assertIn("kapandı (borç yok)", rapor)
        self.assertNotIn("## Giderme", rapor)

    def test_MUTASYON_kirmizi_kaynak_kalem_ve_DORT_secenek(self):
        """Kapanış ölçütü ②: bilinen test (`test_topla`) mutasyonla kırılır."""
        self.kok_borcu()
        (self.k / "scripts" / "ornek.py").write_text("def topla(a, b):\n    return a - b\n",
                                                    encoding="utf-8")
        r = self.kos()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        c = r.stdout
        self.assertIn("kırmızı test: test_topla (test_ornek.OrnekTest.test_topla)", c)
        self.assertIn("kaynak: `scripts/ornek.py` (yayın kalemi 9.9.9-01)", c)
        for isaret, parca in (("①", "geri-al scripts/ornek.py"),
                              ("②", "checkout v9.9.9 -- scripts/ornek.py"),
                              ("③", "kur.cmd\" -Sifirla"), ("④", "%hata-bildir")):
            satir = [s for s in c.splitlines() if s.strip().startswith(isaret)]
            self.assertEqual(len(satir), 1, f"{isaret} satırı yok:\n{c}")
            self.assertIn(parca, satir[0])
        self.assertIn("--takim kok", c)
        # araç DÜZELTMEZ: dosya mutasyonlu kalır, borç sürer
        self.assertIn("a - b", (self.k / "scripts" / "ornek.py").read_text(encoding="utf-8"))
        self.assertEqual([t["komut"] for t in self.borc()["takimlar"]], ["python tests/run_tests.py"])
        self.assertEqual(self.borc()["ilk_kayit"], "2026-01-01T00:00:00+03:00")
        self.assertIn("## Giderme", (self.d / testler.RAPOR_MD).read_text(encoding="utf-8"))

    def test_betik_yoksa_OLCULEMEDI_1_ve_borcta_KALIR(self):
        self.borc_yaz([{"ad": "y", "komut": "python skills/y/tests/run_tests.py", "cwd": ".",
                        "kaynak_yollar": []}])
        r = self.kos()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("ÖLÇÜLEMEDİ", r.stdout)
        self.assertEqual(len(self.borc()["takimlar"]), 1)

    def test_bozuk_borc_kaydi_1_hicbir_sey_KOSMAZ(self):
        self.d.mkdir(parents=True)
        (self.d / "test-borcu.json").write_text("{bozuk", encoding="utf-8")
        r = self.kos()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("ÖLÇÜLEMEDİ", self.cikti(r))
        self.assertEqual(self.iz(), [])


class BozukBorcTest(TestlerTemel):
    def _bozuk(self) -> None:
        self.d.mkdir(parents=True)
        (self.d / "test-borcu.json").write_text("{bozuk", encoding="utf-8")

    def test_tek_takim_yesili_bozuk_kaydi_KAPATMAZ(self):
        self._bozuk()
        r = self.kos("--takim", "x")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((self.d / "test-borcu.json").read_text(encoding="utf-8"), "{bozuk")
        self.assertIn("ÖLÇÜLEMEDİ — borç kaydı okunamadı", r.stdout)

    def test_KONTROL_hepsi_yesilse_bozuk_kayit_KAPANIR(self):
        self._bozuk()
        r = self.kos("--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.d / "test-borcu.json").exists())
        self.assertIn("kapandı (borç yok)", r.stdout)


class BirimTest(TestlerTemel):
    def test_borcu_guncelle_filtresiz_es_gecince_filtreli_DUSER(self):
        borc = {"surum": 1, "takimlar": [
            {"ad": "kok:ornek", "komut": "python tests/run_tests.py -k ornek", "cwd": ".",
             "kaynak_yollar": []},
            {"ad": "x", "komut": "python skills/x/tests/run_tests.py", "cwd": ".", "kaynak_yollar": []}]}
        gecen = [{"ad": "kok", "komut": "python tests/run_tests.py", "cwd": ".", "cikis": 0}]
        yeni = testler.borcu_guncelle(self.d, borc, gecen, hepsi=False)
        self.assertEqual([t["ad"] for t in yeni["takimlar"]], ["x"])

    def test_zaman_asimi_OLCULEMEDI_cokmez(self):
        (self.k / "uyu.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        with mock.patch.object(testler, "TAKIM_ZAMAN_ASIMI", 1):
            s = testler.takim_kos(self.k, {"ad": "u", "komut": "python uyu.py", "cwd": "."},
                                  dict(os.environ))
        self.assertIsNone(s["cikis"])
        self.assertIn("zaman aşımı", s["not"])

    def test_zaman_asimi_CI_en_uzun_kok_kosumundan_buyuk(self):
        """Taşındı (`ZamanAsimiTest`, Z162): CI'da gözlenen en uzun kök koşumu 2411 sn."""
        self.assertGreater(testler.TAKIM_ZAMAN_ASIMI, 2411)

    def test_Z54_modul_komutu_KOSAR_ve_dizin_yoksa_OLCULEMEDI(self):
        """Taşındı (Z54 test_2): `python -m unittest discover -s X` biçimi betik yolu sanılmaz."""
        t = self.k / "mt"
        t.mkdir()
        (t / "test_m.py").write_text("import unittest\n\nclass T(unittest.TestCase):\n"
                                    "    def test_ok(self):\n        pass\n", encoding="utf-8")
        takim = {"ad": "m", "komut": "python -m unittest discover -s mt -t mt", "cwd": "."}
        s = testler.takim_kos(self.k, takim, dict(os.environ))
        self.assertEqual(s["cikis"], 0, s)
        takim["komut"] = "python -m unittest discover -s yok -t yok"
        s = testler.takim_kos(self.k, takim, dict(os.environ))
        self.assertIsNone(s["cikis"])
        self.assertIn("yok yok", s["not"])

    def test_oncelik_bayragi_dusuk(self):
        b = testler._oncelik_bayraklari()
        if os.name == "nt":
            self.assertEqual(b["creationflags"], subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            self.assertIn("preexec_fn", b)

    def test_kok_sure_tahmini_paralel_ise_bolunur(self):
        (self.k / "tests" / "parca-agirlik.json").write_text(
            json.dumps({"kume_sn": {"a": 100, "b": 100, "c": 100, "d": 700}}), encoding="utf-8")
        with mock.patch.object(testler.os, "cpu_count", return_value=4):
            sn, kaynak = testler.sure_tahmini({"ad": "kok", "cwd": ".", "komut": "x"}, {}, self.k)
        self.assertEqual(sn, 700.0, "en uzun kümeden kısa olamaz")
        with mock.patch.object(testler.os, "cpu_count", return_value=1):
            sn, _ = testler.sure_tahmini({"ad": "kok", "cwd": ".", "komut": "x"}, {}, self.k)
        self.assertEqual(sn, 1000.0)
        self.assertIn("paralel", kaynak)


class DoctorBorcTest(TestlerTemel):
    def _sonuclar(self) -> list[tuple[str, str]]:
        doctor.results.clear()
        doctor.check_test_borcu(self.k)
        return list(doctor.results)

    def test_borc_varken_WARN(self):
        self.kok_borcu()
        r = self._sonuclar()
        self.assertEqual(len(r), 1, r)
        self.assertEqual(r[0][0], "WARN")
        self.assertIn("test borcu: 1 takım — %testler (kok", r[0][1])

    def test_KONTROL_borc_yokken_SATIR_YOK(self):
        self.assertEqual(self._sonuclar(), [])

    def test_bozuk_kayit_WARN_OLCULEMEDI(self):
        self.d.mkdir(parents=True)
        (self.d / "test-borcu.json").write_text("{bozuk", encoding="utf-8")
        r = self._sonuclar()
        self.assertEqual(r[0][0], "WARN")
        self.assertIn("ÖLÇÜLEMEDİ", r[0][1])

    def test_kablolama_doctor_main_cagirir_skills_kipinde_CAGIRMAZ(self):
        """kod ≠ kablolama: `main` gerçekten çağırıyor mu (yalnız tam kipte)."""
        for argv, beklenen in ((["doctor.py"], 1), (["doctor.py", "--skills"], 0)):
            doctor.results.clear()
            with mock.patch.object(doctor, "check_test_borcu") as casus, \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                try:
                    doctor.main()
                except SystemExit:
                    pass
            self.assertEqual(casus.call_count, beklenen, argv)


if __name__ == "__main__":
    unittest.main()
