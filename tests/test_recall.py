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


class RecallTest(GeciciTest):
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
