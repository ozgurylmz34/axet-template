# RAP hata teşhisi — belirti → kök neden → çözüm

> Kaynak: ekip RAP playbook'u, RAP backend tecrübe bankası, RAP hata teşhisi kontrol listesi, EML nasıl-yapılır dokümanı, silme
> kontrolü dokümanı ve ekip hafıza dersleri; aXet'e uyarlandı. ADT protokol hataları (412/423/409, kilit, `master_language`,
> classrun bayatlığı): `%sap-adt-foundation` → `known-errors-adt.md`.
> **Kullanım:** mesajı ya da belirtiyi ara → satırı uygula → kör retry yapma. Tanıdık semptomda önce `%recall`.

## 1. Aktivasyon mesajları

| Belirti | Kök neden | Çözüm | Ref |
|---|---|---|---|
| `ROOT keyword missing since <I_view> has the root property` | Root interface'in projection'ı `root` değil | `define root view entity … as projection on` | layering §3 |
| `ROOT keyword not valid` | Projection root, interface root değil | Interface'i de `define root view entity` | layering §3 |
| `Transactional Provider Contract expected` (uyarı) | Projection'ın BDEF'i henüz yok | Transactional ise BDEF ekle; salt-okunursa `as select from` | layering §3–4 |
| `Projection Views are not allowed as base object for this entity type` | Interface join'inde `_C_` view | `_I_` view'a geç; ad alanlarını text/VH view join'iyle çöz | layering §4 |
| `Transactional Projection View must be part of a business object` | BDEF'siz `as projection on` | `define view entity … as select from` | layering §4 |
| `Field X contains a not supported expression` | Projection'da `cast`/`coalesce`/`case` | İfadeyi interface'e taşı | layering §3 |
| `Elements with required UNIT-reference are not supported` | `@Semantics.quantity` alanı aritmetikte | `cast( … as abap.dec(n,m) )` | value-help §3 |
| `reference information missing or data type wrong` (abstract entity) | Miktar/tutar tipi referanssız | Düz `abap.dec(13,3)` / `abap.dec(15,2)` | layering §5 |
| `SDDL_PARSER_MSG 013` (abstract entity, yaratma 201 dönmüştü) | Kaynak boş kaldı | Kaynağı ayrıca yaz, aktive et, içerik doğrula | layering §5 |
| `BEHAVIOR cannot be implemented` / `… in class` | BDEF ve sınıf ayrı ayrı aktive edilmeye çalışıldı | `adt_activate` + `also` (BDEF + sınıf) | layering §7 |
| `The operation "CREATE" is not activated for entity` (CCIMP satırını gösterir) | BDEF'te `early numbering` yok ya da döngüsel sıra | `early numbering` ekle; önce BDEF'ler, sonra sınıfla birlikte | layering §7 |
| `"behavior" is not expected here` + `"define|foreign|scalar" was expected` | Child `define behavior` parent bloğunun içinde | Kapanıştan sonra kardeş blok | layering §6 |
| `The trigger update is only allowed in combination with create here` | `on save { update; }` | `{ create; update; }` | layering §6 |
| `every entity must be lock master/dependent` | Façade'da `strict ( 2 )` | `strict`'i kaldır | layering §6.3 |
| `not an entity with authorization check` | `authorization master ( global )` yok | Ekle + `get_global_authorizations` | layering §6 |
| "key field … should be flagged readonly" (uyarı) | Child key kısıtsız | `field ( readonly : update )` | layering §6 |
| `PARTNERFUNCTION not a valid field` | Key alanı `FIELDS ( … )` içinde | `…ForEdit` alanını kullan | eml §5 |
| `WITH expected after )` | `FIELDS ( … ) FROM …` | `FROM` → `WITH` (FIELDS'i silme) | behavior-impl §8 |
| `class does not contain interface` (`io_msg->if_abap_behv_message~m_severity`) | Yanlış erişim | `io_msg->m_severity` | eml §9 |
| "Inconsistent in active version" zinciri | Bağımlı obje bozuk inaktif | Bağımlıyı temiz kaynakla push, birlikte aktive | layering §7 |
| Toplu aktivasyon "cancelled" | Setteki tek hata | Hatasız alt küme önce | layering §7 |
| Aktivasyon HTTP 200 ama `activationExecuted="false"` / `type="E"` | Sahte başarı | Mesajları oku; `adt_inactive_objects` | layering §7 |
| Aktivasyon `DOĞRULANAMADI` / `dogrulanamadi:true` | Gövde hüküm taşımıyordu (yalnız generation ya da bayraksız) ve worklist sondası ölçemedi | Başarı sayma; `adt_inactive_objects` ile ölç, gerekirse yeniden aktive et | layering §7 |
| VH view "HTTP 400 pre-audit" | Ortamsal olabilir | Gövdeyi oku, tek temiz deneme; hemen silme | value-help §4 |
| abaplint `parser_error` READ/MODIFY satırında | Gerçek sözdizimi hatası olabilir | Çalışan CCIMP ile kıyasla | behavior-impl §9 |
| BDEF aktive olmuyor (genel) | View entity inaktif / composition–parent çifti eksik / mapping uyumsuz | Alt view'ları aktive et; `composition` ↔ `association to parent` tam mı | layering §3 |

## 2. Runtime dump ve yanlış davranış

| Belirti | Kök neden | Çözüm | Ref |
|---|---|---|---|
| `BEHAVIOR_CONTRACT_VIOLATION CC/C:EMPTY_UPDATE` | Determination key alanını UPDATE etti | Numara early numbering handler'ında | behavior-impl §3 |
| `RAISE_SHORTDUMP` / `LCX_ABAP_BEHV_DETVAL_ERROR` (jenerik) | Bir det/val handler'ı patladı | Saf CRUD'a indir, tek tek geri ekle | behavior-impl §6 |
| `… Infinite loop caused by cyclical triggering of on-save determinations` | Guard'sız self-MODIFY determination | Idempotent `mt_done` guard | behavior-impl §5 |
| `BEHAVIOR_ILLEGAL_STATEMENT` (500, handler'da `COMMIT ENTITIES`) | Handler'da commit | Commit etme; framework commit eder | behavior-impl §10 |
| `BEHAVIOR_ILLEGAL_STATEMENT` (SAPLBAPT; UI'da yalnız "HTTP request failed") | Handler/yardımcı sınıfta `COMMIT WORK`/`BAPI_TRANSACTION_*` | Z RFC FM + `DESTINATION 'NONE'` | behavior-impl §10 |
| `BEHAVIOR_ILLEGAL_STATEMENT … MESSAGE_E is not allowed` (`CL_HTTP_CLIENT`) | HTTP iletişim hatasında içeride MESSAGE | Gateway iç proxy; bağlantıyı classrun ile doğrula | behavior-impl §11 |
| `BEHAVIOR_READONLY_FIELD` "Field PARTNERFUNCTION is read-only" | Standart muhatap elle ekleniyor | Muhatap otomatik; mevcut belgeye eklemede `…ForEdit` | eml §4–5 |
| `VPD 030` "Muhatap rolünü girin" / muhatap fonksiyonu boş | Key yok sayıldı | `PartnerFunctionForEdit`; müşteri no ALPHA dolgulu | eml §5 |
| `NOT_FOUND` muhatap update | Olmayan kaydı UPDATE | Önce mevcutları oku, CREATE/UPDATE/DELETE yönlendir | eml §5 |
| COMMIT'te "Kaydetme başarısız oldu" | Birim / fiyat / satış alanı verisi | Veri teşhis sırası + girdi doğrulaması | eml §6 |
| KDV = 0 | Müşteri vergi sınıflandırması | Önce ana veri; çalışan belgeyle kıyas | eml §6 |
| Validation dolu veride yanlış hata veriyor ya da hiç koşmuyor | `BY \_assoc FROM` yalnız key döndürdü | `ALL FIELDS WITH` | behavior-impl §8 |
| Delete validation hiç tetiklenmiyor, silme hep geçiyor | `READ ENTITIES` boş döndü | `keys` üzerinde çalış | delete-guard §7 |
| Alan payload'da yokken de validation tetikleniyor | `field` listesi tetikleyiciyi daraltmaz | Muafiyet handler'da | layering §6 |
| Action/handler dump (genel) | FAILED/REPORTED işlenmemiş; `%cid` boş; mapping eksik | FAILED/REPORTED oku; `%cid`/`%key`; `mapping for` | eml §0 |
| Action sonucu boş (`Success:false`, alanlar boş) | Sonuçta `%cid` yok | `%cid = keys-%cid` | behavior-impl §2 |
| Action'dan yaratılan belge numarası boş | Released BO late numbering | Tüketici yeniden sorgular | eml §2 |
| Not/metin kaydedildi görünüyor ama işlemde yok | Controlled commit metni yazmadı | `SAVE_TEXT savemode_direct = 'X'` | eml §8 |
| Save'de veri yazılmıyor | managed'de elle yazma / unmanaged'de saver boş | managed: framework yazar; unmanaged: saver | layering §6 |
| ETag/kilit hatası (managed) | `lock master`/`etag master` eksik | BDEF'e ekle | draft-and-locks §2 |
| Draft tutarsızlığı | Draft tablosu/`Prepare` eksik | Draft tablosu + draft action'ları (**DOĞRULANMADI**) | draft-and-locks §3 |
| Mesaj kullanıcıda kesik | 50 karakter sınırı | Belge no öneğin ardına, `+N` | delete-guard §6 |
| `CALL_FUNCTION_NOT_REMOTE` | FM Remote-Enabled değil | Kullanıcı SE37'de işaretler | behavior-impl §10 |
| `FUNC_ADT 015 … declares no type` / `Type <X> is not a table type` | FM `TABLES` parametresi | DDIC tablo tipi + `TYPE` | behavior-impl §10 |
| HTTP `Unit … is not created in language EN` | URL'de `sap-language` yok | `&sap-language=<master_language>` | behavior-impl §11 |
| `403 /IWFND/MED/170 service 'sap' not found` | SM59 Path Prefix dolu | Prefix boş, kod tam yol | behavior-impl §11 |
| `Client connection to http://…:443xx broken` / sonra 401 | SSL kapalı / logon kimliksiz | Kullanıcı SM59'u düzeltir | behavior-impl §11 |
| Liste yavaş | Eager join, gereksiz expose | Association (join-on-demand); expose'u daralt | layering §3 |

## 3. Servis ve `$metadata`

| Belirti | Kök neden | Çözüm | Ref |
|---|---|---|---|
| Publish: `Service Binding … does not exist` | SRVB inaktif | `adt_activate srvb` → publish | service-publish §3 |
| Publish ERROR `Do not use conversion exit EXCRT for property …` | Kur alanı dönüşüm çıkışı | `cast( … as abap.dec(9,5) )` | service-publish §7 |
| `$metadata` 404/boş | SRVB aktive/publish edilmedi | aktivasyon + publish | service-publish §3 |
| Yeni alan `$metadata`'da yok | Yeniden publish yok / BDEF-SRVB inaktif | `adt_inactive_objects` → aktivasyon → publish | service-publish §5 |
| Function import `400 … Expected Edm.String` | String parametre tırnaksız | `'…'` | service-publish §6 |
| Navigation `_Item` bulunamıyor (V2) | V2'de ad `to_Item` | `to_<Association>` | service-publish §6 |
| SRVB açıklama değişikliği `423 Locked` | REST ile SRVB düzenleme | Yaratmada doğru ver; sonradan Eclipse ADT | service-publish §2 |

## 4. Araç belirtileri (aXet CLI)

| Belirti | Anlamı | Yapılacak |
|---|---|---|
| `adt_post_shell` `srvb` → `unsupported_type` (çıkış 3) | Bu tipte kabuk yolu yok (REST'te bloke; `tool-catalog.md`). `ddlx`/`dcls` v0.5.2'den beri var | Retry yok; kullanıcı SRVB'yi ADT'de açar (SKILL.md §4) |
| `adt_post_shell` `ddls`/`srvd`/`bdef` → `ok:false` | Yaratma düştü ya da ölçülemedi (`create_not_persisted` = 2xx ama obje yok) | Retry etmeden `exists_after`'a bak (`true`: tekrar yaratma) |
| `adt_post_shell` class/interface/program/include'a `extra` → `invalid_argument` | `extra` yalnız `func`/`enqu`/`ttyp`'te geçerli | `extra`'yı kaldır |
| `adt_push_source bdef` → `activated:false` | Beklenen: `bdef` push'u aktive etmez | `adt_activate` kök `ddls` + `also` [`bdef`, behavior sınıfı] |
| `adt_push_source ccimp` → `push_failed` + `activation_note` | Ana sınıf aktivasyonu inaktif BDEF yüzünden düştü; kaynak yüklenmiş olabilir | `adt_get ccimp` ile kaynağı oku; BDEF + sınıfı `also` ile birlikte aktive et |
| `adt_get` behavior sınıfı → kaynak çok kısa | `source/main` boş (normal) | CCIMP için `adt_get` `{"name":"<sınıf>","object_type":"ccimp"}` ya da `adt_grep_source` |
| `adt_grep_source` `class_includes_not_scanned` | CCIMP okunamadı | "yok" deme; tekrar ölç ya da kullanıcıdan |
| Yeni DDLS'e ilk push `423 InvalidLockHandle` + "SAP did not return CORRNR", her çağrıda aynı handle | Önceki araç setinde kalıcı kilit handle önbelleği (deterministik); aXet CLI'de **DOĞRULANMADI** | Retry = patinaj. `%sap-adt-foundation` K-02/K-03 merdiveni; sürerse DUR |
| `reviewer_blocker` | Yazma kapısı incelemesi BLOCKER | Kaynağı düzelt; `skip_reviewer` aXet'te reddedilir |
| İnceleme zaman aşımı ("BLOCKER, 0 bulgu, reviewer_timeout") | Önceki araç setinde kök nedeni giderilmiş bir hataydı | Görülürse yeni sorun: DUR, kullanıcıya bildir; atlatma yok |
| `adt_publish_service` `published:null` | Gövde hüküm taşımıyor | ÖLÇÜLEMEDİ; `$metadata`'yı kullanıcıdan iste |
| `activation_verified:null` | Aktivasyon kanıtlanmadı | `adt_inactive_objects` ile elle ölç |

## 5. Teşhis sırası (ortak çekirdek)

1. Hata gövdesini ve mesaj kimliğini oku (`[VPD 030]` gibi); jenerik metinle hipotez kurma.
2. Bu dosya + `%sap-adt-foundation` known-errors + `%recall`.
3. Kontrol grubu: aynı işi yapan **çalışan** belge/obje ile kıyasla ("aynı kodla eski belge çalışıyorsa kod suçsuzdur").
4. Released BO'da alan davranışı tuhafsa önce projeksiyon CDS kaynağını oku.
5. Pahalı bir çare (yeniden yaratma, BAPI'ye geçiş, yaklaşım değiştirme) ilk denemede tutmadıysa tekrarlama; dayandığı teşhisi
   sorgula.
6. Buffer başarısını kalıcılık sanma; geri oku.
