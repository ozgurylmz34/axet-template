# -*- coding: utf-8 -*-
"""CLI + yazma kapısı senaryoları (alt süreç; çevrimdışı).

Kapı testlerinde beklenen exit 2 + doğru `error.code`, kontrolün AĞDAN ÖNCE çalıştığını kanıtlar:
ağa gidilseydi sahte host (127.0.0.1:9) bağlantı hatası → exit 1 üretirdi. Kontrol grubu olarak
her kümede en az bir "kapıdan geçen" çağrı exit 1 (bağlantı hatası) vermelidir.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import _helpers as H

ROOT: Path
HOME_OPT: Path
HOME_NO: Path

S1 = ["--sap-write", "--scope", "S1", "--reason", "Test gerekçesi: kapı sırası doğrulaması"]
TR = "TESTK900001"


def setUpModule():
    global ROOT, HOME_OPT, HOME_NO
    ROOT = Path(tempfile.mkdtemp(prefix="axet_sapadt_"))
    HOME_OPT = H.build_home(ROOT, optin=True)
    HOME_NO = H.build_home(ROOT, optin=False)


def tearDownModule():
    shutil.rmtree(ROOT, ignore_errors=True)


_sayac = [0]


def proje(**kw) -> Path:
    _sayac[0] += 1
    return H.make_project(ROOT / "projeler", f"p{_sayac[0]}", **kw)


def post_shell_args(name="ZAXET_TEST_OBJ", transport=TR):
    return {"object_type": "class", "name": name, "package": "$TMP",
            "transport": transport, "description": "Test sınıfı"}


class Kapi(unittest.TestCase):
    def kos(self, ad, argv, *, home=None, project=None, env=None, rc=None, code=None):
        rc_g, data, out, err = H.run_cli(home or HOME_OPT, argv, project=project, env_extra=env)
        kod_g = ((data or {}).get("error") or {}).get("code") if data else "JSON-YOK"
        beklenen = f"exit {rc}" + (f" · {code}" if code else "")
        gercek = f"exit {rc_g} · {kod_g}"
        ok = (rc is None or rc_g == rc) and (code is None or kod_g == code) and data is not None
        H.kaydet(ad, beklenen, gercek, ok)
        self.assertIsNotNone(data, f"{ad}: stdout tek JSON değil:\n{out}\n{err}")
        if rc is not None:
            self.assertEqual(rc_g, rc, f"{ad}: {out}\n{err[-800:]}")
        if code is not None:
            self.assertEqual(kod_g, code, f"{ad}: {out}")
        for alan in ("ok", "tool", "class", "result", "error", "gate"):
            self.assertIn(alan, data, f"{ad}: sözleşme alanı eksik: {alan}")
        return data, out, err

    # ── 1. --list ────────────────────────────────────────────────────────────────────
    def test_01_list(self):
        data, _o, _e = self.kos("1 --list", ["--list"], rc=0)
        self.assertNotIn("HATIRLATMA", _e, "K-O① kontrol grubu: başarılı çağrıda hatırlatma basılmaz")
        tools = {t["name"]: t for t in data["result"]["tools"]}
        okuma = sorted(n for n, t in tools.items() if t["class"] == "read")
        yazma = sorted(n for n, t in tools.items() if t["class"] == "write")
        H.kaydet("1a --list okuma sayısı", "24", str(len(okuma)), len(okuma) == 24)
        self.assertEqual(len(okuma), 24, okuma)
        for ad in ("adt_revisions", "adt_system_info", "adt_object_structure", "sap_doctor"):
            self.assertEqual((tools[ad]["class"], tools[ad]["available_on"]), ("read", ["all"]), ad)
        sd = tools["adt_set_description"]
        ok_sd = (sd["available_on"] == ["s4_private"] and sd.get("requires_transport") is True
                 and {a["name"] for a in sd["args"]} == {"name", "object_type", "description", "transport"})
        H.kaydet("1e adt_set_description: write · s4_private · transport · argümanlar", "hepsi doğru",
                 json.dumps({k: sd.get(k) for k in ("class", "available_on", "requires_transport")}), ok_sd)
        self.assertTrue(ok_sd, sd)
        for ad in ("adt_syntax_check", "adt_classrun"):
            H.kaydet(f"1b {ad} sınıfı", "write", tools[ad]["class"], tools[ad]["class"] == "write")
            self.assertEqual(tools[ad]["class"], "write")
        self.assertIn("write_when", tools["adt_unit_run"])
        self.assertEqual(set(yazma), {"adt_activate", "adt_classrun", "adt_delete", "adt_domain_create",
                                      "adt_dtel_create", "adt_post_shell", "adt_publish_service",
                                      "adt_push_source", "adt_struct_create", "adt_syntax_check",
                                      "adt_screen_generate", "adt_msgclass_write", "adt_set_description",
                                      "adt_table_create", "adt_ttyp_create", "adt_textpool_write"})
        mw = tools["adt_msgclass_write"]
        ok_mw = (mw["available_on"] == ["s4_private"] and mw.get("requires_transport") is True
                 and {a["name"] for a in mw["args"]} == {"name", "transport", "messages", "delete_numbers",
                                                         "allow_overwrite", "package"})
        H.kaydet("1d adt_msgclass_write: write · s4_private · transport · argümanlar", "hepsi doğru",
                 json.dumps({k: mw.get(k) for k in ("class", "available_on", "requires_transport")}), ok_mw)
        self.assertTrue(ok_mw, mw)
        ekran = tools["adt_screen_generate"]
        ok_ekran = (ekran["class"] == "write" and ekran["available_on"] == ["ecc", "s4_private"]
                    and ekran.get("requires_transport") is True and "READ" in ekran.get("requires_transport_when", ""))
        H.kaydet("1c adt_screen_generate: write · ecc/s4_private · transport (READ hariç)", "hepsi doğru",
                 json.dumps({k: ekran.get(k) for k in ("class", "available_on", "requires_transport_when")}), ok_ekran)
        self.assertTrue(ok_ekran, ekran)
        kisit = tools["adt_post_shell"].get("object_type_available_on") or {}
        self.assertEqual(kisit.get("functiongroup"), ["ecc", "s4_private"])
        self.assertEqual(tools["adt_push_source"].get("object_type_available_on"), kisit)

    # ── 2. sap-project.json ─────────────────────────────────────────────────────────
    def test_02_sap_project(self):
        p = proje(sap_project=None)
        self.kos("2a ping (sap-project.json yok)", ["ping"], project=p, rc=0)
        self.kos("2b adt_get (sap-project.json yok)", ["adt_get", "--args-json", '{"name":"ZX"}'],
                 project=p, rc=2, code="sap_project_missing")
        p2 = proje(sap_project="{bozuk json")
        self.kos("2c adt_get (bozuk JSON)", ["adt_get", "--args-json", '{"name":"ZX"}'],
                 project=p2, rc=2, code="sap_project_invalid")
        p3 = proje(sap_project={"sap_profile": "uydurma", "master_language": "TR"})
        self.kos("2d adt_get (enum-dışı profil)", ["adt_get", "--args-json", '{"name":"ZX"}'],
                 project=p3, rc=2, code="sap_project_invalid")
        p4 = proje(sap_project=None)
        self.kos("2e yazma aracı (sap-project.json yok)",
                 ["adt_post_shell", "--args-json", json.dumps(post_shell_args()), *S1],
                 project=p4, rc=2, code="sap_project_missing")

    # ── 3. yazma kapısı 1-3 ─────────────────────────────────────────────────────────
    def test_03_optin_flag_tier(self):
        a = ["adt_post_shell", "--args-json", json.dumps(post_shell_args())]
        p = proje()
        self.kos("3a global opt-in yok", a + S1, home=HOME_NO, project=p, rc=2, code="write_not_optin_global")
        self.kos("3b opt-in var, --sap-write yok", a + S1[1:], project=p, rc=2, code="write_flag_missing")
        p_yok = proje(tier_lines=())
        d, _o, _e = self.kos("3c tier satırı yok (+env ADT_SAP_TIER=DEV)", a + S1, project=p_yok,
                             env={"ADT_SAP_TIER": "DEV"}, rc=2, code="tier_not_writable")
        self.assertEqual(d["gate"]["tier"], "UNKNOWN")
        p_cak = proje(tier_lines=("ADT_SAP_TIER=DEV", "ADT_SAP_TIER=PRD"))
        d, _o, _e = self.kos("3d çakışan iki tier satırı", a + S1, project=p_cak, rc=2, code="tier_not_writable")
        self.assertEqual(d["gate"]["tier"], "UNKNOWN")
        p_onek = proje(tier_lines=("ADT_SAP_TIER_OLD=DEV",))
        self.kos("3e önek satırı (ADT_SAP_TIER_OLD=DEV)", a + S1, project=p_onek, rc=2, code="tier_not_writable")
        p_qa = proje(tier_lines=("ADT_SAP_TIER=QA",))
        d, _o, _e = self.kos("3f tier QA", a + S1, project=p_qa, rc=2, code="tier_not_writable")
        self.assertEqual(d["gate"]["tier"], "QA")

    # ── 4. kapsam beyanı ─────────────────────────────────────────────────────────────
    def test_04_scope(self):
        a = ["adt_post_shell", "--args-json", json.dumps(post_shell_args(name="MARA"))]
        p = proje()
        self.kos("4a --scope yok", a + ["--sap-write"], project=p, rc=2, code="scope_missing")
        self.kos("4b --scope S3", a + ["--sap-write", "--scope", "S3", "--reason", "x" * 20],
                 project=p, rc=2, code="scope_invalid")
        self.kos("4c S1 gerekçesiz", a + ["--sap-write", "--scope", "S1"], project=p, rc=2, code="reason_missing")
        self.kos("4d S1 gerekçe <15 karakter", a + ["--sap-write", "--scope", "S1", "--reason", "kısa"],
                 project=p, rc=2, code="reason_missing")
        self.kos("4e S2 intake'siz", a + ["--sap-write", "--scope", "S2"], project=p, rc=2, code="intake_missing")
        intake_dir = p / ".axet-code" / "intake"
        intake_dir.mkdir(parents=True)
        (intake_dir / "imzasiz.md").write_text(INTAKE_GECERLI.replace("[x]", "[ ]"), encoding="utf-8")
        d, _o, _e = self.kos("4f S2 mutabakatsız intake",
                             a + ["--sap-write", "--scope", "S2", "--intake", ".axet-code/intake/imzasiz.md"],
                             project=p, rc=2, code="intake_invalid")
        self.assertIn("sign-off", d["error"]["message"])
        (p / "disarida.md").write_text(INTAKE_GECERLI, encoding="utf-8")
        self.kos("4g S2 intake klasör dışında",
                 a + ["--sap-write", "--scope", "S2", "--intake", ".axet-code/intake/../../disarida.md"],
                 project=p, rc=2, code="intake_invalid")
        (intake_dir / "gecerli.md").write_text(INTAKE_GECERLI, encoding="utf-8")
        self.kos("4h S2 geçerli intake → sonraki guard (namespace)",
                 a + ["--sap-write", "--scope", "S2", "--intake", ".axet-code/intake/gecerli.md"],
                 project=p, rc=2, code="ADR_0005_A")

    # ── 5-6. araç guard'ları (ağdan önce) ───────────────────────────────────────────
    def test_05_namespace_all_write_tools(self):
        p = proje()
        std = {
            "adt_post_shell": post_shell_args(name="MARA"),
            "adt_push_source": {"name": "MARA", "object_type": "class", "source": "x", "transport": TR},
            "adt_delete": {"name": "MARA", "object_type": "tabl", "transport": TR},
            "adt_activate": {"name": "MARA", "object_type": "class"},
            "adt_publish_service": {"name": "API_TEST_SRV"},
            "adt_classrun": {"name": "CL_ABAP_TYPEDESCR"},
            "adt_domain_create": {"name": "MATNR", "datatype": "CHAR", "length": 10, "description": "x",
                                  "package": "$TMP", "transport": TR},
            "adt_dtel_create": {"name": "MATNR", "domain_name": "MATNR", "description": "x", "package": "$TMP",
                                "transport": TR, "short_label": "a", "medium_label": "b",
                                "long_label": "c", "heading_label": "d"},
            "adt_struct_create": {"name": "BAPIRET2", "fields": [{"name": "F", "type": "char10"}],
                                  "description": "x", "package": "$TMP", "transport": TR},
            "adt_syntax_check": {"name": "SAPMV45A", "object_type": "program"},
            "adt_screen_generate": {"fm_name": "ZAXET_FM_SCREEN_GEN", "program": "SAPMV45A",
                                    "title": "Liste", "transport": TR},
            "adt_msgclass_write": {"name": "VL", "transport": TR,
                                   "messages": [{"no": "001", "text": "Standart sınıfa yazılmaz"}]},
            "adt_set_description": {"name": "MARA", "object_type": "class", "description": "Standart", "transport": TR},
            "adt_table_create": {"name": "MARA", "description": "Standart", "package": "$TMP", "transport": TR,
                                 "fields": [{"name": "MANDT", "type": "mandt", "key": True}]},
            "adt_ttyp_create": {"name": "BAPIRET2_T", "description": "Standart", "package": "$TMP",
                                "transport": TR, "row_type": "BAPIRET2"},
            "adt_textpool_write": {"name": "SAPMV45A", "transport": TR,
                                   "symbols": [{"key": "B01", "text": "Standart"}]},
        }
        _rc, _d, out, _e = H.run_cli(HOME_OPT, ["--list"])
        yazma = {t["name"] for t in json.loads(out)["result"]["tools"] if t["class"] == "write"}
        self.assertEqual(yazma, set(std), "Yeni yazma aracı namespace testine eklenmeli")
        for ad, args in std.items():
            self.kos(f"5 {ad} standart ad", [ad, "--args-json", json.dumps(args), *S1],
                     project=p, rc=2, code="ADR_0005_A")
        self.kos("5 adt_activate also[] standart ad",
                 ["adt_activate", "--args-json", json.dumps({"name": "ZAXET_X", "object_type": "class",
                                                             "also": [{"name": "MARA", "object_type": "tabl"}]}), *S1],
                 project=p, rc=2, code="ADR_0005_A")
        self.kos("5 adt_unit_run allow_risky_tests=true (yazma) standart ad",
                 ["adt_unit_run", "--args-json", json.dumps({"name": "CL_X", "allow_risky_tests": True}), *S1],
                 project=p, rc=2, code="ADR_0005_A")
        self.kos("6a adt_delete standart obje", ["adt_delete", "--args-json",
                 json.dumps({"name": "VBAK", "object_type": "tabl"}), *S1], project=p, rc=2, code="ADR_0005_A")
        _d, _o, err = self.kos("6b transport'suz post_shell (Z paketi)", ["adt_post_shell", "--args-json",
                               json.dumps({**post_shell_args(transport=""), "package": "ZAXET_PKG"}), *S1],
                               project=p, rc=2, code="ADR_0005_C")
        # K-O① (2026-09-18): kapı reddinde "kuralı değiştirme" hatırlatması YALNIZ stderr'e (stdout tek JSON)
        self.assertIn("HATIRLATMA: kapı reddini aşmak için", err)
        # K-M (2026-09-18): `$TMP` TAM eşleşmede transport istenmez; benzer adlar istisna DEĞİL
        for paket in ("$TMPX", "$tmp", " $TMP"):
            self.kos(f"6b K-M − post_shell paket={paket!r}", ["adt_post_shell", "--args-json",
                     json.dumps({**post_shell_args(transport=""), "package": paket}), *S1],
                     project=p, rc=2, code="ADR_0005_C")
        for arac, args in (("adt_post_shell", post_shell_args(transport="")),
                           ("adt_domain_create", {"name": "ZAXET_D", "datatype": "CHAR", "length": 10,
                                                  "description": "Alan", "package": "$TMP", "transport": ""})):
            d, _o, _e = self.kos(f"6b K-M + {arac} $TMP transport'suz", [arac, "--args-json",
                                 json.dumps(args), *S1], project=p)
            self.assertNotEqual(((d or {}).get("error") or {}).get("code"), "ADR_0005_C",
                                f"{arac} $TMP'de hâlâ transport istiyor: {d}")
        self.kos("6b K-M − adt_struct_create $TMP (istisna DIŞI)", ["adt_struct_create", "--args-json",
                 json.dumps({"name": "ZAXET_S", "fields": [{"name": "F", "type": "char10"}],
                             "description": "Yapı", "package": "$TMP", "transport": ""}), *S1],
                 project=p, rc=2, code="ADR_0005_C")

    def test_06_language_env_reviewer(self):
        p_en = proje(language="EN")
        self.kos("6c bağlantı dili EN ≠ master TR", ["adt_activate", "--args-json",
                 json.dumps({"name": "ZAXET_X"}), *S1], project=p_en, rc=2, code="language_mismatch")
        p = proje()
        self.kos("6d env ADT_SAP_URL .conn_adt'yi eziyor (yazma)", ["adt_activate", "--args-json",
                 json.dumps({"name": "ZAXET_X"}), *S1], project=p, env={"ADT_SAP_URL": "http://127.0.0.2:9"},
                 rc=2, code="conn_env_mismatch")
        self.kos("6e env ADT_SAP_URL .conn_adt'yi eziyor (okuma)", ["adt_get", "--args-json",
                 json.dumps({"name": "ZAXET_X"})], project=p, env={"ADT_SAP_URL": "http://127.0.0.2:9"},
                 rc=2, code="conn_env_mismatch")
        self.kos("6f skip_reviewer=true", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZAXET_X", "object_type": "ddls", "source": "x", "skip_reviewer": True}), *S1],
                 project=p, rc=2, code="reviewer_bypass_forbidden")
        kaynak = ("define view entity ZAXET_X as select from t000 {\n"
                  "  key mandt,\n  row_number() over (partition by mandt order by mandt) as rn\n}\n")
        d, _o, _e = self.kos("6g reviewer BLOCKER (window function)", ["adt_push_source", "--args-json",
                             json.dumps({"name": "ZAXET_X", "object_type": "ddls", "source": kaynak}), *S1],
                             project=p, rc=2, code="reviewer_blocker")
        self.assertTrue(d["gate"]["review"].startswith("BLOCKER"), d["gate"])
        self.kos("6g2 reviewer BLOCKER + ack_drop → yine exit 2", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZAXET_X", "object_type": "ddls", "source": kaynak, "ack_drop": "rn"}), *S1],
                 project=p, rc=2, code="reviewer_bypass_forbidden")
        tablo = ("@EndUserText.label : 'Test'\ndefine table zaxet_t {\n"
                 "  key mandt : mandt not null;\n  key id : zaxet_e_id not null;\n}\n")
        self.kos("6g3 tablo push + ack_drop (DROP onayı) → exit 2", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZAXET_T", "object_type": "tabl", "source": tablo, "ack_drop": "amount"}), *S1],
                 project=p, rc=2, code="reviewer_bypass_forbidden")
        d, _o, _e = self.kos("6h KONTROL: tüm kapılar açık → ağa gider (bağlantı hatası)",
                             ["adt_activate", "--args-json", json.dumps({"name": "ZAXET_X"}), *S1],
                             project=p, rc=1)
        self.assertIn("NONE", d["gate"]["review"])
        p_btp = proje(sap_project={"sap_profile": "btp_abap", "master_language": "TR"})
        self.kos("6i btp_abap + adt_transport_list", ["adt_transport_list"], project=p_btp, rc=2,
                 code="tool_not_available_for_profile")

    # ── 6j. Kesin Yasak B: standart tabloya doğrudan DML (kapı; reviewer'dan önce) ───
    def test_06j_std_dml_gate(self):
        p = proje()
        kirli = ("CLASS zaxet_dml IMPLEMENTATION.\n  METHOD run.\n"
                 "    UPDATE vbak SET netwr = 0 WHERE vbeln = iv_vbeln.\n  ENDMETHOD.\nENDCLASS.\n")
        temiz = ("CLASS zaxet_dml IMPLEMENTATION.\n  METHOD run.\n"
                 "    UPDATE zaxet_log SET netwr = 0 WHERE vbeln = iv_vbeln.\n  ENDMETHOD.\nENDCLASS.\n")
        d, _o, _e = self.kos("6j Z sınıfına std tablo UPDATE'li kaynak push → ADR_0005_B",
                             ["adt_push_source", "--args-json",
                              json.dumps({"name": "ZAXET_DML", "object_type": "class", "source": kirli}), *S1],
                             project=p, rc=2, code="ADR_0005_B")
        mesaj = d["error"]["message"]
        # Kapı katmanında reddedildi mi (araç katmanı değil)? result=None + review NOT_RUN kapıyı kanıtlar.
        kapida = d["result"] is None and str(d["gate"]["review"]).startswith("NOT_RUN: kapı")
        icerik = "satır 3" in mesaj and "hedef VBAK" in mesaj and "BAPI → RFC FM → işlem kodu (BDC)" in mesaj
        H.kaydet("6j2 red KAPIDA (result=null) + mesajda satır/hedef/yönlendirme", "kapıda + satır 3/VBAK/BAPI",
                 f"kapida={kapida} icerik={icerik}", kapida and icerik)
        self.assertTrue(kapida, d)
        self.assertTrue(icerik, mesaj)
        # KONTROL GRUBU: aynı sınıf, temiz kaynak (+ pull-state kaydı) → kapıdan geçer, ağa gider (exit 1).
        (p / ".axet-code").mkdir(exist_ok=True)
        (p / ".axet-code" / "sap-pull-state.json").write_text(json.dumps({"class:ZAXET_DML": {
            "sha256": "0" * 64, "pulled_at": "2026-09-13T00:00:00+00:00", "object_type": "class"}}),
            encoding="utf-8")
        d2, _o2, _e2 = self.kos("6j3 KONTROL: aynı sınıf temiz kaynak → kapıdan geçer (ağ hatası)",
                                ["adt_push_source", "--args-json",
                                 json.dumps({"name": "ZAXET_DML", "object_type": "class", "source": temiz}), *S1],
                                project=p, rc=1, code="pull_live_read_failed")
        self.assertNotEqual((d2.get("error") or {}).get("code"), "ADR_0005_B")

    # ── 6k. PULL-BEFORE-EDIT: çekme kaydı yoksa push reddi (ağdan önce) ──────────────
    def test_06k_pull_before_edit_missing(self):
        p = proje()
        d, _o, _e = self.kos("6k push, pull-state kaydı yok → pull_before_edit_missing",
                             ["adt_push_source", "--args-json",
                              json.dumps({"name": "ZAXET_PBE", "object_type": "program",
                                          "source": "REPORT zaxet_pbe.\nWRITE 'x'.\n"}), *S1],
                             project=p, rc=2, code="pull_before_edit_missing")
        self.assertIn("adt_get", d["error"]["message"])
        log = (p / ".axet-code" / "sap-write-log.jsonl").read_text(encoding="utf-8").strip().splitlines()
        son = json.loads(log[-1])
        H.kaydet("6k2 deneme logunda sonuç kodu", "pull_before_edit_missing · exit 2",
                 f"{son['result']} · exit {son['exit_code']}",
                 son["result"] == "pull_before_edit_missing" and son["exit_code"] == 2)
        self.assertEqual(son["result"], "pull_before_edit_missing")

    # ── 7. PII ──────────────────────────────────────────────────────────────────────
    def test_07_pii(self):
        sql = ("SELECT k~kunnr, k~name1 FROM kna1 AS k INNER JOIN knvv AS v "
               "ON k~kunnr = v~kunnr WHERE v~vkorg = '1000'")
        p_qa = proje(tier_lines=("ADT_SAP_TIER=QA",))
        self.kos("7a QA adt_sql_query JOIN+takma ad hassas", ["adt_sql_query", "--args-json",
                 json.dumps({"query": sql})], project=p_qa, rc=2, code="ADR_0011_PII")
        self.kos("7b QA adt_table_read KNA1", ["adt_table_read", "--args-json",
                 json.dumps({"table": "KNA1"})], project=p_qa, rc=2, code="ADR_0011_PII")
        self.kos("7c QA onay kelimesi muğlak ('dene')", ["adt_sql_query", "--args-json",
                 json.dumps({"query": sql, "acknowledge_risk": True, "approval_text": "dene"})],
                 project=p_qa, rc=2, code="ADR_0011_PII")
        p_dev = proje()
        self.kos("7d DEV aynı sorgu → guard geçer, bağlantı hatası", ["adt_sql_query", "--args-json",
                 json.dumps({"query": sql})], project=p_dev, rc=1)

    # ── 5b. Kesin Yasak C: paket yaratma/silme (canlı ölçümde kapıdan geçiyordu) ──────
    def test_05b_package_forbidden(self):
        p = proje()
        for tip in ("package", "devc", "DEVC/K"):
            args = post_shell_args(name="ZAXET_PKG")
            args["object_type"] = tip
            self.kos(f"5b post_shell object_type={tip} → paket yasağı", ["adt_post_shell", "--args-json",
                     json.dumps(args), *S1], project=p, rc=2, code="ADR_0005_C")
        self.kos("5b adt_delete object_type=package → paket yasağı", ["adt_delete", "--args-json",
                 json.dumps({"name": "ZAXET_PKG", "object_type": "package", "transport": TR}), *S1],
                 project=p, rc=2, code="ADR_0005_C")

    # ── 8. deneme logu + sır sızıntısı + TLS uyarısı ────────────────────────────────
    def test_08_log_and_secrets(self):
        p = proje()
        gerekce = f"Parolayı içeren gerekçe {H.PAROLA} sızmamalı"
        _d, out, err = self.kos("8a red edilen deneme (gerekçede parola)",
                                ["adt_post_shell", "--args-json", json.dumps(post_shell_args(name="MARA")),
                                 "--sap-write", "--scope", "S1", "--reason", gerekce],
                                project=p, rc=2, code="ADR_0005_A")
        logf = p / ".axet-code" / "sap-write-log.jsonl"
        self.assertTrue(logf.is_file(), "log dosyası yok")
        metin = logf.read_text(encoding="utf-8")
        son = json.loads(metin.strip().splitlines()[-1])
        ok = (son["tool"] == "adt_post_shell" and son["result"] == "ADR_0005_A" and son["object"] == "MARA"
              and H.PAROLA not in metin and H.SAHTE_URL not in metin and "127.0.0.1" not in metin)
        H.kaydet("8b log satırı var, parola/host YOK", "satır + sızıntı yok",
                 f"result={son['result']} parola_logda={H.PAROLA in metin} host_logda={'127.0.0.1' in metin}", ok)
        self.assertTrue(ok, metin)
        self.assertNotIn(H.PAROLA, out)
        self.kos("8c ağa giden çağrı (logda da iz)", ["adt_activate", "--args-json",
                 json.dumps({"name": "ZAXET_X"}), *S1], project=p, rc=1)
        metin = logf.read_text(encoding="utf-8")
        self.assertEqual(len(metin.strip().splitlines()), 2)
        self.assertNotIn(H.PAROLA, metin)
        # Canlı ölçümde bağlantı hatası mesajı SAP host adını taşıdı → çıktı host'u maskelemeli.
        _d3, out3, err3 = self.kos("8f ağ hatası (okuma) çıktısında host YOK", ["adt_search_objects", "--args-json",
                                   json.dumps({"query": "ZAXET*"})], project=p, rc=1)
        host_var = "127.0.0.1" in out3 or H.SAHTE_URL in out3
        H.kaydet("8g bağlantı hatası çıktısı host maskeli", "host_stdout=False", f"host_stdout={host_var}", not host_var)
        self.assertFalse(host_var, out3)
        tls = err.count(H_TLS)
        H.kaydet("8d TLS uyarısı (verify kapalı)", "stderr'de 1 satır", f"{tls} satır", tls == 1)
        self.assertEqual(tls, 1, err)
        p_v = proje(extra_lines=("ADT_SAP_SSL_VERIFY=true",))
        _r, _dd, _o, err2 = H.run_cli(HOME_OPT, ["ping"], project=p_v)
        H.kaydet("8e TLS uyarısı (verify açık)", "0 satır", f"{err2.count(H_TLS)} satır", err2.count(H_TLS) == 0)
        self.assertEqual(err2.count(H_TLS), 0)

    # ── 10. yeni yazma yolları (2026-09-13): kapı + profil + kullanım (ağdan önce) ──────
    def test_10_new_write_paths(self):
        p = proje()
        ekran = {"fm_name": "ZAXET_FM_SCREEN_GEN", "program": "ZAXET_P_EKRAN", "title": "Liste",
                 "transport": TR}
        d, _o, _e = self.kos("10a screen fm_name standart", ["adt_screen_generate", "--args-json",
                             json.dumps({**ekran, "fm_name": "RS_CUA_INTERNAL_WRITE"}), *S1],
                             project=p, rc=2, code="ADR_0005_A")
        self.assertIsNone(d["result"], "red KAPIDA olmalı (araç katmanı değil)")
        d, _o, _e = self.kos("10b screen WRITE transport yok", ["adt_screen_generate", "--args-json",
                             json.dumps({**ekran, "transport": ""}), *S1], project=p, rc=2, code="ADR_0005_C")
        self.assertIsNone(d["result"])
        d, _o, _e = self.kos("10c screen DELETE + program standart (silme yolu Z/Y şartı)", ["adt_screen_generate",
                             "--args-json", json.dumps({**ekran, "program": "SAPLKKBL", "mode": "DELETE"}), *S1],
                             project=p, rc=2, code="ADR_0005_A")
        self.assertIn("gate", d)
        self.kos("10d screen QA tier", ["adt_screen_generate", "--args-json", json.dumps(ekran), *S1],
                 project=proje(tier_lines=("ADT_SAP_TIER=QA",)), rc=2, code="tier_not_writable")
        self.kos("10e screen kapsam yok", ["adt_screen_generate", "--args-json", json.dumps(ekran), "--sap-write"],
                 project=p, rc=2, code="scope_missing")
        self.kos("10f screen s4_public profilinde yok", ["adt_screen_generate", "--args-json", json.dumps(ekran), *S1],
                 project=proje(sap_project={"sap_profile": "s4_public", "master_language": "TR"}),
                 rc=2, code="tool_not_available_for_profile")
        self.kos("10g screen dynpro 3 hane → kullanım (ağ yok)", ["adt_screen_generate", "--args-json",
                 json.dumps({**ekran, "dynpro": "100"}), *S1], project=p, rc=3, code="invalid_argument")
        d, out, err = self.kos("10h KONTROL screen READ transportsuz → kapıdan geçer (ağ hatası)",
                               ["adt_screen_generate", "--args-json",
                                json.dumps({"fm_name": "ZAXET_FM_SCREEN_GEN", "program": "ZAXET_P_EKRAN",
                                            "mode": "READ"}), *S1], project=p, rc=1)
        sizinti = [s for s in (H.PAROLA, "127.0.0.1", H.KULLANICI + ":") if s in out]
        H.kaydet("10h2 screen ağ hatası çıktısında host/parola YOK", "sızıntı yok", f"{sizinti}", not sizinti)
        self.assertEqual(sizinti, [], out)
        log = (p / ".axet-code" / "sap-write-log.jsonl").read_text(encoding="utf-8")
        self.assertIn('"object": "ZAXET_P_EKRAN"', log)
        self.assertNotIn(H.PAROLA, log)
        fonk = {"object_type": "func", "name": "ZAXET_FM_X", "package": "$TMP", "transport": TR,
                "description": "Test FM"}
        d, _o, _e = self.kos("10i post_shell func standart function_group", ["adt_post_shell", "--args-json",
                             json.dumps({**fonk, "extra": {"function_group": "V45A"}}), *S1],
                             project=p, rc=2, code="ADR_0005_A")
        self.assertIsNone(d["result"], "red KAPIDA olmalı (araç katmanı değil)")
        self.kos("10j post_shell func function_group yok (fail-closed)", ["adt_post_shell", "--args-json",
                 json.dumps(fonk), *S1], project=p, rc=2, code="ADR_0005_A")
        self.kos("10k post_shell fugr btp_abap profilinde yok", ["adt_post_shell", "--args-json",
                 json.dumps({**fonk, "object_type": "fugr", "name": "ZAXET_FG"}), *S1],
                 project=proje(sap_project={"sap_profile": "btp_abap", "master_language": "TR"}),
                 rc=2, code="type_not_available_for_profile")
        self.kos("10l push_source func s4_public profilinde yok", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZAXET_FM_X", "object_type": "func",
                             "source": "FUNCTION zaxet_fm_x.\nENDFUNCTION.\n"}), *S1],
                 project=proje(sap_project={"sap_profile": "s4_public", "master_language": "TR"}),
                 rc=2, code="type_not_available_for_profile")
        self.kos("10m post_shell srvb → desteklenmiyor (kullanım)", ["adt_post_shell", "--args-json",
                 json.dumps({**fonk, "object_type": "srvb", "name": "ZAXET_UI_X_O2"}), *S1], project=p, rc=3,
                 code="unsupported_type")
        self.kos("10n post_shell ddls + extra → kullanım", ["adt_post_shell", "--args-json",
                 json.dumps({**fonk, "object_type": "ddls", "name": "ZAXET_I_X", "extra": {"row_type": "X"}}), *S1],
                 project=p, rc=3, code="invalid_argument")
        dml = "FUNCTION zaxet_fm_x.\n  DELETE FROM vbak WHERE vbeln = '1'.\nENDFUNCTION.\n"
        self.kos("10o push_source func std tablo DML → Yasak B", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZAXET_FM_X", "object_type": "func", "source": dml}), *S1],
                 project=p, rc=2, code="ADR_0005_B")
        self.kos("10p push_source ccimp std tablo DML → Yasak B", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZCL_AXET_BP", "object_type": "ccimp", "transport": TR,
                             "source": "CLASS lhc_x IMPLEMENTATION.\n METHOD m.\n  UPDATE vbak SET netwr = 0.\n"
                                       " ENDMETHOD.\nENDCLASS.\n"}), *S1], project=p, rc=2, code="ADR_0005_B")
        bdef = "managed implementation in class zbp_axet_i_x unique;\n// DELETE FROM vbak.\ndefine behavior for ZAXET_I_X\n{\n}\n"
        self.kos("10q push_source bdef taranmaz → pull-before-edit'e ulaşır", ["adt_push_source", "--args-json",
                 json.dumps({"name": "ZAXET_I_X", "object_type": "bdef", "transport": TR, "source": bdef}), *S1],
                 project=p, rc=2, code="pull_before_edit_missing")
        self.kos("10r post_shell enqu E+Z adı kapıdan geçer (ağ hatası)", ["adt_post_shell", "--args-json",
                 json.dumps({**fonk, "object_type": "enqu", "name": "EZAXET_LO",
                             "extra": {"primary_table": "ZAXET_T", "lock_fields": ["MANDT", "ID"]}}), *S1],
                 project=p, rc=1)
        ve = ("define root view entity ZCA000_I_REP as select from ZCA000_C_ORDER {\n  key id\n}\n")
        d, _o, _e = self.kos("10s ddls RAP view entity → rap_cds_creation zinciri BLOCKER (Rule A)",
                             ["adt_push_source", "--args-json",
                              json.dumps({"name": "ZCA000_I_REP", "object_type": "ddls", "source": ve}), *S1],
                             project=p, rc=2, code="reviewer_blocker")
        ids = [r.get("validator") for r in ((d.get("result") or {}).get("reviewer") or {}).get("results", [])]
        H.kaydet("10s2 RAP CDS push'unda rap_cds_creation validator'ları koştu", "readonly_consumption + reuse_gate",
                 str(ids), "check_rap_readonly_consumption.py" in ids and "check_reuse_gate.py" in ids)
        self.assertIn("check_rap_readonly_consumption.py", ids)

    # ── 11. mesaj sınıfı yazma + domain ön kontrolü (2026-09-13) ─────────────────────────
    def test_11_msgclass_write_domain_preflight(self):
        p = proje()
        mw = {"name": "ZAXET_MSG", "transport": TR, "messages": [{"no": "001", "text": "Test mesajı"}]}
        d, _o, _e = self.kos("11a msgclass_write transport yok → kapıda ADR_0005_C",
                             ["adt_msgclass_write", "--args-json", json.dumps({**mw, "transport": ""}), *S1],
                             project=p, rc=2, code="ADR_0005_C")
        self.assertIsNone(d["result"])
        self.kos("11b msgclass_write s4_public profilinde yok", ["adt_msgclass_write", "--args-json", json.dumps(mw), *S1],
                 project=proje(sap_project={"sap_profile": "s4_public", "master_language": "TR"}),
                 rc=2, code="tool_not_available_for_profile")
        self.kos("11c msgclass_write numara '1' → kullanım (ağ yok)", ["adt_msgclass_write", "--args-json",
                 json.dumps({**mw, "messages": [{"no": "1", "text": "x"}]}), *S1], project=p, rc=3, code="invalid_argument")
        self.kos("11d msgclass_write metin boş → Yasak D", ["adt_msgclass_write", "--args-json",
                 json.dumps({**mw, "messages": [{"no": "001", "text": " "}]}), *S1], project=p, rc=2, code="ADR_0005_D")
        d, _o, _e = self.kos("11e msgclass_write pull kaydı yok → pull_before_edit_missing (ağ yok)",
                             ["adt_msgclass_write", "--args-json", json.dumps(mw), *S1],
                             project=p, rc=2, code="pull_before_edit_missing")
        self.assertIn("NONE", d["gate"]["review"])
        self.kos("11f msgclass_write kapsam yok", ["adt_msgclass_write", "--args-json", json.dumps(mw), "--sap-write"],
                 project=p, rc=2, code="scope_missing")
        dom = {"name": "ZAXET_D_X", "datatype": "FLTP", "length": 16, "description": "Test alanı",
               "package": "$TMP", "transport": TR}
        d, _o, _e = self.kos("11g domain FLTP → preflight_blocker (araç, ağdan önce)",
                             ["adt_domain_create", "--args-json", json.dumps(dom), *S1],
                             project=p, rc=2, code="preflight_blocker")
        ok = (d["result"] is not None and d["gate"]["review"].startswith("NOT_RUN: argüman ön kontrolü")
              and d["result"]["steps"]["pre_flight"]["findings"][0]["rule"] == "R1_datatype")
        H.kaydet("11g2 red araç katmanında + gate.review ön kontrol metni", "result dolu · NOT_RUN: argüman",
                 str(d["gate"]["review"]), ok)
        self.assertTrue(ok, d)
        d, out, _e = self.kos("11h KONTROL domain QUAN geçerli, artefakt yok → ağa gider (exit 1), reviewer SKIP görünür",
                              ["adt_domain_create", "--args-json",
                               json.dumps({**dom, "datatype": "QUAN", "length": 15, "decimals": 3}), *S1],
                              project=p, rc=1)
        rv = (d.get("result") or {}).get("reviewer") or {}
        ok = (rv.get("skip_reason") == "no_artifact_path_provided"
              and d["result"]["steps"]["pre_flight"]["output_length"] == 19
              and d["gate"]["review"].startswith("SKIP (no_artifact_path_provided)")
              and H.PAROLA not in out and "127.0.0.1" not in out)
        H.kaydet("11h2 ağ hatasında da reviewer SKIP + pre_flight(19) yanıtta, sızıntı yok", "SKIP · 19",
                 f"{rv.get('skip_reason')} · {d['gate']['review']}", ok)
        self.assertTrue(ok, out)

    # ── 12. tanı araçları · açıklama · ipuçları · DTEL etiket uzunluğu (2026-09-13) ─────────
    def test_12_doctor_description_hints(self):
        p_yok = proje(sap_project=None)
        d, out, _e = self.kos("12a sap_doctor sap-project.json yok → çalışır, doctor_fail (ağ yok)", ["sap_doctor"],
                              project=p_yok, rc=1, code="doctor_fail")
        cks = {k["id"]: k["status"] for k in d["result"]["checks"]}
        ok = cks.get("sap_project") == "FAIL" and cks.get("logon") == "SKIP" and H.PAROLA not in out
        H.kaydet("12a2 sap_doctor: sap_project FAIL · logon SKIP · parola yok", "FAIL · SKIP", str(cks), ok)
        self.assertTrue(ok, out)
        self.assertIn("known_errors_hint", d)
        p = proje()
        d, out, _e = self.kos("12b sap_doctor live=false (yerel katmanlar)", ["sap_doctor", "--args-json", '{"live": false}'],
                              project=p, rc=0)
        ok = (d["result"]["verdict"] in ("PASS", "WARN") and all(s not in out for s in (H.PAROLA, H.KULLANICI, "127.0.0.1"))
              and "checklist_hint" not in d and "known_errors_hint" not in d)
        H.kaydet("12b2 doctor yerel: değer basılmadı · okuma aracında ipucu yok", "sızıntı yok", d["result"]["verdict"], ok)
        self.assertTrue(ok, out)
        self.kos("12c adt_revisions sap-project.json yok → okuma kapısı", ["adt_revisions", "--args-json", '{"name":"ZX"}'],
                 project=p_yok, rc=2, code="sap_project_missing")
        sd = {"name": "ZCA000_I_DEMO", "object_type": "ddls", "description": "Demo açıklama", "transport": TR}
        d, _o, _e = self.kos("12d adt_set_description transport yok → kapıda ADR_0005_C",
                             ["adt_set_description", "--args-json", json.dumps({**sd, "transport": ""}), *S1],
                             project=p, rc=2, code="ADR_0005_C")
        ch, kh = d.get("checklist_hint") or {}, d.get("known_errors_hint") or {}
        ok = (ch.get("group") == "cds" and any(r["path"].endswith("sap-cds-ddic/references/cds.md") for r in ch.get("refs", []))
              and any(r["path"].endswith("sap-adt-foundation/SKILL.md") for r in kh.get("refs", [])))
        H.kaydet("12d2 yazma reddinde checklist_hint(cds) + known_errors_hint(SKILL §4), çıkış kodu değişmedi",
                 "cds · SKILL.md · exit 2", json.dumps({"g": ch.get("group"), "k": [r["path"] for r in kh.get("refs", [])]}), ok)
        self.assertTrue(ok, d)
        self.kos("12e adt_set_description s4_public profilinde yok", ["adt_set_description", "--args-json", json.dumps(sd), *S1],
                 project=proje(sap_project={"sap_profile": "s4_public", "master_language": "TR"}),
                 rc=2, code="tool_not_available_for_profile")
        self.kos("12f adt_set_description srvb → unsupported_type (kullanım, ağ yok)",
                 ["adt_set_description", "--args-json", json.dumps({**sd, "object_type": "srvb", "name": "ZCA000_UI_SB"}), *S1],
                 project=p, rc=3, code="unsupported_type")
        dt = {"name": "ZCA000_DT_X", "domain_name": "CHAR10", "description": "Demo alan", "package": "$TMP", "transport": TR,
              "short_label": "a" * 11, "medium_label": "b" * 20, "long_label": "c" * 40, "heading_label": "d" * 55}
        d, out, _e = self.kos("12g dtel_create short 11 karakter → ADR_0005_D (ağdan önce)",
                              ["adt_dtel_create", "--args-json", json.dumps(dt), *S1], project=p, rc=2, code="ADR_0005_D")
        self.assertIn("short=11>10", d["error"]["message"])
        self.kos("12h KONTROL dtel_create etiketler tam sınırda → kapıdan geçer, ağa gider (exit 1)",
                 ["adt_dtel_create", "--args-json", json.dumps({**dt, "short_label": "a" * 10}), *S1], project=p, rc=1)

    # ── kullanım hataları ───────────────────────────────────────────────────────────
    def test_09_usage(self):
        p = proje()
        self.kos("U1 bilinmeyen araç", ["adt_yok"], project=p, rc=3, code="unknown_tool")
        self.kos("U2 bozuk --args-json", ["adt_get", "--args-json", "{x"], project=p, rc=3, code="args_invalid_json")
        self.kos("U3 imzada olmayan argüman", ["adt_get", "--args-json", '{"nme":"ZX"}'], project=p, rc=3,
                 code="invalid_args")
        self.kos("U4 bilinmeyen bayrak", ["adt_get", "--yok-bayrak"], project=p, rc=3, code="usage_error")


H_TLS = "UYARI: TLS sertifika doğrulaması kapalı (ADT_SAP_SSL_VERIFY)"

INTAKE_GECERLI = """# INTAKE — test raporu  (2026-09-13)
- Modül / iş-tipi / KAPSAM: SD / rapor / S2 (gerekçe: yeni ekran + 2 yeni CDS)
- İstenen (özet): kalemleri filtreli listede göster
- Etkilenen objeler (canlı-doğrulanmış): ZDEMO1_I_ORDER (reuse), ZDEMO1_C_ORDER (yeni)
- Prior-art: yok
- Kabul kriterleri (EARS): kullanıcı filtre uyguladığında sistem yalnız açık kalemleri listelemeli
- MUTABAKAT: [x] kullanıcı sign-off
"""


if __name__ == "__main__":
    unittest.main()
