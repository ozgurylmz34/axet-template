# -*- coding: utf-8 -*-
"""check_fs_no_analysis_log.py: sınıf başına pozitif + temiz örnek, template bölüm yapısı, kapsam, çıkış kodları."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from _common import SCRIPTS, TEMPLATES, call_main

import check_fs_no_analysis_log as m

SKELETON = """# FS-XX-100 — Örnek geliştirme
| Alan | Değer |
|---|---|
| Doküman no | FS-XX-100 |
| Versiyon | v1.2 |

## 1. Doküman kontrolü
### 1.1 Versiyon geçmişi
| Versiyon | Tarih | Değiştiren | Ne değişti |
|---|---|---|---|
| v1.0 | 01.01.2026 | Analist | İlk sürüm |
| v1.2 | 02.01.2026 | Analist | §4.2 KR-003 eklendi |

### 1.3 İlgili dokümanlar
| Doküman | No | Not |
|---|---|---|
| Teknik spesifikasyon | TS-XX-100 | v0.9 hazırlanıyor |

## 4. Fonksiyonel gereksinimler
### 4.1 Gereksinim listesi
%s

## 11-B. Açık kararlar
| No | Netleştirdiği istek | Seçenekler | Öneri | Karar |
|---|---|---|---|---|
| S-01 | K-1 | a · b | a | bekliyor |

## 12. Onay
| Rol | Ad | Tarih | İmza |
|---|---|---|---|

---

## EK — Karar ve kanıt günlüğü
| Karar no | Konu | Seçenekler | Seçilen | Kim / ne zaman | Kanıt atfı |
|---|---|---|---|---|---|
| K-01 | v1.1'de eklendi | a · b | a | 01.01.2026 | canlı ölçüldü |

### Yayılım tablosu
| Karar no | Dokunulacak yer | Durum | Kim / ne zaman |
|---|---|---|---|
| K-01 | §4.2 — v1.2'de işlendi, DOC-FS-05 bulgusu, kullanıcı: "tamam" | yapıldı | 02.01.2026 |

