# -*- coding: utf-8 -*-
"""`scripts/guncelle.py` — tüketici güncelleme motoru (TASARIM §4/§6/§7/§8/§12a).

İÇERİK: (a) FIXTURE ÜRETECİ — geçici dizinde sahte "public" template deposu (etiket v1/v2/v3)
+ senaryo başına tüketici klonu; (b) §12a'nın istediği senaryo/altın-çıktı/mutasyon testleri.

Fixture üreteci `SahteYayin` sınıfıdır ve elle de çalıştırılabilir (incelemek için):
    python tests/test_guncelle.py --uret <bos-dizin>

Repo DIŞI TMP zorunlu (ölçülmüş tuzak: repo içi TMP'de git testleri yanlış FAIL) — `GeciciTest`
`tempfile.mkdtemp()` kullanır, o da sistem TMP'sindedir.

KAPSAM — bakılmayanlar: gerçek bir tüketici klonunda uçtan uca koşum (`_lab`, P9) · aXet'in
modeli talimatı gerçekten izlemesi · Linux/macOS (Windows'ta ölçüldü) · `butunluk` turundaki
gerçek `doctor.py`/`install.py` davranışı (fixture'da sahte betikler koşar; gerçekleri yalnız
"komut koştu ve çıkışı kaydedildi" düzeyinde ölçülür) · uzun test takımlarının zaman aşımı.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unittest
from pathlib import Path

BURASI = Path(__file__).resolve().parent
if str(BURASI) not in sys.path:
    sys.path.insert(0, str(BURASI))

from _helpers import GeciciTest  # noqa: E402

AXET_HOME = BURASI.parent
GUNCELLE_PY = AXET_HOME / "scripts" / "guncelle.py"
HARITA = AXET_HOME / "guncelle" / "harita.json"


# =====================================================================================================
# FIXTURE ÜRETECİ
# =====================================================================================================
# v1 ağacı: gerçek harita.json'un sınıflandırabildiği yollardan seçildi (sınıfsız dosya motoru
# `sinif: null` koluna düşürür; burada kablolamayı ölçmek istiyoruz, o kolu değil).
V1_AGAC: dict[str, str] = {
    "core/00-temel.md": "CORE-ID: AXET-CORE-TEST\n# Çekirdek\nsatir1\nsatir2\nsatir3\n"
                        "satir4\nsatir5\nsatir6\nson\n",
    "scripts/install.py": "#!/usr/bin/env python3\nimport sys\nprint('install v1')\nsys.exit(0)\n",
    "scripts/doctor.py": "#!/usr/bin/env python3\nimport sys\nprint('doctor v1')\nsys.exit(0)\n",
    "config/permissions.json": '{"deny": ["a"]}\n',
    "LICENSE": "MIT v1\n",
    "skills/ornek-skill/SKILL.md": "---\nname: ornek-skill\n---\n# Örnek\ngovde v1\n",
    # klon kimliği (`kur.ps1` Template-Eksikleri: core/00-temel.md + scripts/install.py + skills-sap/)
    "skills-sap/sap-ornek/SKILL.md": "---\nname: sap-ornek\n---\nsap govde v1\n",
    "tests/test_ornek.py": "# test v1\n",
    "kur.cmd": "@echo off\r\nrem A\r\nrem B\r\nrem C\r\necho v1\r\nrem D\r\nrem E\r\nrem son\r\n",
    "docs/tasinacak.md": "tasinan icerik\nA\nB\n",
    "docs/tasinan2.md": "ikinci tasinan\nX\nY\nZ\n",
    "docs/silinecek.md": "silinecek v1\n",
    # V6 (otomatik SİLME) için AYRI dosya gerekir: `senaryolari_uygula` docs/silinecek.md'yi
    # yerelde de değiştirdiği için o daima V6d olur ve V6 dalı hiçbir testte KOŞMAZ.
    "docs/silinecek2.md": "kullanicinin dokunmadigi, emekliye ayrilan dosya\n",
    # V4B için tabanda VAR olmalı: tabansız bir ikili dosya V7'dir (ad çakışması), V4B değil
    "docs/logo.png": "\x00\x01PNG-v1\x00",
    "skills/silinen-skill/SKILL.md": "---\nname: silinen-skill\n---\nsilinen v1\n",
    # ölçüm komutlarının gerçekten koşabilmesi için (harita: `python tests/run_tests.py …`)
    "tests/run_tests.py": "import sys\nprint('SONUÇ: 3 test · 0 failure')\nsys.exit(0)\n",
}

# v2'de değişenler (yayın kalemi 2-01/2-02)
V2_DEGISIM: dict[str, str | None] = {
    "scripts/doctor.py": "#!/usr/bin/env python3\nimport sys\nprint('doctor v2')\nsys.exit(0)\n",
    "core/00-temel.md": "CORE-ID: AXET-CORE-TEST\n# Çekirdek v2\nsatir1\nsatir2\nsatir3\n"
                        "satir4\nsatir5\nsatir6\nson\n",
}

# v3'te değişenler/eklenenler/silinenler — §4'ün tüm vaka kodlarını tetikleyebilmek için
V3_DEGISIM: dict[str, str | None] = {
    # V1/V4 adayı: taban v1'den beri iki kez değişen dosya (dosya-başı taban senaryosu)
    "scripts/doctor.py": "#!/usr/bin/env python3\nimport sys\nprint('doctor v3')\nsys.exit(0)\n",
    # V4 adayı: üst satır bizden, alt satır kullanıcıdan → temiz birleşme (V4t)
    "core/00-temel.md": "CORE-ID: AXET-CORE-TEST\n# Çekirdek v3\nsatir1\nsatir2\nsatir3\n"
                        "satir4\nsatir5\nsatir6\nson\n",
    # V1 adayı (kullanıcı dokunmaz)
    "config/permissions.json": '{"deny": ["a", "b"]}\n',
    # V2 adayı: yepyeni dosya
    "scripts/sap_stamp.py": "print('yeni')\n",
    # V5 adayı: kullanıcının sildiği skill bu yayında güncellendi
    "skills/silinen-skill/SKILL.md": "---\nname: silinen-skill\n---\nsilinen v3\n",
    # V6d adayı: template sildi, kullanıcı da değiştirdi (senaryolari_uygula)
    "docs/silinecek.md": None,
    # V6 adayı: template sildi, kullanıcı DOKUNMADI → otomatik silme dalı
    "docs/silinecek2.md": None,
    # V1R adayı: yeniden adlandırma, kullanıcı dokunmamış (içerik aynı → git -M yakalar)
    "docs/tasinacak.md": None,
    "docs/tasindi.md": "tasinan icerik\nA\nB\n",
    # V4R adayı: yeniden adlandırma + iki taraf da değişmiş
    "docs/tasinan2.md": None,
    "docs/tasindi2.md": "ikinci tasinan\nX bizden\nY\nZ\n",
    # V4B adayı: ikili dosya (binary attribute .png)
    "docs/logo.png": "\x00\x01PNG-v3\x00",
    # CRLF ölçümü: .cmd dosyası (eol=crlf) hem bizde hem kullanıcıda değişir
    "kur.cmd": "@echo off\r\nrem bizden\r\nrem A\r\nrem B\r\nrem C\r\necho v3\r\n"
               "rem D\r\nrem E\r\nrem son\r\n",
    # V7 adayı: kullanıcı aynı yola kendi dosyasını koymuş olacak
    "skills/cakisan/SKILL.md": "---\nname: cakisan\n---\ntemplate surumu\n",
    # BEYANSIZ EYLEM vakası: v3'te DEĞİŞİYOR ama hiçbir yayın kaleminin `dosyalar` listesinde
    # geçmiyor → kapsamda, sayaçta görünür, ama hiçbir zaman uygulanmaz. Plan bunu SÖYLEMELİ.
    "docs/beyansiz.md": "yayin kaleminde beyan edilmemis yeni dosya\n",
}

YAYINLAR = {
    "yayinlar": [
        {
            "etiket": "v2", "tarih": "2026-01-01", "min_axet": "1.0.0",
            "kalemler": [
                {"id": "2-01", "baslik": "doctor: v2 düzeltmesi", "tur": "duzeltme", "kritik": False,
                 "neden": "hata", "dosyalar": ["scripts/doctor.py"], "gerektirir": [],
                 "test": ["kok:test_ornek"]},
                {"id": "2-02", "baslik": "çekirdek: satır2 netleşti", "tur": "kural", "kritik": False,
                 "neden": "belirsizdi", "dosyalar": ["core/00-temel.md"], "gerektirir": [],
                 "test": []},
            ],
        },
        {
            "etiket": "v3", "tarih": "2026-02-01", "min_axet": "1.0.0",
            "kalemler": [
                {"id": "3-01", "baslik": "doctor + yeni araç", "tur": "yetenek", "kritik": False,
                 "neden": "eksikti", "dosyalar": ["scripts/doctor.py", "scripts/sap_stamp.py"],
                 "gerektirir": [], "test": ["kok:test_ornek"]},
                {"id": "3-02", "baslik": "çekirdek başlığı", "tur": "kural", "kritik": False,
                 "neden": "—", "dosyalar": ["core/00-temel.md"], "gerektirir": [], "test": []},
                {"id": "3-03", "baslik": "izin listesi genişledi", "tur": "guvenlik", "kritik": True,
                 "neden": "açık", "dosyalar": ["config/permissions.json"], "gerektirir": [], "test": []},
                {"id": "3-04", "baslik": "skill onarımı + emeklilik + taşıma", "tur": "duzeltme",
                 "kritik": False, "neden": "—",
                 "dosyalar": ["skills/silinen-skill/SKILL.md", "docs/silinecek.md",
                              "docs/silinecek2.md",
                              "docs/tasinacak.md", "docs/tasindi.md",
                              "docs/tasinan2.md", "docs/tasindi2.md"],
                 "gerektirir": [], "test": []},
                {"id": "3-05", "baslik": "logo + kur.cmd + çakışan skill", "tur": "yetenek",
                 "kritik": False, "neden": "—",
                 "dosyalar": ["docs/logo.png", "kur.cmd", "skills/cakisan/SKILL.md"],
                 "gerektirir": ["3-01"], "test": []},
            ],
        },
    ]
}


class SahteYayin:
    """Sahte public template deposu + ondan türemiş tüketici klonu.

    public: c1(v1) → c2(v2) → c3(v3).  tüketici: v1'de klonlanmış, sonra `fetch --tags` yapmış
    ⇒ HEAD = c1, origin/main = c3, merge-base = c1 (gerçek tüketici deseninin aynısı).
    """

    def __init__(self, test: GeciciTest, kok: Path) -> None:
        self.t = test
        self.kok = kok
        self.public = kok / "public"
        self.tuketici = kok / "tuketici"

    # --- kurulum -------------------------------------------------------------------------------
    def _yaz(self, dizin: Path, agac: dict) -> None:
        for yol, icerik in agac.items():
            h = dizin / yol
            if icerik is None:
                if h.exists():
                    h.unlink()
                continue
            h.parent.mkdir(parents=True, exist_ok=True)
            ikili = h.suffix.lower() in (".png", ".jpg", ".zip", ".pdf", ".exe")
            if ikili:
                h.write_bytes(icerik.encode("latin-1"))
            else:
                with open(h, "w", encoding="utf-8", newline="") as fh:
                    fh.write(icerik)

    def uret(self) -> "SahteYayin":
        self.public.mkdir(parents=True)
        g = self.t.git
        g(self.public, "init", "-q", "-b", "main")
        # .gitattributes: gerçek template'in ilgili satırları (CRLF/binary davranışı ölçülecek)
        self._yaz(self.public, {
            ".gitattributes": "* text=auto\n*.py text eol=lf\n*.md text eol=lf\n*.json text eol=lf\n"
                              "*.cmd text eol=crlf\n*.png binary\n",
            ".gitignore": "/.axet-guncelleme/\n",
        })
        self._yaz(self.public, V1_AGAC)
        g(self.public, "add", "-A")
        g(self.public, "commit", "-q", "-m", "v1")
        g(self.public, "tag", "v1")
        # tüketici klonu: v1 hâli
        g(self.kok, "clone", "-q", str(self.public), str(self.tuketici))
        # public ilerler
        self._yaz(self.public, V2_DEGISIM)
        g(self.public, "add", "-A")
        g(self.public, "commit", "-q", "-m", "v2")
        g(self.public, "tag", "v2")
        self._yaz(self.public, V3_DEGISIM)
        self._yaz(self.public, {"guncelle/yayinlar.json":
                                json.dumps(YAYINLAR, ensure_ascii=False, indent=1) + "\n"})
        g(self.public, "add", "-A")
        g(self.public, "commit", "-q", "-m", "v3")
        g(self.public, "tag", "v3")
        # tüketici uzağı görsün
        g(self.tuketici, "fetch", "-q", "--tags", "origin")
        # `onkontrol` origin'in RESMÎ template adresi olmasını ister (K4). Testte resmî adres
        # sahte public deponun kendisidir; üretim varsayılanı (RESMI_ORIGIN) dokunulmadan kalır.
        self.t.env["AXET_GUNCELLE_BEKLENEN_ORIGIN"] = str(self.public)
        return self

    # --- senaryo mutasyonları ------------------------------------------------------------------
    def yerel_degistir(self, yol: str, icerik: str) -> None:
        h = self.tuketici / yol
        h.parent.mkdir(parents=True, exist_ok=True)
        with open(h, "w", encoding="utf-8", newline="") as fh:
            fh.write(icerik)

    def yerel_sil(self, yol: str) -> None:
        (self.tuketici / yol).unlink()

    def yerel_ikili(self, yol: str, veri: bytes) -> None:
        h = self.tuketici / yol
        h.parent.mkdir(parents=True, exist_ok=True)
        h.write_bytes(veri)

    # --- motoru çağır --------------------------------------------------------------------------
    def calistir(self, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GUNCELLE_PY), "--klon", str(self.tuketici), *args],
            cwd=str(self.kok), env=self.t.env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)

    def durum_dizini(self) -> Path:
        return self.tuketici / ".axet-guncelleme"

    def plan(self) -> dict:
        return json.loads((self.durum_dizini() / "plan.json").read_text(encoding="utf-8"))

    def durum(self) -> dict:
        return json.loads((self.durum_dizini() / "durum.json").read_text(encoding="utf-8"))

    def vakalar(self) -> dict[str, str]:
        """yol → vaka kodu (altın çıktı karşılaştırması için düzleştirilmiş plan)."""
        out: dict[str, str] = {}
        for k in self.plan()["kalemler"]:
            for d in k["dosyalar"]:
                out[d["yol"]] = d["vaka"]
        return out


class GuncelleTemel(GeciciTest):
    """Ortak kurulum: sahte yayın + tüketici klonu, senaryo mutasyonları uygulanmış."""

    def setUp(self) -> None:
        super().setUp()
        self.f = SahteYayin(self, self.tmp).uret()

    def senaryolari_uygula(self) -> None:
        """§12a'nın istediği tüm vaka kodlarını aynı klonda tetikleyen mutasyon kümesi."""
        f = self.f
        # V3: yerel değişmiş, yeni gelmiyor
        f.yerel_degistir("LICENSE", "MIT yerel\n")
        # V4t: taban ≠ yerel ≠ yeni, satırlar çakışmıyor (kullanıcı son satırı değiştirdi)
        # ⚠ kullanıcının değişikliği bizimkinden UZAK bir satırda olmalı: git birleşmesi
        # BİTİŞİK satır değişikliklerini de çakışma sayar (ölçüldü 2026-09-17).
        f.yerel_degistir("core/00-temel.md",
                         "CORE-ID: AXET-CORE-TEST\n# Çekirdek\nsatir1\nsatir2\nsatir3\n"
                         "satir4\nsatir5\nsatir6\nson yerel\n")
        # V4c: aynı satırda iki taraf da değişti
        f.yerel_degistir("scripts/doctor.py",
                         "#!/usr/bin/env python3\nimport sys\nprint('doctor YEREL')\nsys.exit(0)\n")
        # V5: kullanıcı silmiş, yeni yayın güncelledi
        f.yerel_sil("skills/silinen-skill/SKILL.md")
        # V6d: template sildi, kullanıcı değiştirmiş
        f.yerel_degistir("docs/silinecek.md", "silinecek YEREL\n")
        # V7: kullanıcı, template'in yeni dosyasının yoluna kendi dosyasını koydu
        f.yerel_degistir("skills/cakisan/SKILL.md", "---\nname: cakisan\n---\nKULLANICININ dosyasi\n")
        # V4B: ikili dosya iki tarafta da farklı
        f.yerel_ikili("docs/logo.png", b"\x00\x01PNG-YEREL\x00")
        # V4R: taşınan dosyanın yerelde de değişmiş olması
        f.yerel_degistir("docs/tasinan2.md", "ikinci tasinan\nX\nY\nZ yerelden\n")
        # V4t (.cmd, CRLF): kullanıcı kendi satırını ekledi
        f.yerel_degistir("kur.cmd", "@echo off\r\nrem A\r\nrem B\r\nrem C\r\necho v1\r\n"
                                    "rem D\r\nrem E\r\nrem son\r\nrem yerelden\r\n")
        # VKD: kullanıcının kendi dosyası (template hiç bilmiyor)
        f.yerel_degistir("kendi-notum.md", "benim notum\n")
        # V4e: yerel zaten yeniyle aynı
        f.yerel_degistir("config/permissions.json", '{"deny": ["a", "b"]}\n')

    def hazirla_ve_planla(self) -> subprocess.CompletedProcess:
        r = self.f.calistir("hazirla")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return self.f.calistir("plan")

    def ozel_adimlari_kostur(self) -> None:
        """§7 adım 9: plandaki her `ozel_adim` ayrıca koşulur."""
        adlar = sorted({a for k in self.f.plan()["kalemler"] for a in k["ozel_adimlar"]})
        self.assertTrue(adlar, "fixture en az bir özel adım üretmeliydi (yoksa test anlamsız)")
        for ad in adlar:
            r = self.f.calistir("ozel-adim", ad)
            self.assertEqual(r.returncode, 0, f"{ad}: {self.cikti(r)}")


# =====================================================================================================
# 1. ÖN KONTROL / HAZIRLA
# =====================================================================================================
class OnkontrolTest(GuncelleTemel):
    def test_temiz_klonda_onkontrol_gecer(self):
        r = self.f.calistir("onkontrol")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_yabanci_origin_durdurur(self):
        """K4/§6: origin resmî template adresi değilse geçici kopya çıkarılmaz → DUR."""
        self.git(self.f.tuketici, "remote", "set-url", "origin",
                 "https://github.com/baskasi/fork.git")
        r = self.f.calistir("onkontrol")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("origin", self.cikti(r).lower())

    def test_klon_kimligi_bozuksa_durdurur(self):
        (self.f.tuketici / "core" / "00-temel.md").unlink()
        r = self.f.calistir("onkontrol")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("00-temel.md", self.cikti(r))

    def test_hazirla_etiket_ve_anlik_commit_uretir(self):
        self.f.yerel_degistir("LICENSE", "MIT yerel\n")
        r = self.f.calistir("hazirla")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        etiketler = self.git(self.f.tuketici, "tag", "--list", "guncelle-oncesi-*").stdout.split()
        self.assertEqual(len(etiketler), 1, etiketler)
        # anlık commit gerçekten yerel değişikliği taşıyor
        g = self.git(self.f.tuketici, "show", f"{etiketler[0]}:LICENSE").stdout
        self.assertEqual(g, "MIT yerel\n")

    def test_hazirla_git_kimligi_tanimsiz_ortamda_calisir(self):
        """Tüketicide git kimliği tanımsız olabilir (§2a)."""
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            self.env.pop(k, None)
        self.f.yerel_degistir("LICENSE", "MIT yerel\n")
        r = self.f.calistir("hazirla")
        self.assertEqual(r.returncode, 0, self.cikti(r))


