# -*- coding: utf-8 -*-
"""doctor.py — global config, proje kontrolleri (gitignore, pre-commit, damga, davranış yüzeyi), frontmatter."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
from pathlib import Path
from unittest import mock

from _helpers import GeciciTest  # önce: scripts/ yolunu ekler
import doctor
import sap_stamp


class DoctorTest(GeciciTest):
    def setUp(self) -> None:
        super().setUp()
        # Skill envanteri manifest'i geçici LOCALAPPDATA'dan okur (gerçek %LOCALAPPDATA%\axet-code'a dokunulmaz).
        self.env["LOCALAPPDATA"] = str(self.tmp / "_lad")
        self.env.pop("AXET_SKILLS_DIR", None)

    def doctor(self, cwd):
        return self.calistir("doctor.py", cwd=cwd)

    def satirlar(self, r) -> list[str]:
        return r.stdout.splitlines()

    def var(self, r, durum: str, parca: str) -> None:
        self.assertTrue(any(s.startswith(f"[{durum}]") and parca in s for s in self.satirlar(r)),
                        f"[{durum}] … {parca} yok:\n{r.stdout}")

    def sap_proje(self):
        self.global_config()
        d = self.proje(sap=True)
        r = self.calistir("behavior_manifest.py", "generate", "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return d

    def test_global_config_yok(self):
        d = self.proje()
        r = self.doctor(d)
        self.assertEqual(r.returncode, 1)
        self.var(r, "FAIL", "global config yok")

    def test_saglikli_sap_projesi(self):
        d = self.sap_proje()
        r = self.doctor(d)
        self.var(r, "PASS", ".conn_adt git'e kapalı")
        self.var(r, "PASS", "pre-commit kablolu")
        self.var(r, "PASS", "kesin yasak damgası güncel")
        self.var(r, "PASS", "davranış yüzeyi onaylı manifest'le eş")
        self.var(r, "PASS", "SAP kanonik kesin yasak bölümü okundu")

    # --- K4b: install.py'yi yeniden koşmamış makinede emekli izin desenleri global config'te kalır ---
    def emekli_ekle(self, kurallar: dict) -> None:
        f = self.xdg / "axet-code" / "axet-code.json"
        cfg = json.loads(f.read_text(encoding="utf-8"))
        cfg["permissions"]["rules"]["bash"].update(kurallar)
        f.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    def test_emekli_izin_deseni_warn_ve_tarif(self):
        d = self.sap_proje()
        kontrol = self.doctor(d)
        self.assertFalse([s for s in self.satirlar(kontrol) if s.startswith("[") and "emekli" in s],
                         "kontrol: emekli desen yokken satır basılmamalı")
        kapsam = next((s for s in self.satirlar(kontrol) if s.startswith("KAPSAM")), "")
        self.assertIn("emekli izin deseni yalnız global config'te aranır", kapsam, "kapsam beyanı eksik")
        self.emekli_ekle({"git reset --hard*": "deny", "*deploy_ui.py*deploy *": "ask"})
        r = self.doctor(d)
        # NOT: desen adları EMEKLİ satırında aranır — K12 ezme kontrolü de aynı desen adını yazabilir (o satır
        # emekli mantığından bağımsızdır); süzgeç dar tutulmazsa bu test emekli mantığı bozulsa da geçerdi.
        emekli_satir = [s for s in self.satirlar(r) if "emekli template izin deseni kaldı (2)" in s]
        self.assertEqual(len(emekli_satir), 1, r.stdout)
        self.assertTrue(emekli_satir[0].startswith("[WARN]"), emekli_satir[0])
        for parca in ("bash:git reset --hard*", "bash:*deploy_ui.py*deploy *", "install.py"):
            self.assertIn(parca, emekli_satir[0])
        self.assertFalse([s for s in self.satirlar(r) if s.startswith("[INFO]") and "emekli" in s])
        self.assertEqual(r.returncode, kontrol.returncode, "WARN çıkış kodunu değiştirmemeli")

    def test_emekli_desen_kullanici_karariyla_bilgi_satiri(self):
        d = self.sap_proje()
        self.emekli_ekle({"rm -rf *": "deny"})  # install'ın yazdığı karar 'ask'; kullanıcı 'deny' yapmış
        r = self.doctor(d)
        self.var(r, "INFO", "bash:rm -rf *")
        self.assertFalse([s for s in self.satirlar(r) if s.startswith("[WARN]") and "emekli template izin" in s],
                         r.stdout)

    def test_emekli_listesi_install_py_den_gelir(self):
        self.global_config()
        self.emekli_ekle({"*sahte-emekli*": "ask"})
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.xdg)}):
            with mock.patch.object(doctor, "results", []) as sonuc:
                doctor.check_global()
            # süzgeç "emekli template izin deseni"dir, düz "emekli" değil: desen adı 'emekli' içeriyor ve K12 ezme
            # kontrolü de aynı adı yazıyor → dar süzgeç olmadan bu test emekli mantığından bağımsız geçerdi
            self.assertFalse([m for _, m in sonuc if "emekli template izin deseni" in m],
                             "kontrol: listede olmayan desen emekli sayılmamalı")
            with mock.patch.object(doctor, "results", []) as sonuc, \
                    mock.patch.object(doctor.inst, "RETIRED_RULES", {"bash": {"*sahte-emekli*": "ask"}}):
                doctor.check_global()
            self.assertTrue([m for s, m in sonuc if s == "WARN" and "emekli template izin deseni kaldı" in m
                             and "bash:*sahte-emekli*" in m], sonuc)

    # --- K12: canlı config'teki ask/allow deseni template deny'ını uzunlukla ezebilir (yalnız WARN) -------------
    EZME = "uzunlukla ezebilir"

    def kural_ekle(self, arac: str, kurallar: dict) -> None:
        f = self.xdg / "axet-code" / "axet-code.json"
        cfg = json.loads(f.read_text(encoding="utf-8"))
        cfg["permissions"]["rules"].setdefault(arac, {}).update(kurallar)
        f.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    def ezme_satirlari(self, r) -> list[str]:
        return [s for s in self.satirlar(r) if self.EZME in s]

    def test_ezme_uzun_ask_deny_ezebilir_warn(self):
        d = self.sap_proje()
        kontrol = self.doctor(d)
        self.assertEqual(self.ezme_satirlari(kontrol), [],
                         f"kontrol: taze kurulumda ezme satırı olmamalı:\n{kontrol.stdout}")
        kapsam = next((s for s in self.satirlar(kontrol) if s.startswith("KAPSAM")), "")
        self.assertIn("uzunluk-önceliği yalnız global config'te aranır", kapsam, "kapsam beyanı eksik")
        # ① gerçekten yaşandı: bu ask deseni '*git reset --hard*' deny'ını ezip komutu sorulmadan çalıştırmıştı
        self.kural_ekle("bash", {"*Remove-Item*-Recurse*": "ask"})
        r = self.doctor(d)
        self.var(r, "WARN", self.EZME)
        self.var(r, "WARN", "bash:*Remove-Item*-Recurse* (ask; sabit 19, toplam 22)")
        self.assertEqual(r.returncode, kontrol.returncode, "WARN çıkış kodunu değiştirmemeli")
        self.assertFalse([s for s in self.ezme_satirlari(r) if not s.startswith("[WARN]")], r.stdout)
        # DARALT: jokersiz (yalnız kendi metnine uyan) desen AZ SAYIDA deny ile çakışır → o deny'lar ADIYLA yazılır.
        # `*X*` biçimli desenler zincirli komut yüzünden hemen her deny ile çakışır (yukarıdaki vakada 29) ve liste
        # "… ve N deny daha" özetine düşer; ölçülmüş vaka da zincirliydi. Ayırt edici ölçüt İSİM + ÖZETE DÜŞMEME.
        # ⚠ "TAM OLARAK TEK deny" diye çivilenMEZ: K11 `*git reset *--hard*` desenini ekleyince aynı komuta uyan
        # ikinci bir template deny'ı oluştu ve satır iki deny listeledi — davranış DOĞRU, eski çivi kırılgandı.
        # (Ölçüldü 2026-09-17 entegrasyon dalında: K11 ve K12 tek başına yeşil, birleşince bu test kırmızıydı.)
        self.kural_ekle("bash", {"git reset --hard --quiet": "ask"})
        r = self.doctor(d)
        self.var(r, "WARN", "bash:git reset --hard --quiet (ask; sabit 24, toplam 24) → ezebileceği deny: "
                            "*git reset --hard* (sabit 16, toplam 18)")
        satir = next(s for s in self.ezme_satirlari(r) if "git reset --hard --quiet" in s)
        self.assertNotIn("deny daha", satir,
                         "jokersiz desen özet satırına düşmemeli (az deny ile çakışır): " + satir)

    def test_ezme_cakismayan_ya_da_kisa_desen_uretmez(self):
        """Yanlış pozitif kontrol grubu: (a) uzun ama hiçbir deny ile çakışmayan desen, (b) çakışan ama kısa desen."""
        d = self.sap_proje()
        self.kural_ekle("bash", {"git status --short --branch --untracked-files=all": "allow",  # jokersiz, uzun
                                 "*Rm-It*": "ask"})                                             # çakışır ama kısa
        r = self.doctor(d)
        self.assertEqual(self.ezme_satirlari(r), [], f"yanlış pozitif:\n{r.stdout}")

    def test_ezme_allow_sayilir_arac_alani_ayri(self):
        """Alan ayrımı ('edit' deseni 'bash' deny'larıyla karşılaştırılMAZ) + 'allow' da 'ask' gibi sayılır.

        ⚠ Alan ayrımı CLI üzerinden ölçülemez: kurulum artık HİÇ `edit` kuralı yazmıyor (`CLONE_PROTECTED`
        2026-09-18'de kaldırıldı, install.py `load_rules` üstündeki not) → canlı config'te karşılaştırılacak
        `edit` deny'ı yok. Kaldırmadan ÖNCE de CLI'den ölçülemiyordu, çünkü o desenler AXET_HOME'un DİSK
        YOLUNDAN türetiliyordu (ölçüldü: bu ağaçta en kısa `edit` deny 103 kr, `C:/ax/axet` kurulumunda 17 kr
        → beklenti kurulum yolunun UZUNLUĞUNA bağlı kırmızıya dönüyordu; CI `runs-on: windows-latest`).
        İki gerekçe de aynı sonuca çıkar: alan ayrımı SABİT template fixture'ıyla birim seviyesinde ölçülür.
        """
        uzun = "*edit-cok-uzun-bir-desen-ornegi-burada*"
        sabit_template = {"bash": {"*bash-cok-uzun-bir-deny-deseni-buraya*": "deny"},
                          "edit": {"*/core/*": "deny"}}
        bulgular = doctor.ezebilen_izin_desenleri(
            {"permissions": {"rules": {"edit": {uzun: "allow"}}}}, template_kurallari=sabit_template)
        self.assertEqual([b["arac"] for b in bulgular], ["edit"], bulgular)
        # asıl iddia: desen YALNIZ kendi alanının deny'larıyla kıyaslandı — bash deny'ı sızmadı
        self.assertEqual(bulgular[0]["denyler"], ["*/core/*"], bulgular)
        # ... ve 'allow' kararı da 'ask' gibi riskli sayılıyor
        self.assertEqual(bulgular[0]["karar"], "allow", bulgular)
        # CLI ucu: 'bash' deny'ları yola bağlı DEĞİL (sabit template metni) → orada uçtan uca ölçülebilir
        d = self.sap_proje()
        self.kural_ekle("bash", {"*bash-cok-uzun-bir-desen-ornegi-burada*": "allow"})
        r = self.doctor(d)
        self.var(r, "WARN", "bash:*bash-cok-uzun-bir-desen-ornegi-burada*")
        self.assertIn("allow", next(s for s in self.ezme_satirlari(r) if "bash-cok-uzun" in s))

    def test_ezme_sabit_kisa_ama_toplam_uzun_desen_riskli(self):
        """`_kesin_kisa` HEM sabit HEM toplam uzunluk ister (`and`) — mutasyon koruması.

        Ayırt edici vaka: `*g*i*t* *p*u*s*h*` SABİT uzunlukta (8) `*git push -f*`dan (11) kısa ama
        TOPLAMDA uzun (17 > 13). `and` → "kesin kısa" DEĞİL → WARN. `or` mutantı sessiz kalır.
        Bu WARN, "eşleştirmede sabit mi toplam mı belirleyici" sorusu DOĞRULANMADI kaldığı için alınan
        tek savunmadır; regresyon koruması olmadan sessizce gevşeyebilir (ölçüldü: bu test yokken
        `and`→`or` mutasyonu 66 testin TAMAMINDAN kaçtı).
        """
        d = self.sap_proje()
        self.kural_ekle("bash", {"*g*i*t* *p*u*s*h*": "ask"})
        self.var(self.doctor(d), "WARN", "bash:*g*i*t* *p*u*s*h* (ask; sabit 8, toplam 17)")


    def test_ezme_esit_uzunluk_da_riskli(self):
        """Ölçüldü: eşitlikte ask kazanır → 'kesin kısa' değilse risklidir."""
        d = self.sap_proje()
        self.kural_ekle("bash", {"*git push -X*": "ask"})  # sabit 11 = '*git push -f*' (11), toplam 13 = 13
        self.var(self.doctor(d), "WARN", "bash:*git push -X*")

    def test_ezme_cok_bulgu_ozet_satirina_duser(self):
        """Gürültü sınırı: en çok EZME_EN_COK_SATIR satır + 1 özet."""
        d = self.sap_proje()
        fazla = doctor.EZME_EN_COK_SATIR + 2
        self.kural_ekle("bash", {f"*kullanici-deseni-{i:02d}-cok-uzun*": "ask" for i in range(fazla)})
        r = self.doctor(d)
        self.assertEqual(len(self.ezme_satirlari(r)), doctor.EZME_EN_COK_SATIR + 1, "\n".join(self.ezme_satirlari(r)))
        self.var(r, "WARN", "… ve 2 izin deseni daha template deny'ını uzunlukla ezebilir")

    # --- negatif ---
    def test_gitignore_eksik(self):
        d = self.sap_proje()
        (d / ".gitignore").unlink()
        self.var(self.doctor(d), "FAIL", ".conn_adt .gitignore'da DEĞİL")

    def test_hookspath_ayarsiz(self):
        d = self.sap_proje()
        self.git(d, "config", "--unset", "core.hooksPath")
        self.var(self.doctor(d), "WARN", "core.hooksPath ayarlı değil")

    def test_runner_yolu_yok(self):
        d = self.sap_proje()
        hook = d / ".githooks" / "pre-commit"
        self.yaz(hook, hook.read_text(encoding="utf-8").replace("project_precommit.py", "yok.py"))
        self.var(self.doctor(d), "WARN", "runner yolu diskte yok")

    def test_damga_elle_degismis(self):
        d = self.sap_proje()
        f = d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8").replace("istisna yok", "istisna var", 1), encoding="utf-8")
        r = self.doctor(d)
        self.var(r, "FAIL", "kesin yasak damgası kanonik metinden FARKLI")
        self.var(r, "FAIL", "elle değiştirilmiş")
        self.var(r, "FAIL", "davranış yüzeyinde ONAYSIZ değişiklik")

    def test_damga_farkli_ve_yok_guncelle_proje_onerir(self):
        # v0.5.2: v0.5.1'den beri %guncelle-proje eski/eksik damgayı yeniler (Z55) — doctor önce onu önermeli
        d = self.sap_proje()
        f = d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8").replace("istisna yok", "istisna var", 1), encoding="utf-8")
        self.var(self.doctor(d), "FAIL", "%guncelle-proje")
        metin = f.read_text(encoding="utf-8")
        i, j = metin.index(sap_stamp.BASLA), metin.index(sap_stamp.BITIR) + len(sap_stamp.BITIR)
        f.write_text(metin[:i] + metin[j:], encoding="utf-8")
        r = self.doctor(d)
        self.var(r, "FAIL", "damgası YOK")
        self.var(r, "FAIL", "%guncelle-proje")

    def test_damga_ikinci_kopya(self):
        d = self.sap_proje()
        f = d / "AGENTS.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n" + sap_stamp.kanonik_blok() + "\n", encoding="utf-8")
        self.var(self.doctor(d), "FAIL", "kesin yasak damgası BOZUK")

    def test_sap_disi_projede_bozuk_damga(self):
        self.global_config()
        d = self.proje()
        r = self.doctor(d)
        self.assertFalse(any("damgası" in s for s in self.satirlar(r)), "kontrol grubu: damgasız projede satır olmamalı")
        metin, _ = sap_stamp.damgala((d / "AGENTS.md").read_text(encoding="utf-8"))
        (d / "AGENTS.md").write_text(metin.replace("istisna yok", "istisna var", 1), encoding="utf-8")
        self.var(self.doctor(d), "FAIL", "kesin yasak damgası kanonik metinden FARKLI")

    def test_manifest_yok_uyari(self):
        self.global_config()
        d = self.proje()
        self.var(self.doctor(d), "WARN", "davranış yüzeyi manifest'i yok")

    def test_kanonik_bozuksa_cokmez(self):
        d = self.sap_proje()
        bozuk = self.yaz(self.tmp / "00-sap.md", "# SAP\nSAP-CORE-ID: X\n")
        doctor.results.clear()
        with mock.patch.object(sap_stamp, "SAP_CORE", bozuk), contextlib.redirect_stdout(io.StringIO()):
            doctor.check_template()
            doctor.check_project(d, False)
        mesajlar = [f"{s} {m}" for s, m in doctor.results]
        self.assertTrue(any(m.startswith("FAIL") and "kanonik metin okunamadı" in m for m in mesajlar), mesajlar)
        self.assertTrue(any(m.startswith("FAIL") and "SAP kanonik kesin yasak bölümü BOZUK" in m for m in mesajlar), mesajlar)

    # --- 2026-09-14: kurulum akışında ölçülen kör noktalar ---
    def test_git_reposu_degil_uyari(self):
        kontrol = self.sap_proje()
        self.assertFalse(any("git reposu değil" in s for s in self.satirlar(self.doctor(kontrol))),
                         "kontrol grubu: git'li projede satır olmamalı")
        d = self.proje("gitsiz", git_init=False)
        r = self.doctor(d)
        self.var(r, "WARN", "proje git reposu değil")
        self.assertFalse(any("pre-commit kablolu" in s for s in self.satirlar(r)))

    def test_sap_profili_yer_tutuculu(self):
        import json
        d = self.sap_proje()
        self.var(self.doctor(d), "PASS", "sap-project.json geçerli (profil s4_private")
        f = d / "sap-project.json"
        veri = json.loads(f.read_text(encoding="utf-8"))
        veri["sap_profile"] = "<ecc|s4_private|s4_public|btp_abap>"
        f.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        r = self.doctor(d)
        self.assertEqual(r.returncode, 1, r.stdout)
        # ⚠ Aynı metin `SAP satırı ↔ sap-project.json ÖLÇÜLEMEDİ (…)` FAIL satırının parantezinde de
        # geçer ⇒ `self.var(... parca)` o satırla da sağlanırdı. Ölçüt: satır bu metinle BAŞLAR.
        self.assertTrue(any(s.startswith("[FAIL] sap-project.json geçersiz: sap_profile")
                            for s in self.satirlar(r)), r.stdout)

    def test_sap_profil_dogrulayici_yoksa_olculemedi(self):
        d = self.sap_proje()
        doctor.results.clear()
        with mock.patch.object(doctor.inst, "AXET_HOME", self.tmp / "yok"), contextlib.redirect_stdout(io.StringIO()):
            durum, mesaj = doctor.sap_proje_dogrula(d)
        self.assertEqual(durum, "olculemedi", mesaj)
        self.assertIn("ÖLÇÜLEMEDİ", mesaj)

    def test_agents_yer_tutucu(self):
        self.assertEqual(doctor.yer_tutucular("Paket: `<source_root>/PAKETLER.md`\n<!-- yorum <x> -->\n"
                                              "Amaç: stok raporu <https://ornek.invalid>\n"), [])
        self.assertEqual(doctor.yer_tutucular("Amaç: <kısa açıklama>\nTest: <komut>\n"), ["<kısa açıklama>", "<komut>"])
        self.global_config()
        d = self.proje()
        r = self.doctor(d)
        self.var(r, "WARN", "AGENTS.md'de doldurulmamış yer tutucu")
        self.var(r, "WARN", "<kısa açıklama>")
        f = d / "AGENTS.md"
        metin = f.read_text(encoding="utf-8")
        for p in set(doctor.yer_tutucular(metin)):
            metin = metin.replace(p, "dolu")
        f.write_text(metin, encoding="utf-8")
        self.var(self.doctor(d), "PASS", "AGENTS.md yer tutucuları doldurulmuş")

    def test_frontmatter(self):
        iyi ="---\nname: x\ndescription: >\n  kısa açıklama: iki nokta blokta serbest\n---\n"
        self.assertEqual(doctor.frontmatter_problems(iyi), [])
        uzun = "---\nname: x\ndescription: " + "a" * 1025 + "\n---\n"
        self.assertTrue(any("1024" in p for p in doctor.frontmatter_problems(uzun)))
        self.assertEqual(doctor.frontmatter_problems("---\nname: x\ndescription: " + "a" * 1024 + "\n---\n"), [])
        self.assertTrue(doctor.frontmatter_problems("---\nname: x\ndescription: Kullan: şurada\n---\n"))
        self.assertTrue(doctor.frontmatter_problems("---\nname: x\n---\n"))
        self.assertTrue(doctor.frontmatter_problems("frontmatter yok"))

    # --- Y8 skill envanteri, alt süreç olarak (geçici LOCALAPPDATA) ---
    def test_proje_skill_ad_cakismasi(self):
        self.global_config()
        d = self.proje()
        r = self.doctor(d)
        self.assertFalse(any("skill ad çakışması" in s for s in self.satirlar(r)), "kontrol grubu")
        self.var(r, "PASS", "marketplace manifest'i yok")
        self.var(r, "INFO", "skill envanteri KAPSAM")
        self.yaz(d / ".axet-code" / "skills" / "recall" / "SKILL.md",
                 "---\nname: recall\ndescription: >\n  sahte kopya.\n---\n")
        r = self.doctor(d)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.var(r, "FAIL", "skill ad çakışması: 'recall' (proje)")

    def test_skills_kipi_ad_denetimi(self):
        self.global_config()
        d = self.proje()
        r = self.calistir("doctor.py", "--skills", "--ad", "recall", "--ad", "humanizer", cwd=d)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.var(r, "FAIL", "'recall' template skill adıyla AYNI")
        self.var(r, "PASS", "'humanizer' template skill adlarıyla çakışmıyor")
        self.var(r, "INFO", "template skill adları:")
        self.assertFalse(any("global config okundu" in s for s in self.satirlar(r)), "yalnız envanter koşmalı")

    def test_bozuk_config_traceback_yok(self):
        """Bulgu 3 uçtan uca: bozuk global/proje config iki kipte de traceback vermez."""
        f = self.global_config()
        d = self.proje()
        for glob_ham, proje_ham in ((b'{"options": "x"}', b"[]"), (b'{"a": "\xe7"}', b'{"a": "\xe7"}')):
            f.write_bytes(glob_ham)
            (d / ".axet-code.json").write_bytes(proje_ham)
            for args in ((), ("--skills",)):
                r = self.calistir("doctor.py", *args, cwd=d)
                self.assertNotIn("Traceback", r.stderr, f"{glob_ham} {proje_ham} {args}\n{r.stderr}")
                self.assertIn("SONUÇ:", r.stdout)
                self.var(r, "WARN", "skill envanteri ÖLÇÜLEMEDİ: proje-config")


SAP_ETIKET = "AGENTS.md SAP satırı ↔ sap-project.json"
# test_yeni_proje.SERBEST_SAP_MADDELERI ile aynı liste (iki test dosyası birbirini içe aktarmaz).
SERBEST_SAP_MADDELERI = ("- SAP profilini değiştirme", "- SAP profili kullanıcı onayı olmadan değişmez",
                         "- SAP: profil değişikliği yasak", "- SAP'de master language ile login dili aynı olmalı",
                         "- SAP: master language ve login dili aynı")
# re-gate MEDIUM-1: kanonik satırın yanında değer gibi görünen FARKLI serbest değer → ÖLÇÜLEMEDİ (sahte PASS yok).
# re-gate LOW-3: anahtar başka sözcüğün parçasıysa (userprofile) anahtar değil → tutarlı. (test_yeni_proje'de aynı listeler.)
DEGER_BENZERI_SAP_MADDELERI = ("- SAP notu: master language en", "- SAP notu: master language EN.",
                               "- SAP notu: master_language en", "- SAP notu: sistem profili ecc.",
                               "- SAP notu: profil s4-public")
KELIME_SINIRI_SAP_MADDELERI = ("- SAP userprofile: SAP_ALL", "- SAP: yetkiprofili: Z_ALL")
KANONIK_SAP ="- SAP (varsa): sistem profili s4_private · sürüm 2023 · master_language: {dil} · aktif paket: — x"


class SapSatiriTest(GeciciTest):
    """AGENTS.md `- SAP` satırı ↔ sap-project.json (yalnız doctor raporu). Fikstür: sap_profile=s4_private,
    release=2023, master_language=TR, cleancore_policy=balanced (_helpers.proje)."""

    def setUp(self) -> None:
        super().setUp()
        self.env["LOCALAPPDATA"] = str(self.tmp / "_lad")
        self.global_config()

    def satir_yaz(self, d, satir: str | None) -> None:
        f = d / "AGENTS.md"
        satirlar = f.read_text(encoding="utf-8").splitlines(keepends=True)
        i = next(n for n, s in enumerate(satirlar) if s.startswith("- SAP"))
        if satir is None:
            del satirlar[i]
        else:
            satirlar[i] = satir + "\n"
        f.write_text("".join(satirlar), encoding="utf-8")

    def kos(self, d) -> list[str]:
        doctor.results.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            doctor.check_project(d, False)
        return [f"[{s}] {m}" for s, m in doctor.results if SAP_ETIKET in m]

    def test_tablo(self):
        d = self.proje(sap=True)
        tablo = [
            # (etiket, satır, [(durum, [parçalar])] — satırla ilgili TÜM doctor satırları, sırasıyla)
            ("tutarlı", KANONIK_SAP.format(dil="TR"), [("PASS", ["tutarlı", "s4_private", "TR"])]),
            ("EN↔TR çelişki", KANONIK_SAP.format(dil="EN"), [("FAIL", ["ÇELİŞKİ", "master_language EN", "TR"])]),
            ("profil çelişki", "- SAP (varsa): sistem profili ecc · sürüm 2023 · master_language: TR",
             [("FAIL", ["ÇELİŞKİ", "sistem profili ecc", "s4_private"])]),
            ("backtick'li", "- SAP (varsa): sistem profili `s4_private` · master_language: `EN`",
             [("FAIL", ["master_language EN", "TR"])]),
            ("backtick'li tutarlı", "- SAP (varsa): sistem profili `s4_private` · master_language: `tr`", [("PASS", ["tutarlı"])]),
            ("**SAP** biçimi", "- **SAP**: sistem profili s4_private · master_language: EN", [("FAIL", ["master_language EN"])]),
            ("Master_Language", "- SAP: profil S4_PRIVATE · Master_Language: tr", [("PASS", ["tutarlı"])]),
            ("Master_Language çelişki", "- SAP: profil s4_private · Master_Language: EN", [("FAIL", ["master_language EN"])]),
            ("okunamayan satır", "- SAP: sistem profili s4_private · master_language: English",
             [("FAIL", ["ÖLÇÜLEMEDİ", "master_language okunamadı"])]),
            ("şablon yer tutucusu", "- SAP (varsa): sistem profili <…> · master_language: <TR|EN> · aktif paket: <…>",
             [("FAIL", ["ÖLÇÜLEMEDİ", "sistem profili okunamadı"])]),
            ("satır yok", None, [("FAIL", ["ÖLÇÜLEMEDİ", "`- SAP` satırı yok"])]),
            # bug gate Y-a: anahtarsız `- SAP…` maddesi (kural) atlanır; anahtarlı satırlar birbirini tutmazsa ÖLÇÜLEMEDİ
            ("anahtarsız kural önce", "- SAP'ye yazmadan önce onay al\n" + KANONIK_SAP.format(dil="TR"), [("PASS", ["tutarlı"])]),
            ("anahtarsız kural önce + çelişki", "- SAP'ye yazmadan önce onay al\n" + KANONIK_SAP.format(dil="EN"),
             [("FAIL", ["ÇELİŞKİ", "master_language EN"])]),
            ("kontrol: yalnız anahtarsız madde", "- SAP'ye yazmadan önce onay al",
             [("FAIL", ["ÖLÇÜLEMEDİ", "sistem profili okunamadı"])]),
            ("iki anahtarlı satır aynı", "- SAP: sistem profili s4_private · master_language: TR\n- SAP notu: master_language: tr",
             [("PASS", ["tutarlı"])]),
            ("iki anahtarlı satır farklı", "- SAP: sistem profili s4_private · master_language: TR\n"
             "- SAP: sistem profili ecc · master_language: TR", [("FAIL", ["ÖLÇÜLEMEDİ", "farklı değer"])]),
            # bug gate MEDIUM-2: gerçek İngilizce satır okunur; anahtar biçimli bozuk değer ÖLÇÜLEMEDİ kalır
            ("İngilizce anahtar", "- SAP: profile s4_private · master language TR", [("PASS", ["tutarlı"])]),
            ("anahtar biçimi bozuk değer", "- SAP: profil: s4x · master_language: TR",
             [("FAIL", ["ÖLÇÜLEMEDİ", "'s4x'"])]),
            ("bozuk anahtar biçimi + doğru satır", "- SAP: profil: s4x\n" + KANONIK_SAP.format(dil="TR"),
             [("FAIL", ["ÖLÇÜLEMEDİ", "farklı değer"])]),
            ("release farkı WARN", "- SAP (varsa): sistem profili s4_private · sürüm 2022 · master_language: TR",
             [("PASS", ["tutarlı"]), ("WARN", ["sürüm 2022", "2023"])]),
            ("cleancore_policy farkı WARN", "- SAP: sistem profili s4_private · sürüm 2023 · master_language: TR · "
             "Cleancore Policy: strict", [("PASS", ["tutarlı"]), ("WARN", ["cleancore_policy strict", "balanced"])]),
            ("çelişki + release farkı", "- SAP: sistem profili ecc · sürüm 2022 · master_language: TR",
             [("FAIL", ["sistem profili ecc"]), ("WARN", ["sürüm 2022"])]),
        ]
        # bug gate MEDIUM-2: serbest metinde profil/dil geçen maddeler doğru satırdan önce ya da sonra → PASS
        for serbest in SERBEST_SAP_MADDELERI:
            tablo.append((f"serbest önce: {serbest}", f"{serbest}\n" + KANONIK_SAP.format(dil="TR"), [("PASS", ["tutarlı"])]))
            tablo.append((f"serbest sonra: {serbest}", KANONIK_SAP.format(dil="TR") + f"\n{serbest}", [("PASS", ["tutarlı"])]))
        # re-gate MEDIUM-1: değer benzeri farklı serbest değer kanonik satırın önünde/arkasında → ÖLÇÜLEMEDİ
        for benzer in DEGER_BENZERI_SAP_MADDELERI:
            tablo.append((f"değer benzeri önce: {benzer}", f"{benzer}\n" + KANONIK_SAP.format(dil="TR"),
                          [("FAIL", ["ÖLÇÜLEMEDİ", "farklı değer"])]))
            tablo.append((f"değer benzeri sonra: {benzer}", KANONIK_SAP.format(dil="TR") + f"\n{benzer}",
                          [("FAIL", ["ÖLÇÜLEMEDİ", "farklı değer"])]))
        # re-gate LOW-3: kelime sınırı
        for parca in KELIME_SINIRI_SAP_MADDELERI:
            tablo.append((f"kelime sınırı: {parca}", KANONIK_SAP.format(dil="TR") + f"\n{parca}", [("PASS", ["tutarlı"])]))
        f = d / "AGENTS.md"
        orijinal = f.read_text(encoding="utf-8")
        for etiket, satir, beklenen in tablo:
            with self.subTest(etiket):
                f.write_text(orijinal, encoding="utf-8")
                self.satir_yaz(d, satir)
                satirlar = self.kos(d)
                self.assertEqual([s.split("]")[0][1:] for s in satirlar], [b[0] for b in beklenen], "\n".join(satirlar))
                for s, (_, parcalar) in zip(satirlar, beklenen):
                    for p in parcalar:
                        self.assertIn(p, s)

    def test_json_yoksa_basilmaz(self):
        d = self.proje(sap=True)
        self.satir_yaz(d, KANONIK_SAP.format(dil="EN"))
        self.assertTrue(any(s.startswith("[FAIL]") for s in self.kos(d)), "kontrol grubu: json varken satır basılmalı")
        (d / "sap-project.json").unlink()
        self.assertEqual(self.kos(d), [])
        sapsiz = self.proje("sapsiz")
        self.satir_yaz(sapsiz, KANONIK_SAP.format(dil="EN"))
        self.assertEqual(self.kos(sapsiz), [])

    def test_json_gecersizse_olculemedi(self):
        d = self.proje(sap=True)
        self.satir_yaz(d, KANONIK_SAP.format(dil="TR"))
        self.assertTrue(any(s.startswith("[PASS]") for s in self.kos(d)), "kontrol grubu")
        f = d / "sap-project.json"
        veri = json.loads(f.read_text(encoding="utf-8"))
        veri["sap_profile"] = "<ecc|s4_private|s4_public|btp_abap>"
        f.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        satirlar = self.kos(d)
        self.assertEqual(len(satirlar), 1, satirlar)
        self.assertTrue(satirlar[0].startswith("[FAIL]") and "ÖLÇÜLEMEDİ" in satirlar[0], satirlar)

    def test_agents_yoksa_olculemedi(self):
        d = self.proje(sap=True)
        (d / "AGENTS.md").unlink()
        satirlar = self.kos(d)
        self.assertEqual(len(satirlar), 1, satirlar)
        self.assertTrue(satirlar[0].startswith("[FAIL]") and "ÖLÇÜLEMEDİ" in satirlar[0] and "AGENTS.md yok" in satirlar[0])

    def test_template_kokunde_basilmaz(self):
        self.assertEqual(self.kos(doctor.inst.AXET_HOME), [])

    def test_uctan_uca_yeni_proje_pass_new_project_sablonu_olculemedi(self):
        """Gerçek iskelet: yeni_proje.py satırı doldurur → PASS. new_project.py --sap şablon satırını bırakır → ÖLÇÜLEMEDİ."""
        self.global_config(sap=True)
        d = self.tmp / "uctan"
        r = self.calistir("yeni_proje.py", str(d), "--no-input", "--sap-profile", "s4_private", "--release", "2023",
                          "--master-language", "TR", "--cleancore-policy", "balanced", "--purpose", "Deneme")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        r = self.calistir("doctor.py", cwd=d)
        self.assertTrue(any(s.startswith("[PASS]") and SAP_ETIKET in s for s in r.stdout.splitlines()), r.stdout)
        self.assertIn("SONUÇ: 0 FAIL", r.stdout)
        ham = self.proje("ham", sap=True)  # sap-project.json dolu, AGENTS.md SAP satırı şablondaki gibi
        r = self.calistir("doctor.py", cwd=ham)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(any(s.startswith("[FAIL]") and SAP_ETIKET in s and "ÖLÇÜLEMEDİ" in s for s in r.stdout.splitlines()),
                        r.stdout)


# Marketplace'ten ölçülen biçim (M2 humanizer): `|-` blok açıklama, ek anahtarlar, iç içe metadata.
PIPE_DASH_SKILL = ("---\nname: {ad}\ndescription: |-\n"
                   + "  Remove signs of AI-generated writing from text: use when editing or reviewing prose.\n" * 5
                   + "license: MIT\nmetadata:\n  author: ornek\n  version: 1.0.0\n---\n\n# {ad}\n\nMetni sadeleştir.\n")


class SkillEnvanteriTest(GeciciTest):
    """Y8: template skill'leri ↔ template dışı skill'ler. Gerçek %LOCALAPPDATA% ve template klasörleri kullanılmaz."""

    def setUp(self) -> None:
        super().setUp()
        self.sablon = self.tmp / "sablon"
        self.lad = self.tmp / "_lad"
        self.lad.mkdir()
        for ad in ("recall", "code-review"):
            self.skill(self.sablon / "skills" / ad, ad)
        self.skill(self.sablon / "skills-sap" / "sap-adt-foundation", "sap-adt-foundation")
        yamalar = [mock.patch.object(doctor.inst, "AXET_HOME", self.sablon),
                   mock.patch.object(doctor.inst, "SKILLS_DIR", self.sablon / "skills"),
                   mock.patch.object(doctor.inst, "SAP_SKILLS_DIR", self.sablon / "skills-sap")]
        for y in yamalar:
            y.start()
            self.addCleanup(y.stop)
        self.proj = self.tmp / "proje"
        self.proj.mkdir()

    def skill(self, dizin, ad, metin=None):
        return self.yaz(dizin / "SKILL.md", metin if metin is not None else
                        f"---\nname: {ad}\ndescription: >\n  {ad} deneme skill'i.\n---\n\n# {ad}\n")

    def manifest(self, *kayitlar, ham=None):
        f = self.lad / "axet-code" / "skills_manifest.json"
        veri = {"skills": {f"id-{i}": {"id": f"id-{i}", "name": ad, "scope": scope, "path": str(yol),
                                       "updated_at": "2026-06-11T07:57:19.301Z", "visibility": "public", "active": True}
                           for i, (ad, scope, yol) in enumerate(kayitlar)}}
        self.yaz(f, ham if ham is not None else json.dumps(veri))
        return f

    def kos(self, cwd="proje", cfg=None, env=None):
        doctor.results.clear()
        inv = doctor.check_skills(self.proj if cwd == "proje" else cwd, cfg or {}, localappdata=str(self.lad),
                                  env=env if env is not None else {})
        return inv, [f"[{s}] {m}" for s, m in doctor.results]

    def var(self, satirlar, durum, parca):
        self.assertTrue(any(s.startswith(f"[{durum}]") and parca in s for s in satirlar), "\n".join(satirlar))

    def yok(self, satirlar, durum, parca):
        self.assertFalse(any(s.startswith(f"[{durum}]") and parca in s for s in satirlar), "\n".join(satirlar))

    # --- bug gate düzeltmeleri ---
    def test_baska_projenin_kaydi_degerlendirilmez(self):
        """Bulgu 1: manifest kullanıcı düzeyinde; başka projenin scope=project kaydı burada FAIL/WARN üretmez."""
        kotu = "---\nname: recall\ndescription: Kullan: ABAP deploy\n---\n"  # ad çakışması + frontmatter + SAP
        baska = self.tmp / "baska-proje" / ".axet-code" / "skills" / "recall"
        self.skill(baska, "recall", kotu)
        self.manifest(("recall", "project", baska))
        for cwd in ("proje", None):
            _, satirlar = self.kos(cwd=cwd)
            self.assertFalse(any(s.startswith("[FAIL]") for s in satirlar), "\n".join(satirlar))
            self.yok(satirlar, "WARN", "SAP işine dokunan")
            self.var(satirlar, "INFO", "başka projeye ait marketplace kaydı")
            self.var(satirlar, "INFO", str(baska))
            self.var(satirlar, "PASS", "template dışı 0 · başka projeye ait 1 (değerlendirilmedi)")
        # scope=global aynı yol → eskisi gibi değerlendirilir
        self.manifest(("recall", "global", baska))
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (manifest · marketplace · scope=global)")
        self.var(satirlar, "WARN", "global kapsamlı marketplace skill'i: 'recall'")
        # kontrol grubu: aynı kayıt bu projenin altında → FAIL
        burada = self.proj / ".axet-code" / "skills" / "recall"
        self.skill(burada, "recall", kotu)
        self.manifest(("recall", "project", burada))
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (proje · marketplace · scope=project)")
        self.var(satirlar, "FAIL", "`skill_uninstall recall`")
        self.var(satirlar, "FAIL", "template dışı skill frontmatter")
        self.yok(satirlar, "INFO", "başka projeye ait")

    def test_ust_dizinden_alt_projenin_kaydi_degerlendirilmez(self):
        """N1: cwd monorepo kökü; alt projenin `.axet-code/skills` kaydı bu dizinde yüklenmez → INFO."""
        kotu = "---\nname: recall\ndescription: Kullan: ABAP deploy\n---\n"
        alt = self.proj / "pA" / ".axet-code" / "skills" / "recall"
        self.skill(alt, "recall", kotu)
        self.manifest(("recall", "project", alt))
        _, satirlar = self.kos()
        self.assertFalse(any(s.startswith("[FAIL]") for s in satirlar), "\n".join(satirlar))
        self.yok(satirlar, "WARN", "SAP işine dokunan")
        self.var(satirlar, "INFO", f"başka projeye ait marketplace kaydı (bu dizinde yüklenmez; değerlendirilmedi): 'recall'")
        self.var(satirlar, "INFO", str(alt))
        # cwd altında ama .axet-code/skills dışında başka bir yol da INFO
        diger = self.proj / "araclar" / "recall"
        self.skill(diger, "recall", kotu)
        self.manifest(("recall", "project", diger))
        _, satirlar = self.kos()
        self.assertFalse(any(s.startswith("[FAIL]") for s in satirlar), "\n".join(satirlar))
        self.var(satirlar, "INFO", str(diger))
        # kontrol grubu: kayıt cwd/.axet-code/skills altında → FAIL
        burada = self.proj / ".axet-code" / "skills" / "recall"
        self.skill(burada, "recall", kotu)
        self.manifest(("recall", "project", burada))
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (proje · marketplace · scope=project)")

    def test_manifest_scope_bilinmiyor(self):
        """N2: scope eksik/bilinmeyen ve taranan dizinle eşleşmeyen kayıt → FAIL yok, WARN ÖLÇÜLEMEDİ."""
        kotu = "---\nname: recall\ndescription: Kullan: ABAP deploy\n---\n"
        baska = self.tmp / "baska-proje" / ".axet-code" / "skills" / "recall"
        self.skill(baska, "recall", kotu)
        self.manifest(ham=json.dumps({"skills": {"x": {"id": "x", "name": "recall", "path": str(baska)}}}))
        _, satirlar = self.kos()
        self.assertFalse(any(s.startswith("[FAIL]") for s in satirlar), "\n".join(satirlar))
        self.var(satirlar, "WARN", "manifest kaydında scope bilinmiyor (None) — ÖLÇÜLEMEDİ")
        self.var(satirlar, "PASS", "scope bilinmiyor 1 (değerlendirilmedi)")
        self.manifest(("recall", "workspace", baska))
        _, satirlar = self.kos()
        self.assertFalse(any(s.startswith("[FAIL]") for s in satirlar), "\n".join(satirlar))
        self.var(satirlar, "WARN", "manifest kaydında scope bilinmiyor ('workspace') — ÖLÇÜLEMEDİ")
        # kontrol grubu 1: aynı yol scope=global → değerlendirilir
        self.manifest(("recall", "global", baska))
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall'")
        self.yok(satirlar, "WARN", "scope bilinmiyor")
        # kontrol grubu 2: scope'suz ama taranan bir dizinle eşleşiyor (yüklenen kopya) → değerlendirilir
        burada = self.proj / ".axet-code" / "skills" / "recall"
        self.skill(burada, "recall", kotu)
        self.manifest(ham=json.dumps({"skills": {"x": {"id": "x", "name": "recall", "path": str(burada)}}}))
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (proje · marketplace)")
        self.yok(satirlar, "WARN", "scope bilinmiyor")

    def test_okunamayan_dizin_olculemedi(self):
        """Bulgu 2: iterdir OSError → çıktı kaybolmaz, WARN + KAPSAM'da ÖLÇÜLEMEDİ."""
        d = self.proj / ".axet-code" / "skills"
        self.skill(d / "yerel", "yerel")
        _, satirlar = self.kos()
        self.yok(satirlar, "WARN", "skill envanteri ÖLÇÜLEMEDİ")  # kontrol grubu
        asil = Path.iterdir

        def bozuk(p):
            if p == d:
                raise PermissionError(13, "Erişim engellendi", str(p))
            return asil(p)
        with mock.patch.object(Path, "iterdir", bozuk):
            inv, satirlar = self.kos()
        self.var(satirlar, "WARN", f"skill envanteri ÖLÇÜLEMEDİ: {d} (PermissionError")
        self.var(satirlar, "INFO", "— ÖLÇÜLEMEDİ: ")
        self.var(satirlar, "PASS", "skill envanteri: template 3")
        self.assertNotIn("yerel", {k["ad"] for k in inv["kayitlar"]})

    def test_junction_ayni_skill_bir_kez(self):
        """Bulgu 4: junction üzerinden gelen aynı skill realpath ile tekilleşir."""
        hedef = self.proj / ".axet-code" / "skills"
        self.skill(hedef / "notlar", "notlar")
        kopya = self.tmp / "kopya"
        self.skill(kopya / "notlar", "notlar")
        inv, _ = self.kos(env={"AXET_SKILLS_DIR": str(kopya)})
        self.assertEqual(sum(k["ad"] == "notlar" for k in inv["kayitlar"]), 2, "kontrol grubu: gerçekten ayrı iki dizin")
        if os.name != "nt":
            self.skipTest("junction yalnız Windows")
        bag = self.tmp / "bag"
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(bag), str(hedef)], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0 or not (bag / "notlar" / "SKILL.md").is_file():
            self.skipTest(f"junction kurulamadı: rc={r.returncode} {r.stdout} {r.stderr}")
        try:
            self.assertNotEqual(doctor.inst._norm(bag / "notlar"), doctor.inst._norm(hedef / "notlar"))
            inv, _ = self.kos(env={"AXET_SKILLS_DIR": str(bag)})
            self.assertEqual(sum(k["ad"] == "notlar" for k in inv["kayitlar"]), 1)
        finally:
            os.rmdir(bag)  # yalnız bağ kaldırılır, hedefe dokunulmaz
        self.assertTrue((hedef / "notlar" / "SKILL.md").is_file())

    def test_manifest_yol_yazimi_esitlenir(self):
        """Bulgu 5: manifest yolu `/` ile ve farklı harf büyüklüğüyle yazılsa da eşleşir."""
        hum = self.proj / ".axet-code" / "skills" / "humanizer"
        self.skill(hum, "humanizer", PIPE_DASH_SKILL.format(ad="humanizer"))
        self.manifest(("humanizer", "project", self.proj / ".axet-code" / "skills" / "humanizer2"))
        inv, _ = self.kos()
        yerel = [k for k in inv["kayitlar"] if k["kaynak"] == "proje"]
        self.assertEqual([k["marketplace"] for k in yerel], [False], "kontrol grubu: farklı yol eşleşmemeli")
        yazim = hum.as_posix()
        if os.name == "nt":
            yazim = yazim.swapcase()
        self.assertNotIn("\\", yazim)
        self.assertNotEqual(yazim, str(hum))
        self.manifest(("humanizer", "project", yazim))
        inv, _ = self.kos()
        hum_kayit = [k for k in inv["kayitlar"] if k["ad"] == "humanizer"]
        self.assertEqual([(k["kaynak"], k["marketplace"], k["scope"]) for k in hum_kayit], [("proje", True, "project")])

    # --- envanter ---
    def test_kaynaklar_ve_marketplace_eslesmesi(self):
        dis_cfg = self.tmp / "dis-skills"
        self.skill(dis_cfg / "gitlab", "gitlab")
        ortam = self.tmp / "ortam-skills"
        self.skill(ortam / "notlar", "notlar")
        hum = self.proj / ".axet-code" / "skills" / "humanizer"
        self.skill(hum, "humanizer", PIPE_DASH_SKILL.format(ad="humanizer"))
        self.manifest(("humanizer", "project", hum))
        cfg = {"options": {"skills_paths": [(self.sablon / "skills").as_posix(), dis_cfg.as_posix()]}}
        inv, satirlar = self.kos(cfg=cfg, env={"AXET_SKILLS_DIR": str(ortam)})
        ozet = {(k["ad"], k["kaynak"], k["marketplace"], k["scope"]) for k in inv["kayitlar"]}
        self.assertEqual(ozet, {("recall", "template", False, None), ("code-review", "template", False, None),
                                ("sap-adt-foundation", "template", False, None), ("gitlab", "global-config", False, None),
                                ("notlar", "AXET_SKILLS_DIR", False, None), ("humanizer", "proje", True, "project")})
        self.assertEqual(inv["template_adlari"], {"recall", "code-review", "sap-adt-foundation"})
        self.var(satirlar, "PASS", "template 3 · template dışı 3")
        self.var(satirlar, "PASS", "marketplace manifest'i okundu: 1 kayıt")
        self.var(satirlar, "INFO", "skill envanteri KAPSAM")
        self.assertFalse(any(s.startswith("[FAIL]") for s in satirlar), "\n".join(satirlar))

    def test_proje_disinda_yalniz_global_kaynaklar(self):
        self.skill(self.proj / ".axet-code" / "skills" / "yerel", "yerel")
        inv, _ = self.kos()
        self.assertIn("yerel", {k["ad"] for k in inv["kayitlar"]}, "kontrol grubu: proje kipinde bulunmalı")
        inv, satirlar = self.kos(cwd=None)
        self.assertNotIn("yerel", {k["ad"] for k in inv["kayitlar"]})
        self.var(satirlar, "INFO", "skill envanteri KAPSAM")

    # --- ad çakışması ---
    def test_ad_cakismasi_fail(self):
        self.skill(self.proj / ".axet-code" / "skills" / "recall-plus", "recall-plus")
        _, satirlar = self.kos()
        self.yok(satirlar, "FAIL", "skill ad çakışması")  # kontrol grubu: benzer ama farklı ad
        self.skill(self.proj / ".axet-code" / "skills" / "recall", "recall")
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (proje)")
        self.var(satirlar, "FAIL", "model yanlışını seçebilir (ölçüldü)")
        self.var(satirlar, "FAIL", "yeniden adlandır")

    def test_ad_cakismasi_marketplace_cozumu(self):
        d = self.proj / ".axet-code" / "skills" / "code-review"
        self.skill(d, "code-review", PIPE_DASH_SKILL.format(ad="code-review"))
        self.manifest(("code-review", "project", d))
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "`skill_uninstall code-review`")

    def test_ad_cakismasi_baska_template_klonu(self):
        """Y6-A gate 2 / Y1b: çakışan skill başka bir aXet template klonundansa çözüm o klonda `install.py --uninstall`,
        "yeniden adlandır" DEĞİL (template skill'ini yeniden adlandırmak yanlış çözümdür)."""
        eski = self.tmp / "eski-klon"
        self.skill(eski / "skills" / "recall", "recall")
        self.yaz(eski / "core" / "00-temel.md", "# aXet çekirdek\nCORE-ID: AXET-CORE-0.2.0\n")
        cfg = {"options": {"skills_paths": [(eski / "skills").as_posix()]}}
        _, satirlar = self.kos(cfg=cfg)
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (global-config)")
        self.var(satirlar, "FAIL", f"başka bir aXet template klonu da kayıtlı: {eski}")
        self.var(satirlar, "FAIL", "o klonda `install.py --uninstall`")
        self.yok(satirlar, "FAIL", "yeniden adlandır")
        # kontrol grubu 1: aynı yerleşim ama çekirdek dosyasında CORE-ID imzası yok → dış skill, eski mesaj
        self.yaz(eski / "core" / "00-temel.md", "# başka bir proje\nCORE-ID: BASKA-0.1\n")
        _, satirlar = self.kos(cfg=cfg)
        self.var(satirlar, "FAIL", "skill ad çakışması: 'recall' (global-config)")
        self.var(satirlar, "FAIL", "yeniden adlandır")
        self.yok(satirlar, "FAIL", "başka bir aXet template klonu")
        # kontrol grubu 2: çekirdek dosyası hiç yok → dış skill, eski mesaj
        (eski / "core" / "00-temel.md").unlink()
        _, satirlar = self.kos(cfg=cfg)
        self.var(satirlar, "FAIL", "yeniden adlandır")
        self.yok(satirlar, "FAIL", "başka bir aXet template klonu")

    # --- frontmatter ---
    def test_dis_skill_frontmatter(self):
        self.skill(self.proj / ".axet-code" / "skills" / "humanizer", "humanizer", PIPE_DASH_SKILL.format(ad="humanizer"))
        self.assertEqual(doctor.frontmatter_problems(PIPE_DASH_SKILL.format(ad="humanizer")), [])
        _, satirlar = self.kos()
        self.yok(satirlar, "FAIL", "template dışı skill frontmatter")  # kontrol grubu: geçerli `|-` biçimi
        self.skill(self.proj / ".axet-code" / "skills" / "bozuk", "bozuk",
                   "---\nname: bozuk\ndescription: Kullan: şurada\n---\n")
        self.skill(self.proj / ".axet-code" / "skills" / "uzun", "uzun",
                   "---\nname: uzun\ndescription: |-\n" + ("  " + "a" * 99 + "\n") * 11 + "---\n")
        _, satirlar = self.kos()
        self.var(satirlar, "FAIL", "template dışı skill frontmatter (aXet sessizce düşürür): 'bozuk'")
        self.var(satirlar, "FAIL", "'uzun' (proje)")
        self.var(satirlar, "FAIL", "aXet sınırı 1024")
        self.yok(satirlar, "FAIL", "'humanizer'")

    # --- SAP konusu ---
    def test_sap_konulu_dis_skill_warn(self):
        self.skill(self.proj / ".axet-code" / "skills" / "tasima", "tasima",
                   "---\nname: tasima\ndescription: >\n  Transportation planning notes; Sapanca trip.\n---\n# tasima\n")
        self.skill(self.proj / ".axet-code" / "skills" / "ci", "ci",
                   "---\nname: ci\ndescription: >\n  Deploy the app to production; transport layer notes.\n---\n# ci\n")
        self.assertEqual(doctor.sap_konulari("Deploy the app; transport layer."), [])  # zayıf terim tek başına sayılmaz
        self.assertEqual(doctor.sap_konulari("ABAP transport ve deploy"), ["abap", "deploy", "transport"])
        # N3: yanlış pozitif örnekleri (kontrol grubu) ↔ gerçek SAP metni
        for metin in ("ADT (abstract data type) deploy", "bıçak sap deploy", "sapma payı", "Sapanca", "ASAP deploy",
                      "SAP_BASIS deploy"):
            self.assertEqual(doctor.sap_konulari(metin), [], metin)
        self.assertEqual(doctor.sap_konulari("SAP'ye transport açar"), ["sap", "transport"])
        self.assertEqual(doctor.sap_konulari("SAP deploy"), ["deploy", "sap"])
        self.assertEqual(doctor.sap_konulari("ADT ile abap"), ["abap", "adt"])
        self.assertEqual(doctor.sap_konulari("S/4HANA deploy"), ["deploy", "s/4hana"])
        _, satirlar = self.kos()
        self.yok(satirlar, "WARN", "SAP işine dokunan dış skill")  # kontrol grubu: kelime sınırı + genel deploy/transport
        self.skill(self.proj / ".axet-code" / "skills" / "abaper", "abaper",
                   "---\nname: abaper\ndescription: >\n  Kod yazar.\n---\n# abaper\nADT ile ABAP'a yazar, sonra deploy eder.\n")
        _, satirlar = self.kos()
        self.var(satirlar, "WARN", "SAP işine dokunan dış skill: 'abaper'")
        self.var(satirlar, "WARN", "abap, adt, deploy")
        self.var(satirlar, "WARN", "kesin yasaklar geçerlidir")
        self.yok(satirlar, "WARN", "'tasima'")

    def test_template_skill_sap_konusu_uyari_vermez(self):
        _, satirlar = self.kos()
        self.yok(satirlar, "WARN", "SAP işine dokunan dış skill")  # sap-adt-foundation template'te

    # --- manifest ---
    def test_manifest_global_scope_warn(self):
        d = self.proj / ".axet-code" / "skills" / "humanizer"
        self.skill(d, "humanizer", PIPE_DASH_SKILL.format(ad="humanizer"))
        self.manifest(("humanizer", "project", d))
        _, satirlar = self.kos()
        self.yok(satirlar, "WARN", "global kapsamlı marketplace skill'i")  # kontrol grubu
        g = self.tmp / "global-yeri" / "gitlab"
        self.skill(g, "gitlab")
        self.manifest(("humanizer", "project", d), ("gitlab", "global", g), ("hayalet", "global", self.tmp / "yok"))
        inv, satirlar = self.kos()
        self.var(satirlar, "WARN", "global kapsamlı marketplace skill'i: 'gitlab' (manifest · marketplace · scope=global)")
        self.var(satirlar, "WARN", "'hayalet'")
        self.var(satirlar, "INFO", "manifest kaydının SKILL.md'si diskte yok: 'hayalet'")
        self.assertEqual(sum(1 for k in inv["kayitlar"] if k["ad"] == "humanizer"), 1)

    def test_manifest_yok_bozuk_olculemedi(self):
        _, satirlar = self.kos()
        self.var(satirlar, "PASS", "marketplace manifest'i yok (marketplace kurulumu yok)")
        self.manifest(ham="{bozuk json")
        _, satirlar = self.kos()
        self.var(satirlar, "WARN", "marketplace manifest'i ÖLÇÜLEMEDİ — okunamadı/bozuk")
        self.manifest(ham='{"baska": 1}')
        _, satirlar = self.kos()
        self.var(satirlar, "WARN", "'skills' nesnesi yok")
        doctor.results.clear()
        doctor.check_skills(self.proj, {}, env={})  # LOCALAPPDATA yok
        self.assertTrue(any(s == "WARN" and "ÖLÇÜLEMEDİ — LOCALAPPDATA" in m for s, m in doctor.results), doctor.results)

    def test_manifest_yolu_ortamdan(self):
        self.assertEqual(doctor.manifest_yolu(env={"LOCALAPPDATA": str(self.lad)}),
                         self.lad / "axet-code" / "skills_manifest.json")
        self.assertIsNone(doctor.manifest_yolu(env={}))


