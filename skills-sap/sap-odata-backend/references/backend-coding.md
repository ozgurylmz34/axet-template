# Backend kodlama — performans, güvenlik, RFC FM, test, CDS katmanı

> Kaynak: ekip backend kodlama standardı (performans kuralları, güvenlik kontrol listesi, RFC FM şablonu, ABAP Unit
> deseni, CDS VDM katmanları ve DCL, draft kararı). Genel ABAP desenleri (`FOR ALL ENTRIES` boş kontrol, `GROUP BY`,
> range, kur, clean core tablosu) `%sap-dev` → `references/coding-patterns.md`'dedir; burada tekrarlanmaz.

---

## 1. Performans — her OData okumasında

Her `SELECT`'i ve CDS'i 500 bin+ satıra karşı düşünerek yaz.

| # | Kural | Kötü → İyi |
|---|---|---|
| 1 | `SELECT *` yok | alan listesini yaz |
| 2 | Tüm filtreler `WHERE`'de | tabloyu çekip `FILTER #( … )` ile süzme → filtreyi `WHERE`'e |
| 3 | Döngü içinde `SELECT` yok | `FOR ALL ENTRIES` (boş kontrolüyle — `%sap-dev` coding-patterns §3) ya da join |
| 4 | Arama tablosu `HASHED` | `TYPE HASHED TABLE OF … WITH UNIQUE KEY …` |
| 5 | Aralık taraması `SORTED` | `TYPE SORTED TABLE OF … WITH NON-UNIQUE KEY …` |
| 6 | Toplama DB'de | `SUM( … )`, `COUNT(*)`, `GROUP BY` |
| 7 | Her `GET_ENTITYSET`'te sunucu tarafı paging | `$top/$skip` + `$inlinecount` (`references/dpc-crud.md` §2) |

- CDS: view zincirini 3 seviyeden derine taşıma; karmaşık join için AMDP. CDS'te korelasyonlu alt sorgu yerine
  association.
- CDS performans annotation'ları (`@ObjectModel.resultSet.sizeCategory: #XL`, `@Analytics.dataCategory: #CUBE`) kullanım
  amacına göre; analitik annotation'ı salt performans için ekleme.
- Standart tabloyu okumak yasak değildir; released CDS varsa onu tercih et (`%sap-dev` coding-patterns §7).

## 2. Güvenlik kontrol listesi
- [ ] RFC FM'de ve DPC_EXT'te her yazma işleminden önce `AUTHORITY-CHECK`.
- [ ] OData'ya açılan CDS'lerde `@AccessControl.authorizationCheck: #CHECK` + DCL (§4.2).
- [ ] `SELECT *` yok, alan listesi var.
- [ ] Kodda sabit istemci (`MANDT`), sistem, host ya da kimlik bilgisi yok (`references/outbound-api-call.md` §5).
- [ ] Dinamik `WHERE` kurulmadan önce girdi doğrulanır.
- [ ] `COMMIT`'ten önce BAPI dönüşünde `E` / `A` kontrolü (`references/dpc-crud.md` §3-4).
- [ ] CSRF: UI5 V2 modeli token'ı kendi yönetir; backend'de CSRF kapatılmaz.

