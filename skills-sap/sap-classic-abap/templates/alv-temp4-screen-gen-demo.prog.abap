*&---------------------------------------------------------------------*
*& Report ZBC000_P_ALV_TEMP4
*&---------------------------------------------------------------------*
*& ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
*& değiştir (naming.md §3).
*&
*& ŞABLON 4 — Ekran üretecinin üç yolu tek programda: alan listesi + buton +
*& CUA merge. ZBC000_FM_SCREEN_GEN'in şu yeteneklerini gösterir:
*&   IT_FIELDS (ekran alanı üretimi) · IT_BUTTONS (uygulama toolbar'ı) ·
*&   CUA merge (aynı programda birden çok ekranın status/başlığı korunarak).
*& - 0100 = TEMP1 profili (DOCKING, container yok, buton yok)
*& - 0200 = TEMP2/3 profili (CUST_CTRL 'CC_ALV') + IT_BUTTONS yolu (fcode REFRESH)
*& - 0300 = IT_FIELDS yolu (DOCKING; alan ekranı — ALV yok)
*& Üç ekran + GUI status/başlık üreteçle, donör SAPLKKBL/STANDARD ile üretilir;
*& çağrı değerleri: references/screen-gen-kit.md §4.
*& - ALV = template-first (references/alv-report.md §1): fcat + lcl_event satır içi.
*& ⛔ exit_command_<n> modülü BİLEREK YOK: üretilen akışta AT EXIT-COMMAND
*&   satırı yok → o modül hiç çağrılmaz (ölü kod).
*& ⚠ handle_ucomm hem BACK/EXIT/CANCEL hem &F.. donör fcode'larını yakalar:
*&   nav remap ÇALIŞMAZSA donör fcode'u gelir ve ekranda GÖRÜNÜR olur
*&   (teşhis bir tura iner).
*&
*& ⓘ ETİKET KURALI (kaynak ekipte canlı sondayla ölçüldü): bir GİRİŞ alanı
*&   FROM_DICT='X' ile bile KENDİ ETİKETİNİ GETİRMEZ. Her etiket AYRI bir
*&   TYPE='TEXT' satırıdır; TEXT satırına FROM_DICT='X' ver, TEXT'i BOŞ bırak →
*&   metin DDIC'ten gelir (metin uydurulmaz — kesin yasak D dostu).
*&   ⚠ TEXT satırını unutmak SESSİZ kusurdur (FM uyarı vermez).
*&   Ayrıntı: references/dynpro-dialog-fields.md §1.1.
*& ⓘ Kaynak ekipte bu program, üretecin birleştirilmiş sürümünün regresyon
*&   testi olarak da kullanıldı (TEMP1 kopyasına karşı); şablon olarak kaldı.
*&
*& ⚠ TEK GÖVDE (demo istisnası): gerçek programda include'lara bölünür
*&   (references/programs-includes.md §1).
*& DOĞRULANMADI: bu kopya SAP'de derlenmedi / çalıştırılmadı.
*&
*& KAYNAKTAN FARK (kaynak ekibin canlı şablonuna göre):
*&  1. Ad ZSD… → ZBC000_P_ALV_TEMP4; başlık yorumu genelleştirildi
*&     (tarihli vaka anlatıları çıkarıldı, ders korundu).
*&  2. TABLES vbak → DATA gv_vbeln (seçim) + DATA vbak (0300 ekran alanlarının
*&     global work area'sı; ekran alanı VBAK-<ALAN> adıyla bu değişkene bağlanır,
*&     dynpro-dialog-fields.md §1). Kaynakta TABLES vbak ikisini birden karşılıyordu.
*&  3. Satır kimliği → es_row_no-row_id (alv-report.md §4 MUST).
*&  4. PAI: BACK/CANCEL → LEAVE TO SCREEN 0, EXIT → LEAVE PROGRAM, CLEAR sy-ucomm
*&     (alv-report.md §5 MUST; önce üçü de LEAVE PROGRAM idi). user_command_0200'de
*&     REFRESH dalında da CLEAR sy-ucomm.
*&  5. 4'ün sonucu: BACK/CANCEL'da FORM free_controls (grid + container'lar
*&     serbest bırakılır). Seçim ekranından BAŞKA bir p_dynnr ile yeniden
*&     çalıştırınca eski grid eski container'a bağlı kalıp yeni ekran boş
*&     görünmesin diye. Kaynakta program her çıkışta sonlandığı için gerekmiyordu.
*&---------------------------------------------------------------------*
REPORT zbc000_p_alv_temp4.

TYPES: BEGIN OF ty_row,
         vbeln TYPE vbak-vbeln,
         erdat TYPE vbak-erdat,
         ernam TYPE vbak-ernam,
         netwr TYPE vbak-netwr,
         waerk TYPE vbak-waerk,
       END OF ty_row.

DATA: gt_data    TYPE STANDARD TABLE OF ty_row,
      go_docking TYPE REF TO cl_gui_docking_container,
      go_cc      TYPE REF TO cl_gui_custom_container,
*     Ortak üst sınıf referansı: klasik FORM USING formal parametresi ALT SINIF
*     referansını KABUL ETMEZ ("actual parameter incompatible" — ölçüldü),
*     upcast yalnızca ATAMA ile olur -> parent global değişkende taşınır.
      go_parent  TYPE REF TO cl_gui_container,
      go_grid    TYPE REF TO cl_gui_alv_grid,
      gt_fcat    TYPE lvc_t_fcat,
      gs_layout  TYPE lvc_s_layo.

* 0300 ekranının DDIC'e bağlı alanları (NAME='VBAK-<ALAN>', FROM_DICT='X')
* program tarafında bu global work area'ya bağlanır — adı yapı/tablo adıyla aynı.
DATA vbak TYPE vbak.

DATA gv_vbeln TYPE vbak-vbeln.
SELECT-OPTIONS s_vbeln FOR gv_vbeln.
* Hangi ekranın açılacağı: 0100 (DOCKING) / 0200 (CONTAINER) / 0300 (alanlar).
PARAMETERS p_dynnr TYPE sy-dynnr DEFAULT '0100'.

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

* ALV'yi GO_PARENT'a bağla (0100 docking / 0200 custom control ortak yolu).
FORM show_alv.
  IF go_grid IS NOT INITIAL.
    go_grid->refresh_table_display( ).
    RETURN.
  ENDIF.
  go_grid = NEW #( i_parent = go_parent ).
  PERFORM build_fcat.
  gs_layout = VALUE #( cwidth_opt = abap_true zebra = abap_true sel_mode = 'A' ).
  go_evt = NEW #( ).
  SET HANDLER go_evt->on_hotspot
              go_evt->on_double_click
              go_evt->on_user_command FOR go_grid.
  go_grid->set_table_for_first_display(
    EXPORTING is_layout = gs_layout i_save = 'A'
    CHANGING  it_outtab = gt_data it_fieldcatalog = gt_fcat ).
ENDFORM.

* Seçim ekranına dönerken kontrolleri serbest bırak: bir sonraki çalıştırma
* başka ekran (p_dynnr) seçebilir; grid yeni parent'a baştan kurulmalı.
FORM free_controls.
  IF go_grid IS BOUND.
    go_grid->free( EXCEPTIONS OTHERS = 1 ).
    CLEAR go_grid.
  ENDIF.
  IF go_docking IS BOUND.
    go_docking->free( EXCEPTIONS OTHERS = 1 ).
    CLEAR go_docking.
  ENDIF.
  IF go_cc IS BOUND.
    go_cc->free( EXCEPTIONS OTHERS = 1 ).
    CLEAR go_cc.
  ENDIF.
  CLEAR go_parent.
ENDFORM.

* Nav remap ÇALIŞTI MI — çalışırken görünür kılan ortak PAI dalı.
* Remap AÇIKSA BACK/EXIT/CANCEL gelir; KAPALIYSA donörün &F.. fcode'u gelir.
FORM handle_ucomm.
  DATA(lv_ucomm) = sy-ucomm.
  CLEAR sy-ucomm.                     " yapışkan komut tuzağı
  CASE lv_ucomm.
    WHEN 'BACK' OR 'CANCEL'.
      PERFORM free_controls.
      LEAVE TO SCREEN 0.
    WHEN 'EXIT'.
      LEAVE PROGRAM.
    WHEN '&F01' OR '&F02' OR '&F03' OR '&F04' OR '&F05'
      OR '&F1'  OR '&F2'  OR '&F3'  OR '&F4'  OR '&F5'
      OR '&F12' OR '&F15'.
      MESSAGE |NAV REMAP YOK -- donör fcode geldi: { lv_ucomm }| TYPE 'I'.
      LEAVE PROGRAM.
    WHEN OTHERS.
  ENDCASE.
ENDFORM.

START-OF-SELECTION.
  SELECT vbeln, erdat, ernam, netwr, waerk
    FROM vbak INTO TABLE @gt_data
    UP TO 500 ROWS
    WHERE vbeln IN @s_vbeln.
  CALL SCREEN p_dynnr.

*--- 0100: DOCKING (TEMP1 profili) ------------------------------------*
MODULE status_0100 OUTPUT.
  SET PF-STATUS 'STAT0100'.
  SET TITLEBAR 'TIT0100'.
  IF go_docking IS INITIAL.
    go_docking = NEW #( side  = cl_gui_docking_container=>dock_at_top
                        ratio = 95 ).
  ENDIF.
  go_parent = go_docking.        " upcast (atama ile)
  PERFORM show_alv.
