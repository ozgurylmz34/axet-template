# RAP kontrol listeleri — yazmadan önce · yazarken · kapanış

> Kaynak: ekip RAP oluşturma inceleme listesi, RAP backend oluşturma listesi, RAP hata teşhisi listesi ve RAP standardı; aXet'e
> uyarlandı. Önem: **BLOCKER** = sağlanmadan yazma/ilerleme yok · **WARNING** = gerekçeyle geçilebilir, sessiz geçilmez.
> Ayrıntı için satırdaki referans dosyasına git.

## A. Yazmadan önce (kod yazmadan)

| Kontrol | Önem | Ref |
|---|---|---|
| Kapsam sınıfı (S0/S1/S2) yazılı; S2'de intake artefaktı mutabakatlı (`%sap-intake-triage`) | BLOCKER | SAP çekirdeği |
| Profil `ecc` değil; `s4_public`/`btp_abap`'ta klasik yol kullanılmıyor | BLOCKER | SKILL.md Profil |
| Paket ve transport kullanıcıdan; yeni transport/paket yok | BLOCKER | yasak C |
| Şekil seçimi gerekçeli: managed (yalnız Z tablo) / unmanaged (standart belge → released BO EML ya da BAPI) / davranışsız query | BLOCKER | layering §1 |
| Adlar: `_I_`/`_C_`/`_R_`/`_E_`; BDEF adı = root view adı; sınıf `ZCL_<gövde>_…`; SRVD `UI`/`API`; SRVB `_O2`/`_O4`; ≤ 30 karakter | BLOCKER | `%sap-dev` naming §4.2/§4.3 |
| Tüm `@EndUserText` / açıklamalar `master_language`'de, tam, spesifikasyondan | BLOCKER | yasak D |
| Tablo alan adları sistemden okundu (tahmin yok) | BLOCKER | layering §8 |
| Standart tablo okumasında released CDS successor'ı değerlendirildi; kullanılmıyorsa gerekçe kullanıcıya | WARNING | value-help §3 |
| Value-help envanteri çıkarıldı; her biri için ortak/yerel önerisi **kullanıcıya soruldu**; ortakta varsa yeniden yaratılmıyor | BLOCKER | value-help §1 |
| Muhatap alanları müşteri/satıcı diye sınıflandı; generic BP VH yok | BLOCKER | value-help §2 |
| Audit alanları tespit edildi; kural (create → hepsi, update → yalnız `updated_*`) kullanıcıya teyit ettirildi | BLOCKER | behavior-impl §5 |
| Kilit kararı yazılı: ETag / draft / uygulama-seviyesi | BLOCKER | draft-and-locks §1 |
| Numara kaynağı: NR objesi kullanıcıdan; `early numbering` planlandı; determination ile numara yok; `numbering : managed` yalnız UUID | BLOCKER | behavior-impl §3 |
| Aggregation gerekiyorsa ayrı yardımcı view + association (root'ta `group by` yok) | BLOCKER | layering §3 |
| İfadeler (`cast`/`coalesce`/`case`) interface'te, projection düz | BLOCKER | layering §3 |
| Mevcut çalışan bir RAP objesi okundu (BDEF + CCIMP `adt_grep_source`); "main boş" yanlış alarm değil | WARNING | behavior-impl §1 |
| Gereken her adım için CLI aracı var mı bakıldı; yoksa kullanıcıyla yol belirlendi (Eclipse ADT / bekle) | BLOCKER | SKILL.md §4 |
| Handler'dan commit gerektiren BAPI çağrılacaksa ayrı LUW deseni planlandı (yalnız `s4_private`) | BLOCKER | behavior-impl §10 |

## B. Yazarken

**View entity**
| Kontrol | Önem |
|---|---|
| `define [root] view entity`; `@AbapCatalog.sqlViewName` yok | BLOCKER |
| `@AccessControl.authorizationCheck` var | BLOCKER |
| Root interface root ise projection da `root` | BLOCKER |
| Composition ↔ `association to parent` çifti tutarlı (key yolu, on-koşulu); projection'da `redirected to composition child` / `redirected to parent` | BLOCKER |
| Salt-okunur consumption `as select from` (projection değil); interface join'inde `_C_` view yok — **yazma kapısı bunu kontrol etmez** | BLOCKER |
| Window fonksiyonu (`OVER PARTITION BY`) yok; CURR/QUAN referansları doğru; `@AbapCatalog.preserveKey` yok | BLOCKER / BLOCKER / WARNING |
| `@EndUserText.label` ≤ 40 | WARNING |
| Mevcut aktif root CDS yerinde push (sil-yeniden-yarat yok) | BLOCKER |

**Abstract entity**
| Kontrol | Önem |
|---|---|
| Üç adım: kabuk → kaynak ayrıca yazıldı → aktif kaynakta `abstract entity` + aktif sürüm + içerik eşitliği | BLOCKER |
| Parametre alan tipleri mevcut benzerinden; etiket `master_language` | BLOCKER |

**BDEF**
| Kontrol | Önem |
|---|---|
| Managed yazılabilir root: `lock master` + `etag master`; child `lock dependent` + `etag dependent` | BLOCKER |
| `authorization master ( global )` → CCIMP'te `get_global_authorizations` | BLOCKER |
| Child `define behavior` parent bloğunun dışında (kardeş) | BLOCKER |
| Composition child key `field ( readonly : update )`; hesaplanan alanlar `readonly` bildirilmemiş | BLOCKER / WARNING |
| `on save` tetikleyicisinde `update` varsa `create` de var | BLOCKER |
| EML yalnız Z tabloya (managed); tek MODIFY bloğu; `%cid` benzersiz; handler'da `COMMIT ENTITIES` yok | BLOCKER |
| Action adı `Lock`/`Unlock` değil | BLOCKER |
| BDEF kaynağında ters tırnak (U+0060) yok | BLOCKER |
| Façade'da `strict ( 2 )` yok | BLOCKER |
| Projection BDEF ayrı obje; `use` satırları base ile uyumlu | BLOCKER |

**Behavior implementation**
| Kontrol | Önem |
|---|---|
| BDEF'teki her determination/validation/action ↔ CCIMP `lhc_*` metodu | BLOCKER |
| `BY \_assoc` okumasında key olmayan alan tüketiliyorsa `ALL FIELDS WITH` / `FIELDS ( … ) WITH` | BLOCKER |
| Delete validation `READ ENTITIES` ile değil `keys` ile | BLOCKER |
| Audit determination idempotent guard'lı, `IN LOCAL MODE`, root + child | BLOCKER |
| Handler ve yardımcı sınıfta `COMMIT WORK`/`ROLLBACK WORK`/`BAPI_TRANSACTION_*`/`MESSAGE` yok | BLOCKER |
| Kaynakta kullanıcı adı/şifre yok | BLOCKER |
| Mesajlar ≤ 50 karakter, belge no önekten hemen sonra | BLOCKER |
| abaplint `parser_error` READ/MODIFY satırındaysa çalışan örnekle kıyaslandı | WARNING |
| ATC öncelik 1 temiz; susturma pragması yok | BLOCKER |

**Aktivasyon ve izolasyon**
| Kontrol | Önem |
|---|---|
| Sıra: interface CDS → projection CDS → BDEF → sınıf → SRVD → SRVB | BLOCKER |
| CDS değişti → üstündeki BDEF yeniden aktive edildi | BLOCKER |
| BDEF + sınıf tek istekte (`also`); döngüsel "CREATE not activated" → kademeli | BLOCKER |
| Önce saf CRUD uçtan uca yeşil; determination/validation tek tek eklendi | BLOCKER / WARNING |
| "HTTP 400 pre-audit" ilk seferde silme sebebi sayılmadı; gövde okundu, tek temiz deneme | WARNING |
| Guard reddi (çıkış 2) argüman değiştirerek aşılmadı | BLOCKER |

## C. Kapanış

| Kontrol | Önem |
|---|---|
| Her yeni obje: metadata `masterLanguage` = `master_language`, açıklama doğru | BLOCKER |
| `adt_inactive_objects` önce/sonra ölçüldü; bu işin bıraktığı inaktif yok (BDEF/SRVB dahil) | BLOCKER |
| Aktif kaynak içeriği push edilenle aynı (`readback_verified:true`; `null` ise elle) | BLOCKER |
| Yeni entity → SRVD `expose` + aktivasyon; yeni alan → SRVD değişmedi | BLOCKER |
| SRVB aktive → publish `published:true` | BLOCKER |
| `$metadata`'da yeni alan/entity/function import tip kapsamlı doğrulandı (kullanıcıdan) | BLOCKER |
| Uçtan uca: deep create 201 + numara + validasyon reddi (DEV, onaylı) | BLOCKER |
| Buffer başarısı değil kalıcılık geri okunarak doğrulandı | BLOCKER |
| Silme kontrolü varsa `delete-guard.md` §8 runtime seti | BLOCKER |
| `%code-review` yapıldı; `%verify-done` ile tam kapsam | BLOCKER |
| Denemelerden sonra çalışan yöntem `%remember` ile kaydedildi | WARNING |

## D. aXet yazma kapısı neye bakar, neye bakmaz

Yazma kapısı `adt_push_source`'ta tipe göre inceleme zinciri koşar (kod okuması: `sapadt/_reviewer.py` tip → görev eşlemesi ve
`sapadt/lib/validators/run_review.py` `TASK_VALIDATORS`; 2026-09-14 kod okuması, canlı ölçülmedi). Güncel liste için kodu oku,
bu tablo özet:

