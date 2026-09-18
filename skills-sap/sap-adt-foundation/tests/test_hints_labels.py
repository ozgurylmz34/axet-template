# -*- coding: utf-8 -*-
"""checklist_hint · known_errors_hint (sapadt/hints.py) + DTEL etiket uzunluğu ön kontrolü (2026-09-13). Ağ yok."""
from __future__ import annotations

import ast
import re
import sys
import unittest

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))


class Ipuclari(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sapadt import hints
        cls.h = hints

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"İPUCU {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def test_01_grup_eslemesi_kaynak_kanca_ile_ayni(self):
        beklenen = {"ddls": "cds", "cds": "cds", "view": "cds", "bdef": "rap", "srvd": "rap", "srvb": "rap",
                    "behaviordefinition": "rap", "servicedefinition": "rap", "doma": "ddic-dd", "dtel": "ddic-dd",
                    "struct": "ddic-st", "tabl": "ddic-st", "stru": "ddic-st", "prog": "classic", "program": "classic",
                    "class": "class", "fugr": "fugr", "func": "fugr", "msag": "msag", "enqu": "enqu", "xyz": None, "": None}
        gercek = {t: self.h.tip_grubu(t) for t in beklenen}
        self.kaydet("01 tip → grup (kaynak kanca _checklist sırası + aXet ekleri)", "eşleşme", gercek, gercek == beklenen)

    def test_02_checklist_hint_araclar(self):
        dd = self.h.checklist_hint("adt_dtel_create", {"name": "ZCA000_DT"})
        pub = self.h.checklist_hint("adt_publish_service", {"name": "ZCA000_UI_SB"})
        push = self.h.checklist_hint("adt_push_source", {"object_type": "ddls"})
        yok = self.h.checklist_hint("adt_activate", {"object_type": "xyz"})
        pub_ui5 = [r for r in pub["refs"] if r["path"].endswith("sap-ui5-fiori/SKILL.md")]
        ok = (dd["group"] == "ddic-dd" and pub["group"] == "rap" and len(pub_ui5) == 1
              and pub_ui5[0]["status"] in ("var", "yazılıyor")
              and push["group"] == "cds" and any(r["path"].endswith("sap-code-review/SKILL.md") for r in push["refs"])
              and yok is None)
        self.kaydet("02 dtel_create→ddic-dd · publish→rap+ui5 · push ddls→cds+code-review · bilinmeyen→None",
                    "doğru", f"{dd['group']} {pub['group']} {push['group']} {yok}", ok)

    def test_03_tum_referans_dosyalari_var(self):
        eksik = []
        for rel in {r for g in self.h.GRUP_REFERANSLARI.values() for r in g} | \
                {r for g in self.h.ARAC_EK_REFERANS.values() for r in g}:
            if not (H.SKILLS_SAP / rel).is_file() and rel not in self.h.YAZILIYOR:
                eksik.append(rel)
        self.kaydet("03 checklist hedef dosyaları mevcut (yazılıyor listesi hariç)", "0 eksik", eksik, not eksik)

    def test_04_known_errors_kod_ve_metin(self):
        kilit = self.h.known_errors_hint("adt_set_description", {"error": "lock_conflict"}, ("lock_conflict", "x"), 1)
        e043 = self.h.known_errors_hint("adt_set_description", {"error": "put_precondition_failed",
                                        "sap_body": "SADT_RESOURCE 043 ..."}, ("put_precondition_failed", "412"), 1)
        klasik = self.h.known_errors_hint("adt_push_source", {"error": "sap_error",
                                          "message": "[400] OO_SOURCE_BASED 012 unknown comments"}, ("sap_error", ""), 1)
        fm = self.h.known_errors_hint("adt_push_source", {"error": "sap_error",
                                      "message": "400 FUNC_ADT 015 Parameter P declares no type"}, ("sap_error", ""), 1)
        basari = self.h.known_errors_hint("adt_get", {"ok": True, "message": "HTTP 412 sonra 200; EU 510 yok"}, None, 0)
        bos = self.h.known_errors_hint("adt_get", {"error": "zzz"}, ("zzz", "hiç"), 1)
        kapi = self.h.known_errors_hint("adt_post_shell", None, ("ADR_0005_A", "std"), 2)
        ok = (any("K-07" in r["section"] for r in kilit["refs"])
              and any("K-19" in r["section"] for r in e043["refs"])
              and any(r["path"].endswith("known-errors-classic.md") and "classes.md §3" in r["section"] for r in klasik["refs"])
              and "FUNC_ADT 015" in fm.get("sap_message_keys", []) and basari is None
              and bos is not None and all(r["section"] == "İndeks" for r in bos["refs"])
              and kapi["refs"][0]["path"].endswith("sap-adt-foundation/SKILL.md"))
        self.kaydet("04 lock_conflict→K-07 · SADT_RESOURCE 043→K-19 · OO_SOURCE_BASED 012→classes §3 · FUNC_ADT 015 anahtar · "
                    "exit 0 None · eşleşmesiz → indeks · kapı reddi → SKILL §4", "hepsi doğru",
                    [kilit["refs"][0]["section"], e043["refs"][0]["section"], klasik["refs"][0]["section"]], ok)

    def test_05_referans_bolumleri_var(self):
        eksik = []
        kurallar = [(d, b) for _k, d, b, _n in self.h.KOD_KURALLARI] + [(d, b) for _r, d, b, _n in self.h.METIN_KURALLARI]
        for dosya, bolum in kurallar:
            yol = H.SKILLS_SAP / dosya
            if not yol.is_file():
                eksik.append(f"{dosya} (dosya yok)")
                continue
            metin = yol.read_text(encoding="utf-8")
            for k in re.findall(r"K-\d\d", bolum):
                if f"## {k}" not in metin and f"### {k}" not in metin:
                    eksik.append(f"{dosya}:{k}")
            m = re.match(r"(\w[\w-]*\.md) §(\d+(?:\.\d+)?)", bolum)
            if m:
                hedef = (yol.parent / m.group(1)).read_text(encoding="utf-8")
                if not re.search(rf"^#+ {re.escape(m.group(2))}[.\s]", hedef, re.M):
                    eksik.append(f"{m.group(1)} §{m.group(2)}")
            m2 = re.match(r"§(\d+(?:\.\d+)?) (.+)", bolum)
            if m2 and not re.search(rf"^#+ {re.escape(m2.group(1))}\.? {re.escape(m2.group(2).split(' (')[0])}", metin, re.M):
                eksik.append(f"{dosya} §{m2.group(1)} {m2.group(2)}")
        self.kaydet("05 known_errors_hint bölüm başlıkları hedef dosyalarda var", "0 eksik", eksik, not eksik)


class DtelEtiketUzunlugu(unittest.TestCase):
    def test_01_sinirlar_validator_ile_ayni(self):
        from sapadt.guardrails import DTEL_LABEL_MAX
        yol = H.SCRIPTS / "sapadt" / "lib" / "validators" / "check_dtel_creation_labels.py"
        m = re.search(r"^_MAX = (\{.*\})$", yol.read_text(encoding="utf-8"), re.M)
        kaynak = ast.literal_eval(m.group(1)) if m else None
        H.kaydet("ETİKET 01 DTEL_LABEL_MAX == validator _MAX", str(kaynak), str(DTEL_LABEL_MAX), kaynak == DTEL_LABEL_MAX)
        self.assertEqual(kaynak, DTEL_LABEL_MAX)

    def test_02_sinir_davranisi(self):
        from sapadt.guardrails import GuardrailViolation, require_label_lengths
        tam = {"short": "ğ" * 10, "medium": "b" * 20, "long": "c" * 40, "heading": "  " + "d" * 55 + "  "}
        require_label_lengths(tam)          # sınırda + kenar boşluğu kırpılır → geçer
        sonuc = {}
        for alan, n in (("short", 11), ("medium", 21), ("long", 41), ("heading", 56)):
            try:
                require_label_lengths({**tam, alan: "x" * n})
                sonuc[alan] = "geçti"
            except GuardrailViolation as gv:
                sonuc[alan] = gv.as_dict().get("code")
        ok = set(sonuc.values()) == {"ADR_0005_D"}
        H.kaydet("ETİKET 02 sınır+1 her alan → ADR_0005_D; sınırda (çok baytlı, boşluklu) geçer", "ADR_0005_D × 4",
                 str(sonuc), ok)
        self.assertTrue(ok, sonuc)


if __name__ == "__main__":
    unittest.main()