ENDMODULE.

MODULE user_command_0100 INPUT.
  PERFORM handle_ucomm.
ENDMODULE.

*--- 0200: CUSTOM CONTROL 'CC_ALV' (TEMP2/3 profili) + IT_BUTTONS -----*
MODULE status_0200 OUTPUT.
  SET PF-STATUS 'STAT0200'.
  SET TITLEBAR 'TIT0200'.
  IF go_cc IS INITIAL.
    go_cc = NEW #( container_name = 'CC_ALV' ).
  ENDIF.
  go_parent = go_cc.             " upcast (atama ile)
  PERFORM show_alv.
ENDMODULE.

MODULE user_command_0200 INPUT.
* IT_BUTTONS ile üretilen fcode'un KARŞILIĞI (yoksa toolbar'da tepkisiz buton kalır).
  IF sy-ucomm = 'REFRESH'.
    CLEAR sy-ucomm.
    IF go_grid IS NOT INITIAL.
      go_grid->refresh_table_display( ).
    ENDIF.
    RETURN.
  ENDIF.
  PERFORM handle_ucomm.
ENDMODULE.

*--- 0300: IT_FIELDS yolu (DOCKING, ALV yok — alan ekranı) -----------*
MODULE status_0300 OUTPUT.
  SET PF-STATUS 'STAT0300'.
  SET TITLEBAR 'TIT0300'.
ENDMODULE.

MODULE user_command_0300 INPUT.
  PERFORM handle_ucomm.
ENDMODULE.
