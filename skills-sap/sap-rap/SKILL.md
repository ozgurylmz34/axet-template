---
name: sap-rap
description: >
  Use when building or changing an ABAP RAP stack on S/4HANA: CDS view entity layering for RAP,
  behavior definition (managed/unmanaged, lock and etag, early numbering with a number range /
  numara aralığı / NR object via SNRO, NROB, NRIV and NUMBER_GET_NEXT, determinations,
  validations, actions, dynamic instance feature control vs instance authorization), behavior
  pool and CCIMP handlers, EML against own or released business objects, service
  definition/binding and publish, draft or document lock, value-help placement, delete guards.
  Triggers: "RAP", "BDEF", "behavior", "CCIMP", "EML", "MODIFY ENTITIES", "service binding",
  "SRVB publish", "draft", "belge kilidi", "silme kontrolü", "numara aralığı", "belge numarası",
  "feature control". Do not use for plain CDS or
  DDIC work without behavior (use sap-cds-ddic), classic SEGW/DPC services or dialog programs,
  UI5 code, triaging a NEW request (use sap-intake-triage first) or ECC systems.
---

# SAP RAP — katmanlama, behavior, EML, servis, kilit

> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde her oturum yüklüdür; burada tekrarlanmaz, RAP'a özgü yüzeyi
> `references/layering-and-bdef.md` §8'dedir. Adlandırma: `%sap-dev` → `references/naming.md` §4.2/§4.3.
> ADT protokolü (okuma, push, aktivasyon, kilit, transport, 409, `master_language`): `%sap-adt-foundation`.
> RAP'a özgü olmayan CDS/DDIC ayrıntısı: `%sap-cds-ddic`. Bu skill yalnız RAP'a özgü olanı taşır.