# =====================================================================================================
# 2. PLAN — §4 vaka kodlarının ALTIN ÇIKTISI
# =====================================================================================================
class PlanVakaTest(GuncelleTemel):
    ALTIN = {
        "scripts/doctor.py": "V4c",
        "core/00-temel.md": "V4t",
        "docs/tasinan2.md": "V4R",
        "scripts/sap_stamp.py": "V2",
        "skills/silinen-skill/SKILL.md": "V5",
        "docs/silinecek.md": "V6d",
        "skills/cakisan/SKILL.md": "V7",
        "docs/logo.png": "V4B",
        "kur.cmd": "V4t",
        "docs/tasinacak.md": "V1R",
    }

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        r = self.hazirla_ve_planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.p = self.f.plan()
        self.v = self.f.vakalar()

    def test_altin_cikti_vaka_kodlari(self):
        for yol, beklenen in self.ALTIN.items():
            self.assertEqual(self.v.get(yol), beklenen, f"{yol}: {self.v.get(yol)} ≠ {beklenen}")

    def test_islem_gerektirmeyen_kodlar_dosya_listesinde_degil_sayacta(self):
        """V3/V4e/VKD/V0 listelenmez, yalnız sayılır (§4 + §5 'işlem yok')."""
        self.assertNotIn("LICENSE", self.v, "V3 listelenmemeli")
        self.assertNotIn("config/permissions.json", self.v, "V4e listelenmemeli")
        self.assertNotIn("kendi-notum.md", self.v)
        self.assertGreaterEqual(self.p["sayaclar"].get("V3", 0), 1)
        self.assertGreaterEqual(self.p["sayaclar"].get("V4e", 0), 1)
        self.assertGreaterEqual(self.p["sayaclar"].get("VKD", 0), 1)

    def test_kullanicinin_kendi_dosyasi_hic_kapsama_girmez(self):
        """§2a: iki ağaçta da olmayan yol kullanıcınındır — VKD sayacında bile yolu geçmez."""
        metin = json.dumps(self.p, ensure_ascii=False)
        self.assertNotIn("kendi-notum.md", metin)

    def test_yeniden_adlandirma_hedef_yolu_tasir(self):
        kalem = [d for k in self.p["kalemler"] for d in k["dosyalar"] if d["yol"] == "docs/tasinacak.md"]
        self.assertEqual(len(kalem), 1)
        self.assertEqual(kalem[0].get("yeni_yol"), "docs/tasindi.md")

    def test_dosya_basi_taban_v2de_alinan_dosya_v3te_V1_olur(self):
        """§2a: uygulanan.json tabanı doğru yayına taşır; merge-base olsaydı yanlış çakışma çıkardı."""
        # doctor.py'yi v2 sürümüne getir ve "v2'de uygulandı" diye kaydet
        self.f.yerel_degistir("scripts/doctor.py", V2_DEGISIM["scripts/doctor.py"])
        d = self.f.durum_dizini()
        d.mkdir(exist_ok=True)
        (d / "uygulanan.json").write_text(json.dumps(
            {"surum": 1, "dosyalar": {"scripts/doctor.py": "v2"}, "kalemler": {}},
            ensure_ascii=False), encoding="utf-8")
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.vakalar().get("scripts/doctor.py"), "V1")

    def test_paket_ayni_dosyaya_dokunan_kalemleri_birlestirir(self):
        """§6: aynı dosyaya dokunan kalemler union-find ile tek pakete bağlanır."""
        paket = {k["id"]: k["paket"] for k in self.p["kalemler"]}
        self.assertEqual(paket["2-01"], paket["3-01"], "doctor.py'ye ikisi de dokunuyor")
        self.assertEqual(paket["2-02"], paket["3-02"], "core/00-temel.md'ye ikisi de dokunuyor")

    def test_guvenlik_kalemi_kritik_gelir(self):
        k = {x["id"]: x for x in self.p["kalemler"]}["3-03"]
        self.assertTrue(k["kritik"])

    def test_yeniden_baslat_alani_en_yuksek_gereksinimi_tasir(self):
        self.assertIn(self.p["yeniden_baslat"],
                      ("gerekmez", "yeni-oturum", "install-sonra-yeni-oturum"))
        # config/permissions.json (install-sonra-yeni-oturum) planda V4e = LİSTELENMEZ;
        # listelenenlerin en yükseği çekirdek kuralın "yeni-oturum"u.
        self.assertEqual(self.p["yeniden_baslat"], "yeni-oturum")

    def test_plan_sahte_degil_gercek_haritadan_siniflandirir(self):
        s = {d["yol"]: d["sinif"] for k in self.p["kalemler"] for d in k["dosyalar"]}
        self.assertEqual(s["core/00-temel.md"], "cekirdek-kural")
        self.assertEqual(s["kur.cmd"], "kurulum-araci-kok")
        self.assertEqual(s["skills/cakisan/SKILL.md"], "skill-govde")

    def test_beyansiz_eylem_vakasi_WARN_uretir(self):
        """Kapsamda olup hiçbir kalemin `dosyalar` listesinde geçmeyen EYLEM vakası sessizce
        uygulanmıyordu; yalnız sayaçta görünüyordu — kullanıcı "güncellendi" sanırdı."""
        listelenen = {d["yol"] for k in self.p["kalemler"] for d in k["dosyalar"]}
        self.assertNotIn("docs/beyansiz.md", listelenen, "fixture kurgusu bozulmuş")
        self.assertGreaterEqual(self.p["sayaclar"].get("V2", 0), 1)
        uyarilar = " | ".join(self.p["uyarilar"])
        self.assertIn("docs/beyansiz.md", uyarilar)
        self.assertIn("hiçbir kalem", uyarilar)

    def test_null_etkinli_sinif_plana_girer_ve_kaybolmaz(self):
        """D17 tuzağı: `etkin: null` bir sınıf (kurulum-araci-kok) plandan DÜŞMEZ."""
        d = [x for k in self.p["kalemler"] for x in k["dosyalar"] if x["yol"] == "kur.cmd"]
        self.assertEqual(len(d), 1)
        self.assertIsNone(d[0]["etkin"])


class PlanKenarTest(GuncelleTemel):
    def test_hic_is_yoksa_cikis_1(self):
        """§6: `plan` 1 = güncel, iş yok."""
        # tüketiciyi v3'e getir (hiçbir fark kalmasın)
        self.git(self.f.tuketici, "merge", "-q", "--ff-only", "origin/main")
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # EK-3: "1 döndü" ile "BEKLEDİĞİM SEBEPTEN 1 döndü" ayrışsın
        self.assertIn("Klon güncel: bekleyen yayın kalemi yok", self.cikti(r))

    def test_yayinlar_json_yoksa_cikis_2(self):
        """Eşlemesiz plan üretmek kalem sözleşmesini uydurmak olur → hata (0/1 değil)."""
        self.git(self.f.public, "rm", "-q", "guncelle/yayinlar.json")
        self.git(self.f.public, "commit", "-q", "-m", "yayinlar gitti")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "origin")
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("yayinlar.json", self.cikti(r))

    def test_sinifsiz_dosya_plani_patlatmaz_WARN_yazar(self):
        """Harita bir yolu tanımıyorsa motor DURMAZ: `sinif: null` + görünür WARN.

        Sessizce düşürmek en tehlikeli davranış olurdu (dosya hiç güncellenmez ve kimse bilmez).
        `--harita` ile `belge-docs` sınıfı çıkarılıp `docs/**` bilerek sınıfsız bırakılıyor.
        """
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        harita["siniflar"] = [k for k in harita["siniflar"] if k["sinif"] != "belge-docs"]
        kirpik = self.tmp / "harita-kirpik.json"
        kirpik.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        self.f.yerel_degistir("docs/silinecek.md", "silinecek YEREL\n")
        self.assertEqual(self.f.calistir("hazirla").returncode, 0)
        r = self.f.calistir("--harita", str(kirpik), "plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("sınıfsız", self.cikti(r))
        d = [x for k in self.f.plan()["kalemler"] for x in k["dosyalar"]
             if x["yol"] == "docs/silinecek.md"]
        self.assertEqual(len(d), 1, "sınıfsız dosya plandan DÜŞMEMELİ")
        self.assertIsNone(d[0]["sinif"])

    def test_taban_bulunamazsa_VTB(self):
        """§4: klonda taban commit'i yoksa (sığ klon/force push izi) otomatik işlem YASAK."""
        d = self.f.durum_dizini()
        d.mkdir(exist_ok=True)
        (d / "uygulanan.json").write_text(json.dumps(
            {"surum": 1, "dosyalar": {"scripts/doctor.py": "yok-boyle-etiket"}, "kalemler": {}},
            ensure_ascii=False), encoding="utf-8")
        self.f.yerel_degistir("scripts/doctor.py", "print('yerel baska')\n")
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.vakalar().get("scripts/doctor.py"), "VTB")


# =====================================================================================================
# 3. `etkin`in BEŞ değeri (D17 kayıtlı tuzak)
# =====================================================================================================
class EtkinBesDegerTest(unittest.TestCase):
    """harita.json'daki `etkin` enum'unun 5 değeri var ve 5.si `null`; 38 sınıfın 13'ü null.
    Dört değer varsayan bir zincir o sınıfları sessizce "bilinmeyen" kovasına düşürür (D17)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(AXET_HOME / "scripts"))
        import guncelle  # noqa: PLC0415
        cls.g = guncelle
        cls.harita = json.loads(HARITA.read_text(encoding="utf-8"))

    def test_haritadaki_her_etkin_degeri_acikca_ele_alinir(self):
        for deger in self.harita["etkin_degerleri"]:
            with self.subTest(etkin=deger):
                self.assertIn(deger, self.g.ETKIN_DAVRANIS,
                              f"`etkin={deger!r}` motorda ele alınmıyor — sessizce bilinmeyen kovasına düşer")

    def test_null_ayri_bir_dal_gerekmez_demek(self):
        self.assertIsNone(self.g.ETKIN_DAVRANIS[None]["yeniden_baslat"])

    def test_bilinmeyen_etkin_sessizce_duşmez_patlar(self):
        """Yeni bir 6. değer eklenirse motor SESSİZ kalmaz (fail-loud)."""
        with self.assertRaises(self.g.BilinmeyenEtkin):
            self.g.etkin_davranis("altinci-deger")

    def test_null_sinif_sayisi_haritayla_tutarli(self):
        n = sum(1 for k in self.harita["siniflar"] if k.get("etkin") is None)
        self.assertGreaterEqual(n, 1, "harita'da hiç null yoksa bu tuzak testi anlamını yitirmiştir")


# =====================================================================================================
# 4. SEÇİM
# =====================================================================================================
class SecTest(GuncelleTemel):
    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)

    def test_hepsi_tum_kalemleri_secer(self):
        r = self.f.calistir("sec", "--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        s = json.loads((self.f.durum_dizini() / "secim.json").read_text(encoding="utf-8"))
        self.assertEqual(len(s["kalemler"]), len(self.f.plan()["kalemler"]))

    def test_kritikler_varsayilan_secili(self):
        r = self.f.calistir("sec")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        s = json.loads((self.f.durum_dizini() / "secim.json").read_text(encoding="utf-8"))
        self.assertIn("3-03", s["kalemler"])

    def test_gerektirir_karsilanmazsa_cikis_2(self):
        """§6: seçilen kalemin bağımlılığı seçilmemişse `sec` çıkış 2."""
        r = self.f.calistir("sec", "--kalem", "3-05", "--cikar", "3-01")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("3-01", self.cikti(r))

    def test_secim_paket_biriminde(self):
        """Q2: aynı dosyaya dokunan kalemler birlikte seçilir."""
        r = self.f.calistir("sec", "--kalem", "2-01")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        s = json.loads((self.f.durum_dizini() / "secim.json").read_text(encoding="utf-8"))
        self.assertIn("3-01", s["kalemler"], "2-01 ile 3-01 aynı pakette (doctor.py)")


class SecCaprazYayinGerektirirTest(GuncelleTemel):
    """Z57 — `gerektirir` bağı ÖNCEKİ yayında zaten karşılanmış kaleme işaret ediyorsa `sec` DUR
    ETMEMELİ.

    Ölçülen kusur (v0.5.2 CI yayın provası): v0.5.1 tüketicisi v0.5.2'ye `sec --hepsi` →
    `DUR: 0.5.2-01 kalemi 0.5.1-01 kalemini gerektiriyor ama 0.5.1-01 seçili değil`. 0.5.1-01
    zaten uygulanmıştı; `komut_plan` uygulanmış (`uygulanan.json`) ve içerilmiş (etiket HEAD'in
    atası) yayınların kalemlerini plana HİÇ almıyor, `komut_sec` ise bağı yalnız seçim kümesinde
    arıyordu ⇒ karşılanmış bağ "seçili değil" sayılıyordu.

    Kurgu: v3'ün 3-05 kalemi v2'nin 2-01 kalemini gerektirir (çapraz-yayın bağı).
    KONTROL GRUBU: 2-01 hiç karşılanmamışken (ne uygulandı ne içerildi) ve seçilmemişken `sec`
    YİNE DUR etmeli — düzeltme bağ kontrolünü gevşetip körleştirmemeli. Plan `karsilanan`
    alanını taşımıyorsa (eski motorun planı) fail-closed: DUR.
    """

    def setUp(self) -> None:
        super().setUp()
        yayinlar = json.loads(json.dumps(YAYINLAR))
        for kalem in yayinlar["yayinlar"][1]["kalemler"]:
            if kalem["id"] == "3-05":
                kalem["gerektirir"] = ["2-01"]
        self.f._yaz(self.f.public, {"guncelle/yayinlar.json":
                                    json.dumps(yayinlar, ensure_ascii=False, indent=1) + "\n"})
        self.git(self.f.public, "add", "-A")
        self.git(self.f.public, "commit", "-q", "-m", "3-05 -> 2-01 capraz bag")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "origin")

    def _uygulanmis_2_01(self) -> None:
        """2-01 önceki güncelleme turunda (v2) uygulanmış: dosya v2 içeriğinde + mühür."""
        self.f.yerel_degistir("scripts/doctor.py", V2_DEGISIM["scripts/doctor.py"])
        d = self.f.durum_dizini()
        d.mkdir(exist_ok=True)
        (d / "uygulanan.json").write_text(json.dumps(
            {"surum": 1, "dosyalar": {"scripts/doctor.py": "v2"},
             "kalemler": {"2-01": {"etiket": "v2", "durum": "uygulandi",
                                   "zaman": "2026-01-02T00:00:00"}}},
            ensure_ascii=False), encoding="utf-8")

    def _plan_kalem_idleri(self) -> set[str]:
        return {k["id"] for k in self.f.plan()["kalemler"]}

    def test_uygulanmis_onceki_kalem_bagi_karsilar(self):
        self._uygulanmis_2_01()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertNotIn("2-01", self._plan_kalem_idleri(),
                         "kurgu: uygulanmış kalem plana girmemeli (yoksa test kusuru kurmuyor)")
        r = self.f.calistir("sec", "--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        s = json.loads((self.f.durum_dizini() / "secim.json").read_text(encoding="utf-8"))
        self.assertIn("3-05", s["kalemler"])
        self.assertNotIn("2-01", s["kalemler"], "karşılanmış kalem yeniden SEÇİLMEZ")

    def test_icerilmis_yayinin_kalemi_bagi_karsilar(self):
        """Taze klon v2'de: v2 etiketi HEAD'in atası ⇒ v2'nin kalemleri plana hiç girmez."""
        self.git(self.f.tuketici, "reset", "-q", "--hard", "v2")
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertNotIn("2-01", self._plan_kalem_idleri(),
                         "kurgu: içerilmiş yayının kalemi plana girmemeli")
        r = self.f.calistir("sec", "--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_KONTROL_karsilanmamis_ve_secilmemis_bag_yine_DUR(self):
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertIn("2-01", self._plan_kalem_idleri(), "kurgu: 2-01 bekleyen kalem olmalı")
        r = self.f.calistir("sec", "--kalem", "3-05")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("2-01", self.cikti(r))

    def test_KONTROL_plan_karsilanan_tasimiyorsa_fail_closed_DUR(self):
        """Eski motorun ürettiği plan (alan yok) ⇒ karşılanmışlık ÖLÇÜLEMEZ ⇒ DUR."""
        self._uygulanmis_2_01()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        yol = self.f.durum_dizini() / "plan.json"
        plan = self.f.plan()
        plan.pop("karsilanan", None)
        yol.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        r = self.f.calistir("sec", "--hepsi")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("2-01", self.cikti(r))

    # --- Z57 devamı (bug gate MEDIUM): `atlandi` mühürlü önkoşul ------------------------------------
    # `uygulanan.json`'da `durum: atlandi` = kalem seçildi ama HİÇBİR dosyası doğrulanmadı
    # (`_kapanis_git`) — ya `isaretle --karar ertelendi` ile ertelendi ya da yapılacak iş yoktu.
    # Z58 öncesi kayıt ({etiket, durum, zaman}, `neden` YOK) bu ikisini AYIRMAZ — aşağıdaki
    # `_atlandi_2_01` o eski kaydı kurar. Bağ karşılanmış sayılır (DUR etmek bağımlıyı
    # kalıcı kilitlerdi: atlandi kalem bir daha plana girmez) ama SESSİZ geçmemeli: UYARI + rc 0.
    def _atlandi_2_01(self) -> None:
        """2-01 önceki turda seçildi ama dosyası uygulanmadı (ertelendi): disk ESKİ içerikte."""
        d = self.f.durum_dizini()
        d.mkdir(exist_ok=True)
        (d / "uygulanan.json").write_text(json.dumps(
            {"surum": 1, "dosyalar": {},
             "kalemler": {"2-01": {"etiket": "v2", "durum": "atlandi",
                                   "zaman": "2026-01-02T00:00:00"}}},
            ensure_ascii=False), encoding="utf-8")

    def test_atlandi_onkosul_secimi_bozmaz_ama_UYARI_basar(self):
        self._atlandi_2_01()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertNotIn("2-01", self._plan_kalem_idleri(),
                         "kurgu: mühürlü (atlandi) kalem plana girmemeli")
        self.assertEqual(self.f.plan().get("karsilanan_atlandi"), ["2-01"])
        r = self.f.calistir("sec", "--kalem", "3-05")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        uyari = [s for s in self.cikti(r).splitlines() if s.startswith("UYARI:")]
        self.assertEqual(len(uyari), 1, self.cikti(r))
        for parca in ("3-05", "2-01", "atlandi", "diskte"):
            self.assertIn(parca, uyari[0])

    def test_KONTROL_uygulanmis_onkosul_UYARI_basmaz(self):
        self._uygulanmis_2_01()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.plan().get("karsilanan_atlandi"), [])
        r = self.f.calistir("sec", "--kalem", "3-05")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("UYARI:", self.cikti(r))

    # --- Z58 (v0.5.4): `atlandi` mührü artık NEDENİNİ taşır ------------------------------------------
    # `_kapanis_git` atlandi kaleme `neden` yazar: `ertelendi` (en az bir dosyada `isaretle --karar
    # ertelendi`) · `kabul` (`kapanis --kabul` ile dosyaları bekliyor kaldı) · `is-yok` (planda kalemin
    # dosyası yoktu). Plan `is-yok` DIŞINDAKİ her atlandi kalemi `karsilanan_atlandi`'ya koyar
    # (fail-closed: neden yok/tanınmıyor ⇒ uyar); `is-yok` karşılanmış sayılır, UYARI YOK.
    def _atlandi_2_01_neden(self, neden: str) -> None:
        d = self.f.durum_dizini()
        d.mkdir(exist_ok=True)
        (d / "uygulanan.json").write_text(json.dumps(
            {"surum": 1, "dosyalar": {},
             "kalemler": {"2-01": {"etiket": "v2", "durum": "atlandi", "neden": neden,
                                   "zaman": "2026-01-02T00:00:00"}}},
            ensure_ascii=False), encoding="utf-8")

    def _tek_uyari(self) -> str:
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        r = self.f.calistir("sec", "--kalem", "3-05")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        uyari = [s for s in self.cikti(r).splitlines() if s.startswith("UYARI:")]
        self.assertEqual(len(uyari), 1, self.cikti(r))
        for parca in ("3-05", "2-01", "atlandi", "diskte"):
            self.assertIn(parca, uyari[0])
        return uyari[0]

    def test_Z58_ertelendi_onkosul_UYARI_ertelenmis_der(self):
        self._atlandi_2_01_neden("ertelendi")
        uyari = self._tek_uyari()
        self.assertEqual(self.f.plan().get("karsilanan_atlandi"), ["2-01"])
        self.assertIn("ertelenmiş", uyari)
        self.assertNotIn("ayırt edilemiyor", uyari)
        self.assertNotIn("ikisini ayırmaz", uyari, "eski yanlış cümle kalmamalı")

    def test_Z58_kabul_onkosul_UYARI_kabul_der(self):
        self._atlandi_2_01_neden("kabul")
        uyari = self._tek_uyari()
        self.assertIn("--kabul", uyari)
        self.assertIn("bekliyor", uyari)

    def test_Z58_eski_kayit_neden_yok_UYARI_eski_kayit_metni(self):
        self._atlandi_2_01()
        uyari = self._tek_uyari()
        self.assertIn("eski kayıt", uyari)
        self.assertIn("ayırt edilemiyor", uyari)

    def test_Z58_taninmayan_neden_fail_closed_UYARI(self):
        self._atlandi_2_01_neden("gelecekte-yeni-deger")
        uyari = self._tek_uyari()
        self.assertIn("gelecekte-yeni-deger", uyari)

    def test_Z58_is_yok_onkosul_karsilanmis_UYARI_basmaz(self):
        self._atlandi_2_01_neden("is-yok")
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        plan = self.f.plan()
        self.assertNotIn("2-01", self._plan_kalem_idleri())
        self.assertIn("2-01", plan["karsilanan"], "is-yok kalem KARŞILANMIŞ sayılmalı")
        self.assertEqual(plan.get("karsilanan_atlandi"), [])
        r = self.f.calistir("sec", "--kalem", "3-05")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("UYARI:", self.cikti(r))

    def test_KONTROL_plan_karsilanan_atlandi_tasimiyorsa_bos_kabul(self):
        """Alan yoksa (Z57 ilk sürümünün planı) boş küme: seçim bozulmaz, uyarı basılamaz."""
        self._atlandi_2_01()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        yol = self.f.durum_dizini() / "plan.json"
        plan = self.f.plan()
        plan.pop("karsilanan_atlandi", None)
        yol.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        r = self.f.calistir("sec", "--kalem", "3-05")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("UYARI:", self.cikti(r))


