# -*- coding: utf-8 -*-
"""sap-pdf-output skill yapısı: frontmatter, açıklama uzunluğu, satır sınırı, atıf yapılan dosyaların varlığı, iz taraması.

Model: sap-ui5-user-guide/tests/test_skill_structure.py. Kendi kendine yeter; SAP'ye, ağa bağlanmaz.

KAPSAM (SCOPE) — bakılanlar: SKILL.md frontmatter'ı (yerel kurallar + doctor.frontmatter_problems) · SKILL.md ≤ 150 satır ·
skill içindeki Markdown dosyalarında geçen `references/…`, `templates/…`, `scripts/…`, `$S/…`, `$T/…` atıflarının diskte
varlığı · `%skill` bağlantıları · Markdown tablolarında hücre sayısı · kontrol listesinin AF-005 + AF-XDP-01..07'yi eksiksiz
taşıması · müşteri/kişi izi, dış URL, e-posta.
BAKILMAYANLAR: script'lerin davranışı (kendi testleri) · atıf yapılan bölüm BAŞLIKLARININ hedef dosyada var olması ·
şablonların SAP'de derlenmesi/render edilmesi · metnin doğruluğu.
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

TEXT_EXT = (".md", ".py", ".js", ".json", ".yaml", ".yml", ".txt", ".xdp", ".xml", ".abap")
_EXT = r"(?:md|py|js|json|xdp|xml|abap)"
PATH_RX = re.compile(r"(?<![\w<>/$.-])((?:references|templates|scripts|tests)/[\w.-]+\.%s)\b" % _EXT)
FULL_RX = re.compile(r"skills(?:-sap)?/([\w-]+)/((?:references|templates|scripts)/[\w.-]+\.%s)\b" % _EXT)
ALIAS_RX = re.compile(r"\$([ST])/([\w.-]+\.%s)\b" % _EXT)
SKILL_LINK_RX = re.compile(r"%([a-z][a-z0-9]*(?:-[a-z0-9]+)+)")
ALIASES = {"S": ("scripts/", SKILL_NAME), "T": ("templates/", SKILL_NAME)}

# XML ad alanı kimlikleri (XDP şablonunun zorunlu parçası) adres değildir, iz sayılmaz — yalnız bu iki önek.
NS_ALLOW = r"ns\.adobe\.com/xdp/|www\.xfa\.org/schema/"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _walk(ext):
    for root, dirs, files in os.walk(SKILL):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.lower().endswith(ext):
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
    """(satır, atıf, sahip skill) listesi. Aynı satırda atıftan ÖNCE `%skill` geçiyorsa atıf o skill'indir."""
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        for m in PATH_RX.finditer(line):
            owners = SKILL_LINK_RX.findall(line[:m.start()])
            out.append((no, m.group(1), owners[-1] if owners else SKILL_NAME))
        for m in FULL_RX.finditer(line):
            out.append((no, m.group(2), m.group(1)))
        for m in ALIAS_RX.finditer(line):
            klasor, sahip = ALIASES[m.group(1)]
            out.append((no, klasor + m.group(2), sahip))
    return out


def url_rx():
    return re.compile(r"https?://(?!localhost[:/]|127\.0\.0\.1[:/]|example\.invalid[/\"]|(?:%s))" % NS_ALLOW)


