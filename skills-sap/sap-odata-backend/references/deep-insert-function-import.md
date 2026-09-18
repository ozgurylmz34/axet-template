# Deep insert, function import, Gateway FI içinden EML

> Kaynak: ekip backend kodlama standardı (CREATE_DEEP_ENTITY), OData servisleri playbook'u (function import 405,
> FI parametreleri, UpdateSalesOrder EML dersleri), RAP playbook'u (V2 FI parametre tırnağı, late numbering),
> UI5-OData playbook'u (SEGW→RAP göç tuzakları — yalnız backend tarafı).
> Ölçülmüş dersler tek bir müşteri sistemi ve standart satış siparişi BO'su üzerinde yaşandı; başka BO'ya genelleme
> yaparken sınırı unutma.

---

## 1. Deep insert — `CREATE_DEEP_ENTITY` (başlık + kalem tek POST)

```abap
METHOD /iwbep/if_mgw_appl_srv_runtime~create_deep_entity.
  CASE iv_entity_set_name.
    WHEN 'SalesOrderSet'.
      " 1. Başlık + navigation (kalemler) — MPC'deki deep yapı
      DATA ls_order TYPE zcl_{app}_mpc_ext=>ts_deep_order.   " ToItems tablosunu içeren yerel tip
      io_data_provider->read_entry_data( IMPORTING es_data = ls_order ).

      " 2. BAPI yapılarına eşle (ls_order → başlık, ls_order-toitems → kalemler)
      " 3. BAPI çağır → lt_return (BAPIRET2)
      " 4. zcl_…_bapi_helper=>check_return( lt_return ). zcl_…_bapi_helper=>commit( ).

      " 5. Yaratılan anahtarlarla deep entity'yi dön
      copy_data_to_ref( EXPORTING is_data = ls_order CHANGING cr_data = er_deep_entity ).

    WHEN OTHERS.
      super->/iwbep/if_mgw_appl_srv_runtime~create_deep_entity(
        EXPORTING iv_entity_name     = iv_entity_name
                  iv_entity_set_name = iv_entity_set_name
                  iv_source_name     = iv_source_name
                  io_data_provider   = io_data_provider
                  it_key_tab         = it_key_tab
                  it_navigation_path = it_navigation_path
        IMPORTING er_deep_entity     = er_deep_entity ).
  ENDCASE.
ENDMETHOD.
```
- `WHEN OTHERS` dalında super çağrısı zorunlu: aksi hâlde servisin diğer entity set'lerinde deep insert sessizce ölür.
- Navigation property adı (`ToItems`) SEGW association'ıyla **birebir**; istemci payload'unda da aynı ad kullanılır.
- **Deep yapı tipi:** kaynak standarttaki örnek MPC'nin düz `ts_<entity>` tipinden `to_items` bileşenini data ref
  olarak okuyordu. Deep insert için başlık + kalem tablosunu içeren **yerel bir tip** (MPC_EXT'te ya da DPC_EXT'te)
  tanımlamak gerekir; bu tipin kesin biçimi kaynakta ölçülmedi → **DOĞRULANMADI**, mevcut çalışan bir deep insert'ten
  ya da `/IWBEP/IF_MGW_APPL_SRV_RUNTIME` imzasından (`adt_get`) doğrula.
- Standart belgeye yazma BAPI iledir (kesin yasak B). BAPI adını ve imzasını sistemde doğrula.
- Test: deep POST veri yazar → model çalıştırmaz (`SKILL.md` §6.3).

---

## 2. Function import POST → 405 (koleksiyon döndüren, entity set'e bağlı FI)

- **Belirti:** koleksiyon döndüren ve bir entity set'e bağlı function import'a POST → **405**; istek ABAP'a hiç ulaşmaz.
- **Kök sebep:** Gateway çalışma zamanı dispatcher'ı (`/IWCOR/CL_DS_PROC_DISPATCHER`) bu tür FI POST isteğini
  `execute_action`'a değil, bağlı entity set'in `_get_entityset` metoduna yönlendirir.
