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
        self.assertIn("Klon güncel", self.cikti(r))

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
        self.f.calistir("uygula", "--otomatik")
        d = self.f.durum()["dosyalar"]
        self.assertEqual(d["docs/silinecek.md"]["vaka"], "V6d")
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
        `yerel` bırakılan `skills/cakisan/SKILL.md` İZLENMEYEN kalır; `.gitignore`a eklenince
        `git add -- <yol>` `rc=1` + "ignored by one of your .gitignore files" verir.
        """
        self.assertEqual(self.f.calistir("olc", "--asama", "once").returncode, 0)
        self.assertEqual(self.f.calistir("uygula", "--otomatik").returncode, 0)
        self._tum_yargilari_kapat(haric="skills/cakisan/SKILL.md")
        r = self.f.calistir("isaretle", "skills/cakisan/SKILL.md", "--karar", "yerel")
        self.assertEqual(r.returncode, 0, self.cikti(r))
        self.ozel_adimlari_kostur()
        self.assertEqual(self.f.calistir("olc", "--asama", "sonra").returncode, 0)
        self.assertEqual(self.f.calistir("butunluk").returncode, 0)

        # kontrol grubu: yol gerçekten İZLENMİYOR (yoksa .gitignore `git add`i etkilemez)
        self.assertEqual(self.git(self.f.tuketici, "ls-files", "--",
                                  "skills/cakisan/SKILL.md").stdout.strip(), "")
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

    def test_kapanis_COMMIT_BASARISIZSA_eksik_olur_ve_muhur_basilmaz(self):
        """⛔ BLOCKER-3 (kardeş vaka): commit'in kendisi patlarsa da yalnız `UYARI:` basılıyordu.

        Ayrıca `rc=1` KOŞULSUZ tolere ediliyordu ("commit edilecek bir şey yok" varsayımı).
        Burada stage'de fark VAR ve commit `gpg.program` yok diye patlar ⇒ rc=1'in ikinci
        anlamı ölçülür. `--no-verify` bunu ATLAMAZ (hook değil, imzalama).
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

    def test_hicbir_test_betigi_kosturulamazsa_cikis_2(self):
        for y in ("tests/run_tests.py", "scripts/doctor.py"):
            (self.f.tuketici / y).unlink()
        r = self.f.calistir("olc", "--asama", "once")
        self.assertEqual(r.returncode, 2, self.cikti(r))
        veri = json.loads((self.f.durum_dizini() / "olcum-once.json").read_text(encoding="utf-8"))
        self.assertTrue(veri["testler"], "kayıt yine de yazılmalı (ölçülemedi ≠ hiç bakılmadı)")
        self.assertTrue(all(t["cikis"] is None for t in veri["testler"]),
                        [t for t in veri["testler"] if t["cikis"] is not None])


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