class SkillStructureTest(unittest.TestCase):
    def setUp(self):
        self.skill_md = _read(os.path.join(SKILL, "SKILL.md"))

    def test_frontmatter_local_rules(self):
        fm = _frontmatter(self.skill_md)
        self.assertIsNotNone(fm, "frontmatter yok")
        self.assertRegex(fm, r"(?m)^name: %s$" % re.escape(SKILL_NAME), "name klasör adıyla aynı olmalı")
        desc = description_of(self.skill_md)
        self.assertIsNotNone(desc, "description '>' katlanmış blok olmalı")
        self.assertLessEqual(len(desc), 900, "description %d karakter (hedef ≤ 900; aXet sınırı 1024)" % len(desc))
        self.assertGreater(len(desc), 200, "description tetikleyemeyecek kadar kısa")
        self.assertIn("Triggers:", desc)
        for tetik in ("PDF üret", "PDF mail eki", "form olmadan PDF", "XDP", "toplu", "sevk belgesi PDF"):
            self.assertIn(tetik, desc)
        for line in fm.splitlines():
            if line and not line[0].isspace():
                _, _, value = line.partition(":")
                v = value.strip()
                self.assertNotIn(": ", "" if v == ">" else v, "tırnaksız ': ' YAML'ı bozar — %s" % line)

    def test_skill_md_line_limit(self):
        self.assertLessEqual(len(self.skill_md.splitlines()), 150)

    def test_frontmatter_doctor(self):
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        try:
            import doctor  # noqa: WPS433
            problems_fn = doctor.frontmatter_problems
        except Exception as exc:
            self.skipTest("doctor.frontmatter_problems içe aktarılamadı: %s" % exc)
        finally:
            sys.path.pop(0)
        self.assertEqual([], problems_fn(self.skill_md))

    def test_reference_table_rows_exist(self):
        m = re.search(r"(?m)^## Önce oku[^\n]*\n((?:\|[^\n]*\n)+)", self.skill_md)
        self.assertIsNotNone(m, "SKILL.md'de '## Önce oku' tablosu yok")
        rows = [r for r in m.group(1).splitlines()[2:] if r.strip()]
        self.assertGreaterEqual(len(rows), 5)
        missing = []
        for row in rows:
            refs = resolve_refs(row.split("|")[1])
            self.assertTrue(refs, "tablo satırında dosya atfı yok: %s" % row)
            for _, path, owner in refs:
                base = _skill_dir(owner)
                if base is None or not os.path.isfile(os.path.join(base, path)):
                    missing.append("%s → %s" % (owner, path))
        self.assertEqual([], missing)

    def test_referenced_files_exist(self):
        missing = []
        for path in _walk(".md"):
            for no, ref, owner in resolve_refs(_read(path)):
                base = _skill_dir(owner)
                if base is None or not os.path.isfile(os.path.join(base, ref)):
                    missing.append("%s:%d → %s/%s" % (os.path.relpath(path, SKILL), no, owner, ref))
        self.assertEqual([], missing)

    def test_every_script_and_template_is_referenced(self):
        """Diskteki her script/şablon SKILL.md'de anılır (anılmayan dosya akışta kullanılmaz)."""
        anilan = {ref for _, ref, owner in resolve_refs(self.skill_md) if owner == SKILL_NAME}
        disk = {"scripts/" + f for f in os.listdir(os.path.join(SKILL, "scripts"))
                if f.endswith(".py") and not f.startswith("_")}
        disk |= {"templates/" + f for f in os.listdir(os.path.join(SKILL, "templates"))}
        self.assertEqual([], sorted(disk - anilan))

    def test_skill_links_exist(self):
        names = _all_skill_names()
        bad = []
        for path in _walk(".md"):
            for m in SKILL_LINK_RX.finditer(_read(path)):
                if m.group(1) not in names:
                    bad.append("%s → %%%s" % (os.path.relpath(path, SKILL), m.group(1)))
        self.assertEqual([], bad)

    def test_markdown_tables_consistent(self):
        bad = []
        for path in _walk(".md"):
            in_code, header_cells = False, None
            for no, line in enumerate(_read(path).splitlines(), 1):
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

    def test_checklist_complete(self):
        """AF-005 + AF-XDP-01..07 bu skill'de TEK yerde ve eksiksiz (sap-classic-abap bu satırları almaz)."""
        metin = _read(os.path.join(SKILL, "references", "kontrol-listesi.md"))
        satirlar = re.findall(r"(?m)^\| (AF-[\w-]+) \|", metin)
        beklenen = ["AF-005"] + ["AF-XDP-%02d" % i for i in range(1, 8)]
        self.assertEqual(beklenen, satirlar)
        for sev in ("BLOCKER", "WARNING"):
            self.assertIn(sev, metin)

    def test_mail_default_off_in_trial_template(self):
        abap = _read(os.path.join(SKILL, "templates", "deneme-classrun.clas.abap"))
        self.assertRegex(abap, r"(?i)CONSTANTS gc_mail_acik\s+TYPE abap_bool\s+VALUE abap_false\.")
        self.assertRegex(abap, r"(?i)CONSTANTS gc_test_alici\s+TYPE string\s+VALUE ``\.")
        self.assertIn("embed_fonts = abap_true", abap)

    def test_trace_grep_clean(self):
        forbidden = ["C:" + "\\" + "IX", "C:/" + "IX", "DEV" + "_CORE", "mcp" + "__", "." + "claude",
                     "CLAUDE" + ".md", "ZSD" + "0", "FIT" + "_SE", "ZSD" + "_ONAY", "ADR " + "00", "Claude" + " Code",
                     "PRO" + "VA", "AppData" + "\\" + "Local" + "\\" + "Temp", "howto-" + "pdf"]
        url = url_rx()
        # Kalibrasyon: istisna yalnız iki ad alanı öneki; benzeyen başka adresler iz sayılır.
        for iz in ("https://ns.adobe.com.corp.local/x", "http://www.xfa.org.example/x", "https://sap.example/",
                   "http://ns.adobe.com/other/"):
            self.assertIsNotNone(url.search(iz), iz)
        for temiz in ('xmlns:xdp="http://ns.adobe.com/xdp/"', 'xmlns="http://www.xfa.org/schema/xfa-template/3.3/"',
                      "http://127.0.0.1:8080/"):
            self.assertIsNone(url.search(temiz), temiz)
        email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}\b")
        hits = []
        for path in _walk(TEXT_EXT):
            if os.path.abspath(path) == os.path.abspath(__file__):
                continue  # desen listesinin kendisi
            with open(path, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    rel = os.path.relpath(path, SKILL)
                    hits += ["%s:%d: %s" % (rel, i, f) for f in forbidden if f in line]
                    if url.search(line):
                        hits.append("%s:%d: url" % (rel, i))
                    if email.search(line):
                        hits.append("%s:%d: e-posta" % (rel, i))
        self.assertEqual([], hits)


class ResolveRefsSelfTest(unittest.TestCase):
    """Çözücünün kendisi: yanlış çözerse yukarıdaki testler sessizce yanlış yere bakar."""

    def test_owner_rules(self):
        refs = resolve_refs("`%sap-rap` → `references/behavior-impl.md` ve `$S/pdf_coz.py`, `$T/tek-belge.xdp`\n"
                            "`references/recete.md` `templates/deneme-classrun.clas.abap`")
        self.assertEqual([(1, "references/behavior-impl.md", "sap-rap"),
                          (1, "scripts/pdf_coz.py", SKILL_NAME),
                          (1, "templates/tek-belge.xdp", SKILL_NAME),
                          (2, "references/recete.md", SKILL_NAME),
                          (2, "templates/deneme-classrun.clas.abap", SKILL_NAME)], refs)

    def test_missing_ref_detected(self):
        """Doğru-negatif değil doğru-pozitif: var olmayan atıf çözülür ve diskte bulunmaz."""
        refs = resolve_refs("`references/yok-boyle-bir-dosya.md`")
        self.assertEqual(1, len(refs))
        self.assertFalse(os.path.isfile(os.path.join(SKILL, refs[0][1])))


if __name__ == "__main__":
    unittest.main()
