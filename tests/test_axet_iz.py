# -*- coding: utf-8 -*-
"""axet_iz.py — aXet oturum izi aracının KALİBRASYONU.

Aracın işi "model ne dedi" değil "motor ne kaydetti"dir; hükmü (§0 sırası VAR/YOK) başka ölçümlerin (Z103/Z105
canlı turları) dayanağıdır. Bu yüzden aracın körleşmediği BİLİNEN iki oturumla ölçülür:

  · kanaryalı oturum  → session_brief çağrısı ilk model metninden ÖNCE + ilk satır kanarya ⇒ hüküm VAR
  · kanaryasız oturum → ilk model metni kanaryasız, session_brief sonra ⇒ hüküm YOK
  · sırası bozuk oturum → kanarya VAR ama session_brief ilk metinden SONRA ⇒ hüküm YOK

Üçü BİRLİKTE koşulur: yalnız VAR'ı ölçen takım "her şeye VAR diyen" aracı, yalnız YOK'u ölçen takım "her şeye
YOK diyen" aracı yeşil geçirir. Üçüncü vaka sıra kontrolünün kendisini ölçer: kanarya denetimi sağlamken sıra
denetimi kaldırılırsa YALNIZ o kırılır.

Fikstür şeması gerçek bir aXet DB'sinden ÖLÇÜLDÜ (2026-09-26, test projesi; yalnız `sqlite_master` + JSON anahtar
adları okundu, içerik okunmadı): sessions/messages/read_files/files CREATE cümleleri aşağıda birebirdir. Zaman
damgaları şemadaki "milliseconds" yorumuna RAĞMEN saniyedir (ölçüldü: min/max ≈ 1.79e9) — fikstür de saniye yazar.
Log satırı biçimi aynı ölçümden: JSON satır, `time` ISO-8601 + ofset, izin kararlarında `session_id` DB'deki oturum
kimliğiyle birebir (237/237).

Ölçüm gerçek giriş noktasından yapılır (betik `subprocess` ile çağrılır); fikstür repo DIŞINDAKİ geçici köke yazılır.

KAPSAM — bakılmayan: gerçek bir aXet sürümünün şemayı değiştirip değiştirmediği (araç eksik tablo/kolonda 2 döner,
bu dosya o dalı sentetik ölçer) · DB'nin salt-okur açıldığı (okuma normal bağlantıda da dosyayı değiştirmediği için
ayırt edici bir test kurulamadı; ölçülmedi) · Windows dışı yol biçimleri · çok büyük DB'lerde hız.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import unittest
from pathlib import Path

from _helpers import AXET_HOME, GeciciTest

BETIK = AXET_HOME / "maintenance" / "axet_iz.py"

SEMA = [
    """CREATE TABLE sessions (
    id TEXT PRIMARY KEY, parent_session_id TEXT, title TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0, prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0.0,
    updated_at INTEGER NOT NULL, created_at INTEGER NOT NULL,
    summary_message_id TEXT, todos TEXT, forked_from_session_id TEXT)""",
    """CREATE TABLE files (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, path TEXT NOT NULL, content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
    UNIQUE(path, session_id, version))""",
    """CREATE TABLE messages (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, parts TEXT NOT NULL default '[]',
    model TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, finished_at INTEGER,
    provider TEXT, is_summary_message INTEGER DEFAULT 0 NOT NULL)""",
    """CREATE TABLE read_files (
    session_id TEXT NOT NULL, path TEXT NOT NULL, read_at INTEGER NOT NULL, PRIMARY KEY (path, session_id))""",
]

KANARYA = "[AXET-CORE-0.8.2 · SAP: YOK · proje: PRJ-DENEME · proje hafızası: YOK]"
T0 = int(datetime.datetime(2026, 9, 20, 10, 0, 0).timestamp())   # yerel saat; araç da yerel basar

S_VAR = "aaaa1111-kanaryali"
S_YOK = "bbbb2222-kanaryasiz"
S_SIRA = "cccc3333-sirasibozuk"
S_ALT = "dddd4444-altoturum"


def _metin(t: str) -> dict:
    return {"type": "text", "data": {"text": t}}


def _cagri(ad: str, girdi: dict) -> dict:
    return {"type": "tool_call", "data": {"id": "c1", "name": ad, "input": json.dumps(girdi), "finished": True}}


def _sonuc(ad: str, icerik: str, hata: bool = False) -> dict:
    return {"type": "tool_result", "data": {"tool_call_id": "c1", "name": ad, "content": icerik, "is_error": hata}}


BRIEF = _cagri("bash", {"command": "python \"<AXET_HOME>/scripts/session_brief.py\""})


class AxetIzKalibrasyon(GeciciTest):

    def setUp(self) -> None:
        super().setUp()
        if not BETIK.is_file():
            self.skipTest("maintenance/axet_iz.py yok (public sürümde maintenance/ dışlanır)")

    # --- fikstür -------------------------------------------------------------------------------------------
    def kur(self, proje: Path | None = None) -> Path:
        """<tmp>/proje/.axet-code/{axet-code.db, logs/axet-code.log}: üç kök + bir alt oturum."""
        proje = proje or self.tmp / "proje"
        veri = proje / ".axet-code"
        (veri / "logs").mkdir(parents=True)
        c = sqlite3.connect(veri / "axet-code.db")
        for s in SEMA:
            c.execute(s)
        oturumlar = [(S_VAR, None, "kanaryali oturum", T0), (S_YOK, None, "kanaryasiz oturum", T0 + 100),
                     (S_SIRA, None, "sirasi bozuk oturum", T0 + 200), (S_ALT, S_VAR, "alt ajan", T0 + 20)]
        for sid, ust, baslik, t in oturumlar:
            c.execute("insert into sessions(id,parent_session_id,title,updated_at,created_at) values (?,?,?,?,?)",
                      (sid, ust, baslik, t, t))
        mesajlar = [
            (S_VAR, "user", [_metin("merhaba")], T0),
            (S_VAR, "assistant", [BRIEF], T0 + 1),
            (S_VAR, "tool", [_sonuc("bash", "OZET-SATIRI")], T0 + 2),
            (S_VAR, "assistant", [_metin(KANARYA + "\nözet satırı")], T0 + 3),
            (S_VAR, "assistant", [_cagri("view", {"file_path": "AGENTS.md"})], T0 + 4),
            (S_VAR, "tool", [_sonuc("view", "reddedildi", hata=True)], T0 + 5),
            (S_ALT, "user", [_metin("alt ajan brifingi")], T0 + 21),
            (S_ALT, "assistant", [_metin("ALT-AJAN-CEVABI")], T0 + 22),
            (S_YOK, "user", [_metin("%guncelle-proje")], T0 + 100),
            (S_YOK, "assistant", [_metin("Hemen başlıyorum.")], T0 + 101),
            (S_YOK, "assistant", [BRIEF], T0 + 102),
            (S_SIRA, "user", [_metin("merhaba")], T0 + 200),
            (S_SIRA, "assistant", [_metin(KANARYA)], T0 + 201),
            (S_SIRA, "assistant", [BRIEF], T0 + 202),
        ]
        for i, (sid, rol, parcalar, t) in enumerate(mesajlar):
            c.execute("insert into messages(id,session_id,role,parts,created_at,updated_at) values (?,?,?,?,?,?)",
                      (f"m{i}", sid, rol, json.dumps(parcalar), t, t))
        c.execute("insert into read_files values (?,?,?)", (S_VAR, "OKUNAN-DOSYA.md", T0 + 4))
        c.execute("insert into read_files values (?,?,?)", (S_ALT, "ALT-OKUNAN.md", T0 + 22))
        c.execute("insert into files(id,session_id,path,content,created_at,updated_at) values (?,?,?,?,?,?)",
                  ("f1", S_VAR, "YAZILAN-DOSYA.md", "x", T0 + 4, T0 + 4))
        c.commit()
        c.close()

        def satir(t: int, **alan) -> str:
            zaman = datetime.datetime.fromtimestamp(t).astimezone().isoformat()
            return json.dumps({"time": zaman, "level": "INFO", **alan}, ensure_ascii=False)
        log = [
            satir(T0 + 4, msg="Permission decision", decision="deny", session_id=S_VAR, tool="view",
                  pattern="KANARYALI-RET"),
            # Aynı saniyede BAŞKA oturumun ret satırı: zaman penceresine düşer ama kimliği farklıdır.
            satir(T0 + 4, msg="Permission decision", decision="deny", session_id=S_YOK, tool="bash",
                  pattern="BASKA-OTURUM-RET"),
            # Oturum kimliği taşımayan satır: yalnız zaman penceresiyle eşlenebilir (yedek yol).
            satir(T0 + 5, msg="Sandbox blocked", component="sandbox", pattern="KIMLIKSIZ-RET"),
            "bozuk satır — JSON değil",
        ]
        (veri / "logs" / "axet-code.log").write_text("\n".join(log) + "\n", encoding="utf-8")
        return proje

    def kos(self, *args: str, cwd: Path | None = None):
        r = self.calistir(BETIK, *args, cwd=cwd, scripts_dir=BETIK.parent)
        return r.returncode, self.cikti(r)

    # --- §0 hükmü: kalibrasyon üçlüsü ------------------------------------------------------------------------
    def test_kanaryali_oturumda_sifir_sirasi_var(self):
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "aaaa")
        self.assertIn("§0 sırası: VAR", out, out)
        self.assertEqual(rc, 0, out)

    def test_kanaryasiz_oturumda_sifir_sirasi_yok(self):
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "bbbb")
        self.assertIn("§0 sırası: YOK", out, out)
        self.assertIn("kanarya yok", out, out)
        self.assertEqual(rc, 1, out)

    def test_brief_ilk_metinden_sonra_gelirse_sira_yok(self):
        """Kanarya VAR ama session_brief ilk model metninden SONRA: sıra denetimi tek başına YOK demeli."""
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "cccc")
        self.assertIn("§0 sırası: YOK", out, out)
        self.assertIn("session_brief ilk metinden sonra", out, out)
        self.assertEqual(rc, 1, out)

    # --- özet listesi ----------------------------------------------------------------------------------------
    def test_ozet_listesi_kok_oturumlari_yeniden_eskiye_basar(self):
        p = self.kur()
        rc, out = self.kos(cwd=p)          # --proje verilmezse bulunulan dizin
        self.assertEqual(rc, 0, out)
        satirlar = [s for s in out.splitlines() if s.strip().startswith(("1 ", "2 ", "3 "))]
        self.assertEqual(len(satirlar), 3, out)
        self.assertIn("cccc3333", satirlar[0])
        self.assertIn("bbbb2222", satirlar[1])
        self.assertIn("aaaa1111", satirlar[2])
        self.assertIn("§0=VAR", satirlar[2])
        self.assertIn("§0=YOK", satirlar[1])
        self.assertNotIn("dddd4444", out, "alt oturum kök listesine girmemeli")

    def test_sira_numarasi_en_yeni_koku_secer(self):
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "1")
        self.assertIn("OTURUM cccc3333", out, out)

    # --- tam iz içeriği --------------------------------------------------------------------------------------
    def test_tam_iz_okunan_yazilan_ve_alt_oturumu_basar(self):
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "aaaa")
        self.assertIn("OKUNAN-DOSYA.md", out)
        self.assertIn("YAZILAN-DOSYA.md", out)
        self.assertIn("[HATA]", out, "hatalı araç sonucu işaretlenmeli")
        self.assertIn("OTURUM dddd4444", out, "alt oturum basılmalı")
        self.assertIn("ALT-OKUNAN.md", out)
        self.assertIn("alt oturum — §0 uygulanmaz", out, out)

    def test_log_satiri_oturum_kimligiyle_suzulur(self):
        """Zaman penceresi başka oturumun aynı saniyedeki ret satırını da yakalar; kimlik eşleşmesi yakalamaz."""
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "aaaa")
        self.assertIn("KANARYALI-RET", out, out)
        self.assertNotIn("BASKA-OTURUM-RET", out, out)
        self.assertIn("[kimlik]", out, "hangi eşleşmenin kullanıldığı yazılmalı")

    def test_kimliksiz_log_satiri_zaman_penceresiyle_eslesir_ve_isaretlenir(self):
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "aaaa")
        satir = next((s for s in out.splitlines() if "KIMLIKSIZ-RET" in s), "")
        self.assertIn("[pencere]", satir, out)

    # --- yol çözümü ------------------------------------------------------------------------------------------
    def test_veri_dizini_ust_dizinden_bulunur(self):
        """Motor kuralı (docs/axet-davranis-olcumleri.md "Veri dizini"): .axet-code yoksa üst dizininki."""
        p = self.kur()
        alt = p / "alt" / "derin"
        alt.mkdir(parents=True)
        rc, out = self.kos("--proje", str(alt), "--oturum", "aaaa")
        self.assertEqual(rc, 0, out)
        self.assertIn("ÜST DİZİN", out, out)

    def test_en_yakin_veri_dizininde_db_yoksa_cikis_2(self):
        (self.tmp / "bos" / ".axet-code").mkdir(parents=True)
        rc, out = self.kos("--proje", str(self.tmp / "bos"))
        self.assertEqual(rc, 2, out)
        self.assertIn("axet-code.db", out)

    def test_bilinmeyen_oturum_cikis_2(self):
        p = self.kur()
        rc, out = self.kos("--proje", str(p), "--oturum", "zzzz")
        self.assertEqual(rc, 2, out)
        self.assertIn("'zzzz' önekiyle kök oturum yok", out)
        rc, out = self.kos("--proje", str(p), "--oturum", "9")
        self.assertEqual(rc, 2, out)
        self.assertIn("9. kök oturum yok (3 kök oturum var)", out)

    def test_eksik_sema_cikis_2(self):
        veri = self.tmp / "eski" / ".axet-code"
        veri.mkdir(parents=True)
        c = sqlite3.connect(veri / "axet-code.db")
        c.execute("create table sessions (id text)")
        c.commit()
        c.close()
        rc, out = self.kos("--proje", str(self.tmp / "eski"))
        self.assertEqual(rc, 2, out)
        self.assertIn("şema", out)

    def test_hatali_arguman_cikis_3(self):
        rc, out = self.kos("--bilinmeyen")
        self.assertEqual(rc, 3, out)
        self.assertIn("KULLANIM:", out)
        self.assertIn("--bilinmeyen", out)

    def test_proje_dizini_yoksa_cikis_3(self):
        rc, out = self.kos("--proje", str(self.tmp / "yok"))
        self.assertEqual(rc, 3, out)
        self.assertIn("KULLANIM: proje dizini yok", out)

    # --- beyan ve genelleştirme ------------------------------------------------------------------------------
    def test_kapsam_beyani_her_kosumda_basilir(self):
        p = self.kur()
        for args in ((), ("--oturum", "aaaa"), ("--oturum", "bbbb")):
            rc, out = self.kos("--proje", str(p), *args)
            self.assertIn("KAPSAM — bakılmayanlar:", out, (args, out))

    def test_kodda_makineye_ozgu_mutlak_yol_yok(self):
        """Kaynak araçta müşteri adlı varsayılan proje yolu vardı; genelleştirilmiş kodda sürücü yolu kalmaz."""
        import re
        metin = BETIK.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b[A-Za-z]:[/\\]", metin), "kodda sürücü harfli mutlak yol var")


if __name__ == "__main__":
    unittest.main()
