*&---------------------------------------------------------------------*
*& Report ZBC000_P_ALV_TEMP3
*&---------------------------------------------------------------------*
*& ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
*& değiştir (naming.md §3).
*&
*& ŞABLON 3 — Split (üst/alt) master-detail ALV.
*& Ekranda TEK custom control (CC_ALV); cl_gui_splitter_container ile KOD İÇİNDE
*& 2 satıra (üst/alt, sürüklenebilir ayraç) bölünür. Üst hücre = VBAK (master),
*& alt hücre = seçili siparişin VBAP kalemleri (detail). Üst satıra ÇİFT TIK → alt dolar.
*& ⚠ Split = 2 ayrı container DEĞİL; tek container + splitter.
*& - Ekran 0200 + CC_ALV + STAT0200/TIT0200 ekran üreteciyle üretilir:
*&   ZBC000_FM_SCREEN_GEN, IV_DYNPRO='0200', IV_SCREEN_TYPE='CONTAINER' (tek CC),
*&   donör SAPLKKBL/STANDARD (references/screen-gen-kit.md §4). Split üreteçte
*&   ayrı tip değildir; CONTAINER ekranı + bu programdaki splitter kodu.
*& - ALV = template-first (references/alv-report.md §1): her grid için fcat satır içi.
*&
*& ⚠ TEK GÖVDE (demo istisnası): gerçek programda include'lara bölünür
*&   (references/programs-includes.md §1).
*& DOĞRULANMADI: bu kopya SAP'de derlenmedi / çalıştırılmadı.
*&
*& KAYNAKTAN FARK (kaynak ekibin canlı şablonuna göre):
*&  1. Ad ZSD… → ZBC000_P_ALV_TEMP3; başlık yorumu genelleştirildi.
*&  2. TABLES vbak + FOR vbak-vbeln → DATA gv_vbeln + FOR gv_vbeln
*&     (programs-includes.md §2).
*&  3. Çift tıkta satır kimliği e_row-index → es_row_no-row_id (alv-report.md §4
*&     MUST: üst grid sıralanınca yanlış belgenin kalemleri geliyordu).
*&  4. PAI: BACK/CANCEL → LEAVE TO SCREEN 0, EXIT → LEAVE PROGRAM, CLEAR sy-ucomm
*&     (alv-report.md §5 MUST; önce üçü de LEAVE PROGRAM idi).
*&  5. 4'ün sonucu: seçim ekranından yeniden çalıştırmada eski veri kalmasın diye
*&     START-OF-SELECTION'da CLEAR gt_vbap + PBO'da ELSE dalı (iki grid
*&     refresh_table_display). Kaynakta program her çıkışta sonlandığı için
*&     gerekmiyordu.
*& (Üst griddeki VBELN hotspot'u kaynakta da işleyicisizdi; aynen korundu.)
*&---------------------------------------------------------------------*
REPORT zbc000_p_alv_temp3.

TYPES: BEGIN OF ty_vbak,
         vbeln TYPE vbak-vbeln,
         erdat TYPE vbak-erdat,
         ernam TYPE vbak-ernam,
         netwr TYPE vbak-netwr,
         waerk TYPE vbak-waerk,
       END OF ty_vbak.
TYPES: BEGIN OF ty_vbap,
         vbeln  TYPE vbap-vbeln,
         posnr  TYPE vbap-posnr,
         matnr  TYPE vbap-matnr,
         arktx  TYPE vbap-arktx,
         kwmeng TYPE vbap-kwmeng,
         netwr  TYPE vbap-netwr,
       END OF ty_vbap.

DATA: gt_vbak     TYPE STANDARD TABLE OF ty_vbak,
      gt_vbap     TYPE STANDARD TABLE OF ty_vbap,
      go_cc       TYPE REF TO cl_gui_custom_container,
      go_split    TYPE REF TO cl_gui_splitter_container,
      go_grid_top TYPE REF TO cl_gui_alv_grid,
      go_grid_bot TYPE REF TO cl_gui_alv_grid,
      gs_layout   TYPE lvc_s_layo.

DATA gv_vbeln TYPE vbak-vbeln.
SELECT-OPTIONS s_vbeln FOR gv_vbeln.

CLASS lcl_event DEFINITION.
  PUBLIC SECTION.
    " Üst gridde çift tık -> alt gridi o belgenin kalemleriyle doldur.
    METHODS on_dblclick_top
      FOR EVENT double_click OF cl_gui_alv_grid
      IMPORTING e_row e_column es_row_no.
ENDCLASS.

CLASS lcl_event IMPLEMENTATION.
  METHOD on_dblclick_top.
    READ TABLE gt_vbak INTO DATA(ls_vbak) INDEX es_row_no-row_id.
    IF sy-subrc <> 0.
      RETURN.
    ENDIF.
    SELECT vbeln, posnr, matnr, arktx, kwmeng, netwr
      FROM vbap INTO TABLE @gt_vbap
      WHERE vbeln = @ls_vbak-vbeln.
    IF go_grid_bot IS BOUND.
      go_grid_bot->refresh_table_display( ).
    ENDIF.
  ENDMETHOD.
ENDCLASS.

DATA go_evt TYPE REF TO lcl_event.

FORM build_fcat_top CHANGING ct_fcat TYPE lvc_t_fcat.
  ct_fcat = VALUE #(
    ( fieldname = 'VBELN' coltext = 'Satış Belgesi'    hotspot = abap_true outputlen = 12 )
    ( fieldname = 'ERDAT' coltext = 'Oluşturma Tarihi' )
    ( fieldname = 'ERNAM' coltext = 'Oluşturan' )
    ( fieldname = 'NETWR' coltext = 'Net Değer'        do_sum  = abap_true )
    ( fieldname = 'WAERK' coltext = 'Para Birimi' ) ).
