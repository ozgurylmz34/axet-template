# -*- coding: utf-8 -*-
"""K-O① (davranış testi 2026-09-18): denetim FAIL anında "kuralı değiştirerek geçme" hatırlatması.

Ölçülen vaka: model pre-commit adlandırma FAIL'ini `.rules.md` regex'ini genişleterek, iskelet
aracının ad reddini de dosyaları elle yazarak aştı. Metin davranışı garanti etmez; burada ölçülen
yalnız hatırlatmanın FAIL anında BASILDIĞI ve temiz koşuda BASILMADIĞIDIR (gürültü olmasın).
KAPSAM — bakılmayan: pre-commit altbilgisi (test_precommit) · SAP kapı reddi (sap-adt-foundation
test_cli_gate) · modelin hatırlatmaya uyup uymadığı (davranış testi).
"""
from __future__ import annotations

from _helpers import ABAP_TEMIZ, AXET_HOME, GeciciTest

SCAFFOLD = AXET_HOME / "skills-sap" / "sap-classic-abap" / "scripts" / "scaffold_classic_program.py"


class IskeletAdReddiTest(GeciciTest):
    def test_ad_reddinde_hatirlatma_basilir_ve_dosya_yazilmaz(self):
        out = self.tmp / "programs"
        r = self.calistir(SCAFFOLD, "ZYANLIS_AD", "--title", "Deneme", "--out", str(out))
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("Ad deseni", r.stderr)
        self.assertIn("HATIRLATMA: bu reddi aşmak için dosyaları elle yazma", r.stderr)
        self.assertFalse(out.exists() and any(out.iterdir()), "red hâlinde dosya yazıldı")

    def test_gecerli_adda_hatirlatma_yok(self):
        """KONTROL GRUBU: hatırlatma her çıktıya basılsaydı gürültü olurdu."""
        out = self.tmp / "programs"
        r = self.calistir(SCAFFOLD, "ZSD001_P_DENEME", "--title", "Deneme", "--out", str(out))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("HATIRLATMA", self.cikti(r))


class PaketAdlandirmaCliTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.d = self.proje(sap=True)
        self.paket(self.d, "ZSD001_CLC")

    def test_fail_aninda_hatirlatma_basilir(self):
        self.yaz(self.d / "SOURCE_CODES/SD/ZSD001_CLC/classes/zcl_yanlis.clas.abap", ABAP_TEMIZ)
        r = self.calistir("check_package_naming.py", "--project-dir", str(self.d))
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("HATIRLATMA: bu denetimi geçmek için kuralı", r.stdout)

    def test_temiz_kosuda_hatirlatma_yok(self):
        r = self.calistir("check_package_naming.py", "--project-dir", str(self.d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("HATIRLATMA", r.stdout)