| Push tipi | Görev | Koşan kontroller (özet) | Koşmayan |
|---|---|---|---|
| `ddls` — klasik `define view` | `cds_update` | window fonksiyonu (BLOCKER), deprecated annotation (WARNING), para birimi referansı (BLOCKER), released successor (WARNING) | yapı alanı DTEL aktifliği, root/composition tutarlılığı, sqlViewName |
| `ddls` — `define view entity` / `as projection on` | `rap_cds_creation` | yukarıdakiler + RAP salt-okunur consumption (BLOCKER), yeniden kullanım (WARNING), standart tablo alanı (WARNING) | root/composition tutarlılığı, VH yerleşimi |
| `bdef` | `rap_bdef_creation` | managed ETag (BLOCKER), audit alanı determination (WARNING), ters tırnak (BLOCKER) | child kardeş kuralı, trigger `create;update;`, early numbering |
| `class`, `ccimp`, `ccau` | `class_push` | method parametresinde `TYPE c LENGTH n` (BLOCKER), decimal `WRITE TO` (WARNING), AMDP yorum tırnağı (BLOCKER), dokümantasyon satır genişliği (BLOCKER), released API (WARNING), abaplint (WARNING) | commit/MESSAGE yasağı, BY-assoc okuma |
| `srvd` | `rap_service_binding` | zincir boş → PASS | expose katmanı, VH yerleşimi |
| `srvb`, `prog`, `intf`, `func`, `fugr`, `ddlx`, `dcl` | yok | zincir yok | hepsi |

"PASS" ya da `SKIP` "doğru" demek değildir; kapsam dışı kalanlar bu listelerden elle yürünür. Bağımsız inceleme: `%sap-code-review`.
