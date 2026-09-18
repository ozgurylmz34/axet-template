FUNCTION zbc000_fm_screen_gen
  IMPORTING
    VALUE(iv_program) TYPE scrhprog
    VALUE(iv_dynpro) TYPE scrfdynnr DEFAULT '0100'
    VALUE(iv_transport) TYPE trkorr OPTIONAL
    VALUE(iv_title) TYPE rsmpe_titt-text DEFAULT 'Liste'
    VALUE(iv_screen_type) TYPE char10 DEFAULT 'DOCKING'
    VALUE(iv_cc_name) TYPE scrcname DEFAULT 'CC_ALV'
    VALUE(iv_mode) TYPE char10 DEFAULT 'WRITE'
    VALUE(iv_recreate) TYPE char1 DEFAULT ' '
    VALUE(iv_src_prog) TYPE scrhprog OPTIONAL
    VALUE(iv_src_status) TYPE rsmpe_sta-code DEFAULT 'STANDARD'
    VALUE(iv_cua_merge) TYPE char1 DEFAULT 'X'
    VALUE(iv_nav_remap) TYPE char1 DEFAULT ' '
  EXPORTING
    VALUE(ev_rc) TYPE i
    VALUE(ev_message) TYPE string
  TABLES
    it_buttons TYPE zbc000_tt_screen_button OPTIONAL
    it_fields TYPE zbc000_tt_screen_field OPTIONAL.



