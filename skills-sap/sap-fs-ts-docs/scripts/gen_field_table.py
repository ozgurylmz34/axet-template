# -*- coding: utf-8 -*-
"""CDS (+ interface CDS + BDEF + CSV) → alan açıklama tablosu (Markdown).

Amaç: TS §4.5 (a) alan tablosu ve KD Bölüm 6 alan rehberi için elle yazılan tabloları CDS kaynağından üretmek
(doğruluk kaynağı = CDS annotation'ı; ekran görüntüsünden okuma değil).

Çıkarılan bilgi (öncelik sırasıyla):
  - Alan adı         : CDS eleman adı (alias varsa alias)
  - Anahtar          : `key` öneki
  - Etiket           : @UI.lineItem label → @EndUserText.label → projeksiyon kaynağı CDS'teki aynı eleman → CSV açıklaması
  - Filtre           : @UI.selectionField var mı; @Consumption.filter mandatory:true → (zorunlu)
  - Değer yardımı    : @Consumption.valueHelpDefinition entity.name
  - Düzenlenebilir   : kardeş BDEF `field ( readonly … ) A, B;` → Hayır

Sınır: "oluşturmada zorunlu" CDS'ten kesin çıkmaz; etiketi çözülemeyen alan işaretlenir, uydurulmaz.

Kullanım:
    python gen_field_table.py <cds_dosyası> [--ref-csv alanlar.csv] [-o cikti.md]
Desteklenen uzantılar: .cds · .asddls · .ddls.asddls (BDEF: .bdef · .asbdef · .bdef.asbdef)
Çıkış: 0 başarılı · 2 okunamayan girdi.
"""
import argparse
import csv
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCOPE = ("KAPSAM (SCOPE): gen_field_table — CDS eleman listesi, etiket annotation'ları, filtre/değer yardımı, BDEF readonly. "
         "Bakılmayanlar: ifade/cast alanları (alias'sız), association alanları, oluşturmada zorunluluk, çalışma zamanı "
         "özellik kontrolü (feature control), etiketin sistemdeki DTEL metniyle aynılığı.")

CDS_EXTS = (".ddls.asddls", ".asddls", ".cds")
BDEF_EXTS = (".bdef.asbdef", ".asbdef", ".bdef")


