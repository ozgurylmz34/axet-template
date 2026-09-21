# DPC_EXT — okuma, yazma, kilit, hata

> Kaynak: ekip backend kodlama standardı (DPC_EXT deseni, locking, ETag, hata hiyerarşisi, BAPI helper,
> güvenlik), RAP playbook'u (klasik DB-commit yasağı ve ayrı-LUW deseni), OData servisleri playbook'u
> (BAPIRET2), backend hata kontrol listesi (commit, audit), ekip hafızası (audit alanları).
> Kod örnekleri desendir: yer tutucular `{app}`, `{entityset}`, `Z{AUTH_OBJ}` projeden doldurulur; BAPI/FM adları
> sistemde `adt_search_objects` / `adt_get` ile doğrulanmadan kullanılmaz.

---

## 1. DPC_EXT iskeleti
```abap
CLASS zcl_{app}_dpc_ext DEFINITION INHERITING FROM zcl_{app}_dpc FINAL CREATE PUBLIC.
  PUBLIC SECTION.
  PROTECTED SECTION.
    METHODS {entityset}_get_entityset REDEFINITION.   " koleksiyon okuma
    METHODS {entityset}_get_entity    REDEFINITION.   " tek kayıt
    METHODS {entityset}_create_entity REDEFINITION.   " POST
    METHODS {entityset}_update_entity REDEFINITION.   " PUT/MERGE
    METHODS {entityset}_delete_entity REDEFINITION.   " DELETE
ENDCLASS.
```
- Yalnız gerçekten uyguladığın metodu redefine et; uygulanmayan metodu boş redefine etme (framework ya da super kalsın).
- Function import ve deep insert: `references/deep-insert-function-import.md`.

---

## 2. GET_ENTITYSET

```abap
METHOD {entityset}_get_entityset.
  " Filtre parametrelerini DAİMA kullan — tabloyu filtresiz dönme
  DATA(lo_filter)  = io_tech_request_context->get_filter( ).
  DATA(lt_filters) = lo_filter->get_filter_select_options( ).

  DATA(lt_bukrs) = VALUE #( lt_filters[ property = 'CompanyCode' ]-select_options DEFAULT VALUE #( ) ).

  " Yol A — CDS üzerinden SELECT
  SELECT entity_id, description, status, bukrs, amount, currency
    FROM zsd001_c_order                      " consumption CDS (örnek ad)
    WHERE bukrs  IN @lt_bukrs
      AND status <> 'X'                      " silinmiş kayıt dönmez
    ORDER BY entity_id
    INTO TABLE @DATA(lt_result).

  " Yol B — karmaşık okuma için RFC FM
  " CALL FUNCTION 'Z…_GET_LIST' … ; sy-subrc <> 0 → /iwbep/cx_mgw_busi_exception (§6)

  " Sunucu tarafı paging — atlanmaz
  DATA(lv_top)  = io_tech_request_context->get_top( ).
  DATA(lv_skip) = io_tech_request_context->get_skip( ).
  " $top/$skip'e göre lt_result'tan dilim al → et_entityset

  " $inlinecount=allpages
  IF io_tech_request_context->is_inline_count_requested( ).
    es_response_context-inlinecount = lines( lt_result ).
  ENDIF.
ENDMETHOD.
```
- **Dilimleme sözdizimi:** kaynak standarttaki `lt_result[ skip + 1 .. MIN( … ) ]` biçimi ABAP'ta geçerli bir tablo
  dilimleme ifadesi olarak **DOĞRULANMADI**; `LOOP AT lt_result FROM lv_skip + 1 TO …` ya da `APPEND LINES OF
  lt_result FROM … TO … TO et_entityset` ile yaz ve aktivasyonla doğrula.
- Tüm filtreler `WHERE`'de; veriyi çekip ABAP'ta süzme yok (`references/backend-coding.md` §1).
- Ad filtreleri, `substringof` ve büyük/küçük harf davranışı: `references/filter-search.md`.
- `$expand` — derinliği sınırla, yalnız istenince yükle:
  ```abap
  DATA(lt_expand) = io_tech_request_context->get_expanded_tech_clauses( ).
  " lt_expand'da ilgili navigation varsa kalemleri oku; yoksa hiçbir şeyi otomatik join etme
  ```
  Kaynaktaki `line_exists( lt_expand[ na_src_entity_set_name = … ] )` biçimindeki alan adları bu metodun dönüş
  tipiyle **DOĞRULANMADI**; metodun imzasını sistemde (`adt_get` ile `/IWBEP/IF_MGW_REQ_ENTITYSET`) oku.