*======================================================================
* ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
* değiştir (naming.md §3). Aynı gövde şu adlarda da değişir:
* ZBC000_FG_SCREEN_GEN, ZBC000_TT_SCREEN_BUTTON, ZBC000_TT_SCREEN_FIELD,
* ZBC000_S_SCREEN_BUTTON, ZBC000_S_SCREEN_FIELD.
* DOĞRULANMADI: bu kopya SAP'de derlenmedi / canlı çalıştırılmadı. Kaynak
* ekipte canlı çalışan sürümden yalnız obje adları, varsayılan donör
* (c_def_src_prog + IV_SRC_STATUS varsayılanı), bir mesaj metnindeki karar
* atfı ve yorumlar değiştirildi (references/screen-gen-kit.md §8).
*======================================================================
* PARAMETRE NOTLARI (imza blogunun ICINE yorum konmaz — ADT'nin imza
* ayristiricisiyla test edilmedigi icin bilerek disarida tutuldu).
*======================================================================
* --- DONÖR PARAMETRELERI -------------------------------------------------
* Donör IV_SRC_PROG / IV_SRC_STATUS parametrelerinden gelir.
* IV_SRC_PROG BOS gelirse asagida c_def_src_prog ('SAPLKKBL') atanir;
* IV_SRC_STATUS varsayilani 'STANDARD'. Parametresiz cagri = legacy donör
* (SAPLKKBL/STANDARD) -> IV_NAV_REMAP=' ' iken remap KENDILIGINDEN ACILIR.
* Kit farki: kaynak ekipte varsayilan donör o sistemdeki minimal bir musteri
* raporunun STATUS_0100'u idi (&F2..&F5). O program baska sistemde yoktur ->
* varsayilan her sistemde bulunan standart donöre cekildi.
*
* --- DAVRANIS ANAHTARLARI (IKISI DE OPSIYONEL) ----------------------------
* IV_CUA_MERGE: 'X' (varsayilan) = hedef programin MEVCUT status/titlebar'lari
*   KORUNUR (asagidaki CUA MERGE blogu). ' ' = merge KAPALI, WRITE cluster'i
*   komple degistirir (merge eklenmeden onceki surumun davranisi). Varsayilan 'X'
*   secildi cunku merge SALT-EKLEYICIdir: yalnizca WRITE'in yok edecegi YABANCI
*   satirlari geri kor; kendi STAT/TIT/PFK/ACT/BUT kodlarimizi zaten eler
*   (idempotent). Hedef programin hic CUA'si yoksa (not_found) merge KENDILIGINDEN
*   atlanir -> ilk uretimde davranis merge'siz surumle BIREBIR AYNI.
*   Kabul edilen degerler: 'X' (ac) · ' ' ya da '-' (KAPAT). Deger once BUYUK HARFE
*   normalize edilir; TANINMAYAN deger merge'i KAPATMAZ (fail-closed) -> merge ACIK
*   kalir ve EV_MESSAGE'da "IV_CUA_MERGE taninmayan deger" uyarisi cikar.
* IV_NAV_REMAP: donörün F3/Shift+F3/F12 tuslarini BACK/EXIT/CANCEL'a cevirme.
*   ' ' (varsayilan) = OTOMATIK: yalniz legacy donörde (SAPLKKBL/STANDARD) uygulanir.
*   'X' = ZORLA AC  (donör ne olursa olsun remap et)
*   '-' = ZORLA KAPA (legacy donörde bile remap etme)
*   Deger BUYUK HARFE normalize edilir; TANINMAYAN deger OTOMATIK'e duser ve
*   EV_MESSAGE'da `DIKKAT: IV_NAV_REMAP taninmayan deger ('…') -> OTOMATIK karara
*   dusuldu` olarak GORUNUR. Bu uyari (IV_CUA_MERGE'inki ile birlikte) BASARI
*   yolunda da ERKEN CIKISLARDA da yazilir; `nav_remap=` token'i TEKTIR ve yalniz
*   UYGULANAN karari (ON/OFF) tasir.
*   Neden gerekli: hedef programin PAI'si hangi fcode'u bekliyorsa remap ona gore
*   olmali. Kaynak ekipte olculen: sablon programlar ve ayni ailedeki klasik
*   raporlar 'BACK'/'EXIT'/'CANCEL' bekliyordu; minimal bir musteri donöründen
*   uretilmis baska bir rapor '&F2'/'&F3'/'&F4'/'&F5' bekliyordu. Tek bir sabit
*   kural iki aileden birini bozardi -> anahtar cagirana birakildi.
*
* --- IV_PROGRAM Z/Y KORUMASI ---------------------------------------------
* HEDEF program (IV_PROGRAM) Z*/Y* ile baslamak ZORUNDA. Baslamiyorsa FM hicbir sey
* yazmadan EV_RC=301 ile doner (kesin yasak A: standart obje yazilmaz).
* DONÖR (IV_SRC_PROG) bu kurala TABI DEGIL -- yalnizca OKUNUR, dolayisiyla standart
* donör (SAPLKKBL/STANDARD) mesru kalir.

* GENERIC ekran/GUI-status URETECI (herhangi bir klasik Z programi icin). Programa
* OZEL metin GOMULMEZ: ekran basligi/titlebar cagiran tarafindan IV_TITLE ile gecilir.
* RFC-enabled; /sap/bc/soap/rfc (dialog context, sap-language=TR) ile cagrilir.
* IV_SCREEN_TYPE: DOCKING (container yok) / CONTAINER (1 custom control CC_ALV).
* (Split AYRI tip degil: CONTAINER kullan + programda cl_gui_splitter_container.)
* 1) RPY_DYNPRO_INSERT -> hedef programda Dynpro (screen) + container(lar) + PBO/PAI.
* 2) RS_CUA_INTERNAL_FETCH/WRITE/GENERATE -> donör GUI status'unu (IV_SRC_PROG/IV_SRC_STATUS)
*    referansla kopyalayip STAT<dynnr> + TIT<dynnr> olarak hedef programa yazar
*    (kesin yasak A: standart donör yalnizca OKUNUR, degistirilmez).
*
* VARSAYILAN DONÖR = SAPLKKBL/STANDARD ("Standard for General List Output";
* her sistemde bulunan standart program, yalnizca OKUNUR). BACK/EXIT icerir ama
* buyuk bir fonksiyon havuzu getirir (FUN~185); nav remap OTOMATIK acilir ->
* PAI'si BACK/EXIT/CANCEL bekleyen programla calisir. &F2..&F5 bekleyen bir
* program icin o fcode'lari tasiyan donörü IV_SRC_PROG/IV_SRC_STATUS ile ACIKCA
* ver (remap o donörde OTOMATIK kapali kalir -- bkz. IV_NAV_REMAP).
* HER SEY IV_DYNPRO'ya gore DINAMIK: screen no + flow modulleri (status_<n>/user_command_<n>)
* + status (STAT<n>) + title (TIT<n>). Farkli ekran icin FM kodu DEGISMEZ. IV_MODE:
* WRITE (uret) / READ (oku) / DELETE (sil).
* classrun bu iki adimi YAPAMAZ (dialog sart -> "Session Timed Out"). Recete:
* references/screen-gen-kit.md · references/dynpro-gui-status.md.
* IT_BUTTONS (TABLES, opsiyonel): cagiran OZEL app-toolbar butonlari verirse status'a
* kurulur (fcode/text/icon/quickinfo/fkey). BOS verilirse -> ONCEKI davranis birebir:
* app-toolbar YOK (sadece ALV grid'in kendi toolbar'i). Geriye-donuk uyumlu.
* IT_FIELDS (TABLES, opsiyonel): cagiran ekran ALANI (etiket/giris/checkbox/radio...)
* verirse dynpro'ya kurulur. BOS verilirse -> ONCEKI davranis birebir: alan YOK
* (LT_F2C'ye hic dokunulmaz, LT_CONT degismez). IT_BUTTONS ile ayni emsal.
* Satir tipi ZBC000_S_SCREEN_FIELD, alan adlari RPY_DYFATC ile BIREBIR AYNI ->
* MOVE-CORRESPONDING ile dogrudan aktarilir (donusum/tahmin yok).
* ON-DOGRULAMA (alan verildiginde): konum (LINE/COLUMN) · TEMPLATE'te uzunluk
* (LENGTH ya da FROM_DICT) · container'in gercekten var olmasi. Kusur varsa
* EV_RC=5 + kusurlu alan ADLARI ve HICBIR SEY YAZILMAZ (yarim ekran yok).
* Olcut: "RPY bunu sessizce mi yutuyor?" -- sessiz basarisizlik = sert red.
* SELECT-OPTIONS KAPSAM DISI (bilincli karar): tek bir select-option ekranda 6 ayri
* F2C satiri uretir (TEXT / OPTI_PUSH / LOW / TO_TEXT / HIGH / VALU_PUSH). Bu FM o
* 6'yi ACMAZ; select-option isteyen cagiran 6 satiri KENDISI verir. Sebep: acilim
* kurallari (pozisyon, fcode, ikon) rapor-ekranina gore degisir; FM'e gomulunce
* jenerikligi bozar.
  CONSTANTS:
*   Donör IV_SRC_PROG / IV_SRC_STATUS parametrelerinden gelir. Legacy donör adlari
*   sabit olarak asagida durur — yalniz "bu cagri legacy donör mu?" TESPITI icin
*   kullanilir, donör SECIMI icin DEGIL.
    c_legacy_prog   TYPE scrhprog         VALUE 'SAPLKKBL',
    c_legacy_status TYPE rsmpe_sta-code   VALUE 'STANDARD',
*   Varsayilan donör (IV_SRC_PROG bos gelirse atanir). Kit farki: kaynakta bir
*   musteri programi idi; burada her sistemde bulunan standart SAPLKKBL.
*   IV_SRC_STATUS varsayilani 'STANDARD' ile birlikte legacy donörü verir.
    c_def_src_prog  TYPE scrhprog         VALUE 'SAPLKKBL',
*   Dynpro'nun KENDISI = "kok container". Tipi icin 3 esdeger deger mesru gorunuyor
*   (' ' | 'DYNPRO' | 'SCREEN'), adi 'SCREEN'. Dayanak: type-pool RPYTY
*   (rpyty_dynp_ctype-root/-dynpro/-screen) + LSIFPTOP CONT_SCREEN_NAME.
*   ⚠️ Ilk yazildiginda DOGRULANMADI idi: domain SCRCTYPE'in SABIT DEGER listesinde
*   'SCREEN' YOK -- olculen 10 deger: ' ' DYNPRO LOOP RADIOGROUP SUBSCREEN
*   TABLE_CTRL FIELD_CTRL ABAP_CTRL STRIP_CTRL CUST_CTRL. Kaynak ekipte sonradan
*   IT_FIELDS ile canli alan ekrani uretilerek olculdu ve kabul edildi.
*   Hata modu GURULTULU: rc=6 (illegal_field_value) veya rc=7 (field_not_allowed)
*   gelirse sirasiyla ' ' ve 'DYNPRO' denenir -> sessiz bozulma yok.
    c_cont_root  TYPE scrctype        VALUE 'SCREEN',
    c_cont_rname TYPE scrcname        VALUE 'SCREEN'.
* CUA MERGE: CUA program GENELINE aittir ve RS_CUA_INTERNAL_WRITE
* programin TUM CUA'sini degistirir (delta DEGIL). Bu yuzden FM, yazmadan once
* hedef programin MEVCUT CUA'sini okuyup yeni status'un yanina EKLER -> ayni
* programda 0200 + 0300 + 0400 BIRLIKTE yasar. Merge olmadan her yeni ekran
* oncekilerin status/titlebar'ini SILIYORDU (canli regresyon, 0300 -> STAT0200).
* Her dynpro KENDI set kodlarini alir: PFK<dynnr> / ACT<dynnr> / B<dynnr son 3>.
* Programin hic CUA'si yoksa merge ATLANIR -> ilk uretim onceki davranisla ayni.
* Status + titlebar adlari da screen number'a gore DINAMIK: STAT<dynnr> / TIT<dynnr>
* (ekran 0200 -> STAT0200/TIT0200). Sabit degil -> her ekran kendi status/title'i,
* FM kodu degismez. Programdaki SET PF-STATUS/TITLEBAR ayni adi kullanmali.
  DATA: l_status TYPE rsmpe_sta-code,
        l_tit    TYPE rsmpe_tit-code.

  DATA: ls_header TYPE rpy_dyhead,
        lt_cont   TYPE dycatt_tab,
        lt_f2c    TYPE dyfatc_tab,
        lt_flow   TYPE STANDARD TABLE OF rpy_dyflow,
        ls_flow   TYPE rpy_dyflow,
        l_screen_rc TYPE i,
        l_stat_rc   TYPE i,
        l_gen_rc    TYPE i,
        adm  TYPE rsmpe_adm,
        sta  TYPE STANDARD TABLE OF rsmpe_stat,
        fun  TYPE STANDARD TABLE OF rsmpe_funt,
        men  TYPE STANDARD TABLE OF rsmpe_men,
        mtx  TYPE STANDARD TABLE OF rsmpe_mnlt,
        act  TYPE STANDARD TABLE OF rsmpe_act,
        but  TYPE STANDARD TABLE OF rsmpe_but,
        pfk  TYPE STANDARD TABLE OF rsmpe_pfk,
        sett TYPE STANDARD TABLE OF rsmpe_staf,
        doc  TYPE STANDARD TABLE OF rsmpe_atrt,
        tit  TYPE STANDARD TABLE OF rsmpe_titt,
        biv  TYPE STANDARD TABLE OF rsmpe_buts,
        l_trkey TYPE trkey,
*       MEVCUT (hedef programin) CUA'si — MERGE icin AYRI tablolara okunur.
*       ⚠ AYRI olmak ZORUNDA: RS_CUA_INTERNAL_FETCH ilk isi olarak cikti
*       tablolarini REFRESH eder [KANIT: RS_CUA_INTERNAL_FETCH:63] -> donörden
*       kurdugumuz yeni status ayni tablolara okunsaydi SILINIRDI.
*       📌 O REFRESH satiri ON BIR tablonun HEPSINI kapsar -- `biv` DAHIL:
*         `REFRESH: men, act, but, pfk, set, tit, sta, fun, mtx, doc, biv.`
*         ve `not_found` / IMPORT cikislarindan ONCE gelir (:64 ve :117)
*         -> BU IKI yolda artik (stale) veri kalamaz.
*       ⛔ AMA "stale MUMKUN DEGIL" DIYE GENELLEME YAPMA -- UCUNCU bir cikis var:
*         `unknown_version` (:51-57) REFRESH'ten (:63) ONCE raise ediliyor. TABLES
*         parametreleri REFERANSLA gectigi icin o yolda cagiranin tablolari
*         DOKUNULMADAN kalir. Bu FM'de sorun DEGIL, cunku her iki fetch de
*         TEK-KULLANIMLIK TAZE tabloya okuyor: 1. fetch fonksiyon-yerel `sta…biv`,
*         2. fetch yalnizca burada doldurulan `o_*`. Yani gerekce "REFRESH her
*         zaman kosar" DEGIL, "hedef tablolar zaten bos".
*         ⚠ IKINCI BIR FETCH EKLEYECEK OLAN: bu muafiyet SENIN tablona gecmez --
*           daha once doldurulmus bir tabloya okuyorsan `unknown_version` donen
*           cagrida eski satirlar MERGE'e sizar ve WRITE cluster'i kirli icerikle
*           REPLACE eder = bu FM'in var olma sebebi olan SESSIZ CUA KAYBI.
*           O durumda cagiran tarafta REFRESH ZORUNLU.
*         [olculdu; standart kaynak SADECE OKUNDU]
        o_adm  TYPE rsmpe_adm,
        o_sta  TYPE STANDARD TABLE OF rsmpe_stat,
        o_fun  TYPE STANDARD TABLE OF rsmpe_funt,
        o_men  TYPE STANDARD TABLE OF rsmpe_men,
        o_mtx  TYPE STANDARD TABLE OF rsmpe_mnlt,
        o_act  TYPE STANDARD TABLE OF rsmpe_act,
        o_but  TYPE STANDARD TABLE OF rsmpe_but,
        o_pfk  TYPE STANDARD TABLE OF rsmpe_pfk,
        o_sett TYPE STANDARD TABLE OF rsmpe_staf,
        o_doc  TYPE STANDARD TABLE OF rsmpe_atrt,
        o_tit  TYPE STANDARD TABLE OF rsmpe_titt,
        o_biv  TYPE STANDARD TABLE OF rsmpe_buts,
*       MEVCUT CUA fetch sonucu. DORT AYRI DURUM -- birbirine KARISTIRMA:
*         -1 = merge adimina HIC girilmedi (donör fetch basarisiz -> status adimi kosmadi)
*          0 = mevcut CUA okundu, merge edildi
*          1 = programin HENUZ CUA'si yok (not_found) -> merge ATLANDI, normal ilk uretim
*         >1 = fetch HATASI -> asagida ERKEN CIKIS (yazilsaydi mevcut CUA silinirdi)
        l_merge_rc  TYPE i,
        l_merge_sta TYPE i,              " korunan YABANCI status sayisi (rapor)
        l_merge_tit TYPE i,              " korunan YABANCI titlebar sayisi (rapor)
        l_f2c_bad  TYPE string,          " on-dogrulamada takilan IT_FIELDS satirlari
        l_ftype    TYPE scrntype,        " ETKIN alan tipi (bos ise default TEMPLATE)
        l_io_def   TYPE i,               " I/O default'u UYGULANAN alan sayisi (raporlanir)
        l_devcl_miss TYPE abap_bool,     " TADIR'da program kaydi YOK -> tr_key-devclass bos
        l_legacy_donor TYPE abap_bool,   " donör = SAPLKKBL/STANDARD mi (canlidan korundu)
        l_nav_remap    TYPE abap_bool,   " F3/Sh+F3/F12 -> BACK/EXIT/CANCEL uygulanacak mi
        l_setcode_miss TYPE string,      " donör status'te pfk/act set kodu YOK -> raporlanir
*       --- ANAHTAR PARAMETRELERIN NORMALIZE EDILMIS KOPYALARI -------------------
*       IMPORTING parametreleri YERINDE DEGISTIRILMEZ: EV_MESSAGE'da cagiranin HAM
*       girisi gorunmeli ki "ne gonderdim" ile "nasil yorumlandi" ayirt edilebilsin.
        l_cua_merge    TYPE char1,       " to_upper( IV_CUA_MERGE ), normalize
        l_nav_arg      TYPE char1,       " to_upper( IV_NAV_REMAP ), normalize
        l_cua_bad_arg  TYPE abap_bool,   " IV_CUA_MERGE taninmayan -> merge ACIK kalir + raporlanir
        l_nav_bad_arg  TYPE abap_bool,   " IV_NAV_REMAP taninmayan -> OTOMATIK + raporlanir
*       Taninmayan-giris tanilari TEK STRING'de toplanir. Sebep: bu bilgi yalnizca
*       BASARI yolunda degil, ERKEN CIKISLARDA da gorunmeli -- cagiran donör hatasi
*       alip da parametresinin taninmadigini ogrenemezse ikinci denemeyi ayni yanlisla
*       yapar. Tek yerde kurulur, her cikis yolunda EV_MESSAGE'a eklenir.
        l_arg_diag     TYPE string,      " taninmayan giris uyarilari (tum cikis yollari)
        l_prog_up      TYPE scrhprog.    " to_upper( IV_PROGRAM ) — Z/Y guard'i icin

  CLEAR: ev_rc, ev_message.

*--- IV_PROGRAM Z/Y KORUMASI (kesin yasak A) — HER SEYDEN ONCE ------------------
* Bu FM RFC-enabled JENERIK bir SAP YAZICISIdir: RPY_DYNPRO_INSERT (dynpro yaz),
* RS_SCRP_DELETE (dynpro sil), RS_CUA_INTERNAL_WRITE + RS_CUA_GENERATE (program
* GENELINE ait CUA) hedef programda KALICI degisiklik yapar. IV_PROGRAM'a standart
* (Z/Y ile BASLAMAYAN) bir ad verilirse bu cagrilar STANDART OBJEYE yazar = kesin
* yasak A ihlali; ustelik CUA WRITE delta DEGIL REPLACE oldugu icin o programin
* TUM status/titlebar'i gider. Cagiran disaridan (SOAP-RFC) geldigi icin niyetine
* guvenilemez -> kapi FM'in KENDISINDE durur.
* KAPSAM (bilincli): guard IV_MODE dallarindan ONCE. READ dali da kapsanir; gerekce
* "hangi mod yazici" listesini bakima muhtac ucuncu bir dal olarak tasimamak
* (DELETE ve WRITE zaten yazicidir). Kaynak ekipte olculen cagiranlarin HEPSI Z
* program veriyordu (kayit TAM DEGIL) -> guard mesru cagrilari etkilemez.
* Karsilastirma to_upper KOPYA uzerinden: RFC char alani kucuk harf tasiyabilir ve
* 'zxx001_...' HATALI reddedilirdi. IV_PROGRAM'in KENDISI degistirilmez.
* ⚠ DONÖR (IV_SRC_PROG) BU GUARD'A TABI DEGIL: donör yalnizca OKUNUR
*   (RS_CUA_INTERNAL_FETCH), yazilmaz -> standart donör (SAPLKKBL/STANDARD) mesru
*   ve bugun de kullanilabilen bir yol; guard konsaydi CALISAN bir cagri kirilirdi.
* EV_RC bandi: 301 = giris parametresi gecersiz (300 = IV_DYNPRO ile ayni bant;
* ikisi de TEK BASINA doner, hicbir adim kosmadan).
  l_prog_up = to_upper( iv_program ).
  IF l_prog_up(1) <> 'Z' AND l_prog_up(1) <> 'Y'.
    ev_rc = 301.
    ev_message = |IV_PROGRAM gecersiz ('{ iv_program }') -- HICBIR SEY YAPILMADI. | &&
                 |Bu uretec YALNIZ musteri objelerine (Z*/Y*) yazar. Standart bir | &&
                 |programa dynpro/CUA yazmak kesin yasak A ihlalidir ve CUA | &&
                 |WRITE delta olmadigi icin o programin TUM GUI status/titlebar'ini | &&
                 |silerdi.|.
    RETURN.
  ENDIF.

* L_MERGE_RC baslangici -1 = "merge adimina HIC girilmedi". 0 OLAMAZ: 0'in anlami
* "mevcut CUA okundu ve merge edildi"dir -> donör fetch'i basarisiz olup (satir ~444)
* status adimina hic girilmediginde sonuc mesaji merge hic kosmadigi halde
* `cua_merge=ok kept_status=0` derdi (kanitsiz guven). Uc durum artik ayirt edilir.
  l_merge_rc = -1.

*--- DAVRANIS ANAHTARLARININ NORMALIZASYONU + FAIL-CLOSED OKUMA ---------------
* ⛔ DUZELTILEN DAVRANIS: `IF iv_cua_merge <> 'X'` ve nav-remap SWITCH'inin `ELSE`
*   dali TANINMAYAN her degeri SESSIZCE yikici/otomatik tarafa dusuruyordu. "Acmak
*   icin" gonderilmis 'x' (kucuk harf) / 'J' / '1' gibi bir deger CUA MERGE'i
*   KAPATIYOR, hedef programin diger status/titlebar'lari siliniyor ve EV_RC yine
*   0 donuyordu (sessiz yikim + kanitsiz basari).
* KURAL: (a) once BUYUK HARFE normalize et, (b) KORUYUCU olmayan yol yalniz ACIK
*   istekle secilir; taninmayan deger koruyucu tarafta kalir ve EV_MESSAGE'da GORUNUR.
  l_cua_merge = to_upper( iv_cua_merge ).
  l_nav_arg   = to_upper( iv_nav_remap ).
* IV_CUA_MERGE: merge'i yalniz ACIK kapatma (' ' = bos ya da '-') kapatir; 'X' = ac
* (varsayilan); BASKA HER SEY = taninmayan -> merge ACIK KALIR (fail-closed).
  IF l_cua_merge IS NOT INITIAL AND l_cua_merge <> 'X' AND l_cua_merge <> '-'.
    l_cua_bad_arg = abap_true.
    l_cua_merge   = 'X'.
  ENDIF.
* IV_NAV_REMAP: ' ' = OTOMATIK, 'X' = zorla ac, '-' = zorla kapa; BASKA HER SEY =
* taninmayan -> OTOMATIK'e duser (eski sonucla ayni) ama artik SESSIZ DEGIL.
  IF l_nav_arg IS NOT INITIAL AND l_nav_arg <> 'X' AND l_nav_arg <> '-'.
    l_nav_bad_arg = abap_true.
    l_nav_arg     = space.
  ENDIF.
*--- TANI METNI: HER cikis yolunda raporlanir (erken cikislar DAHIL) -----------
* ⚠ METIN "merge KAPATILMADI" der, "merge ACIK" DEMEZ. Fark onemli: bu tani
*   PARAMETRENIN NASIL YORUMLANDIGINI anlatir, merge'in gercekten kosup kosmadigini
*   DEGIL. Donör fetch'i basarisiz olursa (l_merge_rc = -1) merge zaten hic kosmaz;
*   orada "MERGE ACIK birakildi" demek mesajin kendi `cua_merge=KOSMADI` ciktisiyla
*   CELISIRDI. Alternatif -- taniyi `l_merge_rc >= 0` ile susturmak -- REDDEDILDI:
*   tam da hata yollarinda cagiran girdisinin taninmadigini ogrenmeli.
  IF l_cua_bad_arg = abap_true.
    l_arg_diag = |; DIKKAT: IV_CUA_MERGE taninmayan deger ('{ iv_cua_merge }') -> | &&
                 |merge KAPATILMADI (koruyucu varsayilan; taninmayan deger merge'i | &&
                 |kapatmaz). Kapatmak icin ACIKCA ' ' ya da '-' verin|.
  ENDIF.
  IF l_nav_bad_arg = abap_true.
    l_arg_diag = l_arg_diag && |; DIKKAT: IV_NAV_REMAP taninmayan deger | &&
                               |('{ iv_nav_remap }') -> OTOMATIK karara dusuldu | &&
                               |(gecerli: ' '=OTOMATIK 'X'=ZORLA-AC '-'=ZORLA-KAPA)|.
  ENDIF.

*--- DONÖR COZUMLEMESI -------------------------------------------------------
* IV_SRC_PROG bos gelirse varsayilan donör (c_def_src_prog) atanir. Blok HER dala
* (READ/DELETE dahil) ulasabilsin diye IV_DYNPRO dogrulamasindan ONCE durur.
  IF iv_src_prog IS INITIAL.
    iv_src_prog = c_def_src_prog.
  ENDIF.
  l_legacy_donor = COND abap_bool( WHEN iv_src_prog = c_legacy_prog AND iv_src_status = c_legacy_status
                                     THEN abap_true ELSE abap_false ).

*--- NAVIGASYON REMAP KARARI (IV_NAV_REMAP) ----------------------------------
* ' ' = OTOMATIK -> l_legacy_donor (remap yalniz SAPLKKBL/STANDARD'da). Parametre
*       VERILMEZSE varsayilan donör legacy oldugu icin remap ACIK olur.
* 'X' / '-' = cagiranin acik iradesi (bkz. imza notlari: BACK/EXIT/CANCEL bekleyen
*       aile ile &F2..&F5 bekleyen aile).
* ⚠ SWITCH artik NORMALIZE EDILMIS L_NAV_ARG uzerinde: 'x'/'X' ayni sonucu verir ve
*   taninmayan giris yukarida ISARETLENDI (l_nav_bad_arg) -> ELSE dali artik yalniz
*   MESRU 'otomatik' (' ') girisini tasiyor, sessiz cop-degeri degil.
  l_nav_remap = SWITCH abap_bool( l_nav_arg
                                  WHEN 'X' THEN abap_true
                                  WHEN '-' THEN abap_false
                                  ELSE l_legacy_donor ).

*--- IV_DYNPRO on-dogrulamasi -------------------------------------------
* Butcode asagida |B{ iv_dynpro+1(3) }| ile uretilir. SCRFDYNNR CHAR 4'tur ve cagiran
* SOLA DAYALI '300' verirse alan '300 ' olur -> +1(3) = '00 ' -> '400 ' ile AYNI
* butcode ('B00 ') -> iki ekran ayni app-toolbar'i paylasir = bu FM'de zaten bir kez
* duzeltilen toolbar-cakismasi sinifinin ta kendisi (satir ~458). Ayrica status/titlebar
* adlari (STAT300) dynpro'nun gercek adiyla (0300) uyusmaz.
* SESSIZ NORMALIZASYON YERINE GURULTULU RED secildi -- gerekce:
*   (a) IV_DYNPRO ~20 yerde kullaniliyor (flow modul adlari, ls_header-screen, STAT/TIT,
*       PFK/ACT/BUT kodlari); parametreyi yerinde duzeltmek bunlarin hepsini ORTULU
*       etkiler ve hangi adin uretildigi cagiran icin belirsizlesir.
*   (b) Red, BUGUNKU cagiranlari ('0100'/'0300'/'0400' = tam 4 hane) HIC etkilemez
*       -> geriye-donuk uyumlu; hatali cagiran ise sessiz cakisma yerine ANINDA rc alir.
* EV_RC bandi: 300 = giris parametresi gecersiz (hicbir adim kosmadi). Dosyadaki
* mevcut "adim-bandi" desenine uyar (100+rc = donör fetch, 200+rc = merge fetch).
  IF strlen( iv_dynpro ) <> 4 OR NOT iv_dynpro CO '0123456789'.
    ev_rc = 300.
    ev_message = |IV_DYNPRO gecersiz ('{ iv_dynpro }') -- HICBIR SEY YAPILMADI. | &&
                 |Tam 4 hane RAKAM olmali (ornek '0300'). Sola dayali '300' verilirse | &&
                 |butcode 'B00 ' uretilir ve BASKA bir ekranin app-toolbar'i ile | &&
                 |cakisir (o ekranin butonlari kaybolur).|.
    RETURN.
  ENDIF.

  l_status = |STAT{ iv_dynpro }|.
  l_tit    = |TIT{ iv_dynpro }|.

*--- IV_MODE='READ': mevcut Dynpro'nun container/alan/size verisini OKU (yazma yok) --
* (Manuel SE51 duzeltmelerinden sonra gercek konum/boyutu ogrenmek icin.)
  IF iv_mode = 'READ'.
    CALL FUNCTION 'RPY_DYNPRO_READ'
      EXPORTING
        progname              = iv_program
        dynnr                 = iv_dynpro
        suppress_exist_checks = 'X'
        suppress_corr_checks  = 'X'
      IMPORTING
        header                = ls_header
      TABLES
        containers            = lt_cont
        fields_to_containers  = lt_f2c
        flow_logic            = lt_flow
      EXCEPTIONS
        cancelled             = 1
        not_found             = 2
        permission_error      = 3
        OTHERS                = 4.
    ev_rc = sy-subrc.
    IF sy-subrc = 0.
      ev_message = |HEADER lines={ ls_header-lines } cols={ ls_header-columns }; container={ lines( lt_cont ) }|.
      LOOP AT lt_cont INTO DATA(ls_cr).
        ev_message = ev_message && | [{ ls_cr-type } { ls_cr-name } L{ ls_cr-line } C{ ls_cr-column } H{ ls_cr-height } W{ ls_cr-length } el{ ls_cr-element_of }|.
        ev_message = ev_message && | rv{ ls_cr-c_resize_v } rh{ ls_cr-c_resize_h } lmin{ ls_cr-c_line_min } cmin{ ls_cr-c_coln_min }]|.
      ENDLOOP.
*     EKRAN ALANLARI (fields_to_containers): RPY_DYNPRO_READ zaten LT_F2C'yi dolduruyordu
*     ama EV_MESSAGE'a HIC yazilmiyordu -> cagiran "rc=0" gorup alan bilgisini alamiyordu.
*     Satir tipi RPY_DYFATC (DYFATC_TAB'in row type'i; alan adlari DD03L'den dogrulandi).
*     Kompakt tek-satir/alan format: EV_MESSAGE string'dir ama okuyan taraf kesebilir.
      ev_message = ev_message && | F2C={ lines( lt_f2c ) }:|.
      LOOP AT lt_f2c INTO DATA(ls_fc).
        ev_message = ev_message && | [{ ls_fc-cont_name }/{ ls_fc-name } t{ ls_fc-type } f{ ls_fc-format }|
                                 && | L{ ls_fc-line } C{ ls_fc-column } len{ ls_fc-length } vis{ ls_fc-vislength }|
                                 && | g1{ ls_fc-group1 } i{ ls_fc-input_fld } o{ ls_fc-output_fld }|
                                 && | req{ ls_fc-requ_entry } pos{ ls_fc-poss_entry } mc{ ls_fc-matchcode }|
                                 && | cx{ ls_fc-conv_exit } rf{ ls_fc-ref_field } "{ ls_fc-text }"]|.
      ENDLOOP.
    ELSE.
      ev_message = |RPY_DYNPRO_READ subrc={ sy-subrc }|.
    ENDIF.
*   CUA titlebar'larini da oku (donör artigi temizligini dogrulamak icin)
    CALL FUNCTION 'RS_CUA_INTERNAL_FETCH'
      EXPORTING program = iv_program language = sy-langu state = 'A'
      TABLES sta = sta fun = fun men = men mtx = mtx act = act
             but = but pfk = pfk set = sett doc = doc tit = tit biv = biv
      EXCEPTIONS OTHERS = 0.
    ev_message = ev_message && | TITLES={ lines( tit ) }:|.
    LOOP AT tit INTO DATA(ls_tt).
      ev_message = ev_message && | { ls_tt-code }|.
    ENDLOOP.
    ev_message = ev_message && | FUN={ lines( fun ) } PFK={ lines( pfk ) } MEN={ lines( men ) } BUT={ lines( but ) }:|.
    LOOP AT fun INTO DATA(ls_ff).
      ev_message = ev_message && | { ls_ff-code }(t={ ls_ff-type })|.
    ENDLOOP.
*   --- FUNDTL: BUTON YENIDEN URETIMI ICIN GEREKEN ALANLAR (ikon dahil) ---------
*   NEDEN: yukaridaki FUN dokumu yalniz `code(t=type)` basiyordu. Bir app-toolbar
*   butonunu AYNEN yeniden uretmek icin bu YETMEZ: `IT_BUTTONS` satiri TEXT + ICON
*   + QUICKINFO ister ve bunlarin canli degeri BASKA HICBIR SALT-OKUMA YOLUNDAN
*   olculemiyor -- CUA verisi EUDB cluster'indadir, `RSMPTEXTS` ikon TASIMAZ ve
*   tum `RSMPE_*` objeleri INTTAB'dir (veri tablosu degil) [DD02L olcumu: 49/49].
*   Bu bosluk somut bir riske yol aciyordu: `fun` satiri PROGRAM-GENELINDEDIR ve
*   asagidaki IT_BUTTONS dali `<fn_btn>-icon_id = ls_btn-icon` ile KOSULSUZ yazar
*   -> mevcut bir fcode'u ikinci bir status'e eklerken ICON'u bilmeden BOS
*   gondermek, o fcode'u KULLANAN DIGER EKRANIN ikonunu SESSIZCE SILERDI.
*   Artik once OLCULUR, sonra aynisi geri verilir.
*
*   ⛔ MEVCUT CIKTI DEGISTIRILMEDI: yukaridaki FUN dongusu ve ` FLOW:` blogu
*     BIREBIR AYNI kaldi; bu AYRI bir blok olarak ARAYA eklendi. Eski cikti
*     ` FUN=...:` ve ` FLOW:` isaretlerini arayan bir tuketici KIRILMAZ
*     (yalnizca aralarinda fazladan bir bolum gorur) -- geriye-donuk uyumlu.
*   ⛔ FILTRE `text_type='S' OR icon_id dolu` -- SALT `icon_id dolu` OLAMAZ:
*     o zaman IKONSUZ bir buton listede HIC gorunmez ve cagiran "ikon yok" ile
*     "raporlanmadi"yi AYIRT EDEMEZDI (bulunamadi != yok). Bu FM'in IT_BUTTONS
*     ile kurdugu her fonksiyon `text_type='S'` tasir (asagida acikca atanir)
*     -> ikonsuz olsa bile satiri CIKAR ve `ico=` BOS gorunur = kesin cevap.
*     Donörün textno-tabanli ~190 fonksiyonu boylece elenir (EV_MESSAGE sismez;
*     satir 207'deki "okuyan taraf kesebilir" uyarisi hala gecerli).
*   ⚠ Alan adlari TAHMIN DEGIL: hepsi bu FM'in KENDI IT_BUTTONS dalinda zaten
*     yaziliyor (`text_type` / `fun_text` / `icon_id` / `icon_text` / `info_text`).
    DATA l_fdtl TYPE i.
    LOOP AT fun TRANSPORTING NO FIELDS
         WHERE text_type = 'S' OR icon_id IS NOT INITIAL.
      l_fdtl = l_fdtl + 1.
    ENDLOOP.
    ev_message = ev_message && | FUNDTL={ l_fdtl }:|.
    LOOP AT fun INTO DATA(ls_fd)
         WHERE text_type = 'S' OR icon_id IS NOT INITIAL.
*     `FN:` ONEKI BILINCLI: container ve F2C dokumleri de `[...]` kullaniyor.
*     Onaysiz bir `\[(.*?)\]` taramasi bu satirlari onlarla KARISTIRIRDI; onek
*     tuketicinin `[FN:` ile kesin filtrelemesini saglar (mevcut tuketici
*     `\[SCREEN/...` ile ankrajli, yani bugun de kirilmiyordu -- bu ek emniyet).
      ev_message = ev_message && | [FN:{ ls_fd-code } tt{ ls_fd-text_type }|
                               && | ico={ ls_fd-icon_id }|
                               && | txt="{ ls_fd-fun_text }"|
                               && | itx="{ ls_fd-icon_text }"|
                               && | inf="{ ls_fd-info_text }"]|.
    ENDLOOP.
    ev_message = ev_message && | FLOW:|.
    LOOP AT lt_flow INTO DATA(ls_fl).
      ev_message = ev_message && | / | && ls_fl-line.
    ENDLOOP.
    RETURN.
  ENDIF.

*--- IV_MODE='DELETE': mevcut Dynpro'yu SIL -- YIKICI, GERI ALINAMAZ ---------------
* DIKKAT: bu dal RS_SCRP_DELETE cagirir ve hedef programdaki ekrani GERCEKTEN SILER
* (flow logic + container + alanlar dahil). "(yazma yok)" ifadesi YALNIZ READ dali
* icin dogrudur; buraya yanlislikla kopyalanmisti -- DELETE zararsiz DEGILDIR.
  IF iv_mode = 'DELETE'.
    CALL FUNCTION 'RS_SCRP_DELETE'
      EXPORTING
        dynnr           = iv_dynpro
        progname        = iv_program
        suppress_checks = 'X'
        with_popup      = space
      CHANGING
        corrnum         = iv_transport
      EXCEPTIONS
        OTHERS          = 0.
    ev_message = |Dynpro { iv_program }/{ iv_dynpro } silindi|.
    RETURN.
  ENDIF.

*--- 1) Dynpro (screen) -------------------------------------------------
  ls_header-program    = iv_program.
  ls_header-screen     = iv_dynpro.
  ls_header-language   = sy-langu.
  ls_header-descript   = iv_title.
  ls_header-type       = 'N'.
  ls_header-nextscreen = iv_dynpro.
  ls_header-lines      = 20.
  ls_header-columns    = 120.

* Modül adlari dynpro numarasina gore (status_<dynnr> / user_command_<dynnr>) ->
* programdaki MODULE tanimlariyla eslesir (0100, 0200, ...).
  ls_flow-line = 'PROCESS BEFORE OUTPUT.'.                  APPEND ls_flow TO lt_flow.
  ls_flow-line = |  MODULE status_{ iv_dynpro }.|.          APPEND ls_flow TO lt_flow.
  ls_flow-line = 'PROCESS AFTER INPUT.'.                    APPEND ls_flow TO lt_flow.
  ls_flow-line = |  MODULE user_command_{ iv_dynpro }.|.    APPEND ls_flow TO lt_flow.

* Custom control'lere ABAP'ta cl_gui_custom_container( container_name='...' ) baglanir.
* element_of BOS birakilir -> RPY otomatik SCREEN-root'a baglar (READ'de el=SCREEN gorunur).
* element_of='SCREEN' ACIKCA verilirse INSERT 'illegal_field_value' (rc=6) verir
* (SCREEN satiri tabloda olmadigi icin). Ekran tam boyuta (200x255) buyutulur ki
* container/ALV tum pencereyi kullansin (TEMP2 manuel duzeltmesinden ogrenildi).
* 2 ekran tipi: DOCKING (container yok) / CONTAINER (tek custom control CC_ALV, tam ekran).
* SPLIT AYRI BIR TIP DEGIL: split ekran tarafinda CONTAINER ile AYNIDIR (tek CC_ALV);
* bolme PROGRAMDA cl_gui_splitter_container ile yapilir (CC_ALV'i N hucreye bol, surukle-
* ayrac). Yani split icin FM'de ozel bir sey YOK -> CONTAINER kullan. (Bkz. ZBC000_P_ALV_TEMP3.)
  CASE iv_screen_type.
    WHEN 'CONTAINER'.
      ls_header-lines   = 200.
      ls_header-columns = 255.
*     c_resize_v/h='X' + c_line_min/c_coln_min=1: custom control pencereyle RESIZE olur
*     (yoksa sabit boyutta kalir -> ALV alani pencereyi doldurmaz/"bittiği yerden devam eder").
*     (TEMP3 manuel duzeltmesinden ogrenildi; bundan sonra hep set.)
      APPEND VALUE #( type = 'CUST_CTRL' name = iv_cc_name cu_cc_name = iv_cc_name
                      line = 1 column = 1 height = 200 length = 255
                      c_resize_v = 'X' c_resize_h = 'X'
                      c_line_min = 1   c_coln_min = 1 ) TO lt_cont.
    WHEN OTHERS.
      " DOCKING -> container yok (program cl_gui_docking_container ekler)
  ENDCASE.

*--- IT_FIELDS: ekran alanlarini uret (LT_F2C) --------------------------
* ⚠️ ORTULU "SCREEN KOKU" YOKTUR -- alan container'siz DUSER, ustelik SESSIZCE.
* KANIT (standart kaynak SADECE OKUNDU; kesin yasak A'ya uygun):
*   RPY_DYNPRO_CVT_FROM_EXTFORMAT satir 86-88:
*     LOOP AT fields_to_containers WHERE cont_name = <container>-name
*                                    AND cont_type = <container>-type.
*   Bu dongu CONTAINERS dongusunun ICINDEdir. Yani bir F2C satiri, CONTAINERS
*   tablosunda AYNI (name,type) ikilisine sahip satir YOKSA HIC islenmez ->
*   alan uretilmez ama INSERT rc=0 doner (sahte-OK). Bu yuzden alan verildiginde
*   kok container satirini BIZ ekleriz.
* Kok container EKLEMEK ZARARSIZ: ondan dynpro alani URETILMEZ
*   (LSIFPF11 i_cont_to_field -> "when others. nothing") ve container-ozel
*   oznitelik atanmaz (i_assign_field_cont_attributes -> root/dynpro/screen:
*   "nothing to do"). Sadece eslesme kovasi gorevi gorur.
* GERIYE-DONUK UYUMLULUK: blogun TAMAMI IT_FIELDS DOLU iken calisir. BOS ise
* LT_CONT'a da LT_F2C'ye de HIC dokunulmaz -> RPY_DYNPRO_INSERT bugunku cagrinin
* AYNISINI alir. (IT_BUTTONS emsali.)
  IF it_fields[] IS NOT INITIAL.
*   (a) Kok container'i garanti et (yukaridaki "sessiz dusme" kaniti).
*       ON-DOGRULAMADAN ONCE yapilir: orphan kontrolu LT_CONT'un TAM halini ister.
    IF NOT line_exists( lt_cont[ type = c_cont_root name = c_cont_rname ] ).
      APPEND VALUE #( type = c_cont_root name = c_cont_rname ) TO lt_cont.
    ENDIF.

*   (b) ON-DOGRULAMA -- hepsi INSERT'ten ONCE bilinebilen, satiri kullanilamaz
*       kilan kusurlar. Tek turda TOPLANIR (ilk hatada durmaz -> cagiran hepsini
*       birden gorur), sonra ERKEN RETURN -> hicbir yazma yapilmaz, yarim ekran yok.
*       SIKILIK OLCUTU: "RPY bunu sessizce mi yutuyor, gurultulu mu reddediyor?"
*       Ucu de kullanilamaz alan uretir; ikisini RPY hic sikayet etmeden yutar.
    LOOP AT it_fields INTO DATA(ls_chk).
*     Etkin tip: TYPE bos verilirse asagida TEMPLATE'e donusur -> kontroller de
*     etkin tipe gore yapilmali (yoksa TYPE'i bos birakan satir kontrolu atlatir).
      l_ftype = ls_chk-type.
      IF l_ftype IS INITIAL.
        l_ftype = 'TEMPLATE'.
      ENDIF.

*     (b1) Konum. RPY GURULTULU reddeder (missing_required_field, rc=5) ama HANGI
*          alan oldugunu SOYLEMEZ -> burada isimlendiriyoruz.
*          Kanit: LSIFPF11 i_check_field 1434 (LINE) / 1447 (COLUMN). OKCODE muaf.
*          ⚠ Kaynaktaki TABLE_CTRL istisnasi ALAN tipine degil CONTAINER tipine
*          bakar (SCRCTYPE); bizim container'imiz daima kok -> burada gecersiz.
      IF l_ftype <> 'OKCODE'
         AND ( ls_chk-line IS INITIAL OR ls_chk-column IS INITIAL ).
        l_f2c_bad = |{ l_f2c_bad } { ls_chk-name }(LINE/COLUMN)|.
      ENDIF.

*     (b2) TEMPLATE'te uzunluk. LENGTH ya FROM_DICT ile DDIC'ten gelir ya da
*          cagiran verir -- FM UYDURMAZ. Ikisi de yoksa RPY SESSIZCE 0 genislikli,
*          kullanilamaz bir alan uretir (ya da hangi alan oldugunu soylemeyen rc=5).
*          Uydurmak yerine ZORUNLU tutuyoruz.
      IF l_ftype = 'TEMPLATE'
         AND ls_chk-from_dict IS INITIAL AND ls_chk-length IS INITIAL.
        l_f2c_bad = |{ l_f2c_bad } { ls_chk-name }(LENGTH)|.
      ENDIF.
*     (b2b) Ayni kusur sinifinin TEXT karsiligi: ne metin, ne uzunluk, ne DDIC
*           baglantisi -> 0 genislikli, icerigi olmayan etiket (sessizce hicbir sey).
*           FROM_DICT'li TEXT'te metin DDIC'ten gelir -> o vaka disarida.
*           (TEXT + metin var + LENGTH yok = kusur DEGIL: uzunluk asagida strlen'den.)
      IF l_ftype = 'TEXT'
         AND ls_chk-from_dict IS INITIAL AND ls_chk-length IS INITIAL
         AND ls_chk-text IS INITIAL.
        l_f2c_bad = |{ l_f2c_bad } { ls_chk-name }(TEXT/LENGTH)|.
      ENDIF.

*     (b3) Orphan: CONT_NAME dolu ama LT_CONT'ta o (type,name) yok. RPY bunu
*          TAMAMEN SESSIZ yutar (alan uretilmez, rc=0 doner) -> bu blogun var olma
*          sebebi olan sahte-OK'nin ta kendisi. En sert muamele bunu hak ediyor.
*          (CONT_NAME bos ise asagida koke baglanir -> kusur degil.)
      IF ls_chk-cont_name IS NOT INITIAL
         AND NOT line_exists( lt_cont[ type = ls_chk-cont_type name = ls_chk-cont_name ] ).
        l_f2c_bad = |{ l_f2c_bad } { ls_chk-name }(CONT { ls_chk-cont_type }/{ ls_chk-cont_name })|.
      ENDIF.
    ENDLOOP.
    IF l_f2c_bad IS NOT INITIAL.
      ev_rc = 5.
      ev_message = |IT_FIELDS gecersiz -- ekran YARATILMADI. Kusurlu alan(lar):| &&
                   |{ l_f2c_bad }. | &&
                   |LINE/COLUMN: konum zorunlu (OKCODE haric). | &&
                   |LENGTH: TEMPLATE'te LENGTH ya da FROM_DICT zorunlu. | &&
                   |CONT: verilen container LT_CONT'ta yok -> RPY alani SESSIZCE atardi.|.
      RETURN.
    ENDIF.

*   (c) Her IT_FIELDS satiri -> bir RPY_DYFATC satiri. Alan adlari BIREBIR ayni
*       (satir tipi RPY_DYFATC'den turetildi) -> MOVE-CORRESPONDING guvenli.
    LOOP AT it_fields INTO DATA(ls_fld).
      APPEND INITIAL LINE TO lt_f2c ASSIGNING FIELD-SYMBOL(<f2c>).
      MOVE-CORRESPONDING ls_fld TO <f2c>.

*     CONT_NAME bos -> kok container (en sik durum: alan dogrudan ekranda).
*     CONT_NAME dolu ama gecersiz olan satirlar (b3)'te zaten ELENDI -> buraya
*     yalnizca container'i LT_CONT'ta VAR olan satirlar gelir.
      IF <f2c>-cont_name IS INITIAL.
        <f2c>-cont_name = c_cont_rname.
        <f2c>-cont_type = c_cont_root.
      ENDIF.

*     TYPE bos -> TEMPLATE (giris/cikis alani; bu parametrenin varlik sebebi).
*     Gecerli tipler: TEXT TEMPLATE RADIO CHECK FRAME FRAME_TMPL PUSH PUSH_TMPL
*     INFOBUTTON OKCODE (LSIFPF11 i_check_field 1418-1427).
      IF <f2c>-type IS INITIAL.
        <f2c>-type = 'TEMPLATE'.
      ENDIF.

*     TEXT etiketinde LENGTH verilmediyse metnin uzunlugu (0 genislikli etiket
*     gorunmez olurdu). TEMPLATE'te uzunluk ya FROM_DICT ile DDIC'ten gelir ya
*     da cagiran verir -> burada uydurulmaz.
      IF <f2c>-length IS INITIAL AND <f2c>-type = 'TEXT' AND <f2c>-text IS NOT INITIAL.
        <f2c>-length = strlen( <f2c>-text ).
      ENDIF.
*     VISLENGTH bos -> LENGTH (SE51 varsayilani: gorunur uzunluk = tanimli uzunluk).
      IF <f2c>-vislength IS INITIAL.
        <f2c>-vislength = <f2c>-length.
      ENDIF.

*     TEMPLATE + INPUT_FLD/OUTPUT_FLD'in IKISI de bos -> normal Giris/Cikis alani.
*     Kanit: LSIFPF11 i_input_field_in 1114 (input_fld <> ' ' ise giris ACIK).
*     ⚠ Bu default IZIN VERICI yondedir (alan DUZENLENEBILIR olur). Kisitlayici
*     yon (yalniz OUTPUT_FLD='X') daha "guvenli" gorunur ama bu parametrenin
*     varlik sebebi GIRIS ekrani (0300/0400) -> her satirda bayrak yazdirmak
*     ergonomiyi bozar ve asil sik hatayi (giris alani acilmadi) dogurur.
*     Sessizlik riskini default'u degistirerek degil GORUNUR kilarak kapatiyoruz:
*     kac satira uygulandigi sayilip EV_MESSAGE'a yazilir (io_default=N).
*     Salt-okunur isteyen cagiran OUTPUT_FLD='X' tek basina ya da REQU_ENTRY='N'
*     (= giris YASAK) verir -> kosul kirilir, default devreye GIRMEZ.
      IF <f2c>-type = 'TEMPLATE'
         AND <f2c>-input_fld IS INITIAL AND <f2c>-output_fld IS INITIAL.
        <f2c>-input_fld  = 'X'.
        <f2c>-output_fld = 'X'.
        l_io_def = l_io_def + 1.
      ENDIF.
    ENDLOOP.
  ENDIF.

* IV_RECREATE='X': mevcut Dynpro'yu once SIL (flow logic/container degisikligini
* uygulamak icin — RPY_DYNPRO_INSERT mevcut ekrani overwrite ETMEZ, already_exists doner).
  IF iv_recreate = 'X'.
    CALL FUNCTION 'RS_SCRP_DELETE'
      EXPORTING
        dynnr           = iv_dynpro
        progname        = iv_program
        suppress_checks = 'X'
        with_popup      = space
      CHANGING
        corrnum         = iv_transport
      EXCEPTIONS
        OTHERS          = 0.
  ENDIF.

  CALL FUNCTION 'RPY_DYNPRO_INSERT'
    EXPORTING
      header                 = ls_header
      corrnum                = iv_transport
      suppress_corr_checks   = space
    TABLES
      containers             = lt_cont
      fields_to_containers   = lt_f2c
      flow_logic             = lt_flow
    EXCEPTIONS
      cancelled              = 1
      already_exists         = 2
      program_not_exists     = 3
      not_executed           = 4
      missing_required_field = 5
      illegal_field_value    = 6
      field_not_allowed      = 7
      not_generated          = 8
      illegal_field_position = 9
      OTHERS                 = 10.
  l_screen_rc = sy-subrc.

*--- 2) GUI status + titlebar (fetch-template) --------------------------
  CALL FUNCTION 'RS_CUA_INTERNAL_FETCH'
    EXPORTING
      program         = iv_src_prog
      language        = sy-langu
      state           = 'A'
    IMPORTING
      adm             = adm
    TABLES
      sta             = sta
      fun             = fun
      men             = men
      mtx             = mtx
      act             = act
      but             = but
      pfk             = pfk
      set             = sett
      doc             = doc
      tit             = tit
      biv             = biv
    EXCEPTIONS
      not_found       = 1
      unknown_version = 2
      OTHERS          = 3.
  IF sy-subrc <> 0.
    l_stat_rc = 100 + sy-subrc.
  ELSE.
*   Bloat azalt: sadece donör status'unu tut (tanim havuzlari kalir).
    DELETE sta  WHERE code   <> iv_src_status.
    DELETE sett WHERE status <> iv_src_status.
    READ TABLE sta WITH KEY code = iv_src_status INTO DATA(ls_src).
*   ⛔ SY-SUBRC KONTROLU ZORUNLU -- kontrolsuz birakildiginda hata SESSIZ ve YIKICI.
*   Donör fetch rc=0 dondugu halde STANDARD satiri gelmezse (yukaridaki DELETE'ten
*   sonra STA BOS kalir) LS_SRC bos olur -> L_SRC_PFK/L_SRC_ACT BOSTUR ve zincir
*   sirayla soyle cokerdi:
*     (1) `DELETE pfk WHERE code <> l_src_pfk` / `DELETE act WHERE code <> l_src_act`
*         -> kodu bos-OLMAYAN TUM donör satirlarini siler (havuzlar bosalir),
*     (2) STA bos oldugu icin asagidaki LOOP'lar hicbir sey yapmaz -> YENI STATUS
*         HIC KURULMAZ (ne pfkcode/actcode atamasi, ne STANDARD->STAT<n> yeniden
*         adlandirmasi),
*     (3) merge dali `DELETE o_sta WHERE code = l_status` ile programin MEVCUT
*         STAT<dynnr>'ini de merge adaylarindan CIKARIR,
*     (4) RS_CUA_INTERNAL_WRITE tum cluster'i REPLACE eder -> STAT<dynnr> ve ona
*         bagli SET satirlari TAMAMEN YOK OLUR; SET PF-STATUS runtime'da var
*         olmayan bir status'e isaret eder.
*   Ve bunlarin hicbiri RC'ye YANSIMAZDI: WRITE rc=0 doner, cagiran EV_RC=0 gorup
*   "basarili" sanardi -- bu FM'in var olma sebebi olan SESSIZ CUA kaybinin ta kendisi.
*   ⚠ Kapsam DURUST tarif edilir: kaybedilen, tam da URETILMEK ISTENEN ekranin
*     status'udur. YABANCI statusler merge'de geri eklendigi icin ETKILENMEZ
*     (o_sta/o_pfk/o_act bizim kodlarimiz DISINDA dokunulmadan tasinir).
*   Cozum: WRITE'a HIC GIRMEDEN cik. EV_RC bandi 120 = "donör fetch OK ama donör
*   status satiri yok".
*   ⚠ BANTLAR ARALIK OLARAK dusunulmeli, cunku sonuc DAIMA `l_screen_rc` (0..10,
*     RPY_DYNPRO_INSERT OTHERS=10) ile TOPLANIR:
*       donör fetch HATASI : 100+subrc(1..3) + 0..10 -> 101..113
*       donör status YOK   : 120           + 0..10 -> 120..130   (bu dal)
*       merge fetch HATASI : 200+subrc(2..3) + 0..10 -> 202..213
*       giris parametresi  : 300 (tek basina; hicbir adim kosmadi)
*     Taban 110 SECILEMEZ: 110..120 araligi donör-fetch bandinin ustune biner
*     (ornek: ev_rc=111 hem "donör fetch rc=1 + screen rc=10" hem "donör status
*     yok + screen rc=1" olurdu) -> EV_RC'ye bakan yanlis teshis koyar. 120 ayrik.
    IF sy-subrc <> 0.
      l_stat_rc  = 120.
      ev_rc      = l_screen_rc + l_stat_rc.
      ev_message = |screen({ iv_program }/{ iv_dynpro }) rc={ l_screen_rc }; | &&
                   |DONOR STATUS BULUNAMADI ({ iv_src_prog }/{ iv_src_status }) -- | &&
                   |CUA'ya HICBIR SEY YAZILMADI (mevcut status/titlebar KORUNDU). | &&
                   |Devam edilseydi { l_status } sessizce SILINIR ve EV_RC yine | &&
                   |basarili gorunurdu. | &&
                   |status({ l_status }+{ l_tit }) rc={ l_stat_rc }; generate kosmadi| &&
                   l_arg_diag.   " taninmayan giris tanisi ERKEN CIKISTA da gorunur
      RETURN.
    ENDIF.

*   --- SET KODLARINI DYNPRO'YA OZEL YAP (CUA MERGE'in ON SARTI) -------------
*   CUA program GENELINE aittir: RS_CUA_INTERNAL_WRITE tek bir
*   `EXPORT ... TO DATABASE eudb(cu) ID eudb_key` yapar ve eudb_key-name = PROGRAM
*   [KANIT: RS_CUA_INTERNAL_WRITE:161-178, standart kaynak OKUNDU].
*   Yani yazma DELTA DEGIL; programin TUM CUA'sinin YERINE GECER.
*   Eskiden her ekran DONORUN AYNI set kodlarini (butcode/pfkcode/actcode) yeniden
*   kullaniyordu. Bu iki ekranli programda CALISMAZ:
*     - Toolbar status'un `butcode`una gore secilir; iki status ayni butcode'u
*       gosterirse AYNI toolbar'i gorur -> 0300 uretimi 0200'un butonlarini yok etti.
*     - pfk/act satirlari (code,pfno) / (code,no) ile anahtarli; ayni kodu paylasan
*       iki ekranin buton slotlari CAKISIR.
*   Cozum: her dynpro KENDI set kodlarina sahip olur -> statusler birbirine
*   dokunmadan ayni programda yasar ve yeniden uretim idempotent olur.
*   ⚠ Kodlar SALT-RAKAM OLAMAZ: LSMPIF03 `check_intcode` bir kodu, `code+6(14)` bos
*   VE ilk 6 karakter rakamsa "index" sayar; `check_adm` bu durumda WRITE'i
*   `invalid_data` ile REDDEDER [KANIT: LSMPIF03:48-53 + 86-102]. Bu yuzden harf onekli.
    DATA(l_src_pfk) = ls_src-pfkcode.
    DATA(l_src_act) = ls_src-actcode.
    DATA(l_pfkcode) = CONV rsmpe_stat-pfkcode( |PFK{ iv_dynpro }| ).
    DATA(l_actcode) = CONV rsmpe_stat-actcode( |ACT{ iv_dynpro }| ).
*   butcode YALNIZ 4 KARAKTER (RSMPE_STAT-BUTCODE CHAR 4, DD03L olcumu) -> 'B'+son 3 hane.
*   ⚠ Bilinen sinir: 0300 ile 1300 ayni butcode'u ('B300') uretirdi. Klasik Z
*   programlarinda dynpro 0100-0900 araliginda kullanildigi icin pratikte cakismaz.
    DATA(l_butcode) = CONV rsmpe_stat-butcode( |B{ iv_dynpro+1(3) }| ).

*   Donörün YALNIZ bu status'un kullandigi set'ini tut ve YENIDEN ADLANDIR.
*   (Donörün diger pfk/act havuzlari zaten REFERANSSIZ tasiniyordu — bloat.)
*   ⚠ DONÖR-AGNOSTIK GUARD: donör artik parametrik oldugu
*     icin "donör status'un pfkcode/actcode'u DOLU" varsayimi ARTIK GARANTI DEGIL.
*     Bos olsaydi `DELETE pfk WHERE code <> l_src_pfk` kodu bos-OLMAYAN TUM donör
*     satirlarini silerdi -> havuz bosalir, sta yine PFK<n>/ACT<n>'ye isaret eder ->
*     referanssiz status = runtime 00256 ("Gecerli bir islev secin"), ustelik RC=0.
*     Bilinmeyeni SESSIZ VARSAYIM yerine GURULTULU RAPOR ile karsiliyoruz: havuz
*     bosaltilir ve durum EV_MESSAGE'a yazilir.
*     Legacy donörde (SAPLKKBL/STANDARD — repo surumunun kanitlanmis yolu) ikisi de
*     DOLU -> bu dal HIC calismaz, davranis birebir ayni kalir.
    IF l_src_pfk IS NOT INITIAL.
      DELETE pfk WHERE code <> l_src_pfk.
      LOOP AT pfk ASSIGNING FIELD-SYMBOL(<p0>).
        <p0>-code = l_pfkcode.
      ENDLOOP.
    ELSE.
      REFRESH pfk.
      l_setcode_miss = |{ l_setcode_miss } PFK|.
    ENDIF.
    IF l_src_act IS NOT INITIAL.
      DELETE act WHERE code <> l_src_act.
      LOOP AT act ASSIGNING FIELD-SYMBOL(<a0>).
        <a0>-code = l_actcode.
      ENDLOOP.
    ELSE.
      REFRESH act.
      l_setcode_miss = |{ l_setcode_miss } ACT|.
    ENDIF.
    LOOP AT sta ASSIGNING FIELD-SYMBOL(<s0>).
      <s0>-pfkcode = l_pfkcode.
      <s0>-actcode = l_actcode.
*     CTXCODE = donörden kopyalanan DORDUNCU set kodu (baglam menusu). Digerleri
*     gibi YENIDEN ADLANDIRILAMAZ, cunku bu FM baglam menusu URETMEZ -> dogru
*     davranis onu tasimak degil BOSALTMAK.
*     ⚠ OLCULDU (standart kaynak SADECE OKUNDU, kesin yasak A'ya uygun) -- CTXCODE
*       yalnizca status'un MODAL alani "baglam menusu" tipindeyken anlamlidir:
*         · yazarken LSMPIF02 edittab_to_sourcetab:661-668 -> deger INT_CTX'e
*           ancak `if sta-modal = con_stdtype_context` ise tasinir;
*         · okurken LSMPIF01 merge_ctx:2041-2046 -> ayni kosulu arar;
*         · EUDB cluster'ina giden yapida (RSMPE_STA) CTXCODE ALANI HIC YOKTUR
*           [DD03L olcumu: CODE MODAL ACTCODE PFKCODE BUTCODE].
*       ⇒ Normal (dialog) status icin bu CLEAR bir NO-OP'tur: DAVRANIS DEGISMEZ,
*         canli 4 ekran icin regresyon riski YOK.
*       ⇒ Donör bir gun baglam-menulu bir status olursa: men/mtx'i asagida REFRESH
*         ettigimiz icin tasinacak ctx referansi YETIM kalirdi -- CLEAR onu keser.
*     Yalnizca BIZIM satirimizi etkiler: bu noktada STA'da sadece donör satiri var
*     (yukaridaki `DELETE sta WHERE code <> iv_src_status`); yabanci statusler
*     merge adiminda SONRADAN eklenir, kendi CTXCODE'lariyla dokunulmadan gecer.
      CLEAR <s0>-ctxcode.
    ENDLOOP.

*   ⚠️ NAVIGASYON REMAP KOSULLU (karar L_NAV_REMAP'te).
*   Legacy donörün (SAPLKKBL/STANDARD) fonksiyon kodlari (&F03/&F15/&F12)
*   programin bekledigi BACK/EXIT/CANCEL semantigiyle eslesmez -> remap SART.
*   Minimal bir musteri donörü ise (&F2/&F3/&F4/&F5, dogru TR metinle) kodlarini
*   AS-IS tasir; remap orada uygulansa &F2..&F5 bekleyen hedef PAI BOZULURDU.
*   Varsayilan = legacy donör mu (OTOMATIK); IV_NAV_REMAP='X'/'-' ile cagiran ezebilir.
    IF l_nav_remap = abap_true.
*     F3 (pfno 03) -> BACK, Shift+F3 (15) -> EXIT, F12 (12) -> CANCEL.
      LOOP AT pfk ASSIGNING FIELD-SYMBOL(<p>) WHERE code = l_pfkcode.
        CASE <p>-pfno.
          WHEN '03'. <p>-funcode = 'BACK'.
          WHEN '15'. <p>-funcode = 'EXIT'.
          WHEN '12'. <p>-funcode = 'CANCEL'.
        ENDCASE.
      ENDLOOP.
    ENDIF.

*   Status kodunu donör kodundan -> STAT<dynnr> (sta + mevcut set).
    LOOP AT sta ASSIGNING FIELD-SYMBOL(<s>) WHERE code = iv_src_status.
      <s>-code = l_status.
    ENDLOOP.
    LOOP AT sett ASSIGNING FIELD-SYMBOL(<f>) WHERE status = iv_src_status.
      <f>-status = l_status.
    ENDLOOP.

*   ⚠️ TOOLBAR PRUNE GERI ALINDI: donör act/fun/toolbar'i temizlemek BACK/EXIT/CANCEL'i
*   GECERSIZ kildi (runtime "00256 Gecerli bir islev secin"). Bir fonksiyonun gecerli
*   olmasi `act` (aktif fonksiyon listesi) gerektirir; set/pfk tek basina yetmiyor.
*   Donör STANDARD'in act/fun/toolbar'i BUTUNUYLE KORUNUR -> BACK/EXIT/CANCEL donörde
*   gecerli + re-map ile F3/Sh+F3/F12'ye bagli -> butonlar + ESC(=F12) calisir.
*   (Toolbar'da donör ALV fonksiyonlari kalir; tam-minimal status from-scratch CUA isi.)
*   BACK/EXIT/CANCEL fun + set'te yoksa garanti et (donörde varsa dokunma).
*   ⚠️ REMAP ile AYNI KAPIDA: bu uc fonksiyonu remap YAPILMADAN eklemek, &F2..&F5
*   donörlu bir status'e HICBIR TUSA/BUTONA bagli olmayan uc yetim fonksiyon
*   koyardi (fun+set sisirilir, davranis degismez) -- ve daha kotusu, donörün
*   kendi 'BACK' benzeri tanimi varsa asagidaki CLEAR type onun tipini ezerdi.
*   Bu yuzden blok da L_NAV_REMAP'e bagli (canli surumde de legacy dalin icindeydi).
    IF l_nav_remap = abap_true.
      IF NOT line_exists( fun[ code = 'BACK' ] ).   APPEND VALUE #( code = 'BACK'   fun_text = 'Geri'  ) TO fun. ENDIF.
      IF NOT line_exists( fun[ code = 'EXIT' ] ).   APPEND VALUE #( code = 'EXIT'   fun_text = 'Cikis' ) TO fun. ENDIF.
      IF NOT line_exists( fun[ code = 'CANCEL' ] ). APPEND VALUE #( code = 'CANCEL' fun_text = 'Iptal' ) TO fun. ENDIF.
      IF NOT line_exists( sett[ status = l_status function = 'BACK' ] ).   APPEND VALUE #( status = l_status function = 'BACK' )   TO sett. ENDIF.
      IF NOT line_exists( sett[ status = l_status function = 'EXIT' ] ).   APPEND VALUE #( status = l_status function = 'EXIT' )   TO sett. ENDIF.
      IF NOT line_exists( sett[ status = l_status function = 'CANCEL' ] ). APPEND VALUE #( status = l_status function = 'CANCEL' ) TO sett. ENDIF.
*     3'unu de NORMAL type'a zorla (donörde EXIT type='E' geliyor -> AT EXIT-COMMAND
*     moduluyuz YOK -> Exit takilir). Normal -> user_command_<n> yakalar. ESC=F12=CANCEL.
      LOOP AT fun ASSIGNING FIELD-SYMBOL(<fn2>)
           WHERE code = 'BACK' OR code = 'EXIT' OR code = 'CANCEL'.
        CLEAR <fn2>-type.
      ENDLOOP.
    ENDIF.

*   TOOLBAR/MENU TEMIZLIGI (DIKKATLI): sadece GORUNUR menu bar (men/mtx) +
*   application toolbar (but) kaldirilir. `act` (aktif fonksiyon listesi = GECERLILIK)
*   ve fun/pfk/set KORUNUR -> fonksiyonlar gecerli kalir (00256 YOK). Onceki patinaj
*   act'i de temizlemekti -> fonksiyonlar gecersiz -> 00256. ALV grid'in KENDI toolbar'i
*   ayri (CL_GUI_ALV_GRID), etkilenmez.
    REFRESH: men, mtx, but.
    CLEAR adm-mencode.

    IF it_buttons[] IS INITIAL.
*     --- GERIYE-DONUK UYUMLU: cagiran buton VERMEDI -> onceki davranis birebir:
*     application toolbar YOK (sta-butcode CLEAR); act/pfkcode/fun/pfk KORUNUR
*     (BACK/EXIT/CANCEL gecerli kalir). Asagidaki blok HIC calismaz. ---
      LOOP AT sta ASSIGNING <s>.
        CLEAR <s>-butcode.    " application toolbar yok (act/pfkcode korunur)
      ENDLOOP.
    ELSE.
*     --- IT_BUTTONS DOLU: cagiranin verdigi OZEL app-toolbar butonlarini kur. ---
*     Donör STANDARD'in yapisal SET kodlarini (act/pfk/but) YENIDEN KULLANIRIZ ->
*     yeni set kodu icat etmeye gerek yok; donör act/pfk gecerliligi ile uyumlu kalir.
*     Klasik CUA zinciri: but(no,pfno) -> pfk(pfno->funcode) -> fun(fcode)[text/icon].
*     act(menucode=fcode) fonksiyonu GECERLI kilar (yoksa runtime 00256 — donör-prune
*     dersi: satir 261-283). NO/PFNO donör MAX'in ustunde secilir -> anahtar cakismasi yok.
*     ⛔ l_butcode / l_actcode / l_pfkcode BURADA BILDIRILMEZ — yukarida, set-kodu
*     normalizasyonunda dynpro'ya ozel olarak kuruldular. Burada yeniden bildirmek
*     "already declared" verir; donör kodunu geri atamak ise MERGE'i BOZAR.
      DATA: l_maxpfno  TYPE i,
            l_maxactno TYPE i,
            l_butno    TYPE i,
            l_i        TYPE i,
            l_tmp      TYPE i,
            l_actno_n  TYPE n LENGTH 2,
            l_pfno_n   TYPE n LENGTH 2,
            l_butno_n  TYPE n LENGTH 2.

*     Donör pfk/act icindeki en yuksek numarayi bul -> cakismayan slot uret.
      CLEAR: l_maxpfno, l_maxactno.
      LOOP AT pfk ASSIGNING <p> WHERE code = l_pfkcode.
        IF <p>-pfno CO '0123456789'.
          l_tmp = <p>-pfno.
          IF l_tmp > l_maxpfno. l_maxpfno = l_tmp. ENDIF.
        ENDIF.
      ENDLOOP.
      LOOP AT act ASSIGNING FIELD-SYMBOL(<a>) WHERE code = l_actcode.
        IF <a>-no CO '0123456789'.
          l_tmp = <a>-no.
          IF l_tmp > l_maxactno. l_maxactno = l_tmp. ENDIF.
        ENDIF.
      ENDLOOP.

      l_butno = 0.
      l_i     = 0.
      LOOP AT it_buttons INTO DATA(ls_btn) WHERE fcode IS NOT INITIAL.
        l_i = l_i + 1.

*       (a) fun: fonksiyon tanimi (statik text + ikon + infotext). Toolbar butonu
*           ikon/text/quickinfo'yu bu fonksiyon tanimindan alir.
*           text_type='S' (statik text) ZORUNLU: yoksa RS_CUA_INTERNAL_WRITE FUN_TEXT'i
*           SESSIZCE dusurur -> buton etiketsiz gorunur (kanit: elle-eklenen referans
*           buton TEXT_TYPE=[S]). VARSA guncelle (onceki basarisiz run'in biraktigi bos
*           entry'yi de duzeltir), YOKSA ekle -> idempotent + re-run guvenli.
*           icon_text = text: ikon verilirse text ikon YANINDA gorunur; ikonsuzda fun_text
*           etiket olur -> her iki durumda da text goruntulenir.
        READ TABLE fun ASSIGNING FIELD-SYMBOL(<fn_btn>) WITH KEY code = ls_btn-fcode.
        IF sy-subrc = 0.
          <fn_btn>-text_type = 'S'.
          <fn_btn>-fun_text  = ls_btn-text.
          <fn_btn>-icon_id   = ls_btn-icon.
          <fn_btn>-icon_text = ls_btn-text.
          <fn_btn>-info_text = ls_btn-quickinfo.
        ELSE.
          APPEND VALUE #( code      = ls_btn-fcode
                          text_type = 'S'
                          fun_text  = ls_btn-text
                          icon_id   = ls_btn-icon
                          icon_text = ls_btn-text
                          info_text = ls_btn-quickinfo ) TO fun.
        ENDIF.

*       (b) act: fonksiyonu AKTIF/gecerli listeye ekle (yoksa 00256). NO donör
*           max'in ustunde -> mevcut act satirlariyla anahtar cakismasi olmaz.
        IF NOT line_exists( act[ code = l_actcode menucode = ls_btn-fcode ] ).
          l_actno_n = l_maxactno + l_i.
          APPEND VALUE #( code = l_actcode no = l_actno_n menucode = ls_btn-fcode ) TO act.
        ENDIF.

*       (c) pfk: bos bir fonksiyon-tusu slotu -> funcode=fcode. FKEY verildiyse onu,
*           yoksa donör MAX(pfno)+sira kullan.
        IF ls_btn-fkey IS NOT INITIAL.
          l_pfno_n = ls_btn-fkey.
        ELSE.
          l_pfno_n = l_maxpfno + l_i.
        ENDIF.
        APPEND VALUE #( code = l_pfkcode pfno = l_pfno_n funcode = ls_btn-fcode ) TO pfk.

*       (d) but: app-toolbar butonu -> pozisyon (no), fonksiyon-tusu (pfno),
*           pfk-set (pfk_code). but ustte REFRESH edildi -> pozisyon 01'den baslar.
        l_butno   = l_butno + 1.
        l_butno_n = l_butno.
        APPEND VALUE #( code     = l_butcode
                        pfk_code = l_pfkcode
                        no       = l_butno_n
                        pfno     = l_pfno_n ) TO but.

*       (e) set: status->fonksiyon uyeligi.
        IF NOT line_exists( sett[ status = l_status function = ls_btn-fcode ] ).
          APPEND VALUE #( status = l_status function = ls_btn-fcode ) TO sett.
        ENDIF.
      ENDLOOP.

*     Status'a toolbar SET kodunu BAGLA (CLEAR yerine) -> app-toolbar gorunur.
      LOOP AT sta ASSIGNING <s>.
        <s>-butcode = l_butcode.
      ENDLOOP.
    ENDIF.

*   Titlebar: donörün TUM titlebar'larini (003/800-808/850/DYN/FIL/LS/POP/TI1/TP1...)
*   ATARIZ; sadece kendi TIT0100'umuzu birakiriz (title'lar status'tan bagimsiz, güvenli).
    REFRESH tit.
    APPEND VALUE #( code = l_tit text = iv_title ) TO tit.

*   --- CUA MERGE: hedef programin MEVCUT status/titlebar'larini KORU -----------
*   ⚠ Bu blok olmadan FM YIKICIDIR: WRITE programin tum CUA'sini degistirdigi icin
*   (yukaridaki EXPORT kaniti) her yeni ekran uretimi, o programda DAHA ONCE
*   uretilmis TUM status ve titlebar'lari SILER. Olculen canli vaka: 0300
*   uretimi STAT0200 + TIT0200'u ve 0200'un 5 butonunu yok etti; `SET PF-STATUS
*   'STAT0200'` var olmayan bir status'e isaret eder hale geldi.
*   Cozum: yazmadan ONCE mevcut CUA'yi AYRI tablolara oku ve yeni status'un
*   yanina EKLE. Kendi status/titlebar/set kodlarimiz ELENIR -> ayni ekranin
*   yeniden uretimi cogaltmaz, TAZELER (idempotent).
*
*   --- IV_CUA_MERGE = ' ' -> MERGE KAPALI -----------------------------------
*   Bu, merge eklenmeden onceki surumun davranisidir: WRITE cluster'i komple degistirir,
*   hedef programin diger status/titlebar'lari GIDER. "Temiz sayfa" isteyen (bozuk
*   CUA'yi bastan kurmak isteyen) cagiran icin BILINCLI bir kacis kapisi olarak
*   birakildi -- ama VARSAYILAN DEGIL, cunku sessiz yikim uretiyor.
*   ⚠ MERGE'IN KENDISI ZATEN VERIYE DAYALI: hedef programin CUA'si YOKSA
*     (fetch rc=1 not_found) merge kendiliginden atlanir -> ilk uretimde iki
*     davranis AYNIDIR. Yani anahtar yalniz "CUA'si OLAN programda ne yapalim"
*     sorusunu cevaplar; orada da dogru cevap KORUMAKTIR (olculen canli
*     regresyonu: 0300 uretimi STAT0200+TIT0200'u ve 5 butonu yok etmisti).
*   ⛔ ANAHTAR YALNIZ FETCH'I KESER, akisi SARMALAMAZ: l_merge_rc = -2 kalinca
*     asagidaki `IF l_merge_rc > 1` (erken cikis) ve `IF l_merge_rc = 0` (merge
*     uygulama) dallarinin IKISI de FALSE olur -> merge tamamen atlanir, kod yolu
*     tek ve okunur kalir.
*   ⚠ POLARITE FAIL-CLOSED: kapatma kosulu ARTIK BEYAZ LISTE
*     ('  ' bos ya da '-'), "X degilse kapat" DEGIL. Eskisi taninmayan/kucuk-harf her
*     degeri yikici yola sokuyordu. Deger yukarida to_upper ile normalize edildi ve
*     taninmayanlar 'X'e (merge ACIK) cekildi -> buraya yalniz {'X',' ','-'} gelir.
    IF l_cua_merge IS INITIAL OR l_cua_merge = '-'.
      l_merge_rc = -2.               " = cagiran MERGE'i acikca KAPATTI
    ELSE.
      CALL FUNCTION 'RS_CUA_INTERNAL_FETCH'
        EXPORTING
          program         = iv_program
          language        = sy-langu
          state           = 'A'
        IMPORTING
          adm             = o_adm
        TABLES
          sta             = o_sta
          fun             = o_fun
          men             = o_men
          mtx             = o_mtx
          act             = o_act
          but             = o_but
          pfk             = o_pfk
          set             = o_sett
          doc             = o_doc
          tit             = o_tit
          biv             = o_biv
        EXCEPTIONS
          not_found       = 1
          unknown_version = 2
          OTHERS          = 3.
      l_merge_rc = sy-subrc.
    ENDIF.
*   sy-subrc=1 (not_found) = programin HENUZ CUA'si YOK -> ilk uretim. Bu bir HATA
*   DEGILDIR: merge atlanir ve sonuc ONCEKI DAVRANISLA AYNI olur.
*   ⛔ rc>1 (unknown_version=2 / OTHERS=3) BAMBASKA BIR SEYDIR: programin CUA'si VAR
*   OLABILIR ama OKUNAMADI. Eskiden 1/2/3 ayni kovaya dusuyordu -> merge atlanir, ama
*   asagidaki RS_CUA_INTERNAL_WRITE yine de TUM cluster'i REPLACE ederdi (WRITE delta
*   DEGIL, satir ~453 kaniti) -> programin mevcut TUM status/titlebar'i SILINIRDI.
*   Ustelik EV_RC bundan etkilenmezdi: cagiran rc=0 gorup "basarili" sanardi, ekranlar
*   gitmis olurdu. Bu, FM'in var olma sebebi olan yikimin dar bir HATA YOLUNDAN geri
*   gelmesidir -> WRITE'a HIC GIRMEDEN cik. Sessiz-basari birakma: rc de hatayi gostersin.
*   EV_RC bandi 200+rc: donör fetch icin kullanilan 100+rc deseniyle ayni mantik.
    IF l_merge_rc > 1.
      l_stat_rc = 200 + l_merge_rc.
      ev_rc     = l_screen_rc + l_stat_rc.
      ev_message = |screen({ iv_program }/{ iv_dynpro }) rc={ l_screen_rc }; | &&
                   |MERGE FETCH BASARISIZ (rc={ l_merge_rc }) -- CUA'ya HICBIR SEY | &&
                   |YAZILMADI (status/titlebar DEGISMEDI, mevcut ekranlar KORUNDU). | &&
                   |Devam edilseydi WRITE programin TUM CUA'sini silerdi. | &&
                   |status({ l_status }+{ l_tit }) rc={ l_stat_rc }; generate kosmadi| &&
                   l_arg_diag.   " taninmayan giris tanisi ERKEN CIKISTA da gorunur
      RETURN.
    ENDIF.
    IF l_merge_rc = 0.
*     (a) BIZE ait olani mevcuttan cikar -> yeniden uretimde cogaltma olmaz.
      DELETE o_sta  WHERE code   = l_status.
      DELETE o_sett WHERE status = l_status.
      DELETE o_tit  WHERE code   = l_tit.
      DELETE o_pfk  WHERE code   = l_pfkcode.
      DELETE o_act  WHERE code   = l_actcode.
      DELETE o_but  WHERE code   = l_butcode.
      DELETE o_biv  WHERE sub_code = l_butcode.

*     (b) Kalan YABANCI satirlari ekle. Anahtari yeni tabloda ZATEN VARSA atlanir
*         (donör havuzu ile mevcut CUA ayni satiri tasiyabilir -> duplicate key
*         WRITE'i patlatirdi). Anahtarlar DD03L'den olculdu, tahmin degil.
      LOOP AT o_sta INTO DATA(ls_m_sta).
        IF NOT line_exists( sta[ code = ls_m_sta-code ] ).
          APPEND ls_m_sta TO sta.
          l_merge_sta = l_merge_sta + 1.
        ENDIF.
      ENDLOOP.
      LOOP AT o_tit INTO DATA(ls_m_tit).
        IF NOT line_exists( tit[ code = ls_m_tit-code ] ).
          APPEND ls_m_tit TO tit.
          l_merge_tit = l_merge_tit + 1.
        ENDIF.
      ENDLOOP.
      LOOP AT o_sett INTO DATA(ls_m_set).
        IF NOT line_exists( sett[ status = ls_m_set-status function = ls_m_set-function ] ).
          APPEND ls_m_set TO sett.
        ENDIF.
      ENDLOOP.
*     fun: RSMPE_FUNT anahtari CODE + TEXTNO.
      LOOP AT o_fun INTO DATA(ls_m_fun).
        IF NOT line_exists( fun[ code = ls_m_fun-code textno = ls_m_fun-textno ] ).
          APPEND ls_m_fun TO fun.
        ENDIF.
      ENDLOOP.
      LOOP AT o_pfk INTO DATA(ls_m_pfk).
        IF NOT line_exists( pfk[ code = ls_m_pfk-code pfno = ls_m_pfk-pfno ] ).
          APPEND ls_m_pfk TO pfk.
        ENDIF.
      ENDLOOP.
      LOOP AT o_act INTO DATA(ls_m_act).
        IF NOT line_exists( act[ code = ls_m_act-code no = ls_m_act-no ] ).
          APPEND ls_m_act TO act.
        ENDIF.
      ENDLOOP.
      LOOP AT o_but INTO DATA(ls_m_but).
        IF NOT line_exists( but[ code = ls_m_but-code pfk_code = ls_m_but-pfk_code
                                 no = ls_m_but-no ] ).
          APPEND ls_m_but TO but.
        ENDIF.
      ENDLOOP.
*     doc: RSMPE_ATRT anahtari OBJ_TYPE + OBJ_CODE + SUB_CODE.
      LOOP AT o_doc INTO DATA(ls_m_doc).
        IF NOT line_exists( doc[ obj_type = ls_m_doc-obj_type obj_code = ls_m_doc-obj_code
                                 sub_code = ls_m_doc-sub_code ] ).
          APPEND ls_m_doc TO doc.
        ENDIF.
      ENDLOOP.
      LOOP AT o_biv INTO DATA(ls_m_biv).
        IF NOT line_exists( biv[ obj_code = ls_m_biv-obj_code sub_code = ls_m_biv-sub_code
                                 fcode = ls_m_biv-fcode ] ).
          APPEND ls_m_biv TO biv.
        ENDIF.
      ENDLOOP.
*     ⛔ men/mtx BILEREK MERGE EDILMEZ: bu FM menu cubugu URETMEZ ve `adm-mencode`
*       CLEAR edilir (yukaridaki "TOOLBAR/MENU TEMIZLIGI") -> geri eklenen menuler
*       REFERANSSIZ kalirdi. Elle yapilmis menu cubugu olan bir programda bu FM
*       menuyu kaldirir; bu ONCEDEN BERI boyleydi, merge onu DEGISTIRMEZ.
    ENDIF.

*   DEVCLASS = HEDEF PROGRAMIN gercek paketi; SABIT OLAMAZ. Eskiden ortak paketin
*   adi sabit yaziliydi, oysa bu FM jeneriktir ve baska paketlerdeki programlar
*   icin de cagriliyor -> tr_key BASKA bir paketin adiyla dolduruluyordu.
*   ⚠ DURUST OLCUM (abartma yok): bugunku surumde RS_CUA_INTERNAL_WRITE tr_key'in
*     YALNIZ OBJ_TYPE / OBJ_NAME / SUB_TYPE / SUB_NAME alanlarini okuyor; DEVCLASS'i
*     HICBIR YERDE okumuyor [olculdu: RS_CUA_INTERNAL_WRITE tam kaynak +
*     tuketicileri LSMPIF01 tree_update:1231-1287 ve actual_index:1289-1317 tarandi,
*     `tr_key-devclass` referansi YOK]. Yani sabit deger BUGUN yanlis pakete/
*     transport'a yazmiyordu -- kusur LATENT bir DOGRULUK kusuruydu ve bu duzeltme
*     de olculebilir bir DAVRANIS DEGISIKLIGI URETMEZ (canli 4 ekran icin risksiz).
*     Duzeltilmesinin sebebi: alan bir gun okunursa dogru degeri tasisin.
*   Yontem standardin KENDI deseni: TADIR'dan SALT-OKUMA (kesin yasak B: standart
*   tabloya YAZMA yok, okuma serbest) [emsal: LSMPIF03 get_application_comp:29-32,
*   birebir ayni WHERE].
*   ⛔ TADIR'i "Clean Core" adina I_CustABAPObjDirectoryEntry ile DEGISTIRME --
*     SESSIZ REGRESYON olabilir. Released-successor onerisi bu view'i gosterir;
*     kaynak ekipte CANLI OLCUM oneriyi curuttu:
*       · bir Z program icin `SELECT ... FROM i_custabapobjdirectoryentry` -> 0 SATIR
*         (ayni sorgu TADIR'da programin paketini dondurdu)
*       · view yalnizca birkac SAP paketi (ST-A/PI) iceriyordu
*       · sebep: view `I_CustABAPPackage` ile JOIN'li = yalnizca yazilim bileseni
*         tipi 'C' olan paketler; musteri paketleri `TDEVC-DLVUNIT = 'HOME'`
*         -> JOIN ELER.
*     ⇒ Gecilseydi devclass HER cagirici icin BOS kalirdi. Clean Core uyarisi
*       BILEREK kabul ediliyor (oneri, hard kural degil). Kendi sisteminde
*       view'i kullanmak istersen once ayni sorguyla olc.
*   TADIR'da kayit yoksa alan BOS birakilir ve EV_MESSAGE'da GORUNUR yapilir --
*   burada RETURN etmek, okunmayan bir alan yuzunden CALISAN akisi kirmak olurdu
*   (var olmayan riske karsi yeni hata yolu acmak).
    SELECT SINGLE devclass FROM tadir
      WHERE pgmid    = 'R3TR'
        AND object   = 'PROG'
        AND obj_name = @iv_program
      INTO @l_trkey-devclass.
    IF sy-subrc <> 0.
      CLEAR l_trkey-devclass.
      l_devcl_miss = abap_true.
    ENDIF.
    l_trkey-obj_type = 'PROG'.
    l_trkey-obj_name = iv_program.
    l_trkey-sub_type = 'CUAD'.
    l_trkey-sub_name = iv_program.

    CALL FUNCTION 'RS_CUA_INTERNAL_WRITE'
      EXPORTING
        program      = iv_program
        language     = sy-langu
        tr_key       = l_trkey
        adm          = adm
        state        = 'A'
      TABLES
        sta          = sta
        fun          = fun
        men          = men
        mtx          = mtx
        act          = act
        but          = but
        pfk          = pfk
        set          = sett
        doc          = doc
        tit          = tit
        biv          = biv
      EXCEPTIONS
        not_found    = 1
        invalid_data = 2
        OTHERS       = 3.
    l_stat_rc = sy-subrc.

*   WRITE tanimi yazar ama runtime CUA load'unu URETMEZ (hata 00264:
*   "not generated"). GENERATE ile interface'i uret (dialog context).
    IF l_stat_rc = 0.
      CALL FUNCTION 'RS_CUA_GENERATE'
        EXPORTING
          objectname           = iv_program
          without_messages     = 'X'
          without_checks       = 'X'
        EXCEPTIONS
          not_excecuted        = 1
          object_not_found     = 2
          object_not_specified = 3
          permission_failure   = 4
          OTHERS               = 5.
      l_gen_rc = sy-subrc.
    ENDIF.
  ENDIF.

*--- Sonuc --------------------------------------------------------------
  ev_rc = l_screen_rc + l_stat_rc + l_gen_rc.
* `donor=...`: donör parametrik oldugu icin
* hangi donörün kullanildigi ciktida GORUNUR olmali — cagiran varsayilani mi aldi,
* yoksa kendi verdigini mi, tahmin etmek zorunda kalmasin.
  ev_message = |screen({ iv_program }/{ iv_dynpro }) rc={ l_screen_rc }; | &&
               |status({ l_status }+{ l_tit }) rc={ l_stat_rc } | &&
               |donor={ iv_src_prog }/{ iv_src_status }| &&
*              TEK `nav_remap=` TOKEN'I: uygulanan karar (ON/OFF) burada, taninmayan
*              girisin kendisi ise L_ARG_DIAG'da (asagida) raporlanir. Iki ayri
*              `nav_remap=` token'i yan yana yazmak makine-okunurlugunu bozuyordu.
               COND string( WHEN l_nav_remap = abap_true
                            THEN | nav_remap=ON(F3/Sh+F3/F12->BACK/EXIT/CANCEL)|
                            ELSE | nav_remap=OFF(donör fcode'lari AYNEN; hedef PAI onlari| &&
                                 | yakalamali)| ) && |; | &&
               |generate rc={ l_gen_rc }|.
* CUA MERGE gorunurlugu: kac YABANCI status/titlebar KORUNDU. Cagiran bunu
* gorerek "onceki ekranlarim duruyor mu?" sorusunu KANITLA yanitlar.
* UC DURUM AYRI raporlanir -- "merge kosmadi" ile "merge kostu, korunacak sey yoktu"
* AYNI SEY DEGILDIR: ikisi de eskiden `cua_merge=none`/`ok kept=0` gorunup cagirani
* yaniltiyordu (bkz. L_MERGE_RC bildirimi).
  IF l_merge_rc = 0.
    ev_message = ev_message && |; cua_merge=ok kept_status={ l_merge_sta }| &&
                               | kept_title={ l_merge_tit }|.
  ELSEIF l_merge_rc = 1.
    ev_message = ev_message && |; cua_merge=none(programin onceden CUA'si yoktu| &&
                               | -- ilk uretim, normal)|.
  ELSEIF l_merge_rc = -2.
*   Cagiran IV_CUA_MERGE=' ' ile merge'i KAPATTI. Bu bilgi ciktida DURMALI: aksi
*   halde "kept_status" hic gorunmedigi icin merge kosmus da korunacak sey mi yoktu,
*   yoksa hic mi kosmadi ayirt edilemezdi (mevcut uc-durum ayriminin dorduncusu).
    ev_message = ev_message && |; cua_merge=KAPALI(IV_CUA_MERGE='{ iv_cua_merge }'| &&
                               | verildi -> hedef programin DIGER status/titlebar'lari| &&
                               | SILINDI)|.
  ELSE.
    ev_message = ev_message && |; cua_merge=KOSMADI(donör CUA fetch basarisiz -> | &&
                               |status adimina hic girilmedi; korunan/silinen status| &&
                               | bilgisi YOK)|.
  ENDIF.
* Taninmayan giris tanilari (IV_CUA_MERGE / IV_NAV_REMAP) -- iki erken cikisla AYNI
* metin, tek kaynaktan. Bos ise ekleme yapmaz, mesaj bugunku ile birebir kalir.
  ev_message = ev_message && l_arg_diag.
* Donör status'un set havuzu eksikse SESSIZ KALINMAZ (bkz. donör-agnostik guard).
  IF l_setcode_miss IS NOT INITIAL.
    ev_message = ev_message && |; DIKKAT: donör status'te set kodu YOK ->| &&
                               |{ l_setcode_miss } havuzu BOS baslatildi (fonksiyonlar| &&
                               | gecersiz kalabilir -> runtime 00256); baska bir donör| &&
                               | status secin ya da IT_BUTTONS ile fonksiyon verin|.
  ENDIF.
* TR_KEY-DEVCLASS cozulemedi -> SESSIZ birakilmaz. Bugun bu alan WRITE tarafindan
* okunmuyor (bkz. devclass atamasindaki olcum) -> hata DEGIL, ama "cozulemedi" ile
* "cozuldu" ayirt edilebilir kalsin ki ileride alan okunmaya baslarsa iz elimizde olsun.
  IF l_devcl_miss = abap_true.
    ev_message = ev_message && |; devclass=COZULEMEDI({ iv_program } icin TADIR| &&
                               | R3TR/PROG kaydi yok -> tr_key-devclass BOS gonderildi)|.
  ENDIF.
* IT_FIELDS raporu SADECE alan verildiginde eklenir -> IT_FIELDS bos oldugunda
* EV_MESSAGE metni de bugunku ile BIREBIR ayni kalir (geriye-donuk uyumluluk).
  IF it_fields[] IS NOT INITIAL.
    ev_message = ev_message && |; fields={ lines( lt_f2c ) } io_default={ l_io_def }|.
    IF l_io_def > 0.
      ev_message = ev_message && | (io_default = INPUT_FLD/OUTPUT_FLD verilmedigi icin| &&
                                 | GIRIS+CIKIS'a acilan TEMPLATE alan sayisi; salt-okunur| &&
                                 | isteniyorsa OUTPUT_FLD='X' ya da REQU_ENTRY='N' ver)|.
    ENDIF.
*   CONTAINER modunda CC_ALV tum ekrani kaplar (line 1..200, column 1..255) ->
*   koke konan her alan onunla CAKISIR ve RS_SCRP_CHECK_FIELD_POSITIONS
*   illegal_field_value (rc=6) verir. Alan ekrani icin DOCKING kullanilmali.
    IF iv_screen_type = 'CONTAINER'.
      ev_message = ev_message && |; DIKKAT: CONTAINER modu + IT_FIELDS -> CC_ALV| &&
                                 | tum ekrani kapladigi icin alan cakismasi (rc=6)| &&
                                 | beklenir; alan ekrani icin DOCKING kullan|.
    ENDIF.
  ENDIF.
ENDFUNCTION.