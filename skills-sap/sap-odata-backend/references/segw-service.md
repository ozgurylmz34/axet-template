# SEGW servis ve model tarafı

> Kaynak: ekip backend kodlama standardı (klasik track: OData V2 SEGW, MPC/DPC, servis aktivasyonu),
> OData servisleri playbook'u, bilinen hatalar (SmartFilterBar/SADL), CDS playbook'u (conversion exit), profil matrisi.
> SEGW ve SAP GUI adımlarını **kullanıcı yapar**; model adımları alan alan tarif eder, sonucu kullanıcıdan ister.

---

## 1. Teknoloji seçimi

### 1.1 Profil
| Profil | SEGW klasik OData |
|---|---|
| `ecc` | var (NW 7.31+ Gateway); RAP yok |
| `s4_private` | izinli; yeni işte RAP tercih |
| `s4_public` · `btp_abap` | **yasak** → RAP (`%sap-rap`) |

Profil matrisi rehberdir, kanıt değildir: yetenek şüphesinde canlı sistemde doğrula.

### 1.2 Servis uygulama önceliği (klasik track)
| Öncelik | Senaryo | Teknoloji |
|---|---|---|
| 1 | Okuma ağırlıklı liste, rapor, value help | CDS view → OData V2 (salt-okur ise `@OData.publish`, §6) |
| 2 | İşlem (create/update/delete) | DPC_EXT içinde BAPI / RFC FM |
| 3 | Join/aggregation'lı karmaşık sorgu | CDS (HANA'ya özgü mantık gerekirse AMDP) |
| 4 | Karma (CDS ile oku, RFC ile yaz) | MPC'de CDS entity + DPC_EXT'te RFC çağrısı |
| 5 | CDS mümkün olmayan eski entegrasyon | RFC → SEGW function import |

Aynı iş için RAP yolu açıksa (profil + kullanıcı kararı) bu tablo yerine `%sap-rap`.

---

## 2. SEGW proje yapısı

```
SEGW projesi (servis adı: %sap-dev naming §4.2, ör. ZSD001_ODS_ORDER)
├── Data Model
│   ├── Entity Types        (tekil, PascalCase: SalesOrder)
│   ├── Entity Sets         (SalesOrderSet)
│   ├── Associations / Navigation (To<Hedef>: ToItems, ToHeader)
│   └── Function Imports    (Fiil + İsim: CreateOrder, ApproveRequest)
├── Service Implementation
│   ├── ZCL_…_MPC  / ZCL_…_MPC_EXT   (model; _EXT yalnız dinamik değişiklik için)
│   └── ZCL_…_DPC  / ZCL_…_DPC_EXT   (tüm iş mantığı _EXT'te)
└── Service Maintenance → /IWFND/MAINT_SERVICE
```

Sınıf adları SEGW'nin ürettiği desene göredir; paket `.rules.md` farklı bir istisna yazıyorsa o geçerlidir.
Proje içindeki entity/set/association ad desenleri (ör. eski `ZET_`, `ZA_` önekleri) paketin mevcut servisinden
okunur; yeni servis mevcut servisin desenine uyar.

### 2.1 Tasarım kuralları
```
Entity type:        PascalCase tekil (SalesOrder; SalesOrders değil)
Entity set:         PascalCase + Set (SalesOrderSet)
Property:           PascalCase (CompanyCode, DocumentDate)
Key alanları:       property listesinde ilk sırada, SEGW'de key işaretli
Navigation:         To<HedefEntity> (ToItems, ToHeader)
Function import:    Fiil + İsim (CreateOrder, GetWorklistItems)
HTTP method:        GET=sorgu · POST=create/aksiyon · PUT=tam güncelleme · PATCH/MERGE=kısmi · DELETE=silme
```
- İşlemsel (transactional) her entity'de bir ETag alanı (ör. `ChangedAt` zaman damgası) tanımlanır (§3.2).
- Statik model (property, tip, key, navigation) **SEGW ekranında** tanımlanır; koda taşınmaz. MPC_EXT yalnız
  ekranda yapılamayan dinamik değişiklik içindir.

---

## 3. MPC_EXT

### 3.1 `define` — super her zaman önce
```abap
METHOD define.
  super->define( ).                         " daima önce super

  DATA(lo_entity) = model->get_entity_type( 'MyEntity' ).
  IF lo_entity IS BOUND.
    " SEGW ekranında olmayan property (nadir — ekranı tercih et)
    lo_entity->add_property(
      iv_property_name = 'ComputedField'
      iv_abap_name     = 'COMPUTED_FIELD'
      iv_is_key        = abap_false
      iv_is_nullable   = abap_true
      iv_type          = 'Edm.String' ).
  ENDIF.
ENDMETHOD.
```

### 3.2 ETag
```abap
METHOD define.
  super->define( ).
  DATA(lo_entity) = model->get_entity_type( 'MyEntity' ).
  IF lo_entity IS BOUND.
    lo_entity->get_property( 'ChangedAt' )->set_as_etag( ).
  ENDIF.
ENDMETHOD.
```
- SEGW'de ilgili property'nin "Is ETag" işareti de açık olmalı.
- CDS tabanlı entity'de alan `@Semantics.systemDateTime.lastChangedAt: true` taşır.
- UPDATE'te framework `If-Match` başlığını kendisi karşılaştırır; uyuşmazlıkta `412 Precondition Failed` döner.
- İstemci (UI5 OData modeli) `If-Match`'i kendisi gönderir; DPC_EXT'te ayrıca karşılaştırma kodu yazılmaz.