---

## 3. CREATE / UPDATE / DELETE — kesin yasak B

**Standart tabloya OData üzerinden doğrudan yazma yoktur** (SAP çekirdeği, kesin yasak B). DPC_EXT içinde
`INSERT/UPDATE/MODIFY/DELETE` yalnız **projenin kendi Z tablosuna** yazılabilir; standart veri için sıra:
BAPI → RFC FM → BDC → kullanıcıdan manuel. CLI yazma kapısı kaynakta standart tabloya DML görürse `ADR_0005_B`
(çıkış 2) ile reddeder — komutu eğip bükme, DUR.

```abap
METHOD {entityset}_create_entity.
  DATA ls_input TYPE z{app}_s_create_input.
  io_data_provider->read_entry_data( IMPORTING es_data = er_entity ).
  ls_input-description = er_entity-description.
  ls_input-bukrs       = er_entity-bukrs.

  " Yetki — her yazmadan ÖNCE
  AUTHORITY-CHECK OBJECT 'Z{AUTH_OBJ}'
    ID 'ACTVT' FIELD '01'
    ID 'BUKRS' FIELD ls_input-bukrs.
  IF sy-subrc <> 0.
    RAISE EXCEPTION TYPE /iwbep/cx_mgw_busi_exception
      EXPORTING textid  = /iwbep/cx_mgw_busi_exception=>business_error
                message = 'Not authorized'.
  ENDIF.

  " BAPI / RFC FM çağrısı → lt_return (BAPIRET2)
  " E veya A varsa: BAPI_TRANSACTION_ROLLBACK + busi_exception (mesajla)
  " yoksa:          BAPI_TRANSACTION_COMMIT EXPORTING wait = abap_true

  er_entity-entity_id = lv_new_id.   " yaratılan anahtarı dön
ENDMETHOD.
```
- Kaynaktaki `IMPORTING ev_id = DATA(…)` / `TABLES et_return = DATA(…)` satır-içi tanımı `CALL FUNCTION`'da
  **kullanma**: BAPI parametreleri önceden tanımlı değişkene bağlanır (imzayı `adt_get` ile oku).
- BAPI dönüşü `COMMIT`'ten önce **her zaman** `E`/`A` için kontrol edilir.
- Hata mesajı tipi olarak özel Z yapı değil standart `BAPIRET2` / `BAPIRET2_T` kullanılır.

### 3.1 BAPI dönüş yardımcısı (proje başına bir kez)
```abap
CLASS zcl_{app}_bapi_helper DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    CLASS-METHODS check_return
      IMPORTING it_return       TYPE bapirettab
      RETURNING VALUE(rv_error) TYPE string
      RAISING   /iwbep/cx_mgw_busi_exception.
    CLASS-METHODS commit.
    CLASS-METHODS rollback.
ENDCLASS.

CLASS zcl_{app}_bapi_helper IMPLEMENTATION.
  METHOD check_return.
    DATA(lt_errors) = VALUE bapirettab( FOR ls IN it_return WHERE ( type = 'E' OR type = 'A' ) ( ls ) ).
    IF lt_errors IS NOT INITIAL.
      rv_error = concat_lines_of( table = VALUE string_table( FOR ls_err IN lt_errors ( ls_err-message ) )
                                  sep   = ` | ` ).
      rollback( ).
      RAISE EXCEPTION TYPE /iwbep/cx_mgw_busi_exception
        EXPORTING textid = /iwbep/cx_mgw_busi_exception=>business_error message = rv_error.
    ENDIF.
  ENDMETHOD.
  METHOD commit.
    CALL FUNCTION 'BAPI_TRANSACTION_COMMIT' EXPORTING wait = abap_true.
  ENDMETHOD.
  METHOD rollback.
    CALL FUNCTION 'BAPI_TRANSACTION_ROLLBACK'.
  ENDMETHOD.
ENDCLASS.
```
Sınıf adı `%sap-dev` naming §4.5'e göre verilir (ör. `ZCL_SD001_BAPI_HELPER`); ad kullanıcı onaylı. Genel amaçlı
bir yardımcıya program/servis adı verilmez.

