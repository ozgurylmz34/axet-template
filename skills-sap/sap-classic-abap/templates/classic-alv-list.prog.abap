*&---------------------------------------------------------------------*
*& ŞABLON — Klasik ALV liste programı (KOPYALA + ÖZELLEŞTİR)
*&---------------------------------------------------------------------*
*& Yer tutucular: <PROGRAM> (program adı, küçük harf), kolon başlıkları
*& (spesifikasyondan, master_language'de), okunan tablo/CDS.
*&
*& ⚠ YAPI: Bu şablon TEK GÖVDE yalnız deseni gösterir. GERÇEK programda kod
*&   include'lara BÖLÜNÜR: ana program = INCLUDE + olay blokları;
*&   <GÖVDE>_I_<AD>_T01 (TOP) / _C01 (sınıf) / _F01 (FORM) / _O01 (PBO) /
*&   _I01 (PAI). Bkz. references/programs-includes.md §1 ve
*&   scripts/scaffold_classic_program.py.
*&
*& TEMPLATE-FIRST: field catalog (başlık + hotspot), olay işleyici, layout
*&   programa SATIR İÇİ kodlanır; ortak (instantiate edilen) ALV sınıfı
*&   KULLANILMAZ. Bkz. references/alv-report.md §1.
*&
*& Ekran 0100 + GUI status STAT0100 + başlık TIT0100 ayrıca üretilir
*&   (üreteç FM ya da Screen Painter/Menu Painter): references/dynpro-gui-status.md.
*&   fcode'lar: F3=BACK, Shift+F3=EXIT, F12=CANCEL — normal tip, PAI'de işlenir.
*&   exit_command_0100 modülü YAZILMAZ (akışta AT EXIT-COMMAND yoksa ölü kod).
*&---------------------------------------------------------------------*
REPORT <program>.

TYPES: BEGIN OF ty_row,               " <-- görüntü satırı (programa özgü)
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

*&--- Olay işleyici (YEREL) — hotspot / double_click / user_command ------
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
    " SATIR KİMLİĞİ = ES_ROW_NO-ROW_ID (çıktı tablosu satır no) — E_ROW_ID-INDEX DEĞİL.
    " LVC_S_ROW (e_row/e_row_id) = INDEX + ROWTYPE; toplam/ara toplam satırı ya da
    " do_sum/sıralama/filtre etkinken INDEX iç tablo indeksi değildir → yanlış satır
    " ya da sessiz no-op. Bkz. references/alv-report.md §4.
    READ TABLE gt_data INTO DATA(ls_row) INDEX es_row_no-row_id.
    IF sy-subrc = 0.
      MESSAGE |Belge { ls_row-vbeln } seçildi (kolon { e_column_id-fieldname })| TYPE 'I'.
      " ör: SET PARAMETER + CALL TRANSACTION ... (programa özgü)
    ENDIF.
  ENDMETHOD.
  METHOD on_double_click.
    READ TABLE gt_data INTO DATA(ls_row) INDEX es_row_no-row_id.
    " ... çift tık aksiyonu ...
  ENDMETHOD.
  METHOD on_user_command.
    CASE e_ucomm.                     " özel ALV toolbar fonksiyonları
      WHEN 'ZDEMO'.  " ...
      WHEN OTHERS.
    ENDCASE.
  ENDMETHOD.
ENDCLASS.

DATA go_evt TYPE REF TO lcl_event.

*&--- Field catalog: başlık + hotspot PROGRAMA ÖZGÜ → burada kodlanır -----
*  ÖNCE SOR: DDIC yapısından birleştirme mi (tipli/karmaşık grid için tercih),
*  manuel mi (basit rapor)? Bkz. references/alv-report.md §3.
*  Başlıklar (coltext) spesifikasyondan, master_language'de; iskelet etiketlerinin
*  satır içi kalması kullanıcı kararıyla kabul edilmiş istisnadır.
FORM build_fcat.
  gt_fcat = VALUE lvc_t_fcat(
    ( fieldname = 'VBELN' coltext = 'Satış Belgesi'    hotspot = abap_true  outputlen = 12 )
    ( fieldname = 'ERDAT' coltext = 'Oluşturma Tarihi' )
    ( fieldname = 'ERNAM' coltext = 'Oluşturan' )
    ( fieldname = 'NETWR' coltext = 'Net Değer'        do_sum  = abap_true )
    ( fieldname = 'WAERK' coltext = 'Para Birimi' ) ).
  " Yapıdan birleştirme: set_table_for_first_display( i_structure_name = '<YAPI>' )
  " ya da LVC_FIELDCATALOG_MERGE, sonra yalnız başlık/hotspot/no_out ayarı.
ENDFORM.

START-OF-SELECTION.
  " Clean core: yeni okuma modelinde released CDS tercih edilir; adını sistemde
  " adt_search_objects ile bul (tahmin etme). Standart tabloyu okumak yasak değildir.
  SELECT vbeln, erdat, ernam, netwr, waerk
    FROM vbak INTO TABLE @gt_data
    UP TO 500 ROWS
    WHERE vbeln IN @s_vbeln.
  CALL SCREEN 0100.

MODULE status_0100 OUTPUT.
  SET PF-STATUS 'STAT0100'.
  SET TITLEBAR  'TIT0100'.
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
      EXPORTING is_layout = gs_layout i_save = 'A'      " i_save='A' → varyant kaydı (ALV paritesi)
      CHANGING  it_outtab = gt_data it_fieldcatalog = gt_fcat ).
  ELSE.
    go_grid->refresh_table_display( ).
  ENDIF.
ENDMODULE.

MODULE user_command_0100 INPUT.
  " Navigasyon (MUST): BACK(F3)/CANCEL(F12) -> seçim ekranı (LEAVE TO SCREEN 0);
  " EXIT(Shift+F3) -> LEAVE PROGRAM. BACK/CANCEL'da LEAVE PROGRAM YASAK (ana menüye atlar).
  " Ekranda OK-code alanı tanımlıysa onu da oku ve değerlendirmeden sonra CLEAR et
  " (yapışkan komut tuzağı) — desen: templates/classic-dynpro-dialog.prog.abap.
  DATA(lv_ucomm) = sy-ucomm.
  CLEAR sy-ucomm.
  CASE lv_ucomm.
    WHEN 'BACK' OR 'CANCEL'.
      LEAVE TO SCREEN 0.
    WHEN 'EXIT'.
      LEAVE PROGRAM.
    WHEN OTHERS.
  ENDCASE.
ENDMODULE.
