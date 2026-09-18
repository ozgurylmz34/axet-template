# -*- coding: utf-8 -*-
"""check_intake_signoff.py fixture testi (kaynak çekirdekteki alan-doluluğu fixture'ının uyarlaması).

P* = kapıyı GEÇMEMELİ (şablon kopyası / kısmi doldurma) · K* = kontrol grubu (eskiden de düşen)
N* = yanlış-pozitif çapaları (meşru artefakt GEÇMELİ; düşerse kapı aşırı sıkılaşmıştır).
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

GATE = H.INTAKE_SCRIPTS / "check_intake_signoff.py"

P1 = """# INTAKE — <kısa-ad>  (tarih)
- Modül / iş-tipi / KAPSAM:
- İstenen (özet):
- Çıkan domain-konuları:
- Etkilenen objeler (canlı-doğrulanmış):
- Prior-art: yok
- Kabul kriterleri (EARS):
- Açık kararlar / riskler:
- MUTABAKAT: [x] kullanıcı sign-off
"""
P2 = """# INTAKE — <kısa-ad>  (tarih)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2  (gerekçe: ...)
- İstenen (özet): yeni rapor
- Çıkan domain-konuları: [konu → araştırma özeti (a/b/c eksen)]
- Etkilenen objeler (canlı-doğrulanmış): [obje → reuse/yeni/değişir → blast-radius]
- Prior-art: yok
- Kabul kriterleri (EARS): "<olay> olduğunda sistem <sonuç> yapmalı" / "<durum> ise ..."
- MUTABAKAT: [x] kullanıcı sign-off
"""
P3 = """# INTAKE — sevk raporu  (2026-08-01)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2 (gerekçe: yeni ekran + 2 yeni CDS)
- Etkilenen objeler (canlı-doğrulanmış):
- Prior-art: bulundu: ZDEMO1_I_ORDER benzeri rapor (canlı doğrulandı)
- Kabul kriterleri (EARS): kullanıcı kaydettiğinde sistem sevk kalemini kilitlemeli
- MUTABAKAT: [x] kullanıcı sign-off
"""
K1 = """# INTAKE — sevk raporu  (2026-08-01)
- İstenen (özet): yeni sevk raporu
- Prior-art: yok
- MUTABAKAT: [x] kullanıcı sign-off
"""
K2 = """# INTAKE — sevk raporu  (2026-08-01)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2 (gerekçe: yeni ekran + 2 yeni CDS)
- Etkilenen objeler (canlı-doğrulanmış): ZDEMO1_I_ORDER (değişir, 3 tüketici), ZDEMO1_C_ORDER (yeni)
- Prior-art: bulundu: sipariş raporu (canlı doğrulandı)
- Kabul kriterleri (EARS): kullanıcı kaydettiğinde sistem sevk kalemini kilitlemeli
- MUTABAKAT: [ ] kullanıcı sign-off
"""
N1 = """# INTAKE — sevk emri kalem raporu  (2026-08-01)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2  (gerekçe: yeni ekran + 2 yeni CDS + UI5 app)
- İstenen (özet): sevk emri kalemlerini filtreli grid'de göster
- Çıkan domain-konuları: sevk emri yaşam döngüsü → RAP projeksiyonu üzerinden okunur
- Etkilenen objeler (canlı-doğrulanmış): ZDEMO1_I_ORDER (reuse), ZDEMO1_C_ORDER (yeni), ZCL_DEMO1_RPT (yeni)
- Prior-art: bulundu: sipariş raporu (adt_get ile canlı doğrulandı)
- Kabul kriterleri (EARS): kullanıcı filtre uyguladığında sistem yalnız açık kalemleri listelemeli
- Açık kararlar / riskler: ortak value-help mi lokal mi (kullanıcıya soruldu)
- MUTABAKAT: [x] kullanıcı sign-off
"""
N2 = """# INTAKE — sevk emri kalem raporu  (2026-08-01)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2 (gerekçe: yeni ekran)
- Etkilenen objeler (canlı-doğrulanmış):
    ZDEMO1_I_ORDER  → reuse → 3 tüketici (canlı where-used)
    ZDEMO1_C_ORDER  → yeni  → tüketici yok
- Prior-art: bulundu: sipariş raporu
- Kabul kriterleri (EARS):
    kullanıcı kaydettiğinde sistem sevk kalemini kilitlemeli
