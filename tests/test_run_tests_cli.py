# -*- coding: utf-8 -*-
"""Koşucunun KENDİ doğruluğu: `-k` kullanım hataları sessiz-yeşil vermez (D17 ertelenen kalemi).

Neden ayrı bir test: `unittest.TestResult.wasSuccessful()` **0 test için de True** döner. Dolayısıyla
yazım hatası içeren bir `-k` deseni, düzeltmeden önce ekrana "SONUÇ: 0 test" yazıp **çıkış 0** veriyordu —
yani hiçbir şey ölçülmemişken koşum "geçti" görünüyordu. Bu, çekirdek §7'nin "ölçülemedi ≠ temiz"
kuralının koşucu düzeyindeki hâlidir ve bir insan onu ancak sayıya dikkatle bakarsa fark eder.

Çıkış sözleşmesi: 0 geçti · 1 test başarısız · 2 KULLANIM HATASI (ölçüm yapılmadı).
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

BURASI = Path(__file__).resolve().parent
AXET = BURASI.parent

# Dördü de aynı deliği taşıyordu; dördü birlikte düzeltildi. Yeni bir koşucu eklenirse buraya eklenir.
KOSUCULAR = [
    BURASI / "run_tests.py",
    AXET / "skills-sap" / "sap-fs-ts-docs" / "tests" / "run_tests.py",
    AXET / "skills-sap" / "sap-ui5-user-guide" / "tests" / "run_tests.py",
    AXET / "skills-sap" / "sap-ui5-fiori" / "tests" / "run_tests.py",
    AXET / "skills-sap" / "sap-adt-foundation" / "tests" / "run_tests.py",
]


def kos(kosucu: Path, *arg: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(kosucu), *arg],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(AXET), timeout=120)


class KosucuKullanimHatalari(unittest.TestCase):
    def test_kosucular_diskte_var(self) -> None:
        """Liste bayatlarsa aşağıdaki testler sessizce hiçbir şey ölçmez."""
        eksik = [str(p.relative_to(AXET)) for p in KOSUCULAR if not p.is_file()]
        self.assertEqual([], eksik, f"koşucu listesi bayat: {eksik}")

    def test_eslesmeyen_k_deseni_cikis_2(self) -> None:
        """Yazım hatası = 0 test. 0 test 'başarılı' DEĞİLDİR."""
        for kosucu in KOSUCULAR:
            with self.subTest(kosucu=kosucu.relative_to(AXET)):
                r = kos(kosucu, "-k", "zzz_hicbir_teste_uymayan_desen")
                self.assertEqual(2, r.returncode, f"0 test koştu ama çıkış {r.returncode}\n{r.stdout[-400:]}")
                self.assertIn("HİÇ TEST KOŞMADI", r.stderr)
                self.assertIn("zzz_hicbir_teste_uymayan_desen", r.stderr,
                              "hata metni hangi desenin eşleşmediğini söylemiyor")

    def test_degersiz_k_cikis_2(self) -> None:
        """`-k` desen ister; değersizken ne traceback ne de sessizce TÜM takımı koşma."""
        for kosucu in KOSUCULAR:
            with self.subTest(kosucu=kosucu.relative_to(AXET)):
                r = kos(kosucu, "-k")
                self.assertEqual(2, r.returncode, r.stdout[-400:] + r.stderr[-400:])
                self.assertIn("-k bir desen ister", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_k_degeri_gibi_gorunen_bayrak_desen_sayilmaz(self) -> None:
        """`-k --pdf` gibi bir yazımda bayrak desen sanılmaz."""
        r = kos(BURASI / "run_tests.py", "-k", "--olmayan-bayrak")
        self.assertEqual(2, r.returncode, r.stdout[-300:])
        self.assertIn("-k bir desen ister", r.stderr)

    def test_kontrol_gecerli_desen_calisir(self) -> None:
        """KONTROL (PATTERN #19): bu satır olmadan 'her -k çağrısında 2 dön' diyen bir düzeltme de geçerdi."""
        r = kos(BURASI / "run_tests.py", "-k", "merge_pr")
        self.assertEqual(0, r.returncode, r.stdout[-400:] + r.stderr[-400:])
        self.assertNotIn("HİÇ TEST KOŞMADI", r.stderr)
        self.assertRegex(r.stdout, r"SONUÇ: [1-9]\d* test")


class ParalelKosucu(unittest.TestCase):
    """Paralel kol (2026-09-20) — hız için doğruluk feda edilmediğini ölçer.

    Paralelliğin tek meşru gerekçesi duvar saatidir; ölçüm ANLAMI değişirse kazanç sahtedir.
    En tehlikeli kusur sessizliktir: bir işçi çökerse ya da özetini basmazsa toplam "0 kırmızı"
    görünür ve koşum YEŞİL çıkar. O yüzden çöken işçi burada `error` sayılır.
    """

    def test_paralel_ve_sirali_AYNI_test_sayisini_verir(self) -> None:
        """Eşdeğerlik: dağıtım test kaybetmemeli (kayıp = sessiz kapsam daralması)."""
        import re as _re
        sayilar = {}
        for bayrak in (["-j", "1"], ["-j", "4"]):
            r = kos(BURASI / "run_tests.py", "-k", "guncelle_harita", *bayrak)
            self.assertEqual(0, r.returncode, r.stdout[-500:] + r.stderr[-500:])
            m = _re.search(r"SONUÇ: (\d+) test", r.stdout)
            self.assertIsNotNone(m, r.stdout[-300:])
            sayilar[bayrak[1]] = int(m.group(1))
        self.assertEqual(sayilar["1"], sayilar["4"],
                         f"paralel kol test kaybediyor/çoğaltıyor: {sayilar}")
        self.assertGreater(sayilar["1"], 0, "kontrol grubu boş — ölçüm anlamsız")

    def test_j_degersiz_cikis_2(self) -> None:
        for arg in (["-j"], ["-j", "0"], ["-j", "abc"]):
            with self.subTest(arg=arg):
                r = kos(BURASI / "run_tests.py", *arg)
                self.assertEqual(2, r.returncode, r.stdout[-300:])
                self.assertIn("-j pozitif bir tamsayı ister", r.stderr)

    def test_ozetsiz_isci_SESSIZ_YESIL_vermez(self) -> None:
        """İşçi özet basmadan ölürse (çökme/kill) toplam YEŞİL görünmemeli."""
        import importlib.util, unittest.mock as mock, subprocess as sp  # noqa: PLC0415
        spec = importlib.util.spec_from_file_location("axet_run_tests", BURASI / "run_tests.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        sahte = sp.CompletedProcess(args=[], returncode=1, stdout="hicbir isaret yok", stderr="boom")
        with mock.patch.object(m.subprocess, "run", return_value=sahte):
            ozet = m._isci_kos(["a.B.c"])
        self.assertEqual(1, ozet["error"], f"çöken işçi 'error' sayılmadı: {ozet}")
        self.assertTrue(ozet["kirmizilar"], "çökme kırmızı listesine girmedi")

    def test_KONTROL_ozet_basan_isci_normal_sayilir(self) -> None:
        """Kontrol grubu: her işçiyi 'çöktü' sayan bir düzeltme de yukarıdaki testi geçerdi."""
        import importlib.util, json as _json, unittest.mock as mock, subprocess as sp  # noqa: PLC0415
        spec = importlib.util.spec_from_file_location("axet_run_tests2", BURASI / "run_tests.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        govde = {"test": 3, "failure": 0, "error": 0, "skip": 1, "kirmizilar": []}
        sahte = sp.CompletedProcess(args=[], returncode=0,
                                    stdout=m.ISARET + _json.dumps(govde), stderr="")
        with mock.patch.object(m.subprocess, "run", return_value=sahte):
            ozet = m._isci_kos(["a.B.c"])
        self.assertEqual(govde, ozet)


def _kosucu_modulu(ad: str):
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location(ad, BURASI / "run_tests.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class ParcaKosucu(unittest.TestCase):
    """`--parca k/n` (CI'da takım n runner'a bölünür). Hız kazancı KAPSAM kaybıyla ödenmemeli: bir küme
    hiçbir parçaya düşmezse o testler CI'da HİÇ koşmaz ve CI yeşil görünür — sessiz kapsam daralması."""

    def _dogrula(self, kimlikler, parcalar):
        birlesim = [k for p in parcalar for k in p]
        self.assertEqual(sorted(kimlikler), sorted(birlesim), "parçaların birleşimi ≠ tüm takım")
        self.assertEqual(len(birlesim), len(set(birlesim)), "bir test birden çok parçada")
        kume_kumeleri = [{k.rsplit(".", 1)[0] for k in p} for p in parcalar]
        for i, a in enumerate(kume_kumeleri):  # küme bölünmez: aynı sınıfın testleri tek parçada
            for b in kume_kumeleri[i + 1:]:
                self.assertFalse(a & b, f"küme iki parçaya bölünmüş: {sorted(a & b)[:3]}")

    def test_gercek_takim_her_n_icin_eksiksiz_ve_ayrik(self) -> None:
        m = _kosucu_modulu("axet_run_tests_p1")
        kimlikler = m._kimlikleri_topla(None)
        self.assertGreater(len(kimlikler), 100, "keşif boş — ölçüm anlamsız")
        for n in (1, 2, 3, 5):
            for agirlik in (m._agirliklar(), {}):  # ağırlık dosyası yok/bayat ⇒ yalnız denge bozulur
                with self.subTest(n=n, agirlikli=bool(agirlik)):
                    self._dogrula(kimlikler, m.parcala(kimlikler, n, agirlik))

    def test_bilinmeyen_kume_dusmez_ve_belirlenimci(self) -> None:
        m = _kosucu_modulu("axet_run_tests_p2")
        kimlikler = [f"test_a.S{i}.test_{j}" for i in range(7) for j in range(3)] + ["test_yeni.Y.test_x"]
        agirlik = {f"test_a.S{i}": float(10 - i) for i in range(7)}  # `test_yeni.Y` ağırlık dosyasında YOK
        ilk = m.parcala(kimlikler, 3, agirlik)
        self._dogrula(kimlikler, ilk)
        tersten = m.parcala(list(reversed(kimlikler)), 3, agirlik)
        self.assertEqual([sorted(p) for p in ilk], [sorted(p) for p in tersten],
                         "girdi sırası bölmeyi değiştirdi — runner'lar farklı bölme hesaplar")

    def test_agirlik_dosyasi_gercek_kumeleri_kapsar(self) -> None:
        """Bayat dosya kapsam düşürmez ama dengeyi bozar; çok bayatlarsa CI yavaşlar. Eşik: kümelerin %80'i."""
        m = _kosucu_modulu("axet_run_tests_p3")
        kumeler = {k.rsplit(".", 1)[0] for k in m._kimlikleri_topla(None)}
        agirlik = m._agirliklar()
        self.assertTrue(agirlik, f"{m.AGIRLIK_DOSYASI.name} okunamadı")
        oran = len(kumeler & set(agirlik)) / len(kumeler)
        self.assertGreaterEqual(oran, 0.8, f"ağırlık dosyası bayat: kümelerin %{oran * 100:.0f}'i ölçülü — "
                                "tests/parca-agirlik.json'ı yeniden üret")

    def test_parca_degersiz_cikis_2(self) -> None:
        for arg in (["--parca"], ["--parca", "0/3"], ["--parca", "4/3"], ["--parca", "a/b"], ["--parca", "2"]):
            with self.subTest(arg=arg):
                r = kos(BURASI / "run_tests.py", *arg)
                self.assertEqual(2, r.returncode, r.stdout[-300:])
                self.assertIn("--parca k/n ister", r.stderr)

    def test_parca_toplami_parcasiz_kosuma_esit(self) -> None:
        """Uçtan uca: parçaların SONUÇ sayıları toplamı = parçasız koşum (sıralı kol dahil: -j 1)."""
        import re as _re

        def sayi(*arg):
            r = kos(BURASI / "run_tests.py", "-k", "guncelle_harita", *arg)
            m = _re.search(r"SONUÇ: (\d+) test", r.stdout)
            self.assertIsNotNone(m, r.stdout[-300:] + r.stderr[-300:])
            return int(m.group(1))

        tum = sayi()
        self.assertEqual(tum, sum(sayi("--parca", f"{k}/2", "-j", "1") for k in (1, 2)))


if __name__ == "__main__":
    unittest.main()
