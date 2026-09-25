# EML — kendi BO'n ve released BO (I_SalesOrderTP) ile create / update

> Kaynak: ekip "released satış siparişi BO'su EML ile create/update" nasıl-yapılır dokümanı, RAP playbook'unun EML ve
> `editableFieldFor` bölümleri, RAP standardı ve ekip hafıza dersleri; aXet'e uyarlandı.
> Profil: `s4_private` ve `s4_public` (released BO); ölçümler `s4_private`'ta. `SAVE_TEXT` ve klasik FM'ler `s4_public`/
> `btp_abap`'ta released değildir → orada alternatif **DOĞRULANMADI**.
> Yasak B: standart tabloya doğrudan yazma yok. Released BO'ya EML, sıranın ilk adımıdır (released API → BAPI → RFC FM → BDC →
> manuel); released olmayan BO/tabloya EML ya da SQL ile yazılmaz. EML'i seçmeden önceki 4 canlı teyit (BDEF · operasyon açık ·
> alan yazılabilir · metin/numara/muhatap boşlukları) ve tutmazsa inilecek adım: `%sap-dev` → `write-api-selection.md`.

## 0. Özet kurallar (önce bunlar)

1. Tek `MODIFY ENTITIES` bloğu; tüm `DATA` metot başında; `%cid` benzersiz; set edilen **her** alan `%control`'da `mk-on`.
2. `FAILED` hem MODIFY sonrasında hem COMMIT sonrasında **ayrı ayrı** kontrol edilir. "Created" ≠ "saved".
3. `COMMIT ENTITIES` yalnız handler **dışındaki** tüketicide (klasik program, classrun) yazılır. Behavior handler içinde yasak
   (`behavior-impl.md` §10).
4. Standart muhatapları (AG/RE/RG/WE) elle ekleme — `SoldToParty` ile müşteri ana verisinden otomatik gelir.
5. COMMIT'te jenerik "Kaydetme başarısız oldu" → neredeyse her zaman **veri/ana veri** (§6).
6. Buffer başarısı kalıcılık değildir → geri oku (READ / işlem koduyla) ve doğrula.

## 1. Create — deep create (başlık + kalem), muhatap otomatik

```abap
DATA lt_so   TYPE TABLE FOR CREATE i_salesordertp.
DATA lt_item TYPE TABLE FOR CREATE i_salesordertp\_Item.

lt_so = VALUE #( ( %cid = 'H'
  SalesOrderType = lv_auart  SalesOrganization = lv_vkorg  DistributionChannel = lv_vtweg
  OrganizationDivision = lv_spart  SoldToParty = lv_kunnr_alpha        " AG buradan -> diğerleri otomatik
  PurchaseOrderByCustomer = lv_bstkd  SalesOrderDate = lv_audat
  %control = VALUE #( SalesOrderType = if_abap_behv=>mk-on … ) ) ).
" TransactionCurrency / PricingDate verme -> müşteri ana verisinden gelir. Yalnız farklı olacaksa ver.

lt_item = VALUE #( ( %cid_ref = 'H' %target = VALUE #(
  ( %cid = 'HI1' Product = lv_matnr RequestedQuantity = lv_menge
    RequestedQuantityUnit = lv_vrkme          " malzeme için GEÇERLİ birim olmalı, yoksa save düşer
    Plant = lv_werks StorageLocation = lv_lgort RequestedDeliveryDate = lv_termin
    %control = VALUE #( Product = if_abap_behv=>mk-on … ) ) ) ) ).

MODIFY ENTITIES OF i_salesordertp
  ENTITY SalesOrder
    CREATE FROM lt_so
    CREATE BY \_Item FROM lt_item
  MAPPED DATA(ls_mapped) FAILED DATA(ls_failed) REPORTED DATA(ls_reported).

IF ls_failed-salesorder IS NOT INITIAL OR ls_failed-salesorderitem IS NOT INITIAL.
  " ls_reported'tan %msg->if_message~get_text( ) ile topla; RETURN
ENDIF.
```

## 2. Late numbering — kesin numara (yalnız handler dışı tüketici)