class BozukConfigTest(GeciciTest):
    """Bulgu 3: bozuk global/proje config traceback vermez; FAIL/ÖLÇÜLEMEDİ satırına dönüşür (in-process)."""

    def setUp(self) -> None:
        super().setUp()
        self.cfg = self.xdg / "axet-code" / "axet-code.json"
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        y = mock.patch.object(doctor.inst, "config_path", return_value=self.cfg)
        y.start()
        self.addCleanup(y.stop)

    def global_kos(self, ham: bytes) -> list[str]:
        self.cfg.write_bytes(ham)
        doctor.results.clear()
        cfg, _ = doctor.check_global()
        doctor.check_skills(None, cfg, localappdata=str(self.tmp / "_lad"), env={})
        return [f"[{s}] {m}" for s, m in doctor.results]

    def proje_kos(self, ham: bytes) -> list[str]:
        d = self.tmp / "p"
        d.mkdir(exist_ok=True)
        (d / ".axet-code.json").write_bytes(ham)
        doctor.results.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            doctor.check_project(d, False)
            doctor.check_skills(d, {}, localappdata=str(self.tmp / "_lad"), env={})
        return [f"[{s}] {m}" for s, m in doctor.results]

    def var(self, satirlar, durum, parca):
        self.assertTrue(any(s.startswith(f"[{durum}]") and parca in s for s in satirlar), "\n".join(satirlar))

    def test_global_config_bozuk(self):
        self.global_config()
        s = self.global_kos(self.cfg.read_bytes())  # kontrol grubu: install.py biçimi
        self.var(s, "PASS", "global config okundu")
        self.assertFalse(any("nesne değil" in x or "okunamadı" in x or "ÖLÇÜLEMEDİ:" in x for x in s), "\n".join(s))
        s = self.global_kos(b'{"options": "x"}')
        self.var(s, "FAIL", "global config 'options' nesne değil (str)")
        self.var(s, "WARN", "skill envanteri ÖLÇÜLEMEDİ: global-config: 'options' nesne değil")
        s = self.global_kos(b'{"a": "\xe7"}')
        self.var(s, "FAIL", "global config geçerli JSON değil ya da okunamadı")
        self.var(s, "FAIL", "UnicodeDecodeError")
        s = self.global_kos(b"[]")
        self.var(s, "FAIL", "global config kök değeri nesne değil (list)")
        s = self.global_kos(b'{"options": {"context_paths": "x", "skills_paths": 5}, "permissions": "y"}')
        self.var(s, "FAIL", "context_paths içinde")
        self.var(s, "WARN", "skill envanteri ÖLÇÜLEMEDİ: global-config: 'skills_paths' liste değil (int)")

    def test_proje_config_bozuk(self):
        s = self.proje_kos(b"{}")  # kontrol grubu
        self.var(s, "PASS", "proje config'i şablon izin kurallarını ezmiyor")
        self.assertFalse(any("ÖLÇÜLEMEDİ" in x and "proje-config" in x for x in s), "\n".join(s))
        s = self.proje_kos(b"[]")
        self.var(s, "FAIL", ".axet-code.json kök değeri nesne değil (list)")
        self.var(s, "WARN", "skill envanteri ÖLÇÜLEMEDİ: proje-config: kök değeri nesne değil")
        s = self.proje_kos(b'{"a": "\xe7"}')
        self.var(s, "FAIL", ".axet-code.json geçerli JSON değil ya da okunamadı")
        self.var(s, "WARN", "skill envanteri ÖLÇÜLEMEDİ: proje-config")
        s = self.proje_kos(b'{"options": "x", "permissions": "y"}')
        self.var(s, "FAIL", ".axet-code.json 'options' nesne değil (str)")
        self.var(s, "WARN", "'permissions' nesne değil → izin kuralı ezme denetimi ÖLÇÜLEMEDİ")
        self.assertFalse(any("ezmiyor" in x for x in s), "\n".join(s))

    def test_proje_izin_kurali_nesne_degil(self):
        """N4: permissions / permissions.rules nesne değilse sessiz PASS yok, WARN ÖLÇÜLEMEDİ."""
        s = self.proje_kos(b'{"permissions": {"rules": {}}}')  # kontrol grubu
        self.var(s, "PASS", "proje config'i şablon izin kurallarını ezmiyor")
        self.assertFalse(any("izin kuralı ezme denetimi ÖLÇÜLEMEDİ" in x for x in s), "\n".join(s))
        s = self.proje_kos(b'{"permissions": {"rules": 5}}')
        self.var(s, "WARN", "'permissions.rules' nesne değil → izin kuralı ezme denetimi ÖLÇÜLEMEDİ")
        self.assertFalse(any("ezmiyor" in x for x in s), "\n".join(s))
        s = self.proje_kos(b'{"permissions": []}')
        self.var(s, "WARN", "'permissions' nesne değil → izin kuralı ezme denetimi ÖLÇÜLEMEDİ")


