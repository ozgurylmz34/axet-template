# -*- coding: utf-8 -*-
"""yayin_hazirla.py — sızıntı taramasının sınıf/şiddet ayrımı (D16).

Ölçüm gerçek giriş noktasından yapılır: betik `subprocess` ile ÇAĞRILIR (fonksiyon elle çağrılmaz),
KOK'u kendi konumundan türettiği için her test betiği **sahte bir depoya** kopyalar → gerçek template
klonuna hiç dokunulmaz ve çıkış kodu kablolaması da ölçülmüş olur.

⚠ Sentetik sızıntı örnekleri PARÇALI yazılır (`"NT" + "T DA" + "TA"` gibi). Nedeni ölçüldü (2026-09-17):
bu dosya da yayın paketine girer ve taramadan geçer; örnekler düz yazılsaydı tarayıcı kendi test
fixture'larını gerçek sızıntı sanıp yayını BLOKLARDI (9 sahte BLOCKER). Parçalar test çalışırken
birleşir — yani taranan metin gerçek sızıntının aynısıdır, yalnız kaynak dosyada yan yana durmaz.

KAPSAM — bakılmayan: gerçek `git archive` yolu (`--ref`, commit'li kopya), gerçek push, ikili dosya
taraması, DISLANANLAR listesinin kendisi, NOTICE glob doğrulaması, ASCII dışı kullanıcı adları.
"""
from __future__ import annotations

import importlib.util
import shutil
import unittest
from pathlib import Path
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

BETIK = AXET_HOME / "maintenance" / "yayin_hazirla.py"

# Sahte depoda bulunması gereken dosyalar (betiğin ZORUNLU_DOSYALAR listesi) — eksikse ayrı bir BLOCKER doğar
# ve ölçtüğümüz şey desen değil, dosya eksikliği olurdu.
ZORUNLU = ["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "LICENSES/Apache-2.0.txt",
           "README.md", "AGENTS.md", "kur.cmd", "kur.ps1", "yeni-proje.cmd"]

TB, IB = "\\", "/"  # ters/ileri bölü — `C:\Users\...` örneklerini kaynak dosyada yan yana getirmemek için

# (sınıf adı, sentetik sızıntı satırı) — BLOCKER kalması gereken gerçek sızıntı sınıfları.
SIZINTI_ORNEKLERI = [
    ("şirket adı", "Bu dosya " + "NT" + "T DA" + "TA Business Solutions içindir."),
    ("iç kullanıcı/dizin", "Kullanıcı " + "tr1" + "1718 bu yolu kullanır."),
    ("iç repo adı", "DEV" + "_CORE junction bağlantısı buraya kurulur."),
    ("müşteri izi", "Musteri: " + "Trak" + "ya projesi."),
    ("oturum bağlantısı", "Bkz. https://claude.ai/code/" + "session" + "_abc123"),
    ("gerçek alan adı örneği", "Sunucu: https://your-sap-" + "server.com:44300"),
]