---

## 4. COMMIT kuralları — klasik DPC ↔ RAP

| Bağlam | `BAPI_TRANSACTION_COMMIT` / `COMMIT WORK` |
|---|---|
| Klasik SEGW DPC_EXT (`/iwbep/cx_mgw_*`) | BAPI dönüşü temizse yapılır (§3) |
| RFC FM, DPC'den çağrılıyor | FM içinde **commit yok**; commit DPC_EXT'te BAPI dönüşü doğrulandıktan sonra |
| RAP behavior handler **ya da handler'dan çağrılan yardımcı sınıf** | **YASAK** → çalışma zamanında `BEHAVIOR_ILLEGAL_STATEMENT` dump |
| Gateway function import içinden EML (`MODIFY ENTITIES`) | `COMMIT ENTITIES` **yapılmaz**; Gateway kendi `COMMIT WORK`'ünü yapar (`references/deep-insert-function-import.md` §4) |

- RAP yasağı sözdizimi kontrolünde, ATC'de ve aktivasyonda **görünmez**; yalnız ilk gerçek create/action çağrısında
  dump olarak çıkar (ölçüldü: statik kontrollerin hepsi geçti, ilk çalıştırmada dump). CLI'nin gömülü incelemesinde
  bu kontrol **yok** (aranan: `commit work`, `BAPI_TRANSACTION`; aXet'te araç yok) → push öncesi elle tara.
- **RAP'ten commit isteyen klasik BAPI çağırmanın çalışan yolu (ayrı LUW):** BAPI + commit/rollback'i bir
  **Z RFC-enabled FM**'e sar; çağıran `CALL FUNCTION '<Z_FM>' DESTINATION 'NONE'` der. `'NONE'` ayrı roll area/LUW
  açar, commit orada geçerlidir. Sınıfta commit yok. Tuzaklar:
  - FM **Remote-Enabled** işaretli olmalı (SE37 processing type; ADT'den ayarlanamadı → kullanıcı işaretler), yoksa
    `CALL_FUNCTION_NOT_REMOTE`.
  - `TABLES` parametresi: ADT push `STRUCTURE` kabul etmez; `TYPE` sonrasında **tablo tipi** gerekir (yapı adı →
    `Type <X> is not a table type`). Yeni tablo tipi = yeni DDIC objesi, adı kullanıcı onaylı (`%sap-dev` §6).
  - Çağıranda `EXCEPTIONS system_failure = 1 MESSAGE <değişken>` → değişken karakter tipli (C/N/D/T), `string` değil.
  - RAP tarafı ayrıntısı: `%sap-rap`.

---

## 5. UPDATE / DELETE — enqueue kilidi

UPDATE ve DELETE'te kilit nesnesiyle `ENQUEUE`/`DEQUEUE` kullanılır; hata dalında da kilit bırakılır.
Kilit nesnesi yoksa: yeni DDIC objesidir (adı `%sap-dev` naming §4.7 `EZSD001_…`, kullanıcı onaylı; SE11'de kullanıcı
yaratır ya da ilgili skill).

```abap
METHOD {entityset}_update_entity.
  DATA(lv_id) = VALUE #( it_key_tab[ name = 'EntityId' ]-value DEFAULT '' ).

  CALL FUNCTION 'ENQUEUE_EZSD001_ORDER'          " örnek kilit nesnesi
    EXPORTING  entity_id = lv_id
    EXCEPTIONS foreign_lock = 1 system_failure = 2 OTHERS = 3.
  IF sy-subrc <> 0.
    RAISE EXCEPTION TYPE /iwbep/cx_mgw_busi_exception
      EXPORTING textid  = /iwbep/cx_mgw_busi_exception=>business_error
                message = |Record { lv_id } is locked by another user|.
  ENDIF.

  TRY.
      io_data_provider->read_entry_data( IMPORTING es_data = er_entity ).
      " BAPI çağrısı → lt_return
      zcl_sd001_bapi_helper=>check_return( lt_return ).
      zcl_sd001_bapi_helper=>commit( ).
    CATCH cx_root INTO DATA(lx).
      CALL FUNCTION 'BAPI_TRANSACTION_ROLLBACK'.
      CALL FUNCTION 'DEQUEUE_EZSD001_ORDER' EXPORTING entity_id = lv_id.
      RAISE EXCEPTION TYPE /iwbep/cx_mgw_busi_exception
        EXPORTING textid = /iwbep/cx_mgw_busi_exception=>business_error message = lx->get_text( ).
  ENDTRY.

  CALL FUNCTION 'DEQUEUE_EZSD001_ORDER' EXPORTING entity_id = lv_id.
ENDMETHOD.
```
- ENQUEUE parametre adları (`mode_<tablo>`, anahtar alanlar) kilit nesnesinden türer; üretilen FM imzasını
  `adt_search_objects` + `adt_get` ile oku, tahmin etme.
- Kilit temizliği (SM12) kullanıcı işidir; model enqueue kilidi silmez (kesin yasak C).
- Eşzamanlı güncelleme için ETag: `references/segw-service.md` §3.2.

---

## 6. Hata sınıfları ve message container

| Sınıf | Ne zaman | HTTP |
|---|---|---|
| `/iwbep/cx_mgw_busi_exception` | kullanıcının düzeltebileceği hata: doğrulama, yetki, iş kuralı | 400 |
| `/iwbep/cx_mgw_tech_exception` | teknik/beklenmeyen: DB, sistem | 500 |

Birden fazla doğrulama hatasını ilkinde kesmeden topla, hepsini tek yanıtta dön:
```abap
DATA(lo_msg) = mo_context->get_message_container( ).
IF er_entity-bukrs IS INITIAL.
  lo_msg->add_message( iv_msg_type   = /iwbep/if_message_container=>gcs_message_type-error
                       iv_msg_text   = 'Company code is required'
                       iv_msg_id     = 'ZSD001_MSG'
                       iv_msg_number = '001' ).
ENDIF.
" … diğer kontroller …
IF lo_msg->get_messages( ) IS NOT INITIAL.
  RAISE EXCEPTION TYPE /iwbep/cx_mgw_busi_exception EXPORTING message_container = lo_msg.
ENDIF.
```
```abap
" Teknik hata
TRY.
    " … okuma …
  CATCH cx_sy_open_sql_db INTO DATA(lx_db).
    RAISE EXCEPTION TYPE /iwbep/cx_mgw_tech_exception
      EXPORTING textid = /iwbep/cx_mgw_tech_exception=>technical_error message = lx_db->get_text( ).
ENDTRY.
```
- Mesaj sınıfı adı `%sap-dev` naming §4.7 (`<GÖVDE>_MSG`); mesaj metinleri `master_language`'de, kullanıcıdan.
- Hard-coded İngilizce metin yerine mesaj sınıfı tercih edilir; örneklerdeki metinler yer tutucudur.

---

## 7. Audit alanları (created/updated)
- Z tablo audit alanları taşıyorsa (`created_by/date/time`, `updated_by/date/time` ya da muadili) kullanıcı ayrıca
  istemese de doldurulur; kural her geliştirmede kullanıcıya teyit ettirilir:
  - create → `created_*` **ve** `updated_*` (hepsi)
  - sonraki update → **yalnız** `updated_*`; `created_*` hiç değişmez
  - aynı kural alt (composition/item) kayıtları için de geçerli
- Klasik DPC_EXT'te bu, create/update metodunda BAPI/FM girdisine ya da Z tablo kaydına açıkça yazılır.
  (Ekip deneyimi RAP'ta ölçüldü: idempotent `setAdmin` determination + instance guard → `%sap-rap`. DPC_EXT için
  ayrı ölçülmüş desen yok — **DOĞRULANMADI**, mevcut servisteki çalışan metottan kopyala.)
- Standart tabloda audit alanını elle yazmak kesin yasak B'dir; standart belgede bu alanları BAPI doldurur.
- UI tarafında `Edm.Time` alanlarının gösterimi UI5 skill'inin konusudur.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynak müşteri yardımcı/mesaj yapı adları, müşteri paket adları → `ZSD001` demo ve yer tutucular.
- Frontend deep-insert/`oModel.create` JavaScript örneği alınmadı (UI5 skill'i).
- Commit yasağının kaynaktaki deterministik doğrulayıcısı (`check_no_rap_commit`) aXet'te yok → §4 elle tarama notu.
