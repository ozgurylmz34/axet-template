# -*- coding: utf-8 -*-
"""Skill yönlendirme metinleri — build öncesi paket klasörü/indirme (Z142ⓑ), commit onayında dal bağlamı (Z148),
tek cevaplı soruda `İptal` seçeneği (Z111ⓔ).

Kaynak vakalar (müşteri projesi canlı iş gözlemi, 2026-09-26): ⓐ intake'ten build'e geçişte `%sap-dev` hiç yüklenmedi,
değiştirilen kaynak paket dışına (`.tmp/`) yazılıp oradan push edildi; 2. turda plan klasör kurulumunu SONA koydu
ⓑ commit onay sorusunda yalnız dosya listesi vardı, commit 3 gün önceki `wip/<tarih>` dalına girdi ⓒ transport
sorusunda `ask_user` "≥2 seçenek" hatası sonrası uydurulan 2. seçenek yasak bir eylemdi ("siz açın").

Burada ölçülen: kuralların metinde, doğru adımda ve doğru SIRADA durduğu; öğretilen git komutlarının
`config/permissions.json` deny/ask desenlerine takılmadığı (takılırsa tarif uygulanamaz — test_yerel_birlestirme ile
aynı fnmatchcase simülasyonu).
KAPSAM — bakılmayanlar: modelin metni bulup UYGULADIĞI (canlı lab koşusu gerekir) · `adt_get output_path` ve
`adt_push_source source_path` parametrelerinin araçta VAR olduğu (L1a lane'i yazıyor; birleşince tool-catalog testleri
ölçer) · metnin Türkçe doğruluğu.
"""
from __future__ import annotations

import fnmatch
import json
import re
import unittest

from _helpers import AXET_HOME

SKILLS = AXET_HOME / "skills"
SAP = AXET_HOME / "skills-sap"
COMMIT_PR = SKILLS / "commit-pr" / "SKILL.md"
GUN_SONU = SKILLS / "gun-sonu" / "SKILL.md"
SAP_DEV = SAP / "sap-dev" / "SKILL.md"
INTAKE = SAP / "sap-intake-triage"
FOUNDATION = SAP / "sap-adt-foundation" / "SKILL.md"
IZINLER = AXET_HOME / "config" / "permissions.json"

# Z148 tarifinin öğrettiği komutlar (yer tutucular gerçek adla). Hiçbiri deny/ask'a uymamalı.
TARIF_KOMUTLARI = [
    "git branch --show-current",
    "git rev-list --left-right --count origin/main...HEAD",
    "git rev-list --left-right --count main...HEAD",
    "git log --oneline origin/main..HEAD",
    "git fetch origin",
    "git switch -c wip/2026-09-26-konu origin/main",
    "git switch -c wip/2026-09-26-konu main",
]


def _oku(yol) -> str:
    return yol.read_text(encoding="utf-8")


def _sira(test: unittest.TestCase, metin: str, *parcalar: str) -> None:
    """Her parça metinde VAR ve verilen sırada. (Yalnız `find` kıyası yetmez: bulunamayan parça -1 döner ve her
    kıyası geçer — ölçüldü, M7 mutantı böyle yaşadı.)"""
    yerler = [metin.find(p) for p in parcalar]
    for p, y in zip(parcalar, yerler):
        test.assertGreaterEqual(y, 0, f"yok: {p}")
    test.assertEqual(yerler, sorted(yerler), f"sıra bozuk: {parcalar}")


def _bolum(metin: str, bas: str, son: str) -> str:
    """`bas` desenli satırdan `son` desenli satıra kadar (son hariç). Bulunamazsa ""."""
    m = re.search(rf"(?ms)^{bas}.*?(?=^{son}|\Z)", metin)
    return m.group(0) if m else ""


