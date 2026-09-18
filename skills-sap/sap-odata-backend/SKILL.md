---
name: sap-odata-backend
description: >
  Use when building or changing a classic SAP Gateway OData V2 backend: a SEGW project, entity
  types and sets, MPC_EXT or DPC_EXT classes, GET_ENTITYSET or GET_ENTITY reads with filter and
  paging, create or update or delete through BAPI, deep insert, function import, ETag or enqueue
  locking, Gateway error messages, $metadata checks, and backend rules that a UI depends on
  (filter and search behavior, decimal and date serialization, key padding) or ABAP calling
  another SAP OData API through the internal gateway proxy. Triggers: "SEGW", "DPC_EXT",
  "MPC_EXT", "OData servisi yaz", "entity set ekle", "function import", "deep insert",
  "get_entityset", "servis 400 dönüyor", "toupper desteklenmiyor", "metadata'da alan yok",
  "ABAP'tan OData API çağır", "simülasyon API", "/IWFND/MAINT_SERVICE". Do not use for RAP
  services (service definition, binding, behavior; use sap-rap), for UI5 frontend code, or for
  triaging a new request (use sap-intake-triage first).
---

# SAP klasik OData backend (SEGW / Gateway V2)

> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde (`00-sap.md`) her oturum yüklüdür; burada tekrarlanmaz.
> Adlandırma: `%sap-dev` → `references/naming.md` §4.2 (klasik servis `ZSD001_ODS_<AD>`).
> CLI, yazma kapısı, pull-before-edit, readback: `%sap-adt-foundation`. Bu skill onları tekrar yazmaz.

**Profil:** SEGW klasik OData yalnız `ecc` ve `s4_private`'ta vardır. `s4_public` ve `btp_abap`'ta SEGW
**yasaktır** (orada RAP → `%sap-rap`). `s4_private`'ta yeni işte RAP tercih edilir, SEGW çalışır. Mevcut bir SEGW
servisi RAP'a zorla taşınmaz.