### 3.3 CDS/SADL tabanlı entity'de filtrelenemeyen property
- **Belirti:** CDS/SADL ile üretilen entity type'ta property'ler SEGW'den `filterable` yapılamıyor; UI filtre
  çubuğunda alan görünmüyor.
- **ÇALIŞAN YÖNTEM:** MPC_EXT `define` içinde ilgili property'ye `set_filterable( iv_filterable = abap_true )`.
- (Kaynak projede ikinci çözüm olarak UI'daki akıllı filtre kontrolü kaldırılıp elle filtre kuruldu — UI kararıdır,
  bu skill'in kapsamı dışında.)
- `$metadata`'da `sap:filterable="false"` / `sap:sortable="false"` görünen alana UI sıralama/filtre bağlarsa
  servis 400 döner (`%sap-adt-foundation` → `references/foundation-query.md` §5.1).

---

## 4. Generate, servis kaydı, cache — kullanıcı adımları

### 4.1 Model değişikliği sonrası
1. SEGW'de değişikliği yap (entity/property/FI/complex type).
2. **Generate Runtime Objects.** Generate + aktivasyon yapılmadan `$metadata` güncellenmez.
3. `_EXT` sınıfında yeni metot gerekiyorsa model kaynağı yazar, CLI ile push/activate (`SKILL.md` §5).
4. `$metadata`'yı kullanıcı açar, ilgili bloğu paylaşır; tip-kapsamlı kontrol.

### 4.2 Servis kaydı (ilk kez)
```
1. /IWFND/MAINT_SERVICE → Add Service
2. System Alias: LOCAL (ya da projenin uzak sistem alias'ı — kullanıcıdan)
3. Technical Service Name: <SERVİS_ADI>
4. Service Version: 0001
5. ICF düğümü aktif olmalı: /sap/opu/odata/sap/<SERVİS_ADI>/
```
Paket ve transport kullanıcıdan gelir (kesin yasak C: model yaratmaz).

### 4.3 Cache ve yeniden kayıt — neyi ÇÖZMEZ
Aşağıdakiler ölçülmüş bir vakada (function import POST → 405) **sorunu çözmedi**; sebep dispatcher davranışıydı
(`references/deep-insert-function-import.md` §2):
- `/IWFND/MAINT_SERVICE`'te servisi silip yeniden ekleme
- `/IWBEP/R_MGW_CLEANUP_MD_CACHE` ile metadata cache temizleme
- SEGW'de HTTP method değiştirme

Cache temizliği genel olarak metadata tazeliği için kullanılır; ama bir hatayı "cache" diye teşhis etmeden önce
kontrol grubu kur (çalışan başka FI/entity set aynı serviste ne yapıyor).

### 4.4 Servis adı: teknik ad ↔ Z alias
Teknik servis (`API_…_SRV`) ile Gateway'de kayıtlı Z alias (`ZAPI_…_SRV`) ayrı objelerdir. Hangisinin aktif/yetkili
olduğu `/$metadata` yanıtıyla anlaşılır: **200** ↔ **403/404**. Ölçülen vakada teknik ad 200, Z alias 403 verdi.

---

## 5. Conversion exit'li alan OData'ya açılınca
- **Belirti:** CDS aktive olur ama metadata/servis yayını düşer:
  `Do not use conversion exit <EXIT> for property <FIELD>`. SADL/OData V2 property'de conversion exit'i reddeder.
- Sık alanlar: taşıma birimi numarası (HU), kur alanları (`EXCRT`), birim exit'li DTEL'ler.
- **ÇALIŞAN YÖNTEM:** CDS'te alanı düz tipe çevirerek aç: `cast( <alan> as abap.char( <uzunluk> ) )`;
  kur için `cast( <alan> as abap.dec( 9, 5 ) )`. Değer korunur, exit düşer. UNION'da iki dalda da aynı tipte cast.
- Ölçüm bağlamı: SADL/RAP yayınında görüldü; SEGW'de CDS'e referans veren entity için aynı davranış **DOĞRULANMADI**.
- Anahtar dolgusu (exit'in çıktıyı sıfırsız vermesi) için: `references/serialization.md` §3.

---

## 6. CDS `@OData.publish: true` sınırı
- Yalnız **salt-okur, basit** servis için uygundur.
- Yazma, function import ya da DPC_EXT override gerekiyorsa `@OData.publish` kullanılmaz; servis SEGW ile açılır
  (ya da profil izin veriyorsa RAP).
- CDS katmanlama ve yetki (DCL) notları: `references/backend-coding.md` §4.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynaktaki proje-özel servis/host/istemci adları → yer tutucu (`<SERVİS_ADI>`, `ZSD001_ODS_ORDER`).
- Fiori Launchpad katalog/tile/target mapping/PFCG adımları alınmadı: UI/launchpad yapılandırmasıdır (UI5 skill'i).
- "Response structure" ve rol metni (15+ yıl mimar) alınmadı; aXet çekirdeği §3-§4 ile karşılanıyor.
