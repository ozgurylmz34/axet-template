# -*- coding: utf-8 -*-
"""recall.py — hafıza kaydı GÖVDELERİNİN ve paket `.rules.md` dosyalarının taranması (IS-LISTESI Z71 ②③).

Ölçülen vaka (hatırlama check-up'ı, 2026-09-23): indeks satırı konu söylemeyen ("Çıktı kanalı kararı — kullanıcı
çıktı kanalı hakkında karar") bir proje kaydı, gövdesinde "ALV … Excel'e aktarımı … GUI_DOWNLOAD kullanılmaz" yazdığı
hâlde `%recall "klasik ALV raporu Excel'e disa aktarim export form rutini …"` ile BULUNAMADI (C3) — script yalnız
indeks satırı + description tarıyordu. Paket belirtilmeyen işte paket `.rules.md` önek kuralı da görülmedi (B).

Burada ölçülen: ⓐ gövde eşleşmesi eşik üstüne çıkar ⓑ indeks/özet eşleşmesi gövde eşleşmesinden AĞIR basar
ⓒ `<source_root>/**/.rules.md` taranır, `source_root` `sap-project.json`'dan okunur ⓓ KAPSAM satırı gövdeyi ve paket
kurallarını beyan eder.
KAPSAM — bakılmayanlar: modelin `%recall`'u kendiliğinden çağırması ve sonucu uygulaması (canlı senaryo ölçümü, Z71 ⑤)
· puanlamanın gerçek hafıza setinde sıralama kalitesi (yalnız sentetik vakalar) · süre (performans testi yok).
"""
from __future__ import annotations

import json
from pathlib import Path

from _helpers import AXET_HOME, GeciciTest

RECALL = AXET_HOME / "skills" / "recall" / "scripts" / "recall.py"
# Paket adı geçen ad sorusu. Paket geçmeyen soruda .rules.md'yi getiren recall DEĞİL, core/sap/00-sap.md kuralıdır.
PAKET_SORGUSU = "$TMP paketinde yeni Z tablo adı önek ZAXET naming"
C3_SORGUSU = "klasik ALV raporu Excel'e disa aktarim export form rutini ZAXET_T_ALV03 $TMP"  # check-up C3, AYNEN

BELIRSIZ_KAYIT = """---
name: cikti-kanali
description: kullanici cikti kanali hakkinda verilen karar
type: project
---

Bu projede ALV raporlarinin Excel'e aktarimi YALNIZ yardimci sinif ile yapilir:
`ZCL_AXET_XLSX_EXPORTER=>EXPORT_ALL( it_data = <tablo> )`. `GUI_DOWNLOAD`, `cl_salv_bs_lex` ve
SALV'nin kendi dugmesi kullanilmaz (kullanici karari, 2026-09-22).

**Neden:** kurumsal sablon + tum satirlarin aktarimi tek yerde.
**Nasil uygulanir:** yeni ALV raporu yazarken disa aktarim kodu bu cagriyla yazilir.
"""

RULES = """---
layer: paket
scope: package:$TMP
---

# $TMP (TEST) — Paket kuralları

- **Başlık:** Test/deneme — yerel objeler

## Naming
| Obje tipi | Önek |
|---|---|
| Tablo (DDIC) | `ZAXET_T_<AD>` (tek `T` — tip harfi) |
| Program (rapor, klasik) | `ZAXET_T_ALV<NN>` |
"""


class _RecallTaban(GeciciTest):
    """Ortak kurulum/çağırma yardımcıları (test yok — alt sınıflar testleri iki kez koşturmasın)."""

    def proje_kur(self, indeks_satirlari: list[str], kayitlar: dict[str, str], source_root: str | None = None,
                  rules: dict[str, str] | None = None) -> Path:
        d = self.tmp / "proje"
        mem = d / ".axet-code" / "memory"
        self.yaz(mem / "MEMORY.md", "# PROJE HAFIZASI\n\n## Kararlar ve durum (project)\n\n"
                 + "".join(s + "\n" for s in indeks_satirlari))
        for ad, metin in kayitlar.items():
            self.yaz(mem / ad, metin)
        if source_root is not None:
            self.yaz(d / "sap-project.json", json.dumps({"project": "P", "source_root": source_root}))
        for rel, metin in (rules or {}).items():
            self.yaz(d / rel, metin)
        return d

    def recall(self, d: Path, sorgu: str, *ek: str) -> dict:
        r = self.calistir(RECALL, sorgu, "--project-dir", str(d), "--json", "--top", "10", *ek)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return json.loads(r.stdout)

    @staticmethod
    def yollar(o: dict) -> list[str]:
        return [Path(s["yol"]).name for s in o["sonuc"]]


