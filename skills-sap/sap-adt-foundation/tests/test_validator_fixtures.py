# -*- coding: utf-8 -*-
"""Validator bad/good fixture çiftleri — her validator için kontrol grubu.

Her çift `tests/fixtures/<validator>/{bad,good}/` altında bir mini proje köküdür; validator
alt süreç olarak, `AXET_SAP_PROJECT_DIR` o dizine bakacak şekilde, KENDİ normal kipinde koşar:

    bad/  → exit 1 + çıktıda `[İHLAL]`
    good/ → exit 0 + çıktıda `[İHLAL]` YOK

Neden ikisi birden: yalnız `good` koşmak hiçbir şey yapmayan bir validator'ı da "geçti" sayar;
yalnız `bad` koşmak her girdiye FAIL diyen birini yakalamaz. Çift olmadan ölçüm tek yönlüdür.

KAPSAM — bakılmayanlar: validator'ın bulgu METNİNİN doğruluğu (yalnız `[İHLAL]` varlığı) ·
run_review zincirine kayıtlı olup olmadığı (bkz. `sap-code-review/tests/test_checklists.py`) ·
fixture'ı olmayan validator'lar — `FIXTURESIZ` sözlüğünde tek tek gerekçelidir ve o sözlük
diskteki `check_*.py` kümesiyle test tarafından eşitlenir; "SIRADA" gerekçesi ÖLÇÜLMEDİ demektir.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import _helpers as H

FIXTURES = H.TESTS_DIR / "fixtures"
VALIDATOR_DIR = H.SCRIPTS / "sapadt" / "lib" / "validators"

# Fixture çifti bulunan validator'lar (argümansız, proje-geneli tarama kipini destekleyenler).
# İkinci alan = o validator'ın bulgu satırındaki damga. Damgalar ÖLÇÜLDÜ (2026-09-15), varsayılmadı:
# çoğu `[İHLAL]` basar, `check_dtel_creation_labels` ise `[BLOCKER]` başlığıyla toplu rapor verir.
# Tek bir damga varsaymak bu validator'da sahte-PASS üretirdi.
CIFTLI = [
    ("check_amdp_comment_apostrophe", "[İHLAL]"),
    ("check_bdef_backtick", "[İHLAL]"),
    ("check_decimal_write_to", "[İHLAL]"),
    ("check_dtel_creation_labels", "[BLOCKER]"),
    ("check_method_param_type_c", "[İHLAL]"),
]

# Bilinçli olarak fixture'sız kalanlar → GEREKÇESİ. Bu sözlük diskteki `check_*.py` kümesiyle
# test tarafından EŞİTLENİR (`test_kapsam_listesi_kodla_esit`): yeni bir validator eklenip buraya
# da CIFTLI'ye de yazılmazsa test kırmızı olur. Gerekçesiz "sırası geldikçe" kaydı serbest metin
# olarak dursaydı liste sessizce bayatlardı (bug gate 2026-09-15, MEDIUM — 22 validator'ın 12'si
# ne fixture'lı ne gerekçeliydi). Aynı eşitlik deseni: sap-code-review/tests/test_checklists.py.
FIXTURESIZ = {
    "check_abaplint": "dış abaplint/Node bağımlılığı; yokluğunda ÖLÇEMEDİM döner",
    "check_released_objects": "released_successors verisine ve canlı sisteme dayanır",
    "check_sap_active_version": "canlı ADT okuması ister (çevrimdışı fixture ile izole edilemez)",
    "check_sap_master_language": "yazma çağrısının payload'ını denetler, dosya taraması değil",
    "check_reuse_gate": "repo geneli yeniden-kullanım kıyası; bad/good proje kalıbına girmez",
    # Aşağıdakiler bad/good kalıbına UYAR ama fixture'ları henüz yazılmadı — sıraya alındı.
    # "ölçülmedi" demektir, "temiz" DEĞİL (çekirdek §7 KAPSAM BEYANI).
    "check_audit_fields_autofill": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_cds_currency_reference": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_deprecated_annotations": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_docu_itf_line_width": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_domain_output_length": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_rap_managed_etag": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_rap_readonly_consumption": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_sap_struct_consistency": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_standard_table_fields": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_struct_field_dtel_active": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_table_field_drop": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
    "check_window_function_compatibility": "SIRADA — fixture yazılmadı (ölçülmedi ≠ temiz)",
}


def _kos(validator: str, taraf: str):
    kok = FIXTURES / validator / taraf
    r = subprocess.run(
        [sys.executable, str(VALIDATOR_DIR / f"{validator}.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=H.clean_env({"AXET_SAP_PROJECT_DIR": str(kok)}),
        cwd=str(kok), timeout=120, stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class ValidatorFixtureCiftiTest(unittest.TestCase):
    def test_fixture_dizinleri_var(self) -> None:
        eksik = [f"{v}/{t}" for v, _d in CIFTLI for t in ("bad", "good")
                 if not (FIXTURES / v / t).is_dir()]
        self.assertEqual([], eksik, f"fixture dizini yok: {eksik}")

    def test_validator_dosyalari_var(self) -> None:
        eksik = [v for v, _d in CIFTLI if not (VALIDATOR_DIR / f"{v}.py").is_file()]
        self.assertEqual([], eksik, f"validator dosyası yok: {eksik}")

    def test_kapsam_listesi_kodla_esit(self) -> None:
        """Her `check_*.py` ya fixture'lı ya gerekçeli olmalı — beyan koda karşı eşitlenir.

        Bu olmadan liste sessizce bayatlar: yarın eklenen 23. validator için hiçbir şey FAIL
        etmezdi (bug gate 2026-09-15, MEDIUM).
        """
        diskte = {p.stem for p in VALIDATOR_DIR.glob("check_*.py")}
        self.assertGreater(len(diskte), 10, "validator dizini beklenenden boş — ölçüm geçersiz")
        beyan = {v for v, _d in CIFTLI} | set(FIXTURESIZ)
        beyansiz = sorted(diskte - beyan)
        hayalet = sorted(beyan - diskte)
        self.assertEqual([], beyansiz,
                         "şu validator'lar ne CIFTLI'de ne FIXTURESIZ'de: " + str(beyansiz))
        self.assertEqual([], hayalet,
                         "listede var ama diskte yok (silinmiş/yeniden adlandırılmış): "
                         + str(hayalet))
        gerekcesiz = sorted(v for v, g in FIXTURESIZ.items() if not (g or "").strip())
        self.assertEqual([], gerekcesiz, f"FIXTURESIZ gerekçesi boş: {gerekcesiz}")
        cakisma = sorted({v for v, _d in CIFTLI} & set(FIXTURESIZ))
        self.assertEqual([], cakisma, f"hem CIFTLI hem FIXTURESIZ: {cakisma}")

    def test_bad_fail_good_pass(self) -> None:
        sapma = []
        for v, damga in CIFTLI:
            kod_b, cikti_b = _kos(v, "bad")
            ok_b = kod_b == 1 and damga in cikti_b
            H.kaydet(f"{v}: bad → FAIL", f"exit 1 + {damga}",
                     f"exit {kod_b}, {damga} {'var' if damga in cikti_b else 'YOK'}", ok_b)
            if not ok_b:
                sapma.append(f"{v}/bad: exit={kod_b} damga={damga in cikti_b}")

            kod_g, cikti_g = _kos(v, "good")
            ok_g = kod_g == 0 and damga not in cikti_g
            H.kaydet(f"{v}: good → PASS", f"exit 0, {damga} yok",
                     f"exit {kod_g}, {damga} {'VAR' if damga in cikti_g else 'yok'}", ok_g)
            if not ok_g:
                sapma.append(f"{v}/good: exit={kod_g} damga={damga in cikti_g}")

        self.assertEqual([], sapma, "bad/good çifti beklenenin tersini verdi:\n  "
                                    + "\n  ".join(sapma))


if __name__ == "__main__":
    unittest.main()