def kib(bayt: int) -> str:
    return f"{bayt / 1024:.1f}".replace(".", ",") + " KiB"


class BaglamBoyutuTest(GeciciTest):
    """D6: bağlam dosyalarının toplam baytı (yalnız rapor). Global config geçici dosya (gerçek ~/.config/axet-code'a
    dokunulmaz); cwd varsayılan olarak otomatik kök dosyası olmayan boş geçici dizin."""

    def setUp(self) -> None:
        super().setUp()
        self.env["LOCALAPPDATA"] = str(self.tmp / "_lad")
        self.cfg = self.xdg / "axet-code" / "axet-code.json"
        self.bos = self.tmp / "bos"
        self.bos.mkdir()

    def dosya(self, ad: str, bayt: int) -> Path:
        yol = self.tmp / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        with open(yol, "wb") as fh:
            fh.truncate(bayt)
        return yol

    def cfg_yaz(self, *girdiler, ham: str | None = None) -> None:
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.write_text(ham if ham is not None else json.dumps(
            {"options": {"context_paths": [str(g) if isinstance(g, Path) else g for g in girdiler]}}), encoding="utf-8")

    def kos(self, cwd: object = "bos") -> list[str]:
        doctor.results.clear()
        self.olcum = doctor.check_baglam_boyutu(self.bos if cwd == "bos" else cwd, self.cfg)
        self.tum = [f"[{s}] {m}" for s, m in doctor.results]
        satirlar = [s for s in self.tum if f"] {doctor.BAGLAM_ETIKETI}:" in s]
        self.assertEqual(len(satirlar), 1, self.tum)
        return satirlar

    def durum(self, satirlar: list[str]) -> str:
        return satirlar[0].split("]")[0][1:]

    def test_esik_sinirlari(self):
        self.assertEqual((doctor.BAGLAM_WARN, doctor.BAGLAM_FAIL), (204800, 1048576))
        for bayt, beklenen in ((0, "PASS"), (204799, "PASS"), (204800, "WARN"), (1048575, "WARN"), (1048576, "FAIL")):
            with self.subTest(bayt=bayt):
                f = self.dosya("g.md", bayt)
                self.cfg_yaz(f)
                s = self.kos()
                self.assertEqual(self.durum(s), beklenen, s)
                self.assertIn(f"{kib(bayt)} toplam, 1 dosya", s[0])
                self.assertIn(f"en büyük: {f} {kib(bayt)} (global-config)", s[0])
                self.assertNotIn("ÖLÇÜLEMEDİ", s[0])
        # eşik dosya başına değil TOPLAM üzerinde
        for ikinci, beklenen in ((102399, "PASS"), (102400, "WARN")):
            with self.subTest(ikinci=ikinci):
                self.cfg_yaz(self.dosya("a.md", 102400), self.dosya("b.md", ikinci))
                self.assertEqual(self.durum(self.kos()), beklenen)
        for ikinci, beklenen in ((524287, "WARN"), (524288, "FAIL")):
            with self.subTest(ikinci=ikinci):
                self.cfg_yaz(self.dosya("a.md", 524288), self.dosya("b.md", ikinci))
                self.assertEqual(self.durum(self.kos()), beklenen)

    def test_en_buyuk_uc_dosya(self):
        d = [self.dosya(f"d{i}.md", b) for i, b in enumerate((1000, 5000, 3000, 2000))]
        self.cfg_yaz(*d)
        s = self.kos()
        en = s[0].split("en büyük: ")[1]
        self.assertNotIn(str(d[0]), en)
        self.assertLess(en.index(str(d[1])), en.index(str(d[2])))
        self.assertLess(en.index(str(d[2])), en.index(str(d[3])))
        self.assertIn(f"{kib(11000)} toplam, 4 dosya", s[0])

    def test_global_proje_otomatik_birlesir(self):
        proje = self.tmp / "proje"
        g = self.dosya("g.md", 150 * 1024)
        self.dosya("proje/.axet-code/memory/MEMORY.md", 60 * 1024)
        self.cfg_yaz(g)
        s = self.kos(proje)  # kontrol grubu: proje config'i yok → yalnız global
        self.assertEqual(self.durum(s), "PASS", s)
        self.yaz(proje / ".axet-code.json", json.dumps({"options": {"context_paths": [".axet-code/memory/MEMORY.md"]}}))
        s = self.kos(proje)
        self.assertEqual(self.durum(s), "WARN", s)
        self.assertIn(f"{kib(210 * 1024)} toplam, 2 dosya", s[0])
        self.assertIn(f"global-config {kib(150 * 1024)}/1 dosya · proje-config {kib(60 * 1024)}/1 dosya · otomatik "
                      f"{kib(0)}/0 dosya", s[0])
        self.cfg_yaz()  # kontrol grubu: global boş, yalnız proje
        self.assertEqual(self.durum(self.kos(proje)), "PASS")
        self.cfg_yaz(g)
        self.dosya("proje/AGENTS.md", 1024)
        self.dosya("proje/.github/copilot-instructions.md", 2048)
        self.dosya("proje/notloaded.md", 900 * 1024)  # otomatik listede yok → sayılmaz
        s = self.kos(proje)
        self.assertIn(f"otomatik {kib(3072)}/2 dosya", s[0])
        self.assertIn(f"{kib(213 * 1024)} toplam, 4 dosya", s[0])
        self.assertEqual(self.durum(s), "WARN")
        self.assertNotIn("notloaded", s[0])

    def test_eksik_dosya_pass_sayilmaz(self):
        yok = self.tmp / "yok.md"
        self.cfg_yaz(self.dosya("k.md", 10 * 1024))
        self.assertEqual(self.durum(self.kos()), "PASS")  # kontrol grubu
        for okunan, beklenen in ((10 * 1024, "WARN"), (300 * 1024, "WARN"), (1048576, "FAIL")):
            with self.subTest(okunan=okunan):
                self.cfg_yaz(self.dosya("k.md", okunan), yok)
                s = self.kos()
                self.assertEqual(self.durum(s), beklenen, s)
                self.assertIn("ÖLÇÜLEMEDİ (1)", s[0])
                self.assertIn(str(yok), s[0])
                self.assertIn(f"{kib(okunan)} toplam, 1 dosya", s[0])
                if beklenen == "WARN":
                    self.assertIn("toplam ÖLÇÜLEMEDİ", s[0])
        self.assertTrue(any(x.startswith("[INFO]") and "bu koşuda ÖLÇÜLEMEDİ" in x and str(yok) in x for x in self.tum))

    def test_okunamayan_dosya_ve_dizin(self):
        f = self.dosya("kilitli.md", 1024)
        self.cfg_yaz(f)
        self.assertEqual(self.durum(self.kos()), "PASS")  # kontrol grubu
        asil_open = Path.open

        def bozuk_open(p, *a, **k):
            if p == f:
                raise PermissionError(13, "Erişim engellendi", str(p))
            return asil_open(p, *a, **k)
        with mock.patch.object(Path, "open", bozuk_open):
            s = self.kos()
        self.assertEqual(self.durum(s), "WARN", s)
        self.assertIn("PermissionError", s[0])
        self.assertIn("toplam ÖLÇÜLEMEDİ", s[0])
        d = self.tmp / "ctxdir"
        self.dosya("ctxdir/a.md", 1024)
        self.cfg_yaz(d)
        self.assertEqual(self.durum(self.kos()), "PASS")  # kontrol grubu
        asil_scandir = os.scandir

        def bozuk_scandir(p=None):
            if p is not None and Path(p) == d:
                raise PermissionError(13, "Erişim engellendi", str(p))
            return asil_scandir(p) if p is not None else asil_scandir()
        with mock.patch.object(os, "scandir", bozuk_scandir):
            s = self.kos()
        self.assertEqual(self.durum(s), "WARN", s)
        self.assertIn("ÖLÇÜLEMEDİ", s[0])
        self.assertIn(f"{kib(0)} toplam, 0 dosya", s[0])

    def test_dizin_girdisi_ust_sinir(self):
        d = self.tmp / "ctxdir"
        a = self.dosya("ctxdir/a.md", 150 * 1024)
        self.cfg_yaz(d)
        s = self.kos()
        self.assertEqual(self.durum(s), "PASS", s)
        self.assertIn(f"{a} {kib(150 * 1024)}", s[0])
        self.assertNotIn("üst sınır", s[0])
        self.dosya("ctxdir/b.txt", 1024)  # üst sınır aynı bantta → önem değişmez, ama etiketle yazılır
        s = self.kos()
        self.assertEqual(self.durum(s), "PASS", s)
        self.assertIn("üst sınır (ölçülmemiş davranış): 1 dosya", s[0])
        self.assertIn(f"{kib(150 * 1024)} toplam, 1 dosya", s[0])
        c = self.dosya("ctxdir/alt/c.md", 60 * 1024)  # üst sınır WARN eşiğini aşar → PASS verilmez
        s = self.kos()
        self.assertEqual(self.durum(s), "WARN", s)
        self.assertIn("üst sınır (ölçülmemiş davranış): 2 dosya", s[0])
        self.assertIn(str(c), s[0])
        self.assertIn("toplam ÖLÇÜLEMEDİ", s[0])
        self.assertIn(f"{kib(150 * 1024)} toplam, 1 dosya", s[0])
        self.cfg_yaz(a, a)  # yinelenen girdi: bir kez sayılır, ikincisi üst sınır
        s = self.kos()
        self.assertIn(f"{kib(150 * 1024)} toplam, 1 dosya", s[0])
        self.assertIn("birden fazla kez listelenmiş", s[0])

    def test_dizin_dosya_siniri_olculemedi(self):
        """bug gate LOW-3: çok dosyalı dizin girdisi sınırda kesilir → ÖLÇÜLEMEDİ (toplam PASS sayılmaz)."""
        d = self.tmp / "buyukdizin"
        for i in range(4):
            self.dosya(f"buyukdizin/alt/f{i}.txt", 10)
        self.cfg_yaz(d)
        s = self.kos()  # kontrol grubu: sınır altında
        self.assertEqual(self.durum(s), "PASS", s)
        self.assertNotIn("dosya sayısı sınırı", s[0])
        with mock.patch.object(doctor, "BAGLAM_DOSYA_SINIRI", 3):
            s = self.kos()
        self.assertEqual(self.durum(s), "WARN", s)
        self.assertIn("ÖLÇÜLEMEDİ", s[0])
        self.assertIn("dosya sayısı sınırı aşıldı", s[0])
        self.assertIn("toplam ÖLÇÜLEMEDİ", s[0])

    def test_belirsiz_dosya_acilmaz_ve_kapsam_symlink(self):
        """bug gate LOW-3: yalnız üst sınıra giren dosya açılmaz (stat yeter); yüklendiği ölçülen dosya açılmaya devam eder."""
        d = self.tmp / "ctxdir"
        a = self.dosya("ctxdir/a.md", 1024)
        b = self.dosya("ctxdir/alt/b.md", 2048)
        self.cfg_yaz(d)
        acilan: list[Path] = []
        asil_open = Path.open

        def say(p, *x, **k):
            acilan.append(Path(p))
            return asil_open(p, *x, **k)
        with mock.patch.object(Path, "open", say):
            s = self.kos()
        self.assertIn(a, acilan, "kontrol grubu: yüklendiği ölçülen dosya açılabilirlik için açılır")
        self.assertNotIn(b, acilan)
        self.assertIn("üst sınır (ölçülmemiş davranış): 1 dosya", s[0])
        self.assertTrue(any(x.startswith("[INFO]") and "symlink'li alt klasörler izlenmez" in x for x in self.tum), self.tum)

    def test_olculmemis_girdi_bicimleri(self):
        self.dosya("bos/goreli.md", 10)
        for girdi in ("C:/*.md" if os.name == "nt" else "/*.md", "~/notlar.md", "$HOME/x.md", "%USERPROFILE%/x.md",
                      "goreli.md", 5, ""):
            with self.subTest(girdi=girdi):
                self.cfg_yaz(girdi)
                s = self.kos()
                self.assertEqual(self.durum(s), "WARN", s)
                self.assertIn("ÖLÇÜLEMEDİ (1)", s[0])
        # kontrol grubu: aynı göreli yol PROJE config'inde cwd'ye göre çözülür (ölçülen davranış)
        self.cfg_yaz()
        self.yaz(self.bos / ".axet-code.json", json.dumps({"options": {"context_paths": ["goreli.md"]}}))
        s = self.kos()
        self.assertEqual(self.durum(s), "PASS", s)
        self.assertIn(f"proje-config {kib(10)}/1 dosya", s[0])

    def test_config_yok_ve_bozuk(self):
        s = self.kos()
        self.assertEqual(self.durum(s), "PASS", s)
        self.assertIn(f"{kib(0)} toplam, 0 dosya", s[0])
        self.assertTrue(any(x.startswith("[INFO]") and "global config yok" in x for x in self.tum), self.tum)
        self.cfg_yaz(ham='{"options": {}}')
        self.assertEqual(self.durum(self.kos()), "PASS")  # kontrol grubu
        for ham, parca in (("{bozuk", "okunamadı"), ('{"options": {"context_paths": "x"}}', "liste değil"),
                           ('{"options": []}', "'options' nesne değil"), ("[]", "kök değeri nesne değil")):
            with self.subTest(ham=ham):
                self.cfg_yaz(ham=ham)
                s = self.kos()
                self.assertEqual(self.durum(s), "WARN", s)
                self.assertIn(parca, s[0])
        self.cfg_yaz(ham="{bozuk")
        self.assertEqual(self.durum(self.kos(None)), "WARN")  # proje dışı (cwd yok) da çökmez

    def _utf8_disi_env(self) -> None:
        # PYTHONIOENCODING/PYTHONUTF8 cp1254 kusurunu gizler; alt süreç Windows varsayılan kodlamasıyla koşsun.
        for k in ("PYTHONIOENCODING", "PYTHONUTF8"):
            self.env.pop(k, None)

    def test_template_kokunde_uctan_uca(self):
        self.global_config(sap=True)
        self._utf8_disi_env()
        home = doctor.inst.AXET_HOME
        r = self.calistir("doctor.py", cwd=home)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        beklenen = [doctor.inst.CORE_FILE, doctor.inst.TEAM_MEMORY]
        beklenen += sorted(p for p in doctor.inst.SAP_CORE_DIR.iterdir() if p.is_file() and p.name.endswith(".md"))
        beklenen += [home / a for a in doctor.BAGLAM_OTOMATIK if (home / a).is_file()]
        toplam = sum(p.stat().st_size for p in beklenen)
        satir = [x for x in r.stdout.splitlines() if f"] {doctor.BAGLAM_ETIKETI}:" in x]
        self.assertEqual(len(satir), 1, r.stdout)
        self.assertTrue(satir[0].startswith(f"[{doctor.baglam_onemi(toplam)}]"), satir)
        self.assertIn(f"{kib(toplam)} toplam, {len(beklenen)} dosya", satir[0])
        self.assertIn("00-temel.md", satir[0])
        self.assertTrue(any(x.startswith("[INFO] bağlam boyutu KAPSAM") and "token sayısı" in x and "TUI" in x
                            for x in r.stdout.splitlines()), r.stdout)
        self.assertIn("bağlam boyutu yalnız dosya baytıdır", r.stdout)

    def test_proje_uctan_uca_fail_ve_turkce_cikti(self):
        self.global_config()
        self._utf8_disi_env()
        d = self.tmp / "uc"
        self.dosya("uc/buyuk.md", 1048576)
        self.yaz(d / ".axet-code.json", json.dumps({"options": {"context_paths": ["buyuk.md", "yok.md"]}}))
        r = self.calistir("doctor.py", cwd=d)
        self.assertNotIn("Traceback", r.stderr, r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout)
        satir = [x for x in r.stdout.splitlines() if f"] {doctor.BAGLAM_ETIKETI}:" in x]
        self.assertEqual(len(satir), 1, r.stdout)
        self.assertTrue(satir[0].startswith("[FAIL]"), satir)
        self.assertIn("ÖLÇÜLEMEDİ (1)", satir[0])
        self.assertIn(str(d / "yok.md"), satir[0])
        self.assertIn("proje-config " + kib(1048576) + "/1 dosya", satir[0])