- **DENENEN — BAŞARISIZ:** `/IWFND/MAINT_SERVICE`'te servisi silip yeniden ekleme · `/IWBEP/R_MGW_CLEANUP_MD_CACHE` ·
  SEGW'de HTTP method değiştirme.
- **ÇALIŞAN YÖNTEM (ölçülmüş vaka):** istemci FI yerine **sonuç entity set'ini GET ile okur**, parametreleri URL
  parametresi olarak verir; backend'de o entity set'in `<entityset>_get_entityset` metodu override edilir.
  - Parametreler `server_request` üzerinden istek URI'sinden (`~request_uri` header alanı) regex ile ayrıştırıldı.
  - JSON taşıyan parametre URL-encoded gelir → `cl_http_utility=>unescape_url( )` ile çözülür.
  - Parametreleri URI'den regex'le ayrıştırmak kırılgandır; `io_tech_request_context` filtre/parametre API'sinin bu
    senaryoda işe yarayıp yaramadığı **DOĞRULANMADI** — önce onu dene, olmazsa bu yolu kullan.
- **Sınır:** yalnız "koleksiyon döndüren + entity set'e bağlı FI + POST" birleşimi ölçüldü. Tek sonuç döndüren FI,
  entity set'siz FI ya da GET FI için bu davranış iddia edilmez.
- Uzun vadede aynı ihtiyaç RAP'ta static function (okuma → GET) / static action (yazma → POST) ile karşılanır (`%sap-rap`).

---

## 3. Function import parametreleri

- **Tüm parametreler gönderilir.** Opsiyonel görünse de atlanan parametre → `Invalid Function Import Parameter '<P>'`.
  Boş olabilecek string parametre boş dizge (`''`) olarak gönderilir.
- Parametre adları **büyük/küçük harfe duyarlıdır** ve `$metadata`'daki `FunctionImport` bloğundan birebir alınır
  (ölçülen serviste `Iv` önekli PascalCase: `IvSoldToParty`).
- V2 URL'de string parametre **tek tırnaklı**: `GetBalance?IvCustomer='0000012345'&IvCompanyCode=''`.
  Tırnaksız → `400 Invalid function import parameter type … Expected Edm.String` (RAP V2 servisinde ölçüldü; SEGW
  servisinde ayrıca ölçülmedi — **DOĞRULANMADI**, ilk kullanımda dene).
- SEGW, metadata'da olmayan fazla parametreye gevşektir; RAP V2 reddeder (`400 Invalid parameter`). SEGW→RAP göçünde
  fazla parametreler temizlenir.
- Parametre imzası değişince: SEGW Generate → `$metadata` kontrolü (FI bloğu) → çağıran UI'ya haber.

### 3.1 URL uzunluğu
- Değişen kalemleri JSON olarak GET parametresine koymak uzun URL üretti → ICM bağlantıyı kopardı (connection drop).
- **ÇALIŞAN YÖNTEM:** JSON anahtarları kısaltıldı (`I`=kalem, `Q`=miktar, `M`=malzeme, `U`=birim), backend
  JSON ayrıştırıcısı `pretty_mode-low_case` ile okudu (kaynakta sınıf adı yazmıyor; hangi ayrıştırıcı olduğu
  **DOĞRULANMADI** — paketteki çalışan koddan oku).
- Kalıcı çözüm adayı (ölçülmedi): yazma işlemini GET FI yerine POST'a (deep insert ya da action) taşımak.

---

## 4. Gateway function import içinden EML (released BO'ya yazma)

Klasik FI handler'ından released BO'ya `MODIFY ENTITIES` ile yazan kodda ölçülmüş kurallar (standart satış
siparişi BO'su, yeni kalem ekleme senaryosu; belirti: 504 / 0,9 sn'de bağlantı kopması):