*Doküman sonu — FS-XX-100 v1.2*
"""

# Sınıf → (pozitif gövde satırı, aynı sinyalin meşru hâli = temiz karşılık)
VECTORS = {
    m.A: ("Kontrol Et butonu v1.5'te eklendi.",
          "Uygulama SAPUI5 1.120 kütüphanesiyle çalışır; OData V4 servisi kullanılır."),
    m.B: ("Buton matrisi netleştirildi (DOC-FS-05 bulgusu, ADR-7).",
          "| **ADR-4** | Onay akışı tek adımlıdır. |\nOnay akışı ADR-4 ile tanımlıdır; hata kodu M-2 ve L-01 verilir."),
    m.C: ("Fatura tipi ZM12'dir (DEV'de canlı ölçüldü; ilk turda alan adı yanlış yazılmıştı).",
          "Alan eşlemesi TS'te canlı ölçülür; eşleme build öncesi doğrulanmış olmalı."),
    m.D: ("Kullanıcı: \"fiyat koşulu Z001 olmalı\" — kullanıcı notu 17.08.",
          "Fiyat koşulu Z001'dir (kaynak: kullanıcı isteği K-1)."),
    m.E: ("Müşteri malzeme no artık kalem satırında gösterilmez (K-6 revizyonu).",
          "Bölünmeyen artık miktar hesaba katılır; daha önce tahsis edilmiş lot sonradan değiştirilir."),
}


def _doc(govde):
    return SKELETON % govde


def _write(root, rel, text, encoding="utf-8"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding) as fh:
        fh.write(text)
    return path


def _counts(text):
    f, lr, bl = m.scan_text(text)
    return {k: len(v) for k, v in f.items()}, lr, bl


class ClassVectorTest(unittest.TestCase):
    def test_skeleton_itself_is_clean(self):
        """Kontrol grubu: iskeletin kimlik satırları, §1.1/§1.3, 11-B, EK ve alt başlığı sayılmaz."""
        c, lr, bl = _counts(_doc("| FR-001 | Sipariş kaydedilir. |"))
        self.assertEqual(0, sum(c.values()), c)
        self.assertEqual([], lr)
        self.assertGreater(bl, 0)

    def test_each_class_positive_only_itself(self):
        for cls, (pozitif, _) in VECTORS.items():
            with self.subTest(cls=cls):
                c, _, _ = _counts(_doc(pozitif))
                self.assertGreaterEqual(c[cls], 1, "%s yakalanmadı: %s" % (cls, c))

    def test_each_class_clean_counterpart(self):
        for cls, (_, temiz) in VECTORS.items():
            with self.subTest(cls=cls):
                c, _, _ = _counts(_doc(temiz))
                self.assertEqual(0, sum(c.values()), "%s temiz karşılıkta işaret: %s" % (cls, c))

    def test_version_row_length(self):
        uzun = "| v1.3 | 03.01.2026 | Analist | %s |" % ("uzun anlatı " * 40)
        text = _doc("| FR-001 | Sipariş kaydedilir. |").replace("| v1.2 | 02.01.2026 | Analist | §4.2 KR-003 eklendi |",
                                                                  uzun)
        _, lr, _ = _counts(text)
        self.assertEqual(["§1.1"], [e for _, _, e in lr])
        _, lr, _ = _counts(_doc("| FR-001 | Sipariş kaydedilir. |"))
        self.assertEqual([], lr)

    def test_headings_are_body_except_h1(self):
        c, _, _ = _counts(_doc("### 4.3 Etkilenen alanlar (canlı ölçüldü)\nSipariş kaydedilir."))
        self.assertEqual(1, c[m.C])
        c, _, _ = _counts("# FS-XX-1 v1.5 — canlı ölçüldü\n\n## 2. Giriş\nSipariş kaydedilir.\n")
        self.assertEqual(0, sum(c.values()))

    def test_decision_log_file_skipped(self):
        c, lr, bl = _counts("# EK-A — Karar ve kanıt günlüğü\n\n## K-22\nv1.5 canlı ölçüldü, kullanıcı: \"x\"\n")
        self.assertEqual((0, [], 0), (sum(c.values()), lr, bl))


class TemplateAdaptationTest(unittest.TestCase):
    """Template FS şablonunun bölüm yapısına uyarlanan davranışlar — her biri karşıt kontrol grubuyla."""

    def test_subheading_under_decision_log_inherits(self):
        # "### Yayılım tablosu" EK karar günlüğünün altındadır → sayılmaz (SKELETON'daki satır).
        c, _, _ = _counts(_doc("Sipariş kaydedilir."))
        self.assertEqual(0, sum(c.values()), c)
        # Karşıt: aynı seviyede (##) yeni bir bölüm karar günlüğünü KAPATIR → yine gövdedir.
        text = _doc("Sipariş kaydedilir.").replace("*Doküman sonu", "## 13. Ekler\nOnay adımı v1.4'te eklendi.\n\n*Doküman sonu")
        c, _, _ = _counts(text)
        self.assertEqual(1, c[m.A], c)

    def test_related_documents_rows_by_section(self):
        # §1.3'te doküman no ikinci hücrededir ("| Teknik spesifikasyon | TS-XX-100 | v0.9 hazırlanıyor |") → sayılmaz.
        c, _, _ = _counts(_doc("Sipariş kaydedilir."))
        self.assertEqual(0, c[m.A])
        # Karşıt: aynı satır gövde tablosunda → sayılır; §1.3 altındaki düz metin de gövdedir.
        c, _, _ = _counts(_doc("| Teknik spesifikasyon | TS-XX-100 | v0.9 hazırlanıyor |"))
        self.assertEqual(1, c[m.A])
        text = _doc("Sipariş kaydedilir.").replace("| Teknik spesifikasyon | TS-XX-100 | v0.9 hazırlanıyor |",
                                                   "| Teknik spesifikasyon | TS-XX-100 | hazırlanıyor |\n\n"
                                                   "Bu liste v1.1'de genişletildi.")
        c, _, _ = _counts(text)
        self.assertEqual(1, c[m.A])

    def test_review_ids_are_template_formats(self):
        for satir in ("DOC-KD-03 bulgusu kapatıldı.", "DOC-TS-05 gereği eklendi.", "DOC-CR-02 düzeltmesi.",
                      "Karar ADR 12 ile alındı."):
            with self.subTest(satir=satir):
                self.assertEqual(1, _counts(_doc(satir))[0][m.B])
        for satir in ("H-1 eksikliği giderilir.", "Kalem M-2 hatası verir.", "Kalem L-3 ile kapanır.", "PDOC-FS-051 kodu."):
            with self.subTest(satir=satir):
                self.assertEqual(0, _counts(_doc(satir))[0][m.B])

    def test_numbered_subsection_is_not_version_history(self):
        text = _doc("#### 4.1.1 Alt kurallar\nOnay v1.4'te eklendi.").replace("### 4.1 Gereksinim listesi",
                                                                               "### 3.1.1 Alt süreç")
        self.assertEqual(1, _counts(text)[0][m.A])

    def test_hash_comment_in_code_block_keeps_section(self):
        text = _doc("Sipariş kaydedilir.").replace(
            "### Yayılım tablosu", "```\n# yorum satırı\n```\nv1.3'te işlendi (EK içinde).\n\n### Yayılım tablosu")
        self.assertEqual(0, sum(_counts(text)[0].values()))

    def test_headerless_version_table_then_next_table_is_body(self):
        text = ("# FS-XX-2 — Örnek\n\n## 1. Doküman kontrolü\n| Ver. | Tarih | Yazar | Açıklama |\n|---|---|---|---|\n"
                "| v1.3 | 03.01.2026 | X | %s |\n\n| Alan | Değer |\n|---|---|\n| Fatura tipi | v1.5'te değiştirildi |\n"
                % ("çok uzun sürüm anlatısı " * 30))
        c, lr, _ = _counts(text)
        self.assertEqual(1, c[m.A])
        self.assertEqual(["§1.1"], [e for _, _, e in lr])

    def test_template_fs_is_clean(self):
        rc, out, _ = call_main(m.main, [os.path.join(TEMPLATES, "FS-template.md"), "--bulguda-exit1"])
        self.assertEqual(0, rc, out)
        self.assertIn("SONUÇ: TEMİZ", out)

    def test_bom_file_h1_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "FS-XX-3.md", "# FS-XX-3 v1.5 — Örnek\n\n## 2. Giriş\nSipariş kaydedilir.\n", "utf-8-sig")
            rc, out, _ = call_main(m.main, [p, "--bulguda-exit1"])
        self.assertEqual(0, rc, out)


KIRLI = _doc("\n".join(p for p, _ in VECTORS.values()))
TEMIZ = _doc("\n".join(t for _, t in VECTORS.values()))


class ScopeAndExitTest(unittest.TestCase):
    def _tree(self, tmp):
        pk = os.path.join(tmp, "src", "SD", "PKG")
        for rel, text in {
            "docs/FS-XX-980_dogrudan.md": KIRLI,            # kontrol grubu
            "docs/alt/FS-XX-981_altklasor.md": KIRLI,       # alt klasör de docs ağacıdır
            "docs/alt/EK-A-XX-981.md": TEMIZ,
            "docs/TS-XX-980.md": KIRLI,
            "docs/alt/KD-XX-981.md": KIRLI,
            "docs/alt/node_modules/FS-XX-982.md": KIRLI,    # atlanan klasör
            "ref_docs/FS-XX-983_not.md": KIRLI,             # docs dışı
            "docs/alt/notlar.md": KIRLI,                    # öneksiz
        }.items():
            _write(pk, rel, text)
        return tmp

    @staticmethod
    def _warned(out):
        return {ln[7:].split(": gövde")[0].replace("\\", "/").rsplit("/", 1)[-1]
                for ln in out.splitlines() if ln.startswith("[WARN] ")}

    def test_default_scope_and_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _ = call_main(m.main, [self._tree(tmp), "--bulguda-exit1"])
        self.assertEqual(1, rc, out)
        self.assertEqual({"FS-XX-980_dogrudan.md", "FS-XX-981_altklasor.md"}, self._warned(out))
        self.assertIn("KAPSAM: FS/EK 3 tarandı (docs/ alt ağacı) · TS 1 / KD 1 TARANMADI", out)
        self.assertIn("docs/ DIŞINDA FS 1 TARANMADI", out)
        self.assertIn("KAPSAM (SCOPE)", out)
        self.assertIn("BU ARAÇ ŞUNLARA BAKMAZ", out)
        for cls in VECTORS:
            self.assertIn(cls, out)

    def test_opt_in_all_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _ = call_main(m.main, [self._tree(tmp), "--tur", "fs,ek,ts,kd"])
        self.assertEqual(0, rc, out)  # varsayılan uyarıdır, kapı değil
        self.assertEqual({"FS-XX-980_dogrudan.md", "FS-XX-981_altklasor.md", "TS-XX-980.md", "KD-XX-981.md"},
                         self._warned(out))
        self.assertIn("KAPSAM: FS/EK/TS/KD 5 tarandı (docs/ alt ağacı) · taranmayan tür yok", out)

    def test_parent_named_docs_does_not_widen_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            proje = os.path.join(tmp, "docs", "proje")
            _write(proje, "notlar/FS-XX-984.md", KIRLI)
            rc, out, _ = call_main(m.main, [proje, "--bulguda-exit1"])
        self.assertEqual(0, rc, out)
        self.assertIn("DENETLENECEK DOKÜMAN BULUNAMADI", out)

    def test_zero_scope_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _ = call_main(m.main, [tmp])
        self.assertEqual(0, rc)
        self.assertIn("DENETLENECEK DOKÜMAN BULUNAMADI", out)
        self.assertNotIn("SONUÇ: TEMİZ", out)
        self.assertIn("KAPSAM: FS/EK 0 tarandı", out)

    def test_clean_corpus_says_clean_with_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "docs/FS-XX-990.md", TEMIZ)
            rc, out, _ = call_main(m.main, [tmp, "--bulguda-exit1"])
        self.assertEqual(0, rc, out)
        self.assertIn("SONUÇ: TEMİZ — 1 doküman", out)
        self.assertIn("KAPSAM: FS/EK 1 tarandı", out)

    def test_unreadable_and_missing_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "docs/FS-XX-991.md", TEMIZ)
            with mock.patch.object(m, "_oku", side_effect=PermissionError("erişim yok")):
                rc, out, _ = call_main(m.main, [tmp])
            self.assertEqual(2, rc)
            self.assertIn("ÖLÇÜLEMEDİ", out)
            self.assertNotIn("SONUÇ: TEMİZ", out)
            rc, out, _ = call_main(m.main, [os.path.join(tmp, "yok.md")])
            self.assertEqual(2, rc)
            self.assertIn("yol yok", out)
            self.assertTrue(os.path.isfile(p))

    def test_bad_arguments_exit_2(self):
        for argv in (["--tur", "zz"], ["--tur", ""], ["--max-examples", "x"], ["--max-examples", "-1"]):
            with self.subTest(argv=argv):
                rc, _, _ = call_main(m.main, argv)
                self.assertEqual(2, rc)

    def test_selftest(self):
        rc, out, _ = call_main(m.main, ["--selftest"])
        self.assertEqual(0, rc, out)
        self.assertIn("[SELFTEST] OK", out)

    def test_subprocess_without_utf8_mode(self):
        """Türkçe okuma/yazma PYTHONUTF8 ve PYTHONIOENCODING olmadan da doğru (dosyalar utf-8 ile okunur)."""
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "FS-XX-992.md", KIRLI)
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_fs_no_analysis_log.py"), p,
                                "--bulguda-exit1"], capture_output=True, env=env, timeout=120)
        out = r.stdout.decode("utf-8")
        self.assertEqual(1, r.returncode, out + r.stderr.decode("utf-8", "replace"))
        self.assertIn("E önceden→şimdi", out)
        self.assertIn("artık kalem satırında gösterilmez", out)


DIRTY = "Fatura tipi ZM12'dir (DEV'de canlı ölçüldü)."


def _mini(govde):
    return "# FS-XX-1 — Örnek\n\n## 2. Giriş\n%s\n" % govde


def _link_dir(link, target):
    """Dizin bağlantısı: Windows'ta junction (yetki istemez), diğerlerinde symlink. Kurulamazsa False."""
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True)
        return r.returncode == 0 and os.path.isdir(link)
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except OSError:
        return False


