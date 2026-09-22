# Feature control — duruma bağlı düzenlenebilirlik (dynamic instance feature control) ve yetkiden ayrımı

> **Durum:** sözdizimi SAP'nin resmi kaynaklarından alındı (aşağıda "Kaynaklar"). **EML tüketici kolu canlı ÖLÇÜLDÜ
> (2026-09-22, S/4HANA private DEV, `$TMP`) — sonuç ve sınırı §7a.** OData/UI kolu, `IN LOCAL MODE` istisnası, alan düzeyi
> ve başlık→kalem etkisi ölçülmedi: ilk gerçek kullanımda §7'nin kalan adımlarını koş ve `%remember` ile kaydet.
> Eş anlamlılar (arama için): feature control · instance feature control · dinamik özellik kontrolü · salt okunur ·
> read-only · düzenlenemez · onaylanınca değiştirilemez · buton pasif · `features : instance` · `get_instance_features`.

## 1. Ne zaman gerekir — karar kuralı

| Soru | Mekanizma | Örnek |
|---|---|---|
| **NE ZAMAN** yapılabilir? (instance'ın durumuna/verisine bağlı kural) | **feature control** — `( features : instance )` + `get_instance_features` | "Onaylanan talep değiştirilemez / silinemez", "yalnız taslakken silinir", "onaylıya kalem eklenemez", "Onayla butonu yalnız 'Onayda' iken" |
| **KİM** yapabilir? (kullanıcıya/role bağlı kural) | **authorization** — `authorization master ( global, instance )` + `get_instance_authorizations` (ve/veya `get_global_authorizations`) | "Yalnız yöneticiler onaylar", "talep eden kendi talebini onaylayamaz" |

- Durum kuralını yetkiyle kurma: çalışır ama anlam yanlıştır — kullanıcı "yetkiniz yok" görür, oysa kural "bu durumda
  yapılamaz"dır; yetki denetimleri ve rolleri de gereksiz yere kirlenir. (Vaka 2026-09-21: model onaylı talebin
  salt-okunurluğunu önce "yalnız UI'da" deyip atladı, düzeltme istenince `auth-unauthorized` ile kurdu — ikisi de yanlış.)
- Aynı operasyon için ikisi birlikte olabilir: `Approve` aksiyonu durum "Onayda" değilse **feature control** ile pasif,
  talep eden kendisiyse **authorization** ile yetkisiz.
- Sınır her örnekte keskin değildir: SAP'nin kendi örnek senaryosunda "yalnız yorumu yazan değiştirebilir" kuralı feature
  control ile kurulmuştur (Kaynaklar, flight senaryosu `/DMO/ZZ_R_Agency_ReviewTP`). Ekip kuralı yine de yukarıdaki tablodur;
  sapacaksan gerekçeyi intake'e yaz ve kullanıcıya sor.
- **Yalnız UI'da gizlemek yetmez:** OData istemcisi (başka uygulama, Gateway istemcisi, EML tüketicisi) butonu görmeden de
  PATCH/DELETE/aksiyon gönderebilir. Kural backend'de feature control ile zorlanır; UI bunu yalnız **yansıtır** (§6).

## 2. BDEF sözdizimi

Kök (header) — standart operasyonlar, aksiyonlar, alanlar ve kalem ekleme (create-by-association):

```
define behavior for ZSD001_I_ORDER alias Order
persistent table zsd001_t_order
lock master
authorization master ( global, instance )
etag master LocalLastChangedAt
early numbering
{
  create;
  update ( features : instance );
  delete ( features : instance );

  field ( features : instance ) Description;

  action ( features : instance ) submitOrder  result [1] $self;
  action ( features : instance ) approveOrder result [1] $self;

  association _Item { create ( features : instance ); }
}
```

Kalem (child) — kendi operasyonları için kendi bildirimi:

```
define behavior for ZSD001_I_ORDERITEM alias Item
persistent table zsd001_t_orditem
lock dependent by _Order
authorization dependent by _Order
etag dependent by _Order
{
  update ( features : instance );
  delete ( features : instance );
  field ( readonly : update ) OrderId, ItemNo;
  association _Order;
}
```

