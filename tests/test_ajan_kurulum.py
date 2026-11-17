# -*- coding: utf-8 -*-
"""ajan_kurulum.py — şablonun özel aXet ajanlarını kullanıcı ajan dizinine kurma / güncelleme / kaldırma.

Ölçülen motor davranışı (aXet.code 1.5.1): kullanıcı ajanları `$AXET_AGENTS_DIR` ya da
`<XDG_CONFIG_HOME|~/.config>/axet-code/agents` dizininden okunur. Testler gerçek kullanıcı dizinine dokunmaz:
her test geçici bir hedef dizin ve geçici kaynak verir.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

sys.path.insert(0, str(AXET_HOME / "scripts"))
import ajan_kurulum as ak  # noqa: E402

ORNEK = """---
description: deneme ajanı
mode: subagent
---

Önce {{AXET_KLON}}/skills-sap/sap-dev/references/role-briefs.md dosyasını oku.
"""


class _Gecici(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        kok = Path(self._td.name)
        self.kaynak = kok / "kaynak"
        self.hedef = kok / "hedef"
        self.kaynak.mkdir()
        (self.kaynak / "sap-deneme.md").write_text(ORNEK, encoding="utf-8")

    def tearDown(self):
        self._td.cleanup()

    def plan(self, **kw):
        return ak.planla(kaynak=self.kaynak, hedef_dizin=self.hedef, **kw)


class IsleTest(unittest.TestCase):
    def test_yer_tutucu_ve_isaret(self):
        cikti = ak.isle("sap-deneme.md", ORNEK)
        self.assertNotIn("{{AXET_KLON}}", cikti)
        self.assertIn(ak.klon_yolu() + "/skills-sap/sap-dev/references/role-briefs.md", cikti)
        self.assertTrue(ak.bizim_mi(cikti))
        # frontmatter bozulmadı: ilk satır '---', işaret frontmatter'ın DIŞINDA (gövdenin başında)
        self.assertTrue(cikti.startswith("---\ndescription: deneme ajanı\nmode: subagent\n---\n"))
        govde = cikti.split("\n---\n", 1)[1]
        self.assertTrue(govde.lstrip("\n").startswith(ak.İŞARET))

    def test_frontmattersiz_reddedilir(self):
        with self.assertRaises(ValueError):
            ak.isle("x.md", "frontmatter yok\n")

    def test_isaretsiz_metin_bizim_degil(self):
        self.assertFalse(ak.bizim_mi(ORNEK))


class PlanTest(_Gecici):
    def test_ilk_kurulum_ve_ikinci_kosu_degisiklik_yok(self):
        plan = self.plan(sap=True)
        self.assertEqual([e.tur for e in plan], ["yaz"])
        self.assertEqual(ak.uygula(plan), [])
        ikinci = self.plan(sap=True)
        self.assertEqual([e.tur for e in ikinci], ["ayni"])
        self.assertFalse(ak.degisiklik_var(ikinci))

    def test_kaynak_degisince_guncellenir(self):
        ak.uygula(self.plan(sap=True))
        (self.kaynak / "sap-deneme.md").write_text(ORNEK + "\nYeni satır.\n", encoding="utf-8")
        plan = self.plan(sap=True)
        self.assertEqual([e.tur for e in plan], ["guncelle"])
        ak.uygula(plan)
        self.assertIn("Yeni satır.", (self.hedef / "sap-deneme.md").read_text(encoding="utf-8"))

    def test_kullanici_dosyasina_dokunulmaz(self):
        self.hedef.mkdir()
        kullanici = self.hedef / "sap-deneme.md"
        kullanici.write_text("---\ndescription: benim\n---\nbenim ajanım\n", encoding="utf-8")
        plan = self.plan(sap=True)
        self.assertEqual([e.tur for e in plan], ["cakisma"])
        ak.uygula(plan)
        self.assertEqual(kullanici.read_text(encoding="utf-8"), "---\ndescription: benim\n---\nbenim ajanım\n")
        # kaldırma da kullanıcı dosyasını silmez
        ak.uygula(self.plan(sap=True, kaldir=True))
        self.assertTrue(kullanici.exists())

    def test_sap_kapali_ya_da_kaldir_yalniz_bizimkini_siler(self):
        ak.uygula(self.plan(sap=True))
        baska = self.hedef / "kendi-ajanim.md"
        baska.write_text("---\ndescription: x\n---\ny\n", encoding="utf-8")
        for kw in ({"sap": False}, {"sap": True, "kaldir": True}):
            ak.uygula(self.plan(sap=True))
            plan = self.plan(**kw)
            self.assertEqual([(e.tur, e.hedef.name) for e in plan], [("sil", "sap-deneme.md")], kw)
            ak.uygula(plan)
            self.assertFalse((self.hedef / "sap-deneme.md").exists())
            self.assertTrue(baska.exists())

    def test_emekli_ajan_kaldirilir(self):
        ak.uygula(self.plan(sap=True))
        (self.kaynak / "sap-deneme.md").unlink()
        plan = self.plan(sap=True)
        self.assertEqual([e.tur for e in plan], ["sil"])

    def test_hedef_dizin_yoksa_plan_hata_vermez(self):
        self.assertEqual([e.tur for e in self.plan(sap=False)], [])

    def test_kaynak_klasoru_yoksa_kurulu_ajan_silinmez(self):
        """Bug gate LOW-4: kısmi %guncelle'de `agents/` yoksa kurulu işaretli ajanlar 'emekli' sayılmaz."""
        ak.uygula(self.plan(sap=True))
        (self.kaynak / "sap-deneme.md").unlink()
        self.kaynak.rmdir()
        self.assertEqual([], self.plan(sap=True))
        # kaldırma (SAP kapalı) kaynak klasöründen bağımsızdır: işaretli kopya yine silinir
        self.assertEqual(["sil"], [e.tur for e in self.plan(sap=False)])


