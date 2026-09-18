"""
check_sap_master_language.py — Z obje masterLanguage = projenin master_language'i mi doğrula.

Kaynak çekirdekteki aynı adlı validator'ın uyarlaması. Fark: beklenen dil sabit "TR" DEĞİL,
proje kökündeki `sap-project.json` → `master_language` (utils.project_config.master_language).
Beklenen dil çözülemezse ÖLÇÜLMEDİ (SKIP, measured=false) döner — varsayılan dil UYDURULMAZ.

Canlı SAP'de bir Z objenin adtcore:masterLanguage'ı kontrol edilir. Post-create çağrılır
(obje aktif olmalı). Farklı dil → BLOCKER.

Kök sebep: SAP, obje master dilini oturumun logon diline göre belirler; oturum başka dilde
açılırsa obje o dilde yaratılır. Bu validator defense-in-depth'tir (yazma kapısı zaten
bağlantı dili ≠ master_language iken yazmayı `language_mismatch` ile reddeder).

Kullanım:
    python check_sap_master_language.py --name ZDEMO1_I_X --type ddls
    python check_sap_master_language.py --name ZCL_X --type class

Exit: 0 = beklenen dil (veya obje yok/okunamadı → SKIP), 1 = farklı dil (BLOCKER)
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # lib/
sys.path.insert(0, str(Path(__file__).resolve().parent))      # validators/
from _gate_status import gate_status  # noqa: E402

_GATE = Path(__file__).stem


def main() -> int:
    ap = argparse.ArgumentParser(description="Z obje masterLanguage kontrolü (sap-project.json)")
    ap.add_argument("path", nargs="?", help="run_review pozisyonel artifact (ad/tip path'ten türetilir)")
    ap.add_argument("--name", help="obje adı (verilmezse path stem'inden)")
    ap.add_argument("--type", help="ddls/class/... (verilmezse path uzantısından)")
    args, _ = ap.parse_known_args()  # run_review ek flag (--type table vb.) → yut

    try:
        from utils.project_config import master_language  # type: ignore
        beklenen = master_language()
    except Exception:  # noqa: BLE001
        beklenen = None
    if not beklenen:
        print("SKIP — sap-project.json master_language çözülemedi; beklenen dil UYDURULMADI")
        gate_status(_GATE, 'SKIPPED', False, 'master-language-bilinmiyor')
        return 0

    name, otype = args.name, args.type
    if not name and args.path:
        fn = Path(args.path).name
        name = fn.split(".")[0]
        if otype is None:
            low = fn.lower()
            otype = "ddls" if any(e in low for e in (".cds", ".ddls", ".asddls")) else (
                "class" if (".clas" in low or ".abap" in low) else None)
    if not name:
        print("SKIP — ne --name ne pozisyonel path verildi; master language kontrol edilemedi")
        gate_status(_GATE, 'SKIPPED', False, 'obje-adi-verilmedi')
        return 0
    otype = otype or "class"

    try:
        from sap_client import SAPClient  # type: ignore
        import contextlib
        c = SAPClient()
        with contextlib.redirect_stdout(io.StringIO()):
            md = c.get_object_metadata(name, object_type=otype)
    except Exception as exc:
        print(f"SKIP — SAP okunamadı ({type(exc).__name__}); master language kontrol edilemedi")
        gate_status(_GATE, 'SKIPPED', False, 'sap-baglanti-yok')
        return 0

    if not md:
        print(f"SKIP — {name} ({otype}) okunamadı/aktif değil")
        gate_status(_GATE, 'SKIPPED', False, 'metadata-okunamadi')
        return 0

    m = re.search(r'masterLanguage="(\w+)"', md if isinstance(md, str) else str(md))
    lang = m.group(1) if m else None
    if lang and lang.upper() == beklenen.upper():
        print(f"OK — {name} masterLanguage={lang} (beklenen {beklenen})")
        gate_status(_GATE, 'OK', True, 'master-language-uygun')
        return 0

    print(f"\n[BLOCKER] {name} masterLanguage={lang or '?'} — sap-project.json master_language="
          f"{beklenen} bekler.", file=sys.stderr)
    print("  Kök sebep: create oturumu başka logon dilinde açıldıysa SAP objeyi o dilde yaratır. "
          "Obje adı ilk yaratımdaki dile yapışabilir: yeni ad ya da dil düzeltmesi gerekir.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