Kurallar (kaynaklardaki örneklerden):
- `( features : instance )` şu yerlere yazılır: `update`, `delete`, `action`, `field ( … ) <alan>`, ve
  `association _X { create ( features : instance ); }`. Aynı parantezde yetki eki birlikte durabilir:
  `action ( features : instance, authorization : update ) acceptTravel …` (flight draft senaryosu).
- **Onaylı başlığa kalem eklemeyi engellemek** kalemin değil **başlığın** işidir: başlıkta
  `association _Item { create ( features : instance ); }` + başlığın `get_instance_features` sonucunda `%assoc-_Item`.
- **Child entity** kendi `update/delete ( features : instance )` bildirimini ve kendi `get_instance_features` metodunu
  (`FOR <child alias>`) taşıyabilir (`lock dependent` + `authorization dependent` child'da görüldü — flight senaryosu).
  Başlığın `%update`'ini kapatmanın mevcut kalemlerin güncellenmesini/silinmesini **otomatik** engellediği
  **DOĞRULANMADI** → kalem kuralını kalemde ayrıca kur, başlık durumunu kalem handler'ında oku (`BY \_Order` ya da
  kalemdeki anahtarla başlık okuma — `behavior-impl.md` §8 BY-association tuzağı).
- Projection BDEF feature control'ü yeniden bildirmez: `use update;`, `use action approveOrder;`,
  `use association _Item { create; }` yeterlidir; kontrol temel BDEF'ten gelir.