# =====================================================================================================
# 5. UYGULA (otomatik vakalar)
# =====================================================================================================
class UygulaTest(GuncelleTemel):
    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def test_otomatik_vakalar_yazilir_ve_dogrulanir(self):
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        d = self.f.durum()["dosyalar"]
        # V2 — yeni dosya
        self.assertTrue((self.f.tuketici / "scripts/sap_stamp.py").exists())
        self.assertEqual(d["scripts/sap_stamp.py"]["durum"], "dogrulandi")
        # V5 — geri getirildi + görünür log
        self.assertTrue((self.f.tuketici / "skills/silinen-skill/SKILL.md").exists())
        self.assertIn("GERİ GETİRİLDİ", self.cikti(r))
        # V1R — taşındı
        self.assertTrue((self.f.tuketici / "docs/tasindi.md").exists())
        self.assertFalse((self.f.tuketici / "docs/tasinacak.md").exists())

    def test_yargi_vakalarina_uygula_dokunmaz(self):
        self.f.calistir("uygula", "--otomatik")
        # V4c dosyası yerelde kalmalı
        self.assertIn("doctor YEREL", (self.f.tuketici / "scripts/doctor.py").read_text(encoding="utf-8"))
        # V7 dosyası kullanıcınınki kalmalı
        self.assertIn("KULLANICININ",
                      (self.f.tuketici / "skills/cakisan/SKILL.md").read_text(encoding="utf-8"))
        # V6d silinmemeli
        self.assertTrue((self.f.tuketici / "docs/silinecek.md").exists())

    def test_V6d_otomatik_kapanmaz(self):
        """Ad↔içerik uyumu: bu test YALNIZ V6d'yi ölçer (eski adı V6'yı da ölçtüğünü ima
        ediyordu; gövdede tek bir V6 assertion'ı yoktu)."""
        r = self.f.calistir("uygula", "--otomatik")
        # V6d otomatik yola HİÇ girmemeli: dosyanın korunması tek başına kanıt değildir
        # (otomatik yol denenip `git checkout` rastlantıyla patlasa da dosya yerinde kalır).
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("docs/silinecek.md", r.stderr, self.cikti(r))
        d = self.f.durum()["dosyalar"]
        self.assertEqual(d["docs/silinecek.md"]["vaka"], "V6d")
        self.assertEqual(d["docs/silinecek.md"]["durum"], "bekliyor", d["docs/silinecek.md"])
        self.assertNotIn("not_", d["docs/silinecek.md"], "otomatik yol denenmiş")
        self.assertNotIn(d["docs/silinecek.md"]["durum"], ("dogrulandi",),
                         "V6d otomatik kapanamaz — kullanıcıya bilgi vakasıdır")
        self.assertTrue((self.f.tuketici / "docs/silinecek.md").exists())

    def test_V6_otomatik_SILINIR_ve_geri_al_geri_getirir(self):
        """⛔ V6 dalı (`uygula --otomatik`'in SİLME yolu) hiçbir testte KOŞMUYORDU: gate'in M4
        mutasyonu (V6 dalına `AssertionError`) 30 testin hiçbirini kırmadı. Sebep:
        `senaryolari_uygula` tek silinen dosyayı yerelde de değiştirdiği için daima V6d
        çıkıyordu. `docs/silinecek2.md` bu dalı yürüten AYRI fixture dosyasıdır."""
        self.assertEqual(self.f.vakalar().get("docs/silinecek2.md"), "V6")
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.f.tuketici / "docs/silinecek2.md").exists(),
                         "V6 = template emekliye ayırdı, sende değişmemiş → otomatik silinir")
        self.assertIn("SİLİNDİ", self.cikti(r))
        d = self.f.durum()["dosyalar"]["docs/silinecek2.md"]
        self.assertEqual(d["vaka"], "V6")
        self.assertEqual(d["durum"], "dogrulandi")
        g = self.f.calistir("geri-al", "docs/silinecek2.md")
        self.assertEqual(g.returncode, 0, self.cikti(g))
        self.assertTrue((self.f.tuketici / "docs/silinecek2.md").exists(),
                        "geri-al silinen dosyayı geri getirmeli")

    def test_uygula_tekrari_VERILMIS_karari_dusurmez(self):
        """`uygula --otomatik` tekrarı, yargı vakalarına koşulsuz `durum="bekliyor"` yazıyordu:
        verilmiş bir karar `dogrulandi`/`atlandi`'dan düşüyor ve geriye ÇELİŞKİLİ bir kayıt
        kalıyordu (`durum=bekliyor` + `karar=yerel`)."""
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.assertEqual(self.f.calistir("isaretle", "docs/silinecek.md",
                                         "--karar", "yerel").returncode, 0)
        self.assertEqual(self.f.calistir("isaretle", "core/00-temel.md", "--karar", "ertelendi",
                                         "--gerekce", "elle bakılacak").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        d = self.f.durum()["dosyalar"]
        self.assertEqual(d["docs/silinecek.md"]["durum"], "dogrulandi")
        self.assertEqual(d["docs/silinecek.md"]["karar"], "yerel")
        self.assertEqual(d["core/00-temel.md"]["durum"], "atlandi")
        self.assertEqual(d["core/00-temel.md"]["karar"], "ertelendi")

    def test_kontrol_grubu_karar_verilmemis_dosya_bekliyor_kalir(self):
        """Kural daraltma değil ezmeme: hiç karar verilmemiş yargı dosyası yine `bekliyor`."""
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.assertEqual(self.f.durum()["dosyalar"]["docs/silinecek.md"]["durum"], "bekliyor")

    def test_secilmeyen_pakete_dokunmaz(self):
        # yeniden seç: yalnız 3-03 (kritik) paketi
        self.assertEqual(self.f.calistir("sec", "--kalem", "3-03").returncode, 0)
        self.f.calistir("uygula", "--otomatik")
        self.assertFalse((self.f.tuketici / "scripts/sap_stamp.py").exists())
        self.assertEqual((self.f.tuketici / "config/permissions.json")
                         .read_text(encoding="utf-8"), '{"deny": ["a", "b"]}\n')


class YenidenAdlandirmaCakismasiTest(GuncelleTemel):
    """TASARIM §4 +R son cümlesi: **'Yeni yolda zaten L varsa → V7'**.

    Kullanıcı, template'in taşıyacağı YENİ yola kendi dosyasını koymuşsa taşıma bir ad
    çakışmasıdır; motor sessizce üzerine YAZAMAZ (V1R.md:26-27 kartı da bunu söyler).
    """

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.f.yerel_degistir("docs/tasindi.md", "KULLANICININ 40 sayfalik notu\n")
        r = self.hazirla_ve_planla()
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_hedefte_kullanici_dosyasi_varsa_vaka_V7(self):
        self.assertEqual(self.f.vakalar().get("docs/tasinacak.md"), "V7")

    def test_kontrol_grubu_hedef_bossa_vaka_V1R(self):
        """Aynı fixture, yalnız hedefteki kullanıcı dosyası yok → taşıma otomatiktir."""
        (self.f.tuketici / "docs/tasindi.md").unlink()
        self.assertEqual(self.f.calistir("plan").returncode, 0)
        self.assertEqual(self.f.vakalar().get("docs/tasinacak.md"), "V1R")

    def test_uygula_otomatik_hedefteki_kullanici_dosyasini_EZMEZ(self):
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((self.f.tuketici / "docs/tasindi.md").read_text(encoding="utf-8"),
                         "KULLANICININ 40 sayfalik notu\n",
                         "kullanıcının dosyası geri alınamaz biçimde ezildi")

    def test_V7_karari_yeniden_adlandir_kullanici_dosyasini_yerel_olarak_saklar(self):
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("isaretle", "docs/tasinacak.md", "--karar", "yeniden-adlandir")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("KULLANICININ",
                      (self.f.tuketici / "docs/tasindi.md.yerel").read_text(encoding="utf-8"))
        self.assertEqual((self.f.tuketici / "docs/tasindi.md").read_text(encoding="utf-8"),
                         "tasinan icerik\nA\nB\n")


class EksikYayinEtiketiTest(GuncelleTemel):
    """Bekleyen bir yayının etiketi klonda çözülemezse `_hedef_ref` SESSİZCE bir öncekine düşer:
    v3 kalemleri v2 içeriğiyle uygulanır ve `uygulanan.json`'a "uygulandi" yazılır ⇒ kalıcı kayıp.
    """

    def _hazirla_ve_etiketi_sil(self) -> None:
        self.senaryolari_uygula()
        self.assertEqual(self.f.calistir("hazirla").returncode, 0)
        # `hazirla` fetch --tags yapar; etiketi ONDAN SONRA sil (yoksa geri gelir)
        self.git(self.f.tuketici, "tag", "-d", "v3")

    def test_kontrol_grubu_etiket_yerindeyken_plan_0(self):
        self.senaryolari_uygula()
        self.assertEqual(self.f.calistir("hazirla").returncode, 0)
        self.assertEqual(self.f.calistir("plan").returncode, 0)

    def test_bekleyen_yayin_etiketi_cozulemezse_plan_durur(self):
        self._hazirla_ve_etiketi_sil()
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("v3", self.cikti(r))
        self.assertFalse((self.f.durum_dizini() / "plan.json").is_file(),
                         "eksik etiketle plan YAZILMAMALI — v3 kalemleri v2 içeriğiyle uygulanır")

    def test_gecmis_yeniden_yazildiysa_sifirla_onerilir(self):
        """TASARIM §11 force-push istisnası: bayrak varsa mesaj `-Sifirla` önerir."""
        veri = json.loads(json.dumps(YAYINLAR))
        veri["gecmis_yeniden_yazildi"] = True
        self.f._yaz(self.f.public, {"guncelle/yayinlar.json":
                                    json.dumps(veri, ensure_ascii=False, indent=1) + "\n"})
        self.git(self.f.public, "add", "-A")
        self.git(self.f.public, "commit", "-q", "-m", "gecmis yeniden yazildi")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "origin")
        self._hazirla_ve_etiketi_sil()
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("-Sifirla", self.cikti(r))


# =====================================================================================================
# 6. ÖNERİ / İŞARETLE
# =====================================================================================================
class OneriIsaretleTest(GuncelleTemel):
    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)

    def test_V4t_temiz_birlesme_cikis_0(self):
        # EK-3: adı V4t diyor → vakanın gerçekten V4t olduğunu da ÖLÇ (yoksa ad bir iddia,
        # gövde başka bir şey ölçüyor olabilir).
        self.assertEqual(self.f.vakalar().get("core/00-temel.md"), "V4t")
        r = self.f.calistir("oneri", "core/00-temel.md")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        o = (self.f.durum_dizini() / "oneri" / "core/00-temel.md").read_text(encoding="utf-8")
        self.assertIn("# Çekirdek v3", o, "bizim değişikliğimiz")
        self.assertIn("son yerel", o, "kullanıcının değişikliği")
        self.assertNotIn("<<<<<<<", o)

    def test_V4t_iki_fark_ayri_ayri_basilir(self):
        self.assertEqual(self.f.vakalar().get("core/00-temel.md"), "V4t")
        c = self.cikti(self.f.calistir("oneri", "core/00-temel.md"))
        self.assertIn("T→L", c)
        self.assertIn("T→Y", c)

    def test_V4c_cakisma_cikis_1_ve_isaretli_dosya(self):
        self.assertEqual(self.f.vakalar().get("scripts/doctor.py"), "V4c")
        r = self.f.calistir("oneri", "scripts/doctor.py")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        o = (self.f.durum_dizini() / "oneri" / "scripts/doctor.py").read_text(encoding="utf-8")
        self.assertIn("<<<<<<<", o)

    def test_esik_asilirsa_cikis_3_ve_elle_diff(self):
        """K6(a): >3 çakışma bloğu ya da yerel fark >%50 → birleştirme denenmez."""
        self.f.yerel_degistir("core/00-temel.md", "tamamen\nbaska\nbir\nicerik\nburada\n")
        self.assertEqual(self.f.calistir("plan").returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        r = self.f.calistir("oneri", "core/00-temel.md")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        self.assertIn("V4c+ESIK", self.cikti(r))
        self.assertIn("birleştirme DENENMEDİ", self.cikti(r))
        self.assertTrue((self.f.durum_dizini() / "elle" / "core/00-temel.md.yerel.diff").exists())
        self.assertTrue((self.f.durum_dizini() / "elle" / "core/00-temel.md.yeni.diff").exists())

    def test_isaretle_birlesik_yazar_ve_geri_okuyup_dogrular(self):
        self.f.calistir("oneri", "core/00-temel.md")
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "birlesik")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.durum()["dosyalar"]["core/00-temel.md"]["durum"], "dogrulandi")
        disk = (self.f.tuketici / "core/00-temel.md").read_text(encoding="utf-8")
        self.assertIn("# Çekirdek v3", disk)
        self.assertIn("son yerel", disk)

    def test_isaretle_cakisma_isareti_kalirsa_cikis_1(self):
        """§5 V4c adım 5: script çakışma işareti kalmadığını doğrular."""
        self.f.calistir("oneri", "scripts/doctor.py")
        r = self.f.calistir("isaretle", "scripts/doctor.py", "--karar", "birlesik")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("<<<<<<<", self.cikti(r))

    def test_isaretle_diff3_taban_bloku_kalirsa_cikis_1(self):
        """`git merge-file --diff3` DÖRT işaret üretir; dördüncüsü `|||||||  TABAN:`.

        Üçü silinip TABAN bloğu bırakılırsa tabanın ESKİ satırları sessizce birleşmiş içeriğe
        karışır ve motor dosyayı `dogrulandi` sayar. `V4c.md:39-40,52-54` kartı kullanıcıya
        "dördünü de sil, kalırsa FAIL" diye söz verir — söz kodda karşılanmalıdır.
        """
        self.f.calistir("oneri", "scripts/doctor.py")
        o = self.f.durum_dizini() / "oneri" / "scripts/doctor.py"
        metin = o.read_text(encoding="utf-8")
        self.assertIn("|||||||", metin, "fixture diff3 üretmeliydi (yoksa test anlamsız)")
        kirpik = "".join(s for s in metin.splitlines(keepends=True)
                         if not s.startswith(("<<<<<<<", "=======", ">>>>>>>")))
        self.assertIn("|||||||", kirpik, "kırpma dördüncü işareti BIRAKMALI")
        o.write_text(kirpik, encoding="utf-8")
        r = self.f.calistir("isaretle", "scripts/doctor.py", "--karar", "birlesik")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("|||||||", self.cikti(r))
        self.assertNotEqual(self.f.durum()["dosyalar"]["scripts/doctor.py"]["durum"], "dogrulandi")

    def test_isaretle_yeni_ve_yerel_kararlari(self):
        r = self.f.calistir("isaretle", "docs/logo.png", "--karar", "yeni")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((self.f.tuketici / "docs/logo.png").read_bytes(), b"\x00\x01PNG-v3\x00")
        r = self.f.calistir("isaretle", "docs/silinecek.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((self.f.tuketici / "docs/silinecek.md").read_text(encoding="utf-8"),
                         "silinecek YEREL\n")

    def test_isaretle_yeniden_adlandir_kullanicinin_dosyasini_korur(self):
        r = self.f.calistir("isaretle", "skills/cakisan/SKILL.md", "--karar", "yeniden-adlandir")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("KULLANICININ", (self.f.tuketici / "skills/cakisan/SKILL.md.yerel")
                      .read_text(encoding="utf-8"))
        self.assertIn("template surumu", (self.f.tuketici / "skills/cakisan/SKILL.md")
                      .read_text(encoding="utf-8"))

    def test_isaretle_gecersiz_karar_cikis_2(self):
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "uydurma")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("geçersiz karar", self.cikti(r))

    def test_V7de_karar_yeni_REDDEDILIR(self):
        """§5 V7 kartı yalnız `yeniden-adlandir|yerel` tanımlar. `GECERLI_KARARLAR` her kararı
        her vakaya uyguladığı için `yeni`, kullanıcının YEDEKLENMEMİŞ dosyasını (izlenmeyen ⇒
        `guncelle-oncesi-*` etiketinde blob'u yok) geri alınamaz biçimde eziyordu."""
        r = self.f.calistir("isaretle", "skills/cakisan/SKILL.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("V7", self.cikti(r))
        self.assertIn("KULLANICININ", (self.f.tuketici / "skills/cakisan/SKILL.md")
                      .read_text(encoding="utf-8"))
        self.assertFalse((self.f.tuketici / "skills/cakisan/SKILL.md.yerel").exists())

    def test_kontrol_grubu_V7de_yeniden_adlandir_KABUL_EDILIR(self):
        """Aynı dosya, aynı yol — yalnız karar izinli. Matris gevşetme değil, daraltmadır."""
        r = self.f.calistir("isaretle", "skills/cakisan/SKILL.md", "--karar", "yeniden-adlandir")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_V6dde_karar_yeni_REDDEDILIR(self):
        """V6d = "template sildi, sende değişmiş → dokunma, bilgi ver" (§5). `yeni` anlamsız."""
        r = self.f.calistir("isaretle", "docs/silinecek.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("V6d", self.cikti(r))

    def test_hazirla_SONRASI_duzenleme_yikici_kararda_yerel_olarak_saklanir(self):
        """`hazirla` etiketi atıldıktan SONRA yapılan düzenlemenin etikette blob'u YOKTUR;
        `--karar yeni` onu yedeksiz ezerdi."""
        self.f.yerel_degistir("core/00-temel.md",
                              "CORE-ID: AXET-CORE-TEST\n# Çekirdek\nsatir1\nsatir2\nsatir3\n"
                              "satir4\nsatir5\nsatir6\nson yerel\nETIKETTEN SONRA EKLENDI\n")
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("ETIKETTEN SONRA EKLENDI", (self.f.tuketici / "core/00-temel.md.yerel")
                      .read_text(encoding="utf-8"))

    def test_kontrol_grubu_etiketli_icerikte_yerel_kopya_URETILMEZ(self):
        """Yedeği olan içerik için `.yerel` gürültüsü üretilmez — kural dar olmalı."""
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.f.tuketici / "core/00-temel.md.yerel").exists())

    def test_ertelendi_gerekce_ister(self):
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "ertelendi")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("GEREKÇE ister", self.cikti(r))
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "ertelendi",
                            "--gerekce", "elle bakılacak")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.durum()["dosyalar"]["core/00-temel.md"]["durum"], "atlandi")

    def test_crlf_dosyada_birlesme_satir_sonunu_bozmaz(self):
        """TASARIM §14 DOĞRULANMADI kalemi: `git merge-file` CRLF/LF karışık dosyada.
        `kur.cmd` deposunda LF, çalışma ağacında CRLF (`.gitattributes` eol=crlf)."""
        r = self.f.calistir("oneri", "kur.cmd")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.calistir("isaretle", "kur.cmd", "--karar", "birlesik").returncode,
                         0)
        ham = (self.f.tuketici / "kur.cmd").read_bytes()
        self.assertIn(b"rem yerelden", ham)
        self.assertIn(b"rem bizden", ham)
        self.assertEqual(ham.count(b"\r\n"), ham.count(b"\n"),
                         "çalışma ağacında HER satır sonu CRLF olmalı (eol=crlf); çıplak LF "
                         "kalırsa cmd.exe goto/etiket satırlarını yanlış okur")
        self.assertNotIn(b"\r\r\n", ham, "satır sonu ikizlenmesi (CR çoğaldı)")