```abap
COMMIT ENTITIES BEGIN RESPONSE OF i_salesordertp FAILED DATA(lt_cf) REPORTED DATA(lt_cr).
IF lt_cf IS INITIAL.
  LOOP AT ls_mapped-salesorder ASSIGNING FIELD-SYMBOL(<m>).
    CONVERT KEY OF i_salesordertp FROM <m>-%pid TO FINAL(ls_key).   " ön anahtar -> gerçek belge no
    lv_vbeln = ls_key-salesorder.
  ENDLOOP.
ENDIF.
COMMIT ENTITIES END.
IF lt_cf IS NOT INITIAL.   " COMMIT ayrıca kontrol; jenerik "save failed" ise §6
ENDIF.
```
- `CONVERT KEY` yalnız `COMMIT ENTITIES BEGIN … END` içinde geçerlidir.
- **Behavior handler action'ında** (OData üzerinden): COMMIT yasak; `I_SalesOrderTP` numarayı SAVE anında atar → action
  `mapped-salesorder`'ı **boş** alır, yanıtta numara senkron dönmez (`Success = X` ama numara boş); sipariş yine yaratılır.
  Çözüm: başarıdan sonra tüketici, müşteri PO referansıyla released sipariş CDS'ini yeniden sorgulayıp numarayı bulur. (Klasik
  SEGW/DPC normal ABAP bağlamında commit + okuma yapabildiği için bunu yapabiliyordu.)

## 3. Action içinde SAVE'e bağlı yan etki (ör. sipariş notu) — ÇALIŞAN desen

Senaryo: create action'ı kaydı yaratıp hemen ardından ona bağlı bir şey (not metni) yazmak istiyor, ama gerçek anahtar yok ve
tüketilen BO released/unmanaged olduğu için kendi save kancan da yok.

- **Yanlış refleks:** boş anahtarla yan etkiyi yine denemek (alt katman sessizce reddeder → kullanıcıya sahte "not
  kaydedilemedi"); ya da action içinde bekleme/polling/senkron commit zorlamak (handler'da yasak).
- **Doğru desen:**
  1. Yan etkiyi **ayrı bir action**'a taşı; gerçek anahtarı parametre olarak dışarıdan alsın (yeni parametre entity'sinin alan
     adı/tipi mevcut benzerlerinden aynen kopyalanır). Test edilmiş yazıcı metodun gövdesine dokunma, yeni action onu sarsın.
  2. Create action'daki çağrıyı anahtar guard'ıyla koru: anahtar boşsa yan etkiyi **deneme ve uyarma** (tüketici birazdan
     başarıyla yazacak).
  3. Yeni action'ın guard'ları: anahtar boşsa net mesajla reddet · varlık kontrolünde **DCL'li released CDS değil ham tablo**
     oku (DCL kısıtlı kullanıcıda released CDS hata vermeden 0 satır döner ve meşru yazmayı bloklar; okuma yasak değildir) ·
     kilit gerekiyorsa mevcut uygulama kilidinin salt-okunur `check()`'i ile yalnız **başkası** tutuyorsa reddet.
  4. Tüketici gerçek anahtarı yeniden sorguyla bulduktan sonra yeni action'ı çağırır ve bu iki adımlı akışın **her başarısızlık
     dalını** (action başarısız / action hata / sorgu anahtar bulamadı / sorgu hata) kullanıcıya açıkça bildirir.

## 4. Muhatap (partner) — neden elle eklenmez

- Released BO'da `_Partner` create'inde `PartnerFunction` key ve salt-okunurdur:
  `%control`/`FIELDS`'e koymak → `BEHAVIOR_READONLY_FIELD` dump ("Field PARTNERFUNCTION is read-only"); koymamak → `VPD 030`
  "Muhatap rolünü girin".
- Yeni siparişte standart muhataplar `SoldToParty`'den otomatik belirlenir (canlı siparişlerde hepsi otomatik ölçüldü).
- Çalışan eski kod `ls_failed-salesorderpartner`'ı kontrol etmiyorsa muhatap hatasını **yutar**; sipariş otomatik muhataplarla
  yaratılır → "çalışıyor" sanılır.
- Farklı ship-to gerekiyorsa `_Partner` üzerinden kör ekleme yapılmaz; doğru mekanizma (başlık alanı / determinasyon / ayrı
  action) araştırılır.

## 5. Mevcut belgeye child ekleme — `editableFieldFor` (ÇALIŞAN)