class RecallTest(_RecallTaban):
    # ⓐ C3 vakası: konu söylemeyen indeks satırı + anahtar kelimeler yalnız GÖVDEDE
    def test_govdede_gecen_kayit_bulunur(self):
        d = self.proje_kur(["- [Çıktı kanalı kararı](project_cikti-kanali.md) — kullanıcı çıktı kanalı hakkında karar"],
                           {"project_cikti-kanali.md": BELIRSIZ_KAYIT})
        o = self.recall(d, C3_SORGUSU)
        self.assertIn("project_cikti-kanali.md", self.yollar(o), o)

    # ⓐ' gövdede yalnız 3 farklı sözcük (ana eşik 5'in altı) → ayrı "gövde adayı" listesinde (Z71 kapanış C3 koşum 1 sorgusu)
    def test_esik_alti_govde_eslesmesi_aday_listesinde(self):
        d = self.proje_kur(["- [Çıktı kanalı kararı](project_cikti-kanali.md) — kullanıcı çıktı kanalı hakkında karar"],
                           {"project_cikti-kanali.md": BELIRSIZ_KAYIT})
        o = self.recall(d, "ZAXET_T_ALV03 klasik ALV rapor Excel export form rutini $TMP paket")
        self.assertNotIn("project_cikti-kanali.md", self.yollar(o), o)
        self.assertIn("project_cikti-kanali.md", [Path(s["yol"]).name for s in o["govde_adaylari"]], o)

    # ⓑ ağırlık: aynı sözcükler indekste geçen kayıt, yalnız gövdesinde geçen kayıttan önce gelir
    def test_indeks_eslesmesi_govdeden_once_gelir(self):
        acik = ("---\nname: alv-excel\ndescription: x\ntype: project\n---\n\nAyrıntı yok.\n")
        d = self.proje_kur(
            ["- [Çıktı kanalı kararı](project_cikti-kanali.md) — kullanıcı çıktı kanalı hakkında karar",
             "- [ALV Excel dışa aktarım](project_alv-excel.md) — klasik ALV raporu Excel'e dışa aktarım rutini"],
            {"project_cikti-kanali.md": BELIRSIZ_KAYIT, "project_alv-excel.md": acik})
        o = self.recall(d, C3_SORGUSU)
        y = self.yollar(o)
        self.assertIn("project_alv-excel.md", y, o)
        self.assertIn("project_cikti-kanali.md", y, o)
        self.assertLess(y.index("project_alv-excel.md"), y.index("project_cikti-kanali.md"), o)

    # ⓒ paket .rules.md, source_root sap-project.json'dan
    def test_paket_rules_md_bulunur(self):
        d = self.proje_kur([], {}, source_root="SRC", rules={"SRC/TEST/$TMP/.rules.md": RULES})
        o = self.recall(d, PAKET_SORGUSU)
        self.assertIn(".rules.md", self.yollar(o), o)
        self.assertEqual(o["taranan"].get("paket kuralı"), 1, o)

    def test_source_root_disindaki_rules_md_taranmaz(self):
        # sap-project.json source_root=SRC → SOURCE_CODES altındaki dosya paket kuralı sayılmaz
        d = self.proje_kur([], {}, source_root="SRC", rules={"SOURCE_CODES/TEST/$TMP/.rules.md": RULES})
        o = self.recall(d, PAKET_SORGUSU)
        self.assertEqual(o["taranan"].get("paket kuralı"), 0, o)
        self.assertNotIn(".rules.md", self.yollar(o), o)

    def test_sap_project_json_yoksa_paket_kurali_yok_ve_cokmez(self):
        d = self.proje_kur([], {}, rules={"SOURCE_CODES/TEST/$TMP/.rules.md": RULES})
        o = self.recall(d, PAKET_SORGUSU)
        self.assertEqual(o["taranan"].get("paket kuralı"), 0, o)

    # ⓓ düz metin çıktısının KAPSAM beyanı
    def test_kapsam_satiri_govde_ve_paket_kuralini_beyan_eder(self):
        d = self.proje_kur(["- [Çıktı kanalı kararı](project_cikti-kanali.md) — kullanıcı çıktı kanalı hakkında karar"],
                           {"project_cikti-kanali.md": BELIRSIZ_KAYIT}, source_root="SRC",
                           rules={"SRC/TEST/$TMP/.rules.md": RULES})
        r = self.calistir(RECALL, C3_SORGUSU, "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        kapsam = next((s for s in r.stdout.splitlines() if s.startswith("KAPSAM:")), "")
        self.assertIn("paket kuralı 1", kapsam, r.stdout)
        self.assertIn("gövde", kapsam, r.stdout)
        self.assertNotIn("bakılmayan: kayıt/skill gövdeleri", kapsam, r.stdout)


class RecallEsikOlceklemeTest(_RecallTaban):
    """Z108 (2026-09-24): tek terimli sorgu, terimi yalnız AÇIKLAMASINDA taşıyan skill'i bulmuyordu. Ölçülen: gerçek bir tüketici projesinde
    `recall.py "transport" --esik 1` → sap-adt-foundation 2, sap-cds-ddic 1 puan; sap-gui-scripting hiç (açıklamada çoğul
    "transports", indeks eşleşmesi tam sözcük). Sabit eşik 5'e tek terimli sorgu yapısal olarak ulaşamıyordu.
    Burada ölçülen: ⓐ varsayılan eşik sorgunun terim sayısına göre ölçeklenir ⓑ indekste (başlık/açıklama) önek eşleşmesi
    gövdedeki ONEK_EN_AZ kuralıyla aynı ⓒ açık --esik ölçeklenmez ⓓ çok (≥ 5) terimli sorguda sonuç/sıra değişmez
    (kontrol grubu — düzeltmeden önce de yeşildir) ⓔ KAPSAM satırı etkin eşiği ve ölçeklemeyi beyan eder ⓕ genel sayımı
    tam sözcükle (önek değil) ⓖ indekste önekle eşleşen terim gövdede tekrar sayılmaz.
    KAPSAM — bakılmayanlar: gerçek hafıza setinde sıralama kalitesi (önce/sonra ölçümü PR notunda, test değil)."""

    TERIM = "kilimbalik"   # sentetik; template'in hafıza/skill metinlerinde geçmez (rg ile bakıldı, 2026-09-24)
    # Skill adı sorgu terimiyle ÖNEK PAYLAŞMAZ: "kilim-araci" adı "kilim" token'ı üretiyordu ve ters yön önek mutantı
    # (`t.startswith(sozcuk)`) ⓑ testini bu yüzden geçiyordu (Z108 bug gate, bulgu 5).
    SKILL = "desen-araci"

    def skill_kur(self, aciklama: str, ad: str | None = None) -> Path:
        ad = ad or self.SKILL
        d = self.proje_kur([], {})
        self.yaz(d / ".axet-code" / "skills" / ad / "SKILL.md",
                 f"---\nname: {ad}\ndescription: >\n  {aciklama}\n---\n\n# {ad}\n")
        return d

    def skill_yollari(self, o: dict) -> list[str]:
        return [Path(s["yol"]).parent.name for s in o["sonuc"]]

    # ⓐ terim yalnız açıklamada, bir kez → puan 1; sabit eşik 5'te bulunamıyordu
    def test_tek_terimli_sorgu_aciklamadaki_skilli_bulur(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.")
        o = self.recall(d, self.TERIM)
        self.assertIn(self.SKILL, self.skill_yollari(o), o)
        self.assertEqual(o["esik"], 1, o)

    # ⓑ çoğul/ekli biçim: sorgu "kilimbalik" ↔ açıklama "kilimbaliklar" (≥ ONEK_EN_AZ harf → önek eşleşmesi)
    def test_indekste_onek_eslesmesi(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM}lar icin desen hazirlar.")
        o = self.recall(d, self.TERIM, "--esik", "1")
        self.assertIn(self.SKILL, self.skill_yollari(o), o)

    # ⓑ' negatif kontrol: ONEK_EN_AZ'dan kısa sorgu sözcüğü önekle eşleşmez (gövdedeki kuralla aynı). Sınırın iki yanı
    # birlikte ölçülür: 4 harf eşleşmez, 5 harf eşleşir (kontrol grubu). `genel_sayilan == []` şartı testin DOĞRU
    # sebeple geçtiğini sabitler: önceki hâlinde "kili" template'te önekle 4 kayıtta geçtiği için genel sayılıp
    # düşüyordu ve ONEK_EN_AZ=4 mutantına karşı test boştu (Z108 bug gate, bulgu 4).
    def test_kisa_sorgu_sozcugu_onekle_eslesmez(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.")
        # --top 1000: template'teki "kili…" kayıtları (kilit, kilidi) mutantta skill'i ilk 10'un dışına itemesin
        o = self.recall(d, self.TERIM[:4], "--esik", "1", "--top", "1000")
        self.assertEqual(o["genel_sayilan"], [], o)
        self.assertNotIn(self.SKILL, self.skill_yollari(o), o)
        o5 = self.recall(d, self.TERIM[:5], "--esik", "1")
        self.assertIn(self.SKILL, self.skill_yollari(o5), o5)

    # ⓑ'' önek yalnız SORGU sözcüğünden kayıt sözcüğüne doğrudur: kayıt sözcüğü sorgu sözcüğünün öneki ise eşleşmez
    # (ters yön mutantını skill adından bağımsız yakalar)
    def test_onek_ters_yonde_eslesmez(self):
        d = self.skill_kur("Dokuma tezgahinda kilimb desenlerini hazirlar.")
        o = self.recall(d, self.TERIM, "--esik", "1")
        self.assertNotIn(self.SKILL, self.skill_yollari(o), o)

    # ⓕ genel sayımı TAM sözcükle yapılır, puanlama önekli olsa da (Z108 bug gate, bulgu 1-2). Kurgu "code review"
    # vakasının sentetik eşi: ilk terim 12 kayıtta tam geçer (gerçekten genel); ikinci terim tam olarak YALNIZ skill
    # açıklamasında, önekli biçimi ("…lar") 4 kayıtta daha geçer. Önekle sayılsaydı 5 > tavan 4 → genel sayılır, sorgunun
    # iki terimi de düşer ve skill hiç bulunmazdı (gerçek bir tüketici projesinde "code review" → "Eşik üstü kayıt yok").
    def test_genel_sayimi_tam_eslesmeyle_onekli_bicimler_terimi_dusurmez(self):
        d = self.proje_kur([f"- [Zeytinbahce kaydi {i}](project_z{i}.md) — zeytinbahce notu" for i in range(12)]
                           + [f"- [Tezgah notu {i}](project_t{i}.md) — {self.TERIM}lar hakkinda" for i in range(4)], {})
        self.yaz(d / ".axet-code" / "skills" / self.SKILL / "SKILL.md",
                 f"---\nname: {self.SKILL}\ndescription: >\n  Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.\n---\n")
        o = self.recall(d, f"zeytinbahce {self.TERIM}")
        self.assertEqual(o["genel_sayilan"], ["zeytinbahce"], o)
        self.assertIn(self.SKILL, self.skill_yollari(o), o)

    # ⓕ' aynı kusurun gerçek template içeriğiyle ölçümü (template'e BAĞLIDIR — skill açıklamaları değişirse gözden geçir):
    # "code" template'te genel, "review" tam olarak az kayıtta ama önekle (reviewer, reviews …) tavanın üstünde
    def test_code_review_sorgusu_code_review_skillini_bulur(self):
        d = self.proje_kur([], {})
        o = self.recall(d, "code review")
        self.assertNotIn("review", o["genel_sayilan"], o)
        self.assertIn("code-review", self.skill_yollari(o), o)

    # ⓖ gövde puanı indekste ÖNEKLE eşleşmiş terimi yeniden saymaz (çift sayım yok, Z108 bug gate bulgu 3): indeks satırında
    # "kilimbaliklar", gövdede "kilimbalik" → puan 1 (indeks), gövde 0. Gövdeden yalnız TAM indeks sözcükleri çıkarılsaydı
    # (eski `- set(anahtar)`) puan 2, gövde 1 olurdu.
    def test_indekste_onekle_eslesen_terim_govdede_tekrar_sayilmaz(self):
        d = self.proje_kur([f"- [Tezgah notu](project_k.md) — {self.TERIM}lar icin ayar"],
                           {"project_k.md": f"---\nname: k\ndescription: x\ntype: project\n---\n\nBu projede {self.TERIM} "
                                            "tezgahta kullanilmaz.\n"})
        o = self.recall(d, self.TERIM)
        k = next((s for s in o["sonuc"] if Path(s["yol"]).name == "project_k.md"), None)
        self.assertIsNotNone(k, o)
        self.assertEqual((k["puan"], k["govde_puani"]), (1, 0), o)

    # ⓒ kullanıcının açıkça verdiği eşik ölçeklenmez
    def test_acik_esik_olceklenmez(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.")
        o = self.recall(d, self.TERIM, "--esik", "5")
        self.assertNotIn(self.SKILL, self.skill_yollari(o), o)
        self.assertEqual(o["esik"], 5, o)
        self.assertIs(o["esik_olceklendi"], False, o)

    # ⓓ kontrol grubu: 5 terimli sorguda eşik 5 kalır; sıralama ve eşik altı kayıtlar değişmez
    def test_cok_terimli_sorgu_sonucu_degismez(self):
        d = self.proje_kur(
            ["- [Zeytinbahce limonagaci kaydi](project_r1.md) — portakalbahce notu",
             "- [Baska bir konu](project_r2.md) — zeytinbahce limonagaci portakalbahce incirdali",
             "- [Ucuncu konu](project_r3.md) — zeytinbahce hakkinda tek satir",
             "- [Narcicegi incirdali kaydi](project_r4.md) — zeytinbahce limonagaci"],
            {f"project_r{i}.md": f"---\nname: r{i}\ndescription: x\ntype: project\n---\n\nAyrinti yok.\n"
             for i in range(1, 5)})
        o = self.recall(d, "zeytinbahce limonagaci portakalbahce incirdali narcicegi")
        self.assertEqual(self.yollar(o), ["project_r4.md", "project_r1.md"], o)
        self.assertEqual(o["esik"], 5, o)
        self.assertIs(o["esik_olceklendi"], False, o)

    # ⓐ' iki terimli sorguda eşik 3 (biçim: min(5, max(1, 2n − 1)); 3+ terim → 5, değişmez)
    def test_iki_terimli_sorguda_esik_uc(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.")
        o = self.recall(d, f"{self.TERIM} tezgahduzen")
        self.assertEqual((o["esik"], o["terim_sayisi"], o["esik_olceklendi"]), (3, 2, True), o)

    # ⓐ'' ölçeklenmiş eşik YALNIZ gövdesiyle eşleşen kayda uygulanmaz (tüketici projesi ölçümü: "test"/"ui5" tek terimli sorgusu
    # gövdesinde sözcüğü bir kez geçen alakasız kayıtları listeliyordu). Düzeltmeden önce de yeşildir (eşik 5).
    def test_olceklenmis_esik_yalniz_govde_eslesmesine_uygulanmaz(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.")
        self.yaz(d / ".axet-code" / "memory" / "MEMORY.md",
                 "# PROJE HAFIZASI\n\n- [Dokuma notu](project_dokuma.md) — tezgah ayarlari\n")
        self.yaz(d / ".axet-code" / "memory" / "project_dokuma.md",
                 f"---\nname: dokuma\ndescription: x\ntype: project\n---\n\nBu projede {self.TERIM} kullanilmaz.\n")
        o = self.recall(d, self.TERIM)
        self.assertIn(self.SKILL, self.skill_yollari(o), o)
        self.assertNotIn("project_dokuma.md", self.yollar(o), o)

    # ③ tek terim başlık/özetlerde GENEL sayılırsa (çok kayıtta geçer) indeks puanı kalmaz → sessiz boş sonuç yerine uyarı
    def test_tum_terimler_genel_sayilinca_uyari(self):
        d = self.proje_kur([f"- [Zeytinbahce kaydi {i}](project_z{i}.md) — zeytinbahce notu" for i in range(12)], {})
        o = self.recall(d, "zeytinbahce")
        self.assertEqual(o["genel_sayilan"], ["zeytinbahce"], o)
        self.assertIn("genel sayıldı", o["uyari"], o)
        r = self.calistir(RECALL, "zeytinbahce", "--project-dir", str(d))
        self.assertIn("UYARI: sorgunun tüm terimleri", r.stdout, self.cikti(r))

    # ⓐ''' terim sayısı indekste GENEL sayılanlar çıkarılarak alınır (tüketici projesi: "UI5 bootstrap backend" → ui5/backend genel,
    # sap-ui5-fiori açıklamasındaki "bootstrap" ile bulunur; genel terimler de sayılsaydı eşik 5 kalır, bulunmazdı)
    def test_genel_terimler_terim_sayisina_katilmaz(self):
        d = self.proje_kur([f"- [Zeytinbahce kaydi {i}](project_z{i}.md) — zeytinbahce limonagaci notu" for i in range(12)],
                           {})
        self.yaz(d / ".axet-code" / "skills" / self.SKILL / "SKILL.md",
                 f"---\nname: {self.SKILL}\ndescription: >\n  Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.\n---\n")
        o = self.recall(d, f"zeytinbahce limonagaci {self.TERIM}")
        self.assertEqual(o["genel_sayilan"], ["limonagaci", "zeytinbahce"], o)
        self.assertEqual((o["esik"], o["terim_sayisi"]), (1, 1), o)
        self.assertIn(self.SKILL, self.skill_yollari(o), o)

    # ⓔ düz metin KAPSAM satırı etkin eşiği ve ölçekleme gerekçesini söyler
    def test_kapsam_satiri_olceklenen_esigi_beyan_eder(self):
        d = self.skill_kur(f"Dokuma tezgahinda {self.TERIM} desenlerini hazirlar.")
        r = self.calistir(RECALL, self.TERIM, "--project-dir", str(d))
        self.assertEqual(r.returncode, 0, self.cikti(r))
        kapsam = next((s for s in r.stdout.splitlines() if s.startswith("KAPSAM:")), "")
        self.assertIn("eşik 1 (varsayılan 5, 1 terimli sorgu için ölçeklendi)", kapsam, r.stdout)


class HatirlamaYonlendirmeMetniTest(GeciciTest):
    """Z71 ①③ yönlendirme cümleleri (model davranışı canlı ölçüldü; bu test yalnız cümlenin sessizce SİLİNMESİNİ yakalar
    — aynı dosyalara paralel dallar dokunuyor). Anlamı/uygulanmayı ölçmez."""

    def oku(self, rel: str) -> str:
        return (AXET_HOME / rel).read_text(encoding="utf-8")

    def test_bagli_kural_agents_md_yolu_yazili(self):
        self.assertRegex(self.oku("skills/remember/SKILL.md"), r"bağlayıcı kural\*\*.*AGENTS\.md.*Proje kuralları")
        self.assertRegex(self.oku("core/00-temel.md"), r"bağlayıcı kural.*AGENTS\.md.*Proje kuralları")

    def test_paket_belirtilmeyen_ad_onerisinde_rules_md(self):
        self.assertRegex(self.oku("core/sap/00-sap.md"), r"Z obje adı .*ÖNERMEDEN önce.*paket söylenmese de.*\.rules\.md")
