# -*- coding: utf-8 -*-
"""check_package_naming.py — .rules.md Naming regex'leri, include türetme, istisna, --files kipi."""
from __future__ import annotations

from _helpers import GeciciTest  # önce: scripts/ yolunu ekler
import check_package_naming as cpn

UYGUN = [
    "cds/zsd001_i_order.ddls.asddls",
    "cds/zsd001_ui_order.srvd.srvdsrv",
    "classes/zcl_sd001_helper.clas.abap",
    "classes/zcl_sd001_helper.clas.locals_imp.abap",
    "programs/zsd001_p_sevk.prog.abap",
    "programs/includes/zsd001_i_sevk_t01.prog.abap",
    "structures/zsd001_s_head.tabl.xml",
    "tables/zsd001_t_log.tabl.xml",
]


class PackageNamingTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        self.d = self.proje(sap=True, git_init=False)
        self.pkg = self.paket(self.d, "ZSD001_CLC")
        for rel in UYGUN:
            self.yaz(self.pkg / rel, "* kaynak\n")
        self.yaz(self.pkg / "cds" / "README.md", "not\n")

    def kontrol(self, *args: str):
        return self.calistir("check_package_naming.py", "--project-dir", str(self.d), *args)

    def test_uygun_adlar_gecer(self):
        r = self.kontrol()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn(f"{len(UYGUN)} obje dosyası tarandı", r.stdout)
        self.assertIn("KAPSAM", r.stdout)

    def test_alternation_kacisli_pipe_okunur(self):
        kurallar, _ = cpn.kurallari_oku((self.pkg / ".rules.md").read_text(encoding="utf-8"))
        self.assertIn(("service definition", "^ZSD001_(UI|API)_[A-Z0-9_]+$"), kurallar)

    # --- negatif ---
    def test_uymayan_cds_adi(self):
        self.yaz(self.pkg / "cds" / "zorder.ddls.asddls", "x\n")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ZORDER hiçbir regex'e uymuyor", r.stdout)

    def test_uymayan_sinif_oneki(self):
        self.yaz(self.pkg / "classes" / "zcl_helper.clas.abap", "x\n")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ZCL_HELPER", r.stdout)

    def test_include_programdan_turemiyor(self):
        self.yaz(self.pkg / "programs" / "includes" / "zsd001_i_svk_t01.prog.abap", "x\n")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn("türemiyor", r.stdout)

    def test_program_adi_26_karakteri_asar(self):
        self.yaz(self.pkg / "programs" / "zsd001_p_tam_yirmialti_krk.prog.abap", "x\n")  # tam 26 = sınır
        self.assertEqual(self.kontrol().returncode, 0, "kontrol grubu: tam 26 karakter FAIL olmamalı")
        self.yaz(self.pkg / "programs" / "zsd001_p_cok_uzun_bir_ad_xy.prog.abap", "x\n")  # 27
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn("> 26", r.stdout)

    def test_istisna_listesi(self):
        self.yaz(self.pkg / "classes" / "zbp_i_order.clas.abap", "x\n")
        self.assertEqual(self.kontrol().returncode, 1, "kontrol grubu: istisnasız FAIL olmalı")
        kural = self.pkg / ".rules.md"
        kural.write_text(kural.read_text(encoding="utf-8").replace(
            "## Bilinen istisnalar\n", "## Bilinen istisnalar\n- `ZBP_I_ORDER` — RAP behavior pool\n"), encoding="utf-8")
        r = self.kontrol()
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_doldurulmamis_yer_tutucu(self):
        kural = self.pkg / ".rules.md"
        kural.write_text(kural.read_text(encoding="utf-8").replace("`^ZSD001_T_[A-Z0-9_]+$`", "`^{PKG}_T_[A-Z0-9_]+$`"),
                         encoding="utf-8")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn("yer tutucusu", r.stdout)

    def test_gecersiz_regex_cokmez(self):
        kural = self.pkg / ".rules.md"
        kural.write_text(kural.read_text(encoding="utf-8").replace("`^ZSD001_T_[A-Z0-9_]+$`", "`^ZSD001_T_[A-Z0-9_+$`"),
                         encoding="utf-8")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("geçersiz", r.stdout)
        self.assertNotIn("Traceback", self.cikti(r))

    def test_kurallari_olmayan_paket(self):
        self.yaz(self.d / "SOURCE_CODES" / "SD" / "ZSD009" / "cds" / "zsd009_i_x.ddls.asddls", "x\n")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn(".rules.md yok", r.stdout)

    def test_naming_tablosu_bozuk(self):
        kural = self.pkg / ".rules.md"
        kural.write_text(kural.read_text(encoding="utf-8").replace("## Naming", "## Adlar"), encoding="utf-8")
        r = self.kontrol()
        self.assertEqual(r.returncode, 1)
        self.assertIn("regex çıkarılamadı", r.stdout)

    def test_files_kipi_yalniz_verilenler(self):
        kotu = self.yaz(self.pkg / "cds" / "zorder.ddls.asddls", "x\n")
        iyi = "SOURCE_CODES/SD/ZSD001_CLC/cds/zsd001_i_order.ddls.asddls"
        r = self.kontrol("--files", iyi, "README.md", "baska/dosya.abap")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("1 obje dosyası tarandı", r.stdout)
        r = self.kontrol("--files", str(kotu))
        self.assertEqual(r.returncode, 1)

    def test_sap_projesi_degil(self):
        (self.d / "sap-project.json").unlink()
        self.assertEqual(self.kontrol().returncode, 2)
