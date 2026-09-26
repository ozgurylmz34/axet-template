# -*- coding: utf-8 -*-
"""PULL-BEFORE-EDIT (süreç içi, istemci yamalı; ağ yok).

`atom._get_client` sahte bir istemciyle değiştirilir. İstemci hangi çağrıların yapıldığını
kaydeder → "push'a hiç gidilmedi" iddiası çağrı listesiyle kanıtlanır.
"""
from __future__ import annotations

import json
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

AD = "ZAXET_PBE"
TIP = "program"          # reviewer zinciri yok (SKIP) → test hızlı; tip ABAP → Yasak B taraması koşar
KAYNAK = "REPORT zaxet_pbe.\nWRITE 'eski'.\n"


class Sahte:
    def __init__(self, canli: str | None, okuma_hatasi: Exception | None = None):
        self.canli = canli
        self.okuma_hatasi = okuma_hatasi
        self.cagri: list[str] = []

    def download_object(self, name, object_type=None, save_local=False):
        self.cagri.append("download")
        if self.okuma_hatasi:
            raise self.okuma_hatasi
        return self.canli

    def get_object_metadata(self, name, object_type=None):
        self.cagri.append("metadata")
        return "<meta/>"

    def push_object(self, object_name, object_type="class", transport=None, source_file=None):
        self.cagri.append("push")
        self.canli = Path(source_file).read_text(encoding="utf-8")
        return {"success": True, "source_uploaded": True, "activated": True, "readback_ok": True}

    def create_object(self, **kw):
        self.cagri.append("create")
        return "/sap/bc/adt/programs/programs/zaxet_yeni"


