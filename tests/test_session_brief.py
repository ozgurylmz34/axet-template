# -*- coding: utf-8 -*-
"""session_brief.py — bölümler, git'siz dizin, SAP paket bölümü, template içi."""
from __future__ import annotations

from _helpers import AXET_HOME, GeciciTest


class SessionBriefTest(GeciciTest):
    def brief(self, proje):
        r = self.calistir("session_brief.py", "--no-fetch", "--project-dir", str(proje))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return r.stdout

    def test_proje_bolumleri(self):
        d = self.proje()
        out = self.brief(d)
        for bolum in ("DURUM ÇAPASI (git):", "TEMPLATE:", "SAĞLIK:", "İŞ LİSTESİ:", "DEVİR NOTLARI:", "KAPSAM —"):
            self.assertIn(bolum, out)
        self.assertIn("son commit: (commit yok)", out)
        self.assertIn("davranış yüzeyi manifest'i yok", out)  # SAĞLIK doctor WARN'larını taşır
        self.assertNotIn("PAKET:", out)

    def test_sap_aktif_paket(self):
        d = self.proje(sap=True)
        self.paket(d, "ZSD001_CLC")
        f = d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8").replace("aktif paket: <…>", "aktif paket: `ZSD001_CLC`"), encoding="utf-8")
        out = self.brief(d)
        self.assertIn("aktif paket: ZSD001_CLC", out)

    def test_aktif_paket_deger_tablosu(self):
        import session_brief
        d = self.proje(sap=True)
        for ad in ("ZSD001", "ZBC000"):
            self.paket(d, ad)
        f = d / "AGENTS.md"
        sablon = f.read_text(encoding="utf-8")
        self.assertEqual(sablon.count("aktif paket: <…>"), 1)
        liste = "2 paket: ZBC000, ZSD001"
        tablo = [  # (AGENTS.md değeri, beklenen ilk satır parçası)
            # kontrol grubu: geçerli adlar
            ("ZSD001", "aktif paket: ZSD001"), ("`ZBC000`", "aktif paket: ZBC000"),
            ("YSD001", "aktif paket YSD001: SOURCE_CODES/ altında klasörü yok"),
            ("/ABC/PKG", "aktif paket /ABC/PKG: SOURCE_CODES/ altında klasörü yok"),
            # büyük harfli "YOK" biçimce geçerli bir Y paketi (Y + 2 karakter): ayırt edilemez, klasör-yok dalına düşer
            ("YOK", "aktif paket YOK: SOURCE_CODES/ altında klasörü yok"),
            # yazılmamış: yer tutucu, yeni_proje'nin işareti, boş
            ("<…>", "aktif paket AGENTS.md'de yazılı değil · " + liste),
            ("— henüz seçilmedi", "aktif paket AGENTS.md'de yazılı değil · " + liste),
            ("", "aktif paket AGENTS.md'de yazılı değil · " + liste),
            # geçersiz: paket adı sanılmamalı
            ("yok", "aktif paket ÖLÇÜLEMEDİ"), ("zsd001", "aktif paket ÖLÇÜLEMEDİ"),
            ("henüz seçilmedi", "aktif paket ÖLÇÜLEMEDİ"), ("ABCDEF", "aktif paket ÖLÇÜLEMEDİ"),
            ("SAPSD", "aktif paket ÖLÇÜLEMEDİ"), ("Z", "aktif paket ÖLÇÜLEMEDİ"),
        ]
        for deger, beklenen in tablo:
            with self.subTest(deger=deger):
                f.write_text(sablon.replace("aktif paket: <…>", f"aktif paket: {deger}"), encoding="utf-8")
                ilk = session_brief.aktif_paket(d)[0]
                self.assertIn(beklenen, ilk)
                if "ÖLÇÜLEMEDİ" in beklenen:
                    self.assertIn(liste, ilk)
                    self.assertIn(repr(deger), ilk)
        # değer satır sonunu aşıp sonraki satırdan okunmamalı
        f.write_text(sablon.replace("aktif paket: <…> (tüm paketler: `<source_root>/PAKETLER.md`) · transport: kullanıcı verir",
                                    "aktif paket:\nZSD001 sonraki satır"), encoding="utf-8")
        self.assertIn("yazılı değil", session_brief.aktif_paket(d)[0])

    def test_template_icinde_proje_bolumleri_yok(self):
        out = self.brief(AXET_HOME)
        self.assertIn("SAĞLIK:", out)
        self.assertNotIn("İŞ LİSTESİ:", out)

    # --- negatif ---
    def test_git_ve_is_listesi_yok(self):
        d = self.tmp / "bos"
        d.mkdir()
        out = self.brief(d)
        self.assertIn("git reposu değil — durum çapası ÖLÇÜLEMEDİ", out)
        self.assertIn("project_is-listesi.md yok", out)

    def test_aktif_paket_klasoru_yok(self):
        d = self.proje(sap=True)
        f = d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8").replace("aktif paket: <…>", "aktif paket: `ZSD999`"), encoding="utf-8")
        self.assertIn("aktif paket ZSD999", self.brief(d))


class DurumCapasiGitTest(GeciciTest):
    """rc taraması 2026-09-18 (Z15): durum çapası `git status` çıktısını yanlış okuyordu.
    ① `_git` çıktının tamamını baştan kırpıyordu ⇒ ilk porcelain satırının (" M a.txt") dosya
    adı 1 karakter kısalıyordu (ölçüldü: `.txt`). ② status rc≠0 (bozuk index) "temiz" deniyordu.
    KAPSAM — bakılmayan: zaman aşımı dalı (aynı rc≠0 yolundan geçer, ayrı test yok)."""

    def _repo(self):
        import session_brief
        d = self.tmp / "repo"
        d.mkdir()
        self.git(d, "init", "-q")
        self.yaz(d / "a.txt", "1")
        self.git(d, "add", "a.txt")
        self.git(d, "commit", "-q", "-m", "ilk")
        return session_brief, d

    def test_degisen_ilk_dosyanin_adi_tam(self):
        sb, d = self._repo()
        self.yaz(d / "a.txt", "2")
        satir = [s for s in sb.durum_capasi(d) if s.startswith("değişiklik:")][0]
        self.assertIn("— a.txt", satir)

    def test_izlenmeyen_dosya_kontrol_grubu(self):
        sb, d = self._repo()
        self.yaz(d / "b.txt", "x")
        satir = [s for s in sb.durum_capasi(d) if s.startswith("değişiklik:")][0]
        self.assertIn("— b.txt", satir)

    def test_bozuk_indexte_temiz_denmez(self):
        sb, d = self._repo()
        (d / ".git" / "index").write_bytes(b"bozuk")
        r = self.git(d, "status", "--porcelain", kontrol=False)
        self.assertNotEqual(r.returncode, 0, "enjeksiyon tutmadı — test hiçbir şey ölçmez")
        out = sb.durum_capasi(d)
        self.assertFalse(any("temiz" in s for s in out), out)
        self.assertTrue(any("ÖLÇÜLEMEDİ" in s and s.startswith("değişiklik:") for s in out), out)