## When to use this skill
- Bir SEGW servisine entity, property, association, function import ya da deep insert eklerken.
- `ZCL_*_DPC_EXT` / `ZCL_*_MPC_EXT` kaynağını okurken, düzeltirken, genişletirken.
- Servis 400/405/412/500 dönüyor, `$metadata`'da alan görünmüyor, filtre/arama boş geliyor.
- ABAP'tan başka bir SAP OData API'sini çağıran kod yazarken (RAP handler'dan çağrılsa bile bu skill).
- **Kullanma:** RAP servisi (SRVD/SRVB/BDEF) → `%sap-rap` · klasik program/sınıf push ayrıntısı →
  `%sap-classic-abap` · UI5 kodu → UI5 skill'i · yeni talep → önce `%sap-intake-triage`.

## How to use this skill

### 1. RAP mı klasik OData mı?
| Durum | Yol |
|---|---|
| Profil `s4_public` / `btp_abap` | RAP (`%sap-rap`), SEGW yok |
| Yeni servis, `s4_private` | RAP tercih; SEGW gerekçesi (ör. mevcut SEGW servisini genişletmek) kullanıcıyla netleşir |
| Mevcut SEGW servisinde değişiklik | Bu skill |
| `ecc` | Bu skill (RAP yok) |

Karar belirsizse DUR, kullanıcıya sor. Ayrıntı: `references/segw-service.md` §1.

### 2. Önce oku
1. `sap-project.json` profili + paket `.rules.md` (`%sap-dev`).
2. İş türüne göre aşağıdaki referansı aç; hepsini değil.
3. Değişecek `DPC_EXT` / `MPC_EXT` sınıfının **güncel kaynağını** CLI ile çek (`adt_get`, pull-before-edit).
   Aynı servisin çalışan başka bir metodu en iyi desen kaynağıdır: önce onu oku, sonra yaz.

### 3. Servis ve entity tasarımında kullanıcıyla mutabık kal
Kod yazmadan önce tek mesajda göster ve onay al: entity/entity set/property adları ve tipleri, anahtar alanlar,
navigation'lar, function import adı ve **tüm** parametreleri, hangi işlemin hangi BAPI/RFC FM ile yazılacağı,
yetki nesnesi, kilit nesnesi, ETag alanı. Belirsiz bir nokta varsa hepsini tek seferde sor; yapım ortasında soru
açma. Yeni DDIC/DTEL gerekiyorsa ad ve metinler kullanıcıdan (`%sap-dev`).

### 4. Model tarafı (SEGW) — kullanıcı yapar, model tarif eder
SEGW projesi, entity type, Generate, servis kaydı (`/IWFND/MAINT_SERVICE`) ADT REST ile yapılamaz. Model adımları
**numaralı ve alan alan** yazar, geliştirici SAP GUI'de uygular, sonucu (ekran/metadata parçası) paylaşır.
Reçete: `references/segw-service.md`.

### 5. Kod tarafı — CLI ile yaz
`DPC_EXT` / `MPC_EXT` Z sınıflarıdır: `adt_get` → düzenle → `adt_push_source` → `adt_activate` → `adt_get`
readback + `adt_inactive_objects` (`%sap-adt-foundation` §5-7; sınıf push ayrıntısı `%sap-classic-abap`).
SEGW'nin ürettiği temel `MPC`/`DPC` sınıflarına yazılmaz; iş mantığı yalnız `_EXT`'tedir.
- Standart tabloya OData üzerinden yazma ihtiyacı = **kesin yasak B**: DPC içinde doğrudan
  `INSERT/UPDATE/MODIFY/DELETE` yok; BAPI → RFC FM → BDC → kullanıcıdan manuel (`references/dpc-crud.md` §3).
- Push `ADR_0005_B` ile reddedilirse komutu değiştirme; DUR, BAPI yolunu kullanıcıyla konuş.

### 6. Doğrula
1. `$metadata`: CLI'de araç yok → kullanıcı tarayıcıda açar, ilgili `EntityType` / `FunctionImport` bloğunu
   paylaşır; kontrol **tip-kapsamlı** yapılır (`%sap-adt-foundation` → `references/foundation-query.md` §5, §5.1).
2. Okuma isteği (GET, `$filter`, `$top`, `$inlinecount`) için tam URL'yi model yazar, kullanıcı çalıştırır.
3. **Veri yazan istek (POST/PUT/MERGE/DELETE, yazan function import) model tarafından çalıştırılmaz ve
   çalıştırılması önerilmez.** Gerekirse yalnız tarif: DEV sistem + kullanıcının açık onayı + test verisi
   kullanıcıdan. QA/PRD'de hiç.
4. "Servis çalıştı" demek için kontrol grubu: aynı serviste çalıştığı bilinen bir entity set ile karşılaştır.
5. Önemli değişiklikten sonra `%sap-code-review`, "tamam" demeden `%verify-done`.

## Referanslar
| Dosya | İçerik |
|---|---|
| `references/segw-service.md` | Teknoloji önceliği, SEGW proje yapısı, adlandırma kuralları, MPC_EXT (`set_filterable`, ETag), Generate + servis kaydı, cache, conversion exit, CDS `@OData.publish` sınırı |
| `references/dpc-crud.md` | DPC_EXT iskeleti, GET_ENTITYSET (filtre, paging, inlinecount, expand), create/update/delete + BAPI + COMMIT kuralları, yetki, enqueue kilidi, ETag, hata sınıfları, message container, BAPIRET2, audit alanları |
| `references/deep-insert-function-import.md` | `CREATE_DEEP_ENTITY`, function import 405 tuzağı, FI parametre kuralları, Gateway FI içinden EML, URL uzunluğu, SEGW→RAP göç notları |
| `references/filter-search.md` | `/IWBEP` `toupper`/`tolower` 400 (Note 1797736), `substringof`/`startswith`/`endswith`, select options okuma, wildcard sözleşmesi |
| `references/serialization.md` | Decimal/miktar string'e çevirme (`WRITE ... TO` tuzağı), `Edm.DateTime` `/Date(ms)/`, anahtar sıfır dolgusu, conversion exit, `sap-message` header |
| `references/outbound-api-call.md` | ABAP'tan SAP-içi OData API çağrısı: iç gateway proxy (kanonik), dil ve query'li URL tuzakları, CSRF, SM59 (legacy) tuzakları, RAP handler'da `MESSAGE` dump, standart API payload dersleri |
| `references/backend-coding.md` | Performans kuralları, güvenlik kontrol listesi, RFC FM şablonu, ABAP Unit deseni, CDS katmanlama (OData'ya açılan kısım), draft kararı |

## Rules
- Tahmin yok: property adı, tip, FI parametresi, BAPI imzası ve standart API alanı çalışan artefakttan ya da
  sistemden (`adt_get`, kullanıcının paylaştığı `$metadata`) doğrulanır.
- Standart tabloya yazma yalnız BAPI/RFC FM ile (kesin yasak B). Klasik DPC'de BAPI sonrası
  `BAPI_TRANSACTION_COMMIT` yapılır; **RAP handler'da ve ondan çağrılan sınıfta yapılmaz** (`references/dpc-crud.md` §4).
- Kimlik bilgisi (kullanıcı, şifre, token) ABAP kaynağına, script'e, loga yazılmaz; `authenticate( password = … )`
  kopyalanmaz (`references/outbound-api-call.md` §5).
- `sap-client` / host kodda sabitlenmez; runtime'dan alınır.
- SEGW GUI adımlarını ve SM59/servis kaydını model yapmaz; tarif eder. Transport ve paketi kullanıcı verir.
- Servis testi için veri yazan OData isteğini model çalıştırmaz (§6.3).
- "Metadata'da var / servis 200" iddiası tip-kapsamlı kontrol ve kontrol grubu olmadan yazılmaz; doğrulanmayan
  `DOĞRULANMADI` diye etiketlenir.
- Denemelerden sonra çalışan bir Gateway yöntemi bulunduysa `%remember` ile kaydet.