## 3. RFC FM şablonu (DPC'den çağrılan)
```abap
FUNCTION zsd001_fm_order_create
  IMPORTING
    VALUE(is_input)  TYPE zsd001_s_order_input
  EXPORTING
    VALUE(es_output) TYPE zsd001_s_order_output
  TABLES
    et_return TYPE bapiret2_t.   " tablo TİPİ; yapı adı değil (RFC'de 'is not a table type')

  " 1. Girdi doğrulama
  IF is_input-bukrs IS INITIAL.
    APPEND VALUE #( type = 'E' id = 'ZSD001_MSG' number = '001' ) TO et_return.
    RETURN.
  ENDIF.

  " 2. Yetki
  AUTHORITY-CHECK OBJECT 'Z{AUTH_OBJ}' ID 'ACTVT' FIELD '01' ID 'BUKRS' FIELD is_input-bukrs.
  IF sy-subrc <> 0.
    APPEND VALUE #( type = 'E' id = 'ZSD001_MSG' number = '002' ) TO et_return.
    RETURN.
  ENDIF.

  " 3. İş mantığı (BAPI çağrısı vb.)
  TRY.
      " …
      APPEND VALUE #( type = 'S' id = 'ZSD001_MSG' number = '000' ) TO et_return.
    CATCH cx_root INTO DATA(lx_error).
      APPEND VALUE #( type = 'E' id = 'ZSD001_MSG' number = '999' message = lx_error->get_text( ) ) TO et_return.
  ENDTRY.

  " DPC'den çağrılıyorsa burada COMMIT WORK yok — commit DPC_EXT'te dönüş doğrulandıktan sonra
ENDFUNCTION.
```
- İmza **satır-içi ABAP deyimleriyle** yazılır; kaynak standarttaki `*"` yorum bloğu imza ADT push'unda reddedilir
  (`400 Parameter comment blocks are not allowed`) → `%sap-adt-foundation` → `references/known-errors-adt.md` K-15.
- `TABLES` parametresinde `STRUCTURE` ADT push'unda reddedilir; `TYPE <tablo tipi>` kullan (K-15). Örnekteki
  `bapiret2_t`'nin tablo tipi olduğu bilinir; kendi yapın için tablo tipi yoksa yeni DDIC (ad: öneri + canlı kontrol + kullanıcı onayı, `%sap-dev` §6).
- FM ve fonksiyon grubu adları `%sap-dev` naming §4.4; FM push ayrıntısı `%sap-classic-abap`.
- RAP'ten ayrı LUW ile çağrılacak FM'in Remote-Enabled işareti: `references/dpc-crud.md` §4.

## 4. CDS — OData'ya açılan katman

### 4.1 Katmanlar
| Katman | Rol | Not |
|---|---|---|
| Interface / basic (`%sap-dev` naming §4.3 `_I_`) | ham tablo eşlemesi, UI annotation yok, `@VDM.viewType: #BASIC` | OData'ya doğrudan açılmaz |
| Consumption (`_C_`) | join, hesaplanan alan, value help association, `@VDM.viewType: #CONSUMPTION` | OData'ya açılan katman |
| Value help | F4 listeleri | ortak value help varsa yeniden kullan (`%sap-dev` naming §5) |

- Kaynak standartta eski öneklerle (`ZI_`, `ZC_`, `ZVH_`) ve `@AbapCatalog.sqlViewName`'li klasik `define view`
  örneği vardı; ad deseni bugün `%sap-dev` naming'dir. Klasik `define view` mı `define view entity` mi kararı ve CDS
  yazım ayrıntısı bu skill'in kapsamı dışındadır (CDS/RAP skill'i → `%sap-rap`).
- Durum renklendirmesi için hesaplanan `criticality` alanı (0 nötr · 1 kırmızı · 2 turuncu · 3 yeşil) consumption
  katmanında `case` ile üretilir.
- Tutar alanı `@Semantics.amount.currencyCode`, miktar alanı birim referansı taşır. (CLI'nin gömülü inceleme
  zincirinde CDS görevleri için currency/quantity referans kontrolü BLOCKER olarak tanımlı; push sırasında hangi
  görevin koşturulduğu **DOĞRULANMADI**.)

### 4.2 DCL
```abap
@MappingRole: true
define role ZSD001_I_ORDER {
  grant select on ZSD001_I_ORDER
    where ( CompanyCode ) = aspect pfcg_auth( Z{AUTH_OBJ}, BUKRS, ACTVT = '03' );
}
```
Yetki nesnesi ve alanları kullanıcıdan/spesifikasyondan. Standart CDS'ten doğrudan okuyan kodda DCL reddinin
**sessiz 0 satır** üretebileceğini unutma (hata atmaz).

