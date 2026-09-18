#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scaffold_classic_program.py — klasik ABAP program iskeleti (yalnız YEREL dosya; SAP'ye YAZMAZ).

Kaynak ekip araç setindeki aynı adlı script'in aXet'e uyarlanmış kopyası. Değişenler:
  • Include adları aXet adlandırma standardına göre türetilir (`sap-dev` → references/naming.md §4.1):
    <GÖVDE>_P_<AD> (ya da _R_) → <GÖVDE>_I_<AD>_T01 / _C01 / _F01 (+ --dialog: _O01 / _I01, --selscreen: _S01)
  • TITLE zorunludur (naming §6); include açıklaması "TITLE - <sonek>".
  • ALV için ortak sınıf önerisi kaldırıldı (template-first; references/alv-report.md §1).
  • Sonda CLI yazma sırası METİN olarak yazdırılır; script hiçbir SAP çağrısı yapmaz, CLI'yi çalıştırmaz.

Kullanım:
  python scaffold_classic_program.py ZSD001_P_ORDER_LIST --title "Sipariş Listesi" --out <paket>/programs [--dialog] [--selscreen]
Çıkış kodu: 0 başarı · 2 geçersiz ad/uzunluk · 3 dosya zaten var (--force yoksa)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

AD_DESENI = re.compile(r"^(?P<govde>[ZY][A-Z0-9]+)_(?P<tip>[PR])_(?P<ad>[A-Z0-9_]+)$")
PROGRAM_MAX = 26   # naming §4.1: 26 + "_T01" = 30
OBJE_MAX = 30
ACIKLAMA_UYARI = 60  # adt_post_shell ölçülen sınıf açıklama sınırı; program/include için DOĞRULANMADI

BASLIK = """\
*&---------------------------------------------------------------------*
*& {tur} {ad}
*& {aciklama}
*&---------------------------------------------------------------------*
"""


def ana_program(ctx: dict) -> str:
    satirlar = [BASLIK.format(tur="Report", ad=ctx["prog"], aciklama=ctx["title"]),
                f"REPORT {ctx['prog_lc']}.", ""]
    for kod, _ in ctx["includes"]:
        satirlar.append(f"INCLUDE {ctx['inc'][kod].lower()}.")
    satirlar += [
        "",
        "INITIALIZATION.",
        "  \" Seçim ekranı blok başlığı / yorum değişkenleri burada atanır (TEXT-xxx = ... YAZMA).",
        "",
        "START-OF-SELECTION.",
        "  go_app = NEW lcl_app( ).",
        "  go_app->run( ).",
    ]
    if ctx["dialog"]:
        satirlar.append("  CALL SCREEN 0100.                 \" ekran + STAT0100 + TIT0100 ayrıca üretilir")
    return "\n".join(satirlar) + "\n"


def top_include(ctx: dict) -> str:
    govde = [
        BASLIK.format(tur="Include", ad=ctx["inc"]["T01"], aciklama=f"{ctx['title']} - TOP"),
        "\" Seçim ekranı: SELECT-OPTIONS s_<ad> / PARAMETERS p_<ad> — ad <= 8 karakter;",
        "\" FOR hedefi DATA değişkeni (TABLES bildirimi yok). Metinler metin havuzunda (master_language).",
        "",
        "CLASS lcl_data DEFINITION.",
        "  PUBLIC SECTION.",
        "    METHODS select_data.            \" okuma / hesap (standart tabloya doğrudan yazma yok)",
        "ENDCLASS.",
        "",
        "CLASS lcl_alv DEFINITION.",
        "  PUBLIC SECTION.",
        "    METHODS display.                \" ALV satır içi — templates/classic-alv-list.prog.abap",
        "ENDCLASS.",
        "",
        "CLASS lcl_app DEFINITION.",
        "  PUBLIC SECTION.",
        "    METHODS run.",
        "  PRIVATE SECTION.",
        "    DATA mo_data TYPE REF TO lcl_data.",
        "    DATA mo_alv  TYPE REF TO lcl_alv.",
        "ENDCLASS.",
        "",
        "DATA go_app TYPE REF TO lcl_app.",
    ]
    if ctx["dialog"]:
        govde += ["DATA gv_ok_code TYPE sy-ucomm.     \" ekranın OK-code alanı",
                  "DATA gv_fc      TYPE sy-ucomm.     \" normalize edilmiş fcode"]
    return "\n".join(govde) + "\n"