@unittest.skipUnless(BETIK.is_file(), "maintenance/yayin_hazirla.py yok (public sürümde maintenance/ dışlanır)")
class YayinHazirlaTest(GeciciTest):
    def depo(self, **dosyalar: str):
        """Sahte template deposu kurar: zorunlu dosyalar + verilen ek dosyalar. Betik depoya kopyalanır."""
        d = self.tmp / "depo"
        for z in ZORUNLU:
            self.yaz(d / z, "deneme\n")
        for yol, metin in dosyalar.items():
            self.yaz(d / yol.replace("__", "/"), metin)
        self.yaz(d / "maintenance" / "yayin_hazirla.py", BETIK.read_text(encoding="utf-8"))
        self.git(d, "init", "-q", "-b", "main")
        return d

    def tara(self, depo):
        """Gerçek giriş noktası: betiği çalıştırır, (rc, çıktı) döner. Hedef, depo DIŞINDA bir dizindir."""
        hedef = self.tmp / "cikti"
        if hedef.exists():
            shutil.rmtree(hedef)
        r = self.calistir(depo / "maintenance" / "yayin_hazirla.py", "--hedef", str(hedef),
                          "--calisma-agaci", "--yalniz-tara", cwd=depo)
        return r.returncode, self.cikti(r)

    # --- kontrol grubu: temiz depo ------------------------------------------------------------------------
    def test_temiz_depo_exit_0(self):
        rc, c = self.tara(self.depo(**{"docs__kurulum.md": "Kurulum notu.\n"}))
        self.assertEqual(rc, 0, c)
        self.assertIn("BULGU: 0", c)

    # --- gerçek sızıntı sınıfları BLOCKER kalır (sentetik pozitif kontrol) ---------------------------------
    def test_gercek_sizinti_siniflari_blocker_kalir(self):
        for sinif, satir in SIZINTI_ORNEKLERI:
            with self.subTest(sinif=sinif):
                rc, c = self.tara(self.depo(**{"docs__ornek.md": satir + "\n"}))
                self.assertEqual(rc, 1, c)
                self.assertIn("BULGU: 1 (BLOCKER)", c)
                # bulgu satırı biçimi: "<sınıf>: <yol>:<no>: <satır>" — KAPSAM listesindeki ada değil buna bakılır
                self.assertIn(f"{sinif}: docs/ornek.md:1:", c)

    # --- dışlanan dosyaya atıf: WARNING, çıkışı DEĞİŞTİRMEZ -----------------------------------------------
    def test_dislanan_dosyaya_markdown_atifi_warning(self):
        satir = "Ayrıntı: [bakım notu](" + "maintenance/IS-LISTESI.md)\n"
        rc, c = self.tara(self.depo(**{"docs__a.md": satir}))
        self.assertEqual(rc, 0, c)          # WARNING çıkış kodunu DEĞİŞTİRMEZ
        self.assertIn("UYARI: 1 (WARNING", c)
        self.assertIn("dışlanan dosyaya atıf: docs/a.md:1:", c)
        self.assertNotIn("(BLOCKER)", c)    # BLOCKER bulgu bloğu hiç basılmadı

    def test_dislanan_docs_markdown_atifi_warning(self):
        satir = "Bkz. [ölçümler](" + "axet-davranis-olcumleri.md)\n"
        rc, c = self.tara(self.depo(**{"docs__a.md": satir}))
        self.assertEqual(rc, 0, c)
        self.assertIn("dışlanan dosyaya atıf: docs/a.md:1:", c)

    # --- daraltma: markdown link OLMAYAN atıflar artık bulgu değil ----------------------------------------
    def test_markdown_link_olmayan_atif_bulgu_degil(self):
        ornekler = [  # tüketici klonunda dangling OLMAYAN biçimler (D16 teşhisi)
            ("yorum satırı", "# Kaynak: maintenance/IS-LISTESI.md:118 ölçümü\n"),
            ("ters tırnak", "Kilit dosyası (`maintenance/sync-lock.json`) tekrar gerekmez.\n"),
            ("glob/sınıf", '{"glob": ["maintenance/*"], "yukleme": "yüklenmez"}\n'),
            ("düz metin", "public sürüme girmez (maintenance/yayin_hazirla.py:27)\n"),
        ]
        for ad, satir in ornekler:
            with self.subTest(bicim=ad):
                rc, c = self.tara(self.depo(**{"docs__a.md": satir}))
                self.assertEqual(rc, 0, c)
                self.assertNotIn("UYARI", c)          # hiç WARNING üretilmedi
                self.assertNotIn("docs/a.md:1:", c)   # o dosya için hiçbir sınıfta bulgu yok

    # --- C:\Users\ kontrol grubu: yer tutucu geçer, gerçekçi ad yakalanır ---------------------------------
    def test_c_users_kontrol_grubu(self):
        tablo = [  # (metin, BLOCKER bekleniyor mu, açıklama)
            # --- muaf: yer tutucular ve çok kısa adlar
            (f"C:{TB}Users{TB}u", False, "tek harfli test yer tutucusu"),
            (f"C:{TB}Users{TB}u{TB}axet", False, "tek harfli yer tutucu + alt yol"),
            (f"C:{IB}Users{IB}u{IB}core{IB}00-temel.md", False, "ileri bölü + tek harfli yer tutucu"),
            (f"C:{TB}Users{TB}<kullanici>", False, "açılı yer tutucu"),
            (f"C:{TB}Users{TB}ad", False, "iki harf — gerçek kullanıcı adı sayılmaz"),
            (f"C:{TB}Users{TB}Öz", False, "Türkçe iki harf"),
            (f"C:{TB}Users{TB}ÖRNEK{TB}İş", False, "Türkçe yer-tutucu sözcük"),
            (f"C:{IB}Users{IB}user{IB}axet", False, "İngilizce yer-tutucu sözcük"),
            # --- yakalanmalı: gerçek kullanıcı adları (hepsi PARÇALI — bkz. dosya başlığı)
            (f"C:{TB}Users{TB}" + "tr1" + "1718", True, "gerçekçi kullanıcı adı"),
            (f"C:{TB}Users{TB}" + "ozgur" + f"{TB}axet", True, "gerçekçi kullanıcı adı + alt yol"),
            # ASCII dışı ad: eski `[A-Za-z]` deseninin GÖRMEDİĞİ sınıf (2026-09-17 ölçümü)
            (f"C:{TB}Users{TB}" + "Özgür" + f"{TB}İş", True, "Türkçe karakterli gerçek ad (ters bölü)"),
            (f"C:{IB}Users{IB}" + "Özgür" + f"{IB}İş{IB}core{IB}00-temel.md", True,
             "Türkçe karakterli gerçek ad (ileri bölü)"),
            (f"C:{IB}Users{IB}" + "tr1" + f"1718{IB}axet", True, "ileri bölü + gerçekçi ad"),
            (f"C:{TB}Users{TB}" + "ornekci", True, "yer tutucuya benzeyen ama gerçek olan ad"),
        ]
        for metin, beklenen, aciklama in tablo:
            with self.subTest(aciklama=aciklama):
                rc, c = self.tara(self.depo(**{"docs__a.md": f"Yol: {metin}\n"}))
                if beklenen:
                    self.assertEqual(rc, 1, c)
                    self.assertIn("iç kullanıcı/dizin: docs/a.md:1:", c)
                else:
                    self.assertEqual(rc, 0, c)
                    self.assertNotIn("docs/a.md:1:", c)

    # --- tr#####: C:\Users\ daraltması bu sınıfın öbür yarısını bozmadı mı --------------------------------
    def test_tr_numarasi_hala_blocker(self):
        rc, c = self.tara(self.depo(**{"docs__a.md": "Sahip: " + "tr1" + "1718\n"}))
        self.assertEqual(rc, 1, c)
        self.assertIn("iç kullanıcı/dizin: docs/a.md:1:", c)

    # --- KAPSAM beyanı: şiddet ayrımı çıktıda görünür -----------------------------------------------------
    def test_kapsam_beyani_siddet_ayrimini_soyler(self):
        rc, c = self.tara(self.depo())
        self.assertEqual(rc, 0, c)
        self.assertIn("KAPSAM — bakılan (BLOCKER = çıkış 1):", c)
        self.assertIn("KAPSAM — bakılan (WARNING = yalnız listelenir", c)
        self.assertIn("KAPSAM — bakılmayan:", c)


