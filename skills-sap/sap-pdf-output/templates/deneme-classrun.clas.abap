"! ŞABLON — aXet sap-pdf-output deneme sınıfı. SAP'de DERLENMEDİ ve ÇALIŞTIRILMADI (aXet'te ölçülmedi).
"! RENDER_PDF çağrısı ve CL_BCS PDF eki çekirdekte canlı ölçülen desenden (S/4 private 2025). Bu şablonda ayrıca
"! ÖLÇÜLMEYENLER: cl_web_http_utility=>encode_x_base64, ev_trace_string tipi, classrun'un satır biçimi —
"! push'tan önce hedef sistemde imzaları oku (adt_get), sözdizimi denetimi + aktivasyon + geri okuma.
"! Ad: ZCL_<GÖVDE>_PDF_DENEME (yer tutucu; adı, paketi, transportu kullanıcı verir).
"! İş bitince sınıf SİLİNİR (kişisel test adresi taşıyabilir).
"! get_xdp / get_veri gövdelerini ELLE yazma — xdp_abap_uret.py üretir (--veri-gom ile ikisi birden).
CLASS zcl_<gövde>_pdf_deneme DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    INTERFACES if_oo_adt_classrun.
  PRIVATE SECTION.
    "! Mail varsayılan KAPALI. Açmadan önce: alıcı yalnız KENDİ adresin, gönderen politikası soruldu,
    "! kullanıcı onayı alındı. Mail açıkken koşu zaman aşımı/500 verirse TEKRAR KOŞMA — önce SOST/SOOD.
    CONSTANTS gc_mail_acik  TYPE abap_bool VALUE abap_false.
    CONSTANTS gc_test_alici TYPE string    VALUE ``.       " <kendi-adresin> — kullanıcı verir
    CONSTANTS gc_gonderen   TYPE string    VALUE ``.       " boş = sy-uname; relay teknik adres istiyorsa <teknik-adres>
    CONSTANTS gc_b64_satir  TYPE i         VALUE 76.       " sabit base64 satır uzunluğu

    METHODS get_xdp  RETURNING VALUE(rv_xml) TYPE string.
    METHODS get_veri RETURNING VALUE(rv_xml) TYPE string.
    METHODS yaz_base64
      IMPORTING iv_pdf TYPE xstring
                io_out TYPE REF TO if_oo_adt_classrun_out.
    METHODS mail_gonder
      IMPORTING iv_pdf TYPE xstring
                io_out TYPE REF TO if_oo_adt_classrun_out.
ENDCLASS.


