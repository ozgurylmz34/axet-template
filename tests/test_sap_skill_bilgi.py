# -*- coding: utf-8 -*-
"""SAP skill bilgisinin BULUNABİLİRLİĞİ ve intake şablonunun kural içeriği (IS-LISTESI Z34 · Z35 · Z36).

Ölçülen vaka (RAP "masraf talebi" testi, 2026-09-21): aXet numara aralığı tarifini `grep -rE "number range|NRIV|nrng"`
ile aradı → 0 sonuç; tarif `sap-rap/references/behavior-impl.md` §3'te yalnız "NR objesi" diye yazılıydı ⇒ model MAX+1
uydurdu. Aynı testte backend feature control bilgisi hiçbir referansta yoktu; intake şablonu DDIC adı / kural taraması /
sürüm kontrolü istemiyordu.

Burada ölçülen: ⓐ aXet'in yaptığı aramanın (aynı desen, grep -E gibi büyük/küçük harf DUYARLI) artık §3'e düştüğü
ⓑ `sap-rap` açıklamasının eş anlamlıları taşıdığı ve aXet sınırında kaldığı ⓒ feature control referansının var olup
yönlendirildiği ⓓ intake şablonunun yeni bölümleri ve boş şablonun S2 kapısından hâlâ DÜŞTÜĞÜ.
KAPSAM — bakılmayanlar: modelin bu metinleri bulup UYGULADIĞI (davranış testi, IS-LISTESI Z37) · RAP sözdiziminin
canlı sistemde çalıştığı (Z35 canlı adımı) · metnin doğruluğu.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _helpers import AXET_HOME

SAP = AXET_HOME / "skills-sap"
RAP = SAP / "sap-rap"
INTAKE = SAP / "sap-intake-triage"
# aXet'in 2026-09-21 koşumunda kullandığı desen AYNEN (grep -rE, -i YOK).
AXET_ARAMASI = re.compile(r"number range|NRIV|nrng")
ES_ANLAMLILAR = ("number range", "numara aralığı", "SNRO", "NRIV", "NROB", "NUMBER_GET_NEXT", "early numbering")


def _oku(yol: Path) -> str:
    return yol.read_text(encoding="utf-8")


def _bolum(metin: str, baslik_rx: str) -> str:
    """`## N.` başlıklı bölümün gövdesi (bir sonraki `## ` başlığına kadar)."""
    m = re.search(r"(?ms)^" + baslik_rx + r".*?(?=^## |\Z)", metin)
    return m.group(0) if m else ""


def _aciklama(skill_md: str) -> str:
    fm = re.match(r"^---\r?\n(.*?)\r?\n---", skill_md, re.S)
    assert fm, "frontmatter yok"
    m = re.search(r"(?ms)^description: >\s*\n((?:[ \t]+\S.*\n?)+)", fm.group(1) + "\n")
    assert m, "description '>' blok biçiminde değil"
    return " ".join(s.strip() for s in m.group(1).splitlines() if s.strip())


class NumaraAraligiBulunabilirTest(unittest.TestCase):
    """Z34."""

    def test_axet_aramasi_behavior_impl_bolum_3e_duser(self):
        metin = _oku(RAP / "references" / "behavior-impl.md")
        bolum = _bolum(metin, r"## 3\. ")
        self.assertTrue(bolum, "behavior-impl.md'de '## 3.' bölümü yok")
        self.assertRegex(bolum, AXET_ARAMASI, "aXet'in aradığı desen §3'e düşmüyor")
        self.assertIn("NUMBER_GET_NEXT", bolum)

    def test_axet_aramasi_skill_icinde_ilk_isabet_bolum_3(self):
        """KONTROL: desen skill içinde başka yere düşse de §3 isabetler arasında olmalı (grep -r sırası değil, varlık)."""
        isabetler = []
        for yol in sorted(RAP.rglob("*.md")):
            for no, satir in enumerate(_oku(yol).splitlines(), 1):
                if AXET_ARAMASI.search(satir):
                    isabetler.append((yol.name, no))
        self.assertIn("behavior-impl.md", {ad for ad, _ in isabetler}, isabetler)

    def test_aciklama_es_anlamlilari_tasir_ve_sinirda(self):
        md = _oku(RAP / "SKILL.md")
        aciklama = _aciklama(md)
        eksik = [k for k in ES_ANLAMLILAR if k.lower() not in aciklama.lower()]
        self.assertEqual([], eksik, "sap-rap description'ında eksik eş anlamlılar")
        self.assertLessEqual(len(aciklama), 1024, "aXet 1024 üstü açıklamalı skill'i SESSİZCE yüklemez")

    def test_frontmatter_doctor_temiz(self):
        import doctor  # scripts/ _helpers ile yolda
        for skill in ("sap-rap", "sap-dev", "sap-intake-triage"):
            with self.subTest(skill=skill):
                self.assertEqual([], doctor.frontmatter_problems(_oku(SAP / skill / "SKILL.md")))


class FeatureControlTest(unittest.TestCase):
    """Z35."""

    def test_referans_var_ve_ana_kavramlari_tasir(self):
        yol = RAP / "references" / "feature-control.md"
        self.assertTrue(yol.is_file(), "sap-rap/references/feature-control.md yok")
        metin = _oku(yol)
        for parca in ("features : instance", "get_instance_features", "FOR INSTANCE FEATURES", "%update", "%delete",
                      "%action-", "%field-", "%assoc-", "fc-o-disabled", "fc-f-read_only",
                      "get_instance_authorizations", "auth-unauthorized", "sap:updatable-path", "IN LOCAL MODE",
                      # v0.5.2: EML kolu canlı ölçüldü (§7a); ölçülmeyen kolların sınırı hâlâ yazılı olmalı
                      "ÖLÇÜLDÜ", "## 7a.", "ölçülmedi", "**Kanıtlamadığı:**"):
            with self.subTest(parca=parca):
                self.assertIn(parca, metin)

    def test_skill_tablosu_ve_checklist_yonlendirir(self):
        self.assertRegex(_oku(RAP / "SKILL.md"), r"(?m)^\| `references/feature-control\.md` \|",
                         "SKILL.md referans tablosunda feature-control.md satırı yok")
        cl = _oku(RAP / "references" / "checklists.md")
        satirlar = [s for s in cl.splitlines() if "feature control" in s.lower() and "BLOCKER" in s]
        self.assertTrue(satirlar, "checklists.md'de feature control BLOCKER satırı yok")


class IntakeSablonuTest(unittest.TestCase):
    """Z36."""

    def setUp(self):
        self.sablon = _oku(INTAKE / "templates" / "intake-artifact.md")
        self.protokol = _oku(INTAKE / "references" / "protocol.md")

    def test_sablon_yeni_bolumleri_tasir(self):
        for parca in ("Kural taraması", "ONAY: [ ]", "Canlı kontrol", "Sistem sürümü", "Öz-tutarlılık",
                      "local_last_changed_at"):
            with self.subTest(parca=parca):
                self.assertIn(parca, self.sablon)

    def test_yeni_onay_kutulari_mutabakat_sayilmaz(self):
        """Kapı `mutabakat`/`sign-off` + `[x]` aynı satırdaysa işaret sayar; yeni kutular o kelimeyi taşımamalı."""
        for satir in self.sablon.splitlines():
            if "[ ]" in satir and not satir.lstrip("- ").upper().startswith("MUTABAKAT"):
                self.assertNotRegex(satir, r"(?i)mutabakat|sign-?off", satir)

    def test_bos_sablon_isaretlense_de_kapidan_duser(self):
        """Şablon doldurulmadan `[x]` konursa S2 kapısı reddetmeli (şema dosyasının 'boş şablon → çıkış 1' iddiası)."""
        isaretli = self.sablon.replace("MUTABAKAT: [ ]", "MUTABAKAT: [x]")
        self.assertNotEqual(isaretli, self.sablon, "şablonda 'MUTABAKAT: [ ]' satırı yok")
        with tempfile.TemporaryDirectory() as d:
            yol = Path(d) / "bos.md"
            yol.write_text(isaretli, encoding="utf-8")
            r = subprocess.run([sys.executable, str(INTAKE / "scripts" / "check_intake_signoff.py"), str(yol)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(1, r.returncode, r.stdout + r.stderr)

    def test_protokol_kurallari(self):
        for parca in ("Kural taraması", "eş anlamlı", "CVERS", "sap-project.json", "ONAY"):
            with self.subTest(parca=parca):
                self.assertIn(parca, self.protokol)


class DdicAdOnerisiKuraliTest(unittest.TestCase):
    """Z36 ⓐ: Z DDIC adı önerilir + canlı kontrol + açık onay; standart objeye append alanı adı ÖNERİLMEZ."""

    def test_sap_dev_tablosu(self):
        md = _oku(SAP / "sap-dev" / "SKILL.md")
        self.assertNotIn("| DTEL / append alanı adı | AI önermez; kullanıcı belirler. |", md)
        self.assertRegex(md, r"(?m)^\| Yeni Z DDIC objesinin adı")
        self.assertRegex(md, r"(?m)^\| Standart objeye append alanı .*AI önermez")

    def test_eski_genel_yasak_ifadesi_skill_metinlerinde_kalmadi(self):
        """'DTEL adını AI önermez' gibi Z DDIC'i de kapsayan ifade kalmamalı (append bağlamı hariç)."""
        kalan = []
        for yol in list(SAP.rglob("*.md")) + [AXET_HOME / "templates" / "package" / ".rules.md.tmpl"]:
            for no, satir in enumerate(_oku(yol).splitlines(), 1):
                if re.search(r"(?i)DTEL[^.|]*(AI önermez|önermezsin|adı önerme\b|adını önerme\b)", satir) \
                        and "append" not in satir.lower():
                    kalan.append("%s:%d" % (yol.relative_to(AXET_HOME), no))
        self.assertEqual([], kalan)


    def test_kanonik_yasak_a_append_ile_z_ddic_adini_ayirir(self):
        """Kanonik yasak A: 'önermezsin' yalnız standart objeye append; Z DDIC adı öner + canlı kontrol + onay."""
        md = _oku(AXET_HOME / "core" / "sap" / "00-sap.md")
        a = next(s for s in md.splitlines() if s.startswith("| **A — "))
        self.assertNotIn("Append alanı / DTEL adını sen önermezsin", a)
        self.assertIn("append", a.lower())
        self.assertRegex(a, r"Z DDIC[^|]*canlı[^|]*onay")

    def test_kanonik_yasak_a_append_yaratimini_kullaniciya_birakir(self):
        """Z103 (canlı T4): kullanıcı adları verse de append'i AI yaratmaz; A ve C'de DEVAM = kullanıcının sonucunu doğrula."""
        md = _oku(AXET_HOME / "core" / "sap" / "00-sap.md")
        a = next(s for s in md.splitlines() if s.startswith("| **A — "))
        self.assertIn("sen yaratmazsın", a)
        self.assertIn("Kullanıcı adları verse de yaratımı üstlenmezsin", a)
        devam = next(s for s in md.splitlines() if s.startswith("**Yapılması gerekiyorsa:**"))
        self.assertIn("A ve C'de işlemi kullanıcı kendisi yapar", devam)
        ornek = next(s for s in md.splitlines() if s.startswith("**Örnek (A):**"))
        self.assertIn("yaratımı sen yapmazsın", ornek)

    def test_kanonik_yasak_a_standart_obje_yalniz_okunur(self):
        """Kullanıcı kuralı 2026-09-24: standart DDIC objesi/program YALNIZ okunur; append alanının Z DTEL'ini de AI yaratmaz."""
        md = _oku(AXET_HOME / "core" / "sap" / "00-sap.md")
        a = next(s for s in md.splitlines() if s.startswith("| **A — "))
        self.assertIn("Standart objeler YALNIZ OKUNUR", a)
        self.assertIn("program", a)
        self.assertRegex(a, r"append alanını ve o alanın Z DTEL'ini")
        self.assertRegex(a, r"Standarda eklenmeyen bağımsız Z DDIC")

    def test_rol_brifingi_s1_kanonik_bolumun_birebir_kopyasi(self):
        """role-briefs S1 'birebir kopya' der: kanonik KESİN YASAKLAR bölümüyle aynı olmalı (Z103 bug gate)."""
        import sys
        sys.path.insert(0, str(AXET_HOME / "scripts"))
        import sap_stamp
        kanonik = sap_stamp._BOLUM.search(_oku(AXET_HOME / "core" / "sap" / "00-sap.md")).group(0).strip()
        rb = _oku(SAP / "sap-dev" / "references" / "role-briefs.md")
        bas = rb.index("```text\n", rb.index("### S1 — Kesin yasaklar")) + len("```text\n")
        self.assertEqual(kanonik, rb[bas:rb.index("```", bas)].strip())

    def test_append_kopyalari_yaratim_yasagini_tasir(self):
        """Z103: append adını anan ikincil metinler yaratım yasağını da söyler (yalnız 'ad önerilmez' T4 hatasını üretti)."""
        yollar = [SAP / "sap-dev" / "references" / "naming.md", SAP / "sap-adt-foundation" / "references" / "foundation-ops.md",
                  SAP / "sap-abapgit-delivery" / "SKILL.md", SAP / "sap-cds-ddic" / "SKILL.md",
                  SAP / "sap-cds-ddic" / "references" / "domain-dtel.md", SAP / "sap-dev" / "SKILL.md",
                  AXET_HOME / "templates" / "package" / ".rules.md.tmpl"]
        for yol in yollar:
            with self.subTest(yol=yol.name):
                self.assertRegex(_oku(yol), r"(?i)append'i[^.|]*(yaratma|yaratmaz|kullanıcı yaratır|kendisi yaratır|ZIP'e koyma)")
        self.assertNotIn("yalnız kullanıcı talebiyle", _oku(SAP / "sap-dev" / "references" / "naming.md"))

    def test_cekirdek_kabuk_notu_find_kisitini_tasir(self):
        """Her oturum yüklenen çekirdek: Go `find` -iname/-maxdepth desteklemez → rg --files --iglob (Z46)."""
        md = _oku(AXET_HOME / "core" / "00-temel.md")
        kabuk = next(s for s in md.splitlines() if "**Kabuk ortamı:**" in s)
        for parca in ("-iname", "-maxdepth", "rg --files --iglob"):
            self.assertIn(parca, kabuk)

if __name__ == "__main__":
    unittest.main()