def sel_include(ctx: dict) -> str:
    return BASLIK.format(tur="Include", ad=ctx["inc"]["S01"], aciklama=f"{ctx['title']} - SEL") + (
        "\" AT SELECTION-SCREEN / AT SELECTION-SCREEN OUTPUT olayları.\n"
        "\" screen-text YOK (SCREEN yapısında TEXT bileşeni yok); etiketler seçim metniyle.\n")


def cls_include(ctx: dict) -> str:
    return BASLIK.format(tur="Include", ad=ctx["inc"]["C01"], aciklama=f"{ctx['title']} - CL") + """\

CLASS lcl_data IMPLEMENTATION.
  METHOD select_data.
    " Okuma: released CDS tercih (adını sistemde doğrula); FOR ALL ENTRIES öncesi boş kontrol.
  ENDMETHOD.
ENDCLASS.

CLASS lcl_alv IMPLEMENTATION.
  METHOD display.
    " Template-first: field catalog + layout + olay işleyici burada satır içi.
    " Ortak (instantiate edilen) ALV sınıfı KULLANILMAZ.
  ENDMETHOD.
ENDCLASS.

CLASS lcl_app IMPLEMENTATION.
  METHOD run.
    mo_data = NEW lcl_data( ).
    mo_data->select_data( ).
    mo_alv = NEW lcl_alv( ).
  ENDMETHOD.
ENDCLASS.
"""


def f01_include(ctx: dict) -> str:
    return BASLIK.format(tur="Include", ad=ctx["inc"]["F01"], aciklama=f"{ctx['title']} - F01") + (
        "\" FORM rutinleri (OO tercih; klasik FORM gerekirse buraya).\n"
        "\" FORM ... USING alt-sınıf referansı kabul etmez → upcast atama ile.\n")


def o01_include(ctx: dict) -> str:
    return BASLIK.format(tur="Include", ad=ctx["inc"]["O01"], aciklama=f"{ctx['title']} - O01") + """\

MODULE status_0100 OUTPUT.
  SET PF-STATUS 'STAT0100'.
  SET TITLEBAR  'TIT0100'.
  " İlk seferde grid kurulumu, sonra refresh_table_display( ).
ENDMODULE.
"""


def i01_include(ctx: dict) -> str:
    return BASLIK.format(tur="Include", ad=ctx["inc"]["I01"], aciklama=f"{ctx['title']} - I01") + """\

MODULE user_command_0100 INPUT.
  gv_fc = COND #( WHEN gv_ok_code IS NOT INITIAL THEN gv_ok_code ELSE sy-ucomm ).
  CLEAR: gv_ok_code, sy-ucomm.        " zorunlu — yapışkan komut tuzağı

  CASE gv_fc.
    WHEN 'BACK' OR 'CANCEL'.          " F3 / F12 → seçim ekranı
      LEAVE TO SCREEN 0.
    WHEN 'EXIT'.                      " Shift+F3 → programdan çık
      LEAVE PROGRAM.
    WHEN OTHERS.
  ENDCASE.
ENDMODULE.
"""


URETICI = {"T01": top_include, "S01": sel_include, "C01": cls_include, "F01": f01_include,
           "O01": o01_include, "I01": i01_include}
SONEK = {"T01": "TOP", "S01": "SEL", "C01": "CL", "F01": "F01", "O01": "O01", "I01": "I01"}