class AjanDiziniTest(unittest.TestCase):
    def test_axet_agents_dir_onceliklidir(self):
        with mock.patch.dict(os.environ, {"AXET_AGENTS_DIR": "C:/x/ajanlar", "XDG_CONFIG_HOME": "C:/y"}):
            self.assertEqual(ak.ajan_dizini(), Path("C:/x/ajanlar"))

    def test_xdg_tabani(self):
        env = {k: v for k, v in os.environ.items() if k != "AXET_AGENTS_DIR"}
        env["XDG_CONFIG_HOME"] = "C:/y"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(ak.ajan_dizini(), Path("C:/y") / "axet-code" / "agents")


class SablonAjanlariTest(unittest.TestCase):
    """Depodaki gerçek `agents/sap-*.md` tanımları: frontmatter sözleşmesi + yönlendirdikleri dosyalar var mı."""

    AJANLAR = sorted((AXET_HOME / "agents").glob("sap-*.md"))
    ZORUNLU = {"sap-arastirma.md", "sap-backend.md", "sap-ui5.md", "sap-inceleme.md", "sap-gelistirme.md"}

    def _fm(self, metin: str) -> str:
        return metin.split("\n---\n", 1)[0]

    def test_beklenen_ajanlar_var(self):
        self.assertEqual({p.name for p in self.AJANLAR}, self.ZORUNLU)

    def test_frontmatter_ve_govde(self):
        for p in self.AJANLAR:
            metin = p.read_text(encoding="utf-8").replace("\r\n", "\n")
            with self.subTest(ajan=p.name):
                fm = self._fm(metin)
                self.assertTrue(metin.startswith("---\n"))
                m = re.search(r"^description: (.+)$", fm, re.M)
                self.assertIsNotNone(m, "description zorunlu")
                self.assertLessEqual(len(m.group(1)), 1024)
                self.assertRegex(fm, r"(?m)^mode: (primary|subagent|all)$")
                govde = metin.split("\n---\n", 1)[1].strip()
                self.assertTrue(govde, "gövde (prompt) zorunlu — motor boş gövdeyi reddeder (ölçüldü)")
                ak.isle(p.name, metin)  # kurulabilir

    def test_salt_okur_roller_yazamaz(self):
        for ad in ("sap-arastirma.md", "sap-inceleme.md"):
            fm = self._fm((AXET_HOME / "agents" / ad).read_text(encoding="utf-8").replace("\r\n", "\n"))
            with self.subTest(ajan=ad):
                self.assertRegex(fm, r"(?m)^disallowedTools: \[edit, multiedit, write\]$")

    def test_yonlendirilen_dosyalar_var(self):
        for p in self.AJANLAR:
            for yol in re.findall(r"\{\{AXET_KLON\}\}/([^\s`]+)", p.read_text(encoding="utf-8")):
                with self.subTest(ajan=p.name, yol=yol):
                    self.assertTrue((AXET_HOME / yol.rstrip(".,;:")).exists(), yol)

    def test_yonlendirilen_bolum_basliklari_var(self):
        brifler = (AXET_HOME / "skills-sap/sap-dev/references/role-briefs.md").read_text(encoding="utf-8")
        for baslik in ("## (a) SAP araştırma", "## (b) Backend geliştirme alt görevi",
                       "## (c) Ön yüz (UI5) geliştirme alt görevi"):
            with self.subTest(baslik=baslik):
                self.assertIn(baslik, brifler)

    def test_gelistirme_ajani_fazlari(self):
        fm = self._fm((AXET_HOME / "agents" / "sap-gelistirme.md").read_text(encoding="utf-8").replace("\r\n", "\n"))
        self.assertRegex(fm, r"(?m)^mode: primary$")
        self.assertRegex(fm, r"(?m)^extends: coder$")
        adlar = re.findall(r"(?m)^  - name: (\S+)$", fm)
        self.assertEqual(adlar, ["intake", "uygulama"])
        self.assertIn("INTAKE: devam", fm)  # devam mesajı yeniden sınıflanmaz (ölçüldü 2026-11-17)
        self.assertNotIn("gate: approve", fm)  # run kipinde arayüz yok; TUI ölçülmeden açılmaz


