# -*- coding: utf-8 -*-
"""Yayın tarafı (P7): `guncelle/yayinlar.json` şeması · kalem-diff kapsamı · CHANGELOG.md üretimi ·
commit trailer'ı · `session_brief` günlük/kritik satırı.

Ölçüm gerçek giriş noktasından yapılır: yayın aracı `subprocess` ile ÇAĞRILIR (fonksiyon elle
çağrılmaz), KOK'u kendi konumundan türettiği için her test betiği **sahte bir depoya** kopyalar →
gerçek template klonuna hiç dokunulmaz ve çıkış kodu kablolaması da ölçülmüş olur.

⚠ Sentetik sızıntı örnekleri bu dosyada YOKTUR; olsaydı parçalı yazılmaları gerekirdi
(bkz. `tests/test_yayin_hazirla.py` başlığı — bu dosya da yayın paketine girer ve taranır).

KAPSAM — bakılan: şema denetiminin 10 dalı (her biri için KONTROL GRUBU'yla birlikte) ·
`min_axet` yayın→kalem mirası · ilk yayın (git init + commit + etiket + CHANGELOG + trailer) ·
ikinci yayın (var olan public klona yazma, ff-only tüketici, `guncelle.py plan`) ·
eşlemesiz dosya FAIL'i · kalemde bildirilen dosya değişmemişse FAIL · etiket yeniden kullanımı ·
yabancı origin reddi · `session_brief.template_bolumu` satır değişimi ve kritik hatırlatması ·
GERÇEK yayın kolundaki üç koruma (şema sorunu · `yayinlar.json` yok · kalem listesi boş) mesajıyla
birlikte · dolu hedefe yazılmaması · `tur=guvenlik ⇒ kritik` türetmesinin `guncelle.py` ile ayna
olması · ÖLÇÜLEMEDİ satırlarının kalem satırıyla birlikte korunması.

KAPSAM — bakılmayan: gerçek `git push` (araç push etmez, yalnız komutu yazar) · gerçek GitHub ·
`guncelle.py`'nin plan SONRASI komutları (sec/uygula/kapanis — P2'nin kendi takımı) ·
`session_brief`'in `saglik`/`aktif paket` bölümleri · ağ hatası dalı (fetch) ·
`yayin_hazirla`nın sızıntı desenleri (tests/test_yayin_hazirla.py ölçer).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

ARAC = AXET_HOME / "maintenance" / "yayin_hazirla.py"
GUNCELLE = AXET_HOME / "scripts" / "guncelle.py"
HARITA = AXET_HOME / "guncelle" / "harita.json"
SINIFLANDIR = AXET_HOME / "guncelle" / "siniflandir.py"
SESSION_BRIEF = AXET_HOME / "scripts" / "session_brief.py"

ZORUNLU = ["LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "LICENSES/Apache-2.0.txt",
           "README.md", "AGENTS.md", "kur.cmd", "kur.ps1", "yeni-proje.cmd", "aXet-Kur.cmd"]


def kalem(kid: str, **ek) -> dict:
    """Geçerli bir kalem — testler yalnız bozmak istedikleri alanı ezer (vakum-assertion'a karşı)."""
    k = {"id": kid, "baslik": f"deneme kalemi {kid}", "tur": "duzeltme", "kritik": False,
         "neden": "deneme gerekçesi", "dosyalar": ["scripts/doctor.py"], "gerektirir": [],
         "test": ["kok:test_doctor"]}
    k.update(ek)
    return k


# Yayın aracının ürettiği dosyalar (yayin_hazirla.URETILEN_DOSYALAR ile aynı küme).
# Z17 (2026-09-20) sonrası bunlar da kalem-diff kapsamındadır: beyan edilmezse yayın DURUR.
URETILEN = ["CHANGELOG.md", "guncelle/yayinlar.json", "guncelle/ci-durum.json"]


def yayinlar(*yayin: dict) -> dict:
    return {"surum": 1, "yayinlar": list(yayin)}


def yayin(etiket: str, *kalemler: dict, **ek) -> dict:
    y = {"etiket": etiket, "tarih": "2026-10-01", "kalemler": list(kalemler)}
    y.update(ek)
    return y


class YayinTemeli(GeciciTest):
    # Yayın aracı noreply olmayan kimlikle commit atmaz (yayın ⓐ) → akış testleri noreply kimlikle koşar.
    NOREPLY = "test@users.noreply.github.com"

    def setUp(self) -> None:
        super().setUp()
        self.env = dict(self.env, GIT_AUTHOR_EMAIL=self.NOREPLY, GIT_COMMITTER_EMAIL=self.NOREPLY)

    def depo(self, yayinlar_verisi: dict | None = None, motor: bool = False, **dosyalar: str) -> Path:
        """Sahte template deposu: zorunlu dosyalar + yayın aracı (+ istenirse güncelleme motoru)."""
        d = self.tmp / "depo"
        for z in ZORUNLU:
            self.yaz(d / z, "deneme\n")
        self.yaz(d / "scripts" / "doctor.py", "# sahte doctor v1\n")
        for yol, metin in dosyalar.items():
            self.yaz(d / yol.replace("__", "/"), metin)
        self.yaz(d / "maintenance" / "yayin_hazirla.py", ARAC.read_text(encoding="utf-8"))
        if yayinlar_verisi is not None:
            self.yaz(d / "guncelle" / "yayinlar.json",
                     json.dumps(yayinlar_verisi, ensure_ascii=False, indent=1) + "\n")
        if motor:
            self.yaz(d / "scripts" / "guncelle.py", GUNCELLE.read_text(encoding="utf-8"))
            self.yaz(d / "guncelle" / "harita.json", HARITA.read_text(encoding="utf-8"))
            self.yaz(d / "guncelle" / "siniflandir.py", SINIFLANDIR.read_text(encoding="utf-8"))
        return d

    def commitle(self, d: Path, mesaj: str = "deneme") -> None:
        if not (d / ".git").exists():
            self.git(d, "init", "-q", "-b", "main")
        self.git(d, "add", "-A")
        self.git(d, "commit", "-q", "--no-verify", "-m", mesaj)

    def arac(self, depo: Path, *args: str):
        return self.calistir(depo / "maintenance" / "yayin_hazirla.py", *args, cwd=depo)

    def dogrula(self, depo: Path):
        r = self.arac(depo, "--yalniz-dogrula")
        return r.returncode, self.cikti(r)


@unittest.skipUnless(ARAC.is_file(), "maintenance/yayin_hazirla.py yok (public sürümde maintenance/ dışlanır)")
class SemaTest(YayinTemeli):
    """Her negatif dalın yanında KONTROL GRUBU var: aynı fixture'ın bozulmamış hâli 0 dönmeli."""

    def test_gecerli_sema_exit_0(self):
        rc, c = self.dogrula(self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01")))))
        self.assertEqual(rc, 0, c)
        self.assertIn("SORUN: 0", c)

    def test_bos_yayin_listesi_gecerlidir(self):
        """İlk yayından ÖNCEKİ hâl: dosya var, liste boş — bu geçerli bir durumdur."""
        rc, c = self.dogrula(self.depo(yayinlar()))
        self.assertEqual(rc, 0, c)

    def test_guvenlik_kalemi_kritik_degilse_fail(self):
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", tur="guvenlik", kritik=False)))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("tur=guvenlik ise kritik:true zorunlu", c)
        # KONTROL GRUBU: yalnız `kritik` düzeltilince aynı fixture geçmeli
        iyi = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", tur="guvenlik", kritik=True)))
        self.assertEqual(0, self.dogrula(self.depo(iyi))[0])

    def test_neden_bos_ise_fail(self):
        rc, c = self.dogrula(self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", neden="  ")))))
        self.assertEqual(rc, 1, c)
        self.assertIn(".neden boş olamaz", c)

    def test_dosyalar_bos_ise_fail(self):
        rc, c = self.dogrula(self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", dosyalar=[])))))
        self.assertEqual(rc, 1, c)
        self.assertIn(".dosyalar boş olmayan yol listesi olmalı", c)

    def test_yinelenen_kalem_id_fail(self):
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01")),
                         yayin("v0.2.0", kalem("0.1.0-01")))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("kalem id yinelenmiş: 0.1.0-01", c)

    def test_gerektirir_tanimsiz_kaleme_fail(self):
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", gerektirir=["yok-boyle-bir-kalem"])))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("gerektirir tanımsız kaleme işaret ediyor", c)

    def test_gerektirir_sonraki_kaleme_fail(self):
        """İleriye dönük bağımlılık: tüketici onu hiçbir zaman seçemez."""
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", gerektirir=["0.2.0-01"])),
                         yayin("v0.2.0", kalem("0.2.0-01")))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("SONRAKİ bir kaleme işaret ediyor", c)
        # KONTROL GRUBU: GERİYE dönük bağımlılık meşru
        iyi = yayinlar(yayin("v0.1.0", kalem("0.1.0-01")),
                       yayin("v0.2.0", kalem("0.2.0-01", gerektirir=["0.1.0-01"])))
        self.assertEqual(0, self.dogrula(self.depo(iyi))[0])

    def test_capraz_yayin_gerektirir_WARNING_cikisi_etkilemez(self):
        """Z57: önceki yayının kalemine bağ şemaca geçerli (rc 0) ama bakımcıya WARNING basılır."""
        veri = yayinlar(yayin("v0.1.0", kalem("0.1.0-01")),
                        yayin("v0.2.0", kalem("0.2.0-01", gerektirir=["0.1.0-01"])))
        rc, c = self.dogrula(self.depo(veri))
        self.assertEqual(rc, 0, c)
        self.assertIn("SORUN: 0", c)
        self.assertIn("WARNING çapraz-yayın `gerektirir`: 0.2.0-01 (v0.2.0) → 0.1.0-01 (v0.1.0)", c)
        self.assertIn("UYARI: 1", c)

    def test_KONTROL_ayni_yayin_ici_gerektirir_WARNING_basmaz(self):
        veri = yayinlar(yayin("v0.1.0", kalem("0.1.0-01"),
                              kalem("0.1.0-02", gerektirir=["0.1.0-01"])))
        rc, c = self.dogrula(self.depo(veri))
        self.assertEqual(rc, 0, c)
        self.assertNotIn("WARNING çapraz-yayın", c)
        self.assertNotIn("UYARI:", c)

    def test_yayin_sirasi_tersse_fail(self):
        """Motor SON girdiyi en yeni sayar (scripts/guncelle.py:376) — sıra sözleşmedir."""
        bozuk = yayinlar(yayin("v0.2.0", kalem("0.2.0-01")),
                         yayin("v0.1.0", kalem("0.1.0-01")))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("eskiden yeniye sıralı olmalı", c)

    def test_dislanan_yol_beyani_fail(self):
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", dosyalar=["maintenance/IS-LISTESI.md"])))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("public'e girmeyen yolu bildiriyor", c)

    def test_uretilen_dosya_beyani_ARTIK_SERBEST(self):
        """Z17 (2026-09-20): üretilen dosyayı beyan etmek YASAK DEĞİL, ZORUNLU.

        Eski kural tam tersini söylüyordu (*"bu dosyalar yayın aracının çıktısıdır, kaleme ait
        değildir"*) ve `kapsam_dogrula` da onları denetimden muaf tutuyordu. İki kural birlikte
        kapalı bir çember kuruyordu: beyan etmeyince dosya tüketiciye ULAŞMIYOR, beyan edince
        şema hatası alıyordun. Ölçülen sonuç: v0.1.0 · v0.2.0 · v0.3.0 → üçünde de `CHANGELOG.md`
        ve `guncelle/yayinlar.json` tüketici klonuna hiç ulaşmadı.
        ⚠ Bu testin kendisi kör noktanın bekçisiydi: kuralı kaldıran biri ÖNCE bu testi kırar.
        """
        veri = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", dosyalar=list(URETILEN))))
        rc, c = self.dogrula(self.depo(veri))
        self.assertEqual(rc, 0, c)
        self.assertNotIn("üretilen dosyayı bildiriyor", c)

    def test_KONTROL_dislanan_yol_hala_fail(self):
        """Kontrol grubu: yol beyanı denetiminin TÜMÜ kalkmadı, yalnız üretilen-dosya kolu."""
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", dosyalar=["maintenance/IS-LISTESI.md"])))
        rc, c = self.dogrula(self.depo(bozuk))
        self.assertEqual(rc, 1, c)
        self.assertIn("public'e girmeyen yolu bildiriyor", c)

    def test_etiket_bicimi_fail(self):
        rc, c = self.dogrula(self.depo(yayinlar(yayin("0.1.0", kalem("0.1.0-01")))))
        self.assertEqual(rc, 1, c)
        self.assertIn("etiket `vX.Y.Z` biçiminde olmalı", c)

    def test_kapsam_beyani_basilir(self):
        rc, c = self.dogrula(self.depo(yayinlar()))
        self.assertEqual(rc, 0, c)
        self.assertIn("KAPSAM — bakılan:", c)
        self.assertIn("KAPSAM — bakılmayan:", c)


@unittest.skipUnless(ARAC.is_file(), "maintenance/yayin_hazirla.py yok")
class YayinAkisiTest(YayinTemeli):
    def ilk_yayin(self, depo: Path, hedef_ad: str = "yayin") -> tuple[Path, object]:
        hedef = self.tmp / hedef_ad
        r = self.arac(depo, "--hedef", str(hedef), "--ilk")
        return hedef, r

    # --- yayın ⓐ: commit kimliği ---------------------------------------------------------------------------
    def test_noreply_olmayan_kimlik_yayini_durdurur_hedef_bos_kalir(self):
        d = self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        self.commitle(d)
        kurumsal = "biri@" + "sirket.example"  # parçalı: yayın taraması bu dosyayı da tarar
        self.env = dict(self.env, GIT_AUTHOR_EMAIL=kurumsal)  # committer noreply kalır: yazar TEK BAŞINA yeter
        hedef, r = self.ilk_yayin(d)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("GIT_AUTHOR_IDENT: e-posta GitHub noreply adresi değil", c)
        self.assertNotIn("GIT_COMMITTER_IDENT", c)
        self.assertNotIn(kurumsal, c)  # kimlik izi çıktıya basılmaz
        self.assertFalse((hedef / ".git").exists(), "kimlik reddinde depo kurulmamalı")
        self.assertEqual([], list(hedef.iterdir()), "--ilk tekrar koşulabilsin diye hedef BOŞ kalmalı")

    def test_committer_kimligi_de_denetlenir(self):
        d = self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        self.commitle(d)
        self.env = dict(self.env, GIT_COMMITTER_EMAIL="biri@" + "sirket.example")
        hedef, r = self.ilk_yayin(d)
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("GIT_COMMITTER_IDENT: e-posta GitHub noreply adresi değil", self.cikti(r))

    def test_ilk_yayin_commit_etiket_changelog_trailer(self):
        d = self.depo(yayinlar(yayin("v0.1.0",
                                     kalem("0.1.0-01", baslik="doctor: sahte düzeltme"),
                                     kalem("0.1.0-02", tur="guvenlik", kritik=True,
                                           baslik="izin: sahte sıkılaştırma",
                                           dosyalar=["README.md"]))))
        self.commitle(d)
        hedef, r = self.ilk_yayin(d)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        # etiket atıldı
        self.assertEqual("v0.1.0", self.git(hedef, "tag", "-l").stdout.strip())
        # TEK commit (Q2: yayın başı tek commit)
        self.assertEqual(1, len(self.git(hedef, "log", "--oneline").stdout.strip().splitlines()))
        # commit trailer'ları: her kalem için bir satır
        mesaj = self.git(hedef, "log", "-1", "--format=%B").stdout
        self.assertIn("Guncelleme-Kalemi: 0.1.0-01", mesaj)
        self.assertIn("Guncelleme-Kalemi: 0.1.0-02", mesaj)
        # CHANGELOG üretildi ve TASARIM'ın istediği alanları taşıyor
        cl = (hedef / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## v0.1.0 — 2026-10-01", cl)
        self.assertIn("0.1.0-01 · doctor: sahte düzeltme (düzeltme)", cl)
        self.assertIn("**neden:** deneme gerekçesi", cl)
        self.assertIn("`scripts/doctor.py`", cl)
        self.assertIn("**test:** `kok:test_doctor`", cl)
        self.assertIn("**gerektirir:** —", cl)
        self.assertIn("★ 0.1.0-02", cl)          # kritik kalem işaretli
        # maintenance/ public'e girmedi
        self.assertFalse((hedef / "maintenance").exists(), "maintenance/ public kopyaya sızdı")
        # araç PUSH ETMEDİ
        self.assertIn("PUSH YAPILMADI", c)

    def test_min_axet_yayin_duzeyinden_kaleme_miras(self):
        """Motor yalnız KALEM düzeyini okur (guncelle.py:601); yayın düzeyi sessizce düşmemeli."""
        d = self.depo(yayinlar(yayin("v0.1.0",
                                     kalem("0.1.0-01"),                     # kendi min_axet'i YOK
                                     kalem("0.1.0-02", min_axet="9.9.9",    # kendi değeri KAZANMALI
                                           dosyalar=["README.md"]),
                                     min_axet="1.3.0")))
        self.commitle(d)
        hedef, r = self.ilk_yayin(d)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        veri = json.loads((hedef / "guncelle" / "yayinlar.json").read_text(encoding="utf-8"))
        kalemler = {k["id"]: k for k in veri["yayinlar"][0]["kalemler"]}
        self.assertEqual("1.3.0", kalemler["0.1.0-01"].get("min_axet"), "miras uygulanmadı")
        self.assertEqual("9.9.9", kalemler["0.1.0-02"].get("min_axet"), "kalemin kendi değeri ezildi")
        self.assertIn("**asgari aXet sürümü:** 1.3.0",
                      (hedef / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_yayinlar_json_yoksa_yayin_yapilmaz(self):
        """VAKUM ÖNLEMİ (ölçüldü 2026-09-18): yalnız `rc==1` + `.git yok` iddia edildiğinde korunan
        dal TAMAMEN SİLİNSE BİLE test yeşil kalıyordu — beklenen 1, kuralın kendisinden değil çok
        aşağıdaki `assert yayin is not None`'dan doğuyordu. Bu yüzden dalın KENDİ mesajı da iddia
        edilir; ham `Traceback` ise bir kullanıcı-yüzeyi kusurudur, çıktıda bulunmamalıdır."""
        d = self.depo(None)
        self.commitle(d)
        hedef, r = self.ilk_yayin(d)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("yayın kalemleri olmadan yayın yapılamaz", c)
        self.assertNotIn("Traceback", c, f"korunan dal yerine ham traceback ile durdu: {c}")
        self.assertFalse((hedef / ".git").exists(), "yayın kalemleri yokken git kuruldu")

    def test_bos_kalem_listesiyle_yayin_yapilmaz(self):
        """`guncelle/yayinlar.json` VAR ve ŞEMASI GEÇERLİ ama `"yayinlar": []` — ilk gerçek yayına
        kadarki CANLI hâl. Yayını, aşağıdaki `assert` değil, KENDİ mesajlı dalı durdurmalı
        (yayin_hazirla.py: "boş — yayınlanacak kalem yok"). Ölçüldü: o dal silindiğinde yayın yine
        olmuyor ama kullanıcı ham `AssertionError` traceback'i görüyordu.

        ⚠ `SemaTest.test_bos_yayin_listesi_gecerlidir` bu dalı KAPSAMAZ: o yalnız
        `--yalniz-dogrula` şemasının boş listeyi GEÇERLİ saydığını ölçer (ayrı kol)."""
        d = self.depo(yayinlar())
        self.commitle(d)
        hedef, r = self.ilk_yayin(d)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("yayınlanacak kalem yok", c)
        self.assertNotIn("Traceback", c, f"korunan dal yerine ham traceback ile durdu: {c}")
        self.assertFalse((hedef / ".git").exists(), "yayınlanacak kalem yokken git kuruldu")

    def test_sema_sorunu_gercek_yayin_yolunu_durdurur(self):
        """KABLOLAMA (kod ≠ kablolama): şema denetiminin 10 dalı `--yalniz-dogrula` koluyla
        ölçülüyor, o bayrak ise kopyalamadan ÖNCE ayrı bir koldan dönüyor. GERÇEK yayın kolundaki
        dal (yayin_hazirla.py: "YAYIN KALEMLERİ ŞEMA SORUNU" → çıkış 1) böylece TESTSİZ kalmıştı:
        ölçüldü (2026-09-18), o `return 1` kaldırıldığında takımın hiçbir testi kırmızı olmadı ve
        şema sorunu ekrana basılmasına rağmen yayın TAMAMLANDI (etiket atıldı).

        Mesaj iddiası ŞARTTIR: `rc==1` çok aşağıdaki bambaşka bir daldan da gelebilir."""
        bozuk = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", tur="guvenlik", kritik=False,
                                               gerektirir=["YOK-BOYLE-KALEM"])))
        d = self.depo(bozuk)
        self.commitle(d)
        hedef, r = self.ilk_yayin(d)
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("YAYIN KALEMLERİ ŞEMA SORUNU", c)
        self.assertFalse((hedef / ".git").exists(), "şema sorunluyken git geçmişi kuruldu")
        self.assertNotIn("Yayın commit'i:", c, "şema sorunluyken yayın commit'i atıldı")
        # KONTROL GRUBU: aynı fixture'ın YALNIZ şeması düzeltilince aynı akış yayına gider
        iyi = yayinlar(yayin("v0.1.0", kalem("0.1.0-01", tur="guvenlik", kritik=True)))
        d2 = self.depo(iyi)
        self.commitle(d2)
        hedef2, r2 = self.ilk_yayin(d2, "yayin-kontrol")
        self.assertEqual(r2.returncode, 0, self.cikti(r2))
        self.assertTrue((hedef2 / ".git").exists(), "kontrol grubunda yayın yapılmadı")

    def test_bos_olmayan_hedefe_yazilmaz(self):
        """`--ilk` yayında hedefin BOŞ olması korunur (üzerine yazılmaz). PRE-EXISTING guard
        (d1c35cd'de de vardı); P7 onu yalnız `else:` koluna taşıdı — testi buraya eklendi."""
        d = self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        self.commitle(d)
        hedef = self.tmp / "dolu-hedef"
        self.yaz(hedef / "onceki.txt", "dokunulmamalı\n")
        r = self.arac(d, "--hedef", str(hedef), "--ilk")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("hedef boş değil", c)
        self.assertEqual(["onceki.txt"], sorted(p.name for p in hedef.iterdir()),
                         "dolu hedefin üzerine yazıldı")
        self.assertEqual("dokunulmamalı\n", (hedef / "onceki.txt").read_text(encoding="utf-8"))

    # --- ikinci yayın simülasyonu (P7 kabul ölçütü) ---------------------------------------------
    def ikinci_yayina_hazirla(self) -> tuple[Path, Path, Path]:
        """(depo, public bare repo, yayınevi klonu) — ilk yayın yapılmış ve itilmiş hâlde."""
        d = self.depo(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))), motor=True)
        self.commitle(d)
        yayin1, r = self.ilk_yayin(d, "yayin1")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        bare = self.tmp / "public.git"
        self.git(self.tmp, "init", "-q", "--bare", str(bare))
        self.git(yayin1, "remote", "add", "origin", str(bare))
        self.git(yayin1, "push", "-q", "-u", "origin", "main", "--tags")
        return d, bare, yayin1

    def test_ikinci_yayin_ff_only_tuketici_ve_plan(self):
        d, bare, yayinevi = self.ikinci_yayina_hazirla()
        # tüketici ilk yayını klonlar
        tuketici = self.tmp / "tuketici"
        self.git(self.tmp, "clone", "-q", str(bare), str(tuketici))

        # ikinci yayın: SADECE doctor.py değişir ve bir kaleme bağlanır
        self.yaz(d / "scripts" / "doctor.py", "# sahte doctor v2 — düzeltildi\n")
        self.yaz(d / "guncelle" / "yayinlar.json",
                 json.dumps(yayinlar(yayin("v0.1.0", kalem("0.1.0-01")),
                                     yayin("v0.2.0", kalem("0.2.0-01", kritik=True,
                                     baslik="doctor: ikinci düzeltme"),
                                     # Z17: üretilen dosyalar da beyan edilmek ZORUNDA,
                                     # yoksa tüketici klonuna hiç ulaşmazlar.
                                     kalem("0.2.0-uv", baslik="yayın üstverisi",
                                           dosyalar=list(URETILEN), test=[]))),
                            ensure_ascii=False, indent=1) + "\n")
        self.commitle(d, "ikinci yayin hazirligi")
        r = self.arac(d, "--hedef", str(yayinevi), "--origin", str(bare))
        c = self.cikti(r)
        self.assertEqual(r.returncode, 0, c)
        self.assertIn("KALEM-DİFF KAPSAMI:", c)
        self.assertIn("0 sorun", c)
        self.git(yayinevi, "push", "-q", "origin", "main", "--tags")

        # (a) tüketici ff-only güncellenebiliyor mu (force push yok ⇒ doğrusal geçmiş)
        self.git(tuketici, "fetch", "-q", "--tags", "origin")
        ff = self.git(tuketici, "pull", "--ff-only", "-q", "origin", "main", kontrol=False)
        self.assertEqual(0, ff.returncode, f"ff-only pull başarısız: {ff.stderr}")
        self.assertIn("doctor v2", (tuketici / "scripts" / "doctor.py").read_text(encoding="utf-8"))

        # (b) %guncelle motoru: v0.1.0'da kalmış BAŞKA bir tüketici planı üretebiliyor mu
        eski = self.tmp / "tuketici2"
        self.git(self.tmp, "clone", "-q", str(bare), str(eski))
        self.git(eski, "checkout", "-q", "v0.1.0")
        self.git(eski, "checkout", "-q", "-B", "main", "v0.1.0")
        p = self.calistir(GUNCELLE, "--klon", str(eski), "--harita", str(HARITA), "plan", cwd=eski)
        pc = self.cikti(p)
        self.assertEqual(0, p.returncode, pc)
        plan = json.loads((eski / ".axet-guncelleme" / "plan.json").read_text(encoding="utf-8"))
        idler = sorted(k["id"] for k in plan["kalemler"])
        self.assertEqual(["0.2.0-01", "0.2.0-uv"], idler,
                         f"plan yalnız YENİ yayının kalemlerini içermeli: {plan}")
        kalem_01 = next(k for k in plan["kalemler"] if k["id"] == "0.2.0-01")
        self.assertTrue(kalem_01["kritik"], "kritik bayrağı motora geçmedi")
        self.assertEqual(["scripts/doctor.py"], [x["yol"] for x in kalem_01["dosyalar"]])
        # Z17 regresyonu: üretilen dosyalar artık PLANA giriyor. Eskiden hiçbir kaleme
        # bağlı olmadıkları için "beyansız EYLEM" sayılıp UYGULANMIYORLARDI — v0.1.0,
        # v0.2.0 ve v0.3.0'ın ÜÇÜNDE DE ölçüldü (tüketicinin CHANGELOG'u ilk kurulumdan
        # beri bayattı).
        uv = next(k for k in plan["kalemler"] if k["id"] == "0.2.0-uv")
        self.assertIn("CHANGELOG.md", [x["yol"] for x in uv["dosyalar"]],
                      f"üretilen dosyalar plana girmedi: {uv}")

        # (c) tüketici klonunda CHANGELOG.md SINIFSIZ kalmamalı — sınıfsız yol harita denetiminde FAIL'dir
        # (haritada `belge-changelog`; geliştirme reposunda dosya yok, bu yüzden ancak BURADA ölçülebilir)
        sn = self.calistir(tuketici / "guncelle" / "siniflandir.py", "--sinif", "CHANGELOG.md",
                           cwd=tuketici)
        self.assertEqual(0, sn.returncode, self.cikti(sn))
        self.assertEqual("belge-changelog", (sn.stdout or "").strip(),
                         f"CHANGELOG.md tüketici klonunda sınıfsız: {self.cikti(sn)}")

        # (d) Q3: kritik kalem varsayılan olarak SEÇİLİ gelir
        s = self.calistir(GUNCELLE, "--klon", str(eski), "--harita", str(HARITA), "sec", cwd=eski)
        sc = self.cikti(s)
        self.assertEqual(0, s.returncode, sc)
        secim = json.loads((eski / ".axet-guncelleme" / "secim.json").read_text(encoding="utf-8"))
        self.assertIn("0.2.0-01", json.dumps(secim, ensure_ascii=False),
                      f"kritik kalem varsayılan seçimde yok: {secim}")

    def test_eslemesiz_dosya_fail(self):
        """P7 kabul ölçütü: yayın diff'indeki bir dosya hiçbir kaleme ait değilse FAIL, commit YOK."""
        d, bare, yayinevi = self.ikinci_yayina_hazirla()
        onceki = self.git(yayinevi, "rev-parse", "HEAD").stdout.strip()
        self.yaz(d / "scripts" / "doctor.py", "# sahte doctor v2\n")
        self.yaz(d / "README.md", "eslemesiz degisiklik\n")          # HİÇBİR kalemde yok
        self.yaz(d / "guncelle" / "yayinlar.json",
                 json.dumps(yayinlar(yayin("v0.1.0", kalem("0.1.0-01")),
                                     yayin("v0.2.0", kalem("0.2.0-01"))),
                            ensure_ascii=False, indent=1) + "\n")
        self.commitle(d, "eslemesiz")
        r = self.arac(d, "--hedef", str(yayinevi), "--origin", str(bare))
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("eşlemesiz dosya (hiçbir kaleme ait değil): README.md", c)
        self.assertIn("Git geçmişi kurulmadı", c)
        self.assertEqual(onceki, self.git(yayinevi, "rev-parse", "HEAD").stdout.strip(),
                         "FAIL'e rağmen commit atıldı")
        self.assertEqual("v0.1.0", self.git(yayinevi, "tag", "-l").stdout.strip(),
                         "FAIL'e rağmen etiket atıldı")

    def test_kalemde_bildirilen_dosya_degismemisse_fail(self):
        d, bare, yayinevi = self.ikinci_yayina_hazirla()
        self.yaz(d / "scripts" / "doctor.py", "# sahte doctor v2\n")
        self.yaz(d / "guncelle" / "yayinlar.json",
                 json.dumps(yayinlar(yayin("v0.1.0", kalem("0.1.0-01")),
                                     yayin("v0.2.0", kalem("0.2.0-01",
                                                           dosyalar=["scripts/doctor.py", "kur.ps1"]))),
                            ensure_ascii=False, indent=1) + "\n")
        self.commitle(d, "fazla beyan")
        r = self.arac(d, "--hedef", str(yayinevi), "--origin", str(bare))
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("bu yayında DEĞİŞMEMİŞ: kur.ps1", c)

    def test_ayni_etiket_ikinci_kez_reddedilir(self):
        d, bare, yayinevi = self.ikinci_yayina_hazirla()
        self.yaz(d / "scripts" / "doctor.py", "# sahte doctor v2\n")
        self.commitle(d, "ayni etiket")          # yayinlar.json değişmedi → hâlâ v0.1.0
        r = self.arac(d, "--hedef", str(yayinevi), "--origin", str(bare))
        c = self.cikti(r)
        self.assertEqual(r.returncode, 1, c)
        self.assertIn("etiketi hedefte ZATEN VAR", c)

    def test_yabanci_origin_reddedilir(self):
        d, bare, yayinevi = self.ikinci_yayina_hazirla()
        r = self.arac(d, "--hedef", str(yayinevi), "--origin", "https://example.invalid/baska.git")
        c = self.cikti(r)
        self.assertEqual(r.returncode, 2, c)
        self.assertIn("origin adresi beklenenden farklı", c)
        self.assertTrue((yayinevi / "README.md").is_file(), "reddedilen hedefin içeriği silindi")