def _stem(path):
    low = path.lower()
    for ext in CDS_EXTS + BDEF_EXTS:
        if low.endswith(ext):
            return path[: -len(ext)]
    return os.path.splitext(path)[0]


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _body(text):
    """define … entity NAME … { BODY } → (ad, projeksiyon_kaynağı, gövde).

    Gövde `{` araması define ifadesinden SONRA başlar; yoksa başlık annotation'larındaki `{` gövde sanılır.
    """
    m = re.search(r"define\s+(?:root\s+)?(?:view\s+entity|view|abstract\s+entity|custom\s+entity)\s+(\w+)", text, re.I)
    name = m.group(1) if m else "?"
    start = m.end() if m else 0
    pm = re.search(r"as\s+projection\s+on\s+(\w+)", text[start:], re.I)
    proj = pm.group(1) if pm else None
    if pm:
        start += pm.end()
    bi = text.find("{", start)
    if bi < 0:
        return name, proj, ""
    depth = 0
    for i in range(bi, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return name, proj, text[bi + 1:i]
    return name, proj, text[bi + 1:]


def _label_from_annots(annots):
    m = re.search(r"@UI\.lineItem\s*:\s*\[\s*\{[^\]]*?label\s*:\s*'([^']+)'", annots, re.S)
    if m:
        return m.group(1)
    m = re.search(r"@EndUserText\.label\s*:\s*'([^']+)'", annots)
    return m.group(1) if m else None


def _read(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return fh.read()
    except OSError as exc:
        raise FileNotFoundError("%s: %s" % (path, exc))


def parse_cds(path):
    """Döner: (entity_adı, projeksiyon_kaynağı, [alan sözlüğü]). Association/redirect satırları atlanır."""
    name, proj, body = _body(_strip_comments(_read(path)))
    fields, annots = [], []
    for raw in body.split("\n"):
        line = raw.strip().rstrip(",").strip()
        if not line:
            continue
        if line.startswith("@"):
            annots.append(line)
            continue
        if annots and line.endswith(("]", "}", ")")) and not re.match(r"^(key\s+)?[A-Za-z_]\w*\s*(:|,|$)", line):
            annots[-1] += " " + line
            continue
        if re.match(r"^_\w+\s*:", line) or "redirected to" in line or " composition " in line:
            annots = []
            continue
        m = re.match(r"^(key\s+)?([A-Za-z_][\w.]*)(?:\s+as\s+(\w+))?\s*$", line, re.I)
        if not m:
            annots = []
            continue
        elem = m.group(3) or m.group(2).split(".")[-1]
        if elem.startswith("_"):
            annots = []
            continue
        ann = "\n".join(annots)
        vh = re.search(r"valueHelpDefinition[^\]]*?entity\s*:\s*\{\s*name\s*:\s*'([^']+)'", ann, re.S)
        fields.append({
            "name": elem,
            "key": bool(m.group(1)),
            "label": _label_from_annots(ann),
            "filter": "@UI.selectionField" in ann,
            "mandatory": bool(re.search(r"mandatory\s*:\s*true", ann)),
            "vh": vh.group(1) if vh else None,
        })
        annots = []
    return name, proj, fields


def parse_bdef_readonly(stem):
    """`<stem>` + BDEF uzantısı → readonly alan adları kümesi (dosya yoksa boş)."""
    ro = set()
    for ext in BDEF_EXTS:
        p = stem + ext
        if os.path.exists(p):
            txt = _strip_comments(_read(p))
            for m in re.finditer(r"field\s*\(\s*readonly[^)]*\)\s*([^;]+);", txt, re.I):
                ro.update(f.strip() for f in m.group(1).split(",") if f.strip())
            break
    return ro


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_csv_labels(csv_path):
    """CSV (field_name|name + description|medium|long) → {normalize(ad): açıklama}."""
    out = {}
    if not csv_path:
        return out
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = row.get("field_name") or row.get("name") or ""
            desc = row.get("description") or row.get("medium") or row.get("long") or ""
            if key and desc:
                out[_norm(key)] = desc.strip()
    return out


def _sibling_cds(folder, entity):
    for ext in CDS_EXTS:
        for cand in (entity + ext, entity.lower() + ext):
            p = os.path.join(folder, cand)
            if os.path.exists(p):
                return p
    return None


def build_table(path, ref_csv=None):
    name, proj, fields = parse_cds(path)
    folder = os.path.dirname(os.path.abspath(path))
    iface_labels = {}
    ro = parse_bdef_readonly(_stem(path))
    if proj:
        ipath = _sibling_cds(folder, proj)
        if ipath:
            _, _, ifields = parse_cds(ipath)
            iface_labels = {f["name"]: f["label"] for f in ifields if f["label"]}
            ro |= parse_bdef_readonly(_stem(ipath))
    csv_labels = load_csv_labels(ref_csv)

    rows, unresolved = [], []
    for f in fields:
        label = f["label"] or iface_labels.get(f["name"]) or csv_labels.get(_norm(f["name"])) or ""
        if not label:
            unresolved.append(f["name"])
            label = "_(etiket kaynakta yok)_"
        rows.append("| {nm} | {lb} | {k} | {flt} | {vh} | {ed} |".format(
            nm=f["name"], lb=label, k="Evet" if f["key"] else "",
            flt=("Evet" + (" (zorunlu)" if f["mandatory"] else "")) if f["filter"] else "",
            vh=f["vh"] or "", ed="Hayır" if f["name"] in ro else "Evet"))

    md = ["### Alan tablosu — `%s`%s" % (name, (" (projeksiyon kaynağı: `%s`)" % proj) if proj else ""), "",
          "> `gen_field_table.py` ile üretildi. Etiketler CDS annotation'ından, düzenlenebilirlik BDEF readonly'den. "
          "\"Oluşturmada zorunlu\" CDS'ten kesin çıkmaz; elle gözden geçir.", "",
          "| Alan | Etiket | Anahtar | Filtre | Değer yardımı | Düzenlenebilir |",
          "|---|---|---|---|---|---|"]
    md.extend(rows)
    md.append("")
    md.append("_%d alan; %d salt okunur._%s" % (
        len(fields), len(ro & {f["name"] for f in fields}),
        (" Etiketsiz: " + ", ".join(unresolved)) if unresolved else ""))
    return "\n".join(md), unresolved


def main(argv):
    ap = argparse.ArgumentParser(description="CDS → alan tablosu")
    ap.add_argument("cds")
    ap.add_argument("--ref-csv", default=None)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    print(SCOPE, file=sys.stderr if not a.out else sys.stdout)
    try:
        out, unresolved = build_table(a.cds, a.ref_csv)
    except FileNotFoundError as exc:
        print("HATA: okunamadı: %s" % exc, file=sys.stderr)
        return 2
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        print("OK →", a.out, "| etiketsiz:", len(unresolved))
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
