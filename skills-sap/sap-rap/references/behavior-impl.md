# Behavior implementation — behavior pool, CCIMP handler'ları, yasak deyimler, test

> Kaynak: ekip RAP playbook'u (CCIMP handler, early numbering, det/val izolasyonu, façade, SAP içi HTTP çağrısı), RAP backend
> tecrübe bankası, RAP standardı (audit, BY-association), RAP hata teşhisi kontrol listesi ve ekip hafıza dersleri; aXet'e
> uyarlandı. Deneyim `s4_private`'ta ölçüldü. Genel ABAP tuzakları (method imzasında `TYPE c LENGTH n`, sahipsiz ABAP Doc):
> `%sap-dev` → `references/coding-patterns.md`.

## 1. Behavior pool yapısı — `source/main` BOŞTUR

- Global sınıf yalnız bildirimdir; boş gövde **normaldir** (ölçüm: ~160 bayt):
  ```abap
  CLASS zcl_sd001_order DEFINITION PUBLIC ABSTRACT FINAL FOR BEHAVIOR OF zsd001_i_order.
  ENDCLASS.
  CLASS zcl_sd001_order IMPLEMENTATION.
  ENDCLASS.
  ```
- Tüm handler'lar sınıfın **CCIMP** (local implementations) include'undadır: `lhc_<alias>` sınıfları,
  `INHERITING FROM cl_abap_behavior_handler`. Birden fazla handler sınıfı normaldir.
- ⛔ **Tuzak:** yalnız `source/main`'i okuyup "sınıf boş → validasyonlar çalışmıyor" demek. Ölçülmüş yanlış alarm: main boş
  görünen bir pool'un CCIMP'i 10.472 bayt doluydu ve validasyon zinciri çalışıyordu; başka bir ölçümde main 166 bayt,
  CCIMP 21.264 bayt.
- aXet'te CCIMP okuma: `cli adt_get '{"name":"ZCL_SD001_ORDER","object_type":"ccimp"}'` (`name` = ana sınıf; include ucunu
  okur ve pull-before-edit kaydını yazar — çevrimdışı test edildi, canlı **DOĞRULANMADI**).
  Arama için `adt_grep_source` sınıf alt-include'larını tarar ve eşleşmeye `include: "implementations"` yazar:
  `cli adt_grep_source '{"pattern":"METHODS\\s+\\w+\\s+FOR","objects":"ZCL_SD001_ORDER:CLAS"}'`.
  `coverage_complete:false` + `class_includes_not_scanned` ise CCIMP okunamamıştır — "yok" deme.
- Wiring kontrolü: BDEF'teki her `determination` / `validation` / `action` / `function` ↔ CCIMP'te aynı adlı `lhc_*` metodu.
  Eşleşme varsa kablolama sağlamdır.