| # | Kural | Neden (ölçüldü) |
|---|---|---|
| 1 | **`COMMIT ENTITIES` yapma** | Gateway FI bağlamında EML değişikliği Gateway'in kendi `COMMIT WORK`'üyle kaydedilir; ayrıca `COMMIT ENTITIES` çakışır → `CX_ABAP_BEHV_COMMIT_FAILED` dump |
| 2 | **Tek `MODIFY ENTITIES` bloğu** — UPDATE ve `CREATE BY \_item` aynı blokta | Aynı LUW'da ayrı ayrı `MODIFY ENTITIES` deyimleri commit'te `CX_ABAP_BEHV_COMMIT_FAILED` verdi. Yeni kalem varsa/yoksa diye iki tam blok: `IF lt_new IS NOT INITIAL … ELSE … ENDIF` |
| 3 | **Tüm `DATA` tanımları metodun başında** | `IF/ELSE` içinde iki kez `DATA(ls_mapped)` → `already declared`; EML'de `MAPPED ls_mapped` (satır-içi `DATA()` olmadan) |
| 4 | **`FOR … INDEX INTO DATA(…)` kullanma** | EML `WITH VALUE #( … )` içinde desteklenmedi; `sy-tabix` de güvenilmez → tabloyu önce `LOOP` ile hazırla, sonra EML'e ver |
| 5 | **`%cid` benzersiz** | Aynı `%cid` iki kez → `CX_RAP_AMBIGUOUS_CID` dump |
| 6 | Birim ve iş alanı değerleri spesifikasyondan | Kalem tesis/birim değeri sabit yazıldığında doğrulama hatası verdi; değer belgenin mevcut kaleminden ya da spesifikasyondan alınır |

```abap
DATA lv_ctr  TYPE i VALUE 0.
DATA ls_item LIKE LINE OF lt_new_items.
LOOP AT lt_new_items INTO ls_item.
  lv_ctr += 10.
  ls_item-cid = |ITM{ lv_ctr }|.          " ITM10, ITM20 …
  MODIFY lt_new_items FROM ls_item.
ENDLOOP.
```
- ⚠ Kaynaktaki özet iskelette `%cid = ls_ni-material` yazıyordu; aynı malzeme iki kalemde olursa kural 5'i çiğner.
  Sayaç deseni kullanılır.
- Released BO'ya EML yazmadan **önce** operasyonun o BO için sistemde açık olduğu canlı doğrulanır; kapalıysa
  (`The operation "UPDATE/CREATE" is not activated for entity …`) EML değil standart OData API'si (MERGE/PATCH,
  `references/outbound-api-call.md`) ya da released değişiklik BAPI'si. Bu hata aktivasyona kadar görünmez.
- **Late numbering:** belge numarasını SAVE anında atan BO'da (ölçülen: satış siparişi) handler `mapped` içinde
  numarayı boş alır → yanıtta numara senkron dönmez, belge yine de yaratılır. Klasik DPC normal ABAP bağlamında
  commit + okuma yapabildiği için numarayı dönebiliyordu; RAP handler'da çözüm istemcinin referansla yeniden okumasıdır.
- RAP behavior ayrıntısı (handler, `%param`, result satırı): `%sap-rap`.

---

## 5. SEGW → RAP göçünde backend tarafı notları
Çalışan bir UI'yı SEGW servisinden RAP V2 servisine bağlarken ölçülen farklar:

| Konu | SEGW | RAP V2 |
|---|---|---|
| FI'ın entity set'i | olabilir (UI `read("/XxxResultSet")`) | FI'dır → `Resource not found for segment 'XxxResultSet'` |
| Metadata'da olmayan parametre | tolere edilir | `400 Invalid parameter` |
| `[1]` sonuç | düz nesne | fonksiyon adı altında sarmalanır |
| Sonuç alan adları | MPC property adı | abstract entity alan adları **MPC property adlarıyla birebir** tutulursa UI ayrıştırması bozulmaz |

UI tarafındaki uyarlama UI5 skill'inin konusudur.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Müşteri servis adı, sipariş numaraları, tesis/birim/org değerleri, frontend birim eşleme tablosu → çıkarıldı ya da nötrlendi.
- UpdateSalesOrder frontend JSON örneği (JavaScript) alınmadı (UI5 skill'i).