@unittest.skipUnless(BETIK.is_file(), "maintenance/yayin_hazirla.py yok (public sürümde maintenance/ dışlanır)")
class YayinHazirlaGercekAgacTest(GeciciTest):
    """Gerçek çalışma ağacı BLOCKER'sız mı — yayın öncesi kapının bugünkü durumu."""

    def test_gercek_calisma_agaci_blockersiz(self):
        hedef = self.tmp / "cikti"
        r = self.calistir(BETIK, "--hedef", str(hedef), "--calisma-agaci", "--yalniz-tara",
                          cwd=AXET_HOME, timeout=600)
        self.assertEqual(r.returncode, 0, self.cikti(r))


@unittest.skipUnless(BETIK.is_file(), "maintenance/yayin_hazirla.py yok (public sürümde maintenance/ dışlanır)")
class KopyaHatasiTest(GeciciTest):
    """Yayın ⓑ: kopyalama OSError'ı ham traceback değil, yolu ve sebebi söyleyen HATA olur.

    Bu sınıf dosya başlığındaki "gerçek giriş noktası" ilkesinin BİLİNÇLİ istisnasıdır: gerçek MAX_PATH hatası
    makinenin LongPathsEnabled ayarına bağlı, subprocess ile deterministik üretilemiyor ⇒ `copy2` taklit edilir."""

    def modul(self):
        spec = importlib.util.spec_from_file_location("yayin_hazirla_test", BETIK)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_kopyalama_oserror_anlamli_hataya_doner(self):
        m = self.modul()
        with mock.patch.object(m.shutil, "copy2", side_effect=FileNotFoundError(2, "sistem yolu bulamadı")):
            with self.assertRaises(SystemExit) as ctx:
                m.kopyala(self.tmp / "h", "HEAD", calisma_agaci=True)
        mesaj = str(ctx.exception.code)
        self.assertIn("HATA: kopyalanamadı:", mesaj)
        self.assertIn("FileNotFoundError", mesaj)
        self.assertNotIn("MAX_PATH", mesaj)  # kısa yolda yanlış ipucu verilmez

    def test_uzun_yolda_max_path_ipucu(self):
        m = self.modul()
        uzun = Path("C:/" + "k" * 300 + "/a.txt")
        self.assertIn("MAX_PATH", str(m.kopya_hatasi(uzun, FileNotFoundError(2, "x")).code))


if __name__ == "__main__":
    unittest.main()