**Belirti:** mevcut siparişe `CREATE BY \_Partner` ile eklenen muhatap boş fonksiyonla oluşur ("Muhatap için muhatap rolünü
girin"); aynı kod yeni sipariş deep create'inde çalışır.

**Kök neden (projeksiyon CDS kaynağında görünür):**
```
key SalesOrderPartner.PartnerFunction,              // key → create'te yazılamaz
    @ObjectModel.editableFieldFor: 'PartnerFunction'
    SalesOrderPartner.PartnerFunctionForEdit,       // create'te set edilecek alan
```

```abap
MODIFY ENTITIES OF i_salesordertp
  ENTITY SalesOrder CREATE BY \_Partner FIELDS ( PartnerFunctionForEdit Customer )
    WITH VALUE #( ( SalesOrder = lv_vbeln
      %target = VALUE #( ( %cid = 'P1' PartnerFunctionForEdit = '<Z_MUHATAP_FONKSIYONU>' Customer = lv_kunnr_alpha ) ) ) )
  MAPPED DATA(ls_m) FAILED DATA(ls_f) REPORTED DATA(ls_r).
```
- `Customer` ALPHA ile 10 haneye doldurulmuş olmalı (doldurulmamış → boş muhatap, ayrı tuzak).
- Yeni belge deep create'inde (`%cid_ref` root'a) key doğrudan çalışır; yalnız **mevcut belgeye ekleme** `…ForEdit` ister.
- Önce mevcut muhatap fonksiyonlarını oku ve yönlendir: varsa `UPDATE`, yoksa `CREATE BY \_Partner` (`ForEdit` ile),
  kaldırıldıysa `DELETE`.

**DENENEN — BAŞARISIZ**
| Deneme | Sonuç |
|---|---|
| Olmayan muhatabı `UPDATE` | `NOT_FOUND` |
| `%target ( PartnerFunction = … )` | fonksiyon boş → "rol girin" (key yok sayıldı) |
| `FIELDS ( PartnerFunction Customer )` | aktivasyon: `PARTNERFUNCTION not a valid field` |
| Ayrı MODIFY'ı ana MODIFY'a taşımak | etkisiz (sorun kapsam değil alan eşlemesiydi) |
| "Released BO kısıtı, BAPI'ye geç" | yanlış sonuç; çözüm standart RAP'teydi |

**Süreç dersi:** `CREATE BY \_assoc` bir alanı yok sayıyorsa ya da `FIELDS(key)` "not a valid field" diyorsa tahmin etme,
BAPI'ye kaçma → **önce projeksiyon CDS kaynağını oku** (`cli adt_get '{"name":"I_SALESORDERPARTNERTP","object_type":"ddls"}'`)
ve `@ObjectModel.editableFieldFor`, `@ObjectModel.readonly`, gizlenmiş alanları ara. Released BO'da yazılamayan key'in
neredeyse her zaman bir `…ForEdit` muadili vardır. (Standart objeyi **okumak** yasak değildir.)

## 6. COMMIT "Kaydetme başarısız oldu" teşhisi — veri önce