class PullBeforeEdit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="axet_pbe_"))
        cls._eski_env = {k: os.environ.get(k) for k in ("AXET_SAP_PROJECT_DIR", "ADT_SAP_TIER")}
        os.environ.pop("ADT_SAP_TIER", None)
        from sapadt.tools import atom
        from sapadt import pull_state
        cls.atom, cls.ps = atom, pull_state
        cls._eski_client = atom._get_client
        cls._sayac = 0

    @classmethod
    def tearDownClass(cls):
        cls.atom._get_client = cls._eski_client
        for k, v in cls._eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        type(self)._sayac += 1
        self.p = H.make_project(self.root, f"p{self._sayac}")
        os.environ["AXET_SAP_PROJECT_DIR"] = str(self.p)

    def istemci(self, sahte: Sahte):
        self.atom._get_client = lambda: sahte
        return sahte

    def durum(self) -> dict:
        f = self.p / ".axet-code" / "sap-pull-state.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}

    def kaydet(self, ad, beklenen, gercek, ok):
        H.kaydet(f"PBE {ad}", beklenen, gercek, ok)
        self.assertTrue(ok, f"{ad}: {gercek}")

    def test_1_kayit_yok_red(self):
        s = self.istemci(Sahte(KAYNAK))
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'yeni'.\n")
        self.kaydet("kayıt yok → red, istemciye hiç gidilmedi", "pull_before_edit_missing · çağrı=[]",
                    f"{r.get('error')} · çağrı={s.cagri}", r.get("error") == "pull_before_edit_missing" and s.cagri == [])

    def test_2_kayit_var_canli_ayni_gecer_ve_kayit_guncellenir(self):
        s = self.istemci(Sahte(KAYNAK.replace("\n", "\r\n")))     # CRLF canlı ↔ LF kıyas normalize
        g = self.atom.adt_get(AD, TIP)
        k = self.durum().get(f"{TIP}:{AD}") or {}
        self.kaydet("adt_get kaynağı okuyunca kayıt yazılır", "pull_state=kaydedildi + sha",
                    f"{g.get('pull_state')} · sha={str(k.get('sha256'))[:12]}",
                    g.get("pull_state") == "kaydedildi" and k.get("sha256") == self.ps.ozet(KAYNAK))
        s.cagri.clear()
        yeni = KAYNAK + "WRITE 'yeni'.\n"
        r = self.atom.adt_push_source(AD, TIP, yeni)
        k2 = self.durum().get(f"{TIP}:{AD}") or {}
        ok = (r.get("ok") is True and s.cagri[:1] == ["download"] and "push" in s.cagri
              and s.cagri.index("download") < s.cagri.index("push"))
        self.kaydet("kayıt var + canlı aynı → push geçer (önce canlı okuma)", "ok · download<push",
                    f"ok={r.get('ok')} err={r.get('error')} çağrı={s.cagri}", ok)
        self.kaydet("push sonrası kayıt yeni canlı özetle güncellendi", "pull_state=guncellendi · sha=yeni",
                    f"{r.get('pull_state')} · eşit={k2.get('sha256') == self.ps.ozet(yeni)}",
                    r.get("pull_state") == "guncellendi" and k2.get("sha256") == self.ps.ozet(yeni))
        g2 = self.atom.adt_get(AD, TIP, include_source=False)
        self.assertNotIn("pull_state", g2)

    def test_3_kayit_var_canli_farkli_red(self):
        s = self.istemci(Sahte(KAYNAK))
        self.atom.adt_get(AD, TIP)
        s.canli = KAYNAK + "WRITE 'başkası değiştirdi'.\n"
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'benim'.\n")
        self.kaydet("kayıt var + canlı farklı → red, push YOK", "source_changed_since_pull · push yok",
                    f"{r.get('error')} · çağrı={s.cagri}",
                    r.get("error") == "source_changed_since_pull" and "push" not in s.cagri)

    def test_4_canli_okuma_basarisiz_red(self):
        s = self.istemci(Sahte(KAYNAK))
        self.atom.adt_get(AD, TIP)
        s.okuma_hatasi = ConnectionError("bağlantı yok")
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'x'.\n")
        self.kaydet("canlı okuma başarısız → sessiz geçiş YOK", "pull_live_read_failed · push yok",
                    f"{r.get('error')} · çağrı={s.cagri}",
                    r.get("error") == "pull_live_read_failed" and "push" not in s.cagri)

    def test_5_bozuk_durum_dosyasi(self):
        s = self.istemci(Sahte(KAYNAK))
        (self.p / ".axet-code").mkdir(exist_ok=True)
        (self.p / ".axet-code" / "sap-pull-state.json").write_text("{bozuk", encoding="utf-8")
        r = self.atom.adt_push_source(AD, TIP, KAYNAK)
        self.kaydet("bozuk pull-state dosyası → red", "pull_state_unreadable · çağrı=[]",
                    f"{r.get('error')} · çağrı={s.cagri}", r.get("error") == "pull_state_unreadable" and s.cagri == [])

    # ── Z87 ⓑ+ (2026-09-24): yerel kopya çekilen kaynaktan türemediyse canlı satırlar sessizce kaybolur.
    # Kıyas mekanizması bunu YAKALAMAZ (canlı değişmedi); push yazmadan önce canlı ↔ yeni kaynak farkını
    # hesaplar ve silinen satır varsa UYARI verir. Yazma DEVAM eder (sert red kullanıcı kararıyla YOK).
    AB = KAYNAK + "WRITE 'B'.\n"

    def test_7_Z87_bayat_yerel_kopya_uyari_verir_yazma_surer(self):
        s = self.istemci(Sahte(self.AB))
        self.atom.adt_get(AD, TIP)                       # canlı A+B çekildi
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, KAYNAK)   # eski yerel "A" gönderiliyor
        u = r.get("removed_lines_warning") or {}
        self.kaydet("Z87 canlı A+B → yeni A: uyarı var (removed=1, örnek B), yazma yapıldı",
                    "ok · push · removed=1 · sample∋WRITE 'B' · warning metni",
                    f"ok={r.get('ok')} · çağrı={s.cagri} · uyarı={u} · warning={bool(r.get('warning'))}",
                    r.get("ok") is True and "push" in s.cagri and u.get("removed") == 1
                    and any("WRITE 'B'" in x for x in u.get("sample") or []) and bool(r.get("warning"))
                    and s.canli == KAYNAK)

    def test_8_Z87_KONTROL_ekleme_ve_esitlik_uyari_yok(self):
        s = self.istemci(Sahte(KAYNAK))
        self.atom.adt_get(AD, TIP)
        r1 = self.atom.adt_push_source(AD, TIP, self.AB)            # yalnız ekleme
        self.atom.adt_get(AD, TIP)
        r2 = self.atom.adt_push_source(AD, TIP, s.canli.replace("\n", "\r\n"))  # canlı = yeni (CRLF farkı)
        self.kaydet("Z87 KONTROL: ekleme ve eşitlik (CRLF farkı dahil) → uyarı alanı YOK",
                    "ok×2 · uyarı yok×2",
                    f"ok={r1.get('ok')},{r2.get('ok')} · uyarı={'removed_lines_warning' in r1},"
                    f"{'removed_lines_warning' in r2}",
                    r1.get("ok") is True and r2.get("ok") is True
                    and "removed_lines_warning" not in r1 and "removed_lines_warning" not in r2)

    def test_9_Z87_uyari_yazmadan_once_hesaplanir(self):
        s = self.istemci(Sahte(self.AB))
        self.atom.adt_get(AD, TIP)

        def patlayan(**kw):
            s.cagri.append("push")
            raise RuntimeError("ağ koptu")
        s.push_object = patlayan
        r = self.atom.adt_push_source(AD, TIP, KAYNAK)
        u = r.get("removed_lines_warning") or {}
        self.kaydet("Z87 push istisna ile düşse de uyarı yanıtta (yazmadan önce hesaplandı)",
                    "ok:false · removed=1", f"ok={r.get('ok')} err={r.get('error')} · uyarı={u}",
                    r.get("ok") is False and u.get("removed") == 1)

    # ── Z99 (2026-09-26): eski kıyas `SequenceMatcher(autojunk=False)` süre sınırsızdı (10.000 satır, yarısı
    # değişik ≈ 10 sn ölçüldü; ters/yinelenen satırlarda dakikalar). Yeni kıyas çoklu-küme farkı (O(n)).
    # Girdi aranan sonucu İÇERMEZ: silinen/eklenen sayısı üretimden bağımsız olarak hesaplanıp kıyaslanır.
    def test_10_Z99_buyuk_girdi_sure_siniri(self):
        import time
        n = 10_000
        eski = [f"  lv_{i} = {i}." for i in range(n)]
        yeni = [x + ' " d' if i % 2 else x for i, x in enumerate(eski)]   # her ikinci satır değişti
        t0 = time.perf_counter()
        r = self.atom._silinen_satir_uyarisi("\n".join(eski), "\n".join(yeni))
        sure = time.perf_counter() - t0
        u = (r or {}).get("removed_lines_warning") or {}
        self.kaydet("Z99 10.000 satır (yarısı değişik) < 1 sn, sayılar doğru",
                    "sure<1 · removed=5000 · added=5000", f"sure={sure:.2f} · {u.get('removed')}/{u.get('added')}",
                    sure < 1.0 and u.get("removed") == n // 2 and u.get("added") == n // 2)

    def test_11_Z99_yer_degistiren_satir_silinmis_sayilmaz_yinelenen_sayilir(self):
        a = "REPORT z.\nWRITE 'a'.\nWRITE 'b'.\nENDIF.\nENDIF.\n"
        tasinan = "REPORT z.\nWRITE 'b'.\nWRITE 'a'.\nENDIF.\nENDIF.\n"     # yer değişti, hiçbir satır kaybolmadı
        eksik = "REPORT z.\nWRITE 'a'.\nWRITE 'b'.\nENDIF.\n"                # yinelenen ENDIF'in BİRİ kayboldu
        r1 = self.atom._silinen_satir_uyarisi(a, tasinan)
        r2 = self.atom._silinen_satir_uyarisi(a, eksik)
        u2 = (r2 or {}).get("removed_lines_warning") or {}
        self.kaydet("Z99 yeri değişen satır → uyarı YOK · yinelenen satırın biri eksik → removed=1",
                    "r1=None · removed=1 · sample=[ENDIF.]", f"r1={r1} · {u2}",
                    r1 is None and u2.get("removed") == 1 and u2.get("added") == 0
                    and u2.get("sample") == ["ENDIF."])

    def test_12_Z99_ornek_canli_sirasiyla(self):
        eski = "\n".join(f"WRITE {i}." for i in range(10))
        yeni = "\n".join(f"WRITE {i}." for i in range(10) if i not in (7, 2, 9, 4, 5, 8))
        u = (self.atom._silinen_satir_uyarisi(eski, yeni) or {}).get("removed_lines_warning") or {}
        self.kaydet("Z99 örnek (≤5) canlıdaki sırayla", "removed=6 · sample=2,4,5,7,8",
                    f"{u}", u.get("removed") == 6
                    and u.get("sample") == ["WRITE 2.", "WRITE 4.", "WRITE 5.", "WRITE 7.", "WRITE 8."])

    # ── Z142ⓐ (2026-09-26): adt_get(output_path) — kaynak yerel paket klasörüne iner. Yol kuralı adt_pretty_print
    # ile TEK kaynaktan (sapadt.project.yerel_kaynak_yolu); geçersiz yolda SAP'ye hiç gidilmez.
    def test_13_Z142a_adt_get_dosyaya_yazar(self):
        canli = "REPORT zaxet_pbe.\r\nWRITE 'ğüşiöç'.\r\n"
        s = self.istemci(Sahte(canli))
        r = self.atom.adt_get(AD, TIP, output_path="SOURCE_CODES/SD/ZXX001/prog/zaxet_pbe.prog.abap")
        f = self.p / "SOURCE_CODES/SD/ZXX001/prog/zaxet_pbe.prog.abap"
        k = self.durum().get(f"{TIP}:{AD}") or {}
        self.kaydet("Z142ⓐ adt_get output_path → dosya = canlı bayt (UTF-8, satır sonu çevrilmez), source yanıtta yok, "
                    "pull kaydı yazıldı", "written · bayt eşit · source yok · pull",
                    f"ok={r.get('ok')} written={r.get('written')} yol={r.get('output_path')} "
                    f"eşit={f.is_file() and f.read_bytes() == canli.encode('utf-8')} source={'source' in r} "
                    f"pull={r.get('pull_state')}",
                    r.get("ok") is True and r.get("written") is True
                    and r.get("output_path") == "SOURCE_CODES/SD/ZXX001/prog/zaxet_pbe.prog.abap"
                    and f.read_bytes() == canli.encode("utf-8") and "source" not in r
                    and r.get("pull_state") == "kaydedildi" and k.get("sha256") == self.ps.ozet(canli)
                    and s.cagri[:1] == ["download"])

    def test_14_Z142a_gecersiz_yol_ag_yok(self):
        s = self.istemci(Sahte(KAYNAK))
        (self.p / "var.abap").write_text("eski", encoding="utf-8")
        disari = str(self.root / "disari.abap")
        vakalar = {"../kardes.abap": ("invalid_argument", TIP, True), disari: ("invalid_argument", TIP, True),
                   ".conn_adt": ("invalid_argument", TIP, True), "sap-project.json": ("invalid_argument", TIP, True),
                   "notlar/x.txt": ("invalid_argument", TIP, True), ".AXET-CODE/y.abap": ("invalid_argument", TIP, True),
                   "": ("invalid_argument", TIP, True), "a.abap": ("invalid_argument", TIP, False),   # include_source=false
                   "m.xml": ("invalid_argument", "msag", True), "k.xml": ("invalid_argument", "enqu", True),
                   "var.abap": ("output_exists", TIP, True)}
        sonuc = {}
        for yol, (_, tip, kaynakli) in vakalar.items():
            s.cagri.clear()
            r = self.atom.adt_get(AD, tip, include_source=kaynakli, output_path=yol)
            sonuc[yol] = (r.get("error"), len(s.cagri))
        ok = all(sonuc[y] == (v[0], 0) for y, v in vakalar.items())
        ok = ok and (self.p / "var.abap").read_text(encoding="utf-8") == "eski"
        r2 = self.atom.adt_get(AD, TIP, output_path="var.abap", overwrite=True)
        ok = ok and r2.get("written") is True and (self.p / "var.abap").read_text(encoding="utf-8") == KAYNAK
        self.kaydet("Z142ⓐ kök dışı/uzantı/.axet-code/include_source=false/msag/enqu/var olan → red, SAP'ye 0 istek; "
                    "overwrite=true yazar", "11/11 red · overwrite yazar", f"{sonuc} · overwrite={r2.get('written')}", ok)

    def test_15_Z142a_obje_yok_dosya_yazilmaz(self):
        from sap_adt_lib import SAPObjectNotFoundError  # type: ignore
        self.istemci(Sahte(None, okuma_hatasi=SAPObjectNotFoundError("yok")))
        r = self.atom.adt_get(AD, TIP, output_path="yok.abap")
        self.kaydet("Z142ⓐ obje yok → dosya yazılmaz", "exists:false · written:false · dosya yok",
                    f"ok={r.get('ok')} exists={r.get('exists')} written={r.get('written')} "
                    f"dosya={(self.p / 'yok.abap').exists()}",
                    r.get("exists") is False and r.get("written") is False and not (self.p / "yok.abap").exists())

    # ── Z142ⓒ (2026-09-26): push kaynağı yerel dosyadan (`source_path`). İndir (output_path) → düzenle → geri yaz.
    def test_16_Z142c_indir_duzenle_dosyadan_push(self):
        s = self.istemci(Sahte(self.AB))
        g = self.atom.adt_get(AD, TIP, output_path="src/zaxet_pbe.prog.abap")
        f = self.p / "src" / "zaxet_pbe.prog.abap"
        beklenen_ek = "WRITE 'C'.\n"
        f.write_bytes(b"\xef\xbb\xbf" + (f.read_text(encoding="utf-8") + beklenen_ek).encode("utf-8"))  # BOM'lu
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, source_path="src/zaxet_pbe.prog.abap")
        self.kaydet("Z142ⓒ adt_get(output_path) → dosyada düzenle → push(source_path): SAP'ye giden = dosya (BOM'suz)",
                    "ok · push · canlı=A+B+C · uyarı yok · source_path",
                    f"get={g.get('written')} ok={r.get('ok')} err={r.get('error')} çağrı={s.cagri} "
                    f"canlı_eşit={s.canli == self.AB + beklenen_ek} "
                    f"uyarı={'removed_lines_warning' in r} yol={r.get('source_path')}",
                    g.get("written") is True and r.get("ok") is True and "push" in s.cagri
                    and s.canli == self.AB + beklenen_ek and "removed_lines_warning" not in r
                    and r.get("source_path") == "src/zaxet_pbe.prog.abap")

    def test_17_Z142c_bayat_dosya_uyarisi_korunur(self):
        s = self.istemci(Sahte(KAYNAK))
        self.atom.adt_get(AD, TIP, output_path="src/eski.prog.abap")      # dosya = "A"
        s.canli = self.AB                                                  # canlı sonra A+B oldu
        self.atom.adt_get(AD, TIP)                                         # taban yeniden çekildi, dosya YENİLENMEDİ
        r = self.atom.adt_push_source(AD, TIP, source_path="src/eski.prog.abap")
        u = r.get("removed_lines_warning") or {}
        self.kaydet("Z142ⓒ bayat dosyadan push → Z87 removed_lines_warning korunur", "removed=1 · sample∋B",
                    f"ok={r.get('ok')} · {u}", u.get("removed") == 1 and any("'B'" in x for x in u.get("sample") or []))

    def test_18_Z142c_argüman_reddi_ag_yok(self):
        s = self.istemci(Sahte(KAYNAK))
        (self.p / "src").mkdir()
        (self.p / "src" / "bos.prog.abap").write_text("  \n", encoding="utf-8")
        (self.p / "src" / "latin.prog.abap").write_bytes("WRITE 'ğ'.".encode("cp1254"))
        (self.p / "src" / "kirli.prog.abap").write_text(
            "REPORT z.\nUPDATE vbak SET netwr = 0 WHERE vbeln = '1'.\n", encoding="utf-8")
        vakalar = {"ikisi": ({"source": KAYNAK, "source_path": "src/bos.prog.abap"}, "invalid_argument"),
                   "hiçbiri": ({}, "invalid_argument"),
                   ".conn_adt": ({"source_path": ".conn_adt"}, "invalid_argument"),
                   "kök dışı": ({"source_path": "../x.abap"}, "invalid_argument"),
                   ".axet-code": ({"source_path": ".axet-code/x.abap"}, "invalid_argument"),
                   "yok": ({"source_path": "src/yok.prog.abap"}, "source_file_missing"),
                   "boş": ({"source_path": "src/bos.prog.abap"}, "invalid_argument"),
                   "UTF-8 değil": ({"source_path": "src/latin.prog.abap"}, "invalid_argument"),
                   "std DML (2. katman)": ({"source_path": "src/kirli.prog.abap"}, "guardrail_violation")}
        sonuc = {}
        for ad, (args, _) in vakalar.items():
            s.cagri.clear()
            r = self.atom.adt_push_source(AD, TIP, **args)
            sonuc[ad] = (r.get("error"), r.get("code"), len(s.cagri))
        ok = all(sonuc[a][0] == v[1] and sonuc[a][2] == 0 for a, v in vakalar.items())
        ok = ok and sonuc["std DML (2. katman)"][1] == "ADR_0005_B"
        self.kaydet("Z142ⓒ argüman/yol/dosya reddi + 2. katman Yasak B dosya metnini tarar → SAP'ye 0 istek",
                    "9/9 red · çağrı=0", sonuc, ok)

    # ── Z147 (2026-09-26): push yanıtında yazılan objenin inaktif kayıt sayısı (bağımsız worklist sondası).
    def _wl_istemci(self, worklist_metni, push_sonucu=None, durum=200):
        s = self.istemci(Sahte(KAYNAK))
        s.url = "https://example.invalid"

        class _Y:
            def __init__(self):
                self.status_code, self.text, self.headers = durum, worklist_metni, {}

        class _Oturum:
            verify = False

            def get(self_o, url, **kw):
                s.cagri.append("worklist")
                return _Y()
        s.session = _Oturum()
        if push_sonucu is not None:
            def push(object_name, object_type="class", transport=None, source_file=None):
                s.cagri.append("push")
                s.canli = Path(source_file).read_text(encoding="utf-8")
                return dict(push_sonucu)
            s.push_object = push
        return s

    @staticmethod
    def _wl(*adlar):
        ioc, core = "http://www.sap.com/abapxml/inactiveCtsObjects", "http://www.sap.com/adt/core"
        girdi = "".join(f'<ioc:entry><ioc:object ioc:user="TESTUSER_A" ioc:deleted="false"><ioc:ref '
                        f'adtcore:uri="/sap/bc/adt/programs/programs/{a.lower()}" adtcore:type="PROG/P" '
                        f'adtcore:name="{a}" xmlns:adtcore="{core}"/></ioc:object><ioc:transport/></ioc:entry>'
                        for a in adlar)
        return f'<?xml version="1.0" encoding="utf-8"?><ioc:inactiveObjects xmlns:ioc="{ioc}">{girdi}</ioc:inactiveObjects>'

    def test_19_Z147_push_inaktif_sayisi(self):
        sonuc = {}
        yuklendi_aktif_degil = {"success": True, "source_uploaded": True, "activated": False, "readback_ok": None}
        for ad, wl, push_s, durum in (("temiz", self._wl("ZAXET_BASKA"), None, 200),
                                      ("listede", self._wl("ZAXET_BASKA", AD), None, 200),
                                      ("olculemedi", "x", None, 500),
                                      ("aktive-iddiasi-yok", self._wl(AD), yuklendi_aktif_degil, 200)):
            s = self._wl_istemci(wl, push_s, durum)
            self.atom.adt_get(AD, TIP)
            s.cagri.clear()
            r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'z'.\n")
            sonuc[ad] = (r.get("ok"), r.get("inactive_count"), r.get("error"), bool(r.get("inactive_warning")),
                         bool(r.get("inactive_notice")), s.cagri.index("push") < s.cagri.index("worklist"))
        beklenen = {"temiz": (True, 0, None, False, False, True),
                    "listede": (False, 1, "activation_not_executed", False, False, True),
                    "olculemedi": (True, None, None, True, False, True),
                    "aktive-iddiasi-yok": (True, 1, None, False, True, True)}
        self.kaydet("Z147 push: temiz=0 · aktive dendi+listede → ok false · ölçülemedi=null+uyarı · iddia yok → bilgi",
                    str(beklenen), sonuc, sonuc == beklenen)

    def test_20_Z147_yukleme_yoksa_sonda_yok(self):
        s = self._wl_istemci(self._wl(AD), {"success": False, "source_uploaded": False, "activated": False,
                                            "error": "kilit alınamadı"})
        self.atom.adt_get(AD, TIP)
        s.cagri.clear()
        r = self.atom.adt_push_source(AD, TIP, KAYNAK + "WRITE 'z'.\n")
        self.kaydet("Z147 yükleme olmadıysa sonda koşmaz (yazılan obje yok)", "ok false · alan yok · worklist yok",
                    f"ok={r.get('ok')} alan={'inactive_count' in r} çağrı={s.cagri}",
                    r.get("ok") is False and "inactive_count" not in r and "worklist" not in s.cagri)

    # ── L5 bug gate (2026-09-26): `.axetcode-denylist` dizinleri output_path/source_path ile delinemez (iki yön).
    def test_21_denylist_okuma_yazma_reddi_ag_yok(self):
        s = self.istemci(Sahte(KAYNAK))
        (self.p / ".axetcode-denylist").write_text("# yorum\n.conn_adt\nsecrets\nconn/\nhenuz_yok\n", encoding="utf-8")
        for d in ("conn", "secrets/alt", "src"):
            (self.p / d).mkdir(parents=True)
        (self.p / "conn" / "gizli.prog.abap").write_text(KAYNAK, encoding="utf-8")
        (self.p / "secrets" / "alt" / "k.prog.abap").write_text(KAYNAK, encoding="utf-8")
        self.atom.adt_get(AD, TIP)                                          # push için pull kaydı
        red = {}
        for yol in ("conn/yeni.prog.abap", "secrets/alt/y.prog.abap", "conn/alt/derin.prog.abap",
                    "./conn/../conn/z.prog.abap"):
            s.cagri.clear()
            r = self.atom.adt_get(AD, TIP, output_path=yol)
            red[f"get {yol}"] = (r.get("error"), len(s.cagri), (self.p / yol).is_file())
        for yol in ("conn/gizli.prog.abap", "secrets/alt/k.prog.abap"):
            s.cagri.clear()
            r = self.atom.adt_push_source(AD, TIP, source_path=yol)
            red[f"push {yol}"] = (r.get("error"), len(s.cagri), False)
        if os.name == "nt":   # Windows dosya sistemi harf duyarsız → `CONN/` aynı klasör
            s.cagri.clear()
            r = self.atom.adt_get(AD, TIP, output_path="CONN/b.prog.abap")
            red["get CONN/ (nt)"] = (r.get("error"), len(s.cagri), (self.p / "conn" / "b.prog.abap").is_file())
            # Var olmayan klasörde `resolve()` harfi düzeltmez → karşılaştırma `normcase` ister.
            s.cagri.clear()
            r = self.atom.adt_get(AD, TIP, output_path="HENUZ_YOK/c.prog.abap")
            red["get HENUZ_YOK/ (nt)"] = (r.get("error"), len(s.cagri),
                                          (self.p / "henuz_yok" / "c.prog.abap").is_file())
        # Kontrol grubu: önek sınırı (`connx` ≠ `conn`), sıradan klasör; denylist dosyası yokken bugünkü davranış.
        g1 = self.atom.adt_get(AD, TIP, output_path="connx/a.prog.abap")
        g2 = self.atom.adt_get(AD, TIP, output_path="src/b.prog.abap")
        (self.p / ".axetcode-denylist").unlink()
        g3 = self.atom.adt_get(AD, TIP, output_path="conn/yok_iken.prog.abap")
        ok = (all(v == ("invalid_argument", 0, False) for v in red.values())
              and g1.get("written") is True and g2.get("written") is True and g3.get("written") is True)
        self.kaydet("L5 denylist: conn/ secrets altı get(output_path)+push(source_path) red, SAP'ye 0 istek · "
                    "connx/src yazılır · denylist yoksa conn/ yazılır",
                    f"{len(red)} red · 3 yazıldı",
                    f"{red} · yazıldı={[g.get('written') for g in (g1, g2, g3)]}", ok)

    def test_22_denylist_okunamazsa_fail_closed(self):
        self.istemci(Sahte(KAYNAK))
        (self.p / ".axetcode-denylist").write_bytes(b"\xff\xfe\x00conn\n")      # UTF-8 değil
        r = self.atom.adt_get(AD, TIP, output_path="src/c.prog.abap")
        self.kaydet("L5 denylist okunamıyorsa yol reddedilir (okunamadı ≠ boş liste)", "invalid_argument · dosya yok",
                    f"{r.get('error')} · {(self.p / 'src' / 'c.prog.abap').is_file()}",
                    r.get("error") == "invalid_argument" and "denylist" in (r.get("message") or "")
                    and not (self.p / "src" / "c.prog.abap").is_file())

    def test_6_post_shell_etkilenmez(self):
        s = self.istemci(Sahte(None))
        r = self.atom.adt_post_shell("program", "ZAXET_YENI", "$TMP", "TESTK900001", "Test programı")
        self.kaydet("adt_post_shell pull kontrolüne girmez", "ok · çağrı=[create]",
                    f"ok={r.get('ok')} · çağrı={s.cagri}", r.get("ok") is True and s.cagri == ["create"])


if __name__ == "__main__":
    unittest.main()