class TemplateSapmaSinifTest(GeciciTest):
    """doctor `check_template` sapma yönlendirmesi (Z5 + P4 bilgi satırı).

    Birim seviyesinde ölçülür: `check_template()` GERÇEK klonun git durumuna bakar (`bm.template_sinifla()`
    argümansız), o da koşulan ağaca göre değişir → CLI üzerinden deterministik ölçülemez. Bu yüzden
    yönlendirme saf bir fonksiyona (`doctor.template_bulgulari`) ayrıldı ve sentetik girdiyle ölçülüyor.
    """

    @staticmethod
    def olc(**kw) -> dict:
        o = {"durum": "es", "kullanici": [], "guncelle_anlik": [], "guncelle_uygulama": [], "notlar": []}
        o.update(kw)
        return o

    @staticmethod
    def durumlar(bulgular, parca: str) -> list[str]:
        """Bulgu satirlarinin durumlari. KAPSAM satiri sabit bir katalog (yuzey dosyalarini sayar) -> bulgu degil."""
        return [d for d, m in bulgular if parca in m and "KAPSAM" not in m]

    def test_guncelle_uygulama_sapmasi_warn_degil_info(self):
        """Dal SESSİZCE DÜŞEMEZ: satır üretilmeli, dosya SAYISI ve YOLLARI satırda olmalı."""
        b = doctor.template_bulgulari(self.olc(guncelle_uygulama=["core/00-temel.md", "skills/b/SKILL.md"]))
        satir = [m for d, m in b if d == "INFO" and "uyguladığı template güncellemesi" in m]
        self.assertEqual(len(satir), 1, b)
        self.assertIn("2 dosya", satir[0])
        self.assertIn("core/00-temel.md", satir[0])
        self.assertIn("skills/b/SKILL.md", satir[0])
        self.assertEqual(self.durumlar(b, "core/00-temel.md"), ["INFO"], b)
        self.assertEqual([d for d, _ in b if d == "WARN"], [], b)

    def test_guncelle_anlik_sapmasi_info_ama_icerik_kullanicinin_denir(self):
        """Dal SESSİZCE DÜŞEMEZ + gevşetmenin şartı: satır içeriğin KULLANICININ olduğunu söylemeli."""
        b = doctor.template_bulgulari(self.olc(guncelle_anlik=["skills/a/SKILL.md", "AGENTS.md"]))
        satir = [m for d, m in b if d == "INFO" and "anlık commit" in m]
        self.assertEqual(len(satir), 1, b)
        self.assertIn("2 dosya", satir[0])
        self.assertIn("skills/a/SKILL.md", satir[0])
        self.assertIn("AGENTS.md", satir[0])
        self.assertIn("İÇERİK KULLANICININ", satir[0])
        self.assertIn("git -C <template> log -p --author=", satir[0], "inceleme komutu düştü")
        self.assertEqual(self.durumlar(b, "skills/a/SKILL.md"), ["INFO"], b)
        self.assertEqual([d for d, _ in b if d == "WARN"], [], b)

    def test_sinif_bossa_INFO_satiri_HIC_basilmaz(self):
        """Yanlış-pozitif yönü: sapma YOKken `%guncelle` satırı basılırsa kullanıcı olmayan bir işi arar."""
        b = doctor.template_bulgulari(self.olc())
        self.assertEqual([m for d, m in b if "anlık commit" in m or "uyguladığı template güncellemesi" in m], [], b)

    def test_kullanici_sapmasi_varken_PASS_basilmaz(self):
        """Güven veren YANLIŞ satır tuzağı: sapma varken 'sapma yok' diyen bir satır ASLA çıkmamalı."""
        b = doctor.template_bulgulari(self.olc(durum="sapma", kullanici=["commit edilmemiş değişiklik [M]: AGENTS.md"],
                                               guncelle_uygulama=["core/00-temel.md"]))
        self.assertEqual([m for d, m in b if d == "PASS"], [], b)
        self.assertEqual([m for d, m in b if "sapma yok" in m], [], b)

    def test_temizken_PASS_basilir(self):
        """Yukarıdakinin kontrol grubu: gerçekten temizken PASS ÇIKAR (aksi hâlde üstteki test boş yere yeşil)."""
        b = doctor.template_bulgulari(self.olc())
        self.assertEqual(len([m for d, m in b if d == "PASS" and "sapma yok" in m]), 1, b)

    def test_kontrol_grubu_kullanici_sapmasi_warn_kalir(self):
        """Gevşetme yalnız %guncelle sınıfına: kullanıcı sapması hâlâ WARN."""
        b = doctor.template_bulgulari(self.olc(durum="sapma", kullanici=["commit edilmemiş değişiklik [M]: core/00-temel.md"]))
        self.assertEqual(self.durumlar(b, "core/00-temel.md"), ["WARN"], b)

    def test_karisik_hem_warn_hem_info(self):
        b = doctor.template_bulgulari(self.olc(durum="sapma", kullanici=["commit edilmemiş değişiklik [M]: AGENTS.md"],
                                               guncelle_uygulama=["core/00-temel.md"]))
        self.assertEqual(self.durumlar(b, "AGENTS.md"), ["WARN"], b)
        self.assertEqual(self.durumlar(b, "core/00-temel.md"), ["INFO"], b)

    def test_olculemedi_info_ve_pass_basmaz(self):
        b = doctor.template_bulgulari(self.olc(durum="olculemedi", notlar=["x git reposu değil — ÖLÇÜLEMEDİ"]))
        self.assertEqual(self.durumlar(b, "ÖLÇÜLEMEDİ"), ["INFO"], b)
        self.assertEqual([d for d, _ in b if d == "PASS"], [], b)

    def test_olculemedi_notu_PASS_satirinda_KAYBOLMAZ(self):
        """Failure-mode: `@{u}` tanımsız (ya da `git diff`i hata veren) bir klonda commit dalı HİÇ
        ölçülmez ama durum yine `es` gelir. Not PASS satırından düşerse çıktı gerçekten temiz bir
        koşumla BİREBİR aynı görünür ⇒ 'ölçülemedi' sessizce 'temiz' diye okunur (core §7)."""
        n = "upstream tanımlı değil — ÖLÇÜLEMEDİ"
        pas = [m for d, m in doctor.template_bulgulari(self.olc(notlar=[n])) if d == "PASS" and "sapma yok" in m]
        self.assertEqual(len(pas), 1, pas)
        self.assertIn(n, pas[0], "PASS satırı ölçülemedi notunu yutuyor: temiz koşumdan ayırt edilemez")

    def test_kontrol_grubu_not_yokken_PASS_satiri_sade_kalir(self):
        """Üstteki testin kontrol grubu: not YOKken PASS satırına boş parantez/gürültü eklenmemeli
        (aksi hâlde üstteki test davranış yanlışken de yeşil kalabilirdi)."""
        pas = [m for d, m in doctor.template_bulgulari(self.olc()) if d == "PASS" and "sapma yok" in m]
        self.assertEqual(len(pas), 1, pas)
        self.assertNotIn("ÖLÇÜLEMEDİ", pas[0], pas)
        self.assertNotIn("()", pas[0], pas)

    def test_sapma_dalinda_olculemedi_notu_AYRI_INFO_satiri_olur(self):
        """WARN satırı yalnız dosyaları listeler; not oraya sığmaz. Ayrı INFO satırı düşerse sapma
        çıktısında 'commit dalı hiç ölçülmedi' bilgisi tümden kaybolur."""
        n = "upstream tanımlı değil — ÖLÇÜLEMEDİ"
        b = doctor.template_bulgulari(self.olc(durum="sapma", kullanici=["AGENTS.md"], notlar=[n]))
        satir = [m for d, m in b if d == "INFO" and "yüzeyi notları" in m]
        self.assertEqual(len(satir), 1, b)
        self.assertIn(n, satir[0])
        # kontrol grubu (yanlış-pozitif yönü): not yokken bu satır HİÇ basılmaz
        b2 = doctor.template_bulgulari(self.olc(durum="sapma", kullanici=["AGENTS.md"]))
        self.assertEqual([m for d, m in b2 if "yüzeyi notları" in m], [], b2)

    def test_kapsam_beyani_iki_kritik_uyariyi_icerir(self):
        """KAPSAM satırının ADI değil GÖVDESİ ölçülür: iki kritik uyarı silinse de 'bakılmayan'
        kelimesi satırda kalır ve beyan testi yeşil kalırdı (bug-gate 2026-09-18 · M15).
        Aranan dizgeler dar ve ayırt edici — metin yeniden yazılabilir, ANLAM korunmalı."""
        for o in (self.olc(), self.olc(durum="sapma", kullanici=["x"]), self.olc(durum="olculemedi", notlar=["n"])):
            kapsam = [m for d, m in doctor.template_bulgulari(o) if d == "INFO" and "KAPSAM" in m]
            self.assertEqual(len(kapsam), 1, o)
            self.assertIn(doctor.bm.GUNCELLE_EPOSTA, kapsam[0], kapsam)
            self.assertIn("TAKLİT EDİLEBİLİR", kapsam[0],
                          "kimliğin GÜVENLİK SINIRI OLMADIĞI uyarısı düştü → okuyucu onu sınır sanır")
            self.assertIn("upstream", kapsam[0], "'upstream tanımsızsa ÖLÇÜLMEZ' uyarısı düştü")
            self.assertIn("ÖLÇÜLMEZ", kapsam[0], "'upstream tanımsızsa ÖLÇÜLMEZ' uyarısı düştü")

    def test_kapsam_beyani_her_kosumda_basilir(self):
        """En kritik an sıfır-bulgu anı: temiz koşuda da neye BAKILMADIĞI yazılır (core §7)."""
        for o in (self.olc(), self.olc(durum="sapma", kullanici=["x"]), self.olc(guncelle_uygulama=["y"])):
            b = doctor.template_bulgulari(o)
            kapsam = [m for d, m in b if d == "INFO" and "KAPSAM" in m]
            self.assertEqual(len(kapsam), 1, b)
            self.assertIn("bakılmayan", kapsam[0])

    def test_hicbir_sinif_FAIL_uretmez(self):
        """Gate moratoryumu: bu blok çıkış kodunu değiştiren bir kapı AÇMAZ."""
        for o in (self.olc(), self.olc(durum="sapma", kullanici=["x"]), self.olc(durum="olculemedi", notlar=["n"]),
                  self.olc(guncelle_anlik=["a"], guncelle_uygulama=["b"])):
            self.assertEqual([d for d, _ in doctor.template_bulgulari(o) if d == "FAIL"], [], o)