class PaketKlasoruBuildOncesiTest(unittest.TestCase):
    """Z142ⓑ + Z146 yönlendirmesi."""

    def test_sap_dev_bolum3_indir_duzenle_diff_push(self):
        b3 = _bolum(_oku(SAP_DEV), r"### 3\. Paket", r"### 4\.")
        self.assertTrue(b3, "sap-dev §3 bulunamadı")
        for oge in ("build'den ÖNCE", "<source_root>/<MODÜL>/<PAKET>/<tip>/", "`adt_get` `output_path`",
                    "diff", "`adt_push_source` `source_path`", "`%sap-adt-foundation` §2", "`.tmp/`",
                    "--mevcut", "TADIR.AUTHOR", "Owner'ı kendin", "`--owner`"):
            self.assertIn(oge, b3, oge)

    def test_sap_dev_plan_sirasi_paket_klasoru_ilk(self):
        b3 = _bolum(_oku(SAP_DEV), r"### 3\. Paket", r"### 4\.")
        plan = b3[b3.find("Build planını"):]
        self.assertTrue(plan.startswith("Build planını"), "plan sırası cümlesi yok")
        _sira(self, plan, "① paket klasörü", "② değiştirilecek objeleri indir", "③ build.")

    def test_foundation_yerlesim_kurali_atif_hedefi_duruyor(self):
        """sap-dev metni foundation §2'ye atıf verir, kuralı tekrarlamaz — atıf hedefi yerinde olmalı."""
        b2 = _bolum(_oku(FOUNDATION), r"### 2\.", r"### 3\.")
        self.assertIn("İndirilen kaynağı paket adıyla eşleşen klasöre", b2)

    def test_intake_cikisi_sap_deve_devreder(self):
        skill = _oku(INTAKE / "SKILL.md")
        adim8 = _bolum(skill, r"8\. ", r"## ")
        for oge in ("`%sap-dev` ZORUNLU", "§3", "new_package.py", "ilk adımı paket klasörü"):
            self.assertIn(oge, adim8, oge)
        self.assertIn("`sap-dev` skill'ini oku", _oku(INTAKE / "templates" / "command-intake.md"))

    def test_intake_sablonu_build_plani_paket_klasoruyle_baslar(self):
        sablon = _oku(INTAKE / "templates" / "intake-artifact.md")
        satir = next((s for s in sablon.splitlines() if s.startswith("- Build planı")), "")
        self.assertTrue(satir, "şablonda Build planı satırı yok")
        _sira(self, satir, "① paket klasörü", "② değiştirilecek objeleri", "③ <build adımları>")
        self.assertIn("--mevcut", satir)
        # check_intake_signoff alanlarıyla çakışmasın: satır zorunlu alan anahtarlarını taşımamalı (ilk eşleşen kazanır)
        for anahtar in (r"kapsam\s*:", r"prior-?art", r"kabul\s+kriter", r"mutabakat", r"sign-off"):
            self.assertIsNone(re.search(anahtar, satir, re.I), anahtar)


class CommitDalBaglamiTest(unittest.TestCase):
    """Z148: commit onayı dal adını + main'e göre ileri/geriyi söyler; başka günün wip dalında yeni dal önerir."""

    def test_commit_pr_adim4_dal_ileri_geri(self):
        adim4 = _bolum(_oku(COMMIT_PR), r"4\. \*\*Ekle", r"5\. ")
        for oge in ("git branch --show-current", "git rev-list --left-right --count <taban>...HEAD",
                    "`<geri> <ileri>`", "git log --oneline <taban>..HEAD", "git diff --staged --stat",
                    "Yeni dal aç (önerilen)", "`İptal`", "Cevap gelmezse commit yok"):
            self.assertIn(oge, adim4, oge)
        # Koşul doğrulanabilir olgu olmalı ("görünmüyorsa" gibi yargı değil)
        self.assertIn("bu konuşmada sen yazmadıysan", adim4)

    def test_commit_pr_adim3_eski_wip_dali(self):
        adim3 = _bolum(_oku(COMMIT_PR), r"3\. \*\*Dal", r"4\. ")
        for oge in ("Başka günün `wip/` dalındaysan", "bu tarih bugün değil", "git switch -c <yeni-dal> origin/main",
                    "çakışma derse DUR"):
            self.assertIn(oge, adim3, oge)

    def test_gun_sonu_eski_wip_dalina_sessiz_commit_yok(self):
        adim7 = _bolum(_oku(GUN_SONU), r"7\. \*\*WIP commit", r"8\. ")
        for oge in ("Başka günün `wip/` dalındaysan", "`dal: <bu dal>`", "sessizce commit etme",
                    "`%commit-pr` adım 4", "Yeni dal aç (önerilen)", "`İptal`", "dal kararı bekliyor"):
            self.assertIn(oge, adim7, oge)

    def test_tarif_komutlari_izin_kuralina_takilmaz(self):
        bash = json.loads(IZINLER.read_text(encoding="utf-8"))["rules"]["bash"]
        takilan = {k: [(p, v) for p, v in bash.items() if fnmatch.fnmatchcase(k, p)] for k in TARIF_KOMUTLARI}
        takilan = {k: v for k, v in takilan.items() if v}
        self.assertEqual(takilan, {}, "skill'in öğrettiği komut deny/ask desenine uyuyor — tarif uygulanamaz")


