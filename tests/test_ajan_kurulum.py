# -*- coding: utf-8 -*-
"""ajan_kurulum.py — şablonun özel aXet ajanlarını kullanıcı ajan dizinine kurma / güncelleme / kaldırma.

Ölçülen motor davranışı (aXet.code 1.5.1, Windows, `axet-code dirs` + `agent list`, kontrol gruplu 2026-11-17):
kullanıcı ajanları `$AXET_AGENTS_DIR` → `$XDG_CONFIG_HOME/axet-code/agents` → (XDG yoksa, Windows)
`%LOCALAPPDATA%\\axet-code\\agents` dizininden okunur. ⚠ Bu dosyanın v0.5.22 sürümündeki "`<XDG_CONFIG_HOME|~/.config>`"
cümlesi YANLIŞTI: yalnız XDG tanımlı lab'da ölçülmüştü; XDG yokken motor `~/.config/axet-code/agents`'ı OKUMAZ.
Windows dışı (XDG yok) ölçülmedi — kod `~/.config` varsayar.
Testler gerçek kullanıcı dizinine dokunmaz: her test geçici hedef/kaynak verir; ayrıca modül düzeyinde ev dizini
(`_ev_dizini`, USERPROFILE/HOME/HOMEDRIVE/HOMEPATH) ve LOCALAPPDATA geçici dizine yamalanır (setUpModule).
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


_MODUL_YAMALARI: list = []


def setUpModule():
    """Süreç içi testler gerçek ev dizinine / %LOCALAPPDATA%'ya ULAŞAMAZ — yalıtım test edilen koda (XDG/AXET_AGENTS_DIR
    korumasına) bağlı kalmasın. Ölçülmüş vaka (2026-11-17): o korumayı kaldıran bir mutant, gerçek
    `~/.config/axet-code/agents`'taki işaretli kopyaları sildi."""
    td = tempfile.TemporaryDirectory()
    _MODUL_YAMALARI.append(td)
    kok = Path(td.name)
    ev = kok / "ev"
    # Path.home() de yamalı env'den çözülsün: `_ev_dizini` yerine doğrudan Path.home() kullanan bir gerileme/mutant
    # gerçek ev dizinine ulaşmasın (bug-gate R2 F3: yalnız `_ev_dizini` yamalıyken M23 sahte evdeki kopyaları sildi).
    ortam = {"LOCALAPPDATA": str(kok / "yerel"), "USERPROFILE": str(ev), "HOME": str(ev),
             "HOMEDRIVE": ev.drive or "", "HOMEPATH": str(ev)[len(ev.drive):]}
    for yama in (mock.patch.object(ak, "_ev_dizini", return_value=ev),
                 mock.patch.dict(os.environ, ortam)):
        yama.start()
        _MODUL_YAMALARI.append(yama)