class CekirdekMetniTest(GeciciTest):
    """`core/00-temel.md` §11 — `%guncelle` dar istisnası (P4/A4)."""

    def setUp(self) -> None:
        super().setUp()
        self.metin = (doctor.inst.CORE_FILE).read_text(encoding="utf-8")

    def test_cekirdek_satir_siniri(self):
        """doctor'ın kendi eşiği (doctor.py:758) — istisna metni çekirdeği eşiğin üstüne çıkarmamalı."""
        self.assertLessEqual(len(self.metin.splitlines()), 150)

    def test_guncelle_istisnasi_dar_yazilmis(self):
        i = self.metin.find("## 11. Güvenlik")
        j = self.metin.find("\n## ", i + 1)
        bolum = self.metin[i:j if j > 0 else len(self.metin)]
        self.assertIn("Dış kaynaktan gelen içerik", bolum)
        self.assertIn("İstisna", bolum)
        for parca in ("%guncelle", "%guncelle-proje", "origin", "GUNCELLE.md", "guncelle/**",
                      "scripts/guncelle.py", "gevşetemez", "DUR"):
            self.assertIn(parca, bolum, f"§11 istisnasında eksik: {parca}")
        self.assertIn("Başka hiçbir dış içerik", bolum)


class GitKimlikTest(GeciciTest):
    """Z84: git kimliği (user.name/user.email) tanımsızsa: bulunulan repoda remote varsa WARN, yoksa INFO. Ölçülen vaka:
    Windows'ta `user.email` yokken git adresi şirket hesabından türetti, commit HATA VERMEDEN o adresle atıldı; push
    edilirse adres geçmişe girer. İzolasyon: global config geçici dosya, sistem config'i yok, HOME/USERPROFILE geçici,
    cwd başlangıçta git reposu DEĞİL (repo gereken testler onu kendisi `git init` eder)."""

    ADRES = "ad.soyad@sirket.com"

    def setUp(self) -> None:
        super().setUp()
        self.env["LOCALAPPDATA"] = str(self.tmp / "_lad")
        home = self.tmp / "_home"
        home.mkdir()
        self.gitconfig = self.tmp / "_kimlik_gitconfig"
        self.gitconfig.write_text("", encoding="utf-8")
        self.env.update({"GIT_CONFIG_GLOBAL": str(self.gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
                         "HOME": str(home), "USERPROFILE": str(home)})
        self.cwd = self.tmp / "repo_disi"
        self.cwd.mkdir()
        # Ön koşul: cwd bir git reposunun içinde DEĞİL (içindeyse üst reponun yerel config'i sonucu sızdırır).
        r = self.git(self.cwd, "rev-parse", "--is-inside-work-tree", kontrol=False)
        self.assertNotEqual(r.returncode, 0, f"geçici dizin bir git reposunun içinde: {self.cwd}")

    def kimlik(self, ad: str | None, eposta: str | None) -> None:
        satirlar = ["[user]"]
        if ad is not None:
            satirlar.append(f"\tname = {ad}")
        if eposta is not None:
            satirlar.append(f"\temail = {eposta}")
        self.gitconfig.write_text("\n".join(satirlar) + "\n", encoding="utf-8")

    def kimlik_satirlari(self, r) -> list[str]:
        return [s for s in r.stdout.splitlines() if s.startswith("[") and "git kimliği" in s]

    def repo(self, remote: bool) -> None:
        """cwd'yi git reposu yapar; `remote` → push riski gerçek (WARN seviyesi)."""
        self.git(self.cwd, "init", "-q")
        if remote:
            self.git(self.cwd, "remote", "add", "origin", "https://example.invalid/x.git")

    def test_kimliksiz_remote_suz_repo_info(self):
        self.repo(remote=False)
        r = self.calistir("doctor.py", cwd=self.cwd)
        satir = self.kimlik_satirlari(r)
        self.assertEqual(len(satir), 1, r.stdout)
        self.assertTrue(satir[0].startswith("[INFO] git kimliği tanımsız"), satir[0])
        for parca in ("user.email", "user.name", "Windows", "push edilmeyecekse zararsız",
                      "git config --global user.email", "yargılanmaz", "remote yalnız bulunulan repoda ölçülür"):
            self.assertIn(parca, satir[0])

    def test_kimliksiz_repo_disi_info(self):
        satir = self.kimlik_satirlari(self.calistir("doctor.py", cwd=self.cwd))
        self.assertEqual(len(satir), 1, satir)
        self.assertTrue(satir[0].startswith("[INFO] git kimliği tanımsız"), satir[0])

    def test_kimliksiz_remote_lu_repo_warn(self):
        # FAIL'siz taban: global config yoksa ya da .conn_adt gitignore'da değilse doctor rc'si zaten 1 olur ve
        # aşağıdaki rc karşılaştırması kör kalır (ölçüldü).
        self.global_config()
        self.repo(remote=True)
        self.yaz(self.cwd / ".gitignore", ".conn_adt\n")
        r = self.calistir("doctor.py", cwd=self.cwd)
        satir = self.kimlik_satirlari(r)
        self.assertEqual(len(satir), 1, r.stdout)
        self.assertTrue(satir[0].startswith("[WARN] git kimliği tanımsız"), satir[0])
        for parca in ("user.email", "user.name", "Windows", "push edilirse", "git config --global user.email",
                      "yargılanmaz", "remote yalnız bulunulan repoda ölçülür"):
            self.assertIn(parca, satir[0])
        self.assertNotIn("example.invalid", r.stdout.split("git kimliği", 1)[1].splitlines()[0])
        self.assertNotIn("bu makinedeki", satir[0], "proje dizininde genel (template) metni basılmamalı")
        # WARN dalı çıkış kodunu değiştirmemeli: aynı remote'lu repoda kimlikli koşunun rc'siyle karşılaştır.
        self.kimlik("Ad Soyad", self.ADRES)
        kimlikli = self.calistir("doctor.py", cwd=self.cwd)
        self.assertTrue(self.kimlik_satirlari(kimlikli)[0].startswith("[PASS]"), kimlikli.stdout)
        self.assertEqual(kimlikli.returncode, 0, "kontrol grubu: FAIL'siz koşu olmalı (yoksa rc karşılaştırması kör)\n"
                         + kimlikli.stdout)
        self.assertEqual(r.returncode, kimlikli.returncode, "WARN çıkış kodunu değiştirmemeli")

    def test_template_klonunda_genel_metin(self):
        """Kurulumda doctor template klonunda koşar (kur.ps1: Push-Location $Hedef); klonun origin'i vardır.
        Metin "proje" değil bu makinedeki projeler için konuşmalı; seviye WARN kalır. Gerçek AXET_HOME'un yerel
        config'inde kimlik olabileceği için klon eşdeğeri izole bir remote'lu repo + yamalı AXET_HOME kullanılır."""
        self.repo(remote=True)
        (self.cwd / "alt").mkdir()
        doctor.results.clear()
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(doctor.inst, "AXET_HOME", self.cwd):
            doctor.check_git_kimlik(self.cwd)
            doctor.check_git_kimlik(self.cwd / "alt")  # klonun alt dizini de template sayılır
        sonuc = list(doctor.results)
        doctor.results.clear()
        self.assertEqual(len(sonuc), 2, sonuc)
        for durum, mesaj in sonuc:
            self.assertEqual(durum, "WARN", mesaj)
            self.assertIn("git kimliği tanımsız", mesaj)
            self.assertIn("bu makinedeki bir proje uzak sunucuya push edilirse", mesaj)
            self.assertNotIn("; proje uzak sunucuya push edilirse", mesaj)

    def test_remote_olculemezse_warn(self):
        """`git remote` rc 0/128 dışı → güvenli taraf WARN (sessiz INFO değil)."""
        def sahte(argv, **kw):
            if argv[1:3] == ["config", "--get"]:
                return subprocess.CompletedProcess(argv, 1, "", "")
            return subprocess.CompletedProcess(argv, 2, "", "bozuk\n")
        doctor.results.clear()
        with mock.patch.object(doctor.subprocess, "run", side_effect=sahte):
            doctor.check_git_kimlik(self.cwd)
        self.assertEqual(len(doctor.results), 1, doctor.results)
        durum, mesaj = doctor.results[0]
        doctor.results.clear()
        self.assertEqual(durum, "WARN")
        self.assertIn("git kimliği tanımsız", mesaj)
        self.assertIn("remote'u ÖLÇÜLEMEDİ (rc=2: bozuk)", mesaj)

    def test_yalniz_eposta_eksik_warn(self):
        self.repo(remote=True)
        self.kimlik("Ad Soyad", None)
        satir = self.kimlik_satirlari(self.calistir("doctor.py", cwd=self.cwd))
        self.assertEqual(len(satir), 1, satir)
        self.assertTrue(satir[0].startswith("[WARN] git kimliği tanımsız (user.email)"), satir[0])

    def test_yalniz_ad_eksik_warn(self):
        self.repo(remote=True)
        self.kimlik(None, self.ADRES)
        satir = self.kimlik_satirlari(self.calistir("doctor.py", cwd=self.cwd))
        self.assertEqual(len(satir), 1, satir)
        self.assertTrue(satir[0].startswith("[WARN] git kimliği tanımsız (user.name)"), satir[0])

    def test_kimlikli_pass_adres_basilmaz(self):
        kontrol = self.calistir("doctor.py", cwd=self.cwd)
        self.kimlik("Ad Soyad", self.ADRES)
        r = self.calistir("doctor.py", cwd=self.cwd)
        satir = self.kimlik_satirlari(r)
        self.assertEqual(len(satir), 1, r.stdout)
        self.assertTrue(satir[0].startswith("[PASS] git kimliği tanımlı"), satir[0])
        self.assertNotIn(self.ADRES, r.stdout, "adres (kişisel veri) basılmamalı")
        self.assertEqual(r.returncode, kontrol.returncode, "kimlik satırı (INFO↔PASS) çıkış kodunu değiştirmemeli")

    def test_git_yoksa_bilgi_satiri(self):
        doctor.results.clear()
        with mock.patch.object(doctor.shutil, "which", return_value=None):
            doctor.check_git_kimlik()
        self.assertEqual(len(doctor.results), 1, doctor.results)
        durum, mesaj = doctor.results[0]
        self.assertEqual(durum, "INFO")
        self.assertIn("git bulunamadı", mesaj)
        self.assertIn("git kimliği", mesaj)
        doctor.results.clear()
