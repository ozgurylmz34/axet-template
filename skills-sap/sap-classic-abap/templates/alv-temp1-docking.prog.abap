*&---------------------------------------------------------------------*
*& Report ZBC000_P_ALV_TEMP1
*&---------------------------------------------------------------------*
*& ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
*& değiştir (naming.md §3).
*&
*& ŞABLON 1 — Docking ALV (tek ALV, ekranda container YOK).
*& En basit klasik liste deseni: docking container içinde tam ekran ALV.
*& - ALV = template-first (references/alv-report.md §1): field catalog (TR
*&   başlık + hotspot) + olay işleyici (lcl_event) programa SATIR İÇİ;
*&   ortak ALV sınıfı YOK.
*& - Ekran 0100 + GUI status STAT0100 + başlık TIT0100 ekran üreteciyle
*&   üretilir: ZBC000_FM_SCREEN_GEN, IV_SCREEN_TYPE='DOCKING', donör
*&   SAPLKKBL/STANDARD (references/screen-gen-kit.md §4). Üreteç yoksa Screen
*&   Painter + Menu Painter (references/dynpro-gui-status.md §2).
*& - fcode: F3=BACK, Shift+F3=EXIT, F12=CANCEL — normal tip, PAI'de işlenir.
*& - Diğer şablonlar: ZBC000_P_ALV_TEMP2 (custom control container),
*&   ZBC000_P_ALV_TEMP3 (split), ZBC000_P_ALV_TEMP4 (üreteç yolları demosu).
*&
*& ⚠ TEK GÖVDE (demo istisnası): TEMP1-4 üreteçle ekranı üretilip çalıştırılan
*&   hazır demolardır. Gerçek programda kod include'lara BÖLÜNÜR
*&   (references/programs-includes.md §1; iskelet: classic-alv-list.prog.abap).
*& DOĞRULANMADI: bu kopya SAP'de derlenmedi / çalıştırılmadı.
*&
*& KAYNAKTAN FARK (kaynak ekibin canlı şablonuna göre):
*&  1. Ad ZSD… → ZBC000_P_ALV_TEMP1; başlık yorumu genelleştirildi.
*&  2. TABLES vbak + SELECT-OPTIONS … FOR vbak-vbeln → DATA gv_vbeln +
*&     FOR gv_vbeln (programs-includes.md §2: TABLES eskimiş, S/4'te hata).
*&  3. exit_command_0100 modülü SİLİNDİ: üretilen akışta AT EXIT-COMMAND satırı
*&     yok → hiç çağrılmıyordu (ölü kod; alv-report.md §5, dynpro-gui-status.md §5.3).
*&  4. Olaylarda satır kimliği e_row_id-index / e_row-index → es_row_no-row_id
*&     (alv-report.md §4 MUST: sıralı/toplamlı gridde yanlış satır okunuyordu).
*&  5. PAI: BACK/CANCEL → LEAVE TO SCREEN 0 (önce LEAVE PROGRAM idi), EXIT →
*&     LEAVE PROGRAM; fcode okunduktan sonra CLEAR sy-ucomm (alv-report.md §5 MUST).
*&---------------------------------------------------------------------*
REPORT zbc000_p_alv_temp1.

TYPES: BEGIN OF ty_row,
         vbeln TYPE vbak-vbeln,
         erdat TYPE vbak-erdat,
         ernam TYPE vbak-ernam,
         netwr TYPE vbak-netwr,
         waerk TYPE vbak-waerk,
       END OF ty_row.

DATA: gt_data    TYPE STANDARD TABLE OF ty_row,
      go_docking TYPE REF TO cl_gui_docking_container,
      go_grid    TYPE REF TO cl_gui_alv_grid,
      gt_fcat    TYPE lvc_t_fcat,
      gs_layout  TYPE lvc_s_layo.

" Seçim ekranı: FOR hedefi DATA değişkeni (TABLES bildirimi yok); ad <= 8 karakter.
DATA gv_vbeln TYPE vbak-vbeln.
SELECT-OPTIONS s_vbeln FOR gv_vbeln.

CLASS lcl_event DEFINITION.
  PUBLIC SECTION.
    METHODS on_hotspot
      FOR EVENT hotspot_click OF cl_gui_alv_grid
      IMPORTING e_row_id e_column_id es_row_no.
    METHODS on_double_click
      FOR EVENT double_click OF cl_gui_alv_grid
      IMPORTING e_row e_column es_row_no.
    METHODS on_user_command
      FOR EVENT user_command OF cl_gui_alv_grid
      IMPORTING e_ucomm.
ENDCLASS.

CLASS lcl_event IMPLEMENTATION.
  METHOD on_hotspot.
    " Satır kimliği = es_row_no-row_id (çıktı tablosu satır no), e_row_id-index DEĞİL.
    READ TABLE gt_data INTO DATA(ls_row) INDEX es_row_no-row_id.
    IF sy-subrc = 0.
      MESSAGE |Belge { ls_row-vbeln } seçildi (kolon { e_column_id-fieldname })| TYPE 'I'.
    ENDIF.
  ENDMETHOD.
  METHOD on_double_click.
    READ TABLE gt_data INTO DATA(ls_row) INDEX es_row_no-row_id.
    IF sy-subrc = 0.
      MESSAGE |Belge { ls_row-vbeln } (çift tık)| TYPE 'I'.
    ENDIF.
  ENDMETHOD.
  METHOD on_user_command.
    CASE e_ucomm.
      WHEN OTHERS.
    ENDCASE.
  ENDMETHOD.
ENDCLASS.

DATA go_evt TYPE REF TO lcl_event.

FORM build_fcat.
  gt_fcat = VALUE lvc_t_fcat(
    ( fieldname = 'VBELN' coltext = 'Satış Belgesi'    hotspot = abap_true outputlen = 12 )
    ( fieldname = 'ERDAT' coltext = 'Oluşturma Tarihi' )
    ( fieldname = 'ERNAM' coltext = 'Oluşturan' )
    ( fieldname = 'NETWR' coltext = 'Net Değer'        do_sum  = abap_true )
    ( fieldname = 'WAERK' coltext = 'Para Birimi' ) ).
ENDFORM.

START-OF-SELECTION.
  " Standart tablo yalnız OKUNUR (kesin yasak B yazmayı yasaklar, okumayı değil).
  SELECT vbeln, erdat, ernam, netwr, waerk
    FROM vbak INTO TABLE @gt_data
    UP TO 500 ROWS
    WHERE vbeln IN @s_vbeln.
  CALL SCREEN 0100.

MODULE status_0100 OUTPUT.
  SET PF-STATUS 'STAT0100'.
  SET TITLEBAR 'TIT0100'.
  IF go_grid IS INITIAL.
    go_docking = NEW #( side  = cl_gui_docking_container=>dock_at_top
                        ratio = 95 ).
    go_grid    = NEW #( i_parent = go_docking ).
    PERFORM build_fcat.
    gs_layout = VALUE #( cwidth_opt = abap_true zebra = abap_true sel_mode = 'A' ).
    go_evt = NEW #( ).
    SET HANDLER go_evt->on_hotspot
                go_evt->on_double_click
                go_evt->on_user_command FOR go_grid.
    go_grid->set_table_for_first_display(
      EXPORTING is_layout = gs_layout i_save = 'A'
      CHANGING  it_outtab = gt_data it_fieldcatalog = gt_fcat ).
  ELSE.
    go_grid->refresh_table_display( ).
  ENDIF.
ENDMODULE.

MODULE user_command_0100 INPUT.
  " BACK(F3)/CANCEL(F12, ESC) -> seçim ekranı; EXIT(Shift+F3) -> programdan çık.
  DATA(lv_ucomm) = sy-ucomm.
  CLEAR sy-ucomm.                     " yapışkan komut tuzağı
  CASE lv_ucomm.
    WHEN 'BACK' OR 'CANCEL'.
      LEAVE TO SCREEN 0.
    WHEN 'EXIT'.
      LEAVE PROGRAM.
    WHEN OTHERS.
  ENDCASE.
ENDMODULE.