def tearDownModule():
    for nesne in reversed(_MODUL_YAMALARI):
        (nesne.cleanup if isinstance(nesne, tempfile.TemporaryDirectory) else nesne.stop)()
    _MODUL_YAMALARI.clear()


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

    def _ortam(self, **ek):
        env = {k: v for k, v in os.environ.items() if k not in ("AXET_AGENTS_DIR", "XDG_CONFIG_HOME", "LOCALAPPDATA")}
        env.update(ek)
        return mock.patch.dict(os.environ, env, clear=True)

    def test_windows_xdg_yoksa_localappdata(self):
        """Ölçüldü (1.5.1, Windows, XDG yok): motor kullanıcı ajanlarını %LOCALAPPDATA%\\axet-code\\agents'tan okur."""
        with self._ortam(LOCALAPPDATA="C:/yerel"), mock.patch.object(ak, "_windows", return_value=True), \
                mock.patch.object(ak, "_ev_dizini", return_value=Path("C:/ev")):
            self.assertEqual(ak.ajan_dizini(), Path("C:/yerel") / "axet-code" / "agents")
            self.assertEqual(ak.eski_ajan_dizini(), Path("C:/ev") / ".config" / "axet-code" / "agents")
        with self._ortam(LOCALAPPDATA="C:/yerel", XDG_CONFIG_HOME="C:/y"), \
                mock.patch.object(ak, "_windows", return_value=True):
            self.assertEqual(ak.ajan_dizini(), Path("C:/y") / "axet-code" / "agents")
            self.assertIsNone(ak.eski_ajan_dizini())  # XDG varken (testler dahil) eski konum temizliği YOK

    def test_windows_disi_xdg_yoksa_config(self):
        with self._ortam(LOCALAPPDATA="C:/yerel"), mock.patch.object(ak, "_windows", return_value=False), \
                mock.patch.object(ak, "_ev_dizini", return_value=Path("C:/ev")):
            self.assertEqual(ak.ajan_dizini(), Path("C:/ev") / ".config" / "axet-code" / "agents")
            self.assertIsNone(ak.eski_ajan_dizini())

    def test_eski_konumdaki_isaretli_kopya_kaldirilir_kullanicininki_kalir(self):
        with tempfile.TemporaryDirectory() as td:
            kok = Path(td)
            eski = kok / "ev" / ".config" / "axet-code" / "agents"
            eski.mkdir(parents=True)
            (eski / "sap-ui5.md").write_text(ak.isle("sap-ui5.md", ORNEK), encoding="utf-8")
            (eski / "sap-emekli.md").write_text(ak.isle("sap-emekli.md", ORNEK), encoding="utf-8")
            (eski / "sap-kendi.md").write_text("---\ndescription: benim\nmode: subagent\n---\nx\n", encoding="utf-8")
            with self._ortam(LOCALAPPDATA=str(kok / "yerel")), mock.patch.object(ak, "_windows", return_value=True), \
                    mock.patch.object(ak, "_ev_dizini", return_value=kok / "ev"):
                plan = ak.planla(sap=True)
                yeni = kok / "yerel" / "axet-code" / "agents"
                self.assertTrue({e.hedef.parent for e in plan if e.tur == "yaz"} == {yeni}, plan)
                self.assertEqual({"sap-ui5.md", "sap-emekli.md"},
                                 {e.hedef.name for e in plan if e.tur == "sil" and e.hedef.parent == eski})
                self.assertEqual([], ak.uygula(plan))
                self.assertEqual({"sap-kendi.md"}, {p.name for p in eski.iterdir()})
                self.assertTrue((yeni / "sap-ui5.md").exists())
                # kaldırma da eski konumu temizler (yeniden işaretli kopya bırakıp dene)
                (eski / "sap-ui5.md").write_text(ak.isle("sap-ui5.md", ORNEK), encoding="utf-8")
                ak.uygula(ak.planla(sap=False))
                self.assertEqual({"sap-kendi.md"}, {p.name for p in eski.iterdir()})
                self.assertEqual([], list(yeni.glob("sap-*.md")))

    def test_axet_agents_dir_varken_eski_konum_temizligi_yok(self):
        """Katalog iddiası (0.5.23-02): AXET_AGENTS_DIR tanımlıysa davranış değişmez — eski konuma dokunulmaz."""
        with self._ortam(LOCALAPPDATA="C:/yerel", AXET_AGENTS_DIR="C:/ozel"), \
                mock.patch.object(ak, "_windows", return_value=True), \
                mock.patch.object(ak, "_ev_dizini", return_value=Path("C:/ev")):
            self.assertEqual(ak.ajan_dizini(), Path("C:/ozel"))
            self.assertIsNone(ak.eski_ajan_dizini())

    def _iki_tur(self, kok: Path, **ortam) -> Path:
        """Windows varsayımıyla iki kez kurar; ikinci tur hiçbir şey silmemeli, ajanlar yerinde kalmalı."""
        with self._ortam(**ortam), mock.patch.object(ak, "_windows", return_value=True), \
                mock.patch.object(ak, "_ev_dizini", return_value=kok / "ev"):
            kaynak = self._kaynak(kok)
            self.assertEqual([], ak.uygula(ak.planla(sap=True, kaynak=kaynak)))
            ikinci = ak.planla(sap=True, kaynak=kaynak)
            self.assertEqual([], [e for e in ikinci if e.tur == "sil"], ikinci)
            ak.uygula(ikinci)
            hedef = ak.ajan_dizini()
            self.assertEqual({"sap-ui5.md"}, {f.name for f in hedef.glob("sap-*.md")})
            return hedef

    def _kaynak(self, kok: Path) -> Path:
        kaynak = kok / "kaynak"
        if not kaynak.is_dir():
            kaynak.mkdir()
            (kaynak / "sap-ui5.md").write_text(ORNEK, encoding="utf-8")
        return kaynak

    def test_windows_localappdata_yoksa_eski_konum_guncel_konumdur(self):
        """Bug-gate R2 F5: LOCALAPPDATA yokken güncel dizin `~/.config/...`'a düşer = eski konum; kurulan ajanlar ikinci
        turda 'eski konumda' diye SİLİNMEMELİ (eşitlik koruması kaldırılınca 5 ajanın 5'i silindi — ölçüldü)."""
        with tempfile.TemporaryDirectory() as td:
            hedef = self._iki_tur(Path(td))
            self.assertEqual(Path(td) / "ev" / ".config" / "axet-code" / "agents", hedef)

    @unittest.skipUnless(os.name == "nt", "junction yalnız Windows")
    def test_junction_ile_ayni_dizin_silinmez(self):
        """Bug-gate R2 F5: `~/.config/axet-code/agents` bir junction ile `%LOCALAPPDATA%/axet-code/agents`'a
        çıkıyorsa iki yol metni farklıdır ama dizin aynıdır — eski konum temizliği güncel ajanları silmemeli."""
        import _winapi
        with tempfile.TemporaryDirectory() as td:
            kok = Path(td)
            gercek = kok / "yerel" / "axet-code" / "agents"
            gercek.mkdir(parents=True)
            bag = kok / "ev" / ".config" / "axet-code" / "agents"
            bag.parent.mkdir(parents=True)
            _winapi.CreateJunction(str(gercek), str(bag))
            try:
                self.assertTrue(ak._ayni_dizin(bag, gercek))
                self._iki_tur(kok, LOCALAPPDATA=str(kok / "yerel"))
            finally:
                os.rmdir(bag)  # önce bağ (hedefe dokunmadan), sonra geçici ağaç

    def test_ayni_dizin_olculemezse_temizlik_yok(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td) / "a", Path(td) / "b"
            a.mkdir()
            b.mkdir()
            self.assertFalse(ak._ayni_dizin(a, b))
            with mock.patch.object(ak.os.path, "samefile", side_effect=OSError("ölçülemedi")):
                self.assertTrue(ak._ayni_dizin(a, b))  # fail-closed: aynı say → silme yok


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

    BELGE_IZNI = {"read_docx": "allow", "read_xlsx": "allow", "read_pdf": "allow"}
    # Alt ajanlar izinli; ana ajan (mode: primary) izinsiz — ölçülen sorun yalnız alt ajanın asılmasıydı, ana ajana allow
    # kullanıcının config'teki read_* kuralını ezebilir (bağımsız inceleme F4, ölçülmedi ⇒ bilinçli dışarıda).
    IZINLI = {"sap-arastirma.md", "sap-backend.md", "sap-ui5.md", "sap-inceleme.md"}

    def _beklenen_izin(self, ad: str) -> dict[str, str]:
        return self.BELGE_IZNI if ad in self.IZINLI else {}

    def _izin_blogu(self, fm: str) -> dict[str, str]:
        """`permission:` bloğu → {araç: karar}. Blok yoksa {} (iki boşluk girintili `araç: karar` satırları)."""
        m = re.search(r"(?m)^permission:\n((?:  \S.*\n?)*)", fm + "\n")
        if not m:
            return {}
        return dict(re.findall(r"(?m)^  ([a-z_]+): (\S+)$", m.group(1)))

    def test_belge_okuma_izni(self):
        """Ölçüldü (1.5.1 `run`): `permission` bloğu yokken özel alt ajanın `read_docx` çağrısı görünmeyen izin sorusunda
        asılı kaldı (3/3, >290 sn); kontrollü deneyde aynı deneme ajanı blokla 41 sn'de okudu. Blok yalnız üç okuma aracını
        açar (bash/yazma yok) ve yalnız alt ajanlarda durur; ana ajan `sap-gelistirme`de blok YOK."""
        self.assertEqual(self.IZINLI | {"sap-gelistirme.md"}, self.ZORUNLU)
        for p in self.AJANLAR:
            fm = self._fm(p.read_text(encoding="utf-8").replace("\r\n", "\n"))
            with self.subTest(ajan=p.name):
                self.assertEqual(self._izin_blogu(fm), self._beklenen_izin(p.name))
                if p.name in self.IZINLI:
                    self.assertRegex(fm, r"(?m)^mode: subagent$")
                else:
                    self.assertNotIn("permission", fm)

    def test_belge_okuma_izni_kurulumda_korunur(self):
        """Kurulum (`planla` → `uygula`; yer tutucu + işaret) frontmatter'daki izin bloğunu düşürmez/bozmaz."""
        with tempfile.TemporaryDirectory() as td:
            hedef = Path(td) / "hedef"
            plan = ak.planla(sap=True, kaynak=AXET_HOME / "agents", hedef_dizin=hedef)
            self.assertEqual(sorted(e.tur for e in plan), ["yaz"] * len(self.ZORUNLU))
            self.assertEqual(ak.uygula(plan), [])
            for ad in sorted(self.ZORUNLU):
                kurulu = (hedef / ad).read_text(encoding="utf-8")
                with self.subTest(ajan=ad):
                    self.assertTrue(ak.bizim_mi(kurulu))
                    self.assertEqual(self._izin_blogu(self._fm(kurulu)), self._beklenen_izin(ad))

    def test_izin_blogu_ayristirici_KONTROL(self):
        """Ayrıştırıcının kendisi: blok yok → {} · fazladan araç görünür (vakum-assertion'a karşı)."""
        self.assertEqual(self._izin_blogu("---\nmode: subagent"), {})
        self.assertEqual(self._izin_blogu("---\npermission:\n  read_docx: allow\n  bash: allow\nmode: subagent"),
                         {"read_docx": "allow", "bash": "allow"})

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


