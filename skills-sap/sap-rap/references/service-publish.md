# Service definition, service binding ve publish

> Kaynak: ekip RAP playbook'unun SRVD/SRVB/publish bölümleri (kanıtlanan sıra, denenen-başarısız yollar), RAP backend tecrübe
> bankasının servis ve salt-okunur rapor bölümleri, RAP standardı §7 ve RAP oluşturma kontrol listesi; aXet CLI'ye uyarlandı.
> Deneyim `s4_private`'ta ölçüldü. `$metadata` doğrulama yöntemi: `%sap-adt-foundation` → `foundation-query.md` §5.

## 1. Service definition (SRVD)

```
@EndUserText.label: '<master_language metni, spesifikasyondan>'
define service ZSD001_UI_ORDER {
  expose ZSD001_C_ORDER;
  expose ZSD001_C_ORDERITEM;
  expose <ORTAK_PKG>_I_CUSTOMER_VH;     // ortak value-help (value-help.md)
}
```
- `UI` (Fiori/SADL UI) ya da `API` (entegrasyon). Yalnız projection ve salt-okunur query CDS expose edilir.
- SRVD, DDLS ailesinden kaynak tabanlı objedir: kabuk → kaynak → aktivasyon (ADT tipi `SRVD/SRV`).
- aXet yazma kapısında SRVD için içerik kontrolü yok denecek kadar azdır; "PASS" = "kontrol edildi" değildir (`checklists.md` §D).

## 2. Service binding (SRVB)

- Ad: `ZSD001_UI_ORDER_O2` (V2) / `_O4` (V4). Sürüm soneki zorunlu.
- Birincil tip OData V2 - UI. Kaynak standart V4 binding'i "yarat+publish, kullanma" gelecek kapısı olarak önerir; aXet CLI'de V4
  publish aracı yok → V4 isteniyorsa kullanıcıya bildir.
- Açıklama (description) **yaratma anında doğru** verilir. Mevcut SRVB açıklamasını REST ile değiştirmek ölçüldü: GET 200 →
  LOCK 200 → PUT **423 Locked** (geçerli kilit + transport + ETag ile bile). Sonradan düzeltme kullanıcının Eclipse ADT'sinde.

## 3. Kanıtlanan sıra

1. SRVD kabuk → kaynak → aktivasyon.
2. SRVB yarat (V2, SRVD referanslı). Yaratma yanıtı `bindingCreated="false"` / `version="inactive"` döner.
3. **SRVB'yi aktive et** — zorunlu ara adım.
4. Publish (OData V2 publish job) → gövdede `SEVERITY=OK` ("activated locally").
5. `$metadata` = 200 ve beklenen entity/alan/function import var.

**DENENEN — BAŞARISIZ:** SRVB yaratıp doğrudan publish → `Service Binding … does not exist` (sürüm 0001). Mesaj yanıltıcıdır;
gerçek sebep inaktif binding. Statik inceleme bunu yakalayamaz (canlı durum) → sıra kuralı.
Tarihsel: SRVB yaratma bir dönem `400 Session Timed Out` verdi (içerik tipi ve stateful başlık düzeltilince bile); sonra
geçerli gövdeyle 201 ölçüldü. RAP Generator REST'i ölçülen on-prem sistemde kullanılamadı (üreteç listesi boştu).

## 4. aXet CLI eşlemesi

| Adım | CLI | Not |
|---|---|---|
| SRVD kabuğu | `cli adt_post_shell '{"object_type":"srvd","name":"ZSD001_UI_ORDER","package":"<PAKET>","transport":"<TRANSPORT>","description":"<metin>"}'` (`srvdSourceType="S"`; çevrimdışı test edildi, canlı **DOĞRULANMADI**) | `ok:false` → retry etmeden `exists_after`; sonra `adt_get srvd` (pull kaydı). Araç canlıda düşerse kullanıcı Eclipse ADT'de açar |
| SRVD kaynak + aktivasyon | `adt_get srvd` → `adt_push_source srvd` → `adt_activate srvd` | |
| SRVB yaratma | **araç yok** (`adt_post_shell srvb` → `unsupported_type`; REST yaratma yolu bloke — §3 tarihçesi) | kullanıcı Eclipse ADT'de (açıklama `master_language`'de, tam) |
| SRVB aktivasyon | `cli adt_activate '{"name":"ZSD001_UI_ORDER_O2","object_type":"srvb"}'` | aktivasyon yanıtı kanonik hükümle okunur (`activationExecuted="true"` + E/A yok); gövde hüküm taşımıyorsa worklist sondası karar verir (layering §7) |
| Publish (V2) | `cli adt_publish_service '{"name":"ZSD001_UI_ORDER_O2","version":"0001"}'` | hüküm gövdedeki `SEVERITY`'den: `published` `true` / `false` / `null` (= ÖLÇÜLEMEDİ, `ok` yine false) |
| `$metadata` okuma | **araç yok** | kullanıcı `/sap/opu/odata/sap/<SRVB>/$metadata`'yı tarayıcıda açıp ilgili `EntityType` bloğunu paylaşır; kimlik bilgili script yazılmaz |
| SRVB okuma | yok — SRVB CLI tip tablosunda yok (kod okuması); SRVB için yalnız `adt_activate srvb` ve `adt_publish_service` | durum için `adt_inactive_objects` + publish sonucu |