ENDFORM.

FORM build_fcat_bot CHANGING ct_fcat TYPE lvc_t_fcat.
  ct_fcat = VALUE #(
    ( fieldname = 'VBELN'  coltext = 'Satış Belgesi'  outputlen = 12 )
    ( fieldname = 'POSNR'  coltext = 'Kalem' )
    ( fieldname = 'MATNR'  coltext = 'Malzeme' )
    ( fieldname = 'ARKTX'  coltext = 'Açıklama' )
    ( fieldname = 'KWMENG' coltext = 'Miktar' )
    ( fieldname = 'NETWR'  coltext = 'Net Değer' do_sum = abap_true ) ).
ENDFORM.

START-OF-SELECTION.
  SELECT vbeln, erdat, ernam, netwr, waerk
    FROM vbak INTO TABLE @gt_vbak
    UP TO 500 ROWS
    WHERE vbeln IN @s_vbeln.
  CLEAR gt_vbap.                      " yeniden çalıştırmada eski kalemler kalmasın
  CALL SCREEN 0200.

MODULE status_0200 OUTPUT.
  SET PF-STATUS 'STAT0200'.
  SET TITLEBAR 'TIT0200'.
  IF go_split IS INITIAL.
    gs_layout = VALUE #( cwidth_opt = abap_true zebra = abap_true sel_mode = 'A' ).
    " TEK custom control -> splitter ile 2 satıra (üst/alt) böl.
    go_cc    = NEW #( container_name = 'CC_ALV' ).
    go_split = NEW #( parent = go_cc rows = 2 columns = 1 ).
    " set_row_height ÇAĞIRMA -> satırlar otomatik EŞİT bölünür (boşluk yok). Yalnız
    " bir satırı set edersen toplam < tam kalıp aradaki boşluk oluşur. Ayraç sürüklenebilir.
    DATA(lo_top) = go_split->get_container( row = 1 column = 1 ).
    DATA(lo_bot) = go_split->get_container( row = 2 column = 1 ).
    " --- Üst (master): VBAK ---
    go_grid_top = NEW #( i_parent = lo_top ).
    DATA lt_fcat_top TYPE lvc_t_fcat.
    PERFORM build_fcat_top CHANGING lt_fcat_top.
    go_evt = NEW #( ).
    SET HANDLER go_evt->on_dblclick_top FOR go_grid_top.
    go_grid_top->set_table_for_first_display(
      EXPORTING is_layout = gs_layout i_save = 'A'
      CHANGING  it_outtab = gt_vbak it_fieldcatalog = lt_fcat_top ).
    " --- Alt (detail): VBAP (başta boş) ---
    go_grid_bot = NEW #( i_parent = lo_bot ).
    DATA lt_fcat_bot TYPE lvc_t_fcat.
    PERFORM build_fcat_bot CHANGING lt_fcat_bot.
    go_grid_bot->set_table_for_first_display(
      EXPORTING is_layout = gs_layout i_save = 'A'
      CHANGING  it_outtab = gt_vbap it_fieldcatalog = lt_fcat_bot ).
  ELSE.
    go_grid_top->refresh_table_display( ).
    go_grid_bot->refresh_table_display( ).
  ENDIF.
ENDMODULE.

MODULE user_command_0200 INPUT.
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