### 4.3 Draft
- OData V2 + SEGW'de iki seçenek: BOPF tabanlı standart draft (`@ObjectModel.draft.enabled`) ya da Z tabloda elle
  draft yönetimi (`DRAFT_UUID`, `IS_DRAFT` …).
- Draft gerekip gerekmediği geliştirme **başında** kullanıcıyla kararlaştırılır; gerekmedikçe eklenmez.
- `s4_private`'ta yeni draft'lı işlem uygulaması için RAP draft'ı değerlendirilir (`%sap-rap`); BOPF yeni işte
  önerilmez — kaynak standardın "BOPF tercih edilir" ifadesi bu ekip standardının RAP'ı tercih eden sonraki kararıyla
  **çelişiyor**; karar kullanıcının.

## 5. ABAP Unit — kritik yol testleri
Her RFC FM ve DPC_EXT metodu için en az kritik yol testleri:

| # | Senaryo |
|---|---|
| 1 | Mutlu yol |
| 2 | Doğrulama — eksik/hatalı girdi |
| 3 | Yetki — yetkisiz kullanıcı |
| 4 | Uç durum — boş tablo, en büyük veri |
| 5 | Eşzamanlılık — kilit |

```abap
CLASS ltcl_order_create DEFINITION FINAL FOR TESTING DURATION SHORT RISK LEVEL HARMLESS.
  PRIVATE SECTION.
    DATA mt_return TYPE bapiret2_t.
    METHODS setup.
    METHODS create_missing_bukrs FOR TESTING.
ENDCLASS.

CLASS ltcl_order_create IMPLEMENTATION.
  METHOD setup.
    CLEAR mt_return.
  ENDMETHOD.
  METHOD create_missing_bukrs.
    DATA ls_input TYPE zsd001_s_order_input.       " bukrs bilerek boş
    CALL FUNCTION 'ZSD001_FM_ORDER_CREATE'
      EXPORTING is_input  = ls_input
      TABLES    et_return = mt_return.
    cl_abap_unit_assert=>assert_true(
      act = xsdbool( line_exists( mt_return[ type = 'E' ] ) )
      msg = 'Missing company code should return an error' ).
  ENDMETHOD.
ENDCLASS.
```
- Veri yazan mutlu yol testi `RISK LEVEL HARMLESS` değildir; DB'yi taklit etmek için `CL_OSQL_TEST_ENVIRONMENT`
  (kaynakta anılıyor, bu ekipte ölçülmüş kullanımı yok — **DOĞRULANMADI**).
- Çalıştırma: `adt_unit_run` (varsayılan yalnız `harmless`; `allow_risky_tests=true` yazma sınıfı + onay) →
  `%sap-adt-foundation` → `references/foundation-query.md` §4.
- Kaynak şablondaki `assert_not_initial( act = VALUE #( mt_return[ type = 'E' ] OPTIONAL ) )` biçimi de çalışır
  olabilir; örnekteki `line_exists` biçimi tercih edildi, ikisi de aktivasyonla doğrulanmalı.

## 6. Yapım sırası (klasik track)
1. Gereksinim onayı + mimari karar (seçilen yol, alternatifler) — tek mesajda.
2. CDS (varsa) → RFC FM / BAPI sarmalayıcı (varsa) → SEGW modeli (kullanıcı) → DPC_EXT / MPC_EXT.
3. Yapılandırma: servis kaydı (`references/segw-service.md` §4), yetki rolü (kullanıcı/Basis).
4. Uç durumlar ve riskler: hacim, kilit, yetki boşlukları.
5. Test yaklaşımı: §5 senaryoları.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Fiori Launchpad (katalog, tile, target mapping, semantic object, çapraz uygulama navigasyonu) ve PFCG rol adımları
  alınmadı: UI/launchpad yapılandırması (UI5 skill'i).
- "Golden rule" ve rol metni alınmadı. Kaynaktaki FM imzası yorum bloğu biçiminden satır-içi imzaya çevrildi.