## 5. Değişiklik türüne göre ne yapılır

| Değişiklik | Adım |
|---|---|
| Expose edilmiş entity'ye yeni alan | SRVD **değişmez**; alt CDS aktive → servis yeniden publish → `$metadata`'da alan var mı |
| Yeni entity (ör. yeni value-help view) | SRVD'ye `expose` ekle → SRVD aktive → yeniden publish → `$metadata` |
| BDEF'e operasyon (action/function) | base + projection BDEF + CCIMP → birlikte aktivasyon → yeniden publish → `$metadata`'da `FunctionImport` |
| Kök CDS'e alan | BDEF ve SRVB sessizce inaktif kalabilir → `adt_inactive_objects` → gerekiyorsa `adt_activate` (`also`) → publish |

UI testine göndermeden önce `$metadata` deterministik kontrolü yapılır.

## 6. Doğrulama ve uçtan uca test

- `$metadata` alan doğrulaması **tip kapsamlı**: önce `<EntityType Name="…">` bloğunu ayır, alanı yalnız orada ara; `Type`,
  `MaxLength`, `sap:sortable`, `sap:filterable` değerlerini oku (`foundation-query.md` §5.1). `xml:lang` = `master_language`.
- V2'de navigation property adı `to_<Association>` (SADL öneki), `_<Association>` değil.
- V2 function import string parametresi **tek tırnaklı**: `GetBalance?IvCustomer='0000300000'&IvCompany=''`. Tırnaksız →
  `400 Invalid function import parameter type … Expected Edm.String`.
- Uçtan uca kanıt (kaynakta kullanıcı/araç ile yapıldı): deep create JSON POST
  `{ …başlık…, "to_Item": { "results": [ { …kalem… } ] } }` → 201 + numara atandı + validasyon çalıştı (geçersiz girişte 400 +
  mesaj). CSRF servisin kendi GET'inden. Bu test **veri yazar** → yalnız DEV, onayla; aXet'te bunun için araç yok, kullanıcı
  Gateway istemcisi ya da tarayıcı eklentisiyle koşar.
- Publish ≠ Fiori launchpad/IAM yayını. Katalog/rol (IAM/BC/BR) ayrı iştir.
- Publish başarısızsa DUR ve kullanıcıya raporla; zinciri "yayında" sayma.

## 7. Salt-okunur rapor servisi (behavior'suz) — ÇALIŞAN

1. Sarmalayıcı view entity + DCL (`layering-and-bdef.md` §4).
2. SRVD `ZSD001_UI_<X>`: sarmalayıcı + ortak value-help'ler.
3. SRVB `_O2` → aktivasyon → publish.

Tuzaklar:
- Kur alanında `EXCRT` dönüşüm çıkışı (kursk/kurrf tipi) → publish **ERROR** `Do not use conversion exit EXCRT for property …`.
  Çözüm: sarmalayıcıda `cast( <alan> as abap.dec(9,5) )` ("CAST DEC to identical type" uyarısı gelse de çıkış düşer).
- `@EndUserText.label` ≤ 40 karakter.
- DCL kabuğu: aXet CLI'de yok — `adt_post_shell dcl` → `unsupported_type` (canlı reçete yok; `%sap-adt-foundation` → `tool-catalog.md`).
  Kullanıcı Eclipse ADT'de açar. Kaynakta eski DCL yaratma aracı kaynak yüklemesindeki hatayı yutuyordu → kabuktan sonra kaynağı
  ayrıca yaz ve aktif kaynağı oku.
- Read-only projection'da "Transactional Provider Contract expected" uyarısı; `as projection on` yerine `as select from` (§4).

## 8. Profil notu

- `s4_private`: yukarıdakiler ölçüldü.
- `s4_public` / `btp_abap`: servis yayını iletişim senaryosu/katalog modeline bağlıdır; bu reçete orada **DOĞRULANMADI**.
  `btp_abap`'ta transport gCTS'tir, `adt_transport_list` yoktur.
