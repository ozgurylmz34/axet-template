#!/usr/bin/env python3
"""xlsx_lite — yalnız standart kütüphaneyle .xlsx okuma ve yazma (office-excel skill'inin çekirdeği).

Okuma: paylaşılan metin, satır içi metin, sayı, mantıksal, hata ve formülün önbellekteki sonucu. Tarih biçimli
sayı hücreleri ISO metne çevrilir (yerleşik tarih biçim numaraları + özel biçim kodu). 1904 tarih sistemi desteklenir.
Yazma: satır içi metin + sayı + mantıksal; kalın/dolgulu başlık, dondurulmuş başlık satırı, otomatik filtre,
kolon genişliği.
Kapsam dışı: hücre biçimlerini okuma, birleştirilmiş hücre, grafik, pivot; formül yeniden hesaplanmaz
(dosyada önbellek değeri yoksa hücre boş gelir).
"""
from __future__ import annotations

import datetime as _dt
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
M = "{%s}" % NS_MAIN
R = "{%s}" % NS_REL
P = "{%s}" % NS_PKG

BUILTIN_DATE_FMTS = set(range(14, 23)) | {45, 46, 47}
_REF = re.compile(r"^([A-Z]+)(\d+)$")
_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SHEET_BAD = re.compile(r"[\[\]:*?/\\]")
REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"


class XlsxError(Exception):
    """Dosya .xlsx olarak okunamadı ya da istenen sayfa yok."""