- MUTABAKAT: [x] kullanıcı sign-off
"""
N3 = """# INTAKE — sevk emri  (2026-08-01)
* KAPSAM: S2 — yeni sprint
* Etkilenen objeler: ZDEMO1_I_ORDER (değişir)
* Prior-art: yok
* Kabul kriterleri (EARS): sipariş kaydedildiğinde sistem kalem üretmeli
* MUTABAKAT: [X] sign-off
"""
N4 = """# INTAKE — sevk emri  (2026-08-01)
- KAPSAM: S2 (gerekçe: yeni obje seti)
- Etkilenen objeler (canlı-doğrulanmış): ZDEMO1_T_ORDER (yeni tablo)
- Prior-art: yok
- Kabul kriterleri (EARS): kayıt sırasında sistem zorunlu alanları doğrulamalı
- MUTABAKAT: [x] kullanıcı sign-off
"""
N5 = """# INTAKE — başlık biçimli artefakt  (2026-08-20)
## 1. KAPSAM
S2 — yeni servis + iki CDS
## 3. ETKİLENEN / İLGİLİ OBJELER — CANLI DOĞRULANDI
ZDEMO1_I_ORDER (değişir)
## 4. Prior-art
`notes/RESEARCH-siparis.md`
## 5. Kabul kriterleri
kullanıcı kaydettiğinde sistem kalemi kilitlemeli
- MUTABAKAT: [x] kullanıcı sign-off
"""

# P6: sap-intake-triage/references/s2-artifact-schema.md şablonu (açılı yer-tutucular) doldurulmadan + [x]
P6 = """# INTAKE — <kısa-ad>  (<tarih>)
- Modül / iş-tipi / KAPSAM: <modül> / <iş tipi> / S2  (gerekçe: <tek cümle>)
- İstenen (özet): <kullanıcının talebi, kendi cümlelerinle>
- Çıkan domain-konuları: <konu → araştırma özeti (a) domain / (b) canlı sistem / (c) hafıza>
- Etkilenen objeler (canlı-doğrulanmış): <obje → reuse | yeni | değişir → blast-radius → doğrulama kanıtı>
- Prior-art: <bulundu: `<yol ya da kayıt>`  |  yok (arandı: <nerede>)>
- Kabul kriterleri (EARS): <"<olay> olduğunda sistem <sonuç> yapmalı" …>
- Açık kararlar / riskler: <karar bekleyenler, riskler>
- MUTABAKAT: [x] kullanıcı sign-off
"""
# N6 (FP çapası): içerikte karşılaştırma işleci (`<>`, `< … >`) — açılı yer-tutucu SAYILMAMALI
N6 = """# INTAKE — tutar kontrolü  (2026-09-13)
- KAPSAM: S2 (gerekçe: yeni doğrulama + rapor)
- Etkilenen objeler (canlı-doğrulanmış): ZDEMO1_I_ORDER (değişir; filtre tutar <> 0)
- Prior-art: yok (arandı: paket ve hafıza)
- Kabul kriterleri (EARS): tutar < 0 ve iskonto > 10 olduğunda sistem kaydı reddetmeli
- MUTABAKAT: [x] kullanıcı sign-off
"""

SENARYOLAR = [
    ("P6", P6, True, "P6 skill şablonu (<açılı> yer-tutucu) + [x] → red"),
    ("N6", N6, False, "N6 içerikte <> / < … > işleci → geçer"),
    ("P1", P1, True, "P1 BOŞ şablon + [x] → red"),
    ("P2", P2, True, "P2 şablon yer-tutucuları + [x] → red"),
    ("P3", P3, True, "P3 tek alan boş → red"),
    ("K1", K1, True, "K1 KONTROL alan başlığı yok → red"),
    ("K2", K2, True, "K2 KONTROL MUTABAKAT işaretsiz → red"),
    ("N1", N1, False, "N1 doldurulmuş artefakt → geçer"),
    ("N2", N2, False, "N2 çok satırlı değer → geçer"),
    ("N3", N3, False, "N3 farklı madde işareti/yazım → geçer"),
    ("N4", N4, False, "N4 kısa ama meşru 'Prior-art: yok' → geçer"),
    ("N5", N5, False, "N5 markdown başlık biçimi → geçer"),
]


class IntakeSignoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="axet_intake_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fixture(self):
        for kod, icerik, red_beklenir, ad in SENARYOLAR:
            p = self.tmp / f"{kod}.md"
            p.write_text(icerik, encoding="utf-8")
            r = subprocess.run([sys.executable, str(GATE), str(p)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60, env=H.clean_env())
            ok = (r.returncode != 0) == red_beklenir
            H.kaydet(f"10 intake {ad}", f"exit {'1' if red_beklenir else '0'}", f"exit {r.returncode}", ok)
            self.assertTrue(ok, f"{ad}: exit={r.returncode}\n{r.stdout}{r.stderr}")

    def test_denetle_alan_adiyla(self):
        spec = importlib.util.spec_from_file_location("_intake_t", str(GATE))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        p = self.tmp / "P3d.md"
        p.write_text(P3, encoding="utf-8")
        s = mod.denetle(p)
        ok = (not s["ok"]) and s["bos_alanlar"] == ["etkilenen objeler"]
        H.kaydet("10 intake denetle() boş alan ADIYLA (P3)", "bos_alanlar=['etkilenen objeler']",
                 f"ok={s['ok']} bos={s['bos_alanlar']}", ok)
        self.assertTrue(ok, s)


if __name__ == "__main__":
    unittest.main()