MODIFY (etkileşim fazı) geçer, SAVE reddeder. Sıra (kod değil veri):
1. **Birim:** kalem birimi malzeme için tanımlı mı? `SELECT DISTINCT RequestedQuantityUnit FROM i_salesorderitem WHERE Material = '<MATNR>'`
   (`adt_sql_query`; KVKK kuralı QA/PRD'de geçerli).
2. **Fiyat:** benzer geçerli siparişte `TotalNetAmount > 0` mı? 0 ise koşul kaydı yok → fiyatlanamayan sipariş reddedilebilir.
3. Malzeme/üretim yeri/depo satış alanına genişletilmiş mi; müşteri satış alanında tanımlı mı.
4. Girdi doğrulaması ekle: EML'e gitmeden birim/malzeme geçerliliğini kontrol et, net mesaj ver ("Birim X, malzeme Y için geçersiz").

**Vergi (KDV) = 0 geliyorsa:** önce **müşteri ana verisindeki vergi sınıflandırması** (vergisiz/0 seçili olabilir), malzeme vergi
sınıfı, üretim yeri ülkesi; ancak sonra EML/fiyatlandırma kodu. Kontrol grubu: aynı kodla daha önce vergili yaratılmış bir belge
varsa kod suçsuzdur, veri/konfigürasyon değişmiştir (ölçülen vakada kullanıcı ana veriyi düzeltince çözüldü).

## 7. Update — mevcut siparişe kalem ekleme / miktar değiştirme

```abap
DATA lt_new TYPE TABLE FOR CREATE i_salesordertp\_Item.
DATA lt_upd TYPE TABLE FOR UPDATE i_salesordertp\\SalesOrderItem.
lt_new = VALUE #( ( SalesOrder = lv_vbeln %target = VALUE #(
  ( %cid = 'U1' Product = lv_matnr RequestedQuantity = lv_menge RequestedQuantityUnit = lv_vrkme Plant = lv_werks
    %control = VALUE #( … ) ) ) ) ).
lt_upd = VALUE #( ( SalesOrder = lv_vbeln SalesOrderItem = lv_posnr RequestedQuantity = lv_menge
                    %control-RequestedQuantity = if_abap_behv=>mk-on ) ).
MODIFY ENTITIES OF i_salesordertp
  ENTITY SalesOrderItem UPDATE FROM lt_upd
  ENTITY SalesOrder     CREATE BY \_Item FROM lt_new
  MAPPED … FAILED … REPORTED ….
COMMIT ENTITIES RESPONSE OF i_salesordertp FAILED … REPORTED ….   " key bilindiği için CONVERT KEY yok (handler dışı)
```

## 8. Belge başlık metni — kalıcılık tuzağı (unmanaged static action)

Ölçüldü (runtime): bu senaryoda
- `CREATE BY \_Text` tamponda başarılı (`FAILED` boş) ama controlled commit ayrı metin değişikliğini **kalıcı yazmaz**;
- varsayılan `SAVE_TEXT` `sy-subrc = 0` döner ama metin belleğini `COMMIT WORK` ile boşaltır, RAP commit'i bunu tetiklemez.

**ÇALIŞAN:** `SAVE_TEXT … savemode_direct = 'X'` (senkron doğrudan yazım, `COMMIT WORK` bağımlılığı yok; üzerine yazar, boş içerik temizler).
```abap
ls_header-tdobject = 'VBBK'. ls_header-tdname = lv_vbeln. ls_header-tdspras = sy-langu. ls_header-tdid = '<METIN_ID>'.
APPEND VALUE tline( tdformat = '*' tdline = lv_note ) TO lt_lines.
CALL FUNCTION 'SAVE_TEXT' EXPORTING header = ls_header savemode_direct = 'X' TABLES lines = lt_lines EXCEPTIONS OTHERS = 1.
" Okuma: READ ENTITIES OF i_salesordertp ENTITY SalesOrder BY \_Text ALL FIELDS WITH VALUE #( ( SalesOrder = lv_vbeln ) ) RESULT DATA(lt_text).
```
Metin ID'leri projeden (spesifikasyon) gelir. **Süreç dersi:** takılınca yaklaşım değiştirmek (EML ↔ `SAVE_TEXT`) yerine kök sebebi
runtime teşhisiyle bul (burada sorun commit'ti); kalıcılığı geri okuyarak doğrula.

## 9. Teşhis — classrun ile mesaj kimliği yakalama

EML denemesini izole etmek için `IF_OO_ADT_CLASSRUN` sınıfı; her `reported` mesajını T100 kimliğiyle dök (jenerik metin yetmez):
```abap
METHOD msg_line.   " IMPORTING io_msg TYPE REF TO if_abap_behv_message RETURNING VALUE(rv) TYPE string
  rv = io_msg->if_message~get_text( ).
  TRY.
      DATA(lo_t) = CAST if_t100_message( io_msg ).
      rv = |[{ lo_t->t100key-msgid } { lo_t->t100key-msgno }] { rv }|.   " ör. [VPD 030] …
    CATCH cx_root.
  ENDTRY.
ENDMETHOD.
```
- `io_msg->m_severity` doğrudan erişilir; `io_msg->if_abap_behv_message~m_severity` → "class does not contain interface" aktivasyon hatası.
- `does not implement …~main` doğru bir mesajdır: sınıf aktive edilmemiş ya da oturum bayat. **Yeni adla sınıf yaratma** (denendi,
  çözmedi, çöp obje bıraktı) → `%sap-adt-foundation` → `known-errors-adt.md` K-13.
- Classrun kod çalıştırır ve yazabilir → yazma sınıfı; DEV + onay. EML create'i classrun'da COMMIT'le denemek gerçek belge yaratır.