class TekCevapliSoruIptalTest(unittest.TestCase):
    """Z111ⓔ: tek cevaplı soruda ikinci seçenek `İptal`; yasak eylem seçenek yapılmaz. Genel kural çekirdekte
    (lider); burada yalnız somut soru içeren adımlardaki uygulama notları ölçülür."""

    def test_uygulama_notlari(self):
        beklenen = {
            COMMIT_PR: ("`Birleştir` · `İptal`",),
            GUN_SONU: ("`Push et` · `İptal`",),
            SAP_DEV: ("ikinci seçenek `İptal`", "kesin yasak C"),
            INTAKE / "references" / "protocol.md": ("ikinci seçenek `İptal`", "seçenek yapılmaz"),
            SAP / "sistem" / "SKILL.md": ('ikinci\n   seçenek "Vazgeç"',),  # emsal (değiştirilmedi)
        }
        for yol, ogeler in beklenen.items():
            metin = _oku(yol)
            for oge in ogeler:
                self.assertIn(oge, metin, f"{yol.relative_to(AXET_HOME)}: {oge}")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless((AXET_HOME / "maintenance" / "canli-test-plani.md").is_file(),
                     "maintenance/canli-test-plani.md yok (public sürümde maintenance/ dışlanır)")
class RapYenidenKosumPlaniTest(unittest.TestCase):
    """Z37ⓐ: yeniden koşum planındaki istem senaryo dosyasıyla BİREBİR aynı (kıyas bozulmasın) ve gerçek transport
    numarası yok (public repo)."""

    PLAN = AXET_HOME / "maintenance" / "canli-test-plani.md"
    SENARYO = AXET_HOME / "maintenance" / "degerlendirme" / "rap-masraf-talebi.md"

    @staticmethod
    def _istem(metin: str) -> str:
        m = re.search(r"```\n(Bir masraf talebi.*?)```", metin, re.S)
        return m.group(1) if m else ""

    def test_istem_birebir_ayni(self):
        plan, senaryo = _oku(self.PLAN), _oku(self.SENARYO)
        self.assertTrue(self._istem(senaryo), "senaryoda istem bloğu yok")
        self.assertEqual(self._istem(plan), self._istem(senaryo))
        ek = "`$TMP lokal pakette lokal uygulama olacak. ama request gerekirse <TRANSPORT> kullanabilirsin.`"
        self.assertIn(ek, plan)
        self.assertIn(ek, senaryo)

    def test_puan_tablosu_duzeltme_maddelerini_tasir(self):
        b23 = _bolum(_oku(self.PLAN), r"## 23\. ", r"## 24\. ")
        for oge in ("| 4 |", "Z36ⓓ", "| 7 |", "Z34", "| 8 |", "Z36ⓐ", "| 13 |", "Z35", "| 14 |", "Z36ⓑ", "| 15 |",
                    "Z36ⓒ", "1. koşum (2026-09-21)", "2. koşum", "axet-code.db"):
            self.assertIn(oge, b23, oge)

    def test_gercek_transport_numarasi_yok(self):
        desen = re.compile(r"\b[A-Z0-9]{3}K9\d{5}\b")
        for yol in (self.PLAN, self.SENARYO):
            bulgu = [x for x in desen.findall(_oku(yol)) if x != "ZXXK900001"]
            self.assertEqual(bulgu, [], yol.name)