class DoctorAjanTest(unittest.TestCase):
    """doctor.check_ajanlar: eksik → WARN, kurulu → PASS, kullanıcı çakışması → WARN, SAP kapalı → INFO."""

    def setUp(self):
        import doctor
        self.doctor = doctor
        self._td = tempfile.TemporaryDirectory()
        self.dizin = Path(self._td.name) / "ajanlar"
        self._env = mock.patch.dict(os.environ, {"AXET_AGENTS_DIR": str(self.dizin)})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    def durum(self, sap: bool) -> list[tuple[str, str]]:
        self.doctor.results.clear()
        self.doctor.check_ajanlar(sap)
        return [(s, m) for s, m in self.doctor.results if "ajan" in m]

    def test_eksik_kurulu_cakisma(self):
        (s, m), = self.durum(True)
        self.assertEqual("WARN", s, m)
        self.assertIn("%guncelle", m)
        ak.uygula(ak.planla(sap=True))
        (s, m), = self.durum(True)
        self.assertEqual("PASS", s, m)
        (self.dizin / "sap-ui5.md").write_text("---\ndescription: benim\nmode: subagent\n---\nx\n", encoding="utf-8")
        (s, m), = self.durum(True)
        self.assertEqual("WARN", s, m)
        self.assertIn("KULLANICI ajanı", m)

    def test_sap_kapali_info(self):
        (s, _), = self.durum(False)
        self.assertEqual("INFO", s)

    def test_kaynak_klasoru_yoksa_olculemedi_warn(self):
        """R3 bug gate F3: şablonun agents/ klasörü yoksa doctor susmaz, ÖLÇÜLEMEDİ der."""
        with mock.patch.object(ak, "KAYNAK_DIZIN", Path(self._td.name) / "yok"):
            durum = self.durum(True)
        self.assertEqual(["WARN"], [s for s, _ in durum], durum)
        self.assertIn("ÖLÇÜLEMEDİ", durum[0][1])

    def test_emekli_ajan_warn(self):
        """Bug gate LOW-3: şablonda artık olmayan işaretli ajan kuruluysa PASS değil WARN."""
        ak.uygula(ak.planla(sap=True))
        emekli = self.dizin / "sap-eski.md"
        emekli.write_text((self.dizin / "sap-ui5.md").read_text(encoding="utf-8"), encoding="utf-8")
        durum = self.durum(True)
        self.assertEqual(["WARN"], [s for s, _ in durum], durum)
        self.assertIn("sap-eski.md", durum[0][1])


