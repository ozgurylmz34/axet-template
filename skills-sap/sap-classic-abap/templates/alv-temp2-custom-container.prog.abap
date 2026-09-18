*&---------------------------------------------------------------------*
*& Report ZBC000_P_ALV_TEMP2
*&---------------------------------------------------------------------*
*& ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
*& değiştir (naming.md §3).
*&
*& ŞABLON 2 — Custom control container'lı ALV.
*& ALV docking yerine ekranda BELİRLİ YER/BOYUTTA bir custom control alanında
*& (cl_gui_custom_container) gösterilir → başlık alanları + ALV, split,
*& çoklu kontrol senaryolarının temeli.
*& - Ekran 0100 + CUST_CTRL 'CC_ALV' + STAT0100/TIT0100 ekran üreteciyle
*&   üretilir: ZBC000_FM_SCREEN_GEN, IV_SCREEN_TYPE='CONTAINER',
*&   IV_CC_NAME='CC_ALV', donör SAPLKKBL/STANDARD (references/screen-gen-kit.md §4).
*& - ALV = template-first (references/alv-report.md §1): fcat + lcl_event satır içi.
*& Farkı TEMP1'den: docking yerine custom container (i_parent = go_cc).
*&
*& ⚠ TEK GÖVDE (demo istisnası): gerçek programda include'lara bölünür
*&   (references/programs-includes.md §1).
*& DOĞRULANMADI: bu kopya SAP'de derlenmedi / çalıştırılmadı.
*&
*& KAYNAKTAN FARK (kaynak ekibin canlı şablonuna göre):
*&  1. Ad ZSD… → ZBC000_P_ALV_TEMP2; başlık yorumu genelleştirildi.
*&  2. TABLES vbak + FOR vbak-vbeln → DATA gv_vbeln + FOR gv_vbeln
*&     (programs-includes.md §2).
*&  3. exit_command_0100 modülü SİLİNDİ (akışta AT EXIT-COMMAND yok → ölü kod;
*&     alv-report.md §5).
*&  4. Satır kimliği → es_row_no-row_id (alv-report.md §4 MUST).
*&  5. PAI: BACK/CANCEL → LEAVE TO SCREEN 0, EXIT → LEAVE PROGRAM, CLEAR sy-ucomm
*&     (alv-report.md §5 MUST; önce üçü de LEAVE PROGRAM idi).
*&---------------------------------------------------------------------*
REPORT zbc000_p_alv_temp2.

TYPES: BEGIN OF ty_row,
         vbeln TYPE vbak-vbeln,
         erdat TYPE vbak-erdat,
         ernam TYPE vbak-ernam,
         netwr TYPE vbak-netwr,
         waerk TYPE vbak-waerk,
       END OF ty_row.

DATA: gt_data   TYPE STANDARD TABLE OF ty_row,
      go_cc     TYPE REF TO cl_gui_custom_container,
      go_grid   TYPE REF TO cl_gui_alv_grid,
      gt_fcat   TYPE lvc_t_fcat,
      gs_layout TYPE lvc_s_layo.

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
  SELECT vbeln, erdat, ernam, netwr, waerk
    FROM vbak INTO TABLE @gt_data
    UP TO 500 ROWS
    WHERE vbeln IN @s_vbeln.
  CALL SCREEN 0100.

MODULE status_0100 OUTPUT.
  SET PF-STATUS 'STAT0100'.
  SET TITLEBAR 'TIT0100'.
  IF go_grid IS INITIAL.
    " Custom control container — ekrandaki 'CC_ALV' alanına bağla
    go_cc   = NEW #( container_name = 'CC_ALV' ).
    go_grid = NEW #( i_parent = go_cc ).
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