class GateFindingTest(unittest.TestCase):
    """Bağımsız inceleme bulguları: ölçülemeyen yüzey 'temiz' denmez; bölüm/fence/kapsam kuralları."""

    # 1 — okunamayan alt klasör
    def test_unreadable_subdirectory_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "docs/FS-XX-1.md", _mini("Sipariş kaydedilir."))
            _write(tmp, "docs/kilitli/FS-XX-2.md", _mini(DIRTY))
            gercek = os.scandir

            def sahte(p=".", *a):
                if os.path.basename(os.fspath(p)) == "kilitli":
                    raise PermissionError(13, "erişim yok", os.fspath(p))
                return gercek(p, *a)

            with mock.patch("os.scandir", side_effect=sahte):
                rc, out, _ = call_main(m.main, [tmp])
        self.assertEqual(2, rc, out)
        self.assertIn("ÖLÇÜLEMEDİ", out)
        self.assertIn("kilitli", out)
        self.assertNotIn("SONUÇ: TEMİZ", out)

    # 2 — UTF-8 olmayan dosya
    def test_non_utf8_file_exit_2(self):
        for enc in ("utf-16", "cp1254"):
            with self.subTest(enc=enc), tempfile.TemporaryDirectory() as tmp:
                p = os.path.join(tmp, "FS-XX-3.md")
                with open(p, "wb") as fh:
                    fh.write(_mini(DIRTY + " Müşteri no artık gösterilmez.").encode(enc))
                rc, out, _ = call_main(m.main, [p, "--bulguda-exit1"])
                self.assertEqual(2, rc, out)
                self.assertIn("ÖLÇÜLEMEDİ", out)
                self.assertNotIn("SONUÇ: TEMİZ", out)

    # 3 — fence kuralları (CommonMark: aynı karakter, en az açılış uzunluğu, bilgi dizesiz kapanış)
    def test_fence_closing_rules(self):
        for blok in ("```\n~~~\n```", "````\n```\n````", "~~~\n```\n~~~", "```text\nx\n``` "):
            with self.subTest(blok=blok):
                self.assertEqual(1, _counts(_mini(blok + "\n" + DIRTY))[0][m.C])

    def test_unclosed_fence_is_not_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "FS-XX-4.md", _mini("```text\nörnek ekran\n\n## 3. Süreç\n" + DIRTY))
            rc, out, _ = call_main(m.main, [p, "--bulguda-exit1"])
        self.assertEqual(2, rc, out)
        self.assertIn("ÖLÇÜLEMEDİ", out)
        self.assertIn("kod bloğu", out)
        self.assertNotIn("SONUÇ: TEMİZ", out)

    # 4 — yalnız açık günlük başlıkları katman-2; miras yalnız onlarda
    def test_body_heading_with_decision_words_is_body(self):
        for baslik in ("## 4. Fonksiyonel gereksinimler ve karar önerileri\n### 4.1 Gereksinim listesi",
                       "### 4.2 Karar tablosu (açık durumlar)", "## 4. İş kuralları (11-B S-01 sonucu)"):
            with self.subTest(baslik=baslik):
                self.assertEqual(1, _counts("# FS-XX-5 — Örnek\n\n%s\n%s\n" % (baslik, DIRTY))[0][m.C])

    def test_explicit_log_headings_still_exempt(self):
        for baslik in ("## 11-A. Danışman önerileri", "## 11-B. Açık kararlar", "## BÖLÜM 11-B: AÇIK KARARLAR",
                       "## EK — Karar ve kanıt günlüğü\n### Yayılım tablosu", "## Açık kararlar",
                       "## 13. Karar günlüğü", "## 11-A. Build-time doğrulanacaklar (yalnız teknik teyit)"):
            with self.subTest(baslik=baslik):
                self.assertEqual(0, sum(_counts("# FS-XX-5 — Örnek\n\n%s\n%s\n" % (baslik, DIRTY))[0].values()))

    def test_version_section_children_are_body(self):
        text = ("# FS-XX-5 — Örnek\n\n## 1. Doküman kontrolü\n### 1.1 Versiyon geçmişi\n| Versiyon | Tarih |\n|---|---|\n\n"
                "#### 1.1.1 Not\nOnay v1.5'te eklendi.\n")
        self.assertEqual(1, _counts(text)[0][m.A])

    def test_ts_template_control(self):
        rc, out, _ = call_main(m.main, [os.path.join(TEMPLATES, "TS-template.md"), "--tur", "ts", "--bulguda-exit1"])
        self.assertEqual(0, rc, out)
        self.assertIn("SONUÇ: TEMİZ", out)

    # 5 — atlanan klasörler beyan edilir
    def test_skipped_directories_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "docs/archive/FS-XX-9.md", _mini(DIRTY))
            _write(tmp, "docs/tmp/FS-XX-10.md", _mini(DIRTY))
            _write(tmp, "docs/node_modules/paket.js", "x = 1\n")
            rc, out, _ = call_main(m.main, [tmp])
        self.assertEqual(0, rc, out)
        self.assertIn("ATLANAN KLASÖR", out)
        self.assertIn("docs/archive (FS 1)", out)
        self.assertIn("docs/tmp (FS 1)", out)
        self.assertIn("DENETLENECEK DOKÜMAN BULUNAMADI", out)

    # 6 — bağlantılar izlenmez
    def test_directory_links_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            proje, dis = os.path.join(tmp, "proje"), os.path.join(tmp, "dis")
            _write(proje, "docs/FS-XX-IN.md", _mini(DIRTY))
            _write(proje, "docs/alt/notlar.txt", "x\n")
            _write(dis, "docs/FS-XX-OUT.md", _mini(DIRTY))
            ext, loop = os.path.join(proje, "docs", "ext"), os.path.join(proje, "docs", "alt", "loop")
            if not (_link_dir(ext, os.path.join(dis, "docs")) and _link_dir(loop, os.path.join(proje, "docs"))):
                self.skipTest("dizin bağlantısı kurulamadı")
            try:
                rc, out, _ = call_main(m.main, [proje, "--bulguda-exit1"])
            finally:
                for link in (loop, ext):
                    try:
                        os.unlink(link) if os.path.islink(link) else os.rmdir(link)
                    except OSError:
                        pass
        self.assertEqual(1, rc, out)
        self.assertEqual(["FS-XX-IN.md"], [ln.split(": gövde")[0].replace("\\", "/").rsplit("/", 1)[-1]
                                           for ln in out.splitlines() if ln.startswith("[WARN] ")])
        self.assertIn("KAPSAM: FS/EK 1 tarandı", out)
        self.assertIn("BAĞLANTI", out)
        self.assertIn("docs/ext", out)
        self.assertIn("docs/alt/loop", out)

    # 7 — geri izleme patlaması yok
    def test_no_catastrophic_backtracking(self):
        import time
        for satir in ("|" + " " * 20000 + "x", "| " + "*" * 20000 + " x", "|" + " *" * 10000 + "|",
                      "| " + (".md" + " " * 50) * 400 + "x |"):
            with self.subTest(satir=satir[:12]):
                t0 = time.perf_counter()
                m.scan_text(_mini(satir))
                self.assertLess(time.perf_counter() - t0, 1.0)

    # 10 — kullanıcı alıntısı harf büyüklüğünden bağımsız (Türkçe ı/I dahil)
    def test_user_quote_case_insensitive(self):
        for satir in ('KULLANICI: "fiyat koşulu Z001"', "KULLANICI NOTU 17.08 ile netleşti.", 'Kullanici: "x"',
                      "kullanıcı kararı 17.08"):
            with self.subTest(satir=satir):
                self.assertEqual(1, _counts(_mini(satir))[0][m.D])
        for satir in ("KULLANICI İSTEĞİ K-1 gereği.", "Kullanıcı rolü: onaylayıcı."):
            with self.subTest(satir=satir):
                self.assertEqual(0, _counts(_mini(satir))[0][m.D])

    # 11 — başlık başı çapası ve çakışan kökler
    def test_section_number_prefix_anchor(self):
        for baslik in ("### 11.3 Hata", "### 11.1 Mesajlar", "### 21.3 Ek ekran"):
            with self.subTest(baslik=baslik):
                text = "# FS-XX-7 — Örnek\n\n## 5. Ekranlar\n%s\n| Buton | v1.5'te eklendi |\nMetin v1.6'da eklendi.\n" % baslik
                self.assertEqual(2, _counts(text)[0][m.A])

    def test_overlapping_roots_counted_once(self):
        # İki tekilleştirme katmanı var; her vektör birini TEK BAŞINA sınar (biri sökülünce diğeri örtmesin):
        # [kök, kök/docs, dosya] ikisi birlikte · [dosya, kök] yalnız dosya düzeyi · [kök, kök/docs] + atlanan klasör
        # beyanı yalnız klasör düzeyi (dosya düzeyi beyan satırlarını tekilleştirmez).
        with tempfile.TemporaryDirectory() as tmp:
            p = _write(tmp, "docs/FS-XX-11.md", _mini(DIRTY))
            _write(tmp, "docs/archive/FS-XX-12.md", _mini(DIRTY))
            docs = os.path.join(tmp, "docs")
            for argv in ([tmp, docs, p], [p, tmp]):
                with self.subTest(argv=len(argv)):
                    rc, out, _ = call_main(m.main, argv + ["--bulguda-exit1"])
                    self.assertEqual(1, rc, out)
                    self.assertEqual(1, sum(1 for ln in out.splitlines() if ln.startswith("[WARN] ")), out)
                    self.assertIn("SONUÇ: 1 işaretli satır (1 doküman)", out)
            _, out, _ = call_main(m.main, [tmp, docs])
            beyan = next(ln for ln in out.splitlines() if ln.startswith("KAPSAM: "))
            self.assertEqual(1, beyan.count("archive (FS 1)"), beyan)


