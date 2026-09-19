# -*- coding: utf-8 -*-
"""vakum_tara.py — "vakum assertion" tarayıcısının KALİBRASYONU.

Bu dosyanın işi tarayıcının bulduklarını doğrulamak DEĞİL; **tarayıcının kendisinin körleşmediğini**
ölçmektir. Gerekçe ölçüldü (2026-09-18): araç iki kez sessizce yanlış çalıştı ve ikisi de yalnız
kontrol grubuyla yakalandı —

  ① Gövde dilimi `def` satırını içeriyordu ⇒ her test kendi vaadini KENDİ ADIYLA kanıtlıyordu.
     AD-GÖVDE boyutu baştan ölüydü ve çıktı sağlıklı görünüyordu ("0 bulgu").
  ② Sözcük sınırına `_` dahildi ⇒ `s3` simgesi `s3_cekirdek` bileşik adının içinde geçtiği hâlde
     "gövdede yok" sayılıyordu; 3 SAĞLAM test bulgu diye raporlandı.

②'yi düzeltmek ①'i açığa çıkardı: doğru-pozitif sessizce kayboldu. ⇒ **tek kontrol yetmez**,
doğru-pozitif ve doğru-negatif BİRLİKTE koşulur. Bu dosya o iki kontrolü kalıcı kılar.

Ölçüm gerçek giriş noktasından yapılır: betik `subprocess` ile ÇAĞRILIR (fonksiyon elle çağrılmaz),
fixture'lar geçici bir sahte köke yazılır → gerçek `tests/` klasörüne hiç dokunulmaz ve betiğin
argüman/çıkış kablolaması da ölçülmüş olur.

⚠ Bu dosyanın KENDİ test adları bilerek "temiz" seçilmiştir: `vakum_tara.py` depoyu taradığında
`tests/` altındaki her dosyaya bakar, bu dosya da dahil. Adında gövdede geçmeyen bir vaka kodu
(`V6`, `s3` gibi) taşıyan bir test yazılsaydı araç kendi kalibrasyon dosyasını bulgu sayardı —
yayın tarayıcısının 2026-09-17'de düştüğü tuzağın aynısı (kendi fixture'larını sızıntı sanmıştı).

KAPSAM — bakılmayan: bulguların GERÇEKTEN kusur olup olmadığı (onu yalnız mutasyon söyler; bu araç
bir DARALTMA aracıdır, kanıt değil) · `ASSERT-YOK` boyutunun proje-özel assert yardımcılarını
tanıması dışındaki kenar vakaları · Python dışı test dosyaları · tarama hızı.
"""
from __future__ import annotations

import unittest

from _helpers import AXET_HOME, GeciciTest

BETIK = AXET_HOME / "maintenance" / "vakum_tara.py"