# =====================================================================================================
# 7. ÖLÇÜM / BÜTÜNLÜK / GERİ AL / KAPANIŞ / DURUM
# =====================================================================================================
class AkisTest(GuncelleTemel):
    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def birlesik_isaretle(self, yol: str) -> None:
        """`oneri` + `isaretle --karar birlesik`: sonucu `Klon.yaz` ile YALNIZ çalışma ağacına
        yazar (stage ETMEZ) ⇒ kapanışın `git add`i için tek geçerli ölçüm çapası."""
        r = self.f.calistir("oneri", yol)
        self.assertIn(r.returncode, (0, 1), self.cikti(r))
        r = self.f.calistir("isaretle", yol, "--karar", "birlesik")
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def _tum_yargilari_kapat(self, haric: str | None = None) -> None:
        for yol, karar in (("core/00-temel.md", "yeni"), ("scripts/doctor.py", "yeni"),
                           ("kur.cmd", "yeni"), ("docs/logo.png", "yeni"),
                           ("docs/tasinan2.md", "yeni"),
                           ("skills/cakisan/SKILL.md", "yeniden-adlandir"),
                           ("docs/silinecek.md", "yerel")):
            if yol == haric:
                continue
            r = self.f.calistir("isaretle", yol, "--karar", karar)
            self.assertEqual(r.returncode, 0, f"{yol}: {self.cikti(r)}")

    def test_olc_once_ve_sonra_kaydeder(self):
        r = self.f.calistir("olc", "--asama", "once")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        self.assertTrue(veri["testler"], "en az bir test komutu seçilmeliydi")

    def test_olc_gecersiz_asama_cikis_2(self):
        self.assertEqual(self.f.calistir("olc", "--asama", "ortada").returncode, 2)

    def test_geri_al_tek_dosya(self):
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.assertTrue((self.f.tuketici / "scripts/sap_stamp.py").exists())
        r = self.f.calistir("geri-al", "scripts/sap_stamp.py")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertFalse((self.f.tuketici / "scripts/sap_stamp.py").exists(),
                         "tabanda olmayan dosya geri almada silinmeli")

    def test_geri_al_hepsi_yerel_degisikligi_korur(self):
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("geri-al", "--hepsi")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual((self.f.tuketici / "LICENSE").read_text(encoding="utf-8"), "MIT yerel\n")
        self.assertIn("doctor YEREL",
                      (self.f.tuketici / "scripts/doctor.py").read_text(encoding="utf-8"))

    def test_durum_tablo_basar(self):
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("durum")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("scripts/sap_stamp.py", self.cikti(r))
        self.assertIn("dogrulandi", self.cikti(r))

    # --- §12a KAPANIŞ MUTASYONLARI -------------------------------------------------------------
    def test_kapanis_bekleyen_dosya_varsa_1(self):
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("KAPANMADI", (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8"))

    def test_kapanis_durum_json_elle_dogrulandi_yapilirsa_disk_farkli_1(self):
        """§6: ajanın 'yaptım' demesi durum değiştirmez — kapanış diskten yeniden doğrular.

        ⚠ Akışın GERİ KALANI tamamlanır (ölçüm + özel adım + bütünlük), yoksa `kapanis` zaten
        başka bir sebeple 1 döner ve test bu kuralı ölçmemiş olur. Mutasyon M4 ilk hâlinde tam
        olarak bunu gösterdi: disk doğrulaması kapatıldığı hâlde test YEŞİL kalıyordu.
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        # kontrol grubu: bu noktada akış TEMİZ kapanmalı
        self.assertEqual(self.f.calistir("kapanis").returncode, 0,
                         "kontrol grubu kırmızıysa asıl ölçüm anlamsız")
        d = self.f.durum()
        for k in d["dosyalar"].values():
            k["durum"] = "dogrulandi"
        (self.f.durum_dizini() / "durum.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
        # diski boz
        self.f.yerel_degistir("scripts/sap_stamp.py", "elle bozuldu\n")
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertIn("scripts/sap_stamp.py", self.cikti(r))

    def test_kapanis_kabul_ile_cikis_3_ve_gerekce_raporda(self):
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("kapanis", "--kabul", "bilerek yarım bırakıldı")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("bilerek yarım bırakıldı", rapor)

    def test_ozel_adim_kosar_ve_duruma_yazilir(self):
        self.ozel_adimlari_kostur()
        ozel = self.f.durum()["ozel_adimlar"]
        self.assertTrue(ozel)
        self.assertTrue(all(v["durum"] in ("kostu", "manuel") for v in ozel.values()), ozel)

    def test_ozel_adim_bilinmeyen_sinif_cikis_2(self):
        self.assertEqual(self.f.calistir("ozel-adim", "boyle-bir-sinif-yok").returncode, 2)

    def test_kapanis_tamamlanmis_akista_0_ve_uygulanan_json_guncellenir(self):
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        u = json.loads((self.f.durum_dizini() / "uygulanan.json").read_text(encoding="utf-8"))
        self.assertEqual(u["dosyalar"]["scripts/sap_stamp.py"], "v3")
        self.assertIn("3-01", u["kalemler"])
        # kapanış commit'i atıldı
        son = self.git(self.f.tuketici, "log", "-1", "--format=%s").stdout
        self.assertTrue(son.startswith("guncelle:"), son)

    def test_Z58_kapanis_atlandi_kaleme_neden_yazar_ertelendi_ve_is_yok(self):
        """Z58: 3-05'in üç dosyası da ertelendi ⇒ `neden: ertelendi`. 2-01/2-02'nin dosyaları
        (doctor.py, 00-temel.md) v3'ün 3-01/3-02'sinde yeniden beyan edildiği için plan onları
        SONRAKİ kaleme bağlar (komut_plan adım 3) ⇒ plandaki `dosyalar` boş ⇒ `neden: is-yok`.
        Uygulanmış kalem `neden` taşımaz."""
        plan_k = {k["id"]: k for k in self.f.plan()["kalemler"]}
        self.assertEqual(plan_k["2-01"]["dosyalar"], [], "kurgu: 2-01'in dosyası sonraki kaleme geçmeli")
        self.assertEqual(plan_k["2-02"]["dosyalar"], [], "kurgu: 2-02'nin dosyası sonraki kaleme geçmeli")
        self.assertEqual(sorted(d["yol"] for d in plan_k["3-05"]["dosyalar"]),
                         ["docs/logo.png", "kur.cmd", "skills/cakisan/SKILL.md"])
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        ertelenen = ("docs/logo.png", "kur.cmd", "skills/cakisan/SKILL.md")
        for yol in ("core/00-temel.md", "scripts/doctor.py", "docs/tasinan2.md"):
            self.assertEqual(self.f.calistir("isaretle", yol, "--karar", "yeni").returncode, 0)
        self.assertEqual(self.f.calistir("isaretle", "docs/silinecek.md", "--karar", "yerel").returncode, 0)
        for yol in ertelenen:
            r = self.f.calistir("isaretle", yol, "--karar", "ertelendi", "--gerekce", "sonra")
            self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        u = json.loads((self.f.durum_dizini() / "uygulanan.json").read_text(encoding="utf-8"))
        kal = u["kalemler"]
        self.assertEqual((kal["3-05"]["durum"], kal["3-05"].get("neden")), ("atlandi", "ertelendi"))
        self.assertEqual((kal["2-01"]["durum"], kal["2-01"].get("neden")), ("atlandi", "is-yok"))
        self.assertEqual((kal["2-02"]["durum"], kal["2-02"].get("neden")), ("atlandi", "is-yok"))
        self.assertEqual(kal["3-01"]["durum"], "uygulandi")
        self.assertNotIn("neden", kal["3-01"], "uygulanmış kalem neden taşımaz")

    def test_Z58_kapanis_kabul_ile_bekleyen_kalem_neden_kabul(self):
        """`kapanis --kabul` (kod 3) da mühür basar; dosyası `bekliyor` kalan kalem `is-yok`
        DEĞİLDİR (yoksa önkoşul uyarısı sessizce kaybolurdu) ⇒ `neden: kabul`."""
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        r = self.f.calistir("kapanis", "--kabul", "bilerek yarım")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        kal = json.loads((self.f.durum_dizini() / "uygulanan.json").read_text(encoding="utf-8"))["kalemler"]
        self.assertEqual(self.f.durum()["dosyalar"]["core/00-temel.md"]["durum"], "bekliyor",
                         "kurgu: 3-02'nin tek dosyası bekliyor kalmalı")
        self.assertEqual((kal["3-02"]["durum"], kal["3-02"].get("neden")), ("atlandi", "kabul"))
        # Z58 bug gate: 2-01'in tek dosyası (doctor.py) 3-01'e devredildi ve orada `bekliyor` kaldı
        # ⇒ 2-01'in içeriği İNMEDİ ⇒ `kabul` (eskiden "dosyasız" diye `is-yok` deniyordu).
        self.assertEqual(self.f.durum()["dosyalar"]["scripts/doctor.py"].get("durum", "bekliyor"),
                         "bekliyor", "kurgu: devredilen doctor.py inmemeli")
        self.assertEqual(kal["2-01"].get("neden"), "kabul")

    # --- Z58 bug gate (v0.5.4, MEDIUM, ölçüldü): `is-yok` yalnız DEVREDİLEN dosya gerçekten indiyse --
    # Plan her yolu onu beyan eden EN SON kaleme bağlar ⇒ 2-01'in tek dosyası (doctor.py) 3-01'e geçer,
    # 2-01'in `dosyalar`'ı boş kalır. Eski `_atlandi_nedeni` "dosyasız ⇒ is-yok" diyordu: 3-01'de
    # doctor.py ERTELENSE bile 2-01 `is-yok` mühürleniyor, içeriği diske inmiyor ve 2-01'e bağlı
    # kalemin sonraki turdaki UYARI'sı sessizce kayboluyordu (Z58 öncesi UYARI veriyordu ⇒ gerileme).
    # Kontrol grubu: `test_Z58_kapanis_atlandi_kaleme_neden_yazar_ertelendi_ve_is_yok` — orada
    # doctor.py İNER (3-01 uygulandi) ve 2-01 `is-yok` KALIR.
    def _kapanis_doctor_ertelendi(self) -> dict:
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        kararlar = {"core/00-temel.md": "yeni", "docs/tasinan2.md": "yeni", "kur.cmd": "yeni",
                    "docs/logo.png": "yeni", "skills/cakisan/SKILL.md": "yeniden-adlandir",
                    "docs/silinecek.md": "yerel"}
        for yol, kr in kararlar.items():
            r = self.f.calistir("isaretle", yol, "--karar", kr)
            self.assertEqual(r.returncode, 0, self.cikti(r))
        r = self.f.calistir("isaretle", "scripts/doctor.py", "--karar", "ertelendi",
                            "--gerekce", "sonra")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        return json.loads((self.f.durum_dizini() / "uygulanan.json")
                          .read_text(encoding="utf-8"))

    def test_Z58_plan_devredilen_yolu_ve_sahibini_kaydeder(self):
        plan_k = {k["id"]: k for k in self.f.plan()["kalemler"]}
        self.assertEqual(plan_k["2-01"]["dosyalar"], [], "kurgu: 2-01'in dosyası sonraki kaleme geçmeli")
        self.assertEqual(plan_k["2-01"].get("devredilen"), {"scripts/doctor.py": "3-01"})
        self.assertEqual(plan_k["3-01"].get("devredilen"), {}, "sahip kalemin devrettiği yol yok")

    def test_Z58_kapanis_sahip_kalemde_dosya_ertelendiyse_devreden_kalem_is_yok_DEGIL(self):
        u = self._kapanis_doctor_ertelendi()
        kal = u["kalemler"]
        self.assertEqual(kal["3-01"]["durum"], "uygulandi", "kurgu: 3-01'in sap_stamp.py'si indi")
        self.assertNotIn("scripts/doctor.py", u["dosyalar"], "kurgu: doctor.py diske İNMEDİ")
        self.assertEqual((kal["2-01"]["durum"], kal["2-01"].get("neden")), ("atlandi", "ertelendi"),
                         "2-01'in içeriği inmedi — is-yok sayılırsa bağımlının UYARI'sı kaybolur")

    def test_Z58_kapanis_eski_plan_devredilen_alani_yok_is_yok_DEMEZ(self):
        """Plan `devredilen` taşımıyorsa (v0.5.4 öncesi motorun planı) dosyasız kalemin iş-yok mu
        devredilmiş mi olduğu ölçülemez ⇒ fail-closed: `neden` bilinmiyor (null), `is-yok` DEĞİL."""
        yol = self.f.durum_dizini() / "plan.json"
        plan = self.f.plan()
        for kalem in plan["kalemler"]:
            kalem.pop("devredilen", None)
        yol.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        kal = self._kapanis_doctor_ertelendi()["kalemler"]
        self.assertEqual(kal["2-01"]["durum"], "atlandi")
        self.assertIn("neden", kal["2-01"], "alan null yazılır: 'bilinmiyor' ≠ alan unutuldu")
        self.assertIsNone(kal["2-01"]["neden"])

    def test_kapanis_kullanicinin_izlenmeyen_dosyalarini_COMMITLEMEZ(self):
        """§1/§2a kapsam ihlali: `kapanis`'in `git add -A`'sı kullanıcının izlenmeyen
        dosyalarını klona commit'liyordu. Yan etki: `kullanici_dosya_sayisi()` `--others
        --exclude-standard` kullandığı için ilk kapanıştan sonra VKD sayacı 0'a düşüyordu."""
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.birlesik_isaretle("core/00-temel.md")
        self._tum_yargilari_kapat(haric="core/00-temel.md")
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))

        izlenen = self.git(self.f.tuketici, "ls-files", "--", "kendi-notum.md").stdout.strip()
        self.assertEqual(izlenen, "", "kullanıcının kendi dosyası klona COMMIT EDİLDİ (§2a)")
        izlenmeyen = self.git(self.f.tuketici, "ls-files", "--others",
                              "--exclude-standard").stdout.split()
        self.assertIn("kendi-notum.md", izlenmeyen,
                      "VKD sayacının okuduğu küme boşaldı — sayaç bir daha hiç saymaz")
        # yine de plandaki dosyalar commit'lendi (kural daraltma, iptal DEĞİL)
        # ⛔ VAKUM KANIT onarımı: eski hâl `scripts/sap_stamp.py`yi arıyordu; o yolu kapanışın
        # `git add`i DEĞİL, `uygula`nın `checkout_yol`u (`git checkout ref -- <yol>`) stage'ler
        # ⇒ `git add` `fatal` ile tamamen düşmüşken bile assertion GEÇİYORDU (ölçüldü).
        # `--karar birlesik` sonucu `Klon.yaz` ile YALNIZ çalışma ağacına yazılır; onu commit'e
        # sokabilen TEK şey kapanışın `git add`idir ⇒ ölçüm çapası odur.
        dosyalar = self.git(self.f.tuketici, "show", "--name-only", "--format=", "HEAD").stdout
        self.assertIn("core/00-temel.md", dosyalar,
                      "`git add` ile stage'lenebilen TEK yol commit'e girmedi")
        # ve `git add`in ÇIKIŞI ayrıca ölçülür — dolaylı kanıt yetmez
        self.assertNotIn("`git add` başarısız", self.cikti(r))
        self.assertNotIn("did not match any files", self.cikti(r))

    def test_kapanis_butunluk_kosmamissa_1(self):
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # ⛔ VAKUM ASSERTION onarımı: RAPOR.md "## Bütünlük turu" başlığını HER koşulda basar
        # ⇒ `assertIn("bütünlük", ...)` ihlal YOKKEN de geçiyordu. Ölçüt `EKSİK:` satırıdır.
        eksikler = [x for x in self.cikti(r).splitlines() if x.startswith("EKSİK:")]
        self.assertTrue(any("bütünlük turu koşmadı" in x for x in eksikler), eksikler)

    def test_kapanis_yeni_kirmizi_testte_1(self):
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        # sonra-ölçümüne elle yeni kırmızı koy
        y = self.f.durum_dizini() / "olcum-sonra.json"
        veri = json.loads(y.read_text(encoding="utf-8"))
        for t in veri["testler"]:
            t["cikis"] = 1
        y.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # ⛔ VAKUM ASSERTION onarımı: "## Yeni kırmızı testler" başlığı HER koşulda basılır.
        eksikler = [x for x in self.cikti(r).splitlines() if x.startswith("EKSİK:")]
        self.assertTrue(any("YENİ kırmızı" in x for x in eksikler), eksikler)

    def test_kapanis_ozel_adim_kosmamissa_1(self):
        """config/permissions.json sınıfının özel adımı (install.py) koşmadan kapanmaz."""
        # permissions.json'u V4e'den çıkar: yerelde tabana döndür → V1 olur, özel adım gerekir
        self.f.yerel_degistir("config/permissions.json", '{"deny": ["a"]}\n')
        self.assertEqual(self.f.calistir("plan").returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # ⛔ VAKUM ASSERTION onarımı: "özel adım" dizgesi raporun/çıktının başka yerlerinde de
        # geçiyordu ⇒ ölçüt `EKSİK:` satırının kendisidir.
        eksikler = [x for x in self.cikti(r).splitlines() if x.startswith("EKSİK:")]
        self.assertTrue(any("özel adım koşmadı" in x for x in eksikler), eksikler)

    def test_kapanis_TEK_eksik_dosya_icin_bile_1(self):
        """⛔ VAKUM ASSERTION onarımı (gate mutasyonu M1): `kapanis`'in atlanamazlık kuralı
        tamamen kaldırıldığında `AkisTest` 15/15 YEŞİL kalıyordu.

        Sebep: var olan test `uygula` sonrası kapanış çağırıyordu ve o noktada `eksikler` zaten
        "bütünlük turu koşmadı" ile DOLUYDU ⇒ beklenen hata, ölçülmek İSTENENDEN önce
        tetikleniyordu. Burada akışın geri kalanı TAMAM; yalnız TEK dosya `bekliyor`. Kontrol
        grubu aynı testin içinde: o dosya da kapatılınca aynı akış 0 döner.
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat(haric="docs/silinecek.md")
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)

        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        eksikler = [s for s in self.cikti(r).splitlines() if s.startswith("EKSİK:")]
        self.assertEqual(len(eksikler), 1, f"tek eksik bekleniyordu: {eksikler}")
        self.assertIn("docs/silinecek.md", eksikler[0])
        self.assertIn("bekliyor", eksikler[0])

        # kontrol grubu — eksik kapatılınca AYNI akış 0 döner (yani 1'i üreten şey bu kuraldı)
        self.assertEqual(
            self.f.calistir("isaretle", "docs/silinecek.md", "--karar", "yerel").returncode, 0)
        r2 = self.f.calistir("kapanis")
        self.assertEqual(r2.returncode, 0, self.cikti(r2))

    def test_kapanis_BIRLESIK_sonucu_KAPANIS_COMMITINE_girer(self):
        """⛔ SESSİZ VERİ KAYBI kapsayıcısı (BLOCKER-1/4).

        Bugüne dek 146 testin HİÇBİRİ `--karar birlesik` yolunu kapanışa kadar sürmüyordu.
        Ölçülen kusur: `add_yollari` süzgeci `blob_sha("HEAD", y)` kullanıyordu; `Klon.sil()`in
        dokunduğu yol (V6 `docs/silinecek2.md`, V1R `docs/tasinacak.md`) index'ten düşer ama
        HEAD'de DURUR ⇒ süzgeçten geçer ⇒ `git add` `fatal: pathspec … did not match any files`
        der ve o çağrıda HİÇBİR yolu stage etmez ⇒ birleştirilmiş içerik commit'e GİRMEZ,
        `kapanis` yine rc=0 döner ("temiz kapandı" yalanı).
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.birlesik_isaretle("core/00-temel.md")
        self._tum_yargilari_kapat(haric="core/00-temel.md")
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)

        # kontrol grubu: diskte birleşme GERÇEKTEN var (yoksa aşağıdaki ölçüm anlamsız)
        diskte = (self.f.tuketici / "core/00-temel.md").read_text(encoding="utf-8")
        self.assertIn("Çekirdek v3", diskte)
        self.assertIn("son yerel", diskte)

        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        # ① `git add`in ÇIKIŞI ölçülür
        self.assertNotIn("did not match any files", self.cikti(r))
        self.assertNotIn("`git add` başarısız", self.cikti(r))
        # ② asıl ölçüm: birleştirme sonucu KAPANIŞ COMMİT'İNDE mi
        head = self.git(self.f.tuketici, "show", "HEAD:core/00-temel.md").stdout
        self.assertIn("Çekirdek v3", head, "birleştirme sonucu kapanış commit'ine GİRMEDİ")
        self.assertIn("son yerel", head, "kullanıcının satırı commit'te yok")
        # ③ commit ile çalışma ağacı ayrışmıyor
        kirli = self.git(self.f.tuketici, "status", "--porcelain",
                         "--", "core/00-temel.md").stdout.strip()
        self.assertEqual(kirli, "", "kapanıştan sonra dosya hâlâ değişmiş görünüyor")
        # ④ silmeler ve taşımalar da commit'te (`Klon.sil` stage'lemişti)
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertNotIn("docs/silinecek2.md", agac, "V6 silmesi kapanış commit'ine girmedi")
        self.assertNotIn("docs/tasinacak.md", agac, "V1R taşımasının kaynağı commit'te duruyor")
        self.assertIn("docs/tasindi.md", agac, "V1R taşımasının hedefi commit'te yok")

    def test_kapanis_git_add_BASARISIZSA_eksik_olur_ve_1_doner(self):
        """⛔ BLOCKER-2: `git add` başarısızlığı SESSİZ `UYARI:` idi ⇒ `kapanis` 0 dönüyor,
        `uygulanan.json` mühürleniyor, RAPOR.md "KAPANMADI" demiyordu.

        Başarısızlık burada BAŞKA bir yolla zorlanır (düzeltilen kusurla değil): V7 kararı
        `yeniden-adlandir` template dosyasını `skills/cakisan/SKILL.md`'ye yazar (git checkout
        ile ⇒ STAGE'li); test onu `git rm --cached` ile İZLENMEYEN yapıp `.gitignore`a ekler ⇒
        `git add -- <yol>` `rc=1` + "ignored by one of your .gitignore files" verir.
        (Eskiden `yerel` kararı kullanılıyordu: dosya doğal olarak izlenmeyendi. M-6'dan beri
        `yerel` + izlenmeyen dosya kapanışa hiç girmez — bkz.
        test_V7_yerel_izlenmeyen_dosya_kapanis_commitine_GIRMEZ.)
        Ek (P2 kurulum-sonrası ⓐ): başarısızlıktan sonra index'te kapanışın yarım bıraktığı stage
        (`Klon.sil()` silmeleri) KALMAZ.
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat(haric="skills/cakisan/SKILL.md")
        r = self.f.calistir("isaretle", "skills/cakisan/SKILL.md", "--karar", "yeniden-adlandir")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)

        self.git(self.f.tuketici, "rm", "-q", "--cached", "--", "skills/cakisan/SKILL.md")
        # kontrol grubu: yol gerçekten İZLENMİYOR (yoksa .gitignore `git add`i etkilemez)
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--",
                                  "skills/cakisan/SKILL.md").stdout.strip(), "")
        # kontrol grubu: V6 silmesi kapanıştan ÖNCE stage'li (yoksa aşağıdaki "index temiz" vakum)
        self.assertIn("docs/silinecek2.md",
                      self.git(self.f.tuketici, "diff", "--cached", "--name-only").stdout)
        gi = self.f.tuketici / ".gitignore"
        gi.write_text(gi.read_text(encoding="utf-8") + "/skills/cakisan/\n", encoding="utf-8")

        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        eksikler = [x for x in self.cikti(r).splitlines() if x.startswith("EKSİK:")]
        # ⚠ SEBEP de ölçülür: aksi hâlde test, düzeltilen ESKİ kusur yüzünden de geçerdi
        self.assertTrue(any("`git add` başarısız" in x
                            and "ignored by one of your .gitignore files" in x
                            and "skills/cakisan" in x for x in eksikler), eksikler)
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("KAPANMADI", rapor)
        self.assertIn("`git add` başarısız", rapor)
        # mühür BASILMAMALI — "uygulandı" yalanı `komut_plan`da kalemi kalıcı olarak düşürür
        self.assertFalse((self.f.durum_dizini() / "uygulanan.json").exists(),
                         "git add patladığı hâlde uygulanan.json mühürlendi")
        # ⓐ index plandaki yollar için HEAD'e geri alındı — yarım stage (V6 silmesi) KALMADI
        self.assertIn("index'i HEAD'e geri alındı", self.cikti(r))
        stage = self.git(self.f.tuketici, "diff", "--cached", "--name-only").stdout.strip()
        self.assertEqual(stage, "", f"başarısız kapanıştan sonra index'te yarım stage kaldı: {stage}")
        # çalışma ağacı ise DEĞİŞMEDİ: silinen dosya diskte yok, yeniden-adlandırılan duruyor
        self.assertFalse((self.f.tuketici / "docs/silinecek2.md").exists())
        self.assertTrue((self.f.tuketici / "skills/cakisan/SKILL.md").exists())

    def test_V7_yerel_izlenmeyen_dosya_kapanis_commitine_GIRMEZ(self):
        """M-6 (kullanıcı kararı 2026-09-18, TASARIM §6): `--karar yerel` = "bu dosyaya DOKUNMA".

        Eskiden kapanış, İZLENMEYEN bir kullanıcı dosyasını `git add` ile commit'e alıyordu —
        kullanıcının hiç izletmediği dosya aXet commit'iyle depoya giriyordu. Artık girmez:
        dosya diskte kullanıcının içeriğiyle durur, izlenmeyen kalır, kapanış 0 döner.
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat(haric="skills/cakisan/SKILL.md")
        r = self.f.calistir("isaretle", "skills/cakisan/SKILL.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        # kontrol grubu: yol kapanıştan ÖNCE izlenmiyor ve diskte kullanıcının içeriği var
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--",
                                  "skills/cakisan/SKILL.md").stdout.strip(), "")
        once = (self.f.tuketici / "skills/cakisan/SKILL.md").read_text(encoding="utf-8")

        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertNotIn("skills/cakisan/SKILL.md", agac,
                         "`yerel` kararlı izlenmeyen dosya kapanış commit'ine girdi")
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--",
                                  "skills/cakisan/SKILL.md").stdout.strip(), "")
        self.assertEqual((self.f.tuketici / "skills/cakisan/SKILL.md").read_text(encoding="utf-8"),
                         once, "`yerel` kararlı dosyanın içeriği değişti")
        # kontrol grubu: aynı kapanışta DİĞER değişiklikler commit'e girdi (süzgeç aşırı değil)
        self.assertNotIn("docs/silinecek2.md", agac, "V6 silmesi kapanış commit'ine girmedi")

    def test_V4R_birlesik_sonra_ertelendi_yarim_tasima_uretmez(self):
        """Bug gate 2026-09-19 ikinci tur (ölçüldü): "motor yazmadıysa her izlenmeyen yolu koru"
        süzgeci, `birlesik` ile YENİ yola yazılmış V4R dosyası sonradan `ertelendi` yapılınca yeni yolu
        commit dışı bırakıyordu; eski yolun silmesi ise stage'liydi ⇒ HEAD'de İKİ yol da yoktu."""
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.birlesik_isaretle("docs/tasinan2.md")
        self._tum_yargilari_kapat(haric="docs/tasinan2.md")
        r = self.f.calistir("isaretle", "docs/tasinan2.md", "--karar", "ertelendi", "--gerekce", "vazgectim")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        # kontrol grubu: yeni yol motor tarafından yazıldı ve henüz izlenmiyor
        self.assertTrue((self.f.tuketici / "docs/tasindi2.md").is_file())
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--", "docs/tasindi2.md").stdout.strip(), "")
        self.ozel_adimlari_kostur()
        self.f.calistir("olc", "--asama", "sonra")
        self.f.calistir("butunluk")
        r = self.f.calistir("kapanis")
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertTrue("docs/tasindi2.md" in agac or "docs/tasinan2.md" in agac,
                        f"yarım taşıma: iki yol da HEAD'de yok\n{self.cikti(r)}")

    def test_V4R_birlesik_sonra_yerel_yarim_tasima_uretmez(self):
        """Bug gate 2026-09-19 üçüncü tur (ölçüldü): aynı sınıf `yerel` kararında — süzgeç `yerel` için
        yeni yolu da koruyordu; taşıma motor tarafından yapılmışken bu HEAD'de iki yolu da yok ediyordu."""
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.birlesik_isaretle("docs/tasinan2.md")
        self._tum_yargilari_kapat(haric="docs/tasinan2.md")
        r = self.f.calistir("isaretle", "docs/tasinan2.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        # kontrol grubu: taşıma gerçekten olmuş (eski yol diskte yok, yeni yol izlenmiyor)
        self.assertFalse((self.f.tuketici / "docs/tasinan2.md").exists())
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--", "docs/tasindi2.md").stdout.strip(), "")
        self.ozel_adimlari_kostur()
        self.f.calistir("olc", "--asama", "sonra")
        self.f.calistir("butunluk")
        r = self.f.calistir("kapanis")
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertTrue("docs/tasindi2.md" in agac or "docs/tasinan2.md" in agac,
                        f"yarım taşıma: iki yol da HEAD'de yok\n{self.cikti(r)}")

    def test_kapanis_COMMIT_BASARISIZSA_eksik_olur_ve_muhur_basilmaz(self):
        """⛔ BLOCKER-3 (kardeş vaka): commit'in kendisi patlarsa da yalnız `UYARI:` basılıyordu.

        Ayrıca `rc=1` KOŞULSUZ tolere ediliyordu ("commit edilecek bir şey yok" varsayımı).
        Burada stage'de fark VAR ve commit imzalanamadığı için patlar (`gpg.program` yok ⇒
        git rc=128 verir). Hook reddinin ürettiği rc=1 AYRI testte ölçülür
        (`KapanisKabulVeHookTest.test_hook_rc1_...`). `--no-verify` imzalamayı ATLAMAZ.
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.birlesik_isaretle("core/00-temel.md")
        self._tum_yargilari_kapat(haric="core/00-temel.md")
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)
        self.git(self.f.tuketici, "config", "commit.gpgsign", "true")
        self.git(self.f.tuketici, "config", "gpg.program", "boyle-bir-program-yok-xyz")

        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        eksikler = [x for x in self.cikti(r).splitlines() if x.startswith("EKSİK:")]
        self.assertTrue(any("commit'i atılamadı" in x for x in eksikler), eksikler)
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("KAPANMADI", rapor)
        self.assertIn("commit'i atılamadı", rapor)
        self.assertFalse((self.f.durum_dizini() / "uygulanan.json").exists(),
                         "commit patladığı hâlde uygulanan.json mühürlendi")
        # kontrol grubu: imzalama kapatılınca AYNI akış 0 döner ve mühür basılır
        self.git(self.f.tuketici, "config", "commit.gpgsign", "false")
        r2 = self.f.calistir("kapanis")
        self.assertEqual(r2.returncode, 0, self.cikti(r2))
        self.assertTrue((self.f.durum_dizini() / "uygulanan.json").exists())

    def test_rapor_kapsam_beyani_iceriyor(self):
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self.f.calistir("kapanis")
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("KAPSAM —", rapor)
        self.assertIn("bakılmayanlar", rapor)


class Z58AtlandiNedeniBirimTest(unittest.TestCase):
    """`_atlandi_nedeni` birim ölçümü: akış fikstüründe kurulamayan dal — devredilen yol `dogrulandi`
    ama SAHİBİ bu turda `uygulandi` mühürlenmedi (seçilmedi / durum.json önceki turdan kalma).
    Yolun kendi durumu tek başına "içerik bu turda indi" demez ⇒ `is-yok` DEĞİL."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(AXET_HOME / "scripts"))
        import guncelle  # noqa: PLC0415
        cls.g = guncelle

    KALEM = {"id": "2-01", "dosyalar": [], "devredilen": {"scripts/doctor.py": "3-01"}}
    DURUM = {"dosyalar": {"scripts/doctor.py": {"durum": "dogrulandi"}}}

    def test_Z58_birim_sahip_uygulanmadiysa_dogrulandi_yol_is_yok_DEGIL(self):
        self.assertEqual(self.g._atlandi_nedeni(self.KALEM, self.DURUM, set()), "kabul")

    def test_Z58_birim_KONTROL_sahip_uygulandi_ve_yol_dogrulandi_is_yok(self):
        self.assertEqual(self.g._atlandi_nedeni(self.KALEM, self.DURUM, {"3-01"}), "is-yok")

    def test_Z58_birim_islemsiz_kalem_devredilen_bos_is_yok(self):
        kalem = {"id": "2-09", "dosyalar": [], "devredilen": {}}
        self.assertEqual(self.g._atlandi_nedeni(kalem, {"dosyalar": {}}, set()), "is-yok")


class KapanisKabulVeHookTest(GuncelleTemel):
    """P2 ⓑ: `kapanis --kabul` altında git tarafının davranışı + hook reddi (rc=1).

    M-1: `--kabul` verilip git tarafı (add/commit) PATLARSA kapanış 1 döner; rapor aynı anda
    hem "KAPANMADI" hem "Kullanıcı onaylı açık FAIL ile kapandı" diyordu — "onaylı kapandı"
    satırı yalnız kod=3'te (onaylı açık FAIL, git tarafı TEMİZ) basılır.
    Ön-eksik burada `butunluk`un KOŞTURULMAMASIYLA üretilir ⇒ `--kabul` olmadan kapanış reddeder.
    """

    # AkisTest'ten MİRAS DEĞİL (miras onun tüm testlerini ikinci kez koşturur) — yalnız yardımcılar
    birlesik_isaretle = AkisTest.birlesik_isaretle
    _tum_yargilari_kapat = AkisTest._tum_yargilari_kapat

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def _hazirla(self, *, butunluk: bool, birlesik: str | None = None,
                 haric: str | None = None, karar: tuple[str, str] | None = None) -> None:
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        if birlesik:
            self.birlesik_isaretle(birlesik)
        self._tum_yargilari_kapat(haric=haric)
        if karar:
            r = self.f.calistir("isaretle", karar[0], "--karar", karar[1])
            self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        if butunluk:
            self.assertEqual(self.f.calistir("butunluk").returncode, 0)

    def _rapor(self) -> str:
        return (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")

    def _muhur(self) -> bool:
        return (self.f.durum_dizini() / "uygulanan.json").exists()

    def test_kabul_ile_ADD_hatasi_ortulmez(self):
        self._hazirla(butunluk=False, haric="skills/cakisan/SKILL.md",
                      karar=("skills/cakisan/SKILL.md", "yeniden-adlandir"))
        self.git(self.f.tuketici, "rm", "-q", "--cached", "--", "skills/cakisan/SKILL.md")
        gi = self.f.tuketici / ".gitignore"
        gi.write_text(gi.read_text(encoding="utf-8") + "/skills/cakisan/\n", encoding="utf-8")
        r = self.f.calistir("kapanis", "--kabul", "bilerek-kabul")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertFalse(self._muhur(), "git add patladığı hâlde mühür basıldı")
        rapor = self._rapor()
        self.assertIn("`git add` başarısız", rapor)
        self.assertIn("KAPANMADI", rapor)
        self.assertNotIn("Kullanıcı onaylı açık FAIL ile kapandı", rapor,
                         "git tarafı patladığı hâlde rapor 'onaylı kapandı' diyor (M-1)")

    def test_kabul_ile_COMMIT_hatasi_ortulmez(self):
        self._hazirla(butunluk=False, birlesik="core/00-temel.md", haric="core/00-temel.md")
        self.git(self.f.tuketici, "config", "commit.gpgsign", "true")
        self.git(self.f.tuketici, "config", "gpg.program", "boyle-bir-program-yok-xyz")
        r = self.f.calistir("kapanis", "--kabul", "bilerek-kabul")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertFalse(self._muhur(), "commit patladığı hâlde mühür basıldı")
        rapor = self._rapor()
        self.assertIn("commit'i atılamadı", rapor)
        self.assertNotIn("Kullanıcı onaylı açık FAIL ile kapandı", rapor,
                         "commit patladığı hâlde rapor 'onaylı kapandı' diyor (M-1)")

    def test_kabul_ile_git_tarafi_kosar_ve_3_doner(self):
        """Kontrol grubu: git tarafı temizken `--kabul` = rc 3 + mühür + "onaylı" satırı."""
        self._hazirla(butunluk=False, birlesik="core/00-temel.md", haric="core/00-temel.md")
        r = self.f.calistir("kapanis", "--kabul", "bilerek-kabul")
        self.assertEqual(r.returncode, 3, self.cikti(r))
        self.assertTrue(self._muhur())
        self.assertIn("Kullanıcı onaylı açık FAIL ile kapandı", self._rapor())
        head = self.git(self.f.tuketici, "show", "HEAD:core/00-temel.md").stdout
        self.assertIn("Çekirdek v3", head)
        self.assertIn("son yerel", head)

    def test_izlenen_yol_diskte_yoksa_silmesi_commite_girer(self):
        """Plan yolu index'te var, diskte yok (elle silindi) ⇒ silme stage'lenir ve commit'e girer."""
        self._hazirla(butunluk=True)
        izli = self.git(self.f.tuketici, "ls-files", "--", "scripts/sap_stamp.py").stdout.strip()
        self.assertEqual(izli, "scripts/sap_stamp.py", "kontrol: yol index'te olmalı")
        (self.f.tuketici / "scripts/sap_stamp.py").unlink()
        r = self.f.calistir("kapanis", "--kabul", "bilerek-kabul")
        self.assertIn(r.returncode, (0, 3), self.cikti(r))
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertNotIn("scripts/sap_stamp.py", agac,
                         "index'te olup diskte olmayan yolun silmesi commit'e girmedi")

    def test_hook_rc1_commiti_durdurursa_eksik_olur_ve_muhur_basilmaz(self):
        """`--no-verify` prepare-commit-msg'i ATLAMAZ; hook exit 1 ⇒ git commit rc=1 + stage'de
        fark var ⇒ "commit edilecek bir şey yok" sanılıp tolere EDİLMEZ."""
        self._hazirla(butunluk=True, birlesik="core/00-temel.md", haric="core/00-temel.md")
        hp = self.git(self.f.tuketici, "rev-parse", "--git-path", "hooks").stdout.strip()
        hd = Path(hp) if Path(hp).is_absolute() else self.f.tuketici / hp
        hd.mkdir(parents=True, exist_ok=True)
        (hd / "prepare-commit-msg").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        once = self.git(self.f.tuketici, "rev-parse", "HEAD").stdout.strip()
        r = self.f.calistir("kapanis")
        self.assertEqual(once, self.git(self.f.tuketici, "rev-parse", "HEAD").stdout.strip(),
                         "kontrol: hook commit'i engellemeliydi")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertFalse(self._muhur(), "commit atılmadığı hâlde mühür basıldı")
        self.assertIn("commit'i atılamadı", self._rapor())


class OlcumOlculemediTest(GuncelleTemel):
    """§6 `olc`: "0 koştu (kırmızı olsa bile) · **2 koşturulamadı**" · §7 adım 6: "2 → DUR".

    Koşulsuz `return 0`, "ölçülemeyen güncelleme yapılmaz" kuralını mekanik olarak devre dışı
    bırakıyordu: hiç test koşmadığında da akış "ölçüldü" sayılıp devam ediyordu.
    """

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def test_kontrol_grubu_test_gercekten_kosunca_0(self):
        r = self.f.calistir("olc", "--asama", "once")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        self.assertTrue(any(t["cikis"] is not None for t in veri["testler"]), veri["testler"])

    def test_haritada_hic_test_komutu_yoksa_cikis_2(self):
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        for s in harita["siniflar"]:
            s["test"] = []
        kirpik = self.tmp / "harita-testsiz.json"
        kirpik.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        r = self.f.calistir("--harita", str(kirpik), "olc", "--asama", "once")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("ölçülemedi", self.cikti(r).lower())

    # --- Z16/A: KABLOLAMA — ayıklama `olc` akışında GERÇEKTEN devrede mi? ------------------
    def _filtreli_harita(self) -> str:
        """Seçili bir sınıfa, filtresiz komutun `-k`'lı eşini EKLE (ikisi de aynı ölçümde)."""
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        eklendi = False
        for s in harita["siniflar"]:
            for kom in [x["komut"] for x in s.get("test", [])]:
                if kom == "python tests/run_tests.py":
                    s["test"].append({"komut": "python tests/run_tests.py -k ornek",
                                      "cwd": ".", "on_kosul": None})
                    eklendi = True
                    break
        self.assertTrue(eklendi, "fixture geçersiz: haritada filtresiz kök komutu yok")
        kirpik = self.tmp / "harita-filtreli.json"
        kirpik.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        return str(kirpik)

    def test_kapsanan_filtreli_komut_OLC_akisinda_kosulmaz(self):
        r = self.f.calistir("--harita", self._filtreli_harita(), "olc", "--asama", "once")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("[KAPSANDI]", self.cikti(r),
                      "ayıklama kablolanmamış: `olc` filtreli komutu yine koşuyor")
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        kimlikler = [x["kimlik"] for x in veri["testler"]]
        self.assertIn(".::python tests/run_tests.py", kimlikler)
        self.assertNotIn(".::python tests/run_tests.py -k ornek", kimlikler,
                         f"kapsanan komut yine ölçüme girdi: {kimlikler}")

    def test_KONTROL_filtresiz_es_yokken_filtreli_komut_KOSULUR(self):
        """Kontrol grubu: ayıklama ayrım yapıyor mu, yoksa her `-k`'yı mı atıyor?"""
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        for s in harita["siniflar"]:
            s["test"] = [{"komut": "python tests/run_tests.py -k ornek", "cwd": ".",
                          "on_kosul": None}] if s.get("test") else []
        kirpik = self.tmp / "harita-yalniz-filtreli.json"
        kirpik.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        r = self.f.calistir("--harita", str(kirpik), "olc", "--asama", "once")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("[KAPSANDI]", self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        self.assertEqual([x["kimlik"] for x in veri["testler"]],
                         [".::python tests/run_tests.py -k ornek"])

    def test_hicbir_test_betigi_kosturulamazsa_cikis_2(self):
        for y in ("tests/run_tests.py", "scripts/doctor.py"):
            (self.f.tuketici / y).unlink()
        r = self.f.calistir("olc", "--asama", "once")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        self.assertTrue(veri["testler"], "kayıt yine de yazılmalı (ölçülemedi ≠ hiç bakılmadı)")
        self.assertTrue(all(t["cikis"] is None for t in veri["testler"]),
                        [t for t in veri["testler"] if t["cikis"] is not None])


class HazirlaStatusRcTest(GuncelleTemel):
    """rc taraması 2026-09-18 (Z15): `hazirla` `git status` rc'sini okumuyordu ⇒ bozuk index'te
    "temiz" sanılıp anlık commit atlanıyor, geri dönüş etiketi kullanıcının izlenen
    değişikliğini İÇERMİYORDU (ölçüldü: etiketteki LICENSE = eski sürüm).
    KAPSAM — bakılmayan: onkontrol'ün sığ-klon rc dalı (sahte klon gerektirir; kod okumasıyla)."""

    def test_status_basarisizsa_DUR_ve_etiket_atilmaz(self):
        self.f.yerel_degistir("LICENSE", "MIT yerel\n")
        (self.f.tuketici / ".git" / "index").write_bytes(b"bozuk")
        r = self.f.calistir("hazirla")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("git status", self.cikti(r))
        etiketler = self.git(self.f.tuketici, "tag", "-l", "guncelle-oncesi-*").stdout.split()
        self.assertEqual(etiketler, [], "ölçülemeyen durumda geri dönüş noktası atıldı")


class BirlestirRcTest(unittest.TestCase):
    """`git merge-file` hata kodu (Windows'ta 255) "255 çakışma" sayılıyordu ⇒ yanlış teşhis
    ("ayrışma eşiği aşıldı"). Hata taklitle üretilir; kontrol grubu gerçek merge-file'dır."""

    def test_127_ustu_rc_hata_sayilir(self):
        import guncelle  # noqa: PLC0415
        from unittest import mock
        sahte = subprocess.CompletedProcess([], 255, stdout=b"", stderr=b"error: kirik")
        with mock.patch.object(guncelle.subprocess, "run", return_value=sahte):
            with self.assertRaises(guncelle.Dur) as bag:
                guncelle.birlestir(None, "a.md", b"t\n", b"l\n", b"y\n")
        self.assertIn("rc=255", str(bag.exception))

    def test_kontrol_grubu_gercek_cakisma_sayisi(self):
        import guncelle  # noqa: PLC0415
        icerik, cakisma = guncelle.birlestir(None, "a.md", b"x\n", b"yerel\n", b"yeni\n")
        self.assertEqual(cakisma, 1)
        self.assertIn(b"YEREL:a.md", icerik)


class DiskShaOlculemediTest(GuncelleTemel):
    """rc taraması 2026-09-18 (ZARARLI-1): `Klon.disk_sha` `git hash-object` rc≠0'ını yutup
    `None` ("dosya yok") döndürüyordu ⇒ kullanıcının İZLENMEYEN dosyası V7 (yargı) yerine V2
    (otomatik) sınıflanıyor, `_yedeksiz_mi` "ezilecek içerik yok" diyor ve `uygula --otomatik`
    dosyayı YEDEKSİZ eziyordu (ölçüldü: `ALINDI … (V2)`, `.yerel` yok).

    Arıza enjeksiyonu: yalnız o yola bağlı, `required` ve clean komutu başarısız bir filtre —
    `hash-object --path`'i rc≠0 yaptırmanın deterministik yolu (gerçek karşılığı: okunamayan
    dosya, eksik LFS/filtre, kilit).
    KAPSAM — bakılmayan: `stdin_sha` dalı (aynı düzeltme, ayrı test yok) · yazım sonrası geri
    okumanın hash'leyemediği dal (`_yazim_sonrasi_sha`).
    """

    YOL = "skills/cakisan/SKILL.md"
    KULLANICI = "---\nname: cakisan\n---\nKULLANICININ dosyasi\n"

    def _filtreyi_boz(self) -> None:
        t = self.f.tuketici
        (t / ".git" / "info").mkdir(exist_ok=True)
        (t / ".git" / "info" / "attributes").write_text(f"{self.YOL} filter=kirik\n", encoding="utf-8")
        self.git(t, "config", "filter.kirik.clean", "false")
        self.git(t, "config", "filter.kirik.smudge", "cat")
        self.git(t, "config", "filter.kirik.required", "true")
        r = self.git(t, "hash-object", "--path", self.YOL, "--", str(t / self.YOL), kontrol=False)
        self.assertNotEqual(r.returncode, 0, "enjeksiyon tutmadı — test hiçbir şey ölçmez")

    def test_kontrol_grubu_saglam_gitte_yerel_dosya_V7(self):
        self.f.yerel_degistir(self.YOL, self.KULLANICI)
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.vakalar().get(self.YOL), "V7")

    def test_hash_object_duserse_plan_DUR_ve_dosya_dokunulmaz(self):
        self.f.yerel_degistir(self.YOL, self.KULLANICI)
        self._filtreyi_boz()
        r = self.hazirla_ve_planla()
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("ÖLÇÜLEMEDİ", self.cikti(r))
        if (self.f.durum_dizini() / "plan.json").is_file():
            self.assertNotEqual(self.f.vakalar().get(self.YOL), "V2",
                                "okunamayan yerel dosya otomatik ezme vakasına düştü")
        self.assertEqual((self.f.tuketici / self.YOL).read_text(encoding="utf-8"), self.KULLANICI)


class ButunlukTest(GuncelleTemel):
    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def test_butunluk_install_dry_run_ve_doctor_kosar(self):
        r = self.f.calistir("butunluk")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        b = json.loads((self.f.durum_dizini() / "butunluk.json").read_text(encoding="utf-8"))
        adlar = [x["ad"] for x in b["adimlar"]]
        self.assertIn("install --dry-run", adlar)
        self.assertIn("doctor", adlar)

    def test_doctor_kirmiziysa_butunluk_1(self):
        self.f.yerel_degistir("scripts/doctor.py", "import sys\nprint('kirmizi')\nsys.exit(1)\n")
        r = self.f.calistir("butunluk")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        # EK-3: 1'i ÜRETEN adımı da ölç — başka bir adımın FAIL'i de 1 döndürürdü ve test
        # "beklediğim sebepten kırmızı" diyemezdi. ÖLÇÜLDÜ: `doctor` ve `doctor --skills`
        # AYNI betiği çağırdığı için ikisi birden kırmızıya döner; `install --dry-run` yeşil kalır.
        b = json.loads((self.f.durum_dizini() / "butunluk.json").read_text(encoding="utf-8"))
        kirmizi = [a["ad"] for a in b["adimlar"] if a.get("cikis") not in (0, None)]
        self.assertIn("doctor", kirmizi)
        self.assertTrue(all(a.startswith("doctor") for a in kirmizi), b["adimlar"])

    def _guvence(self) -> list[str]:
        b = json.loads((self.f.durum_dizini() / "butunluk.json").read_text(encoding="utf-8"))
        return b["asgari_guvence"]

    def test_asgari_guvence_yerelde_degismis_kanonigi_bildirir(self):
        """§8 adım 7: engellemez ama WARN satırı yazar.

        ⛔ VAKUM ASSERTION onarımı (gate mutasyonu M2): iki `guvence.append("WARN …")` `pass`e
        çevrildiğinde `ButunlukTest` 3/3 YEŞİL kalıyordu — üstelik mutasyon "hiçbirinde sapma
        yok" diye GÜVEN VEREN YANLIŞ satır üretiyordu. Eski assertion yalnız "asgari güvence"
        dizgesini arıyordu ve o dizge sapmasız satırda da geçiyor. Burada bir asgari güvence
        yolu BİLEREK saptırılıyor.
        """
        self.f.yerel_degistir("config/permissions.json", '{"deny": ["a", "b", "KULLANICI"]}\n')
        r = self.f.calistir("butunluk")
        c = self.cikti(r)
        self.assertIn("WARN asgari güvence", c)
        self.assertIn("config/permissions.json", c)
        self.assertIn("FARKLI", c)
        g = " | ".join(self._guvence())
        self.assertIn("config/permissions.json", g)
        self.assertNotIn("sapma yok", g, "sapma varken 'sapma yok' satırı YAZILAMAZ")

    def test_asgari_guvence_yerelde_yoksa_WARN(self):
        (self.f.tuketici / "config" / "permissions.json").unlink()
        r = self.f.calistir("butunluk")
        self.assertIn("YERELDE YOK", self.cikti(r))
        self.assertNotIn("sapma yok", " | ".join(self._guvence()))

    def test_kontrol_grubu_sapma_yokken_WARN_URETILMEZ(self):
        """`senaryolari_uygula` config/permissions.json'u v3 ile AYNI yapar (V4e) ⇒ sapma yok.
        Kontrol grubu olmadan yukarıdaki iki test 'her koşulda WARN yazan' bir koddan da
        geçerdi."""
        self.f.calistir("butunluk")
        g = " | ".join(self._guvence())
        self.assertNotIn("WARN", g)
        self.assertIn("sapma yok", g)


class SurumSozlesmesiTest(GuncelleTemel):
    """`surum` alanı YAZILIYOR ama hiç OKUNMUYORDU.

    Ölçülen sonuç: `uygulanan.json`'a `surum: 2` verilince motor onu sessizce v1 gibi okuyor,
    beklediği alanları bulamayınca `dosyalar` BOŞ dönüyor ⇒ dosya-başı taban sessizce
    merge-base'e düşüyor ⇒ §2a'nın ÖNLEMEK için var olduğu yanlış çakışma geri geliyor.
    """

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.f.calistir("hazirla").returncode, 0)

    def _durum_dosyasi(self, ad: str, veri) -> None:
        d = self.f.durum_dizini()
        d.mkdir(exist_ok=True)
        (d / ad).write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")

    def test_kontrol_grubu_surum_1_okunur_ve_taban_tasinir(self):
        self._durum_dosyasi("uygulanan.json", {"surum": 1,
                                               "dosyalar": {"scripts/doctor.py": "v2"},
                                               "kalemler": {}})
        self.f.yerel_degistir("scripts/doctor.py", V2_DEGISIM["scripts/doctor.py"])
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.vakalar().get("scripts/doctor.py"), "V1")

    def test_uygulanan_json_gelecek_surumu_plani_DURDURUR(self):
        self._durum_dosyasi("uygulanan.json", {"surum": 2,
                                               "dosyalar": {"scripts/doctor.py": "v2"},
                                               "kalemler": {}})
        r = self.f.calistir("plan")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("uygulanan.json", self.cikti(r))
        self.assertIn("surum", self.cikti(r).lower())

    def test_plan_json_gelecek_surumu_DURDURUR(self):
        self.assertEqual(self.f.calistir("plan").returncode, 0)
        p = self.f.plan()
        p["surum"] = 2
        self._durum_dosyasi("plan.json", p)
        r = self.f.calistir("sec", "--hepsi")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("plan.json", self.cikti(r))

    def test_durum_json_gelecek_surumu_DURDURUR(self):
        self.assertEqual(self.f.calistir("plan").returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        self._durum_dosyasi("durum.json", {"surum": 2, "dosyalar": {}, "ozel_adimlar": {}})
        r = self.f.calistir("uygula", "--otomatik")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("durum.json", self.cikti(r))


class KartVarligiTest(GuncelleTemel):
    """Plan bir kart ADI veriyor ama kartın `origin/main:guncelle/kartlar/` altında var olduğunu
    hiç doğrulamıyordu: ajan `kart <KOD>` deyince çıkış 2 alır ve §7 adım 8 orada tıkanır."""

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)

    def test_olmayan_kart_icin_WARN(self):
        # sahte public deposunda hiç kart yok
        uyarilar = " | ".join(self.f.plan()["uyarilar"])
        self.assertIn("kart bulunamadı", uyarilar)
        self.assertIn("V4c", uyarilar)

    def test_kontrol_grubu_kart_varsa_WARN_YOK(self):
        self.f._yaz(self.f.public, {"guncelle/kartlar/V4c.md": "# V4c\n"})
        self.git(self.f.public, "add", "-A")
        self.git(self.f.public, "commit", "-q", "-m", "V4c karti")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "origin")
        self.assertEqual(self.f.calistir("plan").returncode, 0)
        eksik = [u for u in self.f.plan()["uyarilar"] if "kart bulunamadı" in u]
        self.assertFalse([u for u in eksik if "V4c.md" in u], eksik)
        self.assertTrue(eksik, "diğer kartlar hâlâ eksik olmalı (test kendini kandırmasın)")


class OzelAdimIzinTest(GuncelleTemel):
    """`ozel-adim`, serbest metinden çıkardığı `python …` komutunu izin kontrolü olmadan
    koşuyordu. Kabuk enjeksiyonu YOK (`shell=` hiç kullanılmıyor) — sorun başkadır:
    `harita.json`'daki bir Türkçe cümleye `python scripts/install.py --sap-write` yazılması,
    `config/permissions.json`'ın `deny`'ını TEK bir izinli `guncelle.py` çağrısı içinden
    atlatırdı.
    """

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def _harita(self, ozel_adim: str) -> str:
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        for s in harita["siniflar"]:
            if s["sinif"] == "config-izin-kok":
                s["ozel_adim"] = ozel_adim
        yol = self.tmp / "harita-ozel.json"
        yol.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        return str(yol)

    def test_kontrol_grubu_izinli_komut_KOSAR(self):
        h = self._harita("python scripts/install.py --dry-run")
        r = self.f.calistir("--harita", h, "ozel-adim", "config-izin-kok")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(self.f.durum()["ozel_adimlar"]["config-izin-kok"]["durum"], "kostu")

    def test_deny_edilmis_bayrak_KOSTURULMAZ_manuel_adim_olur(self):
        h = self._harita("İzinleri tazele: python scripts/install.py --sap-write yapılmalı")
        # fixture install.py'si koşarsa işaret bıraksın — "koşmadı"yı KANITLA
        self.f.yerel_degistir("scripts/install.py",
                              "import pathlib\n"
                              "pathlib.Path('KOSTU.txt').write_text('kostu')\n")
        r = self.f.calistir("--harita", h, "ozel-adim", "config-izin-kok")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("MANUEL ADIM", self.cikti(r))
        self.assertIn("--sap-write", self.cikti(r))
        self.assertFalse((self.f.tuketici / "KOSTU.txt").exists(),
                         "betik KOŞTU — izin kontrolü atlandı")
        self.assertEqual(self.f.durum()["ozel_adimlar"]["config-izin-kok"]["durum"], "manuel")

    def test_izinli_betik_izinsiz_BAYRAKLA_KOSTURULMAZ_bayrak_kolu_izole(self):
        """⛔ LOW-2: `--sap-write`i allowlist'e EKLEMEK hiçbir testi kırmıyordu.

        Sebep: var olan testte metin `… --sap-write yapılmalı` idi ve `_PY_KOMUT`in
        `[^,;\\n]*` kuyruğu cümlenin son kelimesini de komuta katıyordu ⇒ ret, bayrak
        allowlist'inden DEĞİL, `yapılmalı` argümanından geliyordu (bayrak kolu ÖLÇÜLMEMİŞTİ).
        Burada komut VİRGÜLDE biter ⇒ çıkarılan dizge tam olarak üç parçadır ve reddin TEK
        sebebi bayrak allowlist'idir. Kontrol grubu: `test_kontrol_grubu_izinli_komut_KOSAR`
        (aynı betik, `--dry-run` ile KOŞAR).
        """
        h = self._harita("İzinleri tazele: python scripts/install.py --sap-write, sonra devam et")
        self.f.yerel_degistir("scripts/install.py",
                              "import pathlib\n"
                              "pathlib.Path('KOSTU.txt').write_text('kostu')\n")
        r = self.f.calistir("--harita", h, "ozel-adim", "config-izin-kok")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        # çıkarılan komutun SINIRI ölçülür: cümlenin kalanı komuta KARIŞMAMIŞ
        self.assertIn("`python scripts/install.py --sap-write` →", self.cikti(r))
        # ve ret sebebi BAYRAK kolu
        self.assertIn("izinli olmayan bayrak/argüman: --sap-write", self.cikti(r))
        self.assertFalse((self.f.tuketici / "KOSTU.txt").exists(),
                         "betik KOŞTU — bayrak allowlist'i atlandı")
        self.assertEqual(self.f.durum()["ozel_adimlar"]["config-izin-kok"]["durum"], "manuel")

    def test_allowlist_disi_betik_KOSTURULMAZ(self):
        h = self._harita("python scripts/kotu.py çalıştır")
        (self.f.tuketici / "scripts" / "kotu.py").write_text(
            "import pathlib\npathlib.Path('KOSTU.txt').write_text('kostu')\n", encoding="utf-8")
        r = self.f.calistir("--harita", h, "ozel-adim", "config-izin-kok")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("MANUEL ADIM", self.cikti(r))
        self.assertFalse((self.f.tuketici / "KOSTU.txt").exists())


class OlcKapsamBeyaniTest(GuncelleTemel):
    """⭐ MEDIUM-2 — `OZEL_ADIM_IZINLI` allowlist'i YALNIZ `ozel-adim` yüzeyini kapsar.

    Ölçülen boşluk: `komut_olc`, `harita.json`daki `test[].komut`u `_ozel_adim_izinli_mi`den
    GEÇİRMEDEN koşturur. Seçilen çözüm allowlist'i `olc`e yaymak DEĞİL, kapsamı AÇIKÇA
    daraltmaktır (asimetri bilinçli). Gerekçe ölçüldü: haritadaki 44 test komutunun çoğu
    `python -m unittest discover -s …` / `python skills-sap/…/tests/run_tests.py` biçiminde ve
    allowlist'e sığmıyor ⇒ ① seçeneği `olc`u her sınıfta rc=2 (DUR) yapar, yani ölçüm
    mekanizmasını kapatırdı. Ayrıca `harita_yukle` motorun KENDİ kopyasını okur (K4), `olc`
    komutları serbest METİNDEN çıkarılmaz, ve `olc` zaten klonda duran test betiklerini koşar
    (içerikleri motorca denetlenemez ⇒ dizge allowlist'i orada sahte güvence olurdu).

    Bu sınıf iki şeyi birden çivi ler: ① kaynaktaki KAPSAM BEYANI metni duruyor mu
    ② beyan edilen sınır GERÇEK sınır mı (davranışsal karakterizasyon).
    """

    @classmethod
    def setUpClass(cls):
        for p in (AXET_HOME / "scripts",):
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
        import guncelle  # noqa: PLC0415
        cls.g = guncelle

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def _harita_test(self, komut: str) -> str:
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        for s in harita["siniflar"]:
            if s.get("test"):
                s["test"] = [{"komut": komut, "cwd": "."}]
        yol = self.tmp / "harita-olc.json"
        yol.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        return str(yol)

    def test_kaynakta_KAPSAM_BEYANI_yazili(self):
        """Beyan sessizce silinemesin: metin mekanik olarak çivilenir."""
        metin = GUNCELLE_PY.read_text(encoding="utf-8")
        self.assertIn("KAPSAM BEYANI — bu allowlist YALNIZ `ozel-adim` yüzeyini kapsar", metin)
        self.assertIn("BAKILMAYAN", metin)

    def test_olc_ALLOWLISTTEN_GECMEZ_kapsam_beyani(self):
        # ① kontrol grubu: aynı dizge `ozel-adim` yüzeyinde REDDEDİLİR
        ok, sebep = self.g._ozel_adim_izinli_mi("python scripts/olc_isareti.py")
        self.assertFalse(ok, f"kontrol grubu çöktü — dizge allowlist'ten geçti: {sebep}")
        # ② aynı dizge `olc` yüzeyinde KOŞAR (beyan edilen asimetri)
        h = self._harita_test("python scripts/olc_isareti.py")
        (self.f.tuketici / "scripts" / "olc_isareti.py").write_text(
            "import pathlib\npathlib.Path('OLC_KOSTU.txt').write_text('kostu')\n",
            encoding="utf-8")
        r = self.f.calistir("--harita", h, "olc", "--asama", "once")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertTrue((self.f.tuketici / "OLC_KOSTU.txt").exists(),
                        "`olc` haritadaki komutu koşmadı — KAPSAM BEYANI artık YANLIŞ, "
                        "beyanı güncelle ya da davranışı geri al")


class MotorBagimsizligiTest(GuncelleTemel):
    """K4 lider notu: motor klondaki (eski olabilecek) `scripts/*.py`'yi IMPORT ETMEZ."""

    def test_klondaki_bozuk_modul_plani_etkilemez(self):
        self.senaryolari_uygula()
        for ad in ("behavior_manifest.py", "doctor.py", "install.py", "siniflandir.py"):
            hedef = self.f.tuketici / ("guncelle/" + ad if ad == "siniflandir.py"
                                       else "scripts/" + ad)
            hedef.parent.mkdir(parents=True, exist_ok=True)
            hedef.write_text("raise RuntimeError('eski bozuk motor')\n", encoding="utf-8")
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.vakalar().get("core/00-temel.md"), "V4t")

    def test_kaynak_metninde_klon_scriptleri_import_edilmiyor(self):
        metin = GUNCELLE_PY.read_text(encoding="utf-8")
        for yasak in ("import doctor", "import install", "import behavior_manifest",
                      "import new_project", "import session_brief"):
            self.assertNotIn(yasak, metin, f"K4 ihlali: {yasak}")


class SiniflandirmaTekKaynakTest(unittest.TestCase):
    """`guncelle.sinif_bul` ile `guncelle/siniflandir.siniflandir` aynı haritayı aynı kuralla
    okur ama İKİ AYRI GÖVDEDİR (biri KAYDI, diğeri SINIF ADINI döndürür ⇒ imzaları farklı,
    tek fonksiyona indirilemez). Docstring uzun süre "siniflandir.py import edilir" diyordu;
    edilmiyordu. Doğru çare adı düzeltmek DEĞİL, sapmayı MEKANİK olarak ölçmektir.
    """

    @classmethod
    def setUpClass(cls):
        for p in (AXET_HOME / "scripts", AXET_HOME / "guncelle"):
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
        import guncelle  # noqa: PLC0415
        import siniflandir  # noqa: PLC0415
        cls.g, cls.s = guncelle, siniflandir
        cls.harita = json.loads(HARITA.read_text(encoding="utf-8"))

    def test_iki_gerceklestirim_TUM_izlenen_yollarda_ayni_sinifi_verir(self):
        yollar = subprocess.run(["git", "ls-files"], cwd=str(AXET_HOME), capture_output=True,
                                text=True, encoding="utf-8", errors="replace").stdout.split()
        self.assertGreater(len(yollar), 100, "evren boş ya da git yok — test anlamsız")
        for y in yollar:
            kayit = self.g.sinif_bul(y, self.harita)
            self.assertEqual(kayit["sinif"] if kayit else None,
                             self.s.siniflandir(y, self.harita), y)


class KartTest(GuncelleTemel):
    def test_kart_yoksa_cikis_2(self):
        r = self.f.calistir("kart", "V4c")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        self.assertIn("kart yok", self.cikti(r))
        self.assertIn("guncelle/kartlar/V4c.md", self.cikti(r))

    def test_kart_yeni_surumden_okunur(self):
        self.f._yaz(self.f.public, {"guncelle/kartlar/V4c.md": "# V4c\nkart gövdesi\n"})
        self.git(self.f.public, "add", "-A")
        self.git(self.f.public, "commit", "-q", "-m", "kart")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "origin")
        # yerel kopya BOZUK olsun — kart yine de yeni sürümden gelmeli
        self.f.yerel_degistir("guncelle/kartlar/V4c.md", "BOZUK YEREL\n")
        r = self.f.calistir("kart", "V4c")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertIn("kart gövdesi", self.cikti(r))
        self.assertNotIn("BOZUK", self.cikti(r))


class M6YenidenAdlandirmaTest(GuncelleTemel):
    """M-6'nın yeniden adlandırmalı V7 kolu (bug gate 2026-09-19, BLOCKER #1-#2 — ölçüldü).

    Template `docs/tasinacak.md`'yi `docs/tasindi.md`'ye taşır; kullanıcının yeni yolda
    İZLENMEYEN kendi dosyası vardır ⇒ V7. Eski süzgeç yalnız `karar == yerel` kaydının `hedef_yol`unu
    koruyordu ve o alan ESKİ yolu tutuyordu ⇒ kullanıcının dosyası kapanış commit'ine giriyordu.
    `ertelendi` kararında süzgeç hiç devreye girmiyordu. Taban AkisTest DEĞİL: onun testleri
    V1R taşımasını varsayar, bu fikstürde aynı yol V7'dir.
    """
    OZEL = "KULLANICININ OZEL NOTU\n"

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.f.yerel_degistir("docs/tasindi.md", self.OZEL)
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def _karar_ver_ve_kapat(self, *karar: str):
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.f.calistir("uygula", "--otomatik")
        AkisTest._tum_yargilari_kapat(self)
        r = self.f.calistir("isaretle", "docs/tasinacak.md", *karar)
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.f.calistir("olc", "--asama", "sonra")
        self.f.calistir("butunluk")
        # kontrol grubu: vaka gerçekten V7 ve kullanıcının dosyası kapanıştan ÖNCE izlenmiyor
        plan = json.loads((self.f.durum_dizini() / "plan.json").read_text(encoding="utf-8"))
        kayit = [d for k in plan["kalemler"] for d in k["dosyalar"] if d["yol"] == "docs/tasinacak.md"]
        self.assertEqual([(d["vaka"], d.get("yeni_yol")) for d in kayit], [("V7", "docs/tasindi.md")])
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--", "docs/tasindi.md").stdout.strip(), "")
        return self.f.calistir("kapanis")

    def _kullanici_dosyasi_commite_girmedi(self, r) -> None:
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertNotIn("docs/tasindi.md", agac,
                         f"kullanıcının izlenmeyen dosyası kapanış commit'ine girdi:\n{self.cikti(r)}")
        self.assertEqual((self.f.tuketici / "docs/tasindi.md").read_text(encoding="utf-8"), self.OZEL)

    def test_V7_yeniden_adlandirmali_yerel_yeni_yolu_korur(self):
        r = self._karar_ver_ve_kapat("--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self._kullanici_dosyasi_commite_girmedi(r)
        # kontrol grubu: süzgeç aşırı değil — aynı kapanışta V6 silmesi commit'e girdi
        agac = self.git(self.f.tuketici, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
        self.assertNotIn("docs/silinecek2.md", agac)

    def test_V7_yeniden_adlandirmali_ertelendi_yeni_yolu_korur(self):
        r = self._karar_ver_ve_kapat("--karar", "ertelendi", "--gerekce", "sonra bakarim")
        self._kullanici_dosyasi_commite_girmedi(r)

    def test_V7_karar_verilmeden_kabul_ile_kapanis_yeni_yolu_korur(self):
        """Bug gate 2026-09-19 #2'nin üçüncü kolu: yargı verilmemiş (`bekliyor`) V7 + `kapanis --kabul`."""
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.f.calistir("uygula", "--otomatik")
        AkisTest._tum_yargilari_kapat(self)
        self.ozel_adimlari_kostur()
        self.f.calistir("olc", "--asama", "sonra")
        self.f.calistir("butunluk")
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--", "docs/tasindi.md").stdout.strip(), "")
        r = self.f.calistir("kapanis", "--kabul", "kabul ediyorum")
        self.assertEqual(r.returncode, 3, self.cikti(r))   # kullanıcı onaylı açık FAIL ile kapandı
        self._kullanici_dosyasi_commite_girmedi(r)


class M6EskiYolSilinmisTest(M6YenidenAdlandirmaTest):
    """Bug gate 2026-09-19 dördüncü tur (ölçüldü): aynı üç karar, ama kullanıcı template'in ESKİ yolunu
    önceden kendisi silip commit'lemiş. "Eski yol duruyor mu" işareti burada "taşındı" diyordu ⇒
    kullanıcının yeni yoldaki izlenmeyen dosyası üç kararda da commit'e giriyordu. Testler üst sınıftan."""

    def setUp(self) -> None:
        GuncelleTemel.setUp(self)
        self.senaryolari_uygula()
        self.git(self.f.tuketici, "rm", "-q", "docs/tasinacak.md")
        self.git(self.f.tuketici, "commit", "-qm", "kullanici eski yolu sildi")
        self.f.yerel_degistir("docs/tasindi.md", self.OZEL)
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)


def _uret_elle(hedef: str) -> int:
    """`python tests/test_guncelle.py --uret <dizin>` — fixture'ı elle inceleme için üretir."""
    import tempfile

    class _Sahte(GeciciTest):
        def runTest(self):  # pragma: no cover
            pass

    t = _Sahte()
    t.setUp()
    try:
        kok = Path(hedef).resolve()
        kok.mkdir(parents=True, exist_ok=True)
        t.tmp = kok
        f = SahteYayin(t, kok).uret()
        print(f"public : {f.public}\ntüketici: {f.tuketici}")
        print(f"dene   : python {GUNCELLE_PY} --klon {f.tuketici} plan")
        return 0
    finally:
        tempfile  # noqa: B018


if __name__ == "__main__":
    if "--uret" in sys.argv:
        raise SystemExit(_uret_elle(sys.argv[sys.argv.index("--uret") + 1]))
    unittest.main()


class V4YayinKarisimi:
    """Sahte `fetch`: plan kurulduktan SONRA public'in v4 basmasi.

    Iki karar da ayni suruklenmeyi kurar (madde 7 plana-sabitleme, madde 4 K2 muhur)
    => kurulum tek yerde durur, kopyalanmaz.
    """

    def _v4_yayinla(self) -> None:
        """Sahte `fetch`: public v4 basar, tüketici onu görür (plan ZATEN kurulmuştu)."""
        yayinlar = json.loads(json.dumps(YAYINLAR))
        yayinlar["yayinlar"].append({
            "etiket": "v4", "tarih": "2026-03-01", "min_axet": "1.0.0",
            "kalemler": [{"id": "4-01", "baslik": "çekirdek v4", "tur": "kural", "kritik": False,
                          "neden": "—", "dosyalar": ["core/00-temel.md"], "gerektirir": [],
                          "test": []}],
        })
        self.f._yaz(self.f.public, {
            "core/00-temel.md": "# Çekirdek v4\nsatır1\nsatır2 net\n",
            "guncelle/yayinlar.json": json.dumps(yayinlar, ensure_ascii=False, indent=1) + "\n",
        })
        self.git(self.f.public, "add", "-A")
        self.git(self.f.public, "commit", "-q", "-m", "v4")
        self.git(self.f.public, "tag", "v4")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "origin")



class IsaretlemePlanaSabitTest(V4YayinKarisimi, GuncelleTemel):
    """Madde 7 (karar 2026-09-20) — `isaretle` PLANIN hedefini uygular, canlı ref'i değil.

    Kusur: plan `yeni_etiket`i çiviliyordu (`plan["yeni_etiket"] = b.yeni_ref`) ama
    `komut_isaretle` `b.yeni_ref`i okuyordu; `Baglam` her çağrıda onu YENİDEN hesaplar.
    Plan ile işaretleme arasında bir `fetch` olursa İÇERİK yeni sürümden yazılır, MÜHÜR
    eski sürümü der. Geriye sürüklenme için DUR vardı; İLERİ sürüklenme korumasızdı.

    KONTROL GRUBU: ① sürüklenme YOKken davranış değişmemeli ② sürüklenmenin GERÇEKTEN
    oluştuğu ölçülmeli (yoksa test sürüklenmeyi hiç kurmamış olabilir ve boşuna yeşil kalır).
    """

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)

    def test_1_fetch_plandan_SONRA_gelirse_plan_surumu_uygulanir(self):
        self.assertEqual(self.f.plan()["yeni_etiket"], "v3", "ön koşul: plan v3 ile kuruldu")
        self._v4_yayinla()
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        govde = (self.f.tuketici / "core/00-temel.md").read_text(encoding="utf-8")
        self.assertIn("# Çekirdek v3", govde, "PLANIN hedefi uygulanmalı")
        self.assertNotIn("# Çekirdek v4", govde, "canlı ref SESSİZCE uygulanmamalı")

    def test_2_suruklenme_kullaniciya_SOYLENIR(self):
        self._v4_yayinla()
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "yeni")
        self.assertIn("PLANA sabitlendi", r.stderr, self.cikti(r))
        self.assertIn("v3", r.stderr)

    def test_3_KONTROL_suruklenme_GERCEKTEN_olustu(self):
        """Sürüklenme kurulmadıysa test 1 boşuna yeşil kalır: v4'ün sonra GÖRÜNDÜĞÜNÜ ölç."""
        onceki = self.git(self.f.tuketici, "tag", "-l").stdout
        self._v4_yayinla()
        sonraki = self.git(self.f.tuketici, "tag", "-l").stdout
        self.assertNotIn("v4", onceki, "plan kurulurken v4 GÖRÜNMEMELİYDİ")
        self.assertIn("v4", sonraki, "sahte fetch v4'ü getirmeliydi")

    def test_4_KONTROL_suruklenme_YOKken_davranis_ayni(self):
        """Yanlış pozitif yok: fetch olmadan not basılmaz, içerik yine v3."""
        r = self.f.calistir("isaretle", "core/00-temel.md", "--karar", "yeni")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("PLANA sabitlendi", r.stderr)
        self.assertIn("# Çekirdek v3", (self.f.tuketici / "core/00-temel.md").read_text(encoding="utf-8"))


class KapanisYabanciStageTest(AkisTest):
    """Madde 6 (karar B — "DUR + uyar", 2026-09-20) — kapanış commit'i pathspec ALMAZ.

    `git commit --no-verify -q -m <mesaj>` index'te NE VARSA commit'ler. Kullanıcının
    kapanıştan ÖNCE stage'lediği iş, ARACIN mesajıyla ve pre-commit KOŞMADAN commit'e
    girerdi (PRE-EXISTING). Seçenek A (commit'e pathspec vermek) reddedildi: aracın kendi
    listesi eksik kalırsa kendi değişikliğini sessizce commit'lemezdi = YENİ sessiz kayıp.

    KONTROL GRUBU: yabancı stage YOKken kapanış eskisi gibi commit atmalı — yoksa bu test
    "kapanış artık hiç commit atmıyor"u da yeşil sayardı.
    """

    def _kapanisa_hazirla(self) -> None:
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)

    def _head(self) -> str:
        return self.git(self.f.tuketici, "rev-parse", "HEAD").stdout.strip()

    def test_1_KONTROL_yabanci_stage_YOKken_kapanis_commit_atar(self):
        self._kapanisa_hazirla()
        once = self._head()
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotEqual(self._head(), once, "kapanış commit'i atılmalıydı")

    def test_2_yabanci_stage_varsa_commit_ATILMAZ(self):
        self._kapanisa_hazirla()
        benim = self.f.tuketici / "benim-isim.txt"
        benim.write_text("kullanıcının kendi işi\n", encoding="utf-8")
        self.git(self.f.tuketici, "add", "--", "benim-isim.txt")
        once = self._head()
        r = self.f.calistir("kapanis")
        self.assertEqual(r.returncode, 1, self.cikti(r))
        self.assertEqual(self._head(), once, "HEAD ilerlemiş = yabancı iş commit'lendi")

    def test_3_mesaj_yolu_ve_cozumu_soyler(self):
        self._kapanisa_hazirla()
        (self.f.tuketici / "benim-isim.txt").write_text("x\n", encoding="utf-8")
        self.git(self.f.tuketici, "add", "--", "benim-isim.txt")
        r = self.f.calistir("kapanis")
        cikti = r.stdout + r.stderr
        self.assertIn("ATILMADI", cikti)
        self.assertIn("benim-isim.txt", cikti, "hangi yol yüzünden durdu SÖYLENMELİ")
        self.assertIn("git restore --staged", cikti, "çözüm adımı SÖYLENMELİ")

    def test_4_kullanicinin_isi_index_te_DURUR(self):
        """Araç kullanıcının stage'ine DOKUNMAZ: reddeder, ama işini index'ten atmaz."""
        self._kapanisa_hazirla()
        (self.f.tuketici / "benim-isim.txt").write_text("x\n", encoding="utf-8")
        self.git(self.f.tuketici, "add", "--", "benim-isim.txt")
        self.f.calistir("kapanis")
        stage = self.git(self.f.tuketici, "diff", "--cached", "--name-only").stdout
        self.assertIn("benim-isim.txt", stage, "kullanıcının stage'i korunmalı")


class ButunlukMuhruTest(V4YayinKarisimi, AkisTest):
    """Madde 4 / K2 (karar: "mühürle, fail-closed", 2026-09-20).

    `durum_dizini` döngüler arası TEMİZLENMİYOR ve bu bilerçedir (`uygulanan.json`
    döngüler-üstü, `:458`). Sonuç: ÖNCEKİ turdan kalan `butunluk.json` kapanışta
    "bütünlük turu koştu" sayılıyordu = SAHTE YEŞİL — üstelik NORMAL akışla tetikleniyordu
    (`%guncelle`'yi ikinci kez koşmak). Çare SİLMEK değil MÜHÜRLEMEK: döngü-kapsamlı dosya
    kendi plan kimliğini taşır; uymayan "ölçülmedi"dir (ölçülmedi ≠ temiz).
    """

    BAYAT = "BU TUR İÇİN ÖLÇÜLMEDİ"

    def _tur1_butunluge_kadar(self) -> None:
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat()
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)

    def _kapanis_ciktisi(self):
        r = self.f.calistir("kapanis")
        return r, r.stdout + r.stderr

    def test_1_KONTROL_ayni_turda_bayat_uyarisi_YOK(self):
        """Yanlış pozitif kontrolü: damga uyuyorsa kapanış eskisi gibi geçer."""
        self._tur1_butunluge_kadar()
        r, cikti = self._kapanis_ciktisi()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn(self.BAYAT, cikti)

    def test_2_onceki_turdan_kalan_butunluk_SAHTE_YESIL_vermez(self):
        self._tur1_butunluge_kadar()
        self.assertEqual(self.f.calistir("kapanis").returncode, 0, "ön koşul: tur 1 temiz kapanır")
        self._v4_yayinla()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0, "tur 2 planı kurulmalı")
        self.assertEqual(self.f.plan()["yeni_etiket"], "v4", "ön koşul: tur 2 hedefi v4")
        # tur 2'de `butunluk` KOŞULMADI — eski butunluk.json hâlâ diskte
        r, cikti = self._kapanis_ciktisi()
        self.assertNotEqual(r.returncode, 0, self.cikti(r))
        self.assertIn(self.BAYAT, cikti, "bayat bütünlük 'koştu' sayılmamalı")
        self.assertIn("v3", cikti, "hangi turun damgası olduğu söylenmeli")

    def test_3_tur2de_butunluk_kosunca_bayat_uyarisi_KALKAR(self):
        """Mühür bir duvar değil kapı: doğru turda koşulunca geçer."""
        self._tur1_butunluge_kadar()
        self.assertEqual(self.f.calistir("kapanis").returncode, 0)
        self._v4_yayinla()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.f.calistir("butunluk")
        _r, cikti = self._kapanis_ciktisi()
        self.assertNotIn(self.BAYAT, cikti, "bu turda koşan bütünlük bayat SAYILMAMALI")

    def test_4_damga_dosyaya_gercekten_yaziliyor(self):
        """Kablolama: kapanışın okuduğu alan gerçekten ÜRETİLİYOR mu (kod ≠ kablolama)."""
        self._tur1_butunluge_kadar()
        b = json.loads((self.f.durum_dizini() / "butunluk.json").read_text(encoding="utf-8"))
        self.assertEqual(b.get("plan", {}).get("yeni_etiket"), "v3")
        d = json.loads((self.f.durum_dizini() / "durum.json").read_text(encoding="utf-8"))
        self.assertEqual(d.get("plan", {}).get("yeni_etiket"), "v3")


class CiTabaniTest(GuncelleTemel):
    """Z16 — `once` turu, YARGI VAKASI YOKKEN yayının CI hükmüyle ikame edilir (2026-09-20).

    ⛔ ÖLÇÜLEN SINIF (hız değil, DOĞRULUK): `once` ve `sonra` aynı testleri koşmuyor.
    `komut_olc` testleri klon kökünde koşar ve `tests/**` güncellemenin parçası olabilir ⇒
    `once` ESKİ test kodunu, `sonra` YENİ test kodunu ölçer; `yeni_kirmizilar` ikisini komut
    kimliği bazında karşılaştırır. Testlerin kendisi değişirken "fark = regresyon" çıkarımı
    kurulamaz. CI ise yeni testleri yeni ürüne karşı temiz ortamda ölçmüştür.

    Kontrol grubu fixture'a gömülü: `senaryolari_uygula()` ÇAĞRILMAZSA yargı vakası yoktur
    (ikame beklenir), ÇAĞRILIRSA vardır (ölçüm beklenir).

    KAPSAM — bakılmayan: gerçek `gh` çağrısı (yayın tarafı ayrı ölçülür) · `sonra` turunun
    süresi · CI kaydının doğruluğu (yayıncı kendi hükmünü beyan eder, bu bir güven sınırıdır).
    """

    ETIKET = "v3"
    YESIL_TAKIMLAR = [{"ad": "Testler (kok · Python 3.12)", "sonuc": "success"},
                      {"ad": "Testler (foundation · Python 3.12)", "sonuc": "success"}]

    def _ci_yayinla(self, kayit) -> None:
        """Sahte public'e `guncelle/ci-durum.json` koyar; v3 etiketini o commit'e taşır."""
        h = self.f.public / "guncelle" / "ci-durum.json"
        h.parent.mkdir(parents=True, exist_ok=True)
        h.write_text(json.dumps({"surum": 1, "yayinlar": kayit}, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8", newline="\n")
        self.git(self.f.public, "add", "-A")
        self.git(self.f.public, "commit", "-q", "-m", "ci-durum")
        self.git(self.f.public, "tag", "-f", "v3")
        self.git(self.f.tuketici, "fetch", "-q", "--tags", "--force", "origin")

    def _yesil(self) -> dict:
        return {self.ETIKET: {"kaynak_commit": "abc1234", "hepsi_yesil": True,
                              "isletim_sistemi": "windows-latest", "python": ["3.12"],
                              "takimlar": list(self.YESIL_TAKIMLAR)}}

    def _olc_once(self) -> tuple[subprocess.CompletedProcess, dict]:
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        r = self.f.calistir("olc", "--asama", "once")
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        return r, veri

    # --- ① ikame OLMALI --------------------------------------------------------------------
    def test_1_yesil_ci_ve_yargi_yokken_IKAME_EDILIR(self):
        self._ci_yayinla(self._yesil())
        r, veri = self._olc_once()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(veri.get("kaynak"), "ci", veri)
        self.assertEqual(veri.get("testler"), [], "ikamede hiçbir test KOŞMAMALI")
        self.assertEqual(veri.get("etiket"), self.ETIKET)
        self.assertIn("İKAME", self.cikti(r))
        self.assertIn("KAPSAM", self.cikti(r), "ikame de kapsam beyanı basmalı")

    # --- ② KONTROL: ikame OLMAMALI (dördü de fail-safe dalı) --------------------------------
    def test_2_KONTROL_ci_durumu_YOKKEN_normal_olcer(self):
        r, veri = self._olc_once()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("kaynak", veri, "ci-durum.json yokken ikame OLMAMALI")
        self.assertTrue(any(t["cikis"] is not None for t in veri["testler"]), veri["testler"])

    def test_3_KONTROL_hepsi_yesil_False_ise_olcer(self):
        kayit = self._yesil()
        kayit[self.ETIKET]["hepsi_yesil"] = False
        self._ci_yayinla(kayit)
        _r, veri = self._olc_once()
        self.assertNotIn("kaynak", veri, "hepsi_yesil False iken ikame OLMAMALI")

    def test_4_KONTROL_takimlardan_biri_kirmiziysa_olcer(self):
        kayit = self._yesil()
        kayit[self.ETIKET]["takimlar"][0]["sonuc"] = "failure"
        self._ci_yayinla(kayit)
        _r, veri = self._olc_once()
        self.assertNotIn("kaynak", veri,
                         "hepsi_yesil True olsa BİLE tek kırmızı takım ikameyi engellemeli")

    def test_5_KONTROL_baska_etiketin_kaydi_ISE_YARAMAZ(self):
        self._ci_yayinla({"v99": self._yesil()[self.ETIKET]})
        _r, veri = self._olc_once()
        self.assertNotIn("kaynak", veri, "etiket tutmuyorsa ikame OLMAMALI")

    def test_6_KONTROL_yargi_vakasi_VARSA_yesil_CI_ye_ragmen_olcer(self):
        self._ci_yayinla(self._yesil())
        self.senaryolari_uygula()          # yerel değişiklikler ⇒ yargı vakaları
        _r, veri = self._olc_once()
        self.assertNotIn("kaynak", veri,
                         "yerel değişiklik varsa birleşmiş ağaç hiç test edilmemiştir ⇒ ÖLÇ")


class CiSonrasiTest(GuncelleTemel):
    """Z26 — `sonra` turu da CI ile ikame edilir: yargı vakası yok + CI yeşil + DİSK AĞACI =
    yayın ağacı (2026-09-21). Kullanıcı hedefi: yerel değişikliği olmayan güncelleme dakikalar sürsün.

    ⛔ Şart 2 plan beyanı DEĞİL, disk ölçümüdür: kontrol grupları diske tek dosya ekleyerek /
    uygulamayı atlayarak "plan temiz ama ağaç farklı" vakasını kurar ⇒ ölçüm beklenir.

    KAPSAM — bakılmayan: gerçek CI kaydının doğruluğu (güven sınırı) · satır sonu farkı
    (⚠ `git add` normalize eder ⇒ CRLF/LF farkı GÖRÜNMEZ, "aynı" sayılır — ölçüldü, bug gate
    2026-09-21; davranışı değiştiren bir satır sonu vakası bilinmiyor) · gitignore'lu dosyalar
    (karşılaştırma dışı) · yerel ortam sapması (bütünlük turunun işi).
    """

    ETIKET = CiTabaniTest.ETIKET
    YESIL_TAKIMLAR = CiTabaniTest.YESIL_TAKIMLAR
    _yesil = CiTabaniTest._yesil

    def _ci_yayinla(self, kayit) -> None:
        """Ortak fixture'ın kasıtlı 'beyansız dosya' vakasını kaldırıp yayınlar: o dosya hiçbir
        kaleme bağlı olmadığı için tüketiciye UYGULANMAZ ⇒ ağaç yayından farklı kalır ve ölçüme
        düşülür (doğru davranış, ölçüldü). Burada ölçülen değişken o değil."""
        (self.f.public / "docs" / "beyansiz.md").unlink()
        CiTabaniTest._ci_yayinla(self, kayit)

    def _akis(self, uygula: bool = True, bozucu=None) -> tuple[subprocess.CompletedProcess, dict]:
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        if uygula:
            r = self.f.calistir("uygula", "--otomatik")
            self.assertEqual(r.returncode, 0, self.cikti(r))
        if bozucu:
            bozucu()
        r = self.f.calistir("olc", "--asama", "sonra")
        veri = json.loads((self.f.durum_dizini() / "olcum-sonra.json").read_text(encoding="utf-8"))
        return r, veri

    def test_1_yesil_ci_yargi_yok_agac_ayni_IKAME_EDILIR(self):
        self._ci_yayinla(self._yesil())
        r, veri = self._akis()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertEqual(veri.get("kaynak"), "ci", self.cikti(r))
        self.assertEqual(veri.get("testler"), [], "ikamede hiçbir test KOŞMAMALI")
        self.assertIn("İKAME", self.cikti(r))
        self.assertIn("KAPSAM", self.cikti(r))

    def test_6_RAPOR_ikameyi_KALICI_olarak_soyler(self):
        """Kapanış raporu 'Yeni kırmızı: yok' ile yetinmemeli; yerelde test KOŞULMADIĞINI yazmalı."""
        self._ci_yayinla(self._yesil())
        self._akis()
        self.f.calistir("kapanis")
        rapor = (self.f.durum_dizini() / "RAPOR.md").read_text(encoding="utf-8")
        self.assertIn("sonra-ölçüm: yerelde test KOŞULMADI", rapor)
        self.assertIn("once-ölçüm: yerelde test KOŞULMADI", rapor)

    def test_2_KONTROL_ci_durumu_YOKKEN_olcer(self):
        r, veri = self._akis()
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.assertNotIn("kaynak", veri)
        self.assertTrue(any(t["cikis"] is not None for t in veri["testler"]), veri["testler"])

    def test_3_KONTROL_diske_fazla_dosya_girdiyse_olcer(self):
        self._ci_yayinla(self._yesil())
        r, veri = self._akis(bozucu=lambda: (self.f.tuketici / "fazla.md").write_text(
            "yerel\n", encoding="utf-8"))
        self.assertNotIn("kaynak", veri, "disk ağacı yayından farklıysa ikame OLMAMALI")
        self.assertIn("FARKLI", self.cikti(r))

    def test_4_KONTROL_uygulama_yapilmadiysa_olcer(self):
        self._ci_yayinla(self._yesil())
        _r, veri = self._akis(uygula=False)
        self.assertNotIn("kaynak", veri, "ağaç hâlâ eski sürümdeyken ikame OLMAMALI")

    def test_5_KONTROL_yargi_vakasi_varsa_olcer(self):
        self._ci_yayinla(self._yesil())
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        self.f.calistir("olc", "--asama", "once")
        self.f.calistir("olc", "--asama", "sonra")
        veri = json.loads((self.f.durum_dizini() / "olcum-sonra.json").read_text(encoding="utf-8"))
        self.assertNotIn("kaynak", veri)


class CakismaIsaretiTest(unittest.TestCase):
    """v0.4.2 — çakışma işareti YALNIZ satır başında aranır (git'in yazdığı biçim).

    ⛔ ÖLÇÜLEN KUSUR (v0.4.1, gerçek tüketici güncellemesi 2026-09-21): kapanış `=======`
    alt-dizisini dosyanın HER YERİNDE arıyordu ⇒ `# =====…` bölüm ayracı taşıyan 7 dosya
    (motorun kendisi dahil, yayın blob'uyla bayt-bayt aynı) FAIL verdi. Testler yakalamadı:
    fixture dosyaları tek satırlık sentetik içerikti, gerçek ürün dosyası HİÇ taranmıyordu.
    ⇒ pozitif kontrol olarak GERÇEK ürün dosyaları kullanılır.
    """

    def _f(self):
        import guncelle  # noqa: PLC0415
        return guncelle.cakisma_isaretleri

    def test_1_GERCEK_urun_dosyalari_temiz_sayilir(self):
        kok = BURASI.parent
        yollar = ["scripts/guncelle.py", "scripts/guncelle_proje.py", "kur.ps1",
                  "tests/test_guncelle.py", "skills-sap/sap-adt-foundation/scripts/sapadt/tools/atom.py"]
        for yol in yollar:
            with self.subTest(yol=yol):
                metin = (kok / yol).read_text(encoding="utf-8", errors="replace")
                self.assertIn("=======", metin, "kalibrasyon: dosya alt-diziyi taşımalı")
                self.assertEqual([], self._f()(metin))

    def test_2_KONTROL_gercek_git_cakisma_blogu_YAKALANIR(self):
        blok = "a\n<<<<<<< yerel\nbizim\n||||||| taban\neski\n=======\nonlarin\n>>>>>>> v3\nb\n"
        self.assertEqual(4, len(self._f()(blok)), self._f()(blok))
        self.assertTrue(self._f()("x\r\n=======\r\ny\r\n"), "CRLF'li ayraç satırı da yakalanmalı")
        self.assertTrue(self._f()("<<<<<<<\n"), "etiketsiz işaret de yakalanmalı")

    def test_3_KONTROL_satir_ortasindaki_alt_dizi_isaret_DEGILDIR(self):
        for metin in ("# =========\n", "x = '======='\n", "  =======\n", "a >>>>>>> b\n"):
            with self.subTest(metin=metin):
                self.assertEqual([], self._f()(metin))

    def test_4_urunun_KENDI_isaretleri_referansla_temiz_sayilir(self):
        """Bug gate 2026-09-21: `guncelle/kartlar/V4c.md` örnek bloğu satır başında GERÇEK işaret
        taşır ⇒ yalnız satır başı kuralı o kart değiştiği ilk yayında her tüketicide sahte FAIL
        verirdi. Yayın içeriği referans verilince yalnız FAZLA işaretler sayılır."""
        kart = (BURASI.parent / "guncelle" / "kartlar" / "V4c.md").read_text(encoding="utf-8")
        self.assertTrue(self._f()(kart), "kalibrasyon: kart satır başı işaret taşımalı")
        self.assertEqual([], self._f()(kart, kart), "yayınla aynı kart temiz sayılmalı")
        cakisik = kart + "\n<<<<<<< YEREL:x\nbiz\n||||||| TABAN:x\n=======\nonlar\n>>>>>>> YENİ:x\n"
        self.assertEqual(4, len(self._f()(cakisik, kart)),
                         "KONTROL: referansın üstüne eklenen gerçek çakışma bloğu yakalanmalı")

    def test_5_ayrac_sonrasi_bosluk_da_yakalanir(self):
        self.assertTrue(self._f()("a\n======= \nb\n"), "elle çözümde kalan '======= ' yakalanmalı")


class TopluOkumaTest(GeciciTest):
    """Z31 (2026-09-21): plan turu 1455 git süreci başlatıyordu (76 sn, ölçüldü) → toplu okuma.

    Sözleşme: ① blok içinde cevaplar tek-tek yolla AYNI (dizin yolu, olmayan yol, değişmiş dosya)
    ② önbellek YALNIZ blok içinde yaşar — bloktan sonra yazılan dosyanın hash'i TAZE okunur
    (bayat hash doğrulamayı sessizce körleştirirdi).
    """

    def _klon(self):
        import guncelle  # noqa: PLC0415
        kok = self.tmp / "k"
        kok.mkdir()
        self.git(kok, "init", "-q", "-b", "main")
        self.yaz(kok / "a.txt", "bir\n")
        self.yaz(kok / "d" / "b.txt", "iki\n")
        self.git(kok, "add", "-A")
        self.git(kok, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c1")
        self.yaz(kok / "a.txt", "degisti\n")
        return guncelle.Klon(kok), kok

    def test_1_blok_icinde_cevaplar_tek_tek_yolla_ayni(self):
        k, _ = self._klon()
        yollar = ["a.txt", "d/b.txt", "d", "yok.txt"]
        tek = {y: (k.blob_sha("HEAD", y), k.disk_sha(y) if y != "d" else None) for y in yollar}
        with k.toplu_okuma(yollar):
            # Kalibrasyon SOMUT (bug gate 2026-09-21): `_disk` toplu çağrı düşse de `{}` olur ve
            # her soru tek-tek yola düşse bile "cevaplar aynı" kendiliğinden doğru çıkar ⇒ önbelleğin
            # GERÇEKTEN dolduğu ölçülmezse hız kazancı (Z31) sessizce geri kayabilir.
            self.assertEqual({"a.txt", "d/b.txt"}, set(k._disk), "disk önbelleği dolmadı")
            toplu = {y: (k.blob_sha("HEAD", y), k.disk_sha(y) if y != "d" else None)
                     for y in yollar}
            self.assertTrue(k._agaclar, "ağaç önbelleği kullanılmadı")
        self.assertEqual(tek, toplu)
        self.assertIsNotNone(tek["d"][0], "dizin yolu tree sha döndürmeli (rev-parse ile aynı)")

    def test_2_bloktan_sonra_disk_hash_TAZE(self):
        k, kok = self._klon()
        with k.toplu_okuma(["a.txt"]):
            once = k.disk_sha("a.txt")
        self.yaz(kok / "a.txt", "yeniden yazildi\n")
        self.assertIsNone(k._disk, "önbellek blok dışında KAPALI olmalı")
        self.assertNotEqual(once, k.disk_sha("a.txt"), "yazımdan sonra bayat hash dönmemeli")


class CiTabaniKirmiziTest(unittest.TestCase):
    """Z16 — CI tabanıyla `yeni_kirmizilar` SESSİZ SAHTE-YEŞİL vermemeli.

    CI tabanında `testler` boştur. Eşleme dalı bu durumda hiçbir kimlik bulamaz ve her testi
    `continue` ile atlardı ⇒ her şey kırmızıyken bile "yeni kırmızı yok" denirdi.
    """

    def _kur(self, tmp: Path, once: dict, sonra: dict):
        import guncelle  # noqa: PLC0415
        d = tmp / ".axet-guncelleme"
        d.mkdir(parents=True, exist_ok=True)
        for ad, veri in (("olcum-once.json", once), ("olcum-sonra.json", sonra)):
            (d / ad).write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        klon = guncelle.Klon(tmp)
        return guncelle.yeni_kirmizilar(klon)

    def test_1_ci_tabani_altinda_kirmizi_YAKALANIR(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            yeni = self._kur(
                Path(td),
                {"asama": "once", "kaynak": "ci", "testler": []},
                {"asama": "sonra", "testler": [{"kimlik": ".::python tests/run_tests.py",
                                                "cikis": 1, "failure": 2}]})
            self.assertEqual(yeni, [".::python tests/run_tests.py"])

    def test_2_KONTROL_ci_tabani_altinda_hepsi_yesilse_bos(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            yeni = self._kur(
                Path(td),
                {"asama": "once", "kaynak": "ci", "testler": []},
                {"asama": "sonra", "testler": [{"kimlik": "a", "cikis": 0, "failure": 0}]})
            self.assertEqual(yeni, [])

    def test_3_KONTROL_olculemedi_yeni_kirmizi_SAYILMAZ(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            yeni = self._kur(
                Path(td),
                {"asama": "once", "kaynak": "ci", "testler": []},
                {"asama": "sonra", "testler": [{"kimlik": "a", "cikis": None, "failure": None}]})
            self.assertEqual(yeni, [], "ÖLÇÜLEMEDİ ayrı bir hükümdür, 'yeni kırmızı' değildir")

    def test_4_KONTROL_normal_taban_davranisi_DEGISMEDI(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            yeni = self._kur(
                Path(td),
                {"asama": "once", "testler": [{"kimlik": "a", "cikis": 0, "failure": 0}]},
                {"asama": "sonra", "testler": [{"kimlik": "a", "cikis": 1, "failure": 1}]})
            self.assertEqual(yeni, ["a"])
class KapsananKomutTest(unittest.TestCase):
    """Z16/A — filtresiz eşi koşarken `-k` filtreli komut TEKRAR koşulmamalı.

    Ölçülmüş israf (2026-09-20, v0.3.0 planı, gerçek klon): tur başına 18 komuttan 6'sı
    `python tests/run_tests.py -k …` ve listede FİLTRESİZ `python tests/run_tests.py` de var.
    Kapsama ilişkisi çalıştırıcının semantiğinden gelir (`run_tests.py` `-k`'yı
    `testNamePatterns` yapar = yalnız süzer), sezgiden değil.
    """

    def _ayikla(self, komutlar):
        import guncelle  # noqa: PLC0415
        testler = [{"komut": k, "cwd": c} for c, k in komutlar]
        kalan, dusen = guncelle._kapsananlari_ayikla(testler)
        return [t["komut"] for t in kalan], dusen

    def test_1_filtresiz_es_varsa_filtreli_DUSER(self):
        kalan, dusen = self._ayikla([
            (".", "python tests/run_tests.py -k kur"),
            (".", "python tests/run_tests.py"),
            (".", "python tests/run_tests.py -k install"),
        ])
        self.assertEqual(kalan, ["python tests/run_tests.py"])
        self.assertEqual(len(dusen), 2, f"iki filtreli komut düşmeliydi: {dusen}")

    def test_2_KONTROL_filtresiz_es_YOKSA_filtreli_KALIR(self):
        kalan, dusen = self._ayikla([
            (".", "python tests/run_tests.py -k kur"),
            (".", "python tests/run_tests.py -k install"),
        ])
        self.assertEqual(len(kalan), 2, "filtresiz eş yokken hiçbir şey düşmemeli")
        self.assertEqual(dusen, [])

    def test_3_KONTROL_farkli_cwd_KAPSAMAZ(self):
        kalan, _ = self._ayikla([
            ("skills/x", "python tests/run_tests.py -k kur"),
            (".", "python tests/run_tests.py"),
        ])
        self.assertEqual(len(kalan), 2, "farklı cwd farklı ağaçtır; kapsama iddiası kurulamaz")

    def test_4_KONTROL_farkli_calistirici_KAPSAMAZ(self):
        kalan, _ = self._ayikla([
            (".", "python skills-sap/sap-adt-foundation/tests/run_tests.py -k a"),
            (".", "python tests/run_tests.py"),
        ])
        self.assertEqual(len(kalan), 2, "başka çalıştırıcının filtresi bu çalıştırıcıyla kapsanmaz")

    def test_5_KONTROL_degersiz_k_DUSURULMEZ(self):
        kalan, dusen = self._ayikla([
            (".", "python tests/run_tests.py -k"),
            (".", "python tests/run_tests.py"),
        ])
        self.assertEqual(len(kalan), 2, "değersiz `-k` süzme iddiası kurmaz; dokunulmaz")
        self.assertEqual(dusen, [])

    def test_6_KONTROL_filtresiz_komut_ASLA_dusmez(self):
        kalan, dusen = self._ayikla([
            (".", "python tests/run_tests.py"),
            (".", "python scripts/doctor.py"),
            (".", "python -m unittest discover -s skills-sap/sap-code-review/tests"),
        ])
        self.assertEqual(len(kalan), 3)
        self.assertEqual(dusen, [])

    def test_7_gercek_haritada_israf_OLCULUR_ve_ayiklanir(self):
        """Kanıt testi: gerçek `harita.json`'daki komut evreninde ayıklama bir şeyi düşürüyor mu?"""
        import guncelle  # noqa: PLC0415
        harita = json.loads((BURASI.parent / "guncelle" / "harita.json").read_text(encoding="utf-8"))
        gorulen, testler = set(), []
        for s in harita["siniflar"]:
            for t in s.get("test", []):
                anahtar = (t["komut"], t.get("cwd", "."))
                if anahtar not in gorulen:
                    gorulen.add(anahtar)
                    testler.append(t)
        kalan, dusen = guncelle._kapsananlari_ayikla(testler)
        self.assertGreater(len(dusen), 0,
                           "gerçek haritada filtresiz `tests/run_tests.py` ile birlikte gelen "
                           "filtreli komutlar var; hiçbiri düşmediyse ayıklama kablolanmamıştır")
        self.assertTrue(all("-k" in d for d in dusen), f"yalnız filtreli komut düşmeli: {dusen}")
        self.assertEqual(len(kalan) + len(dusen), len(testler))
class ZamanAsimiTest(unittest.TestCase):
    """Ölçüm komutu zaman aşımına uğrarsa ÇÖKMEZ, `ÖLÇÜLEMEDİ` yazılır (2026-09-20 vakası).

    Gerçek vaka: bir tüketici klonunda `olc --asama once` 34 dk 50 sn koştu ve
    `subprocess.TimeoutExpired` yukarı kaçtı ⇒ traceback, `olcum-once.json` HİÇ yazılmadı,
    35 dakikalık ölçüm çöpe gitti. Kök takımı CI'da 2411 sn sürüyordu, `_run`'ın varsayılanı
    1800 sn'ydi: ölçüm YAPISAL OLARAK imkânsızdı ve bunu hiçbir test söylemiyordu.
    """

    def _kur(self, td: str, patlat: bool):
        import types, subprocess as sp  # noqa: PLC0415
        import guncelle  # noqa: PLC0415
        kok = Path(td)
        (kok / "tests").mkdir(parents=True)
        (kok / "tests" / "run_tests.py").write_text(
            "print('ok')\n", encoding="utf-8")
        klon = guncelle.Klon(kok)
        klon.durum_dizini.mkdir(parents=True, exist_ok=True)
        plan = {"yeni_etiket": "v9", "kalemler": [
            {"id": "9-01", "dosyalar": [{"yol": "tests/test_x.py", "sinif": "test-kok",
                                         "vaka": "V1"}]}]}
        (klon.durum_dizini / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        (klon.durum_dizini / "secim.json").write_text(
            json.dumps({"kalemler": ["9-01"]}), encoding="utf-8")
        harita = {"siniflar": [{"sinif": "test-kok", "glob": ["tests/*"],
                                "test": [{"komut": "python tests/run_tests.py", "cwd": ".",
                                          "on_kosul": None}]}]}
        gercek = guncelle._run

        def sahte(args, cwd, **kw):
            if patlat and args and str(args[-1]).endswith("run_tests.py"):
                raise sp.TimeoutExpired(args, kw.get("timeout", 0))
            return gercek(args, cwd, **kw)

        return guncelle, types.SimpleNamespace(k=klon, harita=harita), sahte

    def test_1_zaman_asimi_COKMEZ_OLCULEMEDI_yazilir(self):
        import tempfile, unittest.mock as mock  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as td:
            g, b, sahte = self._kur(td, patlat=True)
            with mock.patch.object(g, "_run", sahte):
                rc = g.komut_olc(b, argparse.Namespace(asama="once"))
            self.assertEqual(rc, 2, "hiçbir komut ölçülemediyse çıkış 2 olmalı (ÖLÇÜLEMEDİ ≠ temiz)")
            veri = json.loads((b.k.durum_dizini / "olcum-once.json").read_text(encoding="utf-8"))
            self.assertTrue(veri["testler"], "kayıt YAZILMALI — çökmede hiç yazılmıyordu")
            self.assertIsNone(veri["testler"][0]["cikis"])
            self.assertIn("zaman aşımı", veri["testler"][0]["not"])

    def test_2_KONTROL_zaman_asimi_yokken_normal_olculur(self):
        import tempfile, unittest.mock as mock  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as td:
            g, b, sahte = self._kur(td, patlat=False)
            with mock.patch.object(g, "_run", sahte):
                rc = g.komut_olc(b, argparse.Namespace(asama="once"))
            self.assertEqual(rc, 0, "kontrol grubu kırmızıysa asıl ölçüm anlamsız")
            veri = json.loads((b.k.durum_dizini / "olcum-once.json").read_text(encoding="utf-8"))
            self.assertEqual(veri["testler"][0]["cikis"], 0)

    def test_3_olcum_zaman_asimi_kok_takimi_suresini_KAPSAR(self):
        """Sabitin değeri kanıta bağlı: gözlenen en uzun kök koşumu 2411 sn (CI, 2026-09-20)."""
        import guncelle  # noqa: PLC0415
        self.assertGreater(
            guncelle.OLCUM_ZAMAN_ASIMI, 2411,
            "OLCUM_ZAMAN_ASIMI gözlenen en uzun kök takımı koşumunu (2411 sn) kapsamıyor — "
            "ölçüm yapısal olarak imkânsız hâle gelir (2026-09-20 vakası)")


class Z54ModulKomutuOlculurTest(GuncelleTemel):
    """⛔ Z54 (2026-09-22, canlı `butunluk.json`): `python -m unittest discover -s X` biçimli ölçüm
    komutları HİÇ koşmuyordu. Üç çağrı yeri `parcalar[1]`i betik yolu sayıp `<kök>/-m` var mı diye
    bakıyordu ⇒ "ÖLÇÜLEMEDİ — -m yok". Canlıda `sap-code-review takımı` adımı böyle düştü;
    harita.json'da aynı biçimde 5 sınıf / 6 test komutu var (skill-test ×2, validator-zincir-map,
    validator-runner, validator, validator-diger-skill).

    Çağrı yerleri ayrı ayrı ölçülür: `olc` (test_2) · `butunluk` (test_3). `ozel-adim` bu biçimi
    YAPISAL olarak göremez (`_PY_KOMUT` yalnız `python <yol>.py` çıkarır + allowlist yalnız
    `scripts/install.py`) ⇒ orada kırmızı-önce test kurulamaz; test_4 davranışın DEĞİŞMEDİĞİNİ ölçer.
    KAPSAM — bakılmayan: gerçek sap-code-review takımının içeriği (fixture'da tek sahte test koşar).
    """

    MTEST = "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"

    def setUp(self) -> None:
        super().setUp()
        self.senaryolari_uygula()
        self.assertEqual(self.hazirla_ve_planla().returncode, 0)
        self.assertEqual(self.f.calistir("sec", "--hepsi").returncode, 0)
        for s in ("scripts",):
            p = str(AXET_HOME / s)
            if p not in sys.path:
                sys.path.insert(0, p)
        import guncelle  # noqa: PLC0415
        self.g = guncelle

    def test_1_betik_yolu_birim(self):
        by = self.g._betik_yolu
        self.assertEqual(by(["py", "-m", "unittest", "discover", "-s", "a/b", "-t", "a/b"]), "a/b")
        self.assertIsNone(by(["py", "-m", "unittest"]), "-s yoksa ön denetim yok (rc hükmeder)")
        self.assertIsNone(by(["py", "-m", "unittest", "discover", "-s"]))
        self.assertIsNone(by(["py", "-m", "pytest", "-s", "tests"]),
                          "`-s` yalnız `unittest discover`da dizindir (pytest'te çıktı yakalama bayrağı)")
        self.assertEqual(by(["py", "scripts/doctor.py", "--x"]), "scripts/doctor.py")
        self.assertIsNone(by(["py"]))

    def _harita(self, komut: str, validator_ailesi: bool = False) -> str:
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        hedef = self.g.sinif_bul("core/00-temel.md", harita)
        self.assertIsNotNone(hedef, "fixture geçersiz: core/00-temel.md sınıfsız")
        for s in harita["siniflar"]:
            if s.get("test"):
                s["test"] = [{"komut": komut, "cwd": ".", "on_kosul": None}]
        if validator_ailesi:
            hedef["ust_sinif"] = "validator-ailesi"
        yol = self.tmp / "harita-z54.json"
        yol.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        return str(yol)

    def test_2_olc_modul_komutunu_KOSAR(self):
        self.f.yerel_degistir("tests/mtest/test_m.py", self.MTEST)
        komut = "python -m unittest discover -s tests/mtest -t tests/mtest"
        r = self.f.calistir("--harita", self._harita(komut), "olc", "--asama", "once")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        kayit = [t for t in veri["testler"] if t["kimlik"] == f".::{komut}"]
        self.assertEqual(len(kayit), 1, veri["testler"])
        self.assertEqual(kayit[0]["cikis"], 0, kayit[0])
        self.assertNotIn("-m yok", json.dumps(veri, ensure_ascii=False))

    def test_2b_KONTROL_olc_s_dizini_yoksa_OLCULEMEDI(self):
        """Ön denetim KÖRLEŞMEDİ: `-s` dizini gerçekten yoksa yine ÖLÇÜLEMEDİ."""
        komut = "python -m unittest discover -s tests/yok -t tests/yok"
        r = self.f.calistir("--harita", self._harita(komut), "olc", "--asama", "once")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        self.assertTrue(all(t["cikis"] is None for t in veri["testler"]))
        self.assertIn("tests/yok yok", json.dumps(veri, ensure_ascii=False))

    def test_3_butunluk_sap_code_review_adimi_KOSAR(self):
        self.f.yerel_degistir("skills-sap/sap-code-review/tests/test_m.py", self.MTEST)
        h = self._harita("python tests/run_tests.py", validator_ailesi=True)
        r = self.f.calistir("--harita", h, "butunluk")
        b = json.loads((self.f.durum_dizini() / "butunluk.json").read_text(encoding="utf-8"))
        adim = [a for a in b["adimlar"] if a["ad"] == "sap-code-review takımı"]
        self.assertEqual(len(adim), 1, b["adimlar"])
        self.assertEqual(adim[0]["cikis"], 0, adim[0])
        self.assertIn("Ran 1 test", adim[0]["cikti"])
        self.assertEqual(r.returncode, 0, self.cikti(r))

    def test_3b_KONTROL_butunluk_takim_dizini_yoksa_OLCULEMEDI(self):
        h = self._harita("python tests/run_tests.py", validator_ailesi=True)
        self.f.calistir("--harita", h, "butunluk")
        b = json.loads((self.f.durum_dizini() / "butunluk.json").read_text(encoding="utf-8"))
        adim = [a for a in b["adimlar"] if a["ad"] == "sap-code-review takımı"][0]
        self.assertIsNone(adim["cikis"])
        self.assertIn("skills-sap/sap-code-review/tests yok", adim["not"])

    def test_4_ozel_adim_betik_komutu_davranisi_DEGISMEDI(self):
        """`ozel-adim` `-m` biçimini hiç görmez (yapısal); betik yolu denetimi eskisi gibi."""
        self.assertIsNone(self.g._PY_KOMUT.search("python -m unittest discover -s x"))
        harita = json.loads(HARITA.read_text(encoding="utf-8"))
        for s in harita["siniflar"]:
            if s["sinif"] == "config-izin-kok":
                s["ozel_adim"] = "python scripts/install.py --dry-run"
        yol = self.tmp / "harita-ozel-z54.json"
        yol.write_text(json.dumps(harita, ensure_ascii=False), encoding="utf-8")
        (self.f.tuketici / "scripts" / "install.py").unlink()
        r = self.f.calistir("--harita", str(yol), "ozel-adim", "config-izin-kok")
        self.assertIn("betik yok", self.cikti(r))
