# -*- coding: utf-8 -*-
"""sap-ui5-user-guide skill yapısı: frontmatter, açıklama uzunluğu, atıf yapılan dosyaların varlığı, iz taraması.

Kendi kendine yeter (ortak `_common.py`'ye bağlı değildir): `python test_skill_structure.py` ya da
`python -m unittest discover -s <skill>/tests -t <skill>/tests`. SAP'ye, ağa, tarayıcıya bağlanmaz.

KAPSAM (SCOPE) — bakılanlar: SKILL.md frontmatter'ı (yerel kurallar + doctor.frontmatter_problems) · skill içindeki
Markdown dosyalarında geçen `references/…`, `templates/…`, `scripts/…`, `$S/…`, `$D/…` atıflarının diskte varlığı ·
`%skill` bağlantıları · Markdown tablolarında hücre sayısı · müşteri/kişi izi, dış URL, e-posta.
BAKILMAYANLAR: script'lerin davranışı (kendi testleri) · komutların gerçekten çalışması · atıf yapılan bölüm
numaralarının (§A, §E) hedef dosyada var olması · metnin doğruluğu.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SKILL_NAME = os.path.basename(SKILL)
REPO = os.path.dirname(os.path.dirname(SKILL))
SKILL_GROUPS = ("skills-sap", "skills")

# Bu skill'in KENDİ script'leri başka iş şeritlerinde yazılır; birleşmeden önce bu ağaçta olmayabilirler.
OWN_SCRIPTS_NOTE = ("bu skill'in scripts/ klasöründe yok. kd_ortam.py (ARAÇ şeridi) ve mock_veri.py (MOCK şeridi) "
                    "birleşmeden önce bu test KIRMIZI kalır — beklenen durum; birleşmeden SONRA kırmızıysa gerçek eksiktir")

TEXT_EXT = (".md", ".py", ".js", ".json", ".yaml", ".yml", ".txt")
PATH_RX = re.compile(r"(?<![\w<>/$.-])((?:references|templates|scripts|tests)/[\w.-]+\.(?:md|py|js|json))")
FULL_RX = re.compile(r"skills(?:-sap)?/([\w-]+)/((?:references|templates|scripts)/[\w.-]+\.(?:md|py|js|json))")
ALIAS_RX = re.compile(r"\$([SD])/([\w.-]+\.(?:py|js))")
SKILL_LINK_RX = re.compile(r"%([a-z][a-z0-9]*(?:-[a-z0-9]+)+)")
ALIASES = {"S": SKILL_NAME, "D": "sap-fs-ts-docs"}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _md_files():
    for root, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.lower().endswith(".md"):
                yield os.path.join(root, f)


def _text_files():
    for root, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.lower().endswith(TEXT_EXT):
                yield os.path.join(root, f)


def _skill_dir(name):
    for group in SKILL_GROUPS:
        d = os.path.join(REPO, group, name)
        if os.path.isfile(os.path.join(d, "SKILL.md")):
            return d
    return None


def _all_skill_names():
    names = set()
    for group in SKILL_GROUPS:
        base = os.path.join(REPO, group)
        if os.path.isdir(base):
            names |= {d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "SKILL.md"))}
    return names


def _frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    return m.group(1) if m else None


def description_of(text):
    fm = _frontmatter(text)
    if fm is None:
        return None
    m = re.search(r"(?ms)^description: >\s*\n((?:[ \t]+\S.*\n?)+)", fm + "\n")
    if not m:
        return None
    return " ".join(l.strip() for l in m.group(1).splitlines() if l.strip())


def resolve_refs(text):
    """Metindeki dosya atıflarını (satır, atıf, çözülen skill adı) olarak döndürür.

    Kural: aynı satırda atıftan ÖNCE bir `%skill` geçiyorsa atıf o skill'e aittir (`%sap-fs-ts-docs` →
    `references/kd-authoring.md`); geçmiyorsa bu skill'e. `$S/x` bu skill'in, `$D/x` sap-fs-ts-docs'un scripts/'i.
    """
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        for m in PATH_RX.finditer(line):
            owners = SKILL_LINK_RX.findall(line[:m.start()])
            out.append((no, m.group(1), owners[-1] if owners else SKILL_NAME))
        for m in FULL_RX.finditer(line):
            out.append((no, m.group(2), m.group(1)))
        for m in ALIAS_RX.finditer(line):
            out.append((no, "scripts/" + m.group(2), ALIASES[m.group(1)]))
    return out


class SkillStructureTest(unittest.TestCase):
    def setUp(self):
        self.skill_md = _read(os.path.join(SKILL, "SKILL.md"))

    def test_frontmatter_local_rules(self):
        fm = _frontmatter(self.skill_md)
        self.assertIsNotNone(fm, "frontmatter yok")
        self.assertRegex(fm, r"(?m)^name: %s$" % re.escape(SKILL_NAME), "name klasör adıyla aynı olmalı")
        desc = description_of(self.skill_md)
        self.assertIsNotNone(desc, "description '>' katlanmış blok olmalı")
        # aXet 1024'ü aşan açıklamalı skill'i SESSİZCE yüklemez (ölçüldü); ≤ 900 hedef, pay bırakır.
        self.assertLessEqual(len(desc), 1024, "description %d karakter — aXet sınırı 1024" % len(desc))
        self.assertLessEqual(len(desc), 900, "description %d karakter (hedef ≤ 900)" % len(desc))
        self.assertGreater(len(desc), 200, "description tetikleyemeyecek kadar kısa")
        self.assertIn("Triggers:", desc)
        for line in fm.splitlines():
            if line and not line[0].isspace():
                _, _, value = line.partition(":")
                v = value.strip()
                self.assertNotIn(": ", "" if v == ">" else v, "tırnaksız ': ' YAML'ı bozar — %s" % line)

    def test_frontmatter_doctor(self):
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        try:
            import doctor  # noqa: WPS433
            problems_fn = doctor.frontmatter_problems
        except Exception as exc:  # doctor içe aktarılamıyorsa yerel kural testi yine koşar
            self.skipTest("doctor.frontmatter_problems içe aktarılamadı: %s" % exc)
        finally:
            sys.path.pop(0)
        self.assertEqual([], problems_fn(self.skill_md))

    def test_reference_table_rows_exist(self):
        """'Önce oku' tablosunun ilk sütunundaki her dosya var (kendi skill'i ya da `%skill →` ile gösterilen)."""
        m = re.search(r"(?m)^## Önce oku[^\n]*\n((?:\|[^\n]*\n)+)", self.skill_md)
        self.assertIsNotNone(m, "SKILL.md'de '## Önce oku' tablosu yok")
        rows = [r for r in m.group(1).splitlines()[2:] if r.strip()]
        self.assertGreaterEqual(len(rows), 5)
        missing, own_missing = [], []
        for row in rows:
            first = row.split("|")[1]
            refs = resolve_refs(first)
            self.assertTrue(refs, "tablo satırında dosya atfı yok: %s" % row)
            for _, path, owner in refs:
                base = _skill_dir(owner)
                if base is None or not os.path.isfile(os.path.join(base, path)):
                    (own_missing if owner == SKILL_NAME and path.startswith("scripts/") else missing).append(
                        "%s → %s" % (owner, path))
        self.assertEqual([], missing, "önce-oku tablosunda olmayan dosya")
        self.assertEqual([], own_missing, "; ".join(own_missing) + " — " + OWN_SCRIPTS_NOTE)

    def test_referenced_docs_exist(self):
        """Tüm Markdown'larda references/ ve templates/ atıfları çözülüyor (script'ler ayrı testte)."""
        missing = []
        for path in _md_files():
            for no, ref, owner in resolve_refs(_read(path)):
                if ref.startswith(("scripts/", "tests/")):
                    continue
                base = _skill_dir(owner)
                if base is None or not os.path.isfile(os.path.join(base, ref)):
                    missing.append("%s:%d → %s/%s" % (os.path.relpath(path, SKILL), no, owner, ref))
        self.assertEqual([], missing)

    def test_referenced_scripts_exist(self):
        """SKILL.md ve referanslarda adı geçen scripts/ dosyaları var. Başka skill'inkiler hemen, bu skill'inkiler
        diğer iş şeritleri birleşince yeşile döner (mesaj hangisinin eksik olduğunu söyler)."""
        other, own = [], []
        for path in _md_files():
            for no, ref, owner in resolve_refs(_read(path)):
                if not ref.startswith("scripts/"):
                    continue
                base = _skill_dir(owner)
                if base is None or not os.path.isfile(os.path.join(base, ref)):
                    where = "%s:%d → %s/%s" % (os.path.relpath(path, SKILL), no, owner, ref)
                    (own if owner == SKILL_NAME else other).append(where)
        self.assertEqual([], other, "başka skill'in script'i yok")
        self.assertEqual([], sorted(set(own)), OWN_SCRIPTS_NOTE)

    def test_skill_links_exist(self):
        names = _all_skill_names()
        bad = []
        for path in _md_files():
            for m in SKILL_LINK_RX.finditer(_read(path)):
                if m.group(1) not in names:
                    bad.append("%s → %%%s" % (os.path.relpath(path, SKILL), m.group(1)))
        self.assertEqual([], bad)

    def test_markdown_tables_consistent(self):
        """Tablo satırı başlıkla aynı sayıda hücre taşır (kod içindeki `|` tabloyu sessizce bozar)."""
        bad = []
        for path in _md_files():
            lines = _read(path).splitlines()
            in_code, header_cells = False, None
            for no, line in enumerate(lines, 1):
                if line.lstrip().startswith("```"):
                    in_code = not in_code
                    continue
                s = line.strip()
                if in_code or not (s.startswith("|") and s.endswith("|")):
                    header_cells = None
                    continue
                cells = len(re.sub(r"\\\|", "", s).split("|")) - 2
                if header_cells is None:
                    header_cells = cells
                elif cells != header_cells:
                    bad.append("%s:%d: %d hücre (başlık %d)" % (os.path.relpath(path, SKILL), no, cells, header_cells))
        self.assertEqual([], bad)

    def test_trace_grep_clean(self):
        forbidden = ["C:" + "\\" + "IX", "C:/" + "IX", "DEV" + "_CORE", "mcp" + "__", "." + "claude",
                     "CLAUDE" + ".md", "ZSD" + "0", "FIT" + "_SE", "ZSD" + "_ONAY", "ADR " + "00", "Claude" + " Code",
                     "PRO" + "VA", "AppData" + "\\" + "Local" + "\\" + "Temp"]
        url = re.compile(r"https?://(?!localhost[:/]|127\.0\.0\.1[:/]|example\.invalid[/\"])")
        email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}\b")
        hits = []
        for path in _text_files():
            with open(path, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    rel = os.path.relpath(path, SKILL)
                    if os.path.abspath(path) == os.path.abspath(__file__):
                        continue  # desen listesinin kendisi
                    hits += ["%s:%d: %s" % (rel, i, f) for f in forbidden if f in line]
                    if url.search(line):
                        hits.append("%s:%d: url" % (rel, i))
                    if email.search(line):
                        hits.append("%s:%d: e-posta" % (rel, i))
        self.assertEqual([], hits)


class ResolveRefsSelfTest(unittest.TestCase):
    """Çözücünün kendisi: yanlış çözerse yukarıdaki testler sessizce yanlış yere bakar."""

    def test_owner_rules(self):
        refs = resolve_refs("`%sap-fs-ts-docs` → `references/kd-authoring.md` ve `$S/kd_ortam.py`, `$D/build_kd_pdf.py`\n"
                            "`references/akis.md`")
        self.assertEqual([(1, "references/kd-authoring.md", "sap-fs-ts-docs"),
                          (1, "scripts/kd_ortam.py", SKILL_NAME),
                          (1, "scripts/build_kd_pdf.py", "sap-fs-ts-docs"),
                          (2, "references/akis.md", SKILL_NAME)], refs)

    def test_full_paths(self):
        self.assertEqual([(1, "scripts/a.py", "sap-x")],
                         resolve_refs("<TEMPLATE>/skills-sap/sap-x/scripts/a.py · node_modules/.bin/scripts/b.js"))


if __name__ == "__main__":
    unittest.main()