class VakumTaraKalibrasyon(GeciciTest):
    """Her test kendi sahte kökünü kurar: <tmp>/tests/test_ornek.py"""

    def tara(self, govde: str):
        """Fixture'ı yaz, betiği GERÇEK giriş noktasından koş, (rc, çıktı) döndür."""
        t = self.tmp / "tests"
        t.mkdir(exist_ok=True)
        (t / "test_ornek.py").write_text(govde, encoding="utf-8", newline="\n")
        r = self.calistir(BETIK, str(self.tmp), scripts_dir=BETIK.parent)
        return r.returncode, r.stdout

    # --- AD ↔ GÖVDE boyutu -----------------------------------------------------------------------

    def test_adda_vaat_edilen_kod_govdede_yoksa_bulgu(self):
        """DOĞRU POZİTİF. Ad 'V6 silinir' diyor; gövde yalnız V6d ölçüyor, V6'ya dair tek assert yok.

        Bu, gerçek depoda elle doğrulanmış bir bulgunun sadeleştirilmiş hâlidir
        (`test_V6_silinir_ama_V6d_silinmez`). Kaybolursa boyut körleşmiştir.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_V6_silinir_ama_V6d_silinmez(self):\n"
            '        self.assertEqual(self.d["x"]["vaka"], "V6d")\n')
        self.assertIn("AD-GOVDE", cikti, f"doğru-pozitif kayboldu — tarayıcı körleşmiş:\n{cikti}")
        self.assertIn("'V6'", cikti, f"bulgu var ama vaat edilen simge adlandırılmamış:\n{cikti}")

    def test_imza_satiri_govde_sayilmaz(self):
        """REGRESYON ①. Simgenin TEK geçtiği yer `def` satırının kendisi ise, bu ölçüm DEĞİLDİR.

        Gövde dilimi imzayı içerirse her test kendi adını kendi gövdesinde bulur ve hiçbir zaman
        bulgu üretilmez — araç sessizce hep 'temiz' der.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_V9_bir_sey_yapar(self):\n"
            "        self.assertTrue(True)\n")
        self.assertIn("AD-GOVDE", cikti,
                      f"imza satırı gövde sayılmış — her test kendi vaadini kendi adıyla kanıtlar:\n{cikti}")

    def test_bilesik_ad_icinde_gecen_simge_olculmus_sayilir(self):
        """REGRESYON ②. DOĞRU NEGATİF: `s3` simgesi `s3_cekirdek` içinde geçiyorsa vaat ÖLÇÜLMÜŞTÜR.

        Sınır sınıfına `_` dahil edilirse bu 3 sağlam test bulgu diye raporlanır (ölçüldü).
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_s3_cekirdek_dolu(self):\n"
            '        cekirdek = [u for u in self.harita["ust_siniflar"] if u.get("s3_cekirdek")]\n'
            "        self.assertEqual(13, len(cekirdek))\n")
        self.assertNotIn("AD-GOVDE", cikti, f"bileşik ad içindeki simge 'yok' sayılmış — yanlış pozitif:\n{cikti}")

    def test_bitisik_farkli_kod_vaadi_karsilamaz(self):
        """DOĞRU POZİTİF sınırı: `V6` ile `V6d` AYRI kodlardır; `V6d` geçmesi `V6`yı ölçmez.

        ②'nin düzeltmesi fazla geniş yapılırsa (sınırdan alfanümerik de çıkarılırsa) bu ayrım kaybolur
        ve ilk test de sessizce düşer. Bu testin görevi o aşırı-düzeltmeyi yakalamaktır.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_V4c_calisir(self):\n"
            '        self.assertEqual("V4c1", self.vaka)\n')
        self.assertIn("AD-GOVDE", cikti, f"'V4c1' geçmesi 'V4c' vaadini karşılamamalı:\n{cikti}")

    def test_uzun_buyuk_harfli_vurgu_sozcugu_vaat_sayilmaz(self):
        """DOĞRU NEGATİF (Z7 öncelik-2, 2026-09-18): büyük harfli Türkçe vurgu sözcüğü simge DEĞİLDİR.

        37 mutantın 37'si ölmüşken bu sınıf 32 yanlış bulgu üretiyordu. Ürün kodu bu sözcüğü büyük
        harfle içerse bile (mesajlarda geçer) 4 harften uzun parça vaat sayılmaz.
        """
        self.yaz(self.tmp / "scripts" / "urun.py", 'print("DOKUNMAZ")\n')
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_kural_ihlalinde_DOKUNMAZ(self):\n"
            "        self.assertEqual(1, self.sonuc)\n")
        self.assertNotIn("AD-GOVDE", cikti, f"vurgu sözcüğü vaat sayılmış — yanlış pozitif:\n{cikti}")

    def test_kisa_cikti_etiketi_urunde_varsa_vaattir(self):
        """DOĞRU POZİTİF: ad 'WARN' diyor, ürün gerçekten `[WARN]` basıyor, gövde onu ölçmüyor.

        Süzgeç fazla geniş yapılırsa (her büyük harfli parça atılırsa) bu gerçek daraltma adayı kaybolur.
        """
        self.yaz(self.tmp / "scripts" / "urun.py", 'print("[WARN] eksik kart")\n')
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_olmayan_kart_icin_WARN(self):\n"
            "        self.assertIn('eksik kart', self.cikti)\n")
        self.assertIn("'WARN'", cikti, f"üründe geçen kısa etiket vaadi kayboldu — tarayıcı körleşmiş:\n{cikti}")

    def test_kisa_turkce_sozcuk_urunde_gecse_de_vaat_sayilmaz(self):
        """DOĞRU NEGATİF: 'HİÇ' katlanınca 'HIC' olur ve ürün mesajında büyük harfle geçer; etiket değildir."""
        self.yaz(self.tmp / "scripts" / "urun.py", 'print("HİÇ basılmadı")\n')
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_bos_sinifta_satir_HIC_basilmaz(self):\n"
            "        self.assertEqual(0, self.sayi)\n")
        self.assertNotIn("AD-GOVDE", cikti, f"kısa Türkçe sözcük vaat sayılmış:\n{cikti}")

    # --- rc AYIRT EDİLEBİLİRLİĞİ boyutu ----------------------------------------------------------

    def test_sifirdan_farkli_rc_beklenip_sebep_dogrulanmazsa_bulgu(self):
        """`rc != 0` iddiası tek başına 'beklediğim sebepten başarısız oldu' demek değildir.

        Ölçülmüş tuzak: beklenen hata, ölçülmek istenenden ÖNCE gelen bambaşka bir arızadan doğar;
        kural tamamen kaldırılsa test yine yeşil kalır (vakum).
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_gecersiz_girdi_reddedilir(self):\n"
            "        r = self.calistir('olc')\n"
            "        self.assertEqual(2, r.returncode)\n")
        self.assertIn("RC-AYIRT-EDILEMEZ", cikti, f"ayırt edilemez rc iddiası yakalanmadı:\n{cikti}")

    def test_hata_metni_de_dogrulanirsa_bulgu_degil(self):
        """DOĞRU NEGATİF: rc'nin yanında HANGİ hata olduğu da doğrulanıyorsa iddia ayırt edilebilir."""
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_gecersiz_girdi_reddedilir(self):\n"
            "        r = self.calistir('olc')\n"
            "        self.assertEqual(2, r.returncode)\n"
            "        self.assertIn('kart bulunamadi', r.stdout)\n")
        self.assertNotIn("RC-AYIRT-EDILEMEZ", cikti, f"sebebi doğrulanan iddia bulgu sayılmış:\n{cikti}")

    # --- ASSERT-YOK boyutu -----------------------------------------------------------------------

    def test_hicbir_assert_yoksa_bulgu(self):
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_bir_sey_olur(self):\n"
            "        self.calistir('uygula')\n")
        self.assertIn("ASSERT-YOK", cikti, f"assert'siz test yakalanmadı:\n{cikti}")

    def test_projenin_kendi_assert_yardimcisi_taninir(self):
        """DOĞRU NEGATİF: `self.var(...)` gibi proje yardımcıları assert sayılır.

        Tanınmazsa araç 400+ testin çoğunu ASSERT-YOK diye raporlar ve okunamaz hâle gelir.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def var(self, yol):\n"
            "        self.assertTrue(yol.exists())\n"
            "    def test_bir_sey_olur(self):\n"
            "        self.var(self.hedef)\n")
        self.assertNotIn("ASSERT-YOK", cikti, f"proje assert yardımcısı tanınmamış:\n{cikti}")

    # --- kablolama -------------------------------------------------------------------------------

    def test_temiz_kokte_sifir_bulgu_ve_sayimlar_basilir(self):
        """Araç NE BAKTIĞINI söylemeli: taranan dosya ve fonksiyon sayısı sıfır-bulgu hâlinde de basılır.

        'KAPSAM BEYANI' kuralının bu araçtaki karşılığı: en kritik an sıfır-bulgu anıdır.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_hedef_yazilir(self):\n"
            "        self.assertTrue(self.hedef.exists())\n")
        self.assertEqual(0, rc)
        self.assertIn("1 test dosyasi", cikti)
        self.assertIn("1 test fonksiyonu", cikti)
        self.assertIn("Bulgu: 0", cikti)


    def test_bulgu_varken_de_cikis_sifir_kalir(self):
        """⛔ ANTI-GATE. Bu araç hiçbir akışı bloklamaz; bulgu bulsa da çıkış 0 döner.

        Çıkış kodunu bulguya bağlamak aracı sessizce bir gate'e çevirirdi. Yeni gate açmak
        ADR 0019 moratoryumunun 5 şartı + kullanıcının AÇIK onayını ister; o onay istenmedi.
        Bu test o kararın atlanamaz hâlidir.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_V6_silinir(self):\n"
            '        self.assertEqual(1, 1)\n')
        self.assertIn("AD-GOVDE", cikti, "önce bulgu üretildiğini doğrula (yoksa rc=0 anlamsız)")
        self.assertEqual(0, rc, "bulgu varken sıfırdan farklı çıkış = araç gate'e dönüşmüş")

    def test_kapsam_beyani_her_kosumda_basilir(self):
        """Projenin KAPSAM BEYANI kuralı: araç NEYE BAKMADIĞINI da söyler.

        En kritik an sıfır-bulgu anıdır — bulgu varken çıktı zaten okunur.
        """
        rc, cikti = self.tara(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_hedef_yazilir(self):\n"
            "        self.assertTrue(self.hedef.exists())\n")
        self.assertIn("Bulgu: 0", cikti)
        self.assertIn("KAPSAM — bakilanlar:", cikti)
        self.assertIn("KAPSAM — bakilmayanlar:", cikti)
        self.assertIn("MUTASYON", cikti, "aracın kanıt olmadığı uyarısı çıktıda kalmalı")


if __name__ == "__main__":
    unittest.main()