class InstallAjanAdimiTest(GeciciTest):
    """Uçtan uca: gerçek install.py süreci (sahte klon, XDG geçici) ajanları kurar, SAP kapanınca kaldırır,
    `--paketler` (her %guncelle) silinen/eskiyen ajanı yeniden eşitler."""

    def setUp(self) -> None:
        super().setUp()
        self.klon = self.tmp / "klon"
        for rel in ("scripts/install.py", "scripts/ajan_kurulum.py", "config/permissions.json", "core/00-temel.md",
                    "core/sap/00-sap.md", "memory/MEMORY.md"):
            hedef = self.klon / rel
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(AXET_HOME / rel, hedef)
        shutil.copytree(AXET_HOME / "agents", self.klon / "agents")
        (self.klon / "skills").mkdir()
        (self.klon / "skills-sap").mkdir()
        self.ajanlar = self.xdg / "axet-code" / "agents"

    def install(self, *args: str):
        return self.calistir(self.klon / "scripts" / "install.py", *args)

    def kurulu(self) -> set[str]:
        return {p.name for p in self.ajanlar.glob("sap-*.md")} if self.ajanlar.is_dir() else set()

    def test_sap_ac_kapa_ve_paketler_esitler(self):
        beklenen = {p.name for p in (AXET_HOME / "agents").glob("sap-*.md")}
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("AJANLAR: TAMAM", r.stdout, self.cikti(r))
        self.assertEqual(beklenen, self.kurulu())
        govde = (self.ajanlar / "sap-backend.md").read_text(encoding="utf-8")
        self.assertNotIn("{{AXET_KLON}}", govde)
        self.assertIn(self.klon.resolve().as_posix() + "/skills-sap/", govde)
        # --paketler: eksilen ajan yeniden kurulur (güncelleme yolu)
        (self.ajanlar / "sap-ui5.md").unlink()
        r = self.install("--paketler")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("AJANLAR: TAMAM", r.stdout, self.cikti(r))
        self.assertEqual(beklenen, self.kurulu())
        # dry-run yazmaz
        (self.ajanlar / "sap-ui5.md").unlink()
        r = self.install("--sap", "--dry-run")
        self.assertIn("dry-run: yazılmadı", r.stdout, self.cikti(r))
        self.assertNotIn("sap-ui5.md", self.kurulu())
        self.install("--sap")
        # kullanıcı ajanı korunur; --no-sap yalnız şablonunkileri kaldırır
        kendi = self.ajanlar / "kendi.md"
        kendi.write_text("---\ndescription: k\nmode: subagent\n---\nk\n", encoding="utf-8")
        r = self.install("--no-sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual(set(), self.kurulu())
        self.assertTrue(kendi.exists())
        # SAP kapalıyken --paketler ajan kurmaz
        r = self.install("--paketler")
        self.assertEqual(set(), self.kurulu(), self.cikti(r))

    def test_uninstall_kaldirir(self):
        self.install("--sap")
        r = self.install("--uninstall")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual(set(), self.kurulu())


if __name__ == "__main__":
    unittest.main()