class MotorSurumTest(unittest.TestCase):
    """Asgari motor sürümü: `axet-code -v` çıktısı çözülür, 1.5.1'den eski motor 'eski' sayılır, çözülemeyen sürüm
    eski SAYILMAZ (ölçülemedi ≠ eski)."""

    def test_surum_coz(self):
        self.assertEqual((1, 5, 1), ak.surum_coz("axet-code version 1.5.1"))
        self.assertEqual((1, 4, 0), ak.surum_coz("axet-code version v1.4.0\n"))
        self.assertEqual((1, 10, 2), ak.surum_coz("1.10.2-beta"))
        # bug gate F7: çıktıda başka bir sürüm geçse de `version` sözcüğüne bağlı olan alınır
        self.assertEqual((1, 4, 0), ak.surum_coz("update available: 1.6.0\naxet-code version 1.4.0"))
        for bos in (None, "", "axet-code version", "sürüm bilinmiyor"):
            self.assertIsNone(ak.surum_coz(bos), bos)

    def test_motor_eski_mi(self):
        for eski in ((1, 3, 0), (1, 4, 9), (1, 5, 0), (0, 9, 99)):
            self.assertTrue(ak.motor_eski_mi(eski), eski)
        for yeni in ((1, 5, 1), (1, 5, 2), (1, 10, 0), (2, 0, 0), None):
            self.assertFalse(ak.motor_eski_mi(yeni), yeni)

    def test_motor_hata_kodu_olculemedi_sayilir(self):
        """`axet-code -v` sıfırdan farklı dönerse çıktısındaki sürüm GÜVENİLMEZ: ölçülemedi (None), eski değil."""
        tamam = ak.subprocess.CompletedProcess(["axet-code", "-v"], 0, "axet-code version 1.4.0\n", "")
        hata = ak.subprocess.CompletedProcess(["axet-code", "-v"], 1, "axet-code version 1.4.0\n", "")
        with mock.patch.object(ak.shutil, "which", return_value="C:/x/axet-code.exe"):
            with mock.patch.object(ak.subprocess, "run", return_value=tamam):
                self.assertEqual((1, 4, 0), ak.motor_surumu())
            with mock.patch.object(ak.subprocess, "run", return_value=hata):
                self.assertIsNone(ak.motor_surumu())
        with mock.patch.object(ak.shutil, "which", return_value=None):
            self.assertIsNone(ak.motor_surumu())

    def test_mesaj_surumu_ve_yolu_soyler(self):
        m = ak.motor_eski_mesaji((1, 4, 0))
        for parca in ("1.4.0", "1.5.1", "%guncelle"):
            self.assertIn(parca, m)