- `( features : global )` da vardır (instance'tan bağımsız, ör. özellik anahtarı) — bu belge yalnız instance biçimini kapsar.
- Statik alan kontrolü (`field ( readonly )`, `field ( mandatory )`, `field ( mandatory : create, readonly : update )`)
  duruma bağlı değildir; durum kuralı için kullanılamaz.

## 3. Handler — `get_instance_features`

CCIMP'te (behavior pool `source/main` boştur — `behavior-impl.md` §1):

```abap
CLASS lhc_order DEFINITION INHERITING FROM cl_abap_behavior_handler.
  PRIVATE SECTION.
    METHODS get_instance_features FOR INSTANCE FEATURES
      IMPORTING keys REQUEST requested_features FOR Order RESULT result.
ENDCLASS.

CLASS lhc_order IMPLEMENTATION.
  METHOD get_instance_features.
    READ ENTITIES OF zsd001_i_order IN LOCAL MODE
      ENTITY Order
        FIELDS ( Status )
        WITH CORRESPONDING #( keys )
      RESULT DATA(orders)
      FAILED failed.

    result = VALUE #( FOR o IN orders
      LET kapali = xsdbool( o-Status = 'A' OR o-Status = 'R' ) IN
      ( %tky                 = o-%tky
        %update              = COND #( WHEN kapali = abap_true THEN if_abap_behv=>fc-o-disabled
                                                               ELSE if_abap_behv=>fc-o-enabled )
        %delete              = COND #( WHEN o-Status = 'D'     THEN if_abap_behv=>fc-o-enabled
                                                               ELSE if_abap_behv=>fc-o-disabled )
        %action-approveOrder = COND #( WHEN o-Status = 'S'     THEN if_abap_behv=>fc-o-enabled
                                                               ELSE if_abap_behv=>fc-o-disabled )
        %assoc-_Item         = COND #( WHEN kapali = abap_true THEN if_abap_behv=>fc-o-disabled
                                                               ELSE if_abap_behv=>fc-o-enabled )
        %field-Description   = COND #( WHEN kapali = abap_true THEN if_abap_behv=>fc-f-read_only
                                                               ELSE if_abap_behv=>fc-f-unrestricted ) ) ).
  ENDMETHOD.
ENDCLASS.
```

- İmza: `keys` (kontrol edilecek instance anahtarları) · `requested_features` (tüketicinin sorduğu öğeler) · `result`;
  örtük `failed` / `reported` da vardır.
- RESULT bileşenleri: `%tky` · `%update` · `%delete` · `%action-<Aksiyon>` · `%assoc-_<Assoc>` · `%field-<Alan>`.
  Kaynaklarda hem düz (`%update`, `%action-acceptTravel`) hem gruplu (`%features-%update`, `%features-%action-…`)
  yazım görülür; ikisi aynı bileşene erişir.
- Değerler: operasyon → `if_abap_behv=>fc-o-enabled` / `fc-o-disabled`; alan → `if_abap_behv=>fc-f-read_only` /
  `fc-f-unrestricted` (kaynakta görüldü). `fc-f-mandatory` ve diğer alan değerleri bu kaynaklarda görülmedi →
  kullanmadan önce sistemde `IF_ABAP_BEHV` arayüzünden oku (**DOĞRULANMADI**).
- Durum değerleri (`'A'`, `'D'` …) koda gömülmez: domain sabit değerleri ya da sınıf sabitleri — ekip standardı.
- Okuma **`IN LOCAL MODE`** ile yapılır. Aynı ek, handler'daki `READ`/`MODIFY ENTITIES` için feature control, yetki ve
  precheck'i **bastırır** (abap-cheat-sheets EML): kendi aksiyonun (`approveOrder`) durumu güncellerken `update` kapalı olsa da
  `MODIFY ENTITIES … IN LOCAL MODE` çalışır (kaynak iddiası; bu ortamda **ölçülmedi** — §7a). Dış tüketicinin durduğu
  ölçüldü (§7a); kendi iç mantığının durmadığı ise ölçülmedi.
- Handler'da `COMMIT`/`MESSAGE` yasakları aynen geçerlidir (`behavior-impl.md` §10).

## 4. Yetki (authorization) — KİM sorusu, ayrı mekanizma

```abap
METHODS get_instance_authorizations FOR INSTANCE AUTHORIZATION
  IMPORTING keys REQUEST requested_authorizations FOR Order RESULT result.
```

- BDEF: `authorization master ( global, instance )` (child: `authorization dependent by _Order`). Yalnız `( instance )`
  biçimi bu kaynaklarda görülmedi (**DOĞRULANMADI**).
- İstenen operasyon `requested_authorizations-%update = if_abap_behv=>mk-on` ile okunur; sonuç
  `%update` / `%delete` / `%action-<Aksiyon>` = `if_abap_behv=>auth-allowed` / `if_abap_behv=>auth-unauthorized`;
  gerekçe mesajı `reported-<entity>` (`%msg`, `%element-<Alan>`) — flight draft senaryosu.
- "Talep eden kendi talebini onaylayamaz" → burada (`CreatedBy = kullanıcı` ise `%action-approveOrder = auth-unauthorized`).
  Kimin "yönetici" olduğu (yetki objesi + rol) kullanıcı-yönetimi konusudur; yetki objesi yeni Z obje ise ad kuralı
  `%sap-dev` §6.

## 5. Kontrol listesi (bu konu)

| Kontrol | Önem |
|---|---|
| Duruma bağlı her kural (düzenleme, silme, aksiyon, alan, kalem ekleme) backend'de feature control ile; yalnız UI yetmez | BLOCKER |
| Durum kuralı yetkiyle (`auth-unauthorized`) kurulmadı; kişi/rol kuralı feature control'e gömülmedi (sapma gerekçeli ve sorulmuş) | BLOCKER |
| Kalem kuralı kalemde ayrıca kuruldu; kalem ekleme başlığın `%assoc-_<Item>`'i ile | BLOCKER |
| BDEF'teki her `( features : instance )` için CCIMP'te `FOR INSTANCE FEATURES` metodu ve sonuçta ilgili bileşen | BLOCKER |
| Kendi aksiyonun durumu `IN LOCAL MODE` ile güncelliyor (kapalı `update` onu durdurmaz); dış tüketici için canlı test §7 | BLOCKER |

## 6. OData V2 ve freestyle SAPUI5'e yansıması

- SAP'nin OData V2 not sözlüğüne göre (SAP Annotations for OData Version 2.0): entity set'te `sap:updatable-path` /
  `sap:deletable-path` = "duruma göre güncellenebilir/silinebilir", değeri entity type'taki bir **Boolean** özelliğin yolu;
  function import'ta `sap:applicable-path` = aksiyonun o instance için çağrılabilir olduğunu söyleyen Boolean özelliğin yolu;
  özellikte `sap:field-control` = sayısal değer taşıyan özelliğin yolu (0 gizli · 1 salt-okunur · 3 isteğe bağlı · 7 zorunlu).
- RAP'ın bu özellikleri hangi adla ürettiği (`Update_mc`, `Delete_mc`, `<Aksiyon>_ac`, alan için `<Alan>_fc` biçimi) bu
  ortamda **DOĞRULANMADI**: `Update_mc` / `Delete_mc` yalnız bir SAP blog yazısının arama özetinde görüldü, `_ac` bu
  depodaki bir örnek `$metadata` dosyasında (`sap:applicable-path="releaseOrder_ac"`) geçiyor ama o dosyada özelliğin
  kendisi yok. **Önce kullanıcıdan gerçek `$metadata`'yı al** (servis yayınlandıktan sonra) ve adları oradan oku.
- Fiori Elements bu yolları kendiliğinden uygular (butonu pasifler). **Freestyle SAPUI5 uygulamaz**: kontrolün
  `enabled` / `editable` özelliğini `$metadata`'daki Boolean/sayısal özelliğe **sen bağlarsın** (ör. Düzenle butonu
  `enabled="{Update_mc}"` — ad `$metadata`'dan). UI bağlaması yalnız kullanıcı deneyimidir; zorlayan backend'dir.
  UI tarafı: `%sap-ui5-fiori`.
- Backend reddi tüketiciye `failed` + (varsa) `reported` mesajı olarak döner; OData'da dönen HTTP durum kodu ve metni
  **DOĞRULANMADI** → §7'de ölç, UI hata gösterimini ona göre yaz.

## 7a. Ölçüm sonucu — EML tüketici kolu (2026-09-22)

**Düzenek:** Z tablo (anahtar + `DURUM` + `ACIKLAMA` + `LAST_CHANGED timestampl`) → kök view entity → managed BDEF
(`lock master`, `etag master LastChanged`, `update ( features : instance ); delete ( features : instance );`) → behavior pool
CCIMP'te §3'teki `get_instance_features` (`Durum = 'A'` → `%update`/`%delete` = `fc-o-disabled`, değilse `fc-o-enabled`)
→ `IF_OO_ADT_CLASSRUN` sınıfında **`IN LOCAL MODE` OLMADAN** `MODIFY ENTITIES` (dış tüketici). Kayıtlar: `A1` (Durum `A`,
kapalı) ve `N1` (Durum `N`, açık — **kontrol grubu**); her deneme `ROLLBACK ENTITIES` ile kapatıldı.

| Deneme | Sonuç (ölçülen) |
|---|---|
| `UPDATE` A1 + N1 aynı çağrıda | `failed-<entity>` **1 satır: A1**; `%fail-cause` string şablonunda `DISABLED` yazdı. N1 `failed`'da yok |
| `DELETE` A1 + N1 aynı çağrıda | `failed` **1 satır: A1**, `%fail-cause` → `DISABLED`. N1 `failed`'da yok |
| Kontrol: `UPDATE` yalnız N1 + `COMMIT ENTITIES` | `failed` 0 · commit `failed` 0 · tabloda yeni değer kalıcı; A1 değişmedi |

**Kanıtladığı:** §2 BDEF sözdizimi + §3 handler imzası bu sürümde derlenir ve aktive olur; devre dışı operasyonu dış EML
tüketicisi çalıştırınca operasyon **hata vermeden** `failed`'a düşer (istisna yok) — bu yüzden tüketici `failed`'ı okumak
**zorundadır**. **Kanıtlamadığı:** OData'daki HTTP durum kodu/metni (§6), `$metadata` özellik adları, `IN LOCAL MODE`'un kapalı
operasyonu geçtiği iddiası (§3; sınıf içinden ölçülemez, kendi aksiyonun gerekir), alan düzeyi `%field-*`, `GET PERMISSIONS`.

**Yol üstündeki iki tuzak (ölçüldü):**
- Etag'siz managed BDEF'i aXet reviewer'ı yazmadan önce **BLOCKER** ile durdurur (`check_rap_managed_etag`) → tabloya zaman
  damgası alanı + CDS'te `@Semantics.systemDateTime.lastChangedAt: true` + BDEF'te `etag master <Alan>` gerekti.
- CCIMP, BDEF aktif değilken push edilince sınıf aktivasyonu `"<alias>" is not a subentity of the root entity` ile düşer
  (kaynak yüklenmiştir) → kök `ddls` + `also` [`bdef`, behavior sınıfı] tek aktivasyonda geçti.

## 7. Canlı doğrulama (ilk kullanımda zorunlu — SAP yazması kullanıcı onayıyla)

1. Kayıtlar: biri kapalı durumda (ör. onaylı), biri açık (taslak) — aynı entity, aynı kullanıcı.
2. **Test:** kapalı kayda OData `PATCH` (bir alan) → **hata beklenir**; dönen durum kodu + mesaj kaydedilir.
3. **Kontrol grubu:** açık kayda aynı `PATCH` → `204`. (Kontrol grubu yoksa "reddedildi" iddiası ölçülmüş sayılmaz —
   ret başka bir sebepten, ör. ETag/If-Match eksikliğinden gelmiş olabilir.)
4. Aynısı `DELETE`, kapalı kayda kalem `POST` (create-by-association) ve durum dışı aksiyon çağrısı için.
5. `$metadata`'da `sap:updatable-path` / `sap:deletable-path` / `sap:applicable-path` / `sap:field-control` ve işaret ettikleri
   özellikler; freestyle UI'da ilgili kontrolün pasif olduğu.
6. Kendi aksiyonun (`IN LOCAL MODE`) kapalı `update`'e rağmen durumu güncelleyebildiği.
Sonuç (çalışan biçim + denenip olmayan) `%remember` ile ekip hafızasına; bu belgedeki DOĞRULANMADI işaretleri güncellenir.

## Kaynaklar (adıyla; bu belge yazılırken okundu, 2026-09-21)
- SAP ABAP Keyword Documentation / SAP Help Portal, ABAP RAP: "RAP - feature control", "Instance Feature Control",
  "Feature Control" (arama özeti: devre dışı operasyon UI'da pasif görünür; EML tüketicisi çalıştırırsa operasyon başarısız
  olur ve `failed`'a kayıt döner). Sayfa gövdesi otomatik okunamadı; ifade arama özetindendir.
- SAP-samples `abap-platform-refscen-flight` (ABAP platform 2025 dalı): `/DMO/I_TRAVEL_M` + `/DMO/BP_TRAVEL_M`
  (`action ( features : instance )`, `association _Booking { create ( features : instance ); }`, `%assoc-_booking`),
  `/DMO/R_TRAVEL_D` + `/DMO/BP_TRAVEL_D` (`field ( features : instance )`, `%field-…`, `fc-f-read_only`,
  `get_instance_authorizations`, `auth-allowed`/`auth-unauthorized`), `/DMO/ZZ_R_Agency_ReviewTP` (child'da
  `update/delete ( features : instance )`, `%update`/`%delete`), projection `/DMO/C_TRAVEL_APPROVER_M` (`use action`).
- SAP-samples `abap-platform-rap100`, alıştırma 7 "Dynamic Feature Control" (`update/delete ( features : instance )`,
  `get_instance_features` imzası, `%features-%update`).
- SAP-samples `abap-cheat-sheets`, "ABAP EML in RAP" (`IF_ABAP_BEHV=>FC-O` / `FC-F` / `AUTH` sabitleri; `IN LOCAL MODE`'un
  feature control, yetki ve precheck'i bastırması).
- SAP `odata-vocabularies`, "SAP Annotations for OData Version 2.0" (`sap:updatable-path`, `sap:deletable-path`,
  `sap:applicable-path`, `sap:field-control` tanımları).