- CCIMP yazma (çevrimdışı test edildi, canlı **DOĞRULANMADI**): `adt_get ccimp` → `cli adt_push_source '{"name":"ZCL_SD001_ORDER","object_type":"ccimp","source":"<tam include>","transport":"<TRANSPORT>"}' --sap-write ...`
  (uzun kaynakta `--args-file`). Araç yüklemeden sonra ana sınıfı aktive eder; BDEF inaktifse aktivasyon düşer (`push_failed` +
  `activation_note`, kaynak yüklenmiştir) → `adt_activate` + `also` ile BDEF ve sınıf birlikte. Gömülü inceleme `class_push`; Yasak B
  taraması uygulanır. CCIMP ayrı aktive edilmez; sınıfla (ve BDEF'le) birlikte aktive edilir.

## 2. Handler imzaları

Alias BDEF'teki alias'tır; EML kendi BO'nda `IN LOCAL MODE` ve `%tky` ile.

```abap
CLASS lhc_Order DEFINITION INHERITING FROM cl_abap_behavior_handler.
  PRIVATE SECTION.
    METHODS get_global_authorizations FOR GLOBAL AUTHORIZATION
      IMPORTING REQUEST requested_authorizations FOR Order RESULT result.   " boş gövde = serbest
    METHODS earlynumbering_create FOR NUMBERING
      IMPORTING entities FOR CREATE Order.
    METHODS setAdmin FOR DETERMINE ON SAVE
      IMPORTING keys FOR Order~setAdmin.
    METHODS AcquireLock FOR MODIFY
      IMPORTING keys FOR ACTION Order~AcquireLock.
    METHODS GetBalance FOR READ
      IMPORTING keys FOR FUNCTION Order~GetBalance RESULT result.
ENDCLASS.
```
- Yukarıdakiler kaynakta çalışan örneklerden alındı. Validation handler imzası (`FOR VALIDATE ON SAVE IMPORTING keys FOR
  Order~checkItems`) kaynakta tam metin olarak yok → sistemdeki çalışan bir CCIMP ile kıyasla (**DOĞRULANMADI**).
- Function/action sonucu `%param-<Alan>` ile doldurulur.
- **Action sonucu boş dönüyor** (`Success:false`, alanlar boş): sonuç satırına `%cid = <key>-%cid` ekle (action korelasyonu;
  function'da gerekmez).

## 3. Early numbering (NR objesi + CHAR key) — ÇALIŞAN

- BDEF root karakteristiğinde `early numbering` (yoksa `The operation "CREATE" is not activated for entity …`).
- Handler gövdesi: tüketici numara verdiyse koru (idempotent; `mapped-order` `%cid` + key) → yoksa
  `CALL FUNCTION 'NUMBER_GET_NEXT' EXPORTING nr_range_nr = '01' object = '<NR_OBJESI>'` → `mapped-order` (`%cid` + `OrderId`).
  Hata → `failed` + `reported` (`new_message_with_text`).
- NR objesi **kullanıcının** alanıdır: AI yaratmaz, yalnız FM ile tüketir; yoksa runtime hatası → kullanıcıya bildir.
- Aktivasyon: önce BDEF'ler (create aktif olsun) → sonra BDEF'ler + sınıf birlikte. Uçtan uca kanıt: numarasız POST → 201 ve
  numara NR'dan atanmış.
- **DENENEN — BAŞARISIZ:** numarayı `determination … on save { create; }` ile vermek → `BEHAVIOR_CONTRACT_VIOLATION
  CC/C:EMPTY_UPDATE` (determination key alanını `MODIFY … UPDATE` etti; EML UPDATE en az bir key olmayan alan ister) ve
  `LCX_ABAP_BEHV_DETVAL_ERROR`. `numbering : managed` CHAR key'le uyumsuz.
- Profil: `NUMBER_GET_NEXT` klasik FM'dir; `s4_public`/`btp_abap`'ta released karşılığı canlıda doğrulanmalı (**DOĞRULANMADI**).

## 4. Determination kuralları

- Key alanı determination'da set edilmez (numara → §3).
- Kendi entity'sine `MODIFY ENTITIES … UPDATE` yapan on-save determination kendini tekrar tetikler → guard zorunlu (§5).
- `with additional save` + early numbering → create bileşeni boş gelir; create tarafı yazılmaz (kullanma).

## 5. Audit alanları otomatik doldurma — ZORUNLU standart

Tabloda `created_by/create_date/create_time/updated_by/update_date/update_time` (ya da muadili) varsa, kullanıcı ayrıca
istemese de doldurulur. Her geliştirmede alanları DDIC'ten tespit et ve kuralı kullanıcıya **teyit ettir**. Varsayılan:
create → `created_*` ve `updated_*`; sonraki update → yalnız `updated_*`; `created_*` hiç değişmez. Composition child için de.

**ÇALIŞAN YÖNTEM — idempotent `setAdmin` determination**
- BDEF root **ve** child: `determination setAdmin on save { create; update; }`.
- Handler (her entity için ayrı `lhc_`): `READ ENTITIES … IN LOCAL MODE … FIELDS ( CreatedBy ) WITH …` → `CreatedBy` boşsa
  yeni kayıt (6 alan), doluysa update (3 alan) → `MODIFY ENTITIES … IN LOCAL MODE … UPDATE FROM lt_upd` (`%control` ile).
- **İdempotent guard:** sınıf örneği seviyesinde `DATA mt_done` (LUW boyunca yaşar); işlenmiş anahtar ikinci geçişte `CONTINUE`
  → MODIFY yok → döngü kırılır.

**DENENEN — BAŞARISIZ**
- Guard'sız tek `setAdmin` (`IN LOCAL MODE` olsa bile) → `RAISE_SHORTDUMP LCX_ABAP_BEHV_DETVAL_ERROR` "Infinite loop caused by
  cyclical triggering of on-save determinations".
- Ayrı `setCreateAdmin { create; }` + `setUpdateAdmin { update; }` → update tek başına tetikleyici olamaz.
- `with additional save` saver → dump yok ama early numbering'de create bileşeni boş; create admin alanları yazılmaz.

Yazma kapısının BDEF incelemesi audit alanlı tabloda bu determination yoksa uyarı verebilir. `TIMS` alanı OData'da `Edm.Time`
olur; ön yüz gösterimi UI tarafının işidir.

## 6. Determination/validation izolasyon disiplini

`RAISE_SHORTDUMP` / `LCX_ABAP_BEHV_DETVAL_ERROR` jeneriktir (hangi handler patladı söylemez). **Strateji:** BDEF'i saf CRUD'a
indir → aktive et → uçtan uca yeşil → determination/validation'ları **tek tek**, her biri ayrı aktivasyon + test ile geri ekle.
Çalışan CRUD ≠ çalışan det/val. Ölçülmüş izolasyonda okuma + `failed`/`reported` yapan üç validation temiz çıktı; dump'ın tek
sebebi guard'sız self-MODIFY determination'dı (§5).

## 7. Validation kuralları

- Hata: `APPEND VALUE #( %tky = … ) TO failed-<entity>` + `APPEND VALUE #( %tky = … %msg = new_message_with_text( severity =
  if_abap_behv_message=>severity-error text = … ) ) TO reported-<entity>`.
- Mesaj OData'ya **50 karakterde kesilir**; belge numarasını öneğin hemen ardına koy (`delete-guard.md` §6).
- **Delete validation'da `READ ENTITIES` kullanma:** validation koştuğunda örnek tamponda artık silinmiştir → READ boş döner →
  `IF lt IS INITIAL. RETURN.` ya da boş `LOOP` → kontrol **hiç koşmaz**, hata/uyarı yok, statik kontroller görmez. Doğrusu:
  doğrudan `keys` üzerinde çalış (yalnız entity key alanları gelir; başka alan gerekiyorsa veritabanından oku). Ölçülen
  vakada 10 delete validation'ın 9'u bu hatayı taşıyordu → sistemdeki doğru örneği bul, ona hizala.
- Validasyonun gerçekten reddettiğinin kanıtı: geçersiz girişle POST → 400 + beklenen mesaj; geçerli girişle → 201.

## 8. `READ ENTITIES … BY \_assoc` — yalnız KEY döner (HIGH)

- `READ ENTITIES OF zsd001_i_order IN LOCAL MODE ENTITY Order BY \_Item FROM <keys> RESULT lt` child'ın **yalnız key
  alanlarını** doldurur; tarih, durum, tip, tutar gibi alanlar INITIAL kalır → validation/determination **sessizce yanlış**
  çalışır. Sözdizimi temizdir, ATC temizdir, aktive olur; yalnız runtime'da çıkar.
- **ÇALIŞAN:**
  ```abap
  READ ENTITIES OF zsd001_i_order IN LOCAL MODE
    ENTITY Order BY \_Item
      ALL FIELDS WITH CORRESPONDING #( keys )
    RESULT DATA(lt_item).
  " seçili alanlar: FIELDS ( ItemStatus DeliveryDate ) WITH CORRESPONDING #( keys )
  ```
  `FIELDS ( … )` ile `FROM` değil `WITH` yazılır. Yalnız varlık/key kontrolü için `FROM` yeterlidir.
- Ölçülen vakalar: dolu veride her kayıtta "plan tarihi zorunlu" yanlış hatası; strateji seçen alan boş geldiği için bir
  bakiye/kalem validasyonları **hiç koşmuyordu**; üçüncü yerde okunan alan key olduğu için şans eseri çalışıyordu.
- **DENENEN — BAŞARISIZ:** `FIELDS ( … ) FROM …` sözdizimi hatası verince (`WITH expected after )`) `FIELDS`'i silmek → keys-only'ye
  düşürür. Doğru düzeltme `FROM` → `WITH`.
- Mevcut kodu tararken: `BY \_` geçen okumaların sonucunda key olmayan alan tüketiliyor mu bak.
- Kaynakta ayrıca şu biçim çalışan örnek diye geçer: `… BY \_<Assoc> FROM VALUE #( ( <DüzKeyAdı> = … ) ) RESULT lt.` — düz key
  adı (`%tky-` değil); bu biçim de yalnız key döndürür.

## 9. abaplint `parser_error` gerçek olabilir

Yazma kapısındaki abaplint CCIMP'i BDEF bağlamı olmadan tek include olarak ayrıştırır. "Unexpected CLASSDEFINITION" gibi
çoklu-sınıf bulguları yanlış pozitiftir; ama `READ`/`MODIFY` satırındaki `parser_error` / "Statement does not exist" **gerçek
sözdizimi hatası** olabilir (ölçülen vakada BY-association READ yanlıştı, aktivasyon `type="E"` ile düştü). Çalışan bir
CCIMP'teki aynı deyimle kıyasla; kapatma kanıtı aktivasyondur.

## 10. Handler'da yasak deyimler

| Deyim | Sonuç | Doğrusu |
|---|---|---|
| `COMMIT ENTITIES` handler içinde | `500 BEHAVIOR_ILLEGAL_STATEMENT` | Released BO'ya MODIFY yap, commit etme; OData isteğinin sonunda framework commit eder (sipariş gerçekten yazıldı, doğrulandı). |
| `COMMIT WORK` / `ROLLBACK WORK` / `BAPI_TRANSACTION_COMMIT` / `_ROLLBACK` — handler'da **ve handler'ın çağırdığı yardımcı sınıfta** | runtime `BEHAVIOR_ILLEGAL_STATEMENT` dump, bağlantı reset, ön yüzde yalnız "HTTP request failed". Sözdizimi/ATC/abaplint/bağımsız inceleme **geçer**; ilk gerçek create/action testinde çıkar (ölçüldü: üç inceleme turu kaçırdı). | Aşağıdaki ayrı LUW deseni. Yeni kodda `COMMIT` ara (`adt_grep_source`, `pattern: "COMMIT\\s+WORK|BAPI_TRANSACTION_"`). |
| `MESSAGE` | `BEHAVIOR_ILLEGAL_STATEMENT … Statement MESSAGE_E is not allowed`. `cl_http_client` iletişim hatasında içeride MESSAGE verir → dump. | Mesaj `reported` ile; HTTP için §11. |

**Commit gerektiren klasik BAPI'yi RAP'ten çağırmak (ayrı LUW) — ÇALIŞAN (`s4_private`):**
- BAPI + `BAPI_TRANSACTION_COMMIT/ROLLBACK`'i bir **Z RFC-enabled FM**'e sar; çağıran `CALL FUNCTION 'Z…_FM_…' DESTINATION 'NONE'`.
  `'NONE'` ayrı roll area/LUW açar, `COMMIT WORK` orada geçerlidir. Sınıfta commit yok; commit yalnız FM'de. Mesajlar FM'in
  `EXPORTING`/`TABLES` parametrelerinden (tüm BAPIRET2 satırları) döner.
- Tuzaklar: (a) FM **Remote-Enabled** olmalı — ADT'den ayarlanamadı (400), kullanıcı SE37'de işaretler; yoksa
  `CALL_FUNCTION_NOT_REMOTE`. (b) `TABLES` parametresi: ADT push `STRUCTURE`'ı reddeder (`FUNC_ADT 015 … declares no type`),
  ABAP ise `TYPE` sonrası **tablo tipi** ister (`Type <X> is not a table type`) → satır tipi o yapı olan DDIC tablo tipi (ad ve
  metin kullanıcıdan). (c) `EXCEPTIONS system_failure = 1 MESSAGE <var>` → `<var>` karakter benzeri (C/N/D/T), `string` değil.
- FM push protokol notları: `%sap-adt-foundation` → `foundation-ops.md` §4.4.
- `s4_public`/`btp_abap`'ta klasik FM yok → bu desen uygulanmaz; alternatif **DOĞRULANMADI**.

## 11. Handler'dan SAP içi OData/HTTP servis çağrısı

Kural 0: **kullanıcı adı/şifre kaynak koda yazılmaz** (eski SEGW kodundaki `authenticate( username = … password = … )` kopyalanmaz;
yazma kapısı reddeder).

**Tercih edilen — SAP Gateway iç loopback** (`s4_private`'ta ölçüldü; harici HTTP, RFC destination ve kimlik yok):
```abap
" host:port çalışma zamanında (TH_GET_VIRT_HOST_DATA), client = sy-mandt; proje ortak yardımcı sınıfı varsa onu kullan
/iwfnd/cl_sutil_client_proxy=>get_instance( )->web_request(
  EXPORTING it_request_header = VALUE #(
              ( name = if_http_header_fields_sap=>request_method value = 'POST' )
              ( name = if_http_header_fields_sap=>request_uri    value = lv_uri )
              ( name = if_http_header_fields=>content_type        value = 'application/json' )
              ( name = if_http_header_fields=>accept              value = 'application/json' )
              ( name = 'x-csrf-token'                             value = lv_csrf ) )
            iv_request_body = cl_abap_codepage=>convert_to( lv_payload_json )
  IMPORTING ev_status_code = DATA(lv_status) et_response_header = DATA(lt_hdr)
            ev_response_body = DATA(lv_body_x)
  EXCEPTIONS OTHERS = 4 ).
```
- CSRF: önce aynı yoldan GET ile token (proxy tek oturumdur; sonraki POST/PATCH token'ı paylaşır). PATCH'te `if-match: *`.
- **Dil:** URL'e yalnız `sap-client` konursa servis EN çalışır (`Unit … is not created in language EN`) → `&sap-language=<master_language>` ekle.
- **Sorgulu URL** (`?$filter`): yola `?sap-client` eklenince çift `?` olur → host:port'u ayıkla, `path + ( ? ya da & ) + sap-client=`
  diye kur.
- Ortak bir host/token yardımcı sınıfı varsa (başka ekibin) **değiştirme**, yalnız kullan; POST/PATCH'i kendi paketinde yaz.
- RAP handler içinde bu proxy sorunsuz çalıştı; `cl_http_client` iletişim hatasında MESSAGE dump'ı veriyordu.
- Teknik servis (`API_…_SRV`) ile Z takma adı ayrı objelerdir; hangisi yetkili: `$metadata` 200 mü 403/404 mü.

**Eski yol — SM59 destination** (yeni kodda kullanma; destination'ı kullanıcı/Basis yaratır):
`cl_http_client=>create_by_destination( destination = CONV rfcdest( '<DEST>' ) … )`. Ölçülmüş kurulum tuzakları:
SSL kapalı → `Client connection to http://host:443xx broken` (SSL Active); kimlik gönderilmiyor → 401 (logon config'te saklı
kullanıcı); **Path Prefix dolu** → prefix her zaman başa eklenir, `403 /IWFND/MED/170 service 'sap' not found` (prefix boş,
kod tam yolu verir); yazmadan önce `X-CSRF-Token: Fetch` GET (POST-only entity'de GET 404 döner ama token yine gelir).

**Teşhis:** bağlantıyı handler'a gömmeden önce `IF_OO_ADT_CLASSRUN` sınıfıyla dene (RAP bağlamı dışında koşar, MESSAGE dump
etmez, gerçek status görünür). "Eski çıktı / does not implement" → sınıf aktive değil ya da bayat oturum; **yeni adla sınıf
yaratma** (denendi, çözmedi). Deneme sınıflarını iş bitince onayla sil. `%sap-adt-foundation` → `known-errors-adt.md` K-13.

## 12. Unit test — BOTD test double

Test ortamı `CL_BOTD_TXBUFDBL_BO_TEST_ENV` (transaction buffer double, veritabanına dokunmaz):
```abap
CLASS ltc_order DEFINITION FINAL FOR TESTING DURATION SHORT RISK LEVEL HARMLESS.
  PRIVATE SECTION.
    CLASS-DATA env TYPE REF TO if_botd_txbufdbl_bo_test_env.
    CLASS-METHODS class_setup.     " env = cl_botd_txbufdbl_bo_test_env=>create( VALUE #( ( 'ZSD001_I_ORDER' ) ) )
    CLASS-METHODS class_teardown.  " env->destroy( )
    METHODS setup.                 " env->clear_doubles( )
    METHODS create_ok FOR TESTING.
    METHODS validate_qty FOR TESTING.
ENDCLASS.
```
Senaryolar: CRUD (`MODIFY` + `COMMIT ENTITIES` test ortamında → FAILED/REPORTED boş), validation (geçersiz → beklenen mesaj),
determination (türetilen alan), action (beklenen durum), create-by-association (deep create). Koşum: `adt_unit_run`
(varsayılan yalnız `harmless`). Test include'u (CCAU): `adt_get ccau` → `adt_push_source ccau` (`name` = ana sınıf; include yoksa
araç önce iskeleti yaratır sonra yazar, bayt readback — çevrimdışı test edildi, canlı **DOĞRULANMADI**). `method_count:0` = FAIL
(`%sap-classic-abap` → `classes.md` §5).

## 13. ATC disiplini

`adt_atc_check` (proje ATC varyantı). Öncelik 1 bulgular zorunlu düzeltilir. Pseudo-comment/pragma ile susturma yasak.
Öncelik 2/3 ancak kullanıcının açık onayıyla geçilir; sessiz geçiş yok. Bulguları kategoriye göre grupla.