def cli_plani(ctx: dict) -> str:
    inc_adlari = [ctx["inc"][k] for k, _ in ctx["includes"]]
    also = [{"name": n, "object_type": "include"} for n in inc_adlari[1:]]
    also.append({"name": ctx["prog"], "object_type": "prog"})
    aktivasyon = {"name": inc_adlari[0], "object_type": "include", "also": also}
    satir = [
        "",
        "CLI yazma sırası — METİN; bu script ÇALIŞTIRMAZ. Otorite: sap-adt-foundation → references/foundation-ops.md §4.2",
        "Her yazma çağrısı: --sap-write --scope S0|S1|S2 (+ --reason / --intake); transport ve paket KULLANICIDAN.",
        "  1) Her include için:  adt_post_shell  object_type=include  (açıklama aşağıda)",
    ]
    for k, _ in ctx["includes"]:
        satir.append(f"       {ctx['inc'][k]:<32} \"{ctx['title']} - {SONEK[k]}\"")
    satir += [
        f"  2) Ana program:       adt_post_shell  object_type=prog  {ctx['prog']}  \"{ctx['title']}\"",
        "  3) Her obje için adt_get (include_source=true) → pull kaydı",
        "  4) Include'lara tek satır yorum, programa 'REPORT <ad>.' push (adt_push_source)",
        "  5) Tek aktivasyon (önce include'lar, sonra program):",
        "       adt_activate --args-json '" + json.dumps(aktivasyon, ensure_ascii=False) + "'",
        "  6) Gerçek kaynakları push → aynı aktivasyon → adt_inactive_objects + adt_get readback",
    ]
    if ctx["dialog"]:
        satir.append("  7) Ekran 0100 + STAT0100 + TIT0100: sap-classic-abap → references/dynpro-gui-status.md")
    return "\n".join(satir)


def main() -> int:
    ap = argparse.ArgumentParser(description="Klasik ABAP program iskeleti (yerel dosya; SAP'ye yazmaz)")
    ap.add_argument("program", help="Program adı, ör. ZSD001_P_ORDER_LIST (en fazla 26 karakter)")
    ap.add_argument("--title", required=True, help="Program TITLE'ı (kullanıcıdan, master_language'de)")
    ap.add_argument("--out", required=True, help="Çıktı klasörü (ör. <source_root>/<MODÜL>/<PAKET>/programs)")
    ap.add_argument("--dialog", action="store_true", help="Dynpro akışı: _O01 (PBO) + _I01 (PAI) include'ları")
    ap.add_argument("--selscreen", action="store_true", help="Seçim ekranı olayları için _S01 include'u")
    ap.add_argument("--force", action="store_true", help="Var olan dosyaların üzerine yaz")
    args = ap.parse_args()

    prog = args.program.strip().upper()
    m = AD_DESENI.match(prog)
    if not m:
        print("[HATA] Ad deseni <GÖVDE>_P_<AD> ya da <GÖVDE>_R_<AD> olmalı, Z/Y ile başlamalı "
              "(sap-dev → references/naming.md §4.1).", file=sys.stderr)
        return 2
    if len(prog) > PROGRAM_MAX:
        print(f"[HATA] Program adı {len(prog)} karakter; en fazla {PROGRAM_MAX} (include adı 30'u aşar).", file=sys.stderr)
        return 2
    title = args.title.strip()
    if not title:
        print("[HATA] TITLE boş olamaz (kesin yasak D).", file=sys.stderr)
        return 2

    kodlar = ["T01"] + (["S01"] if args.selscreen else []) + ["C01", "F01"] + (["O01", "I01"] if args.dialog else [])
    inc = {k: f"{m['govde']}_I_{m['ad']}_{k}" for k in kodlar}
    uzun = [n for n in inc.values() if len(n) > OBJE_MAX]
    if uzun:
        print(f"[HATA] 30 karakteri aşan include adı: {uzun}", file=sys.stderr)
        return 2

    ctx = {"prog": prog, "prog_lc": prog.lower(), "title": title, "dialog": args.dialog,
           "inc": inc, "includes": [(k, inc[k]) for k in kodlar]}
    dosyalar = {f"{prog}.prog.abap": ana_program(ctx)}
    for k in kodlar:
        dosyalar[f"{inc[k]}.prog.abap"] = URETICI[k](ctx)

    out = Path(args.out)
    var_olan = [n for n in dosyalar if (out / n).exists()]
    if var_olan and not args.force:
        print(f"[HATA] Dosya zaten var (üzerine yazmak için --force): {var_olan}", file=sys.stderr)
        return 3
    out.mkdir(parents=True, exist_ok=True)
    for ad, icerik in dosyalar.items():
        (out / ad).write_text(icerik, encoding="utf-8", newline="\n")
        print(f"[OK] {out / ad}")

    for k in kodlar:
        aciklama = f"{title} - {SONEK[k]}"
        if len(aciklama) > ACIKLAMA_UYARI:
            print(f"[UYARI] '{aciklama}' {len(aciklama)} karakter; ölçülen sınıf açıklama sınırı {ACIKLAMA_UYARI} "
                  "(program/include sınırı DOĞRULANMADI).")
    print(cli_plani(ctx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
