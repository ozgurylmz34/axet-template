# RAP katmanlama, view entity (RAP'a özgü) ve behavior definition

> Kaynak: ekip RAP playbook'u, RAP kodlama standardı, RAP backend tecrübe bankası ve RAP kontrol listeleri; aXet'e
> uyarlandı. Deneyim `s4_private` (on-prem 2025) sisteminde ölçüldü. CDS/DDIC temel yöntemi: `%sap-cds-ddic`.
> Adlar: `%sap-dev` → `references/naming.md` §4.2/§4.3. Örnek adlar nötr demodur (`ZSD001_I_ORDER`, `ZCL_SD001_ORDER`).
> "ÇALIŞAN YÖNTEM" ve "DENENEN — BAŞARISIZ" satırları ölçülmüş deneyimdir.

## 1. Hangi şekil

| Senaryo | Şekil |
|---|---|
| Yeni Z transactional belge (Z tablo; standart belge ya da BAPI sarmıyor) | **managed BO** |
| Standart belge (satış siparişi, teslimat …) üzerinde create/update | **unmanaged façade** — yazma released API'ye (released BO EML · released BAPI · released OData) ya da, o yoksa, BAPI/RFC FM'e gider; standart tabloya doğrudan yazma kesin yasak B. **Hangi API, hangi canlı teyitle:** `%sap-dev` → `write-api-selection.md` |
| Salt-okunur liste / worklist / value help | **davranışsız query CDS** (servisinde behavior'suz expose) |
| Klasik dialog/rapor ya da mevcut SEGW servisi | klasik track — dokunma, RAP'a zorla taşıma yok |

Karar gerekçesi her zaman yazılır (clean core seviyesi A/B/C/D, `%sap-dev` → naming §1). Bir iş kalemi ya klasik ya RAP
track'le gider; RAP seçildiyse aynı iş için SEGW kullanılmaz.

## 2. Katmanlar

```
Service Binding   ZSD001_UI_ORDER_O2 (UI/API + _O2/_O4)   ← publish
  └ Service Definition  ZSD001_UI_ORDER                    ← expose listesi
      ├ Projection view  ZSD001_C_ORDER  (+ projection BDEF ZSD001_C_ORDER)
      └ Interface view   ZSD001_I_ORDER  (root) composition of ZSD001_I_ORDERITEM
          ├ Behavior Definition ZSD001_I_ORDER (= root view adı) → sınıf ZCL_SD001_ORDER
          └ Z tablo(lar)  ZSD001_T_ORDER …                    ← persistence (yalnız Z)
```

- Projection doğrudan tabloya bakmaz; interface view'a bakar. Transactional BO'nun persistence'ı **yalnız Z tablodur**.
- SRVD yalnız projection ve salt-okunur query CDS'leri expose eder; interface view doğrudan expose edilmez.
- BDEF adı **root view entity adıyla aynıdır** (SAP zorunluluğu; farklıysa aktivasyon düşer). Behavior sınıfı ayrıdır:
  `ZCL_<gövde>_<AD>` (`ZBP_*` kullanılmaz). Draft tablosu `ZSD001_A_ORDER_D`.
- `_I_` öneki hem klasik include hem interface view için kullanılır; aynı kök adı iki tipte kullanma.

## 3. View entity — RAP'a özgü kurallar

**ÇALIŞAN YÖNTEM**
- Klasik `define view` değil `define [root] view entity`. `@AbapCatalog.sqlViewName` view entity'de **olmaz** (varsa hata).
- `@AccessControl.authorizationCheck` her interface/projection view'da yazılır (`#CHECK` ya da `#NOT_REQUIRED`).
- Root interface view'ın projection'ı da `define root view entity … as projection on …` olmalı. Aksi:
  `ROOT keyword missing since <I_view> has the root property` → aktivasyon iptal. Tersi: projection root ise interface de root
  olmalı, yoksa `ROOT keyword not valid`.
- BDEF henüz yokken projection aktivasyonu **uyarı** verir (`Transactional Provider Contract expected`) — BDEF gelince kapanır.
- Composition (root ↔ child):
  ```cds
  define root view entity ZSD001_I_ORDER as select from zsd001_t_order
    composition [0..*] of ZSD001_I_ORDERITEM as _Item
  { key order_id as OrderId, …, _Item }

  define view entity ZSD001_I_ORDERITEM as select from zsd001_t_orditem
    association to parent ZSD001_I_ORDER as _Order on $projection.OrderId = _Order.OrderId
  { key order_id as OrderId, key item_no as ItemNo, …, _Order }
  ```
  Projection'da root: `_Item : redirected to composition child ZSD001_C_ORDERITEM`; child projection (root değil):
  `_Order : redirected to parent ZSD001_C_ORDER`. Karşılıklı bağımlı dört CDS'i önce inaktif push et, sonra **tek**
  aktivasyon isteğinde aktive et (`adt_activate` + `also`).
- `cast` / `coalesce` / `case` gibi ifadeler **projection'da desteklenmez** (`Field X contains a not supported expression`) →
  ifadeyi interface view'a koy, projection düz expose etsin.
- Sayım/aggregation root transactional view'da olmaz (root 1:1 kalmalı) → ayrı aggregation yardımcı view'ı
  (`count … group by`) + root'tan association; `coalesce(_Helper.Cnt, 0)` interface'te.
- Türetilmiş alan (ör. tarih + gün) interface'te hesaplanır; projection expose eder; BDEF'te `field ( readonly )` diye
  bildirilmez (association/ifade alanları zaten salt-okunurdur).
- `@EndUserText.label` en fazla 40 karakter (uzunu uyarı verir ve kesilir).
- **Mevcut aktif root CDS** güncellemesi yerinde push ile yapılır. Sil-yeniden-yarat YAPMA: bağlı BDEF/servis zinciri kırılır.
- Released CDS'te `@Semantics.quantity` taşıyan alanı (ör. birim çevrim payı/paydası) aritmetikte ya da `case` içinde
  doğrudan kullanmak → `Elements with required UNIT-reference are not supported` → önce `cast( … as abap.dec(n,m) )`.
- Kaynaklar `@AbapCatalog.compiler.compareFilter` için çelişiyor (bir kayıt "view entity'de gereksiz", standart "true ver"
  diyor) → **DOĞRULANMADI**; aktivasyon mesajına ve `%sap-cds-ddic`'e bak.

## 4. Salt-okunur consumption (BDEF'siz rapor)

**ÇALIŞAN YÖNTEM**
- Interface `ZSD001_I_<RAPOR>` = `define view entity … as select from <tablo/released CDS> … left outer join <I_ view'lar>`.
  Join'de yeniden kullanılan RAP view'ları **interface** (`_I_`) olmalı; association'la çözülen ad alanları interface'te
  element değildir → ilgili text/VH view'ını doğrudan join'le.
- Consumption `ZSD001_C_<RAPOR>` = `define view entity … as select from ZSD001_I_<RAPOR> { key …; … }`.
- Aktivasyon: I_ → C_. "Search help not inherited" uyarıları salt-okunurda zararsız.

**DENENEN — BAŞARISIZ**
1. Interface'te join kaynağı olarak projection view (`ZSD001_C_*`) → `Projection Views are not allowed as base object for this entity type.`
2. Consumption'ı `as projection on ZSD001_I_…` yazmak → `Transactional Projection View must be part of a business object.`
   (`as projection on` transactional'dır, BDEF ister.)

Bu iki kontrol aXet yazma kapısının CDS incelemesinde **koşmaz** (CDS push'u genel CDS zincirine gider) → elle kontrol et.

Klasik (DDIC tabanlı) bir raporu RAP'a taşırken: mevcut klasik CDS'i **sar** (`define view entity ZSD001_C_<X> as select from
<klasik_view>`), mantığı yeniden yazma, klasiğe dokunma; CamelCase alias; key alanlar başta; kaynak
`@Metadata.ignorePropagatedAnnotations` taşıyorsa `@Semantics` (miktar/tutar) sarmalayıcıda tekrar yazılır. Yetki: DCL
(`grant select where ( SalesOrganization ) = aspect pfcg_auth( V_VBAK_VKO, VKORG, ACTVT = '03' )` gibi); kişisel veri ise
view'da `where username = $session.user`. Servis ve publish: `service-publish.md` §7.

## 5. Abstract entity (action/function parametresi ve sonucu)

- `define [root] abstract entity ZSD001_I_<AD>_P` / `_R`: SELECT ve SQL view taşımaz; view entity değildir.
- Sonuç `[0..*]` → koleksiyon döner; DDIC tablo tipi gerekmez.
- **Ölçülen reçete (üç adım, atlanamaz):** ① kabuk ② kaynağı **ayrıca** yaz ③ aktive et ve aktif kaynakta `abstract entity`
  metni + aktif sürüm + yerel ↔ canlı içerik eşitliğini doğrula. ② atlanırsa yaratma `201` döner ama kaynak **0 karakter**
  kalır ve aktivasyon `SDDL_PARSER_MSG 013` ile düşer (ölçüm: yalnız ① ile 0/11, ② ile 11/11). `201` kanıt değildir.
- Sonuç entity'sinde miktar/tutar (`kwmeng`, `wrbtr` tipleri) → `reference information missing or data type wrong`; birim/para
  birimi referansı ister. Yalnız sayı taşıyan sonuçta düz `abap.dec(13,3)` / `abap.dec(15,2)` kullan.
- Parametre alan adı/tipi mevcut benzer parametre entity'sinden **aynen** kopyalanır; uydurulmaz. Etiket `master_language`'de.
- Birden çok operasyon aynı sonuç entity'sini paylaşabilir. UI'ın beklediği alan adları varsa (eski servisten geçiş) sonuç
  alan adları eski property adlarıyla birebir tutulur.
- CLI yolu: `adt_post_shell` `object_type=ddls` (adım ①, yalnız metadata kabuğu — kaynak gövdeye konmaz) → `adt_get` →
  `adt_push_source ddls` (adım ②) → `adt_activate` → readback (adım ③). Kabuk yolu çevrimdışı test edildi, canlı **DOĞRULANMADI**
  (SKILL.md "CLI kapsamı"); araç canlıda düşerse kullanıcı kabuğu Eclipse ADT'de açar.

## 6. Behavior definition kuralları

| Konu | Kural |
|---|---|
| Implementation type | Z tablo → `managed`. Standart belge → `unmanaged` (released BAPI/EML; hangi API: `%sap-dev` → `write-api-selection.md`). |
| Kilit + ETag (**BLOCKER**) | Yazma operasyonlu managed root: `lock master` + `etag master <LastChangedAt alanı>`. ETag alanı root view'da `@Semantics.systemDateTime.lastChangedAt: true` (+ created/lastChangedBy admin alanları). Child: `lock dependent by _Order` + `etag dependent by _Order`. Eksikse eşzamanlılık çalışmaz; yazma kapısının BDEF incelemesi BLOCKER verebilir. |
| Yetki | `authorization master ( global )` varsa CCIMP'te boş gövdeli `get_global_authorizations` **zorunlu** (yoksa uyarı hataya döner; façade'da `not an entity with authorization check`). Child: `authorization dependent by _Order`. |
| Duruma bağlı kural (**BLOCKER**) | "Onaylanınca değiştirilemez / silinemez / kalem eklenemez", "aksiyon yalnız şu durumda" → `update/delete ( features : instance )`, `action ( features : instance )`, `field ( features : instance )`, `association _Item { create ( features : instance ); }` + `get_instance_features` (`feature-control.md`). Yetkiyle (`auth-unauthorized`) kurma; yalnız UI'da gizleme. |
| Numara (NR objesi / numara aralığı, CHAR key) | Root karakteristiğinde `early numbering` + CCIMP `earlynumbering_create FOR NUMBERING` (`behavior-impl.md` §3). `numbering : managed` yalnız UUID/RAW16 → CHAR key'le kullanma. Numarayı determination ile verme. NR objesini kullanıcı yaratır/yönetir. |
| Child behavior | Parent bloğunun `{ }` **dışında**, kapanıştan sonra ayrı üst seviye `define behavior for` (kardeş). İçine yazılırsa `"behavior" is not expected here` + `"define|foreign|scalar" was expected, not "}"`. |
| Child key | Composition child'ın parent'tan gelmeyen key alanı: `field ( readonly : update ) ItemNo` (uyarıyı kapatır, sunucuda korur). Hesaplanan/association alanını `field ( readonly )` ile bildirme. |
| Trigger | `on save { update; }` tek başına geçersiz: `The trigger update is only allowed in combination with create here.` → `{ create; update; }`. `{ delete; }` ve `{ create; }` tek başına serbest. |
| `field` listesi | `validation x on save { field a, b; create; update; }` — `create;`/`update;` operasyon tetikleyicisidir, `field` listesi onu **daraltmaz**. Muafiyet gerekiyorsa handler içinde ver. |
| Action adı | `Lock` / `Unlock` rezervedir → `AcquireLock` / `ReleaseLock`. Action/function adı camelCase. |
| Draft | Varsayılan draft'sız. Draft kararı açık yazılır (`draft-and-locks.md`); draft tablosu `…_A_…_D`. |
| BDEF kaynağında ters tırnak | U+0060 karakteri her çekme+yazma turunda sessizce çoğalıyor (depoda 2, canlıda 8 ölçüldü); push/aktivasyon hata vermez. Yorumlarda kullanma; yazma kapısı BLOCKER verebilir. |
| Metin | `@EndUserText` `master_language`'de, tam, spesifikasyondan. |

### 6.1 Örnek — managed root + child (ÇALIŞAN yapı; adlar demo)
```
managed implementation in class zcl_sd001_order unique;

define behavior for ZSD001_I_ORDER alias Order
persistent table zsd001_t_order
lock master
authorization master ( global )
etag master LastChangedAt
early numbering
{
  create; update; delete;
  association _Item { create; }
  determination setAdmin on save { create; update; }
  validation checkItems on save { create; update; }
  mapping for zsd001_t_order { OrderId = order_id; … }
}

define behavior for ZSD001_I_ORDERITEM alias OrderItem
persistent table zsd001_t_orditem
lock dependent by _Order
authorization dependent by _Order
etag dependent by _Order
{
  update; delete;
  field ( readonly ) OrderId;
  field ( readonly : update ) ItemNo;
  association _Order;
  mapping for zsd001_t_orditem { OrderId = order_id; ItemNo = item_no; … }
}
```
İlk satırın biçimi (`implementation in class … unique`) kaynakta tam metin olarak yok → sistemdeki çalışan bir BDEF ile
kıyasla (**DOĞRULANMADI**). `etag dependent by` biçimi kaynakta "etag dependent" diye geçer → aynı şekilde doğrula.

### 6.2 Projection BDEF (ayrı obje, adı projection root)
```
projection;
define behavior for ZSD001_C_ORDER
{ use create; use update; use delete; use association _Item { create; } use action AcquireLock; }
define behavior for ZSD001_C_ORDERITEM
{ use update; use delete; use association _Order; }
```

### 6.3 Unmanaged façade — standart veri + static function/action (ÇALIŞAN)
Veri standart objelerde, yazma released BO'ya gider; kendi persistence, kilit, numara yok.
1. `define root view entity ZSD001_I_X as select from <standart/released>` (join'ler) → `define root view entity ZSD001_C_X as projection on ZSD001_I_X`.
2. Parametre ve sonuç abstract entity'leri (§5).
3. Interface BDEF:
   ```
   unmanaged implementation in class zcl_sd001_x;
   define behavior for ZSD001_I_X authorization master ( global )
   { static function GetBalance parameter ZSD001_I_BAL_P result [0..*] ZSD001_I_BAL_R;
     static action CreateOrder parameter ZSD001_I_ORD_P result [1] ZSD001_I_ORD_R; }
   ```
   - `strict ( 2 )` **kullanma** (salt-okunur/static-only): `every entity must be lock master/dependent`. strict uyarısını kabul et.
   - READ implement edilmemesi yalnız uyarıdır. Saver implement edilmez ("SAVER not implemented" yalnız uyarı).
4. Projection BDEF: `projection; define behavior for ZSD001_C_X { use function GetBalance; use action CreateOrder; }`.
5. Kural: **okuma = function (V2 GET function import)**, **yazma = action (V2 POST)**. Operasyon eklerken base + projection BDEF'e
   satır, CCIMP'e handler; BDEF değişince ikisi de yeniden yazılır, birlikte aktive edilir, servis yeniden yayınlanır.

## 7. Aktivasyon sırası ve döngüsel bağımlılık

- Sıra: interface CDS → projection CDS → BDEF (interface + projection) → behavior sınıfı → SRVD → SRVB → publish.
- CDS değişince üstündeki BDEF yeniden aktivasyon ister. Kök CDS'e alan eklemek BDEF'i sessizce inaktif bırakır.
- Managed BDEF tek başına: behavior sınıfı yoksa `BEHAVIOR cannot be implemented`. Sınıf tek başına (BDEF inaktifken):
  `BEHAVIOR cannot be implemented in class`. **ÇALIŞAN:** BDEF + sınıf aynı aktivasyon isteğinde (`adt_activate` + `also`).
- `The operation "CREATE" is not activated for entity` (early numbering handler satırını gösterir, yanıltıcı): önce BDEF'te
  `early numbering` var mı bak; varsa kademeli aktive et — önce BDEF'ler (interface + projection, create aktif olsun), sonra
  sınıfla birlikte.
- Toplu aktivasyonda tek bir hata tüm seti iptal eder → hatasız alt küme önce, kalanı sonra.
- "Inconsistent in active version" zinciri → bağımlı CDS'i temiz kaynakla push et, graf aktivasyonu birlikte aktive eder.
- HTTP 200 aktivasyon kanıtı değildir. Hüküm tek kaynaktan (`sap_adt_lib.aktivasyon_govde_hukmu`; elle regex yazma — elle
  yazılan kopyalar ayrıştı, biri yalnız-generation gövdesini başarı, diğeri başarısızlık sayıyordu):
  `True` = `activationExecuted="true"` ve E/A mesajı yok · `False` = boş/HTML/`ioc:inactiveObjects` gövde, E/A mesajı ya da
  yürütülmedi · `None` = gövde hüküm taşımıyor (ör. `activationExecuted="false"` + `generationExecuted="true"`, ya da bayraksız
  gövde) → bağımsız worklist sondası karar verir; sonda ölçemezse sonuç başarı DEĞİLDİR (DOĞRULANAMADI). Sonra
  `adt_inactive_objects`. ⚠ Obje aktivasyondan önce worklist'te değilse "listede yok" ayırt edici değildir.
- Uyarılar ("global authorization not implemented", "key should be readonly", "secondary key … covered/not used") normaldir;
  hata değildir ama okunur.

## 8. Kesin yasakların RAP yüzeyi

| Yasak | RAP'taki karşılığı |
|---|---|
| **A** Standart obje | Interface/projection view yalnız Z tablo/Z CDS kaynaklı. Standart CDS/BO append/extend edilmez; standart behavior'a `extension` yazılmaz. (Salt-okunur query ve façade'da standart tabloyu/released CDS'i **okumak** yasak değildir; released CDS tercih edilir — `value-help.md` §3.) |
| **B** Standart tablo verisi | Managed behavior EML'i yalnız Z tabloya yazar. Standart belge gerekiyorsa unmanaged + sıra: released API (released BO EML · released BAPI · released OData) → BAPI → RFC FM → BDC → manuel (`%sap-dev` → `write-api-selection.md`). Standart tabloya `MODIFY ENTITIES` / SQL yazma yok. |
| **C** Sistem durumu | Transport/paket yaratılmaz; BDEF/CDS/SRVD/SRVB kullanıcının verdiği transporta. Publish mevcut transportu kullanır. NR objesi ve SM59 destination AI tarafından yaratılmaz. |
| **D** Z obje metni | CDS `@EndUserText.label`, BDEF `@EndUserText`, SRVD başlığı `master_language`'de, tam, spesifikasyondan; aktivasyon readback'inde doğrulanır. Tablo alan adları sistemden okunur. |
