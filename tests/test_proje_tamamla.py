# -*- coding: utf-8 -*-
"""Z70 — proje kurulumunun kullanıcı adımları tek çift tıklamada.

`scripts/conn_sablon.py`: SAP bağlantı ŞABLONLARI conn/DEV.env + conn/QA.env (yaz · doğrula · özet). Kural kopyalanmaz:
anahtarlar ve alan kuralları setup_credentials.py'den; ek olarak parola dahil `<...>` yer tutucu denetimi.
`proje-tamamla.cmd` (projede KURULUMU-TAMAMLA.cmd): şablon → (boşsa: yalnız BİLGİ — hangi dosya TAM yoluyla, hangi
alanlar, tekrar çift tık; editör AÇILMAZ, soru SORULMAZ — kullanıcı kararı 2026-09-24) → doğrula → DEV'i etkinleştir →
davranış yüzeyi onayı → doctor → aXet'i aç. Etkileşim `choice`'a boru ile verilir (ölçüldü: choice boru girdisini okur) — ANCAK
davranış yüzeyi onayı boruyla VERİLEMEZ (v0.5.6 gate: `echo E | …` ile ajan kendi değişikliğini onaylayabiliyordu);
testlerde onay, kullanıcının penceredeki `E`sinin eşdeğeri olarak `behavior_manifest.py generate` ile verilir;
`E` cevabı son soruda VERİLMEZ (axet-code açılmasın). Sahte değerler
kullanılır, SAP'ye bağlanılmaz. cmd testleri yalnız Windows (cmd.exe).
KAPSAM — bakılmayanlar: çift tıklanan pencerenin davranışı · `axet-code -c`'nin açılışı · aXet içinden geçiş (canlı ölçüm, rapor).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest

from _helpers import AXET_HOME, SCRIPTS, GeciciTest
import conn_sablon
import yeni_proje

CMD = AXET_HOME / "proje-tamamla.cmd"
SAP_SCRIPTS = AXET_HOME / "skills-sap" / "sap-adt-foundation" / "scripts"
MANIFEST = os.path.join(".axet-code", "behavior-manifest.json")
SAHTE = {"<https://sunucu:port>": "https://sahte-host.invalid:44300", "<kullanici>": "SAHTEKUL",
         "<parola>": "sahte-parola-123", "<3 haneli client, ör. 100>": "100"}
SAHTE_IZLER = ("sahte-host", "SAHTEKUL", "sahte-parola")


def _setup_credentials():
    spec = importlib.util.spec_from_file_location("_z70_sc", SAP_SCRIPTS / "setup_credentials.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def anahtar_deger(metin: str) -> dict[str, str]:
    return dict(s.split("=", 1) for s in metin.splitlines() if s.strip() and not s.lstrip().startswith("#"))


def doldur(f, **degistir) -> None:
    """Şablondaki yer tutucuları sahte değerlerle doldurur; `degistir` ile tek tek ezilir (anahtar=değer)."""
    metin = f.read_text(encoding="utf-8")
    for eski, yeni in SAHTE.items():
        metin = metin.replace(eski, yeni)
    satirlar = [f"{s.split('=', 1)[0]}={degistir[s.split('=', 1)[0]]}" if s.split("=", 1)[0] in degistir else s
                for s in metin.splitlines()]
    f.write_text("\n".join(satirlar) + "\n", encoding="utf-8")


class ZProje(GeciciTest):
    def sap_iskelet(self, ad: str = "zproje"):
        d = self.proje(ad, sap=True)
        veri = json.loads((d / "sap-project.json").read_text(encoding="utf-8"))
        veri["project"] = ad
        (d / "sap-project.json").write_text(json.dumps(veri), encoding="utf-8")
        return d

    def cs(self, *args, d):
        return self.calistir("conn_sablon.py", *args, "--project-dir", str(d))

    def switch(self, d, *args):
        return subprocess.run([sys.executable, str(SAP_SCRIPTS / "switch_tier.py"), *args, "--project-dir", str(d)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=self.env,
                              stdin=subprocess.DEVNULL, timeout=120)


class ConnSablonTest(ZProje):
    def test_z70_sablon_anahtarlari_setup_credentials_ile_birebir(self):
        d = self.sap_iskelet("TRK")
        self.assertEqual(self.cs("hazirla", d=d).returncode, 0)
        beklenen = list(_setup_credentials().ANAHTARLAR)
        for tier in ("DEV", "QA"):
            with self.subTest(tier=tier):
                ham = (d / "conn" / f"{tier}.env").read_bytes()
                self.assertEqual(ham.count(b"\n"), ham.count(b"\r\n"), "Notepad için CRLF")
                kv = anahtar_deger(ham.decode("utf-8"))
                self.assertEqual(list(kv), beklenen, "anahtar kümesi/sırası setup_credentials'tan sapmış")
                self.assertEqual((kv["ADT_SAP_TIER"], kv["ADT_SAP_SYSTEM_NAME"], kv["ADT_SAP_LANGUAGE"]),
                                 (tier, f"TRK_{tier}", "TR"), "tier / <proje>_<tier> / master_language")

    def test_z70_hazirla_var_olani_ezmez(self):
        d = self.sap_iskelet()
        (d / "conn").mkdir(exist_ok=True)
        (d / "conn" / "DEV.env").write_text("kullanicinin dosyasi\n", encoding="utf-8")
        r = self.cs("hazirla", d=d)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("[var, dokunulmadı] conn\\DEV.env", r.stdout)
        self.assertIn("[şablon yazıldı] conn\\QA.env", r.stdout)
        self.assertEqual((d / "conn" / "DEV.env").read_text(encoding="utf-8"), "kullanicinin dosyasi\n")

    def test_z70_dogrula_bos_hatali_gecerli_ve_deger_basmaz(self):
        d = self.sap_iskelet()
        self.cs("hazirla", d=d)
        r = self.cs("dogrula", d=d)
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("conn\\DEV.env: boş şablon, atlandı", r.stdout)
        # hatalı: client 12 + parola doldurulmamış (provadaki vaka)
        doldur(d / "conn" / "DEV.env", ADT_SAP_CLIENT="12", ADT_SAP_PASSWORD="<parola>")
        r = self.cs("dogrula", d=d)
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("ADT_SAP_CLIENT: 3 haneli sayı olmalı", r.stdout)
        self.assertIn("ADT_SAP_PASSWORD: doldurulmamış", r.stdout)
        self.assertNotIn("ADT_SAP_URL", r.stdout, "geçerli alan hata sayıldı")
        for iz in SAHTE_IZLER:
            self.assertNotIn(iz, self.cikti(r), "değer basıldı")
        doldur(d / "conn" / "DEV.env", ADT_SAP_CLIENT="100", ADT_SAP_PASSWORD="sahte-parola-123")
        r = self.cs("dogrula", d=d)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("conn\\DEV.env: dolu, geçerli", r.stdout)
        self.assertIn("conn\\QA.env: boş şablon, atlandı", r.stdout)

    def test_z70_parola_yer_tutucusunu_switch_tier_gecirir_conn_sablon_yakalar(self):
        # Neden ayrı denetim: switch_tier parolada yer tutucu aramaz (parola '<' içerebilir) → doldurulmamış parolalı
        # slota GEÇER. conn_sablon aynı dosyayı HATALI sayar.
        d = self.sap_iskelet()
        self.cs("hazirla", d=d)
        doldur(d / "conn" / "QA.env", ADT_SAP_PASSWORD="<parola>")
        self.assertEqual(self.cs("dogrula", d=d).returncode, 1)
        r = self.switch(d, "QA")
        self.assertEqual(r.returncode, 0, "kontrol: switch_tier parola yer tutucusunu görmüyor olmalı\n" + r.stdout)

    def test_z70_doldurulmamis_sablona_switch_tier_gecmez(self):
        d = self.sap_iskelet()
        self.cs("hazirla", d=d)
        r = self.switch(d, "QA")
        self.assertEqual((r.returncode, json.loads(r.stdout)["error"]["code"]), (1, "placeholder_values"), r.stdout)
        self.assertFalse((d / ".conn_adt").exists())
        doldur(d / "conn" / "QA.env")  # kontrol grubu: doldurulunca geçer
        r = self.switch(d, "QA")
        self.assertEqual((r.returncode, json.loads(r.stdout)["tier"]), (0, "QA"), r.stdout)

    def test_z70_ozet_json_ad_tier_durum_deger_yok(self):
        d = self.sap_iskelet("OZ")
        self.cs("hazirla", d=d)
        doldur(d / "conn" / "DEV.env")
        self.switch(d, "DEV")
        r = self.cs("ozet", "--json", d=d)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        veri = json.loads(r.stdout)
        self.assertEqual(veri["aktif"], {"system": "OZ_DEV", "tier": "DEV"})
        self.assertEqual({s["system"]: s["durum"] for s in veri["systems"]}, {"OZ_DEV": "gecerli", "OZ_QA": "doldurulmamis"})
        for iz in SAHTE_IZLER:
            self.assertNotIn(iz, r.stdout)

    def test_z70_conn_readme_kurulumda_gelir_git_kurali_ve_ezilmez(self):
        d = self.proje("connproje", sap=True)
        readme = (d / "conn" / "README.md").read_text(encoding="utf-8")
        # Z83: README git'e açık ⇒ makine yolu TAŞIMAZ (önceden `<AXET_HOME>` klon yoluyla dolduruluyordu)
        self.assertNotIn(AXET_HOME.as_posix(), readme, "README klonun mutlak yolunu taşıyor")
        self.assertNotIn("<AXET_HOME>", readme)
        for rel, kapali in (("conn/README.md", False), ("conn/DEV.env", True), ("conn/QA.env", True)):
            with self.subTest(rel=rel):
                rc = self.git(d, "check-ignore", "-q", "--no-index", rel, kontrol=False).returncode
                self.assertEqual(rc == 0, kapali, rel)
        (d / "conn" / "README.md").write_text("kendi notum\n", encoding="utf-8")
        r = self.calistir("new_project.py", str(d), "--sap")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((d / "conn" / "README.md").read_text(encoding="utf-8"), "kendi notum\n", "README ezildi")

    def test_z70_denylist_conn_klasorunu_kapatir(self):
        # canlı ölçüm (aXet 1.3.0, sahte dosya): satır yokken ajan conn/QA.env'i OKUDU; `conn` ile reddedildi
        satirlar = (AXET_HOME / "templates" / "project" / ".axetcode-denylist").read_text(encoding="utf-8").splitlines()
        self.assertIn("conn", [s.strip() for s in satirlar])

    def test_z70_sistem_skilli_sap_kurulumunda_ve_dosya_okumaz(self):
        # skill envanteri: `sistem` skills-sap altında (yalnız SAP kurulumunda yüklenir); frontmatter aXet'te ayrışır;
        # akış ad+tier+durum veren `ozet --json` ile listeler, `switch_tier.py <AD>` ile geçer. Davranış (modelin
        # dosya okumadığı) burada ölçülmez — canlı ölçüm raporda.
        import doctor
        skill = AXET_HOME / "skills-sap" / "sistem" / "SKILL.md"
        metin = skill.read_text(encoding="utf-8")
        self.assertEqual(doctor.frontmatter_problems(metin), [])
        self.assertRegex(metin, r"(?m)^name: sistem\s*$")
        self.assertIn("conn_sablon.py ozet --json", metin)
        self.assertIn("switch_tier.py", metin)
        self.assertFalse((AXET_HOME / "skills" / "sistem").exists(), "sistem skill'i genel skills/ altına girmemeli")


@unittest.skipUnless(os.name == "nt", "cmd.exe yalnız Windows'ta")
class ProjeTamamlaTest(ZProje):
    def kos(self, *args: str, girdi: str = "\n", cwd=None) -> subprocess.CompletedProcess:
        # `pause` boru girdisi bitince bekletmez (ölçüldü); çıktı cmd (OEM) + python (utf-8) karışık → ASCII aranır
        return subprocess.run(["cmd", "/c", *args], input=girdi.encode("ascii"), capture_output=True,
                              cwd=str(cwd or self.tmp), env=self.env, timeout=300)

    def onayla(self, d) -> None:
        r = self.calistir("behavior_manifest.py", "generate", "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))

    @staticmethod
    def metin(r: subprocess.CompletedProcess) -> str:
        return r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")

    def sap_projesi(self):
        """Gerçek zincir: yeni_proje.py ile kurulmuş proje (doctor 0 FAIL, KURULUMU-TAMAMLA.cmd yazılmış)."""
        self.global_config(sap=True)
        d = self.tmp / "tamamla"
        r = self.calistir("yeni_proje.py", str(d), "--no-input", "--sap-profile", "s4_private", "--release", "2023",
                          "--master-language", "TR", "--cleancore-policy", "balanced", "--purpose", "Deneme")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return d

    def tier(self, d) -> str:
        return anahtar_deger((d / ".conn_adt").read_text(encoding="utf-8"))["ADT_SAP_TIER"]

    def test_z70_dosya_crlf_ascii_editor_acmaz_soru_sormaz(self):
        """Kullanıcı kararı (2026-09-24): pencere editör AÇMAZ (ne Notepad ne `start`), SAP bilgisi SORMAZ — yalnız
        bilgi verir. Eski test Notepad satırının VARLIĞINI zorluyordu; sözleşme tersine döndü."""
        ham = CMD.read_bytes()
        self.assertTrue(all(b < 128 for b in ham), "cmd ASCII olmalı (konsol kod sayfası)")
        self.assertEqual(ham.count(b"\n"), ham.count(b"\r\n"), "cmd CRLF olmalı (goto/etiket)")
        self.assertNotIn(b"notepad", ham.lower(), "pencere editör AÇMAMALI (yalnız bilgi verir)")
        self.assertNotIn(b'start ""', ham, "pencere başka program başlatmamalı")
        self.assertNotIn(b"AXET_KURULUM_EDITOR_ACMA", ham, "test kaçış değişkeni artık gereksiz")
        self.assertNotIn(b"setup_credentials.py\" --project-dir", ham, "pencere SAP bilgisi SORMAMALI")
        self.assertNotIn(b"set /p", ham.lower(), "pencere SAP bilgisi SORMAMALI (set /p girdi okur)")

    def test_z70_bos_klasor_once_yeni_proje_der(self):
        d = self.tmp / "bos"
        d.mkdir()
        r = self.kos(str(CMD), str(d))
        self.assertEqual(r.returncode, 2, self.metin(r))
        self.assertIn("henuz aXet projesi yok", self.metin(r))
        self.assertIn("%yeni-proje", self.metin(r))
        self.assertEqual(list(d.iterdir()), [])

    def test_z70_arguman_yoksa_bulunulan_dizin(self):
        d = self.tmp / "bos2"
        d.mkdir()
        r = self.kos(str(CMD), cwd=d)
        self.assertEqual(r.returncode, 2, self.metin(r))
        self.assertIn(str(d), self.metin(r))

    def test_z70_ilk_kosu_sablon_yazar_ve_durur(self):
        d = self.sap_projesi()
        r = self.kos(str(CMD), str(d))
        m = self.metin(r)
        self.assertEqual(r.returncode, 3, m)
        self.assertIn("[şablon yazıldı] conn\\DEV.env", m)
        self.assertIn("YAPMAN GEREKEN", m)
        # yalnız BİLGİ: hangi dosya (TAM yol; DEV zorunlu, QA isteğe bağlı), hangi alanlar, tekrar çift tık
        blok = m[m.index("YAPMAN GEREKEN"):]
        self.assertIn(f'ZORUNLU      : "{d / "conn" / "DEV.env"}"', blok)
        self.assertIn(f'Istege bagli : "{d / "conn" / "QA.env"}"', blok)
        for alan in conn_sablon.DOLDURULACAK:
            self.assertIn(alan, blok)
        self.assertIn("tekrar cift tikla", blok)
        self.assertNotIn("[2/4]", m, "şablon doldurulmadan devam etti")
        self.assertFalse((d / ".conn_adt").exists())
        self.assertFalse((d / MANIFEST).exists())

    def test_z70_hatali_dev_alan_adiyla_durur_conn_adt_olsa_da(self):
        d = self.sap_projesi()
        self.kos(str(CMD), str(d))  # şablonlar
        doldur(d / "conn" / "DEV.env", ADT_SAP_CLIENT="12", ADT_SAP_PASSWORD="<parola>")
        for etiket, conn_adt in (("conn_adt yok", False), ("conn_adt var (kontrol)", True)):
            with self.subTest(etiket):
                if conn_adt:
                    (d / ".conn_adt").write_bytes(b"")
                r = self.kos(str(CMD), str(d))
                m = self.metin(r)
                self.assertEqual(r.returncode, 3, m)
                self.assertIn("ADT_SAP_CLIENT", m)
                self.assertIn("ADT_SAP_PASSWORD", m)
                self.assertNotIn("[2/4]", m)
                for iz in SAHTE_IZLER:
                    self.assertNotIn(iz, m, "değer basıldı")

    def test_z70_conn_adt_varsa_bos_sablonla_devam_eder(self):
        # bilinçli sapma (lider onaylı): setup_credentials ile kurulmuş .conn_adt'yi bloklama; hatalı dosya yoksa geç
        d = self.sap_projesi()
        (d / ".conn_adt").write_bytes(b"")  # içerik okunmaz; yalnız varlığı
        r = self.kos(str(CMD), str(d), girdi="H\n")
        m = self.metin(r)
        self.assertEqual(r.returncode, 4, m)
        self.assertIn("aktif baglanti (.conn_adt) zaten var", m)
        self.assertIn("Onaylanacak dosyalar", m)
        self.assertIn("Onay yalniz bu dosyaya CIFT TIKLAYINCA", m)   # boru girdisi: soru hiç sorulmaz
        self.assertFalse((d / MANIFEST).exists())
        self.assertEqual((d / ".conn_adt").read_bytes(), b"", "bağlantı dosyasına dokunuldu")

    def test_z70_gecerli_dev_etkinlesir_onay_doctor_tekrar_ve_sapma(self):
        d = self.sap_projesi()
        self.kos(str(CMD), str(d))
        doldur(d / "conn" / "DEV.env")
        r = self.kos(str(CMD), str(d), girdi="EH\n")
        m = self.metin(r)
        self.assertEqual(self.tier(d), "DEV", m)
        self.assertIn("Aktif sistem DEV olarak ayarlaniyor", m)
        self.assertIn("SAP sistemi: aktif TAMAMLA_DEV (DEV)", m)
        self.assertIn("TAMAMLA_QA (QA)  [doldurulmam", m)
        # boruyla verilen `E` onay DEĞİLDİR: manifest yazılmaz, soru sorulmaz (v0.5.6 gate)
        self.assertEqual(r.returncode, 4, m)
        self.assertIn("Onay yalniz bu dosyaya CIFT TIKLAYINCA", m)
        self.assertNotIn("onayliyor musun", m)
        self.assertFalse((d / MANIFEST).exists(), "boru girdisiyle davranış yüzeyi onaylandı")
        self.onayla(d)           # kullanıcının pencerede `E` demesinin eşdeğeri
        r = self.kos(str(CMD), str(d), girdi="H\n")
        m = self.metin(r)
        self.assertIn("Ayarlar zaten onayli", m)
        self.assertTrue((d / MANIFEST).is_file(), m)
        self.assertIn("[4/4] Kurulum tamam", m)
        self.assertIn(r.returncode, (0, 6), m)  # 6: axet-code PATH'te yok (son soru sorulmaz)
        # tekrar koşu: .conn_adt'ye dokunulmaz, onay sorulmaz
        (d / ".conn_adt").write_text((d / ".conn_adt").read_text(encoding="utf-8") + "# isaret\n", encoding="utf-8")
        r = self.kos(str(CMD), str(d), girdi="H\n")
        m = self.metin(r)
        self.assertIn("# isaret", (d / ".conn_adt").read_text(encoding="utf-8"), "aktif bağlantı ezildi")
        self.assertIn("Ayarlar zaten onayli", m)
        self.assertNotIn("onayliyor musun", m)
        # sapma: onaydan sonra yüzey değişti → değişiklik gösterilir, onay yeniden sorulur
        with open(d / "AGENTS.md", "a", encoding="utf-8") as fh:
            fh.write("- yeni kural\n")
        once = (d / MANIFEST).read_bytes()
        r = self.kos(str(CMD), str(d), girdi="H\n")
        m = self.metin(r)
        self.assertEqual(r.returncode, 4, m)
        self.assertIn("[SAPMA]", m)
        self.assertEqual((d / MANIFEST).read_bytes(), once, "onaysız manifest değişti")

    def test_z70_kisayol_projeyi_bulur_ve_cikis_kodunu_tasir(self):
        d = self.sap_projesi()
        self.assertTrue((d / yeni_proje.KISAYOL).is_file(), "yeni_proje.py kısayolu yazmadı")
        # kısayol başka bir dizinden çağrılır: proje yolu %~dp0'dan gelmeli, cwd'den değil
        r = self.kos(str(d / yeni_proje.KISAYOL), cwd=self.tmp)
        m = self.metin(r)
        self.assertEqual(r.returncode, 3, m)
        self.assertIn(f"aXet kurulum tamamlama - \"{d}\"\r\n", m)
        self.assertTrue((d / "conn" / "DEV.env").is_file())

    def test_z70_doctor_fail_ise_durur_aXet_sorulmaz(self):
        # kontrol grubu: yer tutuculu AGENTS.md (yeni_proje.py koşmamış iskelet) → doctor FAIL
        self.global_config(sap=True)
        d = self.proje("iskelet", sap=True)
        (d / ".conn_adt").write_bytes(b"")
        self.onayla(d)
        r = self.kos(str(CMD), str(d), girdi="EE\n")
        m = self.metin(r)
        self.assertEqual(r.returncode, 5, m)
        self.assertIn("Kontrolde FAIL var", m)
        self.assertNotIn("[4/4]", m)

    def test_z70_kisayol_klon_yoksa_hata_ve_cikis_1(self):
        d = self.tmp / "kyok"
        d.mkdir()
        (d / yeni_proje.KISAYOL).write_bytes(yeni_proje.kisayol_metni(self.tmp / "olmayan-klon").encode("ascii"))
        r = self.kos(str(d / yeni_proje.KISAYOL))
        self.assertEqual(r.returncode, 1, self.metin(r))
        self.assertIn("aXet klonu bulunamadi", self.metin(r))
        # klon yoksa klonun icindeki kur.cmd de yoktur: ilk kurulum dosyasi gosterilir (2026-09-25)
        self.assertIn("aXet-Kur.cmd ile kur", self.metin(r))
        self.assertNotIn("kur.cmd ile kur,", self.metin(r).replace("aXet-Kur.cmd ile kur", ""))

    def test_gate_yolda_ampersand_ciktiyi_bozmaz_komut_calistirmaz(self):
        # v0.5.6 gate: tırnaksız `echo %PROJE%` yolun `&` sonrasını KOMUT olarak çalıştırıyordu (ölçüldü: başlık
        # yolun `&` öncesinde kesildi + "The system cannot find the path specified.")
        d = self.tmp / "R&D" / "yok"
        r = subprocess.run(f'cmd /c ""{CMD}" "{d}""', input=b"\n", capture_output=True, cwd=str(self.tmp),
                           env=self.env, timeout=120)
        m = self.metin(r)
        self.assertEqual(r.returncode, 1, m)
        self.assertIn(f'aXet kurulum tamamlama - "{d}"', m)
        self.assertIn(f'proje klasoru bulunamadi: "{d}"', m)
        self.assertNotIn("cannot find the path", m)

    def test_gate_kisayol_hata_satiri_yolu_tirnaklar(self):
        klon = self.tmp / "R&D" / "klon"
        hata = [s for s in yeni_proje.kisayol_metni(klon).splitlines() if s.startswith("echo HATA")]
        self.assertEqual(len(hata), 1, hata)
        self.assertIn(f'"{klon / yeni_proje.TAMAMLA_CMD}"', hata[0])


if __name__ == "__main__":
    unittest.main()