class DoctorAjanTest(unittest.TestCase):
    """doctor.check_ajanlar: eksik → WARN, kurulu → PASS, kullanıcı çakışması → WARN, SAP kapalı → INFO,
    1.5.1'den eski motor → tek WARN (motoru güncelle)."""

    def setUp(self):
        import doctor
        self.doctor = doctor
        self._td = tempfile.TemporaryDirectory()
        self.dizin = Path(self._td.name) / "ajanlar"
        self._env = mock.patch.dict(os.environ, {"AXET_AGENTS_DIR": str(self.dizin)})
        self._env.start()
        # Makinedeki gerçek motor sürümü sonucu değiştirmesin.
        self._motor = mock.patch.object(ak, "motor_surumu", return_value=(1, 5, 1))
        self._motor.start()

    def tearDown(self):
        self._motor.stop()
        self._env.stop()
        self._td.cleanup()

    def test_eski_motor_tek_warn_kurulu_olsa_da(self):
        """Eski motorda 'eksik → %guncelle' önerisi yanlış olurdu (install atlar); kurulu dosya varsa PASS sahte olurdu."""
        with mock.patch.object(ak, "motor_surumu", return_value=(1, 4, 0)):
            durum = self.durum(True)
            self.assertEqual(["WARN"], [s for s, _ in durum], durum)
            self.assertIn("1.4.0", durum[0][1])
            self.assertNotIn("eksik ya da eski", durum[0][1])
            ak.uygula(ak.planla(sap=True))
            durum = self.durum(True)
            self.assertEqual(["WARN"], [s for s, _ in durum], durum)
            # SAP kapalıyken motor sürümü sorulmaz: INFO aynen
            (s, _), = self.durum(False)
            self.assertEqual("INFO", s)

    def test_motor_olcumu_hata_verirse_cokmez(self):
        """Bug gate F1: yarım güncellemede eski ajan_kurulum.py (motor_surumu yok) doctor'ı çökertmesin."""
        ak.uygula(ak.planla(sap=True))
        with mock.patch.object(ak, "motor_surumu", side_effect=AttributeError("motor_surumu")):
            (s, m), = self.durum(True)
        self.assertEqual("PASS", s, m)
        self.assertIn("ölçülemedi", m)

    def test_eski_konum_kopyasi_warn(self):
        """v0.5.22'nin yanlış dizine (Windows, XDG yok → ~/.config) bıraktığı işaretli kopya: emekli değil, ayrı WARN."""
        kok = Path(self._td.name)
        eski = kok / "ev" / ".config" / "axet-code" / "agents"
        env = {k: v for k, v in os.environ.items() if k not in ("AXET_AGENTS_DIR", "XDG_CONFIG_HOME")}
        env["LOCALAPPDATA"] = str(kok / "yerel")
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(ak, "_windows", return_value=True), \
                mock.patch.object(ak, "_ev_dizini", return_value=kok / "ev"):
            ak.uygula(ak.planla(sap=True))
            (s, m), = self.durum(True)
            self.assertEqual("PASS", s, m)
            eski.mkdir(parents=True)
            (eski / "sap-ui5.md").write_text(ak.isle("sap-ui5.md", ORNEK), encoding="utf-8")
            durum = self.durum(True)
        self.assertEqual(["WARN"], [s for s, _ in durum], durum)
        self.assertIn("eski konum", durum[0][1])
        self.assertNotIn("emekli", durum[0][1])

    def test_olculemeyen_motor_pass_ama_beyanli(self):
        ak.uygula(ak.planla(sap=True))
        with mock.patch.object(ak, "motor_surumu", return_value=None):
            (s, m), = self.durum(True)
        self.assertEqual("PASS", s, m)
        self.assertIn("ölçülemedi", m)

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
        # Alt süreç de gerçek ev dizinine / %LOCALAPPDATA%'ya ulaşamasın (yalıtım koddaki XDG korumasına bağlı kalmasın).
        ev = self.tmp / "_ev"
        ev.mkdir()
        self.env.update({"USERPROFILE": str(ev), "HOME": str(ev), "LOCALAPPDATA": str(self.tmp / "_yerel")})
        # Bug gate F2: makinedeki gerçek motorun sürümü sonucu değiştirmesin (eski motorlu geliştiricide sahte kırmızı).
        self.sahte_motor("1.5.1")

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

    def sahte_motor(self, surum: str) -> None:
        """PATH'in başına `axet-code -v` → `axet-code version <surum>` basan sahte motor koyar (gerçek süreç yolu)."""
        bin_ = self.tmp / "_bin"
        bin_.mkdir(exist_ok=True)
        if os.name == "nt":
            (bin_ / "axet-code.cmd").write_text(f"@echo axet-code version {surum}\r\n", encoding="ascii")
        else:
            p = bin_ / "axet-code"
            p.write_text(f"#!/bin/sh\necho 'axet-code version {surum}'\n", encoding="ascii")
            p.chmod(0o755)
        yol = self.env.get("PATH", "")
        if not yol.startswith(str(bin_) + os.pathsep):
            self.env["PATH"] = str(bin_) + os.pathsep + yol

    def test_eski_motorda_kurulum_atlanir_kaldirma_surer(self):
        beklenen = {p.name for p in (AXET_HOME / "agents").glob("sap-*.md")}
        self.sahte_motor("1.4.0")
        for args in (("--sap",), ("--paketler",), ("--sap", "--dry-run")):
            r = self.install(*args)
            self.assertEqual(0, r.returncode, self.cikti(r))
            self.assertIn("AJANLAR: ATLANDI", r.stdout, (args, self.cikti(r)))
            self.assertIn("1.4.0", r.stdout)
            self.assertEqual(set(), self.kurulu(), args)
        # motor güncellenince aynı yol (%guncelle → --paketler) kurar
        self.sahte_motor("1.5.1")
        r = self.install("--paketler")
        self.assertIn("AJANLAR: TAMAM", r.stdout, self.cikti(r))
        self.assertNotIn("ölçülemedi", r.stdout)
        self.assertEqual(beklenen, self.kurulu())
        # motor eskiye dönse de SAP kapatma işaretli ajanları kaldırır
        self.sahte_motor("1.4.0")
        r = self.install("--no-sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual(set(), self.kurulu())
        # --uninstall da (SAP açıkken) motor sürümünden bağımsız kaldırır
        self.sahte_motor("1.5.1")
        self.install("--sap")
        self.assertEqual(beklenen, self.kurulu())
        self.sahte_motor("1.4.0")
        r = self.install("--uninstall")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertNotIn("ATLANDI", r.stdout, self.cikti(r))
        self.assertEqual(set(), self.kurulu())

    def test_bagimsiz_cli_eski_motora_kurmaz(self):
        """Bug gate F3: `python scripts/ajan_kurulum.py` da install.py ile aynı motor kapısından geçer."""
        self.sahte_motor("1.4.0")
        r = self.calistir(self.klon / "scripts" / "ajan_kurulum.py")
        self.assertEqual(1, r.returncode, self.cikti(r))
        self.assertIn("AJANLAR: ATLANDI", r.stdout, self.cikti(r))
        self.assertEqual(set(), self.kurulu())
        self.sahte_motor("1.5.1")
        r = self.calistir(self.klon / "scripts" / "ajan_kurulum.py")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertEqual({p.name for p in (AXET_HOME / "agents").glob("sap-*.md")}, self.kurulu())
        # kaldırma motor sürümünden bağımsızdır (eski motorda da işaretli ajanlar kaldırılabilmeli)
        self.sahte_motor("1.4.0")
        r = self.calistir(self.klon / "scripts" / "ajan_kurulum.py", "--kaldir")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertNotIn("ATLANDI", r.stdout, self.cikti(r))
        self.assertEqual(set(), self.kurulu())

    def test_olculemeyen_motorda_kurulum_surer_beyanli(self):
        self.sahte_motor("bilinmiyor")  # `axet-code version bilinmiyor` → sürüm çözülemez
        r = self.install("--sap")
        self.assertEqual(0, r.returncode, self.cikti(r))
        self.assertIn("AJANLAR: TAMAM", r.stdout, self.cikti(r))
        self.assertIn("sürümü ölçülemedi", r.stdout, self.cikti(r))
        self.assertEqual({p.name for p in (AXET_HOME / "agents").glob("sap-*.md")}, self.kurulu())


if __name__ == "__main__":
    unittest.main()