@unittest.skipUnless(SESSION_BRIEF.is_file(), "scripts/session_brief.py yok")
class SessionBriefGuncellemeTest(GeciciTest):
    """`session_brief` günlük kalem satırı + kritik hatırlatma (TASARIM §11 Q3/Q4).

    Ölçüm in-process: modül global'leri (AXET_HOME, önbellek) geçici bir klona bağlanır.
    KAPSAM — bakılmayan: gerçek ağ fetch'i · `saglik`/`PAKET` bölümleri."""

    def setUp(self) -> None:
        super().setUp()
        if str(AXET_HOME / "scripts") not in sys.path:
            sys.path.insert(0, str(AXET_HOME / "scripts"))
        import session_brief
        self.sb = session_brief
        self.klon = self.tmp / "axet"
        self.klon.mkdir()
        self.git(self.klon, "init", "-q", "-b", "main")
        self.yaz(self.klon / "README.md", "x\n")
        self.git(self.klon, "add", "-A")
        self.git(self.klon, "commit", "-q", "--no-verify", "-m", "ilk")
        # `origin/main` referansını elle kur: uzak depo olmadan `git show origin/main:...` çalışsın
        self.git(self.klon, "update-ref", "refs/remotes/origin/main", "HEAD")

    def yayinlari_yaz(self, veri: dict) -> None:
        self.yaz(self.klon / "guncelle" / "yayinlar.json",
                 json.dumps(veri, ensure_ascii=False, indent=1) + "\n")
        self.git(self.klon, "add", "-A")
        self.git(self.klon, "commit", "-q", "--no-verify", "-m", "yayinlar")
        self.git(self.klon, "update-ref", "refs/remotes/origin/main", "HEAD")

    def uygulananlari_yaz(self, kalemler: dict) -> None:
        self.yaz(self.klon / ".axet-guncelleme" / "uygulanan.json",
                 json.dumps({"surum": 1, "dosyalar": {}, "kalemler": kalemler}, ensure_ascii=False))

    def klon_geride(self, veri: dict | None, n: int = 5) -> None:
        """HEAD'i `origin/main`'den n commit geride bırakır ve upstream'i TANIMLAR.

        Bu kurulum olmadan `template_durumu` "upstream tanımlı değil — ÖLÇÜLEMEDİ" döner ve
        "N commit geride" satırı hiç ÜRETİLMEZ; o satırın korunup korunmadığını sınayan bir test
        de boş geçerdi (vakum-assertion). `veri` verilirse `guncelle/yayinlar.json` YALNIZ
        origin/main tarafında bulunur — tüketicinin gerçek hâli budur.
        """
        taban = self.git(self.klon, "rev-parse", "HEAD").stdout.strip()
        if veri is not None:
            self.yaz(self.klon / "guncelle" / "yayinlar.json",
                     json.dumps(veri, ensure_ascii=False, indent=1) + "\n")
            self.git(self.klon, "add", "-A")
            self.git(self.klon, "commit", "-q", "--no-verify", "-m", "yayinlar")
            n -= 1
        for i in range(n):
            self.yaz(self.klon / f"f{i}.txt", "x\n")
            self.git(self.klon, "add", "-A")
            self.git(self.klon, "commit", "-q", "--no-verify", "-m", f"c{i}")
        self.git(self.klon, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.git(self.klon, "remote", "add", "origin", str(self.tmp / "sahte-uzak"))
        self.git(self.klon, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
        self.git(self.klon, "config", "branch.main.remote", "origin")
        self.git(self.klon, "config", "branch.main.merge", "refs/heads/main")
        self.git(self.klon, "checkout", "-q", "-B", "main", taban)

    def bolum(self) -> list[str]:
        with mock.patch.object(self.sb, "AXET_HOME", self.klon), \
             mock.patch.object(self.sb, "GUNCELLEME_CACHE", self.tmp / "onbellek"):
            return self.sb.template_bolumu(False)

    def test_yayinlar_yoksa_bugunku_satir_korunur(self):
        """KONTROL GRUBU / vakum önlemi: ölçülemeyen durumda eski davranış AYNEN kalmalı."""
        satirlar = self.bolum()
        self.assertTrue(any("ÖLÇÜLEMEDİ" in s or "güncel" in s or "geride" in s for s in satirlar),
                        f"template satırı hiç üretilmedi: {satirlar}")
        self.assertFalse(any("güncelleme kalemi" in s for s in satirlar),
                         f"yayinlar.json yokken kalem satırı üretildi: {satirlar}")

    # --- "N commit geride" satırının YAŞAM DÖNGÜSÜ (regresyon 2026-09-18) ------------------------
    def test_kalem_tanimli_degilse_commit_geride_satiri_korunur(self):
        """ÖLÇÜLMÜŞ REGRESYON: `yayinlar.json` VAR ama kalem listesi BOŞ iken klonun geride
        olduğu SAKLANIYORDU ("template güncel" deniyordu).

        "hiç yayın kalemi tanımlı değil" ile "kalemler var, hepsi uygulanmış" AYNI ŞEY DEĞİLDİR:
        ilkinde commit sayısı satırının yerine geçecek bir bilgi YOKTUR, o yüzden korunur.
        Bu dal ilk gerçek yayına kadarki TÜM sürede canlıdır (bugünkü `yayinlar.json` boş)."""
        self.klon_geride(yayinlar())
        satirlar = self.bolum()
        self.assertTrue(any("5 commit geride" in s for s in satirlar),
                        f"klon 5 commit geride ama satır kayboldu: {satirlar}")
        self.assertFalse(any("bekleyen güncelleme kalemi yok" in s for s in satirlar),
                         f"hiç kalem tanımlı değilken 'güncel' denildi: {satirlar}")

    def test_bekleyen_kalem_varken_commit_satiri_yer_degistirir(self):
        """KONTROL GRUBU: kalem VARSA Q4 kararı aynen geçerli — commit sayısı satırı düşer."""
        self.klon_geride(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        satirlar = self.bolum()
        self.assertTrue(any("1 güncelleme kalemi bekliyor" in s for s in satirlar), satirlar)
        self.assertFalse(any("commit geride" in s for s in satirlar), satirlar)

    def test_hepsi_uygulanmissa_kalem_satiri_commit_satirinin_yerine_gecer(self):
        """TERS YÖN (kararı burada kilitliyorum): kalemler VAR, hepsi uygulanmış, klon yine geride.

        KARAR: bu NORMAL hâldir — `%guncelle` `origin/main`'i hiçbir zaman merge ETMEZ (TASARIM §2a),
        dolayısıyla BAŞARILI bir güncellemeden sonra klon DAİMA "N commit geride" görünür. O satır
        burada yanlış alarmdır; kalem satırı onun yerine geçer — Q4'ün asıl amacı budur."""
        self.klon_geride(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        self.uygulananlari_yaz({"0.1.0-01": {"etiket": "v0.1.0", "durum": "uygulandi"}})
        satirlar = self.bolum()
        self.assertTrue(any("bekleyen güncelleme kalemi yok" in s for s in satirlar), satirlar)
        self.assertFalse(any("commit geride" in s for s in satirlar), satirlar)

    def test_bekleyen_kalem_satiri_uretilir(self):
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"), kalem("0.1.0-02",
                                                                            dosyalar=["README.md"]))))
        satirlar = self.bolum()
        self.assertTrue(any("2 güncelleme kalemi bekliyor" in s for s in satirlar), satirlar)
        # Q4: "N commit geride" satırı YER DEĞİŞTİRDİ — iki bildirim olmasın
        self.assertFalse(any("commit geride" in s for s in satirlar), satirlar)

    def test_uygulanan_kalem_sayilmaz(self):
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"), kalem("0.1.0-02",
                                                                            dosyalar=["README.md"]))))
        self.uygulananlari_yaz({"0.1.0-01": {"etiket": "v0.1.0", "durum": "uygulandi"}})
        satirlar = self.bolum()
        self.assertTrue(any("1 güncelleme kalemi bekliyor" in s for s in satirlar), satirlar)

    def test_kritik_kalem_warn_satiri(self):
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", kritik=True,
                                                          baslik="izin sıkılaştırması"))))
        satirlar = self.bolum()
        self.assertTrue(any(s.startswith("WARN kritik güncelleme bekliyor: 0.1.0-01") for s in satirlar),
                        satirlar)

    def test_guvenlik_turu_kritik_sayilir(self):
        """TÜRETME: `kritik` alanı YOKKEN (varsayılan False) kritiklik YALNIZ `tur="guvenlik"`ten
        gelmeli (session_brief.py: `bool(k.get("kritik") or k.get("tur") == "guvenlik")`).

        VAKUM ÖNLEMİ (ölçüldü 2026-09-18): fixture `kritik=True` verdiği sürece `or` dalı hiç
        çalışmıyordu — türetme tamamen silinse bile bu test yeşil kalıyordu."""
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", tur="guvenlik"))))
        satirlar = self.bolum()
        self.assertTrue(any(s.startswith("WARN kritik güncelleme bekliyor: 0.1.0-01") for s in satirlar),
                        f"tur=guvenlik kalemi kritik sayılmadı: {satirlar}")
        # KONTROL GRUBU: türetmeyi tetiklemeyen sıradan kalem uyarı ÜRETMEMELİ (aynı klon, yeni içerik)
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", tur="duzeltme"))))
        self.assertFalse(any("WARN kritik" in s for s in self.bolum()),
                         "tur=duzeltme kalemi kritik sayıldı")

    def test_kritik_turetmesi_guncelle_motoruyla_ayni(self):
        """AYNA: `session_brief` ile `scripts/guncelle.py` kritikliği ELLE KOPYALANMIŞ AYNI
        ifadeyle türetir. Ayrışırsa motor kalemi kritik sayarken oturum özeti SUSAR — kullanıcı
        güvenlik kalemini hiç görmez; iki taraf da kendi içinde tutarlı olduğu için hiçbir
        davranış testi bunu yakalamaz.

        KAPSAM — bakılan: iki dosyada da türetme ifadesinin METİN olarak bulunması.
        KAPSAM — bakılmayan: ifadenin doğruluğu (onu davranış testleri ölçer) ve ortak bir
        yardımcıya çıkarılma ihtimali — öyle bir refactor'da bu test bilinçli olarak kırılır ve
        o an tek kaynağa göre güncellenir."""
        import re
        desen = re.compile(r'"kritik":\s*bool\(\s*(\w+)\.get\("kritik"\)\s*or\s*'
                           r'\1\.get\("tur"\)\s*==\s*"guvenlik"\s*\)')
        for etiket, yol in (("scripts/session_brief.py", SESSION_BRIEF), ("scripts/guncelle.py", GUNCELLE)):
            # assertRegex KULLANILMAZ: başarısızlıkta tüm dosyayı çıktıya döker, hata okunamaz olur.
            self.assertTrue(desen.search(yol.read_text(encoding="utf-8")),
                            f"{etiket}: `tur=guvenlik ⇒ kritik` türetmesi bulunamadı — iki kural AYRIŞTI "
                            f"(aranan desen: {desen.pattern})")

    def test_atlanan_kritik_kalem_gorunur_kalir(self):
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", kritik=True))))
        self.uygulananlari_yaz({"0.1.0-01": {"etiket": "v0.1.0", "durum": "atlandi"}})
        satirlar = self.bolum()
        self.assertTrue(any("atlandı (kritik): 0.1.0-01" in s for s in satirlar), satirlar)

    def test_olculemedi_satiri_kalem_satiriyla_birlikte_korunur(self):
        """Kalem satırı üretilirken ÖLÇÜLEMEDİ satırları KORUNUR (session_brief.py:
        `return yeni + [s for s in satirlar if "ÖLÇÜLEMEDİ" in s ...]`).

        Yalnız "commit sayısı" satırı yer değiştirir; ölçülemeyen bir üstbilgiyi yutmak çıktıyı
        hak etmediği kadar emin gösterir — 4be5bc9'da düzeltilen regresyonun AYNI SINIFI.
        Ölçüldü (2026-09-18): `+ [...]` kuyruğu düşürüldüğünde takımın hiçbir testi kırmızı
        olmadı; `test_bekleyen_kalem_satiri_uretilir` yalnız kalem satırının VAR, commit
        satırının YOK olduğunu ölçüyor — korunan satırı kimse iddia etmiyordu.

        Bu fixture'da upstream TANIMSIZDIR, o yüzden `template_durumu` ÖLÇÜLEMEDİ satırı üretir
        (kontrol grubu: aşağıdaki ilk assert o satırın kalemsiz hâlde de var olduğunu gösterir)."""
        temel = self.bolum()                       # kalem YOK: ÖLÇÜLEMEDİ satırı burada olmalı
        self.assertTrue(any("ÖLÇÜLEMEDİ" in s for s in temel),
                        f"fixture ÖLÇÜLEMEDİ satırı üretmiyor — test vakuma düşerdi: {temel}")
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        satirlar = self.bolum()
        self.assertTrue(any("güncelleme kalemi bekliyor" in s for s in satirlar),
                        f"kalem satırı üretilmedi: {satirlar}")
        self.assertTrue(any("ÖLÇÜLEMEDİ" in s for s in satirlar),
                        f"kalem satırı üretilince ÖLÇÜLEMEDİ satırı sessizce düştü: {satirlar}")

    def test_uygulanan_kritik_kalem_uyarmaz(self):
        """KONTROL GRUBU: iş bitince uyarı SUSMALI, yoksa satır gürültüye dönüşür."""
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", kritik=True))))
        self.uygulananlari_yaz({"0.1.0-01": {"etiket": "v0.1.0", "durum": "uygulandi"}})
        self.assertFalse(any("WARN kritik" in s for s in self.bolum()))

    # --- K-F (2026-09-18): yayını ZATEN içeren klon kalemi "bekliyor" saymaz ---------------------
    def test_iceren_klonda_kalem_bekliyor_sayilmaz(self):
        """ÖLÇÜLMÜŞ KUSUR (davranış testi 2026-09-18): taze klon v0.1.0'ı içerdiği hâlde oturum
        özeti "1 güncelleme kalemi bekliyor" diyordu; motor o yayını plana almadığı için kalem
        hiç `uygulandi` olmuyor ⇒ satır `%guncelle` sonrasında bile KALICIYDI."""
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        # kontrol grubu: etiket YOKKEN (çözülemez) kalem bekleyen sayılır — motorla aynı
        self.assertTrue(any("1 güncelleme kalemi bekliyor" in s for s in self.bolum()))
        self.git(self.klon, "tag", "v0.1.0", "HEAD")
        satirlar = self.bolum()
        self.assertTrue(any("bekleyen güncelleme kalemi yok" in s for s in satirlar), satirlar)
        self.assertFalse(any("kalemi bekliyor" in s for s in satirlar), satirlar)

    def test_icermeyen_klonda_kalem_bekliyor_kalir(self):
        """TERS YÖN: etiket origin/main'de, HEAD onun GERİSİNDE ⇒ kalem gerçekten bekliyor."""
        self.klon_geride(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        self.git(self.klon, "tag", "v0.1.0", "refs/remotes/origin/main")
        satirlar = self.bolum()
        self.assertTrue(any("1 güncelleme kalemi bekliyor" in s for s in satirlar), satirlar)

    def test_iceren_klonda_kritik_kalem_uyarmaz(self):
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01", kritik=True))))
        self.git(self.klon, "tag", "v0.1.0", "HEAD")
        self.assertFalse(any("WARN kritik" in s for s in self.bolum()))

    def test_motor_ice_aktarilamazsa_kalem_satiri_OLCULEMEDI_sayilir(self):
        """Ata testi yapılamıyorsa "kalem bekliyor" ya da "güncel" DENMEZ — eski satır aynen kalır."""
        self.yayinlari_yaz(yayinlar(yayin("v0.1.0", kalem("0.1.0-01"))))
        with mock.patch.dict(sys.modules, {"guncelle": None}):
            satirlar = self.bolum()
        self.assertFalse(any("güncelleme kalemi" in s for s in satirlar), satirlar)

    def test_ata_testi_motorla_TEK_KAYNAK(self):
        """AYNA: iki taraf da `guncelle.yayin_durumu`'nu çağırır; ata testi elle kopyalanmaz."""
        self.assertIn("yayin_durumu(", SESSION_BRIEF.read_text(encoding="utf-8"))
        motor = GUNCELLE.read_text(encoding="utf-8")
        self.assertIn("durum_y = yayin_durumu(", motor)
        self.assertEqual(motor.count('"merge-base", "--is-ancestor"'), 1,
                         "ata testi motorda birden fazla yerde — tek kaynak bozuldu")

    def test_main_template_bolumunu_cagirir(self):
        """KABLOLAMA: `main()` TEMPLATE bölümünü artık `template_bolumu`'ndan alıyor mu."""
        import contextlib
        import io
        tampon = io.StringIO()
        with mock.patch.object(self.sb, "template_bolumu", lambda fetch: ["ISARET-SATIRI"]), \
             mock.patch.object(self.sb, "saglik", lambda proj: ["saglik atlandi"]), \
             contextlib.redirect_stdout(tampon):
            with mock.patch.object(sys, "argv", ["session_brief.py", "--project-dir", str(self.klon),
                                                 "--no-fetch"]):
                rc = self.sb.main()
        self.assertEqual(0, rc)
        cikti = tampon.getvalue()
        self.assertIn("ISARET-SATIRI", cikti)


if __name__ == "__main__":
    unittest.main()
