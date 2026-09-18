# -*- coding: utf-8 -*-
"""Toplu yazıcı (`sapadt/populate.py`) — çevrimdışı (IMPLEMENTATION.md §19).

Katman A (bu sınıf): orkestra mantığı, SAHTE çağrı hattıyla (`cagir`/`kontrol` enjekte). Kapı ve araç
burada koşmaz; hangi aracın hangi argümanla, hangi sırayla ÇAĞRILDIĞI ve çağrılMADIĞI ölçülür.
Katman B/C (`test_populate_hat.py`): gerçek `sap_adt_cli.calistir` + kapı + araç + reviewer, sahte SAP.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import _helpers as H

sys.dont_write_bytecode = True
if str(H.SCRIPTS) not in sys.path:
    sys.path.insert(0, str(H.SCRIPTS))

from sapadt import populate as P  # noqa: E402

TR = "TESTK900001"
PKG = "ZAXET_PKG"

DOMAIN_CSV = ("name,datatype,length,decimals,description,fixed_values\n"
              "ZAXET_D_DURUM,CHAR,1,0,Durum alanı,A=Açık;K=Kapalı\n"
              "ZAXET_D_MIKTAR,QUAN,15,3,Miktar alanı,\n")
DTEL_CSV = ("name,type_kind,type_name,description,short,medium,long,heading\n"
            "ZAXET_E_DURUM,domain,ZAXET_D_DURUM,Durum,Durum,Durum bilgisi,Belge durum bilgisi,Belge durumu\n")


def _p(ok=True, result=None, err=None, review=None):
    return {"ok": ok, "tool": "x", "class": "write", "result": result,
            "error": ({"code": err[0], "message": err[1]} if err else None), "gate": {"review": review}}


YOK = (_p(result={"ok": True, "exists": False}), 0)
VAR = (_p(result={"ok": True, "exists": True}), 0)
OLCULEMEDI = (_p(ok=False, result={"ok": False, "error": "connection_failed", "message": "bağlantı yok"},
                 err=("connection_failed", "bağlantı yok")), 1)
YAZDI = (_p(result={"ok": True}), 0)


class SahteHat:
    """Çağrı kaydı + araç başına sıralı yanıt kuyruğu. Kuyruk biterse son yanıt tekrarlanır."""

    def __init__(self, yanitlar: dict | None = None, red: dict | None = None):
        self.cagrilar: list[tuple[str, dict]] = []
        self.kontroller: list[tuple[str, dict]] = []
        self.loglar: list = []
        self.yanitlar = {k: list(v) for k, v in (yanitlar or {}).items()}
        self.red = red or {}          # tool → (kod, mesaj)
        self.artefakt_goruldu: list = []

    def cagir(self, tool, args):
        self.cagrilar.append((tool, dict(args)))
        if args.get("artifact_path"):
            self.artefakt_goruldu.append((args["artifact_path"], Path(args["artifact_path"]).is_file()))
        kuyruk = self.yanitlar.get(tool)
        if not kuyruk:
            raise AssertionError(f"beklenmeyen çağrı: {tool} {args}")
        y = kuyruk.pop(0) if len(kuyruk) > 1 else kuyruk[0]
        if isinstance(y, Exception):
            raise y
        return y

    def kontrol(self, tool, args):
        self.kontroller.append((tool, dict(args)))
        sinif = "read" if tool in ("adt_get", "adt_msgclass_read") else "write"
        return sinif, self.red.get(tool)

    def logla(self, tool, args, err):
        self.loglar.append((tool, err[0]))

    def araclar(self):
        return [t for t, _a in self.cagrilar]


class Orkestra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_populate_test_"))
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def dosya(self, metin, ad="girdi.csv"):
        type(self)._sayac += 1
        d = self.root / f"g{self._sayac}"
        d.mkdir()
        (d / ad).write_text(metin, encoding="utf-8")
        return d / ad

    def dosya_bayt(self, veri: bytes, ad="girdi.csv"):
        type(self)._sayac += 1
        d = self.root / f"g{self._sayac}"
        d.mkdir()
        (d / ad).write_bytes(veri)
        return d / ad

    def kos(self, hat, tur="domain", **kw):
        kw.setdefault("package", PKG)
        kw.setdefault("transport", TR)
        return P.kos(tur, cagir=hat.cagir, kontrol=hat.kontrol, logla=hat.logla, **kw)

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"POPULATE {ad}", beklenen, str(gercek)[:160], ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    # ── 1. girdi doğrulaması: bulgu varsa HİÇBİR çağrı yok (çıkış 3) ─────────────────────────────
    def test_01_domain_kolon_eksik(self):
        hat = SahteHat()
        d, kod = self.kos(hat, csv_yolu=self.dosya("name,datatype,length,description\nZAXET_D,CHAR,1,x\n"))
        self.kaydet("01 domain CSV kolon eksik → 3, 0 kontrol/çağrı", "3 · csv_invalid · 0/0",
                    f"{kod} · {d['error']['code']} · {len(hat.kontroller)}/{len(hat.cagrilar)}",
                    kod == 3 and d["error"]["code"] == "csv_invalid" and not hat.kontroller and not hat.cagrilar)

    def test_02_domain_tum_bulgular_tek_sefer(self):
        hat = SahteHat()
        metin = ("name,datatype,length,decimals,description,fixed_values\n"
                 "ZAXET_D_A,CHAR,1,0,,\n"                  # description boş (ADR 0005-D)
                 "ZAXET_D_B,CHAR,bir,0,Açıklama,\n"         # length sayı değil
                 "ZAXET_D_C,CHAR,1,,Açıklama,\n"            # decimals boş (0'a düşmez)
                 "ZAXET_D_D,CHAR,1,0,Açıklama,A=;K\n"       # fixed_values bozuk (2 bulgu)
                 ",,,,,\n")                                 # tamamen boş: dolgu
        d, kod = self.kos(hat, csv_yolu=self.dosya(metin))
        b = d["result"].get("findings") or []
        self.kaydet("02 domain 4 kusurlu satır → tüm bulgular tek seferde, 0 çağrı", "3 · 5 bulgu · 0",
                    f"{kod} · {len(b)} · {len(hat.cagrilar)}", kod == 3 and len(b) == 5 and not hat.cagrilar)

    def test_03_dtel_etiket_bos_ve_uzun(self):
        for ad, metin, bek in (
            ("heading boş", "name,type_kind,type_name,description,short,medium,long,heading\n"
                            "ZAXET_E,domain,ZAXET_D,Durum,Durum,Durum bil,Belge durum,\n", "`heading` BOŞ"),
            ("short 11 karakter", "name,type_kind,type_name,description,short,medium,long,heading\n"
                                  "ZAXET_E,domain,ZAXET_D,Durum,Durumbilgis,Durum bil,Belge durum,Belge\n", "11 karakter > 10"),
            ("type_kind builtin", "name,type_kind,type_name,description,short,medium,long,heading\n"
                                  "ZAXET_E,builtin,DATS,Tarih,Tarih,Tarih,Belge tarihi,Tarih\n", "yalnız 'domain'"),
        ):
            hat = SahteHat()
            d, kod = self.kos(hat, "dtel", csv_yolu=self.dosya(metin))
            b = " | ".join(d["result"].get("findings") or [])
            self.kaydet(f"03 dtel {ad} → 3, etiket üretilmez, 0 çağrı", f"3 · {bek}", f"{kod} · {b}",
                        kod == 3 and bek in b and not hat.cagrilar and not hat.kontroller)

    def test_04_msag_ve_cds_girdi(self):
        hat = SahteHat()
        d, kod = self.kos(hat, "msag", msag_adi="ZAXET_MSG", msag_aciklama="Mesajlar",
                          csv_yolu=self.dosya("msgno,msgtext\n1,Metin\n002," + "x" * 74 + "\n003,\n"))
        b = d["result"].get("findings") or []
        self.kaydet("04a msag no '1' (dolgu yok) · metin 74 · metin boş → 3 bulgu", "3 · 3", f"{kod} · {len(b)}",
                    kod == 3 and len(b) == 3 and not hat.cagrilar)
        dz = self.root / "cds1"
        dz.mkdir()
        (dz / "ZAXET_I_A.cds").write_text("define view entity ZAXET_I_A as select from t { key a }", encoding="utf-8")
        (dz / "ZAXET_I_B.cds").write_text("@EndUserText.label: 'B'\ndefine view entity ZAXET_I_X as select from t {a}",
                                          encoding="utf-8")
        d, kod = self.kos(hat, "cds", kaynak_dizini=str(dz))
        b = " | ".join(d["result"].get("findings") or [])
        self.kaydet("04b cds etiket yok (varsayılan yok) · dosya adı≠tanım adı → 3", "3 · label · farklı",
                    f"{kod} · {b[:120]}", kod == 3 and "EndUserText.label" in b and "farklı" in b and not hat.cagrilar)

    def test_05_kullanim_kurallari(self):
        csv_d = self.dosya(DOMAIN_CSV)
        for ad, tur, kw in (
            ("force --only yok", "domain", {"force_recreate": True}),
            ("force iki ad", "domain", {"force_recreate": True, "only": "ZAXET_D_DURUM,ZAXET_D_MIKTAR"}),
            ("force enqu", "enqu", {"force_recreate": True, "only": "EZAXET_X"}),
            ("allow_overwrite domain", "domain", {"allow_overwrite": True}),
            ("only CSV'de yok", "domain", {"only": "ZAXET_D_YOK"}),
            ("tablo türü yok", "tabl", {}),
            ("package yok", "domain", {"package": ""}),
        ):
            hat = SahteHat()
            d, kod = self.kos(hat, tur, csv_yolu=csv_d, **kw)
            self.kaydet(f"05 kullanım: {ad} → 3, 0 çağrı", "3 · usage_error · 0", f"{kod} · {d['error']['code']} · "
                        f"{len(hat.cagrilar)}", kod == 3 and d["error"]["code"] == "usage_error" and not hat.cagrilar)

    # ── 2. ön geçiş ──────────────────────────────────────────────────────────────────────────────
    def test_06_on_gecis_red_hicbir_sey_yazilmaz(self):
        hat = SahteHat(red={"adt_domain_create": ("ADR_0005_C", "transport yok")})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV))
        r = d["gate"]["prepass"]
        ok = (kod == 2 and d["error"]["code"] == "prepass_gate_rejected" and not hat.cagrilar
              and len(r["rejections"]) == 2 and r["checked"] == 4
              and hat.loglar == [("adt_domain_create", "ADR_0005_C")] * 2
              and all(s["status"] == P.ISLENMEDI for s in d["result"]["rows"]))
        self.kaydet("06 ön geçiş reddi → 2, 0 çağrı, 4 kontrol, 2 red logu, satırlar islenmedi",
                    "2 · 0 çağrı · 2 red", f"{kod} · {len(hat.cagrilar)} çağrı · {r}", ok)

    def test_07_on_gecis_delete_de_kontrol_edilir(self):
        hat = SahteHat(red={"adt_delete": ("tier_not_writable", "QA")})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), force_recreate=True, only="ZAXET_D_DURUM")
        araclar = [t for t, _a in hat.kontroller]
        self.kaydet("07 --force-recreate: adt_delete ön geçişte kapıya girer; reddi → 2, 0 çağrı",
                    "adt_delete kontrol · 2 · 0", f"{araclar} · {kod} · {len(hat.cagrilar)}",
                    araclar == ["adt_get", "adt_delete", "adt_domain_create"] and kod == 2 and not hat.cagrilar)

    def test_08_dry_run_sap_cagrisi_yok(self):
        hat = SahteHat()
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), dry_run=True)
        self.kaydet("08 dry-run → 0, kontrol koşar, 0 SAP çağrısı", "0 · 4 kontrol · 0 çağrı",
                    f"{kod} · {len(hat.kontroller)} · {len(hat.cagrilar)}",
                    kod == 0 and len(hat.kontroller) == 4 and not hat.cagrilar
                    and d["result"]["summary"][P.DRY_RUN] == 2)

    # ── 3. varlık sondası · atlanan · kısmi başarı ───────────────────────────────────────────────
    def test_09_sonda_olculemedi_yazma_yok(self):
        hat = SahteHat({"adt_get": [OLCULEMEDI, YOK], "adt_domain_create": [YAZDI]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV))
        rows = d["result"]["rows"]
        ok = (kod == 1 and hat.araclar() == ["adt_get", "adt_get", "adt_domain_create"]
              and hat.cagrilar[2][1]["name"] == "ZAXET_D_MIKTAR"
              and rows[0]["status"] == P.HATA and "ÖLÇÜLEMEDİ" in rows[0]["message"] and rows[1]["status"] == P.YAZILDI)
        self.kaydet("09 sonda ölçülemedi → o satır HATA, yazma yok; sıradaki yazılır; exit 1", "1 · create yalnız 2. satır",
                    f"{kod} · {hat.araclar()} · {[r['status'] for r in rows]}", ok)

    def test_10_atlanan_basari_sayilmaz(self):
        hat = SahteHat({"adt_get": [VAR]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV))
        oz = d["result"]["summary"]
        ok = (kod == 0 and oz[P.YAZILDI] == 0 and oz[P.ATLANDI] == 2 and "adt_domain_create" not in hat.araclar()
              and any("YAZILMADI" in n for n in d["result"]["notices"])
              and d["result"]["rows"][0]["suggestion"].startswith("--force-recreate --only ZAXET_D_DURUM "))
        self.kaydet("10 var → atlandı: yazıldı=0, uyarı, öneri tek ada daraltılmış", "0 · yazildi 0 · atlandi 2",
                    f"{kod} · {oz}", ok)
        hat = SahteHat({"adt_get": [VAR]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), fail_on_skip=True)
        self.kaydet("10b atlanan + --fail-on-skip → 4", "4 · skipped_rows", f"{kod} · {d['error']['code']}",
                    kod == 4 and d["error"]["code"] == "skipped_rows")

    def test_11_kismi_basari_durust_cikis(self):
        hata = (_p(ok=False, result={"ok": False, "error": "activation_failed", "message": "aktive olmadı"},
                   err=("activation_failed", "aktive olmadı")), 1)
        hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [YAZDI, hata]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV))
        oz = d["result"]["summary"]
        self.kaydet("11 1 yazıldı + 1 hata → exit 1 partial_failure", "1 · partial_failure · 1/1",
                    f"{kod} · {d['error']['code']} · {oz}",
                    kod == 1 and d["error"]["code"] == "partial_failure" and oz[P.YAZILDI] == 1 and oz[P.HATA] == 1
                    and not d["ok"])

    # ── 3b. yazma adımında sonucu BİLİNMEYEN hata → koşum DURUR (gate-d3 bulgu 1, lider kararı (a)) ────────
    # Yanıt biçimleri `calistir`'ın GERÇEKTE döndürdükleridir (kaynak satırları IMPLEMENTATION.md §19.10):
    # araç istisnası `calistir` içinde `_err_from_exc` ile `unexpected`/`connection_failed` olur (istisna
    # POPULATE'e ULAŞMAZ) · composite hatası yalnız `steps.*` içinde · `push_object` istisnayı `error_type`e yutar.
    UC_CSV = DOMAIN_CSV + "ZAXET_D_UCUNCU,CHAR,2,0,Üçüncü alan,\n"

    @staticmethod
    def _hatali(result, kod, cikis=1):
        return (_p(ok=False, result=result, err=(kod, str((result or {}).get("message") or ""))), cikis)

    B_SINIF, K_SINIF = "sonuc_bilinmiyor", "hesap_kilidi_riski"
    B_MESAJ = "sonuç BİLİNMİYOR, SAP'de durumu kontrol et"
    K_MESAJ = "kimlik reddedildi, koşum durduruldu, hesap kilidi riskine karşı kalan satırlar denenmedi"

    def test_12_bilinmeyen_sonuc_kosumu_durdurur(self):
        B, K, MB, MK = self.B_SINIF, self.K_SINIF, self.B_MESAJ, self.K_MESAJ

        def push(err_type, metin):
            return {"ok": False, "error": "push_failed", "message": metin,
                    "result": {"success": False, "error": metin, "error_type": err_type}}
        vakalar = (   # (ad, araç sonucu, calistir kodu, sınıf, durma kodunda geçmeli, mesajda geçmeli)
            ("araç istisnası → calistir unexpected", {"ok": False, "error": "unexpected",
                                                     "message": "TimeoutError: yanıt gelmedi"}, "unexpected",
             B, "unexpected", MB),
            ("lib SAPConnectionError → connection_failed", {"ok": False, "error": "connection_failed",
                                                           "message": "Connection timeout after 3 attempts"},
             "connection_failed", B, "connection_failed", MB),
            ("adt_activate ulaşılamadı → unreachable", {"ok": False, "error": "unreachable",
                                                       "message": "SAP'ye ULAŞILAMADI"}, "unreachable",
             B, "unreachable", MB),
            ("composite steps.create connection_failed (üst error yok)",
             {"ok": False, "steps": {"create": {"ok": False, "error": "connection_failed", "message": "koptu"}}},
             "tool_failed", B, "connection_failed", MB),
            ("composite steps.activate.error{unexpected}",
             {"ok": False, "steps": {"create": {"ok": True},
                                     "activate": {"ok": False, "error": {"ok": False, "error": "unexpected",
                                                                         "message": "OSError"}}}}, "tool_failed",
             B, "unexpected", MB),
            ("push_failed + error_type SAPConnectionError", push("SAPConnectionError", "Connection failed"),
             "push_failed", B, "SAPConnectionError", MB),
            ("push_failed + error_type TimeoutError (SAP ağacı dışı)", push("TimeoutError", "read timed out"),
             "push_failed", B, "TimeoutError", MB),
            ("sap_error [502]", {"ok": False, "error": "sap_error", "message": "[502] Failed to create domain X"},
             "sap_error", B, "502", MB),
            ("sap_error [503]", {"ok": False, "error": "sap_error", "message": "[503] Failed to create domain X"},
             "sap_error", B, "503", MB),
            ("sap_error [504]", {"ok": False, "error": "sap_error", "message": "[504] Failed to create domain X"},
             "sap_error", B, "504", MB),
            ("steps.create sap_error [504]",
             {"ok": False, "steps": {"create": {"ok": False, "error": "sap_error", "message": "[504] Gateway"}}},
             "tool_failed", B, "504", MB),
            ("push_failed + error_type SAPADTError [503]", push("SAPADTError", "[503] Service Unavailable"),
             "push_failed", B, "503", MB),
            ("auth_failed", {"ok": False, "error": "auth_failed", "message": "Authentication failed. Check credentials."},
             "auth_failed", K, "auth_failed", MK),
            ("steps.create auth_failed",
             {"ok": False, "steps": {"create": {"ok": False, "error": "auth_failed", "message": "Authentication"}}},
             "tool_failed", K, "auth_failed", MK),
            ("sap_error [401]", {"ok": False, "error": "sap_error", "message": "[401] Failed to create domain X"},
             "sap_error", K, "401", MK),
        )
        for ad, sonuc, kod, sinif, kod_parca, mesaj in vakalar:
            hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [self._hatali(sonuc, kod), YAZDI]})
            d, cikis = self.kos(hat, csv_yolu=self.dosya(self.UC_CSV))
            rows = d["result"]["rows"]
            st = [r["status"] for r in rows]
            m = rows[0].get("message") or ""
            stop = d["result"].get("stop") or {}
            ok = (cikis == 1 and (d.get("error") or {}).get("code") == "run_stopped"
                  and st == [P.HATA, P.ISLENMEDI, P.ISLENMEDI]
                  and hat.araclar() == ["adt_get", "adt_domain_create"]
                  and mesaj in m and mesaj in str(d["result"].get("stopped") or "")
                  and stop.get("class") == sinif and kod_parca in str(stop.get("code"))
                  and stop.get("name") == "ZAXET_D_DURUM" and stop.get("row") == 2 and stop.get("step") == "yarat"
                  and stop.get("tool") == "adt_domain_create")
            self.kaydet(f"12 {ad} → koşum DURUR ({sinif}), kalanlar islenmedi, exit 1 run_stopped, durma ayrıntısı",
                        f"1 · run_stopped · hata,islenmedi,islenmedi · {sinif} · kod∋{kod_parca}",
                        f"{cikis} · {(d.get('error') or {}).get('code')} · {st} · {hat.araclar()} · {stop} · {m[:60]}",
                        ok)

    def test_12b_bilinen_red_kosum_surer(self):
        vakalar = (
            ("SAP 4xx sap_error", {"ok": False, "error": "sap_error", "message": "[400] Bad Request"}, "sap_error", 1),
            ("post_shell create_failed", {"ok": False, "error": "create_failed", "message": "[400]",
                                          "exists_after": False}, "create_failed", 1),
            ("reviewer_blocker", {"ok": False, "error": "reviewer_blocker", "message": "BLOCKER"}, "reviewer_blocker", 2),
            ("preflight_blocker", {"ok": False, "error": "preflight_blocker", "message": "FLTP"}, "preflight_blocker", 2),
            ("çalışma anı kapı reddi (result yok)", None, "ADR_0005_C", 2),
            ("locked", {"ok": False, "error": "locked", "message": "is locked by BASKA"}, "locked", 1),
            ("steps.create validation_error (domain tip bilgisi)",
             {"ok": False, "steps": {"create": {"ok": False, "error": "validation_error", "message": "bulunamadı"}}},
             "tool_failed", 1),
            ("push_failed + error_type SAPADTError (HTTP 500 yanıtı)",
             {"ok": False, "error": "push_failed", "message": "[500]",
              "result": {"success": False, "error": "[500]", "error_type": "SAPADTError"}}, "push_failed", 1),
            ("activation_failed", {"ok": False, "error": "activation_failed", "message": "aktive olmadı"},
             "activation_failed", 1),
            ("sap_error [500] (502/503/504 değil)", {"ok": False, "error": "sap_error",
                                                    "message": "[500] Failed to create domain X"}, "sap_error", 1),
            ("sap_error [403] (yetki; kimlik değil)", {"ok": False, "error": "sap_error",
                                                      "message": "[403] Forbidden"}, "sap_error", 1),
            ("sap_error durum kodu TAŞIMIYOR", {"ok": False, "error": "sap_error",
                                                "message": "ATC worklist creation returned empty ID"}, "sap_error", 1),
            ("sap_error '[502]' GÖVDE içinde, başta değil", {"ok": False, "error": "sap_error",
                                                            "message": "[400] Failed — SAP gövdesi: [502] Bad Gateway"},
             "sap_error", 1),
            ("sap_error başında boşluk ' [503] …' (sıkı desen)", {"ok": False, "error": "sap_error",
                                                                 "message": " [503] Service Unavailable"}, "sap_error", 1),
            ("sap_error '[504]' boşluksuz '[504]x' (sıkı desen)", {"ok": False, "error": "sap_error",
                                                                  "message": "[504]Gateway Timeout"}, "sap_error", 1),
            ("steps.create sap_error gövdede [504]",
             {"ok": False, "steps": {"create": {"ok": False, "error": "sap_error",
                                                "message": "Failed to create domain X: body [504] timeout"}}},
             "tool_failed", 1),
            ("push SAPADTError gövdede [503]",
             {"ok": False, "error": "push_failed", "message": "Upload failed",
              "result": {"success": False, "error": "Upload failed: body [503]", "error_type": "SAPADTError"}},
             "push_failed", 1),
            ("create_failed mesajı [401] ile başlıyor (sap_error değil)",
             {"ok": False, "error": "create_failed", "message": "[401] gövde"}, "create_failed", 1),
        )
        for ad, sonuc, kod, cikis_kodu in vakalar:
            hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [self._hatali(sonuc, kod, cikis_kodu), YAZDI]})
            d, cikis = self.kos(hat, csv_yolu=self.dosya(self.UC_CSV))
            rows = d["result"]["rows"]
            st = [r["status"] for r in rows]
            m = rows[0].get("message") or ""
            ok = (cikis == 1 and (d.get("error") or {}).get("code") == "partial_failure"
                  and st == [P.HATA, P.YAZILDI, P.YAZILDI] and hat.araclar().count("adt_domain_create") == 3
                  and "BİLİNMİYOR" not in m and not d["result"].get("stopped"))
            self.kaydet(f"12b KONTROL {ad} → satır HATA, koşum SÜRER", "1 · partial_failure · hata,yazildi,yazildi",
                        f"{cikis} · {(d.get('error') or {}).get('code')} · {st} · {m[:60]}", ok)

    def test_12c_kontrol_A2_cagri_hattinin_kendisi_patlar(self):
        hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [RuntimeError("hat koptu")]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(self.UC_CSV))
        st = [r["status"] for r in d["result"]["rows"]]
        self.kaydet("12c KONTROL A2: çağrı hattının KENDİSİ istisna → koşum durur (step_exception)",
                    "hata,islenmedi,islenmedi", f"{kod} · {st} · {hat.araclar()}",
                    kod == 1 and st == [P.HATA, P.ISLENMEDI, P.ISLENMEDI] and d["error"]["code"] == "run_stopped"
                    and hat.araclar() == ["adt_get", "adt_domain_create"]
                    and d["result"]["rows"][0]["steps"][-1]["error"]["code"] == "step_exception"
                    and (d["result"].get("stop") or {}).get("code") == "step_exception"
                    and (d["result"].get("stop") or {}).get("class") == self.B_SINIF)

    def test_12d_silme_sonucu_bilinmiyor_durma_ayrintisi(self):
        hat, d, kod = self._force((_p(result={"ok": True, "deleted": True, "delete_verified": None}), 0))
        stop = d["result"].get("stop") or {}
        self.kaydet("12d force delete_verified=null → durma ayrıntısı: satır 2 · sil/adt_delete · sonuç bilinmiyor",
                    "sil · adt_delete · sonuc_bilinmiyor · row 2", stop,
                    kod == 1 and stop.get("step") == "sil" and stop.get("tool") == "adt_delete"
                    and stop.get("class") == self.B_SINIF and "delete_verified" in str(stop.get("code"))
                    and stop.get("row") == 2 and stop.get("name") == "ZAXET_D_DURUM")

    # ── 4. --force-recreate: DELETE yanıtı okunur ────────────────────────────────────────────────
    def _force(self, sil, sonda_sonrasi=None, tur="domain"):
        yan = {"adt_get": [VAR] + ([sonda_sonrasi] if sonda_sonrasi else []), "adt_delete": [sil],
               "adt_domain_create": [YAZDI]}
        hat = SahteHat(yan)
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), force_recreate=True, only="ZAXET_D_DURUM")
        return hat, d, kod

    def test_13_force_silme_dogrulandi_yaratir(self):
        hat, d, kod = self._force((_p(result={"ok": True, "deleted": True, "delete_verified": True}), 0))
        self.kaydet("13 force: delete_verified=true → yaratma", "0 · get,delete,create",
                    f"{kod} · {hat.araclar()}", kod == 0 and hat.araclar() == ["adt_get", "adt_delete", "adt_domain_create"])

    def test_14_force_silme_dogrulanamadi_durur(self):
        hat, d, kod = self._force((_p(result={"ok": True, "deleted": True, "delete_verified": None}), 0))
        r = d["result"]
        kodu = (d.get("error") or {}).get("code")   # mutasyonda error None olabilir → istisna değil, iddia düşsün
        durdu = str(r.get("stopped") or "")
        self.kaydet("14 force: delete_verified=null → DUR, create YOK, exit 1 run_stopped", "1 · run_stopped · create yok",
                    f"{kod} · {kodu} · {hat.araclar()} · stopped={durdu[:60]!r}",
                    kod == 1 and kodu == "run_stopped" and "adt_domain_create" not in hat.araclar()
                    and "DOĞRULANAMADI" in durdu)

    def test_15_force_silme_basarisiz_obje_var(self):
        sil = (_p(ok=False, result={"ok": False, "deleted": False}, err=("tool_failed", "")), 1)
        hat, d, kod = self._force(sil, VAR)
        self.kaydet("15 force: DELETE ok:false + sonda var → HATA, create yok, koşum sürer", "1 · partial · create yok",
                    f"{kod} · {d['error']['code']} · {hat.araclar()}",
                    kod == 1 and d["error"]["code"] == "partial_failure" and hat.araclar() == ["adt_get", "adt_delete", "adt_get"]
                    and "hâlâ VAR" in d["result"]["rows"][0]["message"])

    def test_16_force_silme_basarisiz_obje_yok_tutarsiz(self):
        sil = (_p(ok=False, result={"ok": False, "deleted": False}, err=("tool_failed", "")), 1)
        hat, d, kod = self._force(sil, YOK)
        self.kaydet("16 force: DELETE ok:false + sonda yok → HATA (tutarsız), create yok", "1 · create yok",
                    f"{kod} · {hat.araclar()}", kod == 1 and "adt_domain_create" not in hat.araclar()
                    and "tutarsız" in d["result"]["rows"][0]["message"])

    def test_17_force_silme_basarisiz_sonda_olculemedi_durur(self):
        sil = (_p(ok=False, result={"ok": False, "deleted": False}, err=("tool_failed", "")), 1)
        hat, d, kod = self._force(sil, OLCULEMEDI)
        self.kaydet("17 force: DELETE ok:false + sonda ölçülemedi → DUR, create yok", "1 · run_stopped",
                    f"{kod} · {d['error']['code']} · {hat.araclar()}",
                    kod == 1 and d["error"]["code"] == "run_stopped" and "adt_domain_create" not in hat.araclar())

    def test_18_force_silme_istisnasi_durur(self):
        hat, d, kod = self._force(ConnectionError("timeout"))
        self.kaydet("18 force: DELETE istisnası → DUR, create yok", "1 · run_stopped · create yok",
                    f"{kod} · {d['error']['code']} · {hat.araclar()}",
                    kod == 1 and d["error"]["code"] == "run_stopped" and hat.araclar() == ["adt_get", "adt_delete"])

    def test_19_force_silme_kapi_reddi_calisma_aninda(self):
        sil = (_p(ok=False, result=None, err=("tier_not_writable", "QA")), 2)
        hat, d, kod = self._force(sil)
        self.kaydet("19 force: DELETE çalışma anında kapı reddi → HATA, create yok, sonda tekrarı yok", "1 · get,delete",
                    f"{kod} · {hat.araclar()}", kod == 1 and hat.araclar() == ["adt_get", "adt_delete"])

    def test_20_force_obje_yoksa_delete_yok(self):
        hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [YAZDI]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), force_recreate=True, only="ZAXET_D_DURUM")
        self.kaydet("20 force + obje yok → DELETE gönderilmez, yalnız o ad işlenir", "0 · get,create · 1 satır",
                    f"{kod} · {hat.araclar()} · {len(d['result']['rows'])}",
                    kod == 0 and hat.araclar() == ["adt_get", "adt_domain_create"] and len(d["result"]["rows"]) == 1)

    # ── 5. tür akışları · geçici artefakt ────────────────────────────────────────────────────────
    def test_21_dtel_argumanlar_ve_gecici_artefakt(self):
        hat = SahteHat({"adt_get": [YOK], "adt_dtel_create": [YAZDI]})
        metin = ("name,type_kind,type_name,datatype,length,decimals,description,short,medium,long,heading\n"
                 "ZAXET_E_DURUM,domain,ZAXET_D_DURUM,CHAR,1,0,Durum,Durum,Durum bilgisi,Belge durum bilgisi,Belge durumu\n")
        d, kod = self.kos(hat, "dtel", csv_yolu=self.dosya(metin))
        a = hat.cagrilar[1][1]
        tmp = Path(d["result"]["temp_dir"])
        ok = (kod == 0 and a["domain_name"] == "ZAXET_D_DURUM" and a["heading_label"] == "Belge durumu"
              and hat.artefakt_goruldu and hat.artefakt_goruldu[0][1] is True
              and Path(a["artifact_path"]).parent == tmp
              and Path(tempfile.gettempdir()).resolve() in tmp.resolve().parents
              and not tmp.exists() and d["result"]["temp_dir_removed"] is True
              and H.FOUNDATION.resolve() not in tmp.resolve().parents
              and any("araca GEÇMEZ" in n for n in d["result"]["notices"]))
        self.kaydet("21 dtel: etiketler CSV'den · artefakt izole TMP'de, çağrı anında var, sonra silindi · tip kolonu uyarısı",
                    "0 · tmp altında · silindi", f"{kod} · {tmp} · exists={tmp.exists()}", ok)

    def test_22_cds_sira_ve_pull_eksik(self):
        dz = self.root / "cds2"
        dz.mkdir()
        (dz / "ZAXET_I_KALEM.cds").write_text("@EndUserText.label: 'Kalem görünümü'\n"
                                              "define view entity ZAXET_I_KALEM as select from t { key a }",
                                              encoding="utf-8")
        pull_ok = (_p(result={"ok": True, "exists": True, "source": "", "pull_state": "kaydedildi"}), 0)
        hat = SahteHat({"adt_get": [YOK, pull_ok], "adt_post_shell": [YAZDI], "adt_push_source": [YAZDI],
                        "adt_activate": [YAZDI]})
        d, kod = self.kos(hat, "cds", kaynak_dizini=str(dz))
        ok = (kod == 0 and hat.araclar() == ["adt_get", "adt_post_shell", "adt_get", "adt_push_source", "adt_activate"]
              and hat.cagrilar[1][1]["description"] == "Kalem görünümü" and hat.cagrilar[2][1]["include_source"] is True)
        self.kaydet("22a cds: sonda → kabuk → pull → push → aktive; açıklama label'dan", "0 · 5 adım", f"{kod} · {hat.araclar()}", ok)
        pull_yok = (_p(result={"ok": True, "exists": True, "source": "", "pull_state": "yazilamadi: disk"}), 0)
        hat = SahteHat({"adt_get": [YOK, pull_yok], "adt_post_shell": [YAZDI]})
        d, kod = self.kos(hat, "cds", kaynak_dizini=str(dz))
        self.kaydet("22b cds: pull kaydı yok → push YOK, HATA", "1 · push yok", f"{kod} · {hat.araclar()}",
                    kod == 1 and "adt_push_source" not in hat.araclar())

    def test_23_msag_akislari(self):
        csv_m = self.dosya("msgno,msgtext,selfexplainatory\n001,Kayıt bulunamadı,false\n002,Kayıt kilitli,\n")
        var = (_p(result={"ok": True, "exists": True, "count": 1}), 0)
        degismedi = (_p(result={"ok": True, "changed": False}), 0)
        hat = SahteHat({"adt_msgclass_read": [var], "adt_msgclass_write": [degismedi]})
        d, kod = self.kos(hat, "msag", csv_yolu=csv_m, msag_adi="zaxet_msg", msag_aciklama="Mesajlar")
        yaz = hat.cagrilar[-1][1]
        ok = (kod == 0 and hat.araclar() == ["adt_msgclass_read", "adt_msgclass_write"]
              and yaz["messages"] == [{"no": "001", "text": "Kayıt bulunamadı", "selfexplanatory": False},
                                      {"no": "002", "text": "Kayıt kilitli"}]
              and yaz["allow_overwrite"] is False and yaz["name"] == "ZAXET_MSG"
              and d["result"]["summary"][P.ATLANDI] == 1)
        self.kaydet("23a msag var + değişiklik yok → kabuk yok, atlandı; allow_overwrite varsayılan false", "0 · atlandi",
                    f"{kod} · {hat.araclar()} · {d['result']['summary']}", ok)
        red = (_p(ok=False, result={"ok": False, "error": "msgclass_overwrite_not_allowed", "message": "001 değişirdi"},
                  err=("msgclass_overwrite_not_allowed", "001 değişirdi")), 2)
        hat = SahteHat({"adt_msgclass_read": [(_p(result={"ok": True, "exists": False}), 0), var],
                        "adt_post_shell": [YAZDI], "adt_msgclass_write": [red]})
        d, kod = self.kos(hat, "msag", csv_yolu=csv_m, msag_adi="ZAXET_MSG", msag_aciklama="Mesajlar")
        self.kaydet("23b msag yok → kabuk + yeniden oku; üzerine yazma reddi → HATA", "1 · read,shell,read,write",
                    f"{kod} · {hat.araclar()}",
                    kod == 1 and hat.araclar() == ["adt_msgclass_read", "adt_post_shell", "adt_msgclass_read",
                                                   "adt_msgclass_write"]
                    and "msgclass_overwrite_not_allowed" in d["result"]["rows"][0]["message"])


    def test_24_enqu_uc_degerli_sonda(self):
        csv_e = self.dosya("name,description,primary_table,lock_mode,allow_rfc,field_names\n"
                           "EZAXET_BELGE,Belge kilidi,ZAXET_T_BELGE,E,false,MANDT;BELGE_NO\n")
        hat = SahteHat({"adt_get": [OLCULEMEDI]})
        d, kod = self.kos(hat, "enqu", csv_yolu=csv_e)
        self.kaydet("24a enqu sonda ölçülemedi → HATA, post_shell/activate YOK", "1 · yalnız adt_get",
                    f"{kod} · {hat.araclar()}", kod == 1 and hat.araclar() == ["adt_get"]
                    and hat.cagrilar[0][1] == {"name": "EZAXET_BELGE", "object_type": "enqu", "include_source": False})
        hat = SahteHat({"adt_get": [VAR]})
        d, kod = self.kos(hat, "enqu", csv_yolu=csv_e)
        self.kaydet("24b enqu var → atlandı, yazma yok", "0 · atlandi · yalnız adt_get",
                    f"{kod} · {d['result']['summary']} · {hat.araclar()}",
                    kod == 0 and d["result"]["summary"][P.ATLANDI] == 1 and hat.araclar() == ["adt_get"])
        hat = SahteHat({"adt_get": [YOK], "adt_post_shell": [YAZDI], "adt_activate": [YAZDI]})
        d, kod = self.kos(hat, "enqu", csv_yolu=csv_e)
        ek = hat.cagrilar[1][1].get("extra")
        self.kaydet("24c enqu yok → kabuk (extra CSV'den) → aktive", "0 · get,shell,activate",
                    f"{kod} · {hat.araclar()} · {ek}",
                    kod == 0 and hat.araclar() == ["adt_get", "adt_post_shell", "adt_activate"]
                    and ek == {"primary_table": "ZAXET_T_BELGE", "lock_fields": ["MANDT", "BELGE_NO"],
                               "lock_mode": "E", "allow_rfc": False})

    # ── 6. gate-d3 bulgu 2: yinelenen CSV başlığı → csv_invalid (çıkış 3), ön geçiş/çağrı YOK ────────────
    def test_25_yinelenen_baslik_reddedilir(self):
        for ad, tur, metin, kw in (
            ("domain name iki kez (probe D)", "domain",
             "name,datatype,length,decimals,description,name\nZAXET_D_BIR,CHAR,1,0,Bir alan,ZAXET_D_BASKA\n", {}),
            ("domain description iki kez, biri boşluklu", "domain",
             "name,datatype,length,decimals,description, description \nZAXET_D_BIR,CHAR,1,0,Bir,İki\n", {}),
            ("BOM + name iki kez", "domain",
             "﻿name,datatype,length,decimals,description,name\nZAXET_D_BIR,CHAR,1,0,Bir,ZAXET_D_X\n", {}),
            ("dtel short iki kez", "dtel",
             "name,type_kind,type_name,description,short,medium,long,heading,short\n"
             "ZAXET_E,domain,ZAXET_D,Durum,Durum,Durum bil,Belge durum,Belge,Başka\n", {}),
            ("msag msgtext iki kez", "msag", "msgno,msgtext,msgtext\n001,Bir,İki\n",
             {"msag_adi": "ZAXET_MSG", "msag_aciklama": "Mesajlar"}),
        ):
            hat = SahteHat()
            d, kod = self.kos(hat, tur, csv_yolu=self.dosya(metin), dry_run=True, **kw)
            e = d.get("error") or {}
            self.kaydet(f"25 {ad} → 3 csv_invalid, 0 kontrol/çağrı", "3 · csv_invalid · tekrar",
                        f"{kod} · {e} · {len(hat.kontroller)}/{len(hat.cagrilar)}",
                        kod == 3 and e.get("code") == "csv_invalid" and "tekrar" in str(e.get("message"))
                        and not hat.kontroller and not hat.cagrilar)

    # ── 7. gate-d3 bulgu 3: force yolunda silme doğrulandıktan sonra yaratma hatası mesajda ────────────────
    SILINDI = "obje SİLİNDİ (delete_verified); yeniden yaratma başarısız:"

    def test_26_force_silindi_sonra_yaratma_hatasi_mesajda(self):
        sil_ok = (_p(result={"ok": True, "deleted": True, "delete_verified": True}), 0)
        red = self._hatali({"ok": False, "error": "sap_error", "message": "[400] Bad Request"}, "sap_error")
        bilinmez = self._hatali({"ok": False, "error": "unexpected", "message": "TimeoutError"}, "unexpected")
        dz = self.root / "cds_force"
        dz.mkdir(exist_ok=True)
        (dz / "ZAXET_I_KALEM.cds").write_text("@EndUserText.label: 'Kalem görünümü'\n"
                                              "define view entity ZAXET_I_KALEM as select from t { key a }",
                                              encoding="utf-8")
        pull_ok = (_p(result={"ok": True, "exists": True, "source": "", "pull_state": "kaydedildi"}), 0)
        pull_yok = (_p(result={"ok": True, "exists": True, "source": "", "pull_state": "yazilamadi: disk"}), 0)
        dom = {"csv_yolu": self.dosya(DOMAIN_CSV), "only": "ZAXET_D_DURUM"}
        dtel = {"csv_yolu": self.dosya(DTEL_CSV), "only": "ZAXET_E_DURUM"}
        cds = {"kaynak_dizini": str(dz), "only": "ZAXET_I_KALEM"}
        ortak = {"adt_delete": [sil_ok]}
        for ad, tur, kw, yan, durur in (
            ("domain create", "domain", dom, {"adt_get": [VAR], "adt_domain_create": [red]}, False),
            ("dtel create", "dtel", dtel, {"adt_get": [VAR], "adt_dtel_create": [red]}, False),
            ("cds kabuk", "cds", cds, {"adt_get": [VAR], "adt_post_shell": [red]}, False),
            ("cds pull", "cds", cds, {"adt_get": [VAR, pull_yok], "adt_post_shell": [YAZDI]}, False),
            ("cds push", "cds", cds, {"adt_get": [VAR, pull_ok], "adt_post_shell": [YAZDI],
                                      "adt_push_source": [red]}, False),
            ("cds aktive", "cds", cds, {"adt_get": [VAR, pull_ok], "adt_post_shell": [YAZDI],
                                        "adt_push_source": [YAZDI], "adt_activate": [red]}, False),
            ("domain create sonucu BİLİNMİYOR (durma mesajında da)", "domain", dom,
             {"adt_get": [VAR], "adt_domain_create": [bilinmez]}, True),
        ):
            hat = SahteHat({**ortak, **yan})
            d, kod = self.kos(hat, tur, force_recreate=True, **kw)
            row = d["result"]["rows"][0]
            m = row.get("message") or ""
            ok = (kod == 1 and row["status"] == P.HATA and "adt_delete" in hat.araclar() and self.SILINDI in m
                  and (d["error"]["code"] == ("run_stopped" if durur else "partial_failure"))
                  and (not durur or self.SILINDI in str(d["result"].get("stopped"))))
            self.kaydet(f"26 force {ad}: silme doğrulandı → hata mesajı SİLİNDİ önekini taşır",
                        f"1 · hata · '{self.SILINDI[:30]}…'", f"{kod} · {d['error']['code']} · {m[:110]}", ok)
        hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [red]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), only="ZAXET_D_DURUM")
        m = d["result"]["rows"][0].get("message") or ""
        self.kaydet("26 KONTROL force yok, create hatası → SİLİNDİ öneki YOK", "SİLİNDİ yok", m[:110],
                    kod == 1 and "SİLİNDİ" not in m and "adt_delete" not in hat.araclar())

    # ── 8. gate-d3 bulgu 4: UTF-8 olmayan / ayrıştırılamayan CSV → csv_unreadable (çıkış 3) ────────────────
    def test_27_csv_okunamaz_kodlama(self):
        import csv as _csv
        bas = "name,datatype,length,decimals,description,fixed_values\n"
        for ad, tur, veri, kw in (
            ("cp1254 (TR Excel ANSI)", "domain", (bas + "ZAXET_D_BIR,CHAR,1,0,Durum alanı şğı,\n").encode("cp1254"), {}),
            ("UTF-16", "domain", (bas + "ZAXET_D_BIR,CHAR,1,0,Durum,\n").encode("utf-16"), {}),
            ("msag cp1254", "msag", "msgno,msgtext\n001,Kayıt bulunamadı ş\n".encode("cp1254"),
             {"msag_adi": "ZAXET_MSG", "msag_aciklama": "Mesajlar"}),
            ("csv.Error alan sınırı aşımı", "domain",
             (bas + 'ZAXET_D_BIR,CHAR,1,0,"' + "x" * (_csv.field_size_limit() + 1) + '",\n').encode("utf-8"), {}),
        ):
            hat = SahteHat()
            try:
                d, kod = self.kos(hat, tur, csv_yolu=self.dosya_bayt(veri), dry_run=True, **kw)
                gercek = f"{kod} · {d.get('error')}"
                ok = (kod == 3 and (d.get("error") or {}).get("code") == "csv_unreadable"
                      and not hat.kontroller and not hat.cagrilar)
            except Exception as exc:  # noqa: BLE001 — bugünkü davranış: istisna sızar
                gercek, ok = f"İSTİSNA {type(exc).__name__}: {str(exc)[:80]}", False
            self.kaydet(f"27 {ad} → 3 csv_unreadable (istisna sızmaz), 0 kontrol", "3 · csv_unreadable", gercek, ok)
        veri = ("﻿" + bas + "ZAXET_D_BIR,CHAR,1,0,Durum alanı,\n").replace("\n", "\r\n").encode("utf-8")
        hat = SahteHat()
        d, kod = self.kos(hat, csv_yolu=self.dosya_bayt(veri), dry_run=True)
        a = hat.kontroller[-1][1] if hat.kontroller else {}
        self.kaydet("27 KONTROL UTF-8 + BOM + CRLF → geçer (dry-run 0), ad/açıklama temiz", "0 · ZAXET_D_BIR · 'Durum alanı'",
                    f"{kod} · {a.get('name')} · {a.get('description')!r}",
                    kod == 0 and d["result"]["summary"][P.DRY_RUN] == 1 and a.get("name") == "ZAXET_D_BIR"
                    and a.get("description") == "Durum alanı")

    # ── 9. lider şartları: msag readback_failed mesajı · activation_failed inaktif-var notu ────────────────
    INAKTIF = "obje SAP'de İNAKTİF olarak var olabilir"

    def test_28_msag_readback_failed_mesaji(self):
        csv_m = self.dosya("msgno,msgtext\n001,Kayıt bulunamadı\n")
        var = (_p(result={"ok": True, "exists": True, "count": 1}), 0)
        rb = self._hatali({"ok": False, "error": "readback_failed", "changed": True,
                           "message": "PUT kabul edildi ama canlı geri okuma yapılamadı — yazım DOĞRULANMADI."},
                          "readback_failed")
        hat = SahteHat({"adt_msgclass_read": [var], "adt_msgclass_write": [rb]})
        d, kod = self.kos(hat, "msag", csv_yolu=csv_m, msag_adi="ZAXET_MSG", msag_aciklama="Mesajlar")
        row = d["result"]["rows"][0]
        m = row.get("message") or ""
        self.kaydet("28 msag readback_failed → çıkış 1 aynı · mesaj 'PUT kabul edildi, geri okuma doğrulanamadı; SAP'de "
                    "kontrol et', 'başarısız' DEMEZ", "1 · partial_failure · hata · mesaj",
                    f"{kod} · {d['error']['code']} · {row['status']} · {m[:120]}",
                    kod == 1 and d["error"]["code"] == "partial_failure" and row["status"] == P.HATA
                    and "PUT kabul edildi, geri okuma doğrulanamadı; SAP'de kontrol et" in m and "başarısız" not in m)

    def test_29_activation_failed_inaktif_var_notu(self):
        akt = self._hatali({"ok": False, "error": "activation_failed",
                            "message": "Aktivasyon BAŞARISIZ ya da DOĞRULANAMADI (alt katman hükmü)."},
                           "activation_failed")
        csv_e = self.dosya("name,description,primary_table,lock_mode,allow_rfc,field_names\n"
                           "EZAXET_BELGE,Belge kilidi,ZAXET_T_BELGE,E,false,MANDT;BELGE_NO\n")
        dz = self.root / "cds_akt"
        dz.mkdir(exist_ok=True)
        (dz / "ZAXET_I_AKT.cds").write_text("@EndUserText.label: 'Akt'\ndefine view entity ZAXET_I_AKT as select from t { key a }",
                                            encoding="utf-8")
        pull_ok = (_p(result={"ok": True, "exists": True, "source": "", "pull_state": "kaydedildi"}), 0)
        ic_akt = self._hatali({"ok": False, "steps": {"create": {"ok": True},
                                                       "activate": {"ok": False, "log": "",
                                                                    "error": {"ok": False, "error": "activation_failed",
                                                                              "message": "[400] errors"}}}},
                              "tool_failed")
        for ad, tur, kw, yan in (
            ("enqu aktive", "enqu", {"csv_yolu": csv_e},
             {"adt_get": [YOK], "adt_post_shell": [YAZDI], "adt_activate": [akt]}),
            ("cds aktive", "cds", {"kaynak_dizini": str(dz)},
             {"adt_get": [YOK, pull_ok], "adt_post_shell": [YAZDI], "adt_push_source": [YAZDI], "adt_activate": [akt]}),
            ("domain composite steps.activate.error activation_failed", "domain",
             {"csv_yolu": self.dosya(DOMAIN_CSV), "only": "ZAXET_D_DURUM"},
             {"adt_get": [YOK], "adt_domain_create": [ic_akt]}),
        ):
            hat = SahteHat(yan)
            d, kod = self.kos(hat, tur, **kw)
            m = d["result"]["rows"][0].get("message") or ""
            self.kaydet(f"29 {ad} → satır HATA, koşum sürer, mesaj inaktif-var notunu taşır", "1 · partial · İNAKTİF",
                        f"{kod} · {d['error']['code']} · {m[:120]}",
                        kod == 1 and d["error"]["code"] == "partial_failure" and self.INAKTIF in m)
        red = self._hatali({"ok": False, "error": "sap_error", "message": "[400] Bad Request"}, "sap_error")
        hat = SahteHat({"adt_get": [YOK], "adt_domain_create": [red]})
        d, kod = self.kos(hat, csv_yolu=self.dosya(DOMAIN_CSV), only="ZAXET_D_DURUM")
        m = d["result"]["rows"][0].get("message") or ""
        self.kaydet("29 KONTROL create sap_error [400] → inaktif notu YOK", "İNAKTİF yok", m[:100],
                    kod == 1 and self.INAKTIF not in m)


if __name__ == "__main__":
    unittest.main()
