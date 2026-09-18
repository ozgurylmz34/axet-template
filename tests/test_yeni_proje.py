# -*- coding: utf-8 -*-
"""yeni_proje.py — sorarak SAP projesi kurulumu: git init, alan doldurma, ezmeme, dry-run, etkileşimli mod, doctor.
Bug gate (2026-09-14) bulguları: test adında bulgu no (h1, h2, m1, m2, l1-l4, oneri_*)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
from unittest import mock

from _helpers import AXET_HOME, SCRIPTS, GeciciTest  # önce: scripts/ yolunu ekler
import doctor
import new_project
import sap_stamp
import yeni_proje

PROJECT_PY = AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts" / "sapadt" / "project.py"
SABLON_SAP = next(s for s in (new_project.TEMPLATE / "AGENTS.md").read_text(encoding="utf-8").splitlines()
                  if s.startswith("- SAP"))


# bug gate MEDIUM-2: anahtar sözcüğü serbest metinde geçen, değer taşımayan `- SAP…` maddeleri (sahte ÖLÇÜLEMEDİ vermemeli).
# Son satır: iki harfli Türkçe sözcük ("ve") dil sanılmamalı — serbest biçimde yalnız BÜYÜK iki harf dil sayılır.
SERBEST_SAP_MADDELERI = ("- SAP profilini değiştirme", "- SAP profili kullanıcı onayı olmadan değişmez",
                         "- SAP: profil değişikliği yasak", "- SAP'de master language ile login dili aynı olmalı",
                         "- SAP: master language ve login dili aynı")
# re-gate MEDIUM-1: kanonik satırın yanında değer gibi görünen FARKLI serbest değer → ÖLÇÜLEMEDİ (sahte PASS yok).
# re-gate LOW-3: anahtar başka sözcüğün parçasıysa (userprofile) anahtar değil → tutarlı. (test_doctor'da aynı listeler.)
DEGER_BENZERI_SAP_MADDELERI = ("- SAP notu: master language en", "- SAP notu: master language EN.",
                               "- SAP notu: master_language en", "- SAP notu: sistem profili ecc.",
                               "- SAP notu: profil s4-public")
KELIME_SINIRI_SAP_MADDELERI = ("- SAP userprofile: SAP_ALL", "- SAP: yetkiprofili: Z_ALL")


def _sap_project_modulu():
    spec = importlib.util.spec_from_file_location("_test_sap_project", PROJECT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bayraklar(**ek) -> list[str]:
    alanlar = {"--sap-profile": "s4_private", "--release": "2023", "--master-language": "TR",
               "--cleancore-policy": "balanced", "--purpose": "Sevkiyat geliştirmeleri"}
    alanlar.update({k: v for k, v in ek.items() if k.startswith("--")})
    out = ["--no-input"]
    for k, v in alanlar.items():
        if v is not None:
            out += [k, v]
    return out


class YeniProjeTest(GeciciTest):
    def yeni(self, *args: str, **kw):
        return self.calistir("yeni_proje.py", *args, **kw)

    def etkilesimli(self, cevaplar: list[str], *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / "yeni_proje.py"), "--interactive", *args],
                              cwd=str(self.tmp), env=self.env, input="\n".join(cevaplar) + "\n", capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=300)

    def kurulum_dogru(self, d, ad: str) -> None:
        self.assertTrue((d / ".git").is_dir(), "git init yapılmadı")
        self.assertEqual(self.git(d, "config", "--get", "core.hooksPath").stdout.strip(), ".githooks")
        cfg, hata = _sap_project_modulu().load_sap_project(d)
        self.assertIsNone(hata, hata)
        self.assertEqual(cfg["project"], ad)
        agents = (d / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(doctor.yer_tutucular(agents), [])
        self.assertEqual(sap_stamp.denetle(agents)[0], "guncel", "kesin yasak damgası bozuldu")

    def agents_satir_degistir(self, d, eski: str, yeni: str) -> None:
        f = d / "AGENTS.md"
        metin = f.read_text(encoding="utf-8")
        self.assertIn(eski, metin)
        f.write_text(metin.replace(eski, yeni, 1), encoding="utf-8")

    def sap_json_guncelle(self, d, **alanlar) -> None:
        f = d / "sap-project.json"
        veri = json.loads(f.read_text(encoding="utf-8"))
        veri.update(alanlar)
        f.write_text(json.dumps(veri, indent=2, ensure_ascii=False), encoding="utf-8")

    def brief(self, d) -> str:
        r = self.calistir("session_brief.py", "--no-fetch", "--project-dir", str(d), cwd=d)
        return self.cikti(r)

    # --- mutlu yol ---
    def test_bayrakli_tam_kurulum_gitsiz_klasor(self):
        self.global_config(sap=True)
        d = self.tmp / "sevkiyat"
        r = self.yeni(str(d), *bayraklar(), "--rule", "Rapor çıktıları Excel'e aktarılabilir olmalı",
                      "--test-cmd", "python -m pytest")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.kurulum_dogru(d, "sevkiyat")
        agents = (d / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("- Amaç: Sevkiyat geliştirmeleri", agents)
        self.assertIn(f"sistem profili s4_private · sürüm 2023 · master_language: TR · aktif paket: "
                      f"{yeni_proje.AKTIF_PAKET_YOK}", agents)
        self.assertIn("- Test: `python -m pytest`", agents)
        self.assertIn(f"- Çalıştırma / derleme: {yeni_proje.KOMUT_YOK}", agents)
        self.assertIn("- Rapor çıktıları Excel'e aktarılabilir olmalı", agents)
        self.assertIn("- Depo: yerel", agents)
        self.assertIn("SONUÇ: 0 FAIL", r.stdout)
        # terminal adımları: script çalıştırmaz, sonda sırayla basar (doctor'un WARN satırı da manifest komutunu
        # içerdiği için sıra yalnız son bölümde ölçülür)
        self.assertIn("SENİN TERMİNALİNDE", r.stdout)
        son = r.stdout.split("SENİN TERMİNALİNDE", 1)[1]
        i1, i2, i3 = (son.find(s) for s in ("setup_credentials.py", "behavior_manifest.py\" generate", "axet-code -c"))
        self.assertTrue(0 < i1 < i2 < i3, son)
        self.assertIn("proje: sevkiyat", son)
        self.assertFalse((d / ".axet-code" / "behavior-manifest.json").exists(), "manifest üretilmemeli")
        self.assertFalse((d / ".conn_adt").exists())

    def test_etkilesimli_mutlu_yol(self):
        self.global_config(sap=True)
        d = self.tmp / "etk"
        cevaplar = [str(d), "", "s4", "s4_private", "2023", "tr", "", "", "Etkileşimli deneme", "", "", "", "",
                    "abaplint", "Kural A", "", "e"]
        r = self.etkilesimli(cevaplar)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("sap_profile 's4' geçersiz", r.stdout, "geçersiz cevap yeniden sorulmalı")
        self.kurulum_dogru(d, "etk")
        veri = json.loads((d / "sap-project.json").read_text(encoding="utf-8"))
        self.assertEqual((veri["master_language"], veri["cleancore_policy"]), ("TR", "balanced"))
        agents = (d / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("- Doğrulama / lint: `abaplint`", agents)
        self.assertIn("- Kural A", agents)
        self.assertIn("- Amaç: Etkileşimli deneme", agents)

    # --- negatif ---
    def test_etkilesimli_onay_verilmezse_yazmaz(self):
        d = self.tmp / "iptal"
        r = self.etkilesimli(["", "ecc", "EHP8", "EN", "", "Deneme", "", "", "", "", "", "", "h"], str(d))
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("İptal", r.stdout)
        self.assertFalse(d.exists())

    def test_terminal_yoksa_soru_sormaz(self):
        # stdin NUL: Windows'ta isatty() True döner (setup_credentials ölçümü) — yine de soru sorulmamalı.
        d = self.tmp / "tty"
        r = self.yeni(str(d))
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("eksik zorunlu alan", r.stdout)
        self.assertNotIn("Proje adı", r.stdout)
        self.assertFalse(d.exists())

    def test_eksik_bayrak_cikis_2_yazmaz(self):
        d = self.tmp / "eksik"
        r = self.yeni(str(d), *bayraklar(**{"--release": None, "--purpose": None}))
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("--release", r.stdout)
        self.assertIn("--purpose", r.stdout)
        self.assertFalse(d.exists())
        r2 = self.yeni(str(d), *bayraklar(**{"--cleancore-policy": None}))
        self.assertEqual(r2.returncode, 2, self.cikti(r2))
        self.assertIn("--cleancore-policy", r2.stdout)
        self.assertFalse(d.exists())

    def test_dry_run_hicbir_sey_yazmaz(self):
        d = self.tmp / "plan"
        r = self.yeni(str(d), *bayraklar(**{"--sap-profile": "ecc", "--release": "EHP8", "--cleancore-policy": None}),
                      "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("PLAN (dry-run", r.stdout)
        self.assertIn("git init -b main", r.stdout)
        self.assertFalse(d.exists())
        d.mkdir()
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(list(d.iterdir()), [], "var olan klasöre dry-run dosya yazdı")

    def test_gecersiz_dil_ve_profil(self):
        d = self.tmp / "gecersiz"
        for ek, beklenen in (({"--master-language": "TUR"}, "master_language 'TUR' geçersiz"),
                             ({"--sap-profile": "s4"}, "sap_profile 's4' geçersiz"),
                             ({"--cleancore-policy": "sıkı"}, "cleancore_policy 'sıkı' geçersiz")):
            with self.subTest(ek=ek):
                r = self.yeni(str(d), *bayraklar(**ek))
                self.assertEqual(r.returncode, 2, self.cikti(r))
                self.assertIn(beklenen, r.stdout)
                self.assertFalse(d.exists())
        r = self.yeni(str(d), *bayraklar(), "--name", "benim projem")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("dosya adı güvenli", r.stdout)

    def test_template_ve_alt_repo_reddedilir(self):
        hedef = AXET_HOME / "templates" / "yeni-proje-testi"
        r = self.yeni(str(hedef), *bayraklar())
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("template reposunun içinde", r.stdout)
        self.assertFalse(hedef.exists())
        kok = self.tmp / "ust"
        kok.mkdir()
        self.git(kok, "init", "-q", "-b", "main")
        alt = kok / "alt"
        r = self.yeni(str(alt), *bayraklar())
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("alt klasörü", r.stdout)
        self.assertFalse(alt.exists())

    def test_var_olan_kullanici_degeri_ezilmez(self):
        # release farkı kritik değil: korunur, uyarılır, çıkış 0; AGENTS.md dosyadaki değeri taşır.
        self.global_config(sap=True)
        d = self.proje("mevcut", sap=True)
        self.sap_json_guncelle(d, release="2021", cleancore_policy="<ör. balanced>")
        r = self.yeni(str(d), *bayraklar(**{"--release": "2023"}))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        sonra = json.loads((d / "sap-project.json").read_text(encoding="utf-8"))
        self.assertEqual(sonra["release"], "2021", "kullanıcı değeri ezildi")
        self.assertEqual(sonra["cleancore_policy"], "balanced", "yer tutuculu alan doldurulmadı")
        self.assertIn("[KORUNDU]", r.stdout)
        self.assertIn("UYARILAR", r.stdout)
        self.assertNotIn("ÇELİŞKİ", r.stdout)
        self.assertIn("sürüm 2021", (d / "AGENTS.md").read_text(encoding="utf-8"))

    def test_kontrol_grubu_new_project_tek_basina_yer_tutucu_birakir(self):
        d = self.tmp / "kontrol"
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        r = self.calistir("new_project.py", str(d), "--sap")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue(doctor.yer_tutucular((d / "AGENTS.md").read_text(encoding="utf-8")))
        self.assertEqual(doctor.sap_proje_dogrula(d)[0], "gecersiz")
        self.global_config(sap=True)
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.kurulum_dogru(d, "kontrol")

    # --- bug gate: HIGH-1 · kritik alanda korunan değer ≠ istenen ---
    def test_h1_kritik_celiski_cikis_1_ve_agents_jsondan(self):
        self.global_config(sap=True)
        durumlar = (("ml", {"master_language": "EN"}, "master_language: EN", "master_language: TR"),
                    ("profil", {"sap_profile": "ecc"}, "sistem profili ecc", "sistem profili s4_private"))
        for ad, json_degeri, beklenen, olmamali in durumlar:
            with self.subTest(durum=ad):
                d = self.proje(f"celiski-{ad}", sap=True)
                r = self.yeni(str(d), *bayraklar(), "--dry-run")
                self.assertEqual(r.returncode, 0, "kontrol: çelişki yokken dry-run 0 olmalı\n" + self.cikti(r))
                self.sap_json_guncelle(d, **json_degeri)
                once = (d / "AGENTS.md").read_text(encoding="utf-8")
                r = self.yeni(str(d), *bayraklar(), "--dry-run")
                self.assertEqual(r.returncode, 1, self.cikti(r))
                self.assertIn("ÇELİŞKİ", r.stdout)
                self.assertEqual((d / "AGENTS.md").read_text(encoding="utf-8"), once, "dry-run yazdı")
                r = self.yeni(str(d), *bayraklar())
                self.assertEqual(r.returncode, 1, self.cikti(r))
                self.assertIn("SONUÇ: 0 FAIL", r.stdout, "çıkış 1 doctor'dan değil çelişkiden gelmeli")
                self.assertIn("ÇELİŞKİ", r.stdout.split("SONUÇ: KURULUM EKSİK", 1)[1])
                agents = (d / "AGENTS.md").read_text(encoding="utf-8")
                self.assertIn(beklenen, agents, "AGENTS.md sap-project.json'un son hâlinden üretilmedi")
                self.assertNotIn(olmamali, agents)
                alan, deger = next(iter(json_degeri.items()))
                self.assertEqual(json.loads((d / "sap-project.json").read_text(encoding="utf-8"))[alan], deger,
                                 "kullanıcı değeri ezildi")
        # devam: kullanıcı json'u düzeltir (EN→TR) ama AGENTS.md satırı önceki koşudan EN kalır → tutarsızlık FAIL
        d = self.tmp / "celiski-ml"
        self.sap_json_guncelle(d, master_language="TR")
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("master_language EN ≠ sap-project.json TR", r.stdout)

    # --- bug gate: HIGH-2 · aktif paket değeri session_brief regex'ine takılmamalı ---
    def test_h2_session_brief_aktif_paket_yazili_degil(self):
        self.global_config(sap=True)
        d = self.tmp / "brief"
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 0, self.cikti(r))
        cikti = self.brief(d)
        self.assertIn("aktif paket AGENTS.md'de yazılı değil", cikti)
        self.assertNotIn("HEN", cikti)
        # kontrol grubu 1: yalnız new_project ile kurulan proje (şablon <…>) → aynı dal
        k = self.proje("yalniz-new-project", sap=True)
        self.assertIn("aktif paket AGENTS.md'de yazılı değil", self.brief(k))
        # kontrol grubu 2: eski değer ("henüz seçilmedi") eskiden HEN okunuyordu; artık geçersiz değer olarak raporlanır
        self.agents_satir_degistir(k, "aktif paket: <…>", "aktif paket: henüz seçilmedi")
        cikti = self.brief(k)
        self.assertIn("aktif paket ÖLÇÜLEMEDİ", cikti)
        self.assertNotIn("aktif paket HEN", cikti)

    # --- bug gate: MEDIUM-1 · yalnız şablondaki TAM satırlar değişir ---
    def test_m1_kullanici_satirlari_degismez(self):
        self.global_config(sap=True)
        d = self.proje("m1", sap=True)
        kullanici = {"- Amaç: <kısa açıklama>": "- Amaç: Stok raporu (eski metin: <kısa açıklama>)",
                     '- Depo: <remote adresi ya da "yerel">': '- Depo: <remote adresi ya da "yerel"> netleşince yazılacak',
                     "- Test: <komut>": "- Test: <komut> yerine make test",
                     # SAP satırı okunabilir kalmalı (YENİ-1: okunamayan satır FAIL); yer tutucu aktif pakette
                     SABLON_SAP: SABLON_SAP.replace("sistem profili <…>", "sistem profili s4_private · sürüm 2023")
                     .replace("master_language: <TR|EN>", "master_language: TR")
                     .replace("aktif paket: <…>", "aktif paket: <…> (sonra)")}
        for eski, yeni in kullanici.items():
            self.agents_satir_degistir(d, eski, yeni)
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 0, self.cikti(r))
        agents = (d / "AGENTS.md").read_text(encoding="utf-8")
        for yeni in kullanici.values():
            self.assertIn(yeni, agents.splitlines(), "kullanıcı satırı değişti")
        self.assertIn("- Teknoloji: SAP S/4HANA ABAP", agents, "kontrol: şablon satırı doldurulmalı")
        self.assertIn(f"- Çalıştırma / derleme: {yeni_proje.KOMUT_YOK}", agents)
        self.assertIn("[WARN] kullanıcı satırlarında yer tutucu", r.stdout)

    # --- bug gate: MEDIUM-2 · kullanıcı yer tutucusu uyarı, şablon yer tutucusu FAIL ---
    def test_m2_kullanici_yer_tutucusu_uyari_sablon_kalirsa_fail(self):
        self.global_config(sap=True)
        d = self.proje("m2", sap=True)
        self.agents_satir_degistir(d, "- <projeye özel kural>", "- Dil seçimi <TR|EN> ekip kararıdır")
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("[WARN] kullanıcı satırlarında yer tutucu (1): <TR|EN>", r.stdout)
        self.assertIn("[PASS] AGENTS.md şablon yer tutucusu: yok", r.stdout)
        self.assertIn("- Dil seçimi <TR|EN> ekip kararıdır", (d / "AGENTS.md").read_text(encoding="utf-8"))
        # kontrol grubu: şablon satırı kalan metin → FAIL listesi dolu (entegrasyon karşılığı: test_l2)
        # new_project'in kurduğu hâl (<PROJE_ADI>/<AXET_HOME> doldurulmuş) — ham şablon değil
        sablon = new_project._doldur((new_project.TEMPLATE / "AGENTS.md").read_text(encoding="utf-8"), "m2")
        self.assertEqual(len(yeni_proje.sablon_kalanlari(sablon)), len(yeni_proje.SABLON_ISARETLERI))
        self.assertEqual(yeni_proje.diger_yer_tutucular(sablon), [])

    # --- bug gate: LOW-1 · remote kimlik ayıklama ---
    def test_l1_http_kimlik_tablosu(self):
        tablo = [
            ("https://kul:p@ss@host/r.git", True, "https://host/r.git"),
            ("https://kul:ab/cd@host/r.git", True, "https://host/r.git"),
            ("https://TOKEN@host/r.git", True, "https://host/r.git"),
            ("HTTP://u:p@host/r", True, "HTTP://host/r"),
            ("https://host/ekip/r.git", False, "https://host/ekip/r.git"),
            ("ssh://git@host/r.git", False, "ssh://git@host/r.git"),
            ("git@host:ekip/r.git", False, "git@host:ekip/r.git"),
            ("yerel", False, "yerel"),
            # yeniden inceleme YENİ-4: parola her şemada, +http(s) şemaları, query token'ı
            ("ssh://u:pass@host/r.git", True, "ssh://u@host/r.git"),
            ("git+ssh://u:p@host/r.git", True, "git+ssh://u@host/r.git"),
            ("git+https://TOKEN@host/r.git", True, "git+https://host/r.git"),
            ("https://host/r.git?private_token=abc&ref=main", True, "https://host/r.git?ref=main"),
            ("https://host/r.git?Token=abc", True, "https://host/r.git"),
            ("https://host/r.git?password=x#k", True, "https://host/r.git#k"),
            ("https://host/r.git?access_token=abc", True, "https://host/r.git"),
            # bug gate Y-b: ayrıştırılamayan adres fail-closed (sır var sayılır); fragment'teki token anahtarları
            ("https://ghp_abc@[::1/x", True, "https://[::1/x"),
            ("https://host/r.git#access_token=abc", True, "https://host/r.git"),
            ("https://host/r.git#bolum&Token=abc", True, "https://host/r.git#bolum"),
            # bug gate BLOCKER-1: parolada '#' → urlsplit parolanın geri kalanını fragment sayar; önek sızmamalı
            ("https://kul:Pa#password=x@host/r.git", True, "https://host/r.git"),
            ("https://kul:p#a&token=z@host/r.git", True, "https://host/r.git"),
            ("https://kul:p?x@host/r.git", True, "https://host/r.git"),
            # http dışı şemada parolada '#' (HEAD'de de (False, parola açıkta) dönüyordu) → fail-closed, kimlik atılır
            ("ssh://u:p#a@host/r.git", True, "ssh://host/r.git"),
            # kontroller: sır taşımayan query/fragment, IPv6 host, zone id, ssh kullanıcı adı + port kabul
            ("https://host/r.git?ref=main", False, "https://host/r.git?ref=main"),
            ("https://host/r.git#bolum", False, "https://host/r.git#bolum"),
            ("https://host/r.git#L10", False, "https://host/r.git#L10"),
            ("ssh://git@host:22/r.git", False, "ssh://git@host:22/r.git"),
            ("https://[::1]:8443/r.git", False, "https://[::1]:8443/r.git"),
            ("https://[fe80::1%25eth0]/r.git", False, "https://[fe80::1%25eth0]/r.git"),
            ("ssh://git@[::1]:22/r.git", False, "ssh://git@[::1]:22/r.git"),
            # re-gate LOW-2: urlsplit baştaki C0/boşluğu atar, \t\r\n'yi her yerden siler → şema aynı normalize dizgeden okunmalı
            ("\x1bhttps://ghp_TOK@host/r", True, "https://host/r"),
            ("\x01https://ghp_TOK:x@host/r", True, "https://host/r"),
            ("ht\ttps://ghp_TOK@host/r", True, "https://host/r"),
            # re-gate 4: http dışı şemada parolada '/' ya da '@' (urlsplit netloc'u erken keser) → fail-closed, kimlik atılır
            ("ssh://u:p/q@host/r", True, "ssh://host/r"),
            ("git+ssh://u:pa/ss@host/r.git", True, "git+ssh://host/r.git"),
            ("file://u:p/q@host/r", True, "file://host/r"),
            ("ssh://u:p@s/s@host/r", True, "ssh://host/r"),
            # yanlış pozitif kontrolleri (re-gate 4)
            ("file:///C:/x/r.git", False, "file:///C:/x/r.git"),
            ("git@github.com:o/r.git", False, "git@github.com:o/r.git"),
        ]
        for url, kimlik, temiz in tablo:
            with self.subTest(url=url):
                self.assertEqual(yeni_proje.http_kimlik(url), (kimlik, temiz))
        # önerilen (temiz) değer hiçbir sır parçası taşımaz
        for url, kimlik, _ in tablo:
            if not kimlik:
                continue
            with self.subTest(sizinti=url):
                temiz = yeni_proje.http_kimlik(url)[1]
                for parca in ("kul", "Pa", "pass", "password", "token", "TOKEN", "ghp_", "TOK", "u:p", "pa/ss", "\x1b", "\x01"):
                    self.assertNotIn(parca, temiz)
        # re-gate LOW-2: kontrol karakterli metin d_repo/d_metin'de reddedilir (AGENTS.md'ye ve terminale gitmez)
        self.assertIsNone(yeni_proje.d_repo("https://host/r.git"), "kontrol grubu")
        for ham in ("\x1bhttps://host/r.git", "https://host/r.git\x7f", "yerel\x00", "ye\trel"):
            with self.subTest(kontrol=repr(ham)):
                self.assertIn("kontrol karakteri", yeni_proje.d_repo(ham) or "")
                self.assertIn("kontrol karakteri", yeni_proje.d_metin(True)(ham) or "")
        d = self.tmp / "repo-kimlik"
        for url in ("https://kul:p@host/r.git", "https://TOKEN@host/r.git", "ssh://u:pass@host/r.git",
                    "git+https://TOKEN@host/r.git", "https://host/r.git?private_token=abc", "https://ghp_abc@[::1/x",
                    "https://host/r.git#access_token=abc"):
            with self.subTest(repo=url):
                r = self.yeni(str(d), *bayraklar(**{"--repo": url}), "--dry-run")
                self.assertEqual(r.returncode, 2, self.cikti(r))
                self.assertIn("kimlik kısmı olmadan", r.stdout)
                self.assertFalse(d.exists())
        r = self.yeni(str(d), *bayraklar(**{"--repo": "ssh://git@host/r.git"}), "--dry-run")
        self.assertEqual(r.returncode, 0, "kontrol: ssh kullanıcı adı reddedilmemeli\n" + self.cikti(r))

    def test_l1_depo_onerisi_origin(self):
        ortam = {k: self.env[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
        d = self.tmp / "remote"
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        self.git(d, "remote", "add", "origin", "https://kullanici:gi@zli@git.ornek.invalid/ekip/proje.git")
        with mock.patch.dict(os.environ, ortam):
            self.assertEqual(yeni_proje.depo_onerisi(d), "https://git.ornek.invalid/ekip/proje.git")
        # bug gate BLOCKER-1 uçtan uca: parolada '#' olan origin → öneri ve dry-run özetinde parola parçası YOK.
        # Gate F1 (adım 4 fix): bu biçim fail-closed kesim dalından geçer (`https://host:abc/r@x` → `https://x` ile aynı dal)
        # → temizlenen adres güvenilir değil, öneri 'yerel' + adresi basmayan uyarı.
        self.git(d, "remote", "set-url", "origin", "https://kul:Pa#password=x@git.ornek.invalid/ekip/proje.git")
        with mock.patch.dict(os.environ, ortam):
            self.assertEqual(yeni_proje.depo_onerisi(d), "yerel")
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertRegex(r.stdout, r"\n  depo +yerel\n")
        self.assertIn("origin adresi güvenle temizlenemedi", r.stdout)
        for parca in ("kul", "Pa#", "password"):
            self.assertNotIn(parca, r.stdout)
        # re-gate LOW-2 uçtan uca: baştaki ESC şemayı gizleyip token'ı dry-run özetine taşımamalı
        self.git(d, "remote", "set-url", "origin", "\x1bhttps://ghp_TOKSECRET@git.ornek.invalid/e/p.git")
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("https://git.ornek.invalid/e/p.git", r.stdout)
        self.assertNotIn("ghp_", r.stdout)
        self.assertNotIn("\x1b", r.stdout)
        r = self.yeni(str(d), *bayraklar(**{"--repo": "\x1bhttps://ghp_TOKSECRET@git.ornek.invalid/e/p.git"}), "--dry-run")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("kontrol karakteri", r.stdout)
        self.assertNotIn("ghp_", r.stdout)
        d2 = self.tmp / "remotesuz"
        d2.mkdir()
        self.git(d2, "init", "-q", "-b", "main")
        with mock.patch.dict(os.environ, ortam):
            self.assertEqual(yeni_proje.depo_onerisi(d2), "yerel")

    # --- adım 4: http(s) yolunda/query/fragment'te '@' kimlik değildir · scp biçiminde parola · ayrıştırma hatası ---
    def test_a4_http_yol_at_ve_scp_parola_tablosu(self):
        tablo = [
            # '@' yalnız yol/query/fragment'te: yetki (authority) ilk '/', '?' ya da '#'te biter (git credential.c ve
            # curl ile aynı sınır) → kimlik yok, adres olduğu gibi kalır (tabanda (True, 'https://b') dönüyordu)
            ("https://host/a@b", False, "https://host/a@b"),
            ("https://host/r.git?ref=a@b", False, "https://host/r.git?ref=a@b"),
            ("https://host/r.git#a@b", False, "https://host/r.git#a@b"),
            ("https://host:8443/~kul@ekip/r.git", False, "https://host:8443/~kul@ekip/r.git"),
            ("https://[::1]:8443/a@b", False, "https://[::1]:8443/a@b"),
            ("git+https://host/~u@x/r.git", False, "git+https://host/~u@x/r.git"),
            # gate F3: yetki '?' ve '#'te de biter (yolsuz adres) → kimlik yok, uyarıyla kabul (bugünkü davranış sabitlenir)
            ("https://host#a@b", False, "https://host#a@b"),
            ("https://host?ref=a@b", False, "https://host?ref=a@b"),
            # gate F3: ']' sonrası port değil → fail-closed (ayrıştırma hatası DEĞİL, geçersiz yetki: kimlik var sayılır)
            ("https://[::1]x/a@b", True, "https://b"),
            # kimlik yetkide + yolda '@': yalnız kimlik atılır, yol korunur
            ("https://TOKEN@host/~u@x/r.git", True, "https://host/~u@x/r.git"),
            ("https://TO@KEN@host/a@b", True, "https://host/a@b"),
            # parolalı kimlik + sonra '@': parola '@' ya da '/' içeriyor olabilir → fail-closed, son '@'e kadar atılır
            ("https://u:p@s/s@host/r", True, "https://host/r"),
            # yetkide ':' sonrası geçerli port değil (parola '/', '?' ya da '#' içeriyor) → fail-closed
            ("https://kul:Pa/x@host/r", True, "https://host/r"),
            ("https://kul:/x@host/r", True, "https://host/r"),
            # scp biçimi: parola ':' ile kullanıcıdan ayrılır, host:yol ayracı '@'ten sonra gelir
            ("u:p@host:ekip/r.git", True, "u@host:ekip/r.git"),
            ("u:p/q@host:ekip/r.git", True, "u@host:ekip/r.git"),
            ("u:p@ss@host:r.git", True, "host:r.git"),
            # kontroller: parolasız scp, yolunda '@' olan scp, yerel yollar
            ("git@host:ekip/r.git", False, "git@host:ekip/r.git"),
            ("host:ekip/u@x.git", False, "host:ekip/u@x.git"),
            ("./a:b@c:d", False, "./a:b@c:d"),
            ("C:/x/a:b@c:d", False, "C:/x/a:b@c:d"),
            ("C:\\x\\a:b@c:d", False, "C:\\x\\a:b@c:d"),
        ]
        for url, kimlik, temiz in tablo:
            with self.subTest(url=url):
                self.assertEqual(yeni_proje.http_kimlik(url), (kimlik, temiz))
        for url, kimlik, temiz in tablo:
            if kimlik:
                with self.subTest(sizinti=url):
                    for parca in ("TOKEN", "KEN", "Pa", ":p", "p/q", "p@", "s/s", ":/x"):
                        self.assertNotIn(parca, temiz)
        # d_repo: yanlış pozitif kalkar, scp parolası reddedilir, ayrıştırılamayan adres AÇIK mesajla reddedilir
        self.assertIsNone(yeni_proje.d_repo("https://host:8443/~kul@ekip/r.git"))
        self.assertIn("kimlik kısmı olmadan", yeni_proje.d_repo("u:p@host:ekip/r.git") or "")
        hata = yeni_proje.d_repo("https://[::1/x") or ""
        self.assertIn("ayrıştırılamadı", hata)
        self.assertNotIn("adreste parola", hata, "kimliksiz ama ayrıştırılamayan adres 'parola var' diye raporlanmamalı")
        self.assertIn("kimlik kısmı olmadan", yeni_proje.d_repo("https://ghp_abc@[::1/x") or "")
        # gate F3: sınır biçimleri uyarıyla kabul; ']' sonrası port olmayan IPv6 geçersiz yetki olarak (ayrıştırma değil) reddedilir
        for url in ("https://host#a@b", "https://host?ref=a@b"):
            with self.subTest(sinir=url):
                self.assertIsNone(yeni_proje.d_repo(url))
                self.assertEqual(yeni_proje.depo_uyarisi(url), yeni_proje.YOLDA_AT_UYARISI)
        hata = yeni_proje.d_repo("https://[::1]x/a@b") or ""
        self.assertIn("adreste parola", hata)
        self.assertNotIn("ayrıştırılamadı", hata)
        # uçtan uca: dry-run
        d = self.tmp / "a4"
        r = self.yeni(str(d), *bayraklar(**{"--repo": "https://host/~kul@ekip/r.git"}), "--dry-run")
        self.assertEqual(r.returncode, 0, "yolunda '@' olan temiz adres reddedilmemeli\n" + self.cikti(r))
        self.assertIn("https://host/~kul@ekip/r.git", r.stdout)
        for url, beklenen in (("u:p@host:ekip/r.git", "kimlik kısmı olmadan"), ("https://[::1/x", "ayrıştırılamadı")):
            with self.subTest(repo=url):
                r = self.yeni(str(d), *bayraklar(**{"--repo": url}), "--dry-run")
                self.assertEqual(r.returncode, 2, self.cikti(r))
                self.assertIn(beklenen, r.stdout)
                self.assertFalse(d.exists())

    def test_a4_yolda_at_uyari_verir_reddetmez(self):
        # Lider kararı: yetki sınırı kalır; yetkiden SONRA '@' (yol/sorgu/fragment) reddedilmez ama sessiz de kalmaz —
        # kodlanmamış '/?#' içeren token/rakamlı parola (https://TO/KEN@host) bu yolla görünür olur.
        uyari = "adresin yol/sorgu kısmında '@' var; kimlik bilgisi değilse sorun yok, kimlik bilgisiyse adresten çıkar"
        self.global_config(sap=True)
        d = self.tmp / "uyari"
        for url in ("https://TO/KEN@host", "https://host/a@b", "https://host/r.git?ref=a@b"):
            with self.subTest(url=url):
                self.assertIsNone(yeni_proje.d_repo(url), "yolda '@' reddedilmemeli")
                r = self.yeni(str(d), *bayraklar(**{"--repo": url}), "--dry-run")
                self.assertEqual(r.returncode, 0, self.cikti(r))
                self.assertIn(f"! UYARI: depo: {uyari}", r.stdout)
                self.assertFalse(d.exists())
        # kontroller: temiz adres, yerel ve scp uyarı vermez; kimlikli adres uyarı değil ret alır
        # gate F2: http dışı şemada kullanıcı adı ('@' yetkide) uyarı almaz
        for url in ("https://host/org/repo.git", "yerel", "git@host:ekip/r.git", "ssh://git@host/r.git",
                    "git+ssh://git@host/r.git"):
            with self.subTest(kontrol=url):
                r = self.yeni(str(d), *bayraklar(**{"--repo": url}), "--dry-run")
                self.assertEqual(r.returncode, 0, self.cikti(r))
                self.assertNotIn(uyari, r.stdout)
        r = self.yeni(str(d), *bayraklar(**{"--repo": "https://TOKEN@host/a@b"}), "--dry-run")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertNotIn(uyari, r.stdout)
        # gerçek koşu: kur akışının sonundaki UYARILAR bölümünde de görünür
        r = self.yeni(str(d), *bayraklar(**{"--repo": "https://host/a@b"}))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("UYARILAR (çıkış kodunu etkilemez)", r.stdout)
        self.assertIn(uyari, r.stdout.split("UYARILAR (çıkış kodunu etkilemez)", 1)[1])
        self.assertIn("- Depo: https://host/a@b", (d / "AGENTS.md").read_text(encoding="utf-8"))

    def test_a4_depo_onerisi_yolunda_at(self):
        ortam = {k: self.env[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
        d = self.tmp / "remote-at"
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        self.git(d, "remote", "add", "origin", "https://git.ornek.invalid/~kul@ekip/proje.git")
        with mock.patch.dict(os.environ, ortam):
            self.assertEqual(yeni_proje.depo_onerisi(d), "https://git.ornek.invalid/~kul@ekip/proje.git")
        # lider kararı (adım 4 fix EK): scp'de git'in parola sözdizimi yok → temizleme tahmindir; adresi değiştiren
        # temizleme önerilmez ('yerel' + ORIGIN_UYARISI)
        self.git(d, "remote", "set-url", "origin", "kul:gizli@git.ornek.invalid:ekip/proje.git")
        with mock.patch.dict(os.environ, ortam):
            self.assertEqual(yeni_proje.depo_onerisi(d), "yerel")

    # --- gate F1 · F4: belirsiz temizlenen origin önerilmez · ayrıştırma hatası girdiden metin taşımaz ---
    def test_f1_belirsiz_origin_onerilmez_f4_ayristirma_mesaji_sabit(self):
        ortam = {k: self.env[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
        uyari = "origin adresi güvenle temizlenemedi; --repo ile ver"
        d = self.tmp / "belirsiz-origin"
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        # belirsiz: scp'de parola '/' içeriyor olabilir ya da host:yol'un yolunda '@'/':' var (a:b/c@d:e ≡ u:p/q@host:yol) ·
        # scp'de ikinci '@' · http'de geçersiz port/yetki (fail-closed son '@'e kadar keser) · ayrıştırılamayan adres
        belirsiz = {"host:org/u@x:y.git": ("u@x", "x:y"), "a:b/c@d:e": ("d:e", "a@"),
                    "u:p@ss@host:r.git": ("host:r", "ss@"), "https://host:abc/r@x": ("abc", "https://x"),
                    "https://[::1]x/a@b": ("a@b", "https://b"), "https://[SECRETTOKEN]/r": ("SECRETTOKEN",),
                    # lider kararı (EK): scp'de parola sözdizimi yok → adresi DEĞİŞTİREN her scp temizlemesi önerilmez
                    "host:u@x:y.git": ("host@x", "x:y"), "kul:gizli@host:ekip/proje.git": ("gizli", "kul@")}
        for origin, parcalar in belirsiz.items():
            with self.subTest(origin=origin):
                self.git(d, "remote", "remove", "origin", kontrol=False)
                self.git(d, "remote", "add", "origin", origin)
                with mock.patch.dict(os.environ, ortam):
                    self.assertEqual(yeni_proje.depo_onerisi(d), "yerel")
                    oneri, not_ = yeni_proje.depo_onerisi_ve_uyari(d)
                self.assertEqual(oneri, "yerel")
                self.assertIn(uyari, not_ or "")
                for parca in parcalar:
                    self.assertNotIn(parca, not_ or "")
        # kontrol grubu: meşru adresler aynen, kimliği kesin ayrılan adresler temizlenerek önerilir; hiçbiri uyarı almaz
        kontrol = {"git@github.com:org/r.git": "git@github.com:org/r.git", "host:ekip/u@x.git": "host:ekip/u@x.git",
                   "org@vs-ssh.visualstudio.com:v3/org/proj/repo": "org@vs-ssh.visualstudio.com:v3/org/proj/repo",
                   "https://github.com/org/r.git": "https://github.com/org/r.git",
                   "https://gitlab.com/grup/alt/r.git": "https://gitlab.com/grup/alt/r.git",
                   "https://dev.azure.com/org/proj/_git/repo": "https://dev.azure.com/org/proj/_git/repo",
                   "ssh://git@host/r.git": "ssh://git@host/r.git",
                   "https://TOKEN@host/r.git": "https://host/r.git"}
        for origin, beklenen in kontrol.items():
            with self.subTest(kontrol=origin):
                self.git(d, "remote", "set-url", "origin", origin)
                with mock.patch.dict(os.environ, ortam):
                    self.assertEqual(yeni_proje.depo_onerisi_ve_uyari(d), (beklenen, None))
        # uçtan uca (bayraklı): öneri 'yerel', uyarı basılır, adres parçası çıktıya girmez, çıkış 0
        self.git(d, "remote", "set-url", "origin", "host:org/u@x:y.git")
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn(f"! UYARI: depo: {uyari}", r.stdout)
        self.assertRegex(r.stdout, r"\n  depo +yerel\n")
        for parca in ("u@x", "x:y.git", "host@x"):
            self.assertNotIn(parca, r.stdout + r.stderr)
        # etkileşimli: öneri [yerel], uyarı soru öncesi basılır
        r = self.etkilesimli(["", "ecc", "EHP8", "EN", "", "Deneme", "", "", "", "", "", "", "h"], str(d))
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn(uyari, r.stdout.split("Depo (remote adresi ya da yerel)", 1)[0])
        self.assertIn("Depo (remote adresi ya da yerel) [yerel]:", r.stdout)
        for parca in ("u@x", "x:y.git", "host@x"):
            self.assertNotIn(parca, r.stdout + r.stderr)
        # açık --repo: belirsiz scp reddi KALIR, mesaj nedeni söyler (adresi basmaz); kesin parolalı scp mesajı değişmez
        for url in ("host:org/u@x:y.git", "a:b/c@d:e", "u:p@ss@host:r.git"):
            with self.subTest(repo=url):
                hata = yeni_proje.d_repo(url) or ""
                self.assertIn("belirsiz", hata)
                self.assertNotIn(url, hata)
        self.assertNotIn("belirsiz", yeni_proje.d_repo("u:p@host:ekip/r.git") or "")
        self.assertIsNone(yeni_proje.d_repo("host:ekip/u@x.git"), "kontrol: yolunda '@' olan parolasız scp")
        r = self.yeni(str(self.tmp / "yok"), *bayraklar(**{"--repo": "host:org/u@x:y.git"}), "--dry-run")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("belirsiz", r.stdout)
        # F4: ayrıştırma hatası mesajı girdiden metin taşımaz (urlsplit hata metni host parçasını içeriyordu)
        hata = yeni_proje.d_repo("https://[SECRETTOKEN]/r") or ""
        self.assertIn("ayrıştırılamadı", hata)
        self.assertNotIn("SECRETTOKEN", hata)
        r = self.yeni(str(self.tmp / "yok"), *bayraklar(**{"--repo": "https://[SECRETTOKEN]/r"}), "--dry-run")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("ayrıştırılamadı", r.stdout)
        self.assertNotIn("SECRETTOKEN", r.stdout + r.stderr)

    # --- adım 4: new_project.py'nin "Sonraki adımlar" metnine bağımlılık yok ---
    def test_a4_new_project_sonraki_adimlar_metnine_bagli_degil(self):
        # new_project.py yerine taklit: başlığı değişmiş bir "sonraki adımlar" bölümü basar, --no-next-steps verilirse basmaz.
        # Tabanda yeni_proje çıktıyı "Sonraki adımlar:" başlığında bölüyordu → başlık değişince adımlar sızıyordu.
        taklit = self.tmp / "taklit-scripts"
        self.yaz(taklit / "new_project.py", 'import sys\nprint("  [olusturuldu] TAKLIT-DOSYA")\n'
                 'if "--no-next-steps" not in sys.argv:\n    print("\\nNext steps:\\n  1. TAKLIT-ADIM")\n')
        self.yaz(taklit / "doctor.py", 'print("SONUC: taklit doctor")\n')
        self.global_config(sap=True)
        d = self.tmp / "taklit-proje"
        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(yeni_proje, "SCRIPTS", taklit), \
                contextlib.redirect_stdout(out):
            yeni_proje.main([str(d), *bayraklar()])
        self.assertIn("TAKLIT-DOSYA", out.getvalue(), "kontrol: new_project çıktısı aktarılmalı")
        self.assertNotIn("TAKLIT-ADIM", out.getvalue(), "new_project'in sonraki adımları yeni_proje çıktısına sızdı")

    # --- bug gate: LOW-2 · yazılamayan AGENTS.md traceback değil KURULUM EKSİK ---
    def test_l2_agents_yazilamazsa_kurulum_eksik(self):
        self.global_config(sap=True)
        d = self.proje("salt-okunur", sap=True)
        (d / "AGENTS.md").chmod(stat.S_IREAD)
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertNotIn("Traceback", self.cikti(r))
        self.assertIn("[YAZILAMADI] AGENTS.md: PermissionError", r.stdout)
        self.assertIn("SONUÇ: KURULUM EKSİK", r.stdout)
        self.assertIn("[FAIL] AGENTS.md şablon yer tutucusu", r.stdout, "kontrol grubu (m2): şablon kalınca FAIL")

    # --- bug gate: LOW-3 · .git içi hedef ve okunamayan git durumu ---
    def test_l3_git_ici_ve_bozuk_git_reddedilir(self):
        kok = self.tmp / "repo3"
        kok.mkdir()
        self.git(kok, "init", "-q", "-b", "main")
        hedef = kok / ".git" / "icerde"
        r = self.yeni(str(hedef), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn(".git klasörünün içinde", r.stdout)
        self.assertFalse(hedef.exists())
        bozuk = self.tmp / "bozuk"
        bozuk.mkdir()
        (bozuk / ".git").write_text("xyz", encoding="utf-8")
        r = self.yeni(str(bozuk / "yeni"), *bayraklar())
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("git durumu okunamadı", r.stdout)
        self.assertIn("invalid gitfile", r.stdout)
        self.assertFalse((bozuk / "yeni").exists())
        r = self.yeni(str(self.tmp / "duz" / "icerde"), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, "kontrol: git'siz düz yol reddedilmemeli\n" + self.cikti(r))

    # --- bug gate: LOW-4 · klasör adının son bileşeni ---
    def test_l4_klasor_adi_ayrilmis_ve_sonda_nokta_bosluk(self):
        once = sorted(os.listdir(self.tmp))
        for ad in ("CON", "nul.txt", "proje.", "proje "):
            with self.subTest(ad=ad):
                r = self.yeni(os.path.join(str(self.tmp), ad), *bayraklar(), "--name", "gecerli")
                self.assertEqual(r.returncode, 2, self.cikti(r))
                self.assertIn("klasör adı", r.stdout)
        self.assertEqual(sorted(os.listdir(self.tmp)), once)
        r = self.yeni(str(self.tmp / "proje.v2"), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, "kontrol: noktalı geçerli ad reddedilmemeli\n" + self.cikti(r))

    # --- bug gate önerileri ---
    def test_oneri_etkilesimli_klasor_kontrolu_hemen(self):
        kok = self.tmp / "ust-etk"
        kok.mkdir()
        self.git(kok, "init", "-q", "-b", "main")
        iyi = self.tmp / "iyi"
        r = self.etkilesimli([str(kok / "alt"), str(iyi), "", "ecc", "EHP8", "EN", "", "Deneme", "", "", "", "", "",
                              "", "h"])
        self.assertEqual(r.returncode, 2, self.cikti(r))
        i_hata, i_ad = r.stdout.find("alt klasörü"), r.stdout.find("Proje adı")
        self.assertTrue(0 <= i_hata < i_ad, r.stdout)
        self.assertFalse((kok / "alt").exists())
        self.assertFalse(iyi.exists())

    def test_oneri_politika_yalniz_s4_private(self):
        d = self.tmp / "politika"
        r = self.yeni(str(d), *bayraklar(**{"--sap-profile": "ecc", "--release": "EHP8", "--cleancore-policy": "strict"}),
                      "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("UYARI: cleancore_policy='strict' yok sayıldı", r.stdout)
        self.assertIn("sap-project.json cleancore_policy = ''", r.stdout)
        r = self.yeni(str(d), *bayraklar(**{"--cleancore-policy": "strict"}), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("yok sayıldı", r.stdout)
        self.assertIn("sap-project.json cleancore_policy = 'strict'", r.stdout)

    def test_oneri_dry_run_json_okunamazsa_1(self):
        d = self.tmp / "bozuk-json"
        d.mkdir()
        f = self.yaz(d / "sap-project.json", "{bozuk")
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("OKUNAMADI", r.stdout)
        self.assertEqual(f.read_text(encoding="utf-8"), "{bozuk")
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["sap-project.json"])

    # --- yeniden inceleme YENİ-1 · SAP satırı ayrıştırılamazsa ÖLÇÜLEMEDİ, esnek ayrıştırma ---
    def test_y1_sap_satiri_ayristirma_tablosu(self):
        sap = {"sap_profile": "s4_private", "release": "2023", "master_language": "TR"}
        kanonik = "- SAP (varsa): sistem profili s4_private · sürüm 2023 · master_language: {dil} · aktif paket: — x"
        tablo = [
            ("kontrol: kanonik tutarlı", kanonik.format(dil="TR"), "tutarli"),
            ("kontrol: kanonik EN↔TR", kanonik.format(dil="EN"), "celiski"),
            ("backtick değer", kanonik.format(dil="`EN`"), "celiski"),
            ("backtick tutarlı", "- SAP (varsa): sistem profili `s4_private` · master_language: `tr`", "tutarli"),
            ("Master_Language", "- SAP: profil s4_private · Master_Language: EN", "celiski"),
            ("boşluklu anahtar", "- SAP: sistem profili s4_private · master language: EN", "celiski"),
            ("kalın madde", "- **SAP**: sistem profili s4_private · master_language: EN", "celiski"),
            ("büyük harf profil", "- SAP (varsa): sistem profili S4_PRIVATE · master_language: TR", "tutarli"),
            ("English", "- SAP: sistem profili s4_private · master_language: English", "olculemedi"),
            ("şablon yer tutucusu", SABLON_SAP, "olculemedi"),
            ("profil yok", "- SAP: master_language: TR", "olculemedi"),
            ("SAP satırı yok", "- Amaç: x", "olculemedi"),
            # bug gate Y-a: anahtarsız `- SAP…` maddesi atlanır; anahtarlı satırlar farklıysa ÖLÇÜLEMEDİ
            ("anahtarsız kural önce", "- SAP'ye yazmadan önce onay al\n" + kanonik.format(dil="TR"), "tutarli"),
            ("anahtarsız kural önce + çelişki", "- SAP'ye yazmadan önce onay al\n" + kanonik.format(dil="EN"), "celiski"),
            ("kontrol: yalnız anahtarsız madde", "- SAP'ye yazmadan önce onay al", "olculemedi"),
            ("iki anahtarlı satır aynı", kanonik.format(dil="TR") + "\n- SAP notu: master_language: tr", "tutarli"),
            ("iki anahtarlı satır farklı", kanonik.format(dil="TR") + "\n- SAP: sistem profili ecc · master_language: TR",
             "olculemedi"),
            # bug gate MEDIUM-2: serbest metinde profil/dil geçen satır atlanır; gerçek İngilizce satır okunur
            ("İngilizce anahtar", "- SAP: profile s4_private · master language TR", "tutarli"),
            ("anahtar biçimi bozuk değer", "- SAP: profil: s4x · master_language: TR", "olculemedi"),
            ("bozuk anahtar biçimi + doğru satır", "- SAP: profil: s4x\n" + kanonik.format(dil="TR"), "olculemedi"),
        ]
        for serbest in SERBEST_SAP_MADDELERI:
            tablo.append((f"serbest önce: {serbest}", f"{serbest}\n" + kanonik.format(dil="TR"), "tutarli"))
            tablo.append((f"serbest sonra: {serbest}", kanonik.format(dil="TR") + f"\n{serbest}", "tutarli"))
        for benzer in DEGER_BENZERI_SAP_MADDELERI:
            tablo.append((f"değer benzeri önce: {benzer}", f"{benzer}\n" + kanonik.format(dil="TR"), "olculemedi"))
            tablo.append((f"değer benzeri sonra: {benzer}", kanonik.format(dil="TR") + f"\n{benzer}", "olculemedi"))
        for parca in KELIME_SINIRI_SAP_MADDELERI:
            tablo.append((f"kelime sınırı: {parca}", kanonik.format(dil="TR") + f"\n{parca}", "tutarli"))
        for etiket, satir, beklenen in tablo:
            with self.subTest(etiket):
                durum, ayrinti = yeni_proje.sap_satiri_denetle(f"# x\n{satir}\n", sap)
                self.assertEqual(durum, beklenen, ayrinti)

    def test_y1_elle_bozulan_sap_satiri_dry_ve_gercek_1(self):
        self.global_config(sap=True)
        d = self.proje("y1", sap=True)
        r = self.yeni(str(d), *bayraklar())
        self.assertEqual(r.returncode, 0, "kontrol: kanonik satır tutarlı → 0\n" + self.cikti(r))
        self.assertIn("[PASS] AGENTS.md SAP satırı ↔ sap-project.json: tutarlı", r.stdout)
        for etiket, yeni, beklenen in (("backtick EN (E1)", "master_language: `EN`", "master_language EN ≠"),
                                       ("English", "master_language: English", "ÖLÇÜLEMEDİ")):
            with self.subTest(etiket):
                f = d / "AGENTS.md"
                metin = f.read_text(encoding="utf-8")
                satir = next(s for s in metin.splitlines() if s.startswith("- SAP"))
                bozuk = satir.replace(satir[satir.index("master_language:"):].split(" · ")[0], yeni)
                f.write_text(metin.replace(satir, bozuk), encoding="utf-8")
                r = self.yeni(str(d), *bayraklar(), "--dry-run")
                self.assertEqual(r.returncode, 1, self.cikti(r))
                self.assertIn(beklenen, r.stdout)
                r = self.yeni(str(d), *bayraklar())
                self.assertEqual(r.returncode, 1, self.cikti(r))
                self.assertIn(beklenen, r.stdout.split("SONUÇ: KURULUM EKSİK", 1)[-1])
                f.write_text(metin, encoding="utf-8")

    # --- bug gate Y-a: SAP satırından ÖNCE anahtarsız `- SAP…` maddesi sahte ÖLÇÜLEMEDİ/çıkış 1 vermemeli ---
    def test_ya_anahtarsiz_sap_maddesi_atlanir_dry_gercek_doctor(self):
        self.global_config(sap=True)
        d = self.proje("ya", sap=True)
        self.agents_satir_degistir(d, "- SAP (varsa):", "- SAP'ye yazmadan önce onay al\n- SAP (varsa):")
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("ÖLÇÜLEMEDİ", r.stdout)
        r = self.yeni(str(d), *bayraklar())  # gerçek koşu kendi doğrulamasını VE doctor.py'yi koşar
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("[PASS] AGENTS.md SAP satırı ↔ sap-project.json: tutarlı", r.stdout)
        self.assertIn("SONUÇ: 0 FAIL", r.stdout)
        self.assertIn("- SAP'ye yazmadan önce onay al\n- SAP (varsa): sistem profili s4_private",
                      (d / "AGENTS.md").read_text(encoding="utf-8"))

    # --- yeniden inceleme YENİ-3 · UTF-8 olmayan AGENTS.md: dry-run da gerçek koşu da 1, traceback yok ---
    def test_y3_utf8_olmayan_agents_dry_ve_gercek_1(self):
        self.global_config(sap=True)
        d = self.proje("y3", sap=True)
        r = self.yeni(str(d), *bayraklar(), "--dry-run")
        self.assertEqual(r.returncode, 0, "kontrol: UTF-8 AGENTS.md ile dry-run 0\n" + self.cikti(r))
        f = d / "AGENTS.md"
        bozuk = f.read_text(encoding="utf-8").encode("cp1254", errors="replace")
        with self.assertRaises(UnicodeDecodeError, msg="fikstür geçersiz: cp1254 baytları UTF-8 olarak çözülebiliyor"):
            bozuk.decode("utf-8")
        f.write_bytes(bozuk)
        for etiket, ek in (("dry-run", ["--dry-run"]), ("gerçek koşu", [])):
            with self.subTest(etiket):
                r = self.yeni(str(d), *bayraklar(), *ek)
                self.assertEqual(r.returncode, 1, self.cikti(r))
                self.assertNotIn("Traceback", self.cikti(r))
                self.assertIn("UTF-8", r.stdout)
                self.assertEqual(f.read_bytes(), bozuk, "AGENTS.md değişti")

    # --- yeniden inceleme YENİ-5: dışarıdan gelen GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE başka repoya yönlendirmemeli ---
    def test_y5_git_ortam_degiskenleri_hedefi_saptirmaz(self):
        self.global_config(sap=True)
        diger = self.tmp / "diger"
        diger.mkdir()
        self.git(diger, "init", "-q", "-b", "main")
        cfg = diger / ".git" / "config"
        once = cfg.read_bytes()
        ortam = dict(self.env, GIT_DIR=str(diger / ".git"), GIT_WORK_TREE=str(diger),
                     GIT_INDEX_FILE=str(diger / ".git" / "index"), GIT_COMMON_DIR=str(diger / ".git"))
        d = self.tmp / "y5"
        r = subprocess.run([sys.executable, str(SCRIPTS / "yeni_proje.py"), str(d), *bayraklar()], cwd=str(self.tmp),
                           env=ortam, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=300)
        self.assertNotIn("zaten repo kökü", r.stdout, self.cikti(r))
        self.assertTrue((d / ".git").is_dir(), "git init hedefte yapılmadı\n" + self.cikti(r))
        self.assertEqual(cfg.read_bytes(), once, "öteki reponun config'i değişti (core.hooksPath oraya yazıldı)")
        self.assertEqual(self.git(d, "config", "--get", "core.hooksPath").stdout.strip(), ".githooks")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    # --- yeniden inceleme YENİ-2: sonunda boşluk/sekme kalmış şablon satırı da doldurulmalı ve FAIL sayılmalı ---
    def test_y2_sondaki_bosluklu_sablon_satiri(self):
        v = {"purpose": "X", "tech": "T", "repo": "yerel", "test_cmd": "", "run_cmd": "", "lint_cmd": "", "rules": []}
        sap = {"sap_profile": "s4_private", "release": "2023", "master_language": "TR"}
        temiz = new_project._doldur((new_project.TEMPLATE / "AGENTS.md").read_text(encoding="utf-8"), "y2")
        # kontrol grubu: sondaki boşluksuz şablon tam doldurulur
        dolu, _ = yeni_proje.agents_doldur(temiz, v, sap)
        self.assertEqual(yeni_proje.sablon_kalanlari(dolu), [])
        sab = set(yeni_proje.sablon_satirlari().values())
        bosluklu = "".join(s.rstrip("\r\n") + " \t" + s[len(s.rstrip("\r\n")):] if s.rstrip("\r\n") in sab else s
                           for s in temiz.splitlines(keepends=True))
        self.assertNotEqual(bosluklu, temiz)
        self.assertEqual(len(yeni_proje.sablon_kalanlari(bosluklu)), len(yeni_proje.SABLON_ISARETLERI),
                         "sonda boşluklu şablon satırı kalan sayılmadı (sahte PASS)")
        dolu2, rapor = yeni_proje.agents_doldur(bosluklu, v, sap)
        self.assertEqual(yeni_proje.sablon_kalanlari(dolu2), [], "sonda boşluklu şablon satırı doldurulmadı")
        self.assertEqual(len(rapor), len(yeni_proje.SABLON_ISARETLERI), rapor)
        self.assertEqual(yeni_proje.diger_yer_tutucular(dolu2), [])

    # --- yeniden inceleme ÖNERİ: şablon değişirse ham RuntimeError değil, ne olduğunu söyleyen mesaj (çıkış 1) ---
    def test_y7_oneri_bozuk_sablon_mesaji(self):
        bozuk = self.tmp / "bozuk-sablon"
        bozuk.mkdir()
        (bozuk / "AGENTS.md").write_text("# AGENTS.md\n\nşablon işaretleri yok\n", encoding="utf-8")
        # literal metin (yeni_proje.SABLON_BOZUK değil): kontrol grubu eski modülde de AttributeError'sız koşsun
        beklenen = "şablon satırları bulunamadı (templates/project/AGENTS.md değişmiş olabilir)"
        self.global_config(sap=True)
        for ad, ek in (("dry-run", ["--dry-run"]), ("gercek", [])):
            with self.subTest(kosu=ad):
                d = self.tmp / f"y7-{ad}"
                out = io.StringIO()
                # os.environ geçici ortamla değiştirilir: in-process koşunun alt süreçleri gerçek config'e dokunmaz
                with mock.patch.dict(os.environ, self.env, clear=True), \
                        mock.patch.object(new_project, "TEMPLATE", bozuk), contextlib.redirect_stdout(out):
                    rc = yeni_proje.main([str(d), *bayraklar(), *ek])
                self.assertIn(beklenen, out.getvalue())
                self.assertEqual(rc, 1, out.getvalue())

    # --- birim ---
    def test_profil_kumesi_sap_cli_ile_ayni(self):
        self.assertEqual(tuple(yeni_proje.PROFILLER), tuple(_sap_project_modulu().GECERLI_PROFILLER))

    def test_damga_blogundaki_metne_dokunulmaz(self):
        v = {"purpose": "X", "tech": "T", "repo": "yerel", "test_cmd": "", "run_cmd": "", "lint_cmd": "", "rules": []}
        metin = (f"{sap_stamp.BASLA}\n- Amaç: <kısa açıklama>\n{sap_stamp.BITIR}\n\n## Proje kimliği\n"
                 "- Amaç: <kısa açıklama>\n")
        yeni, rapor = yeni_proje.agents_doldur(metin, v, None)
        self.assertIn(f"{sap_stamp.BASLA}\n- Amaç: <kısa açıklama>\n{sap_stamp.BITIR}", yeni)
        self.assertTrue(yeni.endswith("- Amaç: X\n"), yeni)
        self.assertEqual(rapor, ["Amaç"])
