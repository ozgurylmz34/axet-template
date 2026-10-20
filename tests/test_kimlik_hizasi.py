# -*- coding: utf-8 -*-
"""Kontrol listesi kimlik hizası (Z206) — `maintenance/sync_check.py --kimlik-denetle`.

Kural: çekirdek ailelerinin numarasını yalnız çekirdek verir; aXet'e özgü madde `AX-<AİLE>-<nn>` alır ve tek yerde
tanımlanır. Denetim yalnız aXet'in kendi dosyalarını ve `maintenance/kimlik-kaydi.json`'u okur, çekirdeğe ERİŞMEZ
(kayıt `sync_check.py --kimlik-kaydi` ile çekirdekten üretilir).

İki katman:
  ① GERÇEK depo kayda karşı temiz mi (giriş noktası: betik `subprocess` ile çağrılır).
  ② Denetimin KENDİSİ körleşmedi mi — sahte kökte doğru-pozitif + doğru-negatif BİRLİKTE (bir tarayıcı yalnız
     "temiz" diyorsa ölçülmemiştir). Fixture'lar geçici köke yazılır, gerçek ağaca dokunulmaz.

Test adları bilerek kimlik kodu taşımaz: vakum tarayıcısı `tests/`'i de tarar, adda geçip gövdede geçmeyen simge
bulgu sayılır.

KAPSAM — bakılmayan: kaydın çekirdekle güncel olup olmadığı (çekirdeğe erişim yok; tazelik `--update-lock` akışında)
· kural ANLAMI (aynı numara farklı kural — uyum raporundaki başlık benzerliği yalnız ipucu) · uyum raporu (④) çıktısı.
Public sürümde `maintenance/` yoktur → bu dosya açık SKIP verir.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import unittest
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

BETIK = AXET_HOME / "maintenance" / "sync_check.py"
KAYIT = AXET_HOME / "maintenance" / "kimlik-kaydi.json"
MUAF_DOSYA = "skills-sap/sap-adt-foundation/references/known-errors-adt.md"


def tablo(*satirlar: str, baslik: str = "ID") -> str:
    govde = "".join(f"| {k} | {m} | HATA |\n" for k, m in satirlar)
    return f"# Liste\n\n| {baslik} | Madde | Önem |\n|---|---|---|\n{govde}"


@unittest.skipUnless(BETIK.is_file(), "maintenance/sync_check.py yok (public sürümde maintenance/ dışlanır)")
class GercekDepoKimlikHizasi(GeciciTest):

    def test_kayit_dosyasi_dolu_ve_kaynakli(self):
        self.assertTrue(KAYIT.is_file(), "maintenance/kimlik-kaydi.json yok — `sync_check.py --kimlik-kaydi` ile üret")
        kayit = json.loads(KAYIT.read_text(encoding="utf-8"))
        self.assertTrue(kayit.get("commit"), "kayıtta kaynak commit yok")
        self.assertGreater(len(kayit.get("kimlikler") or {}), 100, "kayıt boş ya da eksik üretilmiş")

    def test_cekirdek_kaynak_adi_kural_dosyasi_ve_kayitla_ayni(self):
        """Fixture testleri adı sabitten okur ⇒ sabit tek başına değişse onlar yeşil kalır. Bu test sabiti GERÇEK
        kural dosyası ve kayıtla karşılaştırır (ad metne yazılmaz, dosyalardan okunur)."""
        spec = importlib.util.spec_from_file_location("sync_check_gercek_ad", BETIK)
        sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sc)
        kurallar = json.loads((BETIK.parent / "sync-rules.json").read_text(encoding="utf-8"))
        self.assertIn(sc.CEKIRDEK_KAYNAK, kurallar.get("sources") or {},
                      "CEKIRDEK_KAYNAK sync-rules.json 'sources' içinde yok — --update-lock kaydı yazamaz")
        self.assertEqual(json.loads(KAYIT.read_text(encoding="utf-8")).get("kaynak"), sc.CEKIRDEK_KAYNAK,
                         "kimlik kaydının kaynağı CEKIRDEK_KAYNAK ile aynı değil")

    def test_depo_kayda_uyar(self):
        r = self.calistir(BETIK, "--kimlik-denetle", scripts_dir=BETIK.parent)
        cikti = self.cikti(r)
        self.assertIn("KAPSAM BEYANI", cikti, "kapsam beyanı basılmadı")
        self.assertIn("BAKILMAYAN", cikti)
        self.assertEqual(r.returncode, 0, cikti)
        self.assertIn("[OK]", cikti)


@unittest.skipUnless(BETIK.is_file(), "maintenance/sync_check.py yok (public sürümde maintenance/ dışlanır)")
class KimlikDenetimKalibrasyon(GeciciTest):
    """Sahte kök: <tmp>/kok/skills-sap/... + <tmp>/kayit.json"""

    def setUp(self) -> None:
        super().setUp()
        self.kok = self.tmp / "kok"
        self.kok.mkdir()

    def yaz(self, yol: str, metin: str, satir_sonu: str = "\n") -> None:
        p = self.kok / yol
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(metin, encoding="utf-8", newline=satir_sonu)

    def denetle(self, kimlikler=("FE-01", "FE-02"), commit: str | None = "abc1234", ham: str | None = None):
        kayit = self.tmp / "kayit.json"
        if ham is not None:
            kayit.write_text(ham, encoding="utf-8")
        else:
            veri = {"kimlikler": {k: {"yer": "x.md"} for k in kimlikler},
                    "taranan": ["playbook/checklists"]}
            if commit:
                veri["commit"] = commit
            kayit.write_text(json.dumps(veri), encoding="utf-8")
        r = self.calistir(BETIK, "--kimlik-denetle", "--kok", str(self.kok), "--kayit", str(kayit),
                          scripts_dir=BETIK.parent)
        return r.returncode, self.cikti(r)

    # --- doğru-negatif -------------------------------------------------------------------------------------

    def test_kayitli_cekirdek_kimligi_gecer(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a"), ("AX-FE-01", "b")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 0, cikti)
        self.assertIn("2 tanım", cikti)

    def test_cekirdek_kimligi_iki_skillde_serbest(self):
        self.yaz("skills-sap/a/references/checklists.md", tablo(("FE-01", "a")))
        self.yaz("skills-sap/b/references/checklists.md", tablo(("FE-01", "a")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 0, cikti)
        self.assertIn("FE-01 (2)", cikti, "çok-yerli çekirdek kimliği kapsam beyanında sayılmadı")

    def test_kod_blogu_sablon_ve_basliksiz_tablo_tanim_sayilmaz(self):
        self.yaz("skills-sap/ui/references/checklists.md",
                 tablo(("FE-01", "a")) + "\n```\n| FE-99 | örnek | HATA |\n```\n"
                 + "\n## Belge\n\n| Ad | Açıklama |\n|---|---|\n| FE-98 | belge içi |\n")
        self.yaz("skills-sap/ui/templates/ornek.md", tablo(("FE-97", "şablon")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 0, cikti)
        self.assertNotIn("FE-99", cikti)
        self.assertNotIn("FE-97", cikti)
        self.assertIn("bakılmayan tablo satırı (kimlik biçimli ilk hücre, başlık listede yok): 1", cikti)

    def test_crlf_dosya_ayni_sonucu_verir(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a"), ("FE-99", "b")), satir_sonu="\r\n")
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[KAYITTA-YOK] FE-99", cikti)
        self.assertIn("2 tanım", cikti)

    # --- doğru-pozitif -------------------------------------------------------------------------------------

    def test_kayitta_olmayan_cekirdek_ailesi_kimligi_fail(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a"), ("FE-99", "uydurma")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[KAYITTA-YOK] FE-99", cikti)
        self.assertIn("checklists.md:6", cikti, "ihlalin yeri (dosya:satır) basılmadı")

    def test_baslik_bicimli_tanim_yakalanir(self):
        self.yaz("skills-sap/ui/references/checklists.md",
                 tablo(("FE-01", "a")) + "\n### FE-98 · başlıkla tanımlı\n\n### FE-01 ek · alt bölüm\n")
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[KAYITTA-YOK] FE-98", cikti)
        self.assertNotIn("FE-01 (2)", cikti, "`ek ·` alt bölümü ikinci tanım sayıldı")

    def test_ayni_ax_kimligi_iki_yerde_fail(self):
        self.yaz("skills-sap/a/references/checklists.md", tablo(("AX-FE-01", "a")))
        self.yaz("skills-sap/b/references/checklists.md", tablo(("AX-FE-01", "başka")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[AX-ÇİFT-TANIM] AX-FE-01", cikti)

    def test_ax_kimligi_iki_haneli_numara_ister(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("AX-FE-1", "a"), ("AX-CLC-ATC-01", "b")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[AX-BİÇİM] AX-FE-1", cikti)
        self.assertNotIn("[AX-BİÇİM] AX-CLC-ATC-01", cikti, "çok parçalı aile adı biçim hatası sayıldı")

    # --- dar muafiyet --------------------------------------------------------------------------------------

    def test_muafiyet_yalniz_dosya_ve_aile_ciftine(self):
        self.yaz(MUAF_DOSYA, "# Katalog\n\n### K-01 · bir hata\n\n### K-02 · başka hata\n")
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a"), ("K-03", "muaf dosya dışında")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[KAYITTA-YOK] K-03", cikti, "muafiyet dosya dışına taştı")
        self.assertNotIn("[KAYITTA-YOK] K-01", cikti, "muaf dosyadaki kimlik kayıtta aranmamalı")
        self.assertIn("2 muaf", cikti)

    def test_muaf_katalogda_da_tekillik_aranir(self):
        self.yaz(MUAF_DOSYA, "# Katalog\n\n### K-01 · bir hata\n\n### K-01 · aynı numara\n")
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a")))
        rc, cikti = self.denetle()
        self.assertEqual(rc, 1, cikti)
        self.assertIn("[MUAF-ÇİFT-TANIM] K-01", cikti)

    def test_muaf_aile_cekirdekte_acilirsa_uyarir(self):
        self.yaz(MUAF_DOSYA, "# Katalog\n\n### K-01 · bir hata\n")
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a")))
        rc, cikti = self.denetle(kimlikler=("FE-01", "K-05"))
        self.assertEqual(rc, 0, cikti)
        self.assertIn("muafiyet gözden geçirilmeli): K-: K-05", cikti)

    # --- ÖLÇÜLEMEDİ ----------------------------------------------------------------------------------------

    def test_bos_kayit_olculemedi_verir(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a"), ("FE-99", "b")))
        rc, cikti = self.denetle(kimlikler=())
        self.assertEqual(rc, 2, cikti)
        self.assertIn("[ÖLÇÜLEMEDİ]", cikti)
        self.assertNotIn("[OK]", cikti)

    def test_okunamayan_kayit_olculemedi_verir(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a")))
        rc, cikti = self.denetle(ham="{bozuk")
        self.assertEqual(rc, 2, cikti)
        self.assertIn("[ÖLÇÜLEMEDİ] kimlik kaydı okunamadı", cikti)

    def test_kaynaksiz_kayit_olculemedi_verir(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a")))
        rc, cikti = self.denetle(commit=None)
        self.assertEqual(rc, 2, cikti)
        self.assertIn("kaynak 'commit' alanı yok", cikti)

    def test_sifir_tanim_temiz_sayilmaz(self):
        self.yaz("skills-sap/ui/references/checklists.md", "# Liste\n\nTablo yok.\n")
        rc, cikti = self.denetle()
        self.assertEqual(rc, 2, cikti)
        self.assertIn("0 kimlik tanımı", cikti)

    def test_bos_kok_temiz_sayilmaz(self):
        rc, cikti = self.denetle()
        self.assertEqual(rc, 2, cikti)
        self.assertIn(".md dosyası YOK", cikti)

    def test_kirli_kayit_kapsamda_uyarir(self):
        self.yaz("skills-sap/ui/references/checklists.md", tablo(("FE-01", "a")))
        kayit = self.tmp / "kayit.json"
        kayit.write_text(json.dumps({"commit": "abc1234", "kirli": True, "kimlikler": {"FE-01": {"yer": "x.md"}}}),
                         encoding="utf-8")
        r = self.calistir(BETIK, "--kimlik-denetle", "--kok", str(self.kok), "--kayit", str(kayit),
                          scripts_dir=BETIK.parent)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("kayıt KİRLİ çekirdek ağacından", self.cikti(r))


# Sahte çekirdek SERBEST METNİ: kayıt dosyasına sızmaması gereken işaret. Gerçek sızıntı deseni (yerel liste, git'e
# girmez) burada YAZILMAZ — sınanan özellik "çekirdek başlık metni diske gitmez"dir, desenden bağımsız.
SIZINTI_ISARETI = "SIZINTI-ISARETI-7Q"


@unittest.skipUnless(BETIK.is_file(), "maintenance/sync_check.py yok (public sürümde maintenance/ dışlanır)")
class KimlikKaydiUreteci(GeciciTest):
    """Üretecin giriş noktası `main()` (`--source <kaynak çekirdek>=<sahte çekirdek> --kimlik-kaydi`), süreç İÇİ:
    modül globalleri (kural/kilit/kayıt yolu) geçici dosyalara çevrilir ⇒ gerçek `maintenance/` dosyalarına yazılmaz.
    Kaynak adı `sync_check.CEKIRDEK_KAYNAK`'tan okunur — bu dosya public depoya gider, iç adı düz yazmaz."""

    def setUp(self) -> None:
        super().setUp()
        spec = importlib.util.spec_from_file_location("sync_check_test_kopyasi", BETIK)
        self.sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.sc)
        self.cekirdek = self.tmp / "cekirdek"
        self.cekirdek.mkdir()
        self.yaz("playbook/checklists/liste.md",
                 tablo(("FE-01", f"Ad {SIZINTI_ISARETI} önekinde mi?"), ("DOC-KD-01", "belge maddesi")))
        self.yaz("standards/04-documentation-fs-ts.md",
                 tablo(("RPT-001", "örnek rapor"), ("EXC-001", "örnek istisna"), ("FE-02", "gerçek kural")))
        for ek in self.sc.CEKIRDEK_EK_DOSYALAR:
            self.yaz(ek, "# boş\n")
        self.git(self.cekirdek, "init", "-q")
        self.git(self.cekirdek, "add", "-A")
        self.git(self.cekirdek, "commit", "-q", "-m", "sahte çekirdek")
        self.kurallar = self.tmp / "sync-rules.json"
        self.kural_yaz()
        self.kayit = self.tmp / "kimlik-kaydi.json"

    def yaz(self, yol: str, metin: str) -> None:
        p = self.cekirdek / yol
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(metin, encoding="utf-8", newline="\n")

    def kural_yaz(self, karar: str = "alinmaz", desen: str = "*", ad: str | None = None) -> None:
        ad = ad or self.sc.CEKIRDEK_KAYNAK
        self.kurallar.write_text(json.dumps({"sources": {ad: {}}, "rules": [
            {"source": ad, "pattern": desen, "decision": karar, "status": "-", "targets": [],
             "note": "test"}]}), encoding="utf-8")

    def calistir_main(self, *bayraklar: str) -> tuple[int, str, str]:
        cikti, hata = io.StringIO(), io.StringIO()
        self.kilit = self.tmp / "sync-lock.json"
        with mock.patch.object(self.sc, "RULES_FILE", self.kurallar), \
                mock.patch.object(self.sc, "LOCK_FILE", self.kilit), \
                mock.patch.object(self.sc, "KIMLIK_KAYDI", self.kayit), \
                mock.patch.object(self.sc, "AXET_HOME", self.tmp / "bos-axet"), \
                mock.patch.object(sys, "argv", ["sync_check.py", "--source",
                                                f"{self.sc.CEKIRDEK_KAYNAK}={self.cekirdek}", *bayraklar]), \
                contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(hata):
            rc = self.sc.main()
        return rc, cikti.getvalue(), hata.getvalue()

    def uret(self) -> tuple[int, str]:
        rc, cikti, hata = self.calistir_main("--kimlik-kaydi")
        return rc, cikti + hata

    # --- kilit + kayıt: ikisi birlikte yazılır ya da hiçbiri ----------------------------------------------------

    def test_kilit_guncellemesi_kaydi_da_yazar(self):
        rc, cikti, hata = self.calistir_main("--update-lock")
        self.assertEqual(rc, 0, cikti + hata)
        self.assertTrue(self.kilit.is_file(), cikti)
        self.assertTrue(self.kayit.is_file(), "kilit yazıldı ama kimlik kaydı yazılmadı")

    def test_kayit_uretilemezse_kilit_de_yazilmaz(self):
        (self.cekirdek / self.sc.CEKIRDEK_EK_DOSYALAR[0]).unlink()   # kayıt kaynağı eksik ⇒ üretilemez
        rc, cikti, hata = self.calistir_main("--update-lock")
        self.assertNotEqual(rc, 0, cikti)
        self.assertFalse(self.kilit.exists(), "kimlik kaydı üretilemezken kilit yeni commit'e geçti")
        self.assertFalse(self.kayit.exists())
        self.assertIn("--update-lock YAPILMADI: çekirdek kimlik kaydı üretilemedi", cikti)

    def test_kural_dosyasinda_cekirdek_kaynagi_yoksa_hicbir_sey_yazilmaz(self):
        self.kural_yaz(ad="BASKA-KAYNAK")   # sabit ile kural dosyası ayrışmış
        rc, cikti, hata = self.calistir_main("--update-lock")
        self.assertEqual(rc, 3, cikti + hata)
        self.assertFalse(self.kilit.exists(), "çekirdek kaynağı tanımsızken kilit yazıldı")
        self.assertFalse(self.kayit.exists())
        self.assertIn("'sources' içinde yok", cikti)

    def test_kayit_yazilamazsa_kilit_eski_kalir(self):
        self.kilit = self.tmp / "sync-lock.json"
        eski = '{"sources": {}}\n'
        self.kilit.write_text(eski, encoding="utf-8")
        self.kayit = self.tmp / "olmayan-klasor" / "kimlik-kaydi.json"   # yazım FileNotFoundError ile patlar
        rc, cikti, hata = self.calistir_main("--update-lock")
        self.assertEqual(rc, 3, cikti + hata)
        self.assertEqual(self.kilit.read_text(encoding="utf-8"), eski, "kayıt yazılamadı ama kilit yenilendi")
        self.assertIn("Kimlik kaydı YAZILAMADI", cikti)
        self.assertIn("kilit de YAZILMADI", cikti)

    def test_kuralsiz_varken_kilit_ve_kayit_birlikte_yazilmaz(self):
        self.kural_yaz(desen="playbook/*")   # standards/ dosyaları KURALSIZ kalır
        rc, cikti, hata = self.calistir_main("--update-lock", "--kimlik-kaydi")
        self.assertEqual(rc, 1, cikti)
        self.assertFalse(self.kilit.exists())
        self.assertFalse(self.kayit.exists(), "KURALSIZ varken kilit yazılmadı ama kimlik kaydı yazıldı")
        self.assertIn("kimlik kaydı da YAZILMADI", cikti)

    def test_json_kipinde_yazilmadi_mesaji_stderr(self):
        self.kural_yaz(karar="gecersiz-karar")
        rc, cikti, hata = self.calistir_main("--kimlik-kaydi", "--json")
        self.assertEqual(rc, 2, cikti + hata)
        json.loads(cikti)   # stdout yalnız JSON taşır
        self.assertIn("YAZILMADI", hata)
        self.assertNotIn("YAZILMADI", cikti)

    def test_kayit_dosyasina_cekirdek_basligi_yazilmaz(self):
        rc, cikti = self.uret()
        self.assertTrue(self.kayit.is_file(), cikti)
        ham = self.kayit.read_text(encoding="utf-8")
        self.assertNotIn(SIZINTI_ISARETI, ham, "çekirdek başlık metni kayıt dosyasına sızdı")
        veri = json.loads(ham)
        self.assertIn("FE-01", veri["kimlikler"])
        self.assertTrue(all(set(v) == {"yer"} for v in veri["kimlikler"].values()),
                        "kayıt kimlik başına yalnız `yer` taşımalı (başlık anahtarı yok)")
        self.assertIs(veri["kirli"], False)
        self.assertFalse(self.kilit.exists(), "yalnız --kimlik-kaydi kilide dokunmamalı")

    def test_sablon_ornek_kimlikleri_kayda_girmez(self):
        rc, cikti = self.uret()
        veri = json.loads(self.kayit.read_text(encoding="utf-8"))
        self.assertNotIn("RPT-001", veri["kimlikler"])
        self.assertNotIn("EXC-001", veri["kimlikler"])
        self.assertIn("FE-02", veri["kimlikler"], "dışlama aile dışına (aynı dosyadaki gerçek kurala) taştı")
        self.assertIn("DOC-KD-01", veri["kimlikler"])
        self.assertEqual(len(veri["sablon_haric"]["dislanan"]), 2, veri["sablon_haric"])

    def test_kural_dosyasi_hataliyken_kayit_yazilmaz(self):
        self.kural_yaz(karar="gecersiz-karar")
        rc, cikti = self.uret()
        self.assertEqual(rc, 2, cikti)
        self.assertFalse(self.kayit.exists(), "kural dosyası hatalıyken kimlik kaydı yazıldı")
        self.assertIn("kimlik kaydı YAZILMADI", cikti)

    def test_kirli_cekirdek_kayda_isaretlenir(self):
        (self.cekirdek / "izlenmeyen.txt").write_text("x", encoding="utf-8")
        rc, cikti = self.uret()
        veri = json.loads(self.kayit.read_text(encoding="utf-8"))
        self.assertIs(veri["kirli"], True)
        self.assertIn("kirli: true", cikti)


@unittest.skipUnless(BETIK.is_file(), "maintenance/sync_check.py yok (public sürümde maintenance/ dışlanır)")
class BaslikTemizleme(unittest.TestCase):
    """Uyum raporunun başlık benzerliği: kalın ETİKET (MUST / EKSİK:) başlık sayılmaz."""

    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("sync_check_temiz_kopyasi", BETIK)
        cls.sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.sc)

    def test_kalin_etiket_atlanir(self):
        self.assertEqual(self.sc._temiz("**MUST** — Bir yardımcı görünümün anahtarı"), "Bir yardımcı görünümün anahtarı")
        self.assertEqual(self.sc._temiz("**EKSİK:** **Commit bariyeri** yok"), "Commit bariyeri")

    def test_kalin_cumle_korunur(self):
        self.assertEqual(self.sc._temiz("**Tablo onay kapısı atlandı** — ayrıntı"), "Tablo onay kapısı atlandı")
        self.assertEqual(self.sc._temiz("**MUST**"), "MUST", "etiketten sonra metin yoksa etiket kalır")


if __name__ == "__main__":
    unittest.main()
