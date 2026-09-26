# -*- coding: utf-8 -*-
"""`maintenance/yayin_provasi.py` — Z100: prova `<TMP>`'yi skill'in TMP-OLUSTUR komutuyla yaratır.

⛔ NEDEN: prova motoru skill'in MOTOR-CIKAR komutlarıyla AYNEN çıkarıyordu (Z32) ama `<TMP>`'yi kendi
`mkdir`'iyle yaratıyordu ⇒ Z67'nin TMP-OLUSTUR bloğu (kullanıcının koştuğu İLK komut) provada hiç
koşmuyordu; yalnız `test_guncelle_baslatici` onu izole ölçüyordu (v0.5.8 bug gate, Z100). Belgedeki
blok bozulursa kullanıcının `%guncelle`si ilk adımda düşer ⇒ prova da aynı yerde düşmelidir.

Ne ölçülür: ① komut ADAYIN `skills/guncelle/SKILL.md`'sinden okunur (çalışma ağacından değil)
② korumalı ortamda `<TMP>` `%LOCALAPPDATA%\\Temp` altında yaratılır (komutun birincil dalı; gerçek
Windows düzeni) ③ `prova_kos` bu `<TMP>`'yi MOTOR-CIKAR'a verir ve motor oraya çıkarılır ④ blok
yoksa prova KURULAMAZ (sessiz geri düşüş yok) ⑤ komutun çıktısı dizin değilse ya da klonun içindeyse
`<TMP>` kabul edilmez.
KAPSAM — bakılmayan: gerçek public depo üzerinde tam prova (ağ + `yayin_hazirla`; lider yayında koşar)
· `prova_kos`'un `yeni proje` adımından sonraki akışı (burada bilerek o adımda durdurulur).
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from _helpers import AXET_HOME, GeciciTest

BETIK = AXET_HOME / "maintenance" / "yayin_provasi.py"
sys.path.insert(0, str(AXET_HOME / "maintenance"))
# public sürümde maintenance/ dışlanır ⇒ modül yok; import hatası tüm keşfi (`-k` filtreleri dahil) bozar.
try:
    import yayin_provasi as yp  # noqa: E402
except ModuleNotFoundError:
    if BETIK.is_file():
        raise
    yp = None

SKILL = AXET_HOME / "skills" / "guncelle" / "SKILL.md"


@unittest.skipUnless(BETIK.is_file(), "maintenance/yayin_provasi.py yok (public sürümde maintenance/ dışlanır)")
class Z100TmpOlusturTest(GeciciTest):
    def sahte_public(self, skill_metni: str | None = None) -> Path:
        """Asgari aday: kurulum betiği (0 döner), motor + talimat, skill. `new_project.py` YOK ⇒
        `prova_kos` motor çıkarıldıktan sonra `yeni proje` adımında bilerek durur."""
        pub = self.tmp / "public"
        (pub / "scripts").mkdir(parents=True)
        (pub / "skills" / "guncelle").mkdir(parents=True)
        (pub / "scripts" / "install.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        shutil.copy2(AXET_HOME / "scripts" / "guncelle.py", pub / "scripts" / "guncelle.py")
        shutil.copy2(AXET_HOME / "GUNCELLE.md", pub / "GUNCELLE.md")
        shutil.copytree(AXET_HOME / "guncelle", pub / "guncelle")
        (pub / "skills" / "guncelle" / "SKILL.md").write_text(
            SKILL.read_text(encoding="utf-8") if skill_metni is None else skill_metni,
            encoding="utf-8", newline="")
        self.git(pub, "init", "-q", "-b", "main")
        self.git(pub, "add", "-A")
        self.git(pub, "commit", "-q", "-m", "aday")
        self.git(pub, "tag", "v0")
        return pub

    def ortam(self):
        """`prova_kos` `os.environ`'dan türetir: git'in global/sistem config'i testte yok sayılsın."""
        return mock.patch.dict(os.environ, self.env, clear=True)

    def test_komut_adayin_skill_blogundan_okunur(self):
        pub = self.sahte_public()
        # çalışma ağacındaki kopya bozulsa bile komut COMMIT'ten (adaydan) okunur
        (pub / "skills" / "guncelle" / "SKILL.md").write_text("bozuk\n", encoding="utf-8")
        argv = yp.tmp_komutu(pub, self.tmp / "klon")
        self.assertEqual(argv[0], "-c", argv)
        self.assertIn("axet_guncelle_", argv[1])
        self.assertEqual(argv[-1], (self.tmp / "klon").as_posix(), "`<KLON>` doldurulmadı")

    def test_blok_yoksa_prova_kurulamaz(self):
        pub = self.sahte_public(skill_metni="---\nname: guncelle\n---\nblok yok\n")
        with self.assertRaises(yp.ProvaHatasi) as h:
            yp.tmp_komutu(pub, self.tmp / "klon")
        self.assertIn("TMP-OLUSTUR", str(h.exception))

    def test_gecici_dizin_dogrulamasi(self):
        kon = self.tmp / "klon"
        (kon / "ic").mkdir(parents=True)
        dis = self.tmp / "dis"
        dis.mkdir()
        self.assertEqual(yp.gecici_dizin(f"uyari\n{dis.as_posix()}\n", kon), dis.resolve())
        self.assertIsNone(yp.gecici_dizin((kon / "ic").as_posix(), kon), "klon içindeki dizin kabul edildi")
        self.assertIsNone(yp.gecici_dizin((self.tmp / "yok").as_posix(), kon), "olmayan dizin kabul edildi")
        (dis / "dolu.txt").write_text("x", encoding="utf-8")
        self.assertIsNone(yp.gecici_dizin(dis.as_posix(), kon), "boş olmayan dizin kabul edildi")
        self.assertIsNone(yp.gecici_dizin("", kon))

    def test_prova_kos_tmp_yi_skill_komutuyla_yaratir_ve_motoru_oraya_cikarir(self):
        pub = self.sahte_public()
        is_dizini = self.tmp / "is"
        is_dizini.mkdir()
        with self.ortam(), contextlib.redirect_stdout(io.StringIO()):
            sonuc = yp.prova_kos(pub, "v0", is_dizini)
        adlar = [a["ad"] for a in sonuc["adimlar"]]
        self.assertIn("tmp-olustur", adlar, f"TMP-OLUSTUR adımı koşmadı: {adlar}")
        tmp_adim = sonuc["adimlar"][adlar.index("tmp-olustur")]
        self.assertEqual(tmp_adim["rc"], 0, tmp_adim["cikti"])
        self.assertLess(adlar.index("tmp-olustur"), adlar.index("motor-cikar 1"),
                        "`<TMP>` motor çıkarılmadan ÖNCE yaratılmalı")
        for a in sonuc["adimlar"]:
            if a["ad"].startswith("motor-cikar"):
                self.assertTrue(a["tamam"], f"{a['ad']}: {a['cikti']}")
        # kurgu gereği `yeni proje` adımında durur (aday new_project.py taşımıyor)
        self.assertEqual(sonuc["neden"], "eski sürümle proje açılamadı", sonuc)
        # `<TMP>` korumalı ortamın %LOCALAPPDATA%\Temp'i altında (komutun birincil dalı) ve motoru taşıyor
        temp = is_dizini / "kum-v0" / "localappdata" / "Temp"
        adaylar = sorted(temp.glob("axet_guncelle_*")) if temp.is_dir() else []
        self.assertEqual(len(adaylar), 1, f"{temp} altında tek `<TMP>` bekleniyordu: {adaylar}")
        self.assertTrue((adaylar[0] / "scripts" / "guncelle.py").is_file(), "motor `<TMP>`'ye çıkarılmadı")
        self.assertFalse((is_dizini / "motor-v0").exists(), "eski `mkdir` yolu hâlâ kullanılıyor")

    def test_prova_kos_tmp_olusturulamazsa_FAIL(self):
        """Negatif: komut sıfırdan farklı dönerse (burada: blok DUR basıp çıkıyor) prova FAIL — sessiz
        `mkdir` geri düşüşü YOK."""
        metin = SKILL.read_text(encoding="utf-8")
        bas, bit = yp.TMP_OLUSTUR
        i, j = metin.index(bas), metin.index(bit)
        bozuk = metin[:i] + bas + "\n```bash\npython -c \"import sys; sys.exit('DUR: deneme')\" \"<KLON>\"\n```\n" \
            + metin[j:]
        pub = self.sahte_public(skill_metni=bozuk)
        is_dizini = self.tmp / "is"
        is_dizini.mkdir()
        with self.ortam(), contextlib.redirect_stdout(io.StringIO()):
            sonuc = yp.prova_kos(pub, "v0", is_dizini)
        self.assertEqual(sonuc["hukum"], "FAIL")
        self.assertIn("TMP-OLUSTUR", sonuc["neden"])
        self.assertNotIn("motor-cikar 1", [a["ad"] for a in sonuc["adimlar"]])
