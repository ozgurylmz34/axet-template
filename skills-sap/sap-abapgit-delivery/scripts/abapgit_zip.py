#!/usr/bin/env python3
"""abapgit_zip.py — abapGit çevrimdışı (offline) ZIP teslimi: aç · denetle · paketle · SAP dönüşünü kaydet.

Model SAP'ye yazmaz. Akış:
  1. Geliştirici SAP'de abapGit ile paketi ZIP olarak dışa aktarır  →  `unpack` çalışma alanına açar (taban çizgisi).
  2. Model çalışma alanındaki abapGit dosyalarını düzenler.
  3. `check` / `pack` Kesin Yasak A-B-C-D denetimlerinden geçirip içe aktarma ZIP'i üretir (FAIL varsa ZIP YOK).
  4. Geliştirici ZIP'i SAP'de abapGit ile içe aktarır (pull), aktivasyon/hata çıktısını verir → `status-in` saklar.

Kullanım:
  python abapgit_zip.py unpack EXPORT.zip --root WS [--force]
  python abapgit_zip.py check  --root WS (--files F [F ...] | --all) [--project-dir P] [--main-language-letter X]
                               [--subpackages-exist] [--max-baseline-days 7] [--json]
  python abapgit_zip.py pack   --root WS (--files ... | --all) [aynı seçenekler] [--out Z.zip] [-m NOT] [--list] [--force]
  python abapgit_zip.py status-in DOSYA(.txt/.log/.json/.xml/.md/.csv/.yaml/.zip) --root WS [--label ETIKET]
Çıkış: 0 tamam · 1 hata (dosya/format) · 2 RED (denetim FAIL ya da güvensiz ZIP) · 3 kullanım hatası.
Yalnız standart kütüphane. Kesin Yasak B taraması sap-adt-foundation içindeki tarayıcıyı kullanır; bulunamazsa RED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

DOT_ABAPGIT = ".abapgit.xml"
BASELINE = ".abapgit-baseline.json"
MANIFEST = ".axet-abapgit-manifest.json"
STATUS_DIR = ".abapgit-status"
DIST_DIR = "dist"
LANG_LETTER = {"EN": "E", "TR": "T"}  # E: docs.abapgit.org · T: foundation T100 örneği (sprsl = 'T')
LARGE_SELECTION = 20
TEXT_EXT = {".txt", ".log", ".json", ".xml", ".md", ".csv", ".yaml", ".yml"}
SCANNER_DIR = Path(__file__).resolve().parents[2] / "sap-adt-foundation" / "scripts"

_NAME = re.compile(r"^(?P<obj>[^.]+)\.(?P<type>[a-z0-9]{4})(?:\.(?P<part>[^/]+?))?\.(?P<ext>[a-z0-9]+)$")
_CUSTOMER = re.compile(r"^[ZY][A-Z0-9_]*$", re.IGNORECASE)
_LOCK = re.compile(r"^E[ZY][A-Z0-9_]*$", re.IGNORECASE)
_NS_XML = re.compile(r"^#(?P<ns>[^#]+)#(?P<rest>.+)$")
_NS_JSON = re.compile(r"^\((?P<ns>[^)]+)\)(?P<rest>.+)$")
_TEXT_TAGS = ("DDTEXT", "DESCRIPT")
_DTEL_LABELS = ("REPTEXT", "SCRTEXT_S", "SCRTEXT_M", "SCRTEXT_L")  # DD04V alan adları: DOĞRULANMADI (repo kanıtı yok)
_LANG_TAGS = ("LANGU", "DDLANGUAGE", "MASTERLANG")


class UsageError(Exception):
    pass


class Deny(Exception):
    pass


# ── yardımcılar ─────────────────────────────────────────────────────────────────────────────────────
def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def stamp() -> str:
    return now_utc().strftime("%Y%m%dT%H%M%SZ")


def is_binary(data: bytes) -> bool:
    return b"\x00" in data


def normalized(data: bytes) -> bytes:
    return data if is_binary(data) else data.replace(b"\r\n", b"\n")


def digest(data: bytes) -> str:
    return hashlib.sha256(normalized(data)).hexdigest()


def safe_member(name: str) -> PurePosixPath:
    """ZIP üyesini güvenli göreli yola çevirir; mutlak, sürücü harfli ya da `..` içeren yolu reddeder (zip-slip)."""
    raw = name.replace("\\", "/")
    p = PurePosixPath(raw)
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or any(part == ".." for part in p.parts):
        raise Deny(f"güvensiz ZIP üyesi yolu: {name!r}")
    return p


def read_xml_value(xml: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
    return None if m is None else m.group(1).strip()


def dot_abapgit(root: Path) -> dict:
    path = root / DOT_ABAPGIT
    if not path.is_file():
        return {}
    xml = path.read_text(encoding="utf-8", errors="replace")
    start = read_xml_value(xml, "STARTING_FOLDER") or "/src/"
    return {"MASTER_LANGUAGE": read_xml_value(xml, "MASTER_LANGUAGE"), "STARTING_FOLDER": start,
            "FOLDER_LOGIC": read_xml_value(xml, "FOLDER_LOGIC")}


def start_prefix(start: str) -> str:
    s = start.strip().strip("/")
    return f"{s}/" if s else ""


def load_baseline(root: Path) -> dict:
    path = root / BASELINE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"{BASELINE} okunamadı: {exc}") from None


def project_language(project_dir: str | None) -> tuple[str | None, str]:
    """sap-project.json → master_language (yalnız bu alan okunur)."""
    if not project_dir:
        return None, "--project-dir verilmedi"
    path = Path(project_dir) / "sap-project.json"
    if not path.is_file():
        return None, f"{path} yok"
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("master_language")
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path} okunamadı: {exc}"
    if not isinstance(value, str) or not value.strip() or value.strip().startswith("<"):
        return None, "sap-project.json master_language doldurulmamış"
    return value.strip().upper(), str(path)


def parse_name(rel: str) -> dict | None:
    """`<obje>.<tip>[.<parça>].<uzantı>` → sözlük; eşleşmezse None. Namespace: XML `#ns#`, JSON `(ns)`."""
    base = rel.rsplit("/", 1)[-1]
    m = _NAME.match(base.lower())
    if not m:
        return None
    original_obj = base[: len(m.group("obj"))]
    ns = None
    for rx in (_NS_XML, _NS_JSON):
        nm = rx.match(original_obj)
        if nm:
            ns, original_obj = nm.group("ns"), nm.group("rest")
            break
    return {"object": original_obj, "namespace": ns, "type": m.group("type"), "part": m.group("part"),
            "ext": m.group("ext"), "stem": base[: len(base.split(".")[0])] + "." + m.group("type")}


def customer_object(info: dict) -> bool:
    if info["namespace"] is not None:
        return info["namespace"].upper()[:1] in ("Z", "Y")
    name = info["object"]
    return bool(_CUSTOMER.match(name) or (info["type"] == "enqu" and _LOCK.match(name)))


def load_scanner():
    """Kesin Yasak B tarayıcısı (sap-adt-foundation). Yüklenemezse None → çağıran RED verir (fail-closed)."""
    if not (SCANNER_DIR / "sapadt" / "std_dml_scan.py").is_file():
        return None
    if str(SCANNER_DIR) not in sys.path:
        sys.path.insert(0, str(SCANNER_DIR))
    try:
        from sapadt.std_dml_scan import mesaj, tara  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    return tara, mesaj


# ── seçim ──────────────────────────────────────────────────────────────────────────────────────────
def workspace_files(root: Path) -> list[str]:
    skip_top = {DIST_DIR, STATUS_DIR, ".git"}
    out = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.split("/", 1)[0] in skip_top or rel in (BASELINE, MANIFEST):
            continue
        out.append(rel)
    return sorted(out)


def select(root: Path, files: list[str] | None, all_changed: bool, baseline: dict, prefix: str) -> tuple[list[str], list[dict]]:
    findings: list[dict] = []
    present = workspace_files(root)
    base_files = baseline.get("files", {})
    if all_changed:
        chosen = [r for r in present if r != DOT_ABAPGIT and r.startswith(prefix)
                  and base_files.get(r) != digest((root / r).read_bytes())]
    else:
        chosen = []
        for f in files or []:
            p = Path(f)
            rel = (p.resolve().relative_to(root.resolve()) if p.is_absolute() else PurePosixPath(f.replace("\\", "/"))).as_posix()
            if any(ch in rel for ch in "*?["):
                matched = [r for r in present if fnmatch.fnmatch(r, rel)]
                if not matched:
                    raise UsageError(f"eşleşen dosya yok: {f}")
                chosen.extend(matched)
            elif (root / rel).is_file():
                chosen.append(rel)
            else:
                raise UsageError(f"dosya yok: {f}")
    stems = {}
    for rel in chosen:
        info = parse_name(rel)
        if info:
            stems.setdefault((rel.rsplit("/", 1)[0] if "/" in rel else "", info["stem"].lower()), set()).add(rel)
    expanded = set(chosen)
    for (folder, stem), members in stems.items():
        for r in present:
            if (r.rsplit("/", 1)[0] if "/" in r else "") == folder and r.rsplit("/", 1)[-1].lower().startswith(stem + "."):
                if r not in expanded:
                    expanded.add(r)
                    findings.append({"level": "INFO", "code": "object_siblings_added", "file": r,
                                     "message": "abapGit nesne düzeyinde çalışır: aynı nesnenin diğer dosyası eklendi"})
    for rel, digest_value in base_files.items():
        if rel.startswith(prefix) and not (root / rel).is_file():
            findings.append({"level": "WARN", "code": "deleted_locally", "file": rel,
                             "message": "taban çizgisinde var, çalışma alanında yok: ZIP içe aktarımı silme yapmayabilir "
                                        "(DOĞRULANMADI) — silme SAP'de geliştirici tarafından yapılır"})
    return sorted(r for r in expanded if r != DOT_ABAPGIT), findings


# ── denetim ─────────────────────────────────────────────────────────────────────────────────────────
def check(root: Path, a) -> tuple[list[str], list[dict], dict]:
    findings: list[dict] = []

    def add(level: str, code: str, message: str, file: str | None = None) -> None:
        findings.append({"level": level, "code": code, "file": file, "message": message})

    meta = dot_abapgit(root)
    if not meta:
        add("FAIL", "dot_abapgit_missing", f"{DOT_ABAPGIT} yok: önce SAP'den alınan ZIP'i `unpack` ile aç")
        return [], findings, meta
    prefix = start_prefix(meta["STARTING_FOLDER"])
    baseline = load_baseline(root)
    selected, sel_findings = select(root, a.files, a.all, baseline, prefix)
    findings.extend(sel_findings)
    if not selected:
        add("FAIL", "empty_selection", "paketlenecek dosya yok (--all: taban çizgisine göre değişiklik yok)")

    # D — dil
    ml, ml_source = project_language(a.project_dir)
    repo_letter = (meta.get("MASTER_LANGUAGE") or "").upper() or None
    expected_letter = (a.main_language_letter or "").upper() or (LANG_LETTER.get(ml) if ml else None)
    if ml and not expected_letter:
        add("WARN", "language_unverified",
            f"master_language={ml} için tek harfli SAP dil kodu bu araçta kayıtlı değil → --main-language-letter ver")
    elif not ml and not a.main_language_letter:
        add("WARN", "language_unverified", f"proje dili bilinmiyor ({ml_source}) → --project-dir ya da --main-language-letter")
    if expected_letter and repo_letter and repo_letter != expected_letter:
        add("FAIL", "language_mismatch",
            f"{DOT_ABAPGIT} MASTER_LANGUAGE={repo_letter}, proje ana dili {ml or '?'} → beklenen {expected_letter} "
            "(abapGit nesnenin ana dilini değiştiremez)", DOT_ABAPGIT)

    baseline_dirs = {r.rsplit("/", 1)[0] for r in baseline.get("files", {}) if "/" in r}
    if not baseline:
        add("WARN", "baseline_missing", f"{BASELINE} yok: değişiklik/alt paket karşılaştırması yapılamadı "
            "(SAP'den güncel ZIP'i `unpack` ile açmak önerilir)")
    else:
        try:
            taken = dt.datetime.fromisoformat(baseline.get("created_utc", ""))
            age = (now_utc() - taken).days
            if age > a.max_baseline_days:
                add("WARN", "baseline_stale", f"taban çizgisi {age} günlük: SAP'deki güncel hâli yeniden dışa aktar "
                    "(başkasının değişikliği ezilebilir)")
        except ValueError:
            add("WARN", "baseline_stale", "taban çizgisi tarihi okunamadı")
    if len(selected) > LARGE_SELECTION:
        add("WARN", "large_selection", f"{len(selected)} dosya seçildi: teslimi küçük parçalara bölmeyi düşün")

    scanner = None
    scanner_loaded = False
    present = set(workspace_files(root))
    siblings = {f["file"] for f in sel_findings if f["code"] == "object_siblings_added"}
    for rel in selected:
        data = (root / rel).read_bytes()
        if baseline and rel not in siblings and baseline.get("files", {}).get(rel) == digest(data):
            add("WARN", "unchanged_selected", "taban çizgisine göre değişmemiş", rel)
        if not rel.startswith(prefix):
            add("FAIL", "outside_starting_folder", f"STARTING_FOLDER {meta['STARTING_FOLDER']} dışında: abapGit yok sayar", rel)
            continue
        base = rel.rsplit("/", 1)[-1]
        info = parse_name(rel)
        if info is None:
            add("FAIL", "name_pattern", "dosya adı `<nesne>.<tip>[.<parça>].<uzantı>` kalıbına uymuyor", rel)
            continue
        if base != base.lower() and info["namespace"] is None:
            add("WARN", "uppercase_filename", "abapGit dosya adları küçük harf üretir: SAP'den gelen adla karşılaştır", rel)
        if info["type"] == "devc":
            add("FAIL", "ADR_0005_C_package", "paket tanımı (DEVC) teslime konamaz: paket yaratma/değiştirme Kesin Yasak C", rel)
            continue
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        if baseline and folder and folder not in baseline_dirs and not a.subpackages_exist:
            add("FAIL", "ADR_0005_C_subpackage",
                f"yeni klasör {folder}/: abapGit içe aktarırken alt paket yaratır (Kesin Yasak C). Paket SAP'de "
                "geliştirici tarafından açıldıysa --subpackages-exist ile tekrar dene", rel)
        if not customer_object(info):
            add("FAIL", "ADR_0005_A", f"{info['object'].upper()} müşteri ad alanında değil (Z/Y; kilit nesnesi EZ/EY; "
                "/Z…/ ya da /Y…/): standart nesne değiştirilemez", rel)
            continue
        stem_meta = [f"{base.split('.')[0]}.{info['type']}.xml", f"{base.split('.')[0]}.{info['type']}.json"]
        if not any(f"{folder + '/' if folder else ''}{m}" in present for m in stem_meta):
            add("FAIL", "metadata_missing", f"nesnenin meta dosyası yok ({' ya da '.join(stem_meta)}): abapGit içe "
                "aktaramaz. Aynı tipte mevcut bir nesnenin meta dosyasını örnek al; alan uydurma", rel)
        if baseline and rel not in baseline.get("files", {}) and info["ext"] in ("xml", "json") and not info["part"]:
            add("INFO", "new_object", "yeni nesne: meta dosyasını SAP'den dışa aktarılmış aynı tip bir nesneden kopyala, "
                "metinleri projenin ana dilinde TAM doldur", rel)
        if not is_binary(data) and b"\r\n" in data:
            add("INFO", "crlf_converted", "CRLF → LF çevrilecek (abapGit yalnız LF kabul eder)", rel)
        text = data.decode("utf-8", errors="replace")
        if info["ext"] == "abap":
            if not scanner_loaded:
                scanner, scanner_loaded = load_scanner(), True
            if scanner is None:
                add("FAIL", "std_dml_scan_unavailable", f"Kesin Yasak B tarayıcısı yüklenemedi ({SCANNER_DIR}): "
                    "tarama yapılmadan teslim üretilmez", rel)
            else:
                tara, mesaj = scanner
                # object_type=None: tarayıcı tip bilgisiyle taramayı atlayabilir; .abap dosyası daima taranır (fail-closed)
                hits = tara(text, None)
                if hits:
                    add("FAIL", "ADR_0005_B", mesaj(hits), rel)
        elif info["ext"] == "xml":
            for tag in _TEXT_TAGS:
                if re.search(rf"<{tag}>\s*</{tag}>|<{tag}\s*/>", text):
                    add("FAIL", "ADR_0005_D_text", f"<{tag}> boş: başlık/açıklama boş bırakılamaz (Kesin Yasak D)", rel)
                    break
            if info["type"] == "dtel":
                present_labels = {t: read_xml_value(text, t) for t in _DTEL_LABELS if re.search(rf"<{t}[\s>/]", text)}
                if not present_labels:
                    add("WARN", "ADR_0005_D_labels_unverified",
                        f"DTEL etiket alanı bulunamadı ({', '.join(_DTEL_LABELS)}): dört etiketi SAP'de doğrula", rel)
                else:
                    missing = [t for t in _DTEL_LABELS if not present_labels.get(t)]
                    if missing:
                        add("FAIL", "ADR_0005_D_text", f"DTEL etiketleri eksik/boş: {', '.join(missing)} — dört etiket "
                            "(kısa/orta/uzun/başlık) projenin dilinde TAM yazılır (Kesin Yasak D)", rel)
            for tag in _LANG_TAGS:
                value = read_xml_value(text, tag)
                if value and expected_letter and value.upper() != expected_letter:
                    add("FAIL", "ADR_0005_D_language", f"<{tag}>{value}</{tag}> proje dili {expected_letter} ile uyuşmuyor", rel)
                    break
    return selected, findings, meta


SCOPE = ("KAPSAM — bakılanlar: .abapgit.xml varlığı ve dili · başlangıç klasörü · dosya adı kalıbı · DEVC/yeni alt klasör (C) · "
         "Z/Y ad alanı (A) · meta dosyası varlığı · .abap kaynağında standart tabloya doğrudan yazım (B, foundation "
         "tarayıcısı) · XML'de boş DDTEXT/DESCRIPT, DTEL dört etiket, LANGU/DDLANGUAGE/MASTERLANG (D) · taban çizgisi "
         "yaşı/değişiklik.\nBAKILMAYANLAR: ABAP sözdizimi ve aktivasyon · XML şemasının abapGit sürümüne uygunluğu · "
         "bağımlı nesnelerin varlığı · SAP'deki güncel sürümle çakışma (yalnız taban çizgisi yaşı) · transport · "
         "yetki · standart nesneye örtük değişiklik (ör. enhancement içeriği) · JSON (AFF) biçimli nesnelerde metin/dil.")


def report(findings: list[dict], selected: list[str], as_json: bool) -> int:
    fails = [f for f in findings if f["level"] == "FAIL"]
    if as_json:
        print(json.dumps({"selected": selected, "findings": findings, "verdict": "DENY" if fails else "OK", "scope": SCOPE},
                         ensure_ascii=False, indent=2))
    else:
        print(f"Seçilen dosya: {len(selected)}")
        for rel in selected:
            print(f"  {rel}")
        for f in findings:
            where = f" [{f['file']}]" if f.get("file") else ""
            print(f"{f['level']} {f['code']}{where}: {f['message']}")
        print(SCOPE)
        print(f"SONUÇ: {'RED — ' + str(len(fails)) + ' FAIL' if fails else 'GEÇTİ'}")
    return 2 if fails else 0


# ── komutlar ────────────────────────────────────────────────────────────────────────────────────────
def cmd_unpack(a) -> int:
    root = Path(a.root)
    src = Path(a.zip)
    if not src.is_file():
        raise UsageError(f"ZIP yok: {src}")
    try:
        zf = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        print(f"HATA: geçerli ZIP değil: {src}", file=sys.stderr)
        return 1
    with zf:
        members = [(i, safe_member(i.filename)) for i in zf.infolist() if not i.is_dir()]  # önce hepsini doğrula
        names = {p.as_posix() for _, p in members}
        if DOT_ABAPGIT not in names:
            print(f"HATA: ZIP kökünde {DOT_ABAPGIT} yok: abapGit dışa aktarımı değil", file=sys.stderr)
            return 1
        xml = zf.read(DOT_ABAPGIT).decode("utf-8", errors="replace")
        prefix = start_prefix(read_xml_value(xml, "STARTING_FOLDER") or "/src/")
        wanted = [(i, p) for i, p in members if p.as_posix() == DOT_ABAPGIT or p.as_posix().startswith(prefix)]
        skipped = len(members) - len(wanted)
        old = load_baseline(root).get("files", {}) if root.exists() else {}
        conflicts = []
        for _, p in wanted:
            target = root / p.as_posix()
            if target.is_file():
                current = digest(target.read_bytes())
                if old.get(p.as_posix()) != current:
                    conflicts.append(p.as_posix())
        if conflicts and not a.force:
            print("RED: çalışma alanında taban çizgisinden farklı (yerel değişiklikli) dosyalar var; üzerine yazılmadı:",
                  file=sys.stderr)
            for c in conflicts[:20]:
                print(f"  {c}", file=sys.stderr)
            print("Önce değişiklikleri teslim et ya da bilerek ezmek için --force.", file=sys.stderr)
            return 2
        files = {}
        for info, p in wanted:
            data = zf.read(info)
            target = root / p.as_posix()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[p.as_posix()] = digest(data)
    (root / BASELINE).write_text(json.dumps({"source_zip": src.name, "created_utc": now_utc().isoformat(timespec="seconds"),
                                             "files": files}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"açıldı: {len(files)} dosya → {root} · taban çizgisi {BASELINE}")
    if skipped:
        print(f"NOT: başlangıç klasörü ({prefix or '/'}) dışındaki {skipped} dosya alınmadı")
    if conflicts:
        print(f"UYARI: {len(conflicts)} yerel değişiklik --force ile ezildi")
    return 0


def cmd_check(a) -> int:
    root = Path(a.root)
    if not root.is_dir():
        raise UsageError(f"çalışma alanı yok: {root}")
    selected, findings, _ = check(root, a)
    return report(findings, selected, a.json)


def cmd_pack(a) -> int:
    root = Path(a.root)
    if not root.is_dir():
        raise UsageError(f"çalışma alanı yok: {root}")
    selected, findings, meta = check(root, a)
    code = report(findings, selected, a.json)
    if code:
        print("ZIP üretilmedi (FAIL giderilmeli).", file=sys.stderr)
        return code
    out = Path(a.out) if a.out else root / DIST_DIR / f"{root.resolve().name}-{stamp()}.zip"
    if out.exists() and not a.force:
        raise UsageError(f"çıktı zaten var: {out} (--force)")
    out.parent.mkdir(parents=True, exist_ok=True)
    converted = 0
    manifest = {"created_utc": now_utc().isoformat(timespec="seconds"), "note": a.message or "",
                "starting_folder": meta.get("STARTING_FOLDER"), "master_language": meta.get("MASTER_LANGUAGE"),
                "files": {}, "warnings": [f"{f['code']}: {f.get('file') or ''}" for f in findings if f["level"] == "WARN"]}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(DOT_ABAPGIT, normalized((root / DOT_ABAPGIT).read_bytes()))
        for rel in selected:
            raw = (root / rel).read_bytes()
            data = normalized(raw)
            converted += data != raw
            zf.writestr(rel, data)
            manifest["files"][rel] = hashlib.sha256(data).hexdigest()
        zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"ZIP: {out} · {len(selected)} dosya · CRLF→LF {converted}")
    if a.list:
        for rel in selected:
            print(f"  {rel}")
    print("Geliştirici adımları (SAP GUI, abapGit):\n"
          "  1. abapGit → çevrimdışı repoyu aç (yoksa New Offline; mevcut paketi seç — paket yaratma).\n"
          "  2. Import zip → bu dosyayı seç → Pull zip; istenirse kendi transport'unu seç.\n"
          "  3. Aktivasyon sonucunu/hata listesini metin olarak kaydet ve modele ver (`status-in`).\n"
          "  4. Silinmesi gereken nesneler varsa ZIP bunları silmez: SAP'de elle.")
    return 0


def cmd_status_in(a) -> int:
    root = Path(a.root)
    src = Path(a.artifact)
    if not src.is_file():
        raise UsageError(f"dosya yok: {src}")
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", a.label or "sap").strip("-") or "sap"
    dest = root / STATUS_DIR
    saved = []
    ts = stamp()

    def store(name: str, data: bytes) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / f"{ts}-{label}-{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)}"
        target.write_bytes(data)
        saved.append(target)

    if src.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(src) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    p = safe_member(info.filename)
                    if p.parts and p.parts[0] == "src" or Path(p.name).suffix.lower() not in TEXT_EXT:
                        continue
                    store(p.as_posix().replace("/", "_"), zf.read(info))
        except zipfile.BadZipFile:
            print(f"HATA: geçerli ZIP değil: {src}", file=sys.stderr)
            return 1
    elif src.suffix.lower() in TEXT_EXT:
        store(src.name, src.read_bytes())
    else:
        raise UsageError(f"desteklenmeyen dosya türü {src.suffix!r}: {', '.join(sorted(TEXT_EXT))} ya da .zip")
    if not saved:
        print("UYARI: saklanacak metin dosyası bulunamadı (ZIP içinde src/ dışında metin yok)")
        return 1
    for s in saved:
        print(f"saklandı: {s}")
    print("Sonraki adım: kaydı oku, hata satırlarını ilgili dosyalara eşle; düzeltmeyi yeniden `pack` ile teslim et.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="abapGit çevrimdışı ZIP teslimi (model SAP'ye yazmaz)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("unpack", help="SAP'den dışa aktarılan ZIP'i çalışma alanına aç")
    u.add_argument("zip")
    u.add_argument("--root", required=True)
    u.add_argument("--force", action="store_true")

    def selection(p: argparse.ArgumentParser) -> None:
        p.add_argument("--root", required=True)
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--files", nargs="+")
        g.add_argument("--all", action="store_true", help="taban çizgisine göre değişen tüm dosyalar")
        p.add_argument("--project-dir", help="sap-project.json bulunan proje kökü (master_language)")
        p.add_argument("--main-language-letter", help="tek harfli SAP dil kodu (ör. E); eşleme bilinmiyorsa")
        p.add_argument("--subpackages-exist", action="store_true", help="yeni klasörlerin alt paketi SAP'de zaten var")
        p.add_argument("--max-baseline-days", type=int, default=7)
        p.add_argument("--json", action="store_true")

    c = sub.add_parser("check", help="denetle, ZIP üretme")
    selection(c)
    k = sub.add_parser("pack", help="denetle ve içe aktarma ZIP'i üret")
    selection(k)
    k.add_argument("--out")
    k.add_argument("-m", "--message")
    k.add_argument("--list", action="store_true")
    k.add_argument("--force", action="store_true")
    s = sub.add_parser("status-in", help="SAP'deki içe aktarma/aktivasyon çıktısını sakla")
    s.add_argument("artifact")
    s.add_argument("--root", required=True)
    s.add_argument("--label")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 3
    handlers = {"unpack": cmd_unpack, "check": cmd_check, "pack": cmd_pack, "status-in": cmd_status_in}
    try:
        return handlers[a.cmd](a)
    except UsageError as exc:
        print(f"KULLANIM HATASI: {exc}", file=sys.stderr)
        return 3
    except Deny as exc:
        print(f"RED: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