class RegateFindingTest(unittest.TestCase):
    """İkinci inceleme turu: tekilleştirme yalnız TARANAN dosyayı kapsar; dosya kimliği; nitelikli TEMİZ; günlük başlıkları."""

    # 1 — walk'ta görülüp TARANMAYAN dosya doğrudan verilince sessizce düşmemeli (iki sıra)
    def test_unscanned_walked_file_given_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            disarida = _write(tmp, "FS-XX-1.md", _mini(DIRTY))           # docs/ dışı
            tur_disi = _write(tmp, "docs/TS-XX-2.md", _mini(DIRTY))      # varsayılan türde değil
            for dosya in (disarida, tur_disi):
                for argv in ([tmp, dosya], [dosya, tmp]):
                    with self.subTest(dosya=os.path.basename(dosya), sira=os.path.basename(argv[0])):
                        rc, out, _ = call_main(m.main, argv + ["--bulguda-exit1"])
                        self.assertEqual(1, rc, out)
                        self.assertEqual(1, sum(1 for ln in out.splitlines() if ln.startswith("[WARN] ")), out)
                        self.assertIn("doğrudan verilen dosya 1", out)
                        self.assertNotIn("BULUNAMADI", out)

    # 2 — harfe duyarlı klasörde FS-A.md ve fs-a.md AYRI dosyadır
    def test_case_sensitive_names_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = os.path.join(tmp, "docs")
            os.makedirs(docs)
            if os.name == "nt":
                subprocess.run(["fsutil", "file", "setCaseSensitiveInfo", docs, "enable"], capture_output=True)
            _write(tmp, "docs/FS-A.md", _mini("Sipariş kaydedilir."))
            _write(tmp, "docs/fs-a.md", _mini(DIRTY))
            if len(os.listdir(docs)) != 2:
                self.skipTest("bu dosya sisteminde harfe duyarlı klasör kurulamadı")
            rc, out, _ = call_main(m.main, [tmp, "--bulguda-exit1"])
        self.assertEqual(1, rc, out)
        self.assertIn("KAPSAM: FS/EK 2 tarandı", out)
        self.assertIn("fs-a.md", out)

    # 3 — atlanan klasör sayılamadıysa TEMİZ niteliksiz yazılmaz (çıkış kodu değişmez)
    def test_uncountable_skipped_folder_qualifies_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "docs/FS-XX-8.md", _mini("Sipariş kaydedilir."))
            _write(tmp, "docs/archive/sub/FS-XX-9.md", _mini(DIRTY))
            gercek = os.scandir

            def sahte(p=".", *a):
                if os.path.basename(os.fspath(p)) == "sub":
                    raise PermissionError(13, "erişim yok", os.fspath(p))
                return gercek(p, *a)

            with mock.patch("os.scandir", side_effect=sahte):
                rc, out, _ = call_main(m.main, [tmp, "--bulguda-exit1"])
        self.assertEqual(0, rc, out)
        self.assertIn("SONUÇ: TEMİZ (taranan kapsamda) — 1 atlanan klasör sayılamadı", out)
        self.assertNotIn("SONUÇ: TEMİZ —", out)

    # 5 — template/fs-authoring'in gerçekten yazdığı günlük başlığı biçimleri
    def test_log_heading_variants(self):
        gunluk = ["## §11-A Danışman Önerileri", "## §11-B Açık Kararlar", "## **11-B. Açık kararlar**",
                  "## 11B. Açık kararlar", "## EKLER", "## EKLER — Karar ve kanıt günlüğü",
                  "## EK — FS-SD-001 Sipariş onayı Karar ve Kanıt Günlüğü", "## Kararlar günlüğü",
                  "## Ek A: Karar ve kanıt günlüğü", "## 11-A. Danışman önerileri", "## EK — Karar ve kanıt günlüğü"]
        govde = ["## 4. Fonksiyonel gereksinimler ve karar önerileri", "## Ekran akışı ve karar günlüğü bağlantısı",
                 "## Ekler ve referanslar", "## Eklenen alanlar", "## 110-B Alan grubu"]
        for baslik in gunluk:
            with self.subTest(gunluk=baslik):
                self.assertEqual(0, sum(_counts("# FS-XX-5 — Örnek\n\n%s\n%s\n" % (baslik, DIRTY))[0].values()))
        for baslik in govde:
            with self.subTest(govde=baslik):
                self.assertEqual(1, _counts("# FS-XX-5 — Örnek\n\n%s\n%s\n" % (baslik, DIRTY))[0][m.C])

    def test_log_file_by_h1_variants(self):
        for h1 in ("# FS-SD-001 EK — Karar ve Kanıt Günlüğü", "# EK — FS-SD-001 (Sipariş onay ekranı) Karar ve Kanıt Günlüğü",
                   "# EK — Karar ve kanıt günlüğü", "# Karar ve Kanıt Günlüğü — FS-SD-001"):
            with self.subTest(h1=h1):
                self.assertEqual(0, sum(_counts("%s\n\n## K-22\n%s\n" % (h1, DIRTY))[0].values()))
        # Negatif kontrol: H1'de "karar önerileri" geçen FS gövdesi taranır.
        self.assertEqual(1, _counts("# FS-SD-001 — Karar önerileri formu\n\n## 2. Giriş\n%s\n" % DIRTY)[0][m.C])


if __name__ == "__main__":
    unittest.main()
