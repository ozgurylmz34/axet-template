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


class AcilisBriefTest(GeciciTest):
    """Z105: session_brief özeti `.axet-code/acilis-brief.md`'ye de yazar; proje config'i onu her oturumda yükler."""

    def brief(self, proje):
        r = self.calistir("session_brief.py", "--no-fetch", "--project-dir", str(proje))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return r.stdout

    def test_brief_yazilir_ve_ozetle_ayni(self):
        d = self.proje()
        out = self.brief(d)
        self.assertEqual(out.rstrip().splitlines()[-1][:len("açılış brief'i yazıldı: .axet-code/acilis-brief.md (")],
                         "açılış brief'i yazıldı: .axet-code/acilis-brief.md (")
        metin = (d / ".axet-code" / "acilis-brief.md").read_text(encoding="utf-8")
        ilk = metin.splitlines()[0]
        self.assertRegex(ilk, r"^# AÇILIŞ BRIEF'İ — aXet · üretim: \d{4}-\d\d-\d\d \d\d:\d\d$")
        zaman = ilk.split("üretim: ")[1]
        self.assertIn(f"[OTURUM ÖZETİ — session_brief.py · {zaman} ·", out)  # stdout ile aynı an
        self.assertIn(f"`Açılış brief'i: {zaman}`", metin)
        for parca in ("`%skill`", "`— BAYAT`", "`[ÇEKİRDEK YOK]`", "kimlik", "DURUM ÇAPASI (git):", "SAĞLIK:",
                      "İŞ LİSTESİ:", "HATIRLATMALAR:", "KAPSAM —"):
            self.assertIn(parca, metin)
        self.assertNotIn("\n\n\n", metin)
        # git'e girmez: proje .axet-code/.gitignore'u onu dışlar
        r = self.git(d, "check-ignore", ".axet-code/acilis-brief.md", kontrol=False)
        self.assertEqual(r.returncode, 0, "brief git'e kapalı değil")

    def test_cekirdek_skill_kurali_acilisi_one_alir(self):
        """Z105 lab (2026-09-25, AXET_TEST, hüküm oturum DB'sinden): `%skill` ile açılan oturumda model §8'deki
        "SKILL.md'yi okumadan işe başlama" satırından skill akışına sapıyor, §0 açılışını atlıyordu (v0.5.9+v0.5.10
        ölçümlerinde 0/8). Açılışı YALNIZ bu satıra eklemek tuttu (2/2 skill; sonraki mesajlarda tekrar yok).
        Koşulun biçimi de ölçüldü: "ilk yanıtsa" diye yazılan koşul atlandı; modelin kendi mesajlarından
        doğrulayabileceği "bu konuşmada henüz kimlik satırı YAZMADIYSAN" biçimi tuttu.
        KAPSAM — bakılan: satırın metni. Bakılmayan: modelin fiilen uyduğu (canlı ölçüm, IS-LISTESI Z105)."""
        metin = (AXET_HOME / "core" / "00-temel.md").read_text(encoding="utf-8")
        satir = next((s for s in metin.splitlines() if s.startswith("- Kullanıcı `%<ad>` yazdıysa")), None)
        self.assertIsNotNone(satir, "§8 skill satırı bulunamadı")
        for parca in ("§0 açılışıyla başlar", "henüz kimlik satırı YAZMADIYSAN", "önceki mesajlarına bak",
                      "\"ilk yanıt mı\" diye yorumlama", "Açılış brief'i: <üretim saati>"):
            self.assertIn(parca, satir)

    def test_sablon_config_brief_yolunu_yukler(self):
        import json
        import doctor
        import session_brief
        cfg = json.loads((AXET_HOME / "templates" / "project" / ".axet-code.json").read_text(encoding="utf-8"))
        self.assertIn(session_brief.BRIEF_DOSYASI.as_posix(), cfg["options"]["context_paths"])
        self.assertEqual(session_brief.BRIEF_DOSYASI.as_posix(), doctor.BRIEF_DOSYASI)

    def test_kimlik_kaynagi_degil(self):
        """Brief kanaryayı ve doctor --live'ı yanıltmamalı: çekirdek kimliği ve kimlik etiketleri dosyada olmaz."""
        import session_brief
        from datetime import datetime
        govde = ["SESSION_NOTES son kayıt:", "  CORE-ID: AXET-CORE-9.9.9 · SAP-CORE-ID : X · PROJECT-MEMORY-ID: Y",
                 "  MEMORY-ID: Z · PROJECT-ID: P · SAP-STAMP-ID: S"]
        # bug gate MEDIUM-1 (ölçülen kaçaklar): markdown, küçük harf, tam genişlikli iki nokta, kanarya kopyası
        govde += ["  **CORE-ID**: AXET-CORE-0.8.0", "  core-id: axet-core-0.8.0", "  CORE-ID：AXET-CORE-0.8.0",
                  "  [AXET-CORE-0.8.0 · SAP: AXET-SAP-0.5.1 · proje: P1]", "  MEMORY-ID AXET-TEAM-MEMORY"]
        metin = session_brief.brief_metni(datetime(2026, 1, 2, 3, 4), govde)
        self.assertNotRegex(metin, r"(?i)\b(?:SAP-CORE|SAP-STAMP|PROJECT-MEMORY|PROJECT|MEMORY|CORE)-ID\W{0,3}[:：]")
        self.assertNotRegex(metin, r"(?i)AXET-(?:CORE|SAP|TEAM)-")
        self.assertIn("CORE-ID (etiket) AXET·CORE-9.9.9", metin)  # içerik okunur kalır, yalnız eşleşme bozulur
        self.assertIn("PROJECT-ID (etiket) P", metin)
        # kontrol grubu: yönerge başlığı çekirdek kimliğini/kanarya biçimini taşımaz
        self.assertNotIn("AXET-CORE", session_brief.brief_metni(datetime(2026, 1, 2, 3, 4), []))
        self.assertNotRegex(session_brief.brief_metni(datetime(2026, 1, 2, 3, 4), []), r"-ID\s*:")

    def test_boyut_siniri(self):
        import session_brief
        from datetime import datetime
        govde = [f"  satır {i} " + "ç" * 200 for i in range(200)]
        metin = session_brief.brief_metni(datetime(2026, 1, 2, 3, 4), govde)
        self.assertLessEqual(len(metin.encode("utf-8")), session_brief.BRIEF_AZAMI_BAYT + 300)
        self.assertIn("… KESİLDİ:", metin)
        self.assertTrue(metin.startswith("# AÇILIŞ BRIEF'İ"))
        kisa = session_brief.brief_metni(datetime(2026, 1, 2, 3, 4), govde[:3])  # kontrol grubu
        self.assertNotIn("KESİLDİ", kisa)

    def test_axet_code_klasoru_yoksa_yazilmaz(self):
        d = self.tmp / "bos"
        d.mkdir()
        out = self.brief(d)
        self.assertIn("açılış brief'i YAZILMADI: .axet-code/ yok", out)
        self.assertFalse((d / ".axet-code").exists())

    def test_template_icinde_yazilmaz(self):
        hedef = AXET_HOME / ".axet-code" / "acilis-brief.md"
        once = hedef.stat().st_mtime_ns if hedef.exists() else None
        out = self.brief(AXET_HOME)
        self.assertNotIn("açılış brief'i", out)
        self.assertEqual(once, hedef.stat().st_mtime_ns if hedef.exists() else None)

    def test_yazim_hatasi_eski_brief_korunur(self):
        import session_brief
        d = self.proje()
        hedef = d / ".axet-code" / "acilis-brief.md"
        hedef.write_text("ESKİ BRIEF\n", encoding="utf-8")
        from unittest import mock
        gercek_replace = session_brief.os.replace
        kaynaklar = []
        with mock.patch.object(session_brief.os, "replace",
                               side_effect=lambda a, b: (kaynaklar.append(str(a)), gercek_replace(a, b))[1]):
            self.assertIn("yazıldı", session_brief.brief_yaz(d, "YENİ\n"))  # kontrol grubu
        self.assertEqual(hedef.read_text(encoding="utf-8"), "YENİ\n")
        # bug gate LOW-1: geçici ad süreçe özgü (eşzamanlı iki süreç birbirinin geçici dosyasını taşımasın)
        self.assertEqual(len(kaynaklar), 1)
        self.assertIn(f".{session_brief.os.getpid()}.yaziliyor", kaynaklar[0])
        hedef.write_text("ESKİ BRIEF\n", encoding="utf-8")
        from unittest import mock
        with mock.patch.object(session_brief.os, "replace", side_effect=PermissionError(13, "kilitli")):
            sonuc = session_brief.brief_yaz(d, "YENİ\n")
        self.assertIn("açılış brief'i YAZILAMADI (PermissionError", sonuc)
        self.assertIn("ESKİ kalır", sonuc)
        self.assertEqual(hedef.read_text(encoding="utf-8"), "ESKİ BRIEF\n")
        self.assertEqual([p.name for p in hedef.parent.iterdir() if p.name.endswith(".yaziliyor")], [])

    def test_sap_profili_ve_yasaklar(self):
        import json
        import session_brief
        d = self.proje(sap=True)
        f = d / "sap-project.json"
        veri = json.loads(f.read_text(encoding="utf-8"))
        f.write_text(json.dumps(dict(veri, master_language="<ör. TR>", release="")), encoding="utf-8")
        satirlar = session_brief.sap_profili(d)  # doldurulmamış: yer tutucu + boş
        self.assertIn("master_language: YOK", satirlar[0])
        self.assertIn("/YOK ·", satirlar[0])
        self.assertIn("⛔ SAP KESİN YASAKLAR", satirlar[1])
        self.assertTrue(any(s.startswith("⚠ master_language doldurulmamış") for s in satirlar), satirlar)
        veri.update(sap_profile="s4_private", release="2025", master_language="TR", cleancore_policy="balanced")
        f.write_text(json.dumps(veri), encoding="utf-8")
        satirlar = session_brief.sap_profili(d)
        self.assertEqual(satirlar[0], "profil: s4_private/2025 · cleancore: balanced · master_language: TR")
        self.assertIn("master_language (TR)", satirlar[1])
        self.assertEqual(len(satirlar), 2)
        f.write_text("{bozuk", encoding="utf-8")
        self.assertIn("ÖLÇÜLEMEDİ", session_brief.sap_profili(d)[0])
        self.assertEqual(session_brief.sap_profili(self.proje("sapsiz")), [])  # SAP dışı projede bölüm yok
        self.assertIn("SAP:", self.brief(d))


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
