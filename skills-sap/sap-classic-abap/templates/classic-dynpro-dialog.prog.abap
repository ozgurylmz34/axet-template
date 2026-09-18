*&---------------------------------------------------------------------*
*& ŞABLON — Klasik modal Dynpro DİYALOG ekranı (KOPYALA + ÖZELLEŞTİR)
*&---------------------------------------------------------------------*
*& Yer tutucular: <PROGRAM>, ekran no (örnekte 0400), fcode'lar, DDIC yapısı
*& (örnekte nötr demo ZSD001_S_DLG — adı ve alanları kullanıcı onaylar).
*&
*& SINIR (kardeş şablon, kopyası DEĞİL):
*&   LİSTE/RAPOR ekranı (çok satır, ALV grid)  → classic-alv-list.prog.abap
*&   DİYALOG ekranı (TEK KAYITLIK modal form: düzeltme/ekleme/transfer —
*&     DDIC yapıya bağlı alanlar + doğrulama + kaydet akışı) → BU şablon
*&   Aynı programda ikisi bir arada olabilir (liste + ondan açılan diyaloglar).
*&
*& ÖNCE OKU (bu şablon yalnız iskelettir):
*&   references/dynpro-dialog-fields.md — karar ağacı, F4 dört mekanizma,
*&     etiket kuralı, çok turlu CUA tuzakları, doğrulama
*&   references/dynpro-gui-status.md — ekran + GUI status üretimi (üreteç FM
*&     ya da Screen Painter/Menu Painter), donör, container değerleri
*&   references/programs-includes.md §1 — include bölme (bu şablon TEK GÖVDE
*&     gösterir; gerçek programda T01/C01/O01/I01/F01'e bölünür)
*&   ⛔ exit_command_<n> MODÜLÜ YAZMA: akışta AT EXIT-COMMAND yoksa hiç
*&     çağrılmaz. ESC = F12 = CANCEL, PAI yakalar.
*&   ⚠ Klasik FORM ... USING alt-sınıf referansını kabul etmez ("actual
*&     parameter incompatible"): upcast yalnız ATAMA ile —
*&       DATA go_parent TYPE REF TO cl_gui_container.
*&       go_parent = go_docking.   " sonra PERFORM ... USING go_parent
*&---------------------------------------------------------------------*
*&
*& 1) DDIC YAPI — diyalog alanlarının TEK KAYNAĞI (programa özel gs_* yapı +
*&    MOVE-CORRESPONDING köprüsüne DÖNME). Ekran alanı doğrudan bu yapının
*&    bileşenine bağlanır → uzunluk / CONV_EXIT / arama yardımı DDIC'ten gelir.
*&
*&    define structure zsd001_s_dlg {
*&      ver_matnr  : matnr;
*&      ver_werks  : werks_d;
*&      ver_lgort  : lgort_d
*&        with value help h_t001l                    " bileşene bağlama —
*&          where lgort = zsd001_s_dlg.ver_lgort      " ekran ALAN ADINA değil
*&            and werks = zsd001_s_dlg.ver_werks;     " YAPI BİLEŞENİNE yapılır
*&      hed_referans : xblnr;
*&      hed_tarihi   : bldat;
*&      @Semantics.quantity.unitOfMeasure : 'zsd001_s_dlg.meins'
*&      menge      : menge_d;
*&      meins      : meins;
*&    }
*&
*&    Ekran üretiminde her alan (üreteç FM payload'ı ya da Screen Painter'da
*&    "sözlükten al"):
*&        NAME='ZSD001_S_DLG-VER_LGORT'  TYPE='TEMPLATE'  FROM_DICT='X'
*&        MATCHCODE=''   (elle matchcode DDIC bağlamasının ÖNÜNE GEÇER)
*&    ⭐ ETİKET AYRI SATIRDIR: giriş alanı FROM_DICT ile bile kendi etiketini
*&      GETİRMEZ. Her etiket için TYPE='TEXT' + FROM_DICT='X' + TEXT BOŞ →
*&      metin DDIC'ten gelir. Unutmak SESSİZ kusurdur.
*&    ⚠ Alan ekranı docking ister (container modunda CC_ALV tüm ekranı
*&      kaplar → rc=6). Üreteç yolunda donör AÇIKÇA verilir: bu şablonun
*&      PAI'si BACK/EXIT/CANCEL bekler; minimal donör &F2..&F5 üretir. Kit
*&      üretecinde varsayılan SAPLKKBL/STANDARD (references/screen-gen-kit.md).
*& ---------------------------------------------------------------------
*&
REPORT <program>.                     " <-- gerçek programda ana program = INCLUDE'lar + olaylar

*&--- TOP include (_T01) — DDIC yapıya bağlı work area + sabitler -------
DATA zsd001_s_dlg TYPE zsd001_s_dlg.  " <-- adı YAPI ADIYLA AYNI: ekran alanları
                                       "     ZSD001_S_DLG-VER_LGORT diye adreslenir.
DATA gv_ok_code TYPE sy-ucomm.        " ekranın OK-code alanı
DATA gv_fc      TYPE sy-ucomm.        " normalize edilmiş fcode

CONSTANTS: c_scrf_ver_lgort TYPE screen-name VALUE 'ZSD001_S_DLG-VER_LGORT'.
                                       " LOOP AT SCREEN'de alan adıyla eşlemek için

*&--- PBO (_O01) ----------------------------------------------------------
MODULE status_0400 OUTPUT.
  SET PF-STATUS 'STAT0400'.
  SET TITLEBAR  'TIT0400'.
  PERFORM dlg_dynamic_lock.           " ⚠ ÇAĞRI PBO'DA OLMAK ZORUNDA — LOOP AT SCREEN /
                                       "   MODIFY SCREEN yalnız PBO'da anlamlı; PAI'de
                                       "   kilit SESSİZCE uygulanmaz.
ENDMODULE.

*&--- Dinamik alan kilidi (_F01) — "koşullu salt okuma" deseni -----------
*  Kapsam içi kayıt varsa alan otomatik doldurulur + kilitlenir; kapsam dışıysa
*  giriş açık kalır ⇒ kapsam dışı senaryoda regresyon yok.
FORM dlg_dynamic_lock.
  DATA lv_fixed TYPE char20.          " <-- programa özgü: bir ana veri okumasının
                                       "     döndürdüğü sabit değer

  IF zsd001_s_dlg-ver_matnr IS NOT INITIAL.
    lv_fixed = |okuma burada|.        " <-- ör. iş mantığı sınıfının metodu
  ENDIF.

  LOOP AT SCREEN.
    IF screen-name = c_scrf_ver_lgort.
      IF lv_fixed IS INITIAL.
        screen-input = 1.             " kapsam dışı → giriş açık
      ELSE.
        screen-input = 0.             " uyarlanmış → salt okuma
      ENDIF.
      MODIFY SCREEN.
    ENDIF.
  ENDLOOP.
ENDFORM.

*&--- PAI (_I01) — fcode dağıtımı (BU ekranın KENDİ fcode'u) ---------------
*  ⭐ AYRI FCODE KURALI: fcode metni + quickinfo PROGRAM GENELİDİR. İki diyalog
*    aynı kaydet fcode'unu paylaşırsa birinin etiketi yanlış görünür → her
*    diyalog ekranı kendine özel kod taşır (ör. bu ekran DLGKAY, bir başkası TRFKAY).
MODULE user_command_0400 INPUT.
  gv_fc = COND #( WHEN gv_ok_code IS NOT INITIAL THEN gv_ok_code ELSE sy-ucomm ).
  CLEAR: gv_ok_code, sy-ucomm.        " ⚠ ZORUNLU — atlanırsa yapışkan komut

  CASE gv_fc.
    WHEN 'DLGKAY'.                    " bu ekranın KENDİ kaydet fcode'u
      PERFORM dlg_validate_and_save CHANGING DATA(lv_ok).
      IF lv_ok = abap_true.
        LEAVE TO SCREEN 0.            " modal kapanır, çağıran ekrana döner
      ENDIF.
      " Başarısız: alanlar ekranda kalır, kullanıcı düzeltip tekrar dener.

    WHEN 'VERMAT'.                    " buton + popup F4 — hedefi FCODE belirler;
      PERFORM dlg_f4_matnr.           " GET CURSOR kullanma (imleç başka alanda
                                       " olabilir → sessiz yanlış yazım / no-op).

    WHEN 'BACK' OR 'CANCEL'.
      LEAVE TO SCREEN 0.
    WHEN 'EXIT'.
      LEAVE PROGRAM.
    WHEN OTHERS.                      " tanımsız fcode'da hiçbir şey yapılmaz
  ENDCASE.
ENDMODULE.

*&--- Buton + popup F4 (_F01) — Z arama yardımı (SHLP) YARATILAMADIĞINDA ---
*  Z SHLP ADT araç setiyle yaratılamaz (dynpro-dialog-fields.md §2.1). Süzgeçli
*  F4 gerekiyorsa çare buton + popup'tır.
*  REUSE_ALV_POPUP_TO_SELECT tercih — F4IF_INT_TABLE_VALUE_REQUEST değil:
*  (a) PAI'den ekran adreslemesi gereksiz (hedef fcode'dan belli), (b) tek
*  seçimde birden çok alan yazılacaksa RETFIELD modeli bunu ifade edemez.
FORM dlg_f4_matnr.
  TYPES: BEGIN OF ty_f4,
           matnr TYPE matnr,
           maktx TYPE maktx,
         END OF ty_f4.
  DATA lt_f4 TYPE STANDARD TABLE OF ty_f4.

* CLEAN CORE: ham MARA/MAKT yerine released ürün + ürün açıklaması CDS'i.
* Aşağıdaki CDS/alan adları kaynak sistemde kullanıldı; hedef sistemde
* adt_get / adt_search_objects ile DOĞRULA. Kapsam süzgeci WHERE'e girer.
  SELECT p~product AS matnr, t~productdescription AS maktx
    FROM i_product AS p
         LEFT OUTER JOIN i_productdescription AS t     " LEFT OUTER — açıklaması
           ON  t~product  = p~product                  " olmayan kayıt listeden
           AND t~language = @sy-langu                  " düşmesin
    INTO TABLE @lt_f4.

  IF lt_f4 IS INITIAL.
    MESSAGE 'Kapsam içinde kayıt bulunamadı.' TYPE 'S' DISPLAY LIKE 'W'.
    RETURN.
  ENDIF.

  DATA lt_fcat TYPE slis_t_fieldcat_alv.
  " ... fcat kurulumu (programın kanonik fcat FORM'una devret) ...

  DATA ls_sel  TYPE slis_selfield.
  DATA lv_exit TYPE char1.
  CALL FUNCTION 'REUSE_ALV_POPUP_TO_SELECT'
    EXPORTING
      i_title             = 'Seçim'
      i_selection         = abap_true
      i_zebra             = abap_true
      i_tabname           = 'LT_F4'
      it_fieldcat         = lt_fcat
      i_callback_program  = sy-repid
    IMPORTING
      es_selfield         = ls_sel
      e_exit              = lv_exit
    TABLES
      t_outtab            = lt_f4
    EXCEPTIONS
      program_error       = 1
      OTHERS              = 2.
  IF sy-subrc <> 0 OR lv_exit = abap_true OR ls_sel-tabindex <= 0.
    RETURN.                           " kullanıcı vazgeçti — alan değişmez
  ENDIF.

  READ TABLE lt_f4 INTO DATA(ls_f4) INDEX ls_sel-tabindex.
  IF sy-subrc = 0.
    zsd001_s_dlg-ver_matnr = ls_f4-matnr.
  ENDIF.
ENDFORM.

*&--- Doğrulama → kaydetme akışı (_F01) ------------------------------------
*  SIRA: (1) saf girdi kontrolü (DB'ye bakmaz) → (2) kilit → (3) DB'ye bakan
*    kontrol (bakiye/çakışma) → (4) yaz → (5) commit/unlock. DB kontrolü kilit
*    ALINDIKTAN SONRA (yarış koşulu).
FORM dlg_validate_and_save CHANGING cv_ok TYPE abap_bool.
  CLEAR cv_ok.

* ① Zorunlu alan / saf girdi kontrolü.
  IF zsd001_s_dlg-ver_matnr IS INITIAL OR zsd001_s_dlg-hed_referans IS INITIAL.
    MESSAGE 'Zorunlu alanlar eksik.' TYPE 'S' DISPLAY LIKE 'E'.
    RETURN.
  ENDIF.

* ② Kilit (programa özgü lock object / ENQUEUE_*).
* ③ DB'ye bağlı kontrol (iş kuralı sınıfta kalır; ekran modülü yalnız çağırır).
* ④ Yaz: BAPI ya da iş mantığı sınıfının metodu. Standart tabloya doğrudan
*    INSERT/UPDATE/DELETE/MODIFY YASAK (kesin yasak B: BAPI → RFC FM → BDC → manuel).
* ⑤ COMMIT / unlock — TRY/CATCH ile; unlock her koşulda (CATCH içinde de).

  cv_ok = abap_true.
ENDFORM.