CLASS zcl_<gövde>_pdf_deneme IMPLEMENTATION.

  METHOD if_oo_adt_classrun~main.
    DATA ls_opt   TYPE cl_fp_ads_util=>ty_gs_options_pdf.
    DATA lv_pdf   TYPE xstring.
    DATA lv_pages TYPE i.
    DATA lv_trace TYPE string.                            " tipi hedef sistemde doğrula

    ls_opt-embed_fonts = abap_true.                       " Türkçe glifler için ŞART (AF-XDP-05)

    DATA(lv_xdp_x)  = cl_web_http_utility=>encode_utf8( get_xdp( ) ).
    DATA(lv_data_x) = cl_web_http_utility=>encode_utf8( get_veri( ) ).

    TRY.
        cl_fp_ads_util=>render_pdf( EXPORTING iv_xml_data     = lv_data_x
                                              iv_xdp_layout   = lv_xdp_x
                                              iv_locale       = 'tr_TR'     " projenin yerel ayarı
                                              is_options      = ls_opt
                                    IMPORTING ev_pdf          = lv_pdf
                                              ev_pages        = lv_pages
                                              ev_trace_string = lv_trace ).
      CATCH cx_fp_ads_util INTO DATA(lx_ads).
        " İz istisnadan önce dolar (çekirdekte kaynak okuması; canlı hata koşusu yapılmadı)
        out->write( |HATA render: { lx_ads->get_text( ) }| ).
        DATA(lv_iz_hata) = substring( val = lv_trace len = nmin( val1 = 2000 val2 = strlen( lv_trace ) ) ).
        out->write( |ADS_IZ_BASI={ lv_iz_hata }| ).
        RETURN.
    ENDTRY.

    out->write( |EV_PAGES={ lv_pages }| ).                " beklenenle aynı mı? (AF-XDP-06)
    out->write( |PDF_BAYT={ xstrlen( lv_pdf ) }| ).
    DATA(lv_iz) = substring( val = lv_trace len = nmin( val1 = 500 val2 = strlen( lv_trace ) ) ).
    out->write( |ADS_IZ_BASI={ lv_iz }| ).
    yaz_base64( iv_pdf = lv_pdf io_out = out ).

    IF gc_mail_acik = abap_true.
      mail_gonder( iv_pdf = lv_pdf io_out = out ).
    ENDIF.
  ENDMETHOD.


  METHOD yaz_base64.
    " pdf_coz.py bu işaretler arasını okur; satırlar sabit uzunlukta (son satır hariç)
    DATA(lv_b64) = cl_web_http_utility=>encode_x_base64( iv_pdf ).
    DATA(lv_len) = strlen( lv_b64 ).
    DATA lv_off TYPE i.
    io_out->write( `>>>PDF-BASE64-BASLA<<<` ).
    WHILE lv_off < lv_len.
      DATA(lv_parca) = nmin( val1 = gc_b64_satir val2 = lv_len - lv_off ).
      DATA(lv_satir) = substring( val = lv_b64 off = lv_off len = lv_parca ).
      io_out->write( lv_satir ).
      lv_off = lv_off + lv_parca.
    ENDWHILE.
    io_out->write( `>>>PDF-BASE64-BITTI<<<` ).
  ENDMETHOD.


  METHOD mail_gonder.
    " ⛔ Dışa dönük iş: alıcı/içerik kullanıcı onaylı, alıcı YALNIZ kendi adresin. Koşu TEK istek —
    "    zaman aşımı/500 → tekrar koşma, önce SOST/SOOD (mail iki kez gidebilir).
    IF gc_test_alici IS INITIAL.
      io_out->write( `MAIL: atlandı — gc_test_alici boş` ).
      RETURN.
    ENDIF.
    TRY.
        DATA(lo_req) = cl_bcs=>create_persistent( ).
        DATA(lo_doc) = cl_document_bcs=>create_document(
                         i_type    = 'HTM'                          " RAW değil
                         i_subject = 'PDF deneme'                   " CHAR50 keser
                         i_text    = cl_bcs_convert=>string_to_soli( iv_string = `<p>PDF deneme koşusu.</p>` ) ).
        lo_doc->add_attachment( i_attachment_type    = 'PDF'
                                i_attachment_subject = 'deneme'
                                i_attachment_size    = CONV #( xstrlen( iv_pdf ) )
                                i_att_content_hex    = cl_bcs_convert=>xstring_to_solix( iv_xstring = iv_pdf )
                                i_attachment_header  = VALUE soli_tab( ( line = `&SO_FILENAME=deneme.pdf` ) ) ).
        lo_req->set_document( lo_doc ).
        lo_req->set_message_subject( ip_subject = `PDF deneme koşusu` ).   " > 50 karakter konu buradan
        IF gc_gonderen IS INITIAL.
          lo_req->set_sender( cl_sapuser_bcs=>create( sy-uname ) ).      " relay serbest bırakıyorsa
        ELSE.
          lo_req->set_sender( cl_cam_address_bcs=>create_internet_address(
                                i_address_string = CONV #( gc_gonderen ) ) ).
        ENDIF.
        lo_req->add_recipient( i_recipient = cl_cam_address_bcs=>create_internet_address(
                                               i_address_string = CONV #( gc_test_alici ) ) ).
        lo_req->set_send_immediately( abap_true ).
        IF lo_req->send( ) = abap_true.
          COMMIT WORK.   " classrun RAP bağlamı DEĞİL — RAP dışı deneme sınıfı istisnası (BE-26 gerekçesi)
          io_out->write( `MAIL: send() true — teslimi SOST/SOES'te kontrol et (718 kabul · 812 gönderen yetkisiz)` ).
        ELSE.
          io_out->write( `MAIL: send() false` ).
        ENDIF.
      CATCH cx_bcs INTO DATA(lx_bcs).
        io_out->write( |MAIL HATA: { lx_bcs->get_text( ) }| ).
    ENDTRY.
  ENDMETHOD.


  " >>> URETILDI: get_xdp
  METHOD get_xdp.
    " Yer tutucu — xdp_abap_uret.py --xdp <.xdp> --veri <.xml> --abap <bu dosya> --veri-gom bu bloğu yazar.
  ENDMETHOD.
  " <<< URETILDI: get_xdp

  " >>> URETILDI: get_veri
  METHOD get_veri.
    " Yer tutucu — deneme koşusunda örnek veri; ürün kodunda veri XML'i gerçek veriden kurulur.
  ENDMETHOD.
  " <<< URETILDI: get_veri

ENDCLASS.