## When to use this skill
- Yeni ya da değişen RAP objesi: interface/projection view entity, BDEF, behavior sınıfı/CCIMP, SRVD, SRVB.
- Behavior koduna dokunmak: numbering, determination, validation, action/function, EML, silme kontrolü.
- Servis yayınlamak ya da `$metadata`'da alanın/entity'nin görünmemesini teşhis etmek.
- Belge kilidi (ETag / draft / uygulama-seviyesi) ya da value-help yerleşimi kararı.
- **Kullanma:** yeni talebin ilk ele alınışı → `%sap-intake-triage`; davranışsız CDS/tablo → `%sap-cds-ddic`;
  UI5 ön yüz kodu (bu skill yalnız backend'dir); klasik SEGW/rapor.

## Profil
| `sap_profile` | Durum |
|---|---|
| `s4_private` | Aşağıdaki deneyimin tamamı burada ölçüldü (on-prem 2025). |
| `s4_public` · `btp_abap` | RAP ana modeldir; ama klasik yollar (RFC FM + `DESTINATION 'NONE'`, SM59, `ENQUEUE_READ`, user-exit, `NUMBER_GET_NEXT`, `SAVE_TEXT`, `_CLC` paketi) yoktur ya da released değildir → released karşılığını canlıda doğrula (**DOĞRULANMADI**). `btp_abap`'ta `adt_transport_list` yok. |
| `ecc` | RAP yok → DUR, kullanıcıya bildir (klasik track). |

## How to use this skill

### 1. Şekli seç (kod yazmadan)
Z tablo üzerinde yeni transactional belge → **managed**; standart belge (satış siparişi vb.) → **unmanaged façade** +
released BO EML / BAPI; liste/rapor/VH → **davranışsız query CDS**. Ayrıntı ve örnek BDEF'ler:
`references/layering-and-bdef.md`. Karar gerekçesini (clean core seviyesi) yaz.

### 2. Yazmadan önce
`references/checklists.md` §A'yı yürü. En az şunlar cevaplı olmalı:
1. Kapsam sınıfı (S0/S1/S2) yazılı mı; paket ve transport **kullanıcıdan** geldi mi.
2. Mevcut çalışan bir RAP objesi var mı → `adt_get` ile oku; behavior pool'un `source/main`'i **boştur**, handler'lar
   CCIMP'tedir (`references/behavior-impl.md` §1).
3. Okunacak standart tablo için released CDS successor'ı; value-help envanteri (ortak mı yerel mi → **kullanıcıya sor**);
   audit alanları (kural teyidi); kilit ihtiyacı (ETag / draft / uygulama-seviyesi); numara kaynağı (numara aralığı / NR
   objesi kullanıcıdan — `references/behavior-impl.md` §3).
4. Duruma bağlı kural var mı ("onaylanınca değiştirilemez", "yalnız taslakken silinir", "onaylıya kalem eklenmez") →
   backend'de **feature control** (`references/feature-control.md`); kim yapabilir sorusu ayrıca **authorization**. Yalnız UI'da
   gizlemek yetmez.
5. Tüm etiket/açıklamalar spesifikasyondan, `master_language`'de; tahmin yok.

### 3. Yazma sırası
Her adım `%sap-adt-foundation` akışıyla: güncel kaynağı `adt_get` ile çek → kapsam beyanıyla yaz → sistemden oku → inaktif
listesini ölç. Çağrı biçimi: `cli <tool> '{…}'` (yazmada `--sap-write --scope …`).

| # | Obje | CLI | Not |
|---|---|---|---|
| 1 | DDIC (domain → DTEL → tablo) | composite araçlar | `%sap-cds-ddic`; tablo öncesi alan+DTEL+anahtar onayı |
| 2 | Interface CDS → projection CDS | `adt_post_shell ddls` → `adt_get` → `adt_push_source ddls` → `adt_activate` | |
| 3 | BDEF (interface + projection) **ve** behavior sınıfı | sınıf: `adt_post_shell class` + `adt_push_source class`; BDEF: `adt_post_shell bdef` → `adt_get bdef` → `adt_push_source bdef`; CCIMP: `adt_get ccimp` → `adt_push_source ccimp` | aktivasyon **birlikte**: `adt_activate` + `also` (`bdef` push'u aktive etmez) |
| 4 | SRVD | `adt_post_shell srvd` → `adt_get` → `adt_push_source srvd` → `adt_activate` | |
| 5 | SRVB → aktivasyon → publish | SRVB yaratma ⚠ · `adt_activate srvb` · `adt_publish_service` | `references/service-publish.md` |

Aktivasyon zinciri: interface CDS → projection CDS → BDEF → behavior sınıfı → SRVD → SRVB → publish. CDS değişince üstündeki
BDEF yeniden aktivasyon ister. Bağımlı objeleri tek istekte aktive et:
`adt_activate '{"name":"ZSD001_I_ORDER","object_type":"ddls","also":[{"name":"ZSD001_I_ORDER","object_type":"bdef"},{"name":"ZCL_SD001_ORDER","object_type":"class"}]}'`
(kök CDS + BDEF + behavior sınıfı; `%sap-adt-foundation` → `tool-catalog.md` `adt_push_source` bdef satırı).

Yeni davranışı parça parça ekle: önce saf CRUD'u aktive et ve uçtan uca test et, sonra determination/validation'ları **tek tek**
(`references/behavior-impl.md` §6).

### 4. CLI kapsamı (⚠ işaretliler)
Kaynak: `--list` + `%sap-adt-foundation` → `references/tool-catalog.md` (2026-09-13). `ddls`/`srvd`/`bdef` kabuğu ve
`bdef`/`ccimp`/`ccau` okuma/push yolları çevrimdışı sahte istemciyle test edildi, canlı **DOĞRULANMADI**; diğer satırlar kod
okumasıdır. Bir yazma çağrısı `unsupported_type` dönerse **tekrar deneme, ham REST script'i yazma**: DUR, kullanıcıya bildir.

| İş | Durum |
|---|---|
| `adt_get`: `ddls`, `srvd`, `class` | var |
| `adt_get`: `bdef` | var (özel ham okuma yolu) |
| `adt_get`: sınıf alt-include'u `ccimp` / `ccau` (`name` = ana sınıf) | var — include ucunu okur, pull-before-edit kaydını yazar; include yoksa `include_absent_proven:true`. Metin araması için `adt_grep_source` |
| `adt_get`: `srvb` | yok |
| `adt_post_shell`: `class`, `interface`, `prog`, `include` | var (`extra` verme: `invalid_argument`) |
| Yeni kabuk: `ddls` (abstract entity dahil; yalnız metadata kabuğu), `srvd`, `bdef` (**ad = kök entity adı**) | var → `adt_get` → `adt_push_source` → `adt_activate` → readback. `ok:false` → retry etmeden `exists_after` |
| Yeni kabuk: `srvb`, `dcl`, `ddlx` | yok (`unsupported_type`; SRVB REST'te bloke, DCL/DDLX için canlı reçete yok). Kullanıcı Eclipse ADT'de açar (oturum dili = `master_language`) → `adt_get` ile doğrula |
| `adt_push_source`: `ddls`, `srvd`, `class` (mevcut objeye) | var |
| `adt_push_source`: `bdef` | var — LOCK → PUT → UNLOCK → readback, **aktive etmez** (`activated:false`) → `adt_activate` kök `ddls` + `also` [`bdef`, behavior sınıfı]; transport zorunlu |
| `adt_push_source`: `ccimp` / `ccau` | var — `name` = ana sınıf, önce aynı tiple `adt_get`; ana sınıfı aktive eder, BDEF inaktifse düşer (`push_failed` + `activation_note`; kaynak yüklenmiştir) → `also` ile birlikte aktive et; transport zorunlu. `ccdef`/`ccmac` → `unsupported_type` |
| `adt_activate` (`also` dahil): `ddls`, `bdef`, `class`, `srvd`, `srvb`, `dcl`, `ddlx` | var |
| SRVB | yalnız `adt_activate srvb` ve `adt_publish_service` (OData V2) var; SRVB yaratma, okuma ve V4 publish yok |
| `$metadata` okuma · OData uçtan uca POST testi | yok → kullanıcı (tarayıcı / Gateway istemcisi) |

Alt katmandaki `create_behavior_definition` fonksiyonu CLI aracı değildir ve kaynak ortamda 404 vermiştir → önerme, çağırma;
BDEF kabuğu `adt_post_shell bdef` ile açılır. Eksik adımda (SRVB/DCL/DDLX kabuğu, `$metadata`) seçenek sun: (a) kullanıcı ADT'de
yapar, sen `adt_get` ile doğrular ve zinciri CLI ile sürdürürsün; (b) CLI'ye araç eklenmesi beklenir.

### 5. Sistemden doğrula
- Her yaratmadan sonra metadata'dan `masterLanguage` ve açıklama; her push'tan sonra `readback_verified`.
- `adtcore:version="active"` boş kabukta da "active" der → kanıt değildir. Kanıt: `adt_inactive_objects` + aktif kaynak içeriği.
- BDEF ↔ CCIMP eşlemesi: BDEF'teki her `determination/validation/action` için CCIMP'te `lhc_*` metodu (`adt_grep_source`).
- Servis: publish `published:true` + kullanıcıdan `$metadata`'da ilgili `EntityType`/`FunctionImport` bloğu.
- Buffer başarısı (`FAILED` boş, `sy-subrc = 0`, HTTP 200) kalıcılık değildir → geri okuyarak doğrula.

### 6. İnaktif obje ölçümü
İşten önce ve sonra `adt_inactive_objects` sayısı. Kök CDS'e alan eklemek bağlı BDEF'i (ve SRVB'yi) **sessizce inaktif**
bırakır; CDS aktivasyonu onları birlikte aktive etmez. Başka birinin WIP'i olabilecek inaktifleri kendiliğinden aktive
etme/atma — raporla.

### 7. Hata olursa
`references/troubleshoot.md` (aktivasyon mesajı · runtime dump · araç belirtisi indeksi). Genel teşhis dersleri ve
412/423/409: `%sap-adt-foundation` → `references/known-errors-adt.md`.

## Referanslar
| Dosya | İçerik |
|---|---|
| `references/layering-and-bdef.md` | Şekil seçimi, katmanlar, RAP view entity kuralları, read-only consumption, abstract entity, BDEF kuralları ve örnekleri, aktivasyon sırası, kesin yasakların RAP yüzeyi |
| `references/behavior-impl.md` | Behavior pool/CCIMP, handler imzaları, early numbering, determination/validation, audit alanları, BY-association okuma tuzağı, yasak deyimler (COMMIT/MESSAGE), commit gerektiren BAPI, handler'dan OData çağrısı, BOTD unit test, ATC |
| `references/eml.md` | Released BO (I_SalesOrderTP) create/update, muhatap, `editableFieldFor`, late numbering, "kaydetme başarısız" teşhisi, action içi yan etki, metin kalıcılığı, classrun teşhisi |
| `references/service-publish.md` | SRVD, SRVB, aktivasyon → publish sırası, `$metadata` doğrulama, değişiklik türüne göre adımlar, salt-okunur rapor servisi |
| `references/draft-and-locks.md` | ETag / draft / uygulama-seviyesi kilit kararı, kilit reçetesi, `ENQUEUE_READ` |
| `references/value-help.md` | Ortak ya da yerel VH, muhatap (müşteri/satıcı) kuralı, released CDS tercihi |
| `references/delete-guard.md` | Silme kontrolünün katmanları, delete validation tuzakları, 50 karakter mesaj sınırı, runtime kabul |
| `references/feature-control.md` | Duruma bağlı düzenlenebilirlik: dynamic instance feature control (update/delete/action/alan/kalem ekleme), `get_instance_features` sonucu, feature control ↔ authorization ayrımı, OData V2 / freestyle UI'a yansıması |
| `references/checklists.md` | Yazmadan önce · yazarken · kapanış kontrol listeleri; yazma kapısının neye bakıp neye bakmadığı |
| `references/troubleshoot.md` | Belirti → kök neden → çözüm indeksi |

## Rules
- Tahmin yok: annotation, BDEF sözdizimi, alan adı ve handler imzası çalışan bir artefakttan (sistemdeki Z RAP objesi, bu
  referanslar) doğrulanır; released BO'da alan yazılamıyorsa önce projeksiyon CDS kaynağını oku.
- Transport, paket, NR objesi (ve aralık numarası), SM59 destination **kullanıcıdan** gelir; sen yaratmazsın/önermezsin.
  Yeni Z DDIC objesi (domain, DTEL, tablo …) ve NR objesi için **ad önerebilirsin**: adlandırma standardına uygun, canlıda
  kontrol edilmiş (varsa başka ad), tablo hâlinde sunulmuş ve kullanıcı açıkça onaylamış olmalı (`%sap-dev` §6). Standart
  objeye append alanının adını önermezsin (kesin yasak A).
- Standart tabloya `MODIFY ENTITIES`/SQL yazma yok; standart belge released BO EML ya da BAPI ile. Standart objeye
  `extension`/append yok.
- Behavior handler içinde `COMMIT ENTITIES`, `COMMIT WORK`, `ROLLBACK WORK`, `BAPI_TRANSACTION_COMMIT` ve `MESSAGE` yok
  (handler'ın çağırdığı yardımcı sınıf dahil). Statik kontroller bunu görmez; ilk runtime testinde dump olur.
- Yazma kapısı reddederse (çıkış 2) argümanı eğip bükme, `skip_reviewer` verme; kaynağı düzelt ya da DUR.
- Kalıcı değişiklik bitince `%sap-code-review`; "tamam" demeden `%verify-done` (runtime/e2e kanıtı dahil). Denemelerden sonra
  çalışan bir RAP yöntemi bulduysan `%remember`.
- Alt ajana RAP araştırması devredersen brifinge kesin yasakları, "yazma sınıfı araç çağırma" kuralını ve
  "behavior pool main boştur, CCIMP'e bak" uyarısını metin olarak yaz.