def col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def col_letters(index: int) -> str:
    index += 1
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def _resolve(base_dir: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    stack: list[str] = []
    for part in (base_dir + "/" + target).split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if stack:
                stack.pop()
        else:
            stack.append(part)
    return "/".join(stack)


def part_rels(zf: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    """Bir paket parçasının ilişkileri: {Id: (hedef parça yolu, ilişki tipi)}. Dış hedefler atlanır."""
    base, _, name = part.rpartition("/")
    rels_path = f"{base}/_rels/{name}.rels" if base else f"_rels/{name}.rels"
    try:
        root = ET.fromstring(zf.read(rels_path))
    except KeyError:
        return {}
    out = {}
    for rel in root.iter(P + "Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        out[rel.get("Id")] = (_resolve(base, rel.get("Target", "")), rel.get("Type", ""))
    return out


def open_zip(path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise XlsxError(f"{Path(path).name}: geçerli bir .xlsx (zip) değil — eski .xls ya da bozuk dosya olabilir") from None


def workbook_part(zf: zipfile.ZipFile) -> str:
    for target, typ in part_rels(zf, "").values():
        if typ.endswith("/officeDocument"):
            return target
    return "xl/workbook.xml"


def sheet_parts(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """[(sayfa adı, sayfa parça yolu)] çalışma kitabındaki sırayla."""
    wb = workbook_part(zf)
    try:
        root = ET.fromstring(zf.read(wb))
    except KeyError:
        raise XlsxError("çalışma kitabı parçası yok (xl/workbook.xml)") from None
    rels = part_rels(zf, wb)
    out = []
    for sheet in root.iter(M + "sheet"):
        target = rels.get(sheet.get(R + "id"), (None, ""))
        if target[0] and target[1].endswith("/worksheet"):
            out.append((sheet.get("name", ""), target[0]))
    return out


def list_sheets(path) -> list[str]:
    with open_zip(path) as zf:
        return [name for name, _ in sheet_parts(zf)]


def _node_text(node) -> str:
    """<si>/<is> içindeki metin: düz <t> ya da zengin metin parçaları (<r><t>); fonetik (<rPh>) hariç."""
    parts = []
    for child in node:
        if child.tag == M + "t":
            parts.append(child.text or "")
        elif child.tag == M + "r":
            t = child.find(M + "t")
            parts.append(t.text or "" if t is not None else "")
    return "".join(parts)


def _is_date_code(code: str) -> bool:
    cleaned = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code).lower()
    return bool(re.search(r"[dmyhs]", cleaned))


def _date_styles(zf: zipfile.ZipFile, styles_part: str | None) -> set[int]:
    if not styles_part:
        return set()
    try:
        root = ET.fromstring(zf.read(styles_part))
    except KeyError:
        return set()
    custom = {int(n.get("numFmtId", "0")): n.get("formatCode", "") for n in root.iter(M + "numFmt")}
    xfs = root.find(M + "cellXfs")
    out: set[int] = set()
    if xfs is None:
        return out
    for i, xf in enumerate(xfs.findall(M + "xf")):
        fid = int(xf.get("numFmtId", "0"))
        if fid in BUILTIN_DATE_FMTS or (fid in custom and _is_date_code(custom[fid])):
            out.add(i)
    return out


def serial_to_iso(value: float, date1904: bool = False) -> str:
    base = _dt.datetime(1904, 1, 1) if date1904 else _dt.datetime(1899, 12, 30)
    moment = base + _dt.timedelta(seconds=round(value * 86400))
    if moment.time() == _dt.time(0, 0):
        return moment.date().isoformat()
    return moment.isoformat(sep=" ")


def _number(text: str):
    f = float(text)
    if f.is_integer() and abs(f) < 1e15:
        return int(f)
    return f


def read_rows(path, sheet: str | None = None) -> tuple[str, list[list]]:
    """(sayfa adı, satırlar). `sheet`: sayfa adı ya da 1'den başlayan sıra no; verilmezse ilk sayfa.
    Satırlar dosyadaki konumlarını korur: aradaki boş satırlar `[]`, boş hücreler `None`."""
    with open_zip(path) as zf:
        sheets = sheet_parts(zf)
        if not sheets:
            raise XlsxError("çalışma kitabında sayfa yok")
        chosen = None
        if sheet in (None, ""):
            chosen = sheets[0]
        else:
            chosen = next((s for s in sheets if s[0] == sheet), None)
            if chosen is None and str(sheet).isdigit() and 1 <= int(sheet) <= len(sheets):
                chosen = sheets[int(sheet) - 1]
        if chosen is None:
            raise XlsxError(f"sayfa yok: {sheet!r} · sayfalar: {', '.join(s[0] for s in sheets)}")
        wb = workbook_part(zf)
        wb_root = ET.fromstring(zf.read(wb))
        pr = wb_root.find(M + "workbookPr")
        date1904 = pr is not None and pr.get("date1904", "").lower() in ("1", "true")
        wb_rels = part_rels(zf, wb).values()
        shared_part = next((t for t, typ in wb_rels if typ.endswith("/sharedStrings")), None)
        styles_part = next((t for t, typ in wb_rels if typ.endswith("/styles")), None)
        shared: list[str] = []
        if shared_part:
            try:
                shared = [_node_text(si) for si in ET.fromstring(zf.read(shared_part)).iter(M + "si")]
            except KeyError:
                shared = []
        date_styles = _date_styles(zf, styles_part)

        rows: list[list] = []
        with zf.open(chosen[1]) as fh:
            for _event, el in ET.iterparse(fh):
                if el.tag != M + "row":
                    continue
                r_attr = el.get("r")
                row_no = int(r_attr) if r_attr and r_attr.isdigit() else len(rows) + 1
                while len(rows) < row_no - 1:
                    rows.append([])
                values: list = []
                for c in el.findall(M + "c"):
                    ref = c.get("r", "")
                    m = _REF.match(ref)
                    idx = col_index(m.group(1)) if m else len(values)
                    t = c.get("t", "n")
                    v = c.find(M + "v")
                    text = v.text if v is not None else None
                    if t == "s":
                        val = shared[int(text)] if text is not None and int(text) < len(shared) else None
                    elif t == "inlineStr":
                        node = c.find(M + "is")
                        val = _node_text(node) if node is not None else None
                    elif t == "b":
                        val = None if text is None else text.strip() in ("1", "true")
                    elif t in ("str", "e", "d"):
                        val = text
                    else:
                        if text is None or text == "":
                            val = None
                        else:
                            try:
                                val = _number(text)
                            except ValueError:
                                val = text
                            if isinstance(val, (int, float)) and int(c.get("s", "0")) in date_styles:
                                val = serial_to_iso(float(val), date1904)
                    while len(values) < idx:
                        values.append(None)
                    if len(values) == idx:
                        values.append(val)
                    else:
                        values[idx] = val
                while values and values[-1] is None:
                    values.pop()
                rows.append(values)
                el.clear()
        while rows and not rows[-1]:
            rows.pop()
        return chosen[0], rows


# ── yazma ─────────────────────────────────────────────────────────────────────────────────────────

def safe_sheet_name(name: str, used: set[str]) -> tuple[str, str | None]:
    """Excel sayfa adı kuralı: en fazla 31 karakter, []:*?/\\ yok, benzersiz. (ad, uyarı|None)"""
    original = name
    name = _SHEET_BAD.sub("_", name or "Sayfa").strip("'") or "Sayfa"
    name = name[:31]
    base, n = name, 2
    while name.lower() in used:
        suffix = f"_{n}"
        name = base[:31 - len(suffix)] + suffix
        n += 1
    used.add(name.lower())
    return name, (None if name == original else f"sayfa adı {original!r} → {name!r} (Excel kuralı)")


def _cell_xml(ref: str, value, style: int) -> str:
    s_attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{ref}"{s_attr}/>' if style else ""
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{s_attr}><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)) and value == value and value not in (float("inf"), float("-inf")):
        return f'<c r="{ref}"{s_attr}><v>{value!r}</v></c>'
    if isinstance(value, (_dt.datetime, _dt.date)):
        value = value.isoformat()
    text = _XML_ILLEGAL.sub("", str(value))
    return f'<c r="{ref}" t="inlineStr"{s_attr}><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def _sheet_xml(rows: list[list], header: bool, freeze: bool, autofilter: bool) -> str:
    width = max((len(r) for r in rows), default=0)
    height = len(rows)
    last = f"{col_letters(max(width, 1) - 1)}{max(height, 1)}"
    out = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">',
           f'<dimension ref="A1:{last}"/>', '<sheetViews><sheetView workbookViewId="0">']
    if freeze and header and height > 1:
        out.append('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>')
    out.append('</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/>')
    if width:
        out.append("<cols>")
        for j in range(width):
            longest = max((len(str(r[j])) for r in rows if j < len(r) and r[j] is not None), default=0)
            out.append(f'<col min="{j + 1}" max="{j + 1}" width="{min(max(longest + 2, 8), 60)}" customWidth="1"/>')
        out.append("</cols>")
    out.append("<sheetData>")
    for i, row in enumerate(rows):
        style = 1 if header and i == 0 else 0
        cells = "".join(_cell_xml(f"{col_letters(j)}{i + 1}", v, style) for j, v in enumerate(row))
        out.append(f'<row r="{i + 1}">{cells}</row>')
    out.append("</sheetData>")
    if autofilter and header and width and height > 1:
        out.append(f'<autoFilter ref="A1:{last}"/>')
    out.append("</worksheet>")
    return "".join(out)


_STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<styleSheet xmlns="{NS_MAIN}">'
           '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
           '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
           '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
           '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill></fills>'
           '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
           '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
           '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
           '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>'
           '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def write_xlsx(path, sheets: list[tuple[str, list[list]]], *, header: bool = True, freeze: bool = True,
               autofilter: bool = True) -> list[str]:
    """Sayfaları .xlsx olarak yazar. `sheets`: [(ad, satırlar)] — ilk satır başlık (header=True iken).
    Dönüş: uyarılar (ör. düzeltilen sayfa adı)."""
    if not sheets:
        raise ValueError("en az bir sayfa gerekli")
    used: set[str] = set()
    warnings, names = [], []
    for name, _rows in sheets:
        safe, warn = safe_sheet_name(name, used)
        names.append(safe)
        if warn:
            warnings.append(warn)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    wb_sheets, wb_rels, defined = [], [], []
    for i, (name, (_n, rows)) in enumerate(zip(names, sheets), start=1):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        wb_sheets.append(f'<sheet name="{escape(name, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>')
        wb_rels.append(f'<Relationship Id="rId{i}" Type="{REL_TYPE}worksheet" Target="worksheets/sheet{i}.xml"/>')
        width = max((len(r) for r in rows), default=0)
        if autofilter and header and width and len(rows) > 1:
            quoted = name.replace("'", "''")
            defined.append(f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i - 1}" hidden="1">'
                           f"{escape(chr(39) + quoted + chr(39))}!$A$1:${col_letters(width - 1)}${len(rows)}</definedName>")
    ct.append("</Types>")
    wb_rels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="{REL_TYPE}styles" Target="styles.xml"/>')
    workbook = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">'
                f'<sheets>{"".join(wb_sheets)}</sheets>'
                + (f'<definedNames>{"".join(defined)}</definedNames>' if defined else "") + "</workbook>")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "".join(ct))
        zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                    f'<Relationships xmlns="{NS_PKG}"><Relationship Id="rId1" Type="{REL_TYPE}officeDocument" '
                    'Target="xl/workbook.xml"/></Relationships>')
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                    f'<Relationships xmlns="{NS_PKG}">{"".join(wb_rels)}</Relationships>')
        zf.writestr("xl/styles.xml", _STYLES)
        for i, (_name, rows) in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows, header, freeze, autofilter))
    return warnings
