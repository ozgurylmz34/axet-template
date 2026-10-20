# -*- coding: utf-8 -*-
"""yayin_hazirla.py — sızıntı taramasının sınıf/şiddet ayrımı (D16).

Ölçüm gerçek giriş noktasından yapılır: betik `subprocess` ile ÇAĞRILIR (fonksiyon elle çağrılmaz),
KOK'u kendi konumundan türettiği için her test betiği **sahte bir depoya** kopyalar → gerçek template
klonuna hiç dokunulmaz ve çıkış kodu kablolaması da ölçülmüş olur.

⚠ Sentetik sızıntı örnekleri PARÇALI yazılır (`"Orn" + "ekfirma"` gibi). Nedeni ölçüldü (2026-09-17):
bu dosya da yayın paketine girer ve taramadan geçer; örnekler düz yazılsaydı tarayıcı kendi test
fixture'larını gerçek sızıntı sanıp yayını BLOKLARDI (9 sahte BLOCKER). Parçalar test çalışırken
birleşir — yani taranan metin gerçek sızıntının aynısıdır, yalnız kaynak dosyada yan yana durmaz.

KAPSAM — bakılmayan: gerçek `git archive` yolu (`--ref`, commit'li kopya), gerçek push, ikili dosya
taraması, DISLANANLAR listesinin kendisi, NOTICE glob doğrulaması, ASCII dışı kullanıcı adları.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

BETIK = AXET_HOME / "maintenance" / "yayin_hazirla.py"

# Sahte depoda bulunması gereken dosyalar (betiğin ZORUNLU_DOSYALAR listesi) — eksikse ayrı bir BLOCKER doğar
# ve ölçtüğümüz şey desen değil, dosya eksikliği olurdu.
ZORUNLU = ["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "LICENSES/Apache-2.0.txt",
           "README.md", "AGENTS.md", "kur.cmd", "kur.ps1", "yeni-proje.cmd", "aXet-Kur.cmd"]

ORTAM = "AXET_SIZINTI_EK"
UYDURMA = "Orn" + "ekfirma"  # uydurma müşteri adı (gerçek ad bu depoya yazılmaz)

# Z193/Z204 sentetikleri (parçalı — bu dosya da taranır). İç ad UYDURMADIR; test, betik kopyasının desenine ekler.
SENTETIK_IC_AD = "Uydurma" + "_IcDepo"
SAHTE_TENANT = "qz7" + "firma.s4hana.cloud" + ".sap"
SAHTE_TRANSPORT = "QZ7" + "K912345"

TB, IB = "\\", "/"   # ters/ileri bölü — `C:\Users\...` örneklerini kaynak dosyada yan yana getirmemek için
KULLANICI_YOLU = "C:" + TB + "Users" + TB + "Orn" + "ekkisi" + TB + "proje"   # uydurma kullanıcı adı

# (sınıf adı, sentetik sızıntı satırı) — BLOCKER kalması gereken gerçek sızıntı sınıfları.
SIZINTI_ORNEKLERI = [
    ("iç kullanıcı/dizin", "Kullanıcı " + "tr1" + "1718 bu yolu kullanır."),
    ("iç repo adı", "DEV" + "_CORE junction bağlantısı buraya kurulur."),
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
        self.env.pop(ORTAM, None)   # makinedeki gerçek liste testi etkilemesin; her test kendi listesini kurar
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

    # --- Z133: satır numarası git'in satırıdır (Unicode ayraçlar satır bölmez) -----------------------------
    def test_unicode_ayrac_satir_numarasini_kaydirmaz(self):
        sizinti = SIZINTI_ORNEKLERI[1][1]   # "iç repo adı"
        for ad, ayrac in [("U+2028", " "), ("U+0085", "\x85"), ("form feed", "\x0c")]:
            with self.subTest(ayrac=ad):
                rc, c = self.tara(self.depo(**{"docs__a.md": f"bir{ayrac}iki\n{sizinti}\n"}))
                self.assertEqual(rc, 1, c)
                self.assertIn("iç repo adı: docs/a.md:2:", c)   # git'te 2. satır; splitlines 3 derdi

    def test_KONTROL_ayracsiz_dosyada_satir_numarasi(self):
        rc, c = self.tara(self.depo(**{"docs__a.md": f"bir\niki\n{SIZINTI_ORNEKLERI[1][1]}\n"}))
        self.assertEqual(rc, 1, c)
        self.assertIn("iç repo adı: docs/a.md:3:", c)

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

    # --- yerel müşteri/kurum listesi (2026-09-25): ad KODDA durmaz, git-dışı dosyadan / ortamdan okunur -----
    def test_yerel_liste_dosyasi_adi_blocker_yakalar(self):
        d = self.depo(**{"docs__a.md": "Proje: " + UYDURMA + " teslimatı.\n"})
        self.yaz(d / "maintenance" / "sizinti-yerel.txt", "# yorum satırı\n\n" + UYDURMA.lower() + "\n")
        rc, c = self.tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("yerel liste (müşteri/kurum): docs/a.md:1:", c)
        self.assertIn("KAPSAM — yerel liste (müşteri/kurum): 1 desen (dosya 1; içerik basılmaz)", c)
        self.assertFalse((self.tmp / "cikti" / "maintenance").exists(), "liste public kopyaya girmemeli")

    def test_ortam_degiskeni_listesi_yakalar(self):
        d = self.depo(**{"docs__a.md": "Kurum: " + UYDURMA + "\n"})
        self.env[ORTAM] = "baskaad;" + UYDURMA
        rc, c = self.tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("yerel liste (müşteri/kurum): docs/a.md:1:", c)
        self.assertIn("2 desen (ortam 2", c)

    def test_KONTROL_liste_varken_temiz_metin_bulgu_degil(self):
        d = self.depo(**{"docs__a.md": "Kurulum notu.\n"})
        self.yaz(d / "maintenance" / "sizinti-yerel.txt", UYDURMA + "\n")
        rc, c = self.tara(d)
        self.assertEqual(rc, 0, c)
        self.assertIn("BULGU: 0", c)

    def test_liste_yoksa_olculemedi_der(self):
        rc, c = self.tara(self.depo(**{"docs__a.md": "Proje: " + UYDURMA + "\n"}))
        self.assertEqual(rc, 0, c)   # tarama kipi: bulamaz ama SESSİZ değildir
        self.assertIn("YÜKLENMEDİ", c)
        self.assertIn("ÖLÇÜLEMEDİ", c)

    def test_liste_yoksa_gercek_yayin_baslamaz(self):
        d = self.depo()
        r = self.calistir(d / "maintenance" / "yayin_hazirla.py", "--hedef", str(self.tmp / "yayin"), "--ilk", cwd=d)
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("müşteri/kurum ad listesi yok", self.cikti(r))
        self.assertFalse((self.tmp / "yayin").exists(), "listesiz yayında hedefe dokunulmamalı")

    def test_liste_git_te_izleniyorsa_hata(self):
        d = self.depo()
        self.yaz(d / "maintenance" / "sizinti-yerel.txt", UYDURMA + "\n")
        self.git(d, "add", "maintenance/sizinti-yerel.txt")
        rc, c = self.tara(d)
        self.assertNotEqual(rc, 0, c)
        self.assertIn("git'te izleniyor", c)

    def test_gecersiz_regex_hata_ve_desen_basilmaz(self):
        d = self.depo()
        self.yaz(d / "maintenance" / "sizinti-yerel.txt", "gizliad(\n")
        rc, c = self.tara(d)
        self.assertNotEqual(rc, 0, c)
        self.assertIn("sizinti-yerel.txt:1 geçersiz regex", c)
        self.assertNotIn("gizliad", c)

    # --- KAPSAM beyanı: şiddet ayrımı çıktıda görünür -----------------------------------------------------
    def test_kapsam_beyani_siddet_ayrimini_soyler(self):
        rc, c = self.tara(self.depo())
        self.assertEqual(rc, 0, c)
        self.assertIn("KAPSAM — bakılan (BLOCKER = çıkış 1):", c)
        self.assertIn("KAPSAM — bakılan (WARNING = yalnız listelenir", c)
        self.assertIn("KAPSAM — bakılmayan:", c)

    # --- Z145ⓑ (2026-09-26): geliştirme deposunun KENDİSİ de public — `--depo-tara` tüm depoyu yerinde tarar ----
    # Vaka: yerel listedeki bir müşteri adı maintenance/IS-LISTESI.md üzerinden main'e girdi; yayın taraması
    # maintenance/'ı dışladığı için görmedi. Kip: BLOCKER = yerel liste · öbür DESENLER = UYARI · liste yoksa rc 1.
    def depo_tara(self, depo, *ek: str):
        r = self.calistir(depo / "maintenance" / "yayin_hazirla.py", "--depo-tara", *ek, cwd=depo)
        return r.returncode, self.cikti(r)

    def liste(self, d):
        self.yaz(d / "maintenance" / "sizinti-yerel.txt", "# yerel liste\n" + UYDURMA + "\n")

    def test_depo_tara_maintenance_icindeki_ad_blocker(self):
        d = self.depo(**{"maintenance__IS-LISTESI.md": "Z1: " + UYDURMA + " projesinde ölçüldü.\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("yerel liste (müşteri/kurum): maintenance/IS-LISTESI.md:1:", c)
        self.assertIn("BULGU: 1 (BLOCKER)", c)
        # kontrol grubu = Z145'in kendisi: yayın taraması aynı depoda bu adı GÖRMEZ (maintenance/ dışlanır)
        rc_yayin, c_yayin = self.tara(d)
        self.assertEqual(rc_yayin, 0, c_yayin)
        self.assertNotIn("IS-LISTESI.md", c_yayin)

    def test_KONTROL_depo_tara_temiz_depo_ve_liste_kendini_yakalamaz(self):
        d = self.depo(**{"maintenance__IS-LISTESI.md": "Z1: nötr metin.\n"})
        self.liste(d)                       # liste burada gitignore'lu DEĞİL → dışlama TAM yolla yapılmalı
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertIn("BULGU: 0", c)
        self.assertNotIn("sizinti-yerel.txt:", c)
        self.assertIn("maintenance/sizinti-yerel.txt .gitignore'da DEĞİL", c)   # ayrıca uyarılır

    def test_depo_tara_liste_disi_ayni_ad_baska_dosyada_yakalanir(self):
        """Dışlama dosya ADINA değil TAM yola bağlı: başka klasördeki aynı adlı dosya taranır."""
        d = self.depo(**{"docs__sizinti-yerel.txt": UYDURMA + "\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("yerel liste (müşteri/kurum): docs/sizinti-yerel.txt:1:", c)

    def test_depo_tara_izlenen_taranir_gitignore_lu_taranmaz(self):
        d = self.depo(**{"docs__izlenen.md": UYDURMA + "\n", "yerel__not.md": UYDURMA + "\n",
                         ".gitignore": "/yerel/\n/maintenance/sizinti-yerel.txt\n"})
        self.liste(d)
        self.git(d, "add", "docs/izlenen.md")
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("docs/izlenen.md:1:", c)
        self.assertNotIn("yerel/not.md", c)
        self.assertNotIn(".gitignore'da DEĞİL", c)   # kontrol: liste gitignore'lu → uyarı yok

    def test_depo_tara_desenler_uyari_cikisi_etkilemez(self):
        d = self.depo(**{"maintenance__sync.json": SIZINTI_ORNEKLERI[1][1] + "\n" + SIZINTI_ORNEKLERI[1][1] + "\n",
                         "maintenance__not.md": SIZINTI_ORNEKLERI[2][1] + "\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertRegex(c, r"iç repo adı: \d+ satır \(yalnız sayı")
        self.assertIn("maintenance/sync.json 2", c)                  # dosya başına sayı
        self.assertNotIn("iç repo adı: maintenance/sync.json", c)    # satırlar tek tek listelenmez
        self.assertIn("oturum bağlantısı: maintenance/not.md:1:", c)
        self.assertIn("BULGU: 0", c)

    def test_depo_tara_liste_yoksa_fail_closed(self):
        d = self.depo(**{"maintenance__IS-LISTESI.md": "Z1: " + UYDURMA + "\n"})
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("ÖLÇÜLEMEDİ", c)
        self.assertNotIn("BULGU: 0", c)

    def test_depo_tara_hedefle_birlikte_kullanim_hatasi(self):
        d = self.depo()
        self.liste(d)
        rc, c = self.depo_tara(d, "--hedef", str(self.tmp / "cikti"))
        self.assertEqual(rc, 2, c)
        self.assertIn("--depo-tara tek başına kullanılır", c)
        self.assertFalse((self.tmp / "cikti").exists())

    # --- L5 bug gate (2026-09-26): git'in listelediği ama `is_file()` False dönen yol SESSİZCE düşmez ------------
    # Gerçek MAX_PATH makinenin LongPathsEnabled ayarına bağlı (KopyaHatasiTest notu) ⇒ aynı sınıf deterministik
    # üretilir: izlenen dosya çalışma ağacından silinir → `ls-files --cached` listeler, `is_file()` False döner.
    def test_acilamayan_yol_kapsamda_olculemedi_sayilir(self):
        d = self.depo(**{"notlar__silinen.md": "nötr\n", "notlar__kalan.md": "nötr\n"})
        self.liste(d)
        self.git(d, "add", "notlar/silinen.md")
        (d / "notlar" / "silinen.md").unlink()
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)                       # çıkış kodu değişmez; görünürlük KAPSAM satırındadır
        self.assertIn("KAPSAM — ÖLÇÜLEMEDİ 1 yol", c)
        self.assertIn("ilk 5: notlar/silinen.md", c)
        rc2, c2 = self.tara(d)                           # yayın kipi (--calisma-agaci) aynı sınıfı aynı biçimde söyler
        self.assertIn("KAPSAM — ÖLÇÜLEMEDİ 1 yol", c2)
        self.assertIn("ilk 5: notlar/silinen.md", c2)

    def test_KONTROL_acilamayan_yol_yoksa_olculemedi_sifir(self):
        d = self.depo(**{"notlar__kalan.md": "nötr\n"})
        self.liste(d)
        self.git(d, "add", "notlar/kalan.md")
        rc, c = self.depo_tara(d)
        self.assertIn("KAPSAM — ÖLÇÜLEMEDİ 0 yol", c)   # sıfırken de basılır
        self.assertNotIn("ilk 5:", c)
        rc2, c2 = self.tara(d)
        self.assertIn("KAPSAM — ÖLÇÜLEMEDİ 0 yol", c2)

    def test_depo_tara_kapsam_beyani(self):
        d = self.depo()
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        for s in ("KAPSAM — BLOCKER (çıkış 1): yerel liste (müşteri/kurum): 1 desen",
                  "KAPSAM — dışlanan:", "KAPSAM — bakılmayan:", "git geçmişi"):
            self.assertIn(s, c)

    # --- Z193 (2026-10-19): iç repo adı (ve DESENLER'in öbür BLOCKER sınıfları) yayına GİREN yolda BLOCKER ----------
    # Vaka 2026-10-04: `tests/`'e düşen bir iç ad `--depo-tara`da BULGU 0 ile geçti, CI'ın public düzen taraması aynı
    # satırı BLOCKER saydı (6 iş kırmızı). Muafiyet artık yalnız DISLANANLAR yollarında (`dislanan_mi`).
    def sentetik_ic_ad_deposu(self, **dosyalar: str):
        """Betik kopyasındaki "iç repo adı" desenine UYDURMA bir ad eklenir — gerçek iç ad bu teste yazılmaz.
        Desen satırı bulunamazsa test sessizce boş ölçmesin diye ASSERT edilir."""
        d = self.depo(**dosyalar)
        kopya = d / "maintenance" / "yayin_hazirla.py"
        metin = kopya.read_text(encoding="utf-8")
        isaret = '(BLOCKER, "iç repo adı", r"'
        self.assertEqual(metin.count(isaret), 1, "iç repo adı desen satırı bulunamadı")
        kopya.write_text(metin.replace(isaret, isaret + SENTETIK_IC_AD + "|"), encoding="utf-8")
        self.liste(d)
        return d

    def test_depo_tara_ic_ad_yayin_yolunda_blocker(self):
        d = self.sentetik_ic_ad_deposu(**{"tests__test_ornek.py": "# " + SENTETIK_IC_AD + " junction\n"})
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("iç repo adı: tests/test_ornek.py:1:", c)
        self.assertIn("BULGU: 1 (BLOCKER)", c)

    def test_KONTROL_depo_tara_ic_ad_maintenance_icinde_bulgu_degil(self):
        d = self.sentetik_ic_ad_deposu(**{"maintenance__IS-LISTESI.md": "Z1: " + SENTETIK_IC_AD + " eşlemesi\n"})
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertIn("BULGU: 0", c)
        # (betik kopyası da sentetik adı taşır — desen satırı; o da dışlanan yolda sayılır)
        self.assertRegex(c, r"iç repo adı: \d+ satır \(yalnız sayı — dışlanan yol;[^\n]*maintenance/IS-LISTESI\.md 1")

    def test_depo_tara_muafiyet_dislananlar_listesinden_gelir(self):
        """Muafiyet `maintenance/` önekine değil DISLANANLAR'a bağlı: `_lab/` sayılır, benzer adlı yayın yolu sayılmaz."""
        d = self.sentetik_ic_ad_deposu(**{"_lab__not.md": SENTETIK_IC_AD + "\n",
                                          "docs__maintenance-notu.md": SENTETIK_IC_AD + "\n"})
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("iç repo adı: docs/maintenance-notu.md:1:", c)
        self.assertNotIn("iç repo adı: _lab/not.md", c)
        self.assertIn("_lab/not.md 1", c)

    def test_depo_tara_tum_blocker_siniflari_yayin_yolunda_blocker(self):
        d = self.depo(**{"docs__sizinti.md": "\n".join(s for _, s in SIZINTI_ORNEKLERI) + "\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn(f"BULGU: {len(SIZINTI_ORNEKLERI)} (BLOCKER)", c)
        for no, (sinif, _) in enumerate(SIZINTI_ORNEKLERI, 1):
            self.assertIn(f"{sinif}: docs/sizinti.md:{no}:", c)

    # --- Z204 (2026-10-19): yapısal kimlik izi (tenant host · transport no) — WARN-FIRST, token basılmaz ------------
    def test_depo_tara_yapisal_iz_uyari_cikis_kodu_ayni(self):
        d = self.depo(**{"docs__baglanti.md": "Sunucu: https://" + SAHTE_TENANT + "/sap/bc/adt\nİş: "
                         + SAHTE_TRANSPORT + " kaydı\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)                                 # warn-first: çıkış kodu değişmez
        self.assertIn("BULGU: 0", c)
        self.assertIn("yapısal kimlik izi: docs/baglanti.md:1 (tenant host)", c)
        self.assertIn("yapısal kimlik izi: docs/baglanti.md:2 (transport no)", c)
        self.assertNotIn(SAHTE_TENANT, c)                          # token basılmaz
        self.assertNotIn(SAHTE_TRANSPORT, c)
        (d / "docs" / "baglanti.md").unlink()                      # kontrol: aynı depo, iz yok → aynı çıkış kodu
        rc0, c0 = self.depo_tara(d)
        self.assertEqual(rc0, rc, c0)
        self.assertNotIn("yapısal kimlik izi:", c0)

    def test_KONTROL_depo_tara_yapisal_iz_yer_tutucular_sessiz(self):
        satirlar = ["https://<tenant>.s4hana.cloud" + ".sap", "https://abc123.eu10.hana.ondemand" + ".com",
                    "eu10.hana.ondemand" + ".com", "https://xxx.s4hana.cloud" + ".sap", "XXX" + "K900001",
                    "<SID>K9NNNNN", "SAH" + "K900123", "ZXX001_ORDERK123456"]
        d = self.depo(**{"docs__ornekler.md": "\n".join(satirlar) + "\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertNotIn("yapısal kimlik izi:", c)

    def test_depo_tara_bolge_bicimli_tenant_ara_etiketle_uyari(self):
        """Ö1 (bug gate 2026-10-19): bölge muafiyeti yalnız host TAM `<bölge>.<sonek>` iken — ara etiket varsa uyarı."""
        d = self.depo(**{"docs__idp.md": "https://ab12.authentication.eu10.hana.ondemand" + ".com/oauth\n"
                                          + "eu10.hana.ondemand" + ".com\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertIn("yapısal kimlik izi: docs/idp.md:1 (tenant host)", c)
        self.assertNotIn("docs/idp.md:2", c)                       # kontrol: yalın bölge alanı sessiz

    # --- F2 (bug gate 2026-10-19): JSON kaçışlı değer + üretilen CHANGELOG — yayın ve depo taraması AYNI görür ------
    def test_json_kacisli_kullanici_yolu_iki_taramada_blocker(self):
        d = self.depo(**{"docs__ayar.json": json.dumps({"ornek": {"yol": KULLANICI_YOLU}}) + "\n"})
        self.liste(d)
        self.assertNotIn(KULLANICI_YOLU, (d / "docs" / "ayar.json").read_text(encoding="utf-8"))  # ham metinde kaçışlı
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertIn("iç kullanıcı/dizin: docs/ayar.json:json$.ornek.yol:", c)
        rc_y, c_y = self.tara(d)                                    # yayın taraması aynı fonksiyonla aynı bulgu
        self.assertEqual(rc_y, 1, c_y)
        self.assertIn("iç kullanıcı/dizin: docs/ayar.json:json$.ornek.yol:", c_y)

    def test_KONTROL_json_yer_tutucu_yol_ve_bozuk_json_sessiz(self):
        yer_tutucu = "C:" + TB + "Users" + TB + "<kullanici>" + TB + "proje"
        d = self.depo(**{"docs__ayar.json": json.dumps({"yol": yer_tutucu}) + "\n",
                         "docs__bozuk.json": '{"yol": "' + KULLANICI_YOLU.replace(TB, TB * 2) + '"\n'})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)                                  # bozuk JSON çözülmez → yalnız ham (kaçışlı) satır
        self.assertNotIn("docs/ayar.json:", c)
        self.assertNotIn("docs/bozuk.json:", c)

    def test_json_ham_satirda_gorunen_deger_bir_kez_raporlanir(self):
        """Çözülmüş değer, ham satırla AYNI eşleşmeyi veriyorsa ikinci bulgu üretmez (bulgu sayısı şişmez)."""
        d = self.depo(**{"docs__musteri.json": json.dumps({"ad": UYDURMA}) + "\n"})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertEqual(1, c.count("docs/musteri.json:"), c)
        self.assertIn("docs/musteri.json:1:", c)                    # ham satır numarasıyla, json$ yoluyla değil

    def test_json_anahtari_host_olan_yapisal_iz_tokeni_basmaz(self):
        """Bug gate 3. tur: JSON yapısal iz konumu anahtar yolunu basmaz (anahtarın kendisi host olabilir) — `json#N`."""
        kacisli = SAHTE_TENANT.replace(".", TB + "u002e")             # ham satırda desen tutmaz, çözülmüş anahtarda tutar
        d = self.depo(**{"docs__k.json": '{"' + kacisli + '": 1}\n'})
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertIn("yapısal kimlik izi: docs/k.json:json#1 (tenant host)", c)
        self.assertNotIn(SAHTE_TENANT.split(".")[0], c)              # host etiketi hiçbir yerde basılmaz

    def test_bom_lu_json_cozulur_ve_bozuk_json_olculemedi_sayilir(self):
        """Bug gate 3. tur: BOM'lu JSON'un çözülmüş değerleri taranır; ayrıştırılamayan .json sessiz düşmez (KAPSAM)."""
        d = self.depo(**{"docs__bom.json": "﻿" + json.dumps({"yol": KULLANICI_YOLU}) + "\n",
                         "docs__bozuk.json": '{"yol": 1\n'})
        self.liste(d)
        self.assertEqual(b"\xef\xbb\xbf", (d / "docs" / "bom.json").read_bytes()[:3])
        for kip, (rc, c) in (("depo", self.depo_tara(d)), ("yayın", self.tara(d))):
            self.assertEqual(rc, 1, kip + c)
            self.assertIn("iç kullanıcı/dizin: docs/bom.json:json$.yol:", c, kip)
            self.assertIn("ÖLÇÜLEMEDİ 1 .json (ayrıştırılamadı", c, kip)
            self.assertIn("ilk 5: docs/bozuk.json)", c, kip)

    def test_KONTROL_gecerli_json_olculemedi_sifir(self):
        d = self.depo(**{"docs__ayar.json": json.dumps({"a": 1}) + "\n"})
        self.liste(d)
        for kip, (rc, c) in (("depo", self.depo_tara(d)), ("yayın", self.tara(d))):
            self.assertEqual(rc, 0, kip + c)
            self.assertIn("ÖLÇÜLEMEDİ 0 .json (ayrıştırılamadı", c, kip)

    def _yayinlar(self, baslik: str) -> str:
        return json.dumps({"surum": 1, "yayinlar": [{"etiket": "v0.0.1", "tarih": "2026-10-19", "kalemler": [
            {"id": "0.0.1-01", "baslik": baslik, "tur": "duzeltme", "neden": "deneme", "dosyalar": ["README.md"]}]}]})

    def test_depo_tara_uretilen_changelog_taranir(self):
        """Yalnız ÜRETİLEN biçimde oluşan metin (başlık + tür etiketi): JSON'da yok, CHANGELOG'da var."""
        d = self.depo(**{"guncelle__yayinlar.json": self._yayinlar(UYDURMA) + "\n"})
        self.yaz(d / "maintenance" / "sizinti-yerel.txt", UYDURMA + r" \(düzeltme\)" + "\n")
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 1, c)
        self.assertRegex(c, r"yerel liste \(müşteri/kurum\): CHANGELOG\.md\(üretilen←guncelle/yayinlar\.json\):\d+:")
        self.assertNotIn("guncelle/yayinlar.json:", c.split("BULGU:")[-1])   # JSON'un kendisi bu deseni taşımaz
        self.assertIn("KAPSAM — ek yüzey: üretilen CHANGELOG.md (←guncelle/yayinlar.json)", c)

    def test_KONTROL_depo_tara_yayinlar_yoksa_uretilen_olculemedi(self):
        d = self.depo()
        self.liste(d)
        rc, c = self.depo_tara(d)
        self.assertEqual(rc, 0, c)
        self.assertIn("üretilen CHANGELOG.md: ÖLÇÜLEMEDİ (guncelle/yayinlar.json yok)", c)


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


@unittest.skipUnless(BETIK.is_file(), "maintenance/yayin_hazirla.py yok (public sürümde maintenance/ dışlanır)")
class CiDurumUretTest(unittest.TestCase):
    """Z16 — yayına taşınan CI hükmü (`guncelle/ci-durum.json`) FAIL-SAFE üretilmeli.

    ⛔ ÖLÇÜLEN SINIF: bu kaydı tüketici `%guncelle` okuyup `olc --asama once` turunu ikame
    etmekte kullanır. Yanlışlıkla `hepsi_yesil: true` yazmak, ölçülmemiş bir güncellemeyi
    "ölçüldü" saydırır ⇒ her belirsizlik dalı `false` yazmalı ve SEBEBİNİ söylemeli.

    KAPSAM — bakılmayan: gerçek `gh` çağrısı ve ağ (burada taklit edilir) · `gh` çıktı
    biçiminin gelecekte değişmesi · `_ci_os()`/`_ci_python()` (ayrı, workflow dosyasından okur).
    """

    ETIKET = "v9.9.9"
    # CI adları (Z149 aşama 1, Z158 3 → 5 parça): kök ve kök-public 5 parça + foundation + skill + CI tamam — 13 iş.
    ADLAR = ([f"Testler (kok {k}/5 · Python 3.12)" for k in range(1, 6)]
             + [f"Testler (kok-public {k}/5 · Python 3.12)" for k in range(1, 6)]
             + ["Testler (foundation · Python 3.12)", "Testler (skill · Python 3.12)", "CI tamam"])
    YESIL = "".join(f"{a}\tsuccess\n" for a in ADLAR)

    def modul(self):
        spec = importlib.util.spec_from_file_location("yayin_hazirla_ci", BETIK)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def _uret(self, m, cikti: str, kod: int = 0, kapali: bool = False) -> dict:
        with mock.patch.object(m, "git_sessiz_komut",
                               side_effect=lambda argv: ((0, "git@github.com:o/r.git\n", "")
                                                         if argv[0] == "git" else (kod, cikti, "hata"))):
            kayit = m.ci_durum_uret("deadbee", self.ETIKET, None, kapali)
        return kayit[self.ETIKET]

    def test_1_hepsi_yesilse_TRUE(self):
        m = self.modul()
        y = self._uret(m, self.YESIL)
        self.assertTrue(y["hepsi_yesil"], y)
        self.assertEqual(len(y["takimlar"]), len(self.ADLAR))
        self.assertNotIn("not", y)

    def test_2_KONTROL_tek_takim_kirmiziysa_FALSE_ve_ADINI_soyler(self):
        m = self.modul()
        y = self._uret(m, self.YESIL.replace("success", "failure", 1))
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("Testler (kok 1/5 · Python 3.12)", y["not"])

    def test_3_KONTROL_ci_hala_kosuyorsa_FALSE_ve_BEKLE_der(self):
        m = self.modul()
        y = self._uret(m, self.YESIL.replace("success", "null", 1))
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("kosuyor", y["not"].lower(),
                      "null conclusion 'kırmızı' değil 'henüz bitmedi'dir — teşhis ayrılmalı")

    def test_4_KONTROL_asgari_takim_eksikse_FALSE(self):
        m = self.modul()
        y = self._uret(m, "Baska Is\tsuccess\n")
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("asgari", y["not"])

    def test_5_KONTROL_gh_hata_verirse_FALSE(self):
        m = self.modul()
        y = self._uret(m, "", kod=1)
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("okunamadi", y["not"])

    def test_6_KONTROL_hic_check_run_yoksa_FALSE(self):
        m = self.modul()
        y = self._uret(m, "")
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("check-run", y["not"])

    def test_7_KONTROL_kapaliysa_gh_HIC_SORULMAZ_ve_FALSE(self):
        m = self.modul()
        with mock.patch.object(m, "git_sessiz_komut",
                               side_effect=AssertionError("gh çağrılmamalıydı")):
            y = m.ci_durum_uret("deadbee", self.ETIKET, None, True)[self.ETIKET]
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("ci-durum-yok", y["not"])

    def test_9_isler_HIC_BASLAMADIYSA_kirmizi_takim_DEMEZ(self):
        """Z23 — kota/ödeme duvarında işler saniyeler içinde `failure` döner, hiç adım koşmaz.

        Bunu "yeşil olmayan takım" diye yazmak yanlış teşhistir: kod kırılmadı, ölçülmedi.
        """
        m = self.modul()
        y = self._uret(m, "".join(f"{a}\tfailure\t3\n" for a in self.ADLAR))
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("BASLAMADI", y["not"])
        self.assertNotIn("yesil olmayan", y["not"])

    def test_10_KONTROL_uzun_suren_failure_GERCEK_kirmizidir(self):
        m = self.modul()
        y = self._uret(m, "".join(f"{a}\t{'failure' if i == 0 else 'success'}\t{640 if i == 0 else 400}\n"
                                  for i, a in enumerate(self.ADLAR)))
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("yesil olmayan", y["not"])
        self.assertIn("Testler (kok 1/5 · Python 3.12)", y["not"])

    def test_11_KONTROL_sure_alani_yesil_hukmu_BOZMAZ(self):
        m = self.modul()
        y = self._uret(m, "".join(f"{a}\tsuccess\t600\n" for a in self.ADLAR))
        self.assertTrue(y["hepsi_yesil"], y)
        self.assertEqual({t["sonuc"] for t in y["takimlar"]}, {"success"})

    def test_12_KONTROL_public_duzen_kolu_EKSIKSE_FALSE(self):
        """Z27 — tüketici testleri public ağaçta koşar; o kol yoksa CI hükmü eksiktir."""
        m = self.modul()
        y = self._uret(m, "".join(f"{a}\tsuccess\n" for a in self.ADLAR if "kok-public" not in a))
        self.assertFalse(y["hepsi_yesil"])
        self.assertIn("kok-public", y["not"])

    def test_8_uretilen_dosyalar_ci_durumu_KAPSAR(self):
        """Kapsam muafiyeti tek kaynaktan gelmeli; unutulursa kalem-diff FAIL verirdi."""
        m = self.modul()
        self.assertIn(m.CI_DURUM_YOLU, m.URETILEN_DOSYALAR)


@unittest.skipUnless(BETIK.is_file(), "maintenance/yayin_hazirla.py yok (public sürümde maintenance/ dışlanır)")
class CiAsgariTakimlarWorkflowIleAyni(unittest.TestCase):
    """`CI_ASGARI_TAKIMLAR` ↔ `.github/workflows/testler.yml` (Z149 aşama 1). Workflow'da bir iş adı değişir de
    liste değişmezse `hepsi_yesil` hiç True olamaz (asgari takım "eksik") ⇒ her yayında HERKES yavaş tam ölçüme
    düşer — sessizce. Ters yön: listede olup workflow'da olmayan ad da aynı sonucu doğurur."""

    def test_adlar_workflow_matrisinden_turetilenle_ayni(self):
        import re
        wf = (AXET_HOME / ".github" / "workflows" / "testler.yml").read_text(encoding="utf-8")
        satirlar = re.findall(r"- \{takim: ([\w-]+), parca: '([^']*)', python: '([^']+)'\}", wf)
        self.assertGreaterEqual(len(satirlar), 3, "matris include satırları okunamadı — ölçüm anlamsız")
        self.assertIn("name: CI tamam", wf)
        beklenen = {f"Testler ({t}{' ' + p if p else ''} · Python {py})" for t, p, py in satirlar} | {"CI tamam"}
        spec = importlib.util.spec_from_file_location("yayin_hazirla_ad", BETIK)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(beklenen, set(m.CI_ASGARI_TAKIMLAR))
