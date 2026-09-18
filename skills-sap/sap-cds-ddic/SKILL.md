---
name: sap-cds-ddic
description: >
  Use when designing, creating, changing or verifying SAP CDS views (DDLS: classic define view,
  view entity, abstract entity) or data dictionary objects: domain, data element, structure,
  table type, Z transparent table, lock object (ENQU) and message class (MSAG); also when reading
  packing instructions through released CDS. Carries measured working methods, failed paths and
  pre-write checklists for these object types, mapped to the aXet SAP CLI.
  Triggers: "CDS yarat", "CDS view", "view entity", "sqlViewName", "domain yarat", "DTEL",
  "data element", "struct yarat", "tablo yarat", "tabloya alan ekle", "table type",
  "lock object", "kilit objesi", "ENQUEUE", "mesaj sınıfı", "MSAG", "ambalajlama talimatı".
  Do not use for triaging a NEW request (use sap-intake-triage first), for generic ADT
  read/push/activate/lock/transport questions (use sap-adt-foundation), for RAP behavior
  definitions or service bindings, or for non-SAP code.
---

# SAP CDS ve veri sözlüğü (DDIC) objeleri

> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde (`00-sap.md`) her oturum yüklüdür; burada tekrarlanmaz.
> Adlandırma: `%sap-dev` → `references/naming.md` §4.3 (CDS) · §4.7 (veri sözlüğü) · §5 (alan tipleme sırası).
> ADT protokolü (pull-before-edit, yazma kapısı ve kapsam beyanı, 409, `master_language`, aktivasyon
> doğrulaması, kilit, transport): `%sap-adt-foundation` → `references/foundation-ops.md` · `known-errors-adt.md`.
> Bu skill yalnız bu obje tiplerine özgü **yöntemi, tuzakları ve kontrol listelerini** taşır.

## When to use this skill
- CDS view (classic `define view`, `define view entity`, `define abstract entity`) yazarken ya da değiştirirken.
- Domain, data element, structure, table type, Z tablo, lock object, mesaj sınıfı yaratırken/değiştirirken.
- Bu objelerde "aktive oldu ama boş / alan gelmedi / 0 satır" gibi bir belirtiyi teşhis ederken.
- Ambalajlama talimatını (kasa + kasa-içi adet) okuyan bir geliştirmede.
- **Kullanma:** yeni talebin ilk ele alınışı → `%sap-intake-triage`; tek başına okuma/push/aktivasyon/kilit
  sorusu → `%sap-adt-foundation`; behavior definition, service definition/binding → bu skill değil.

## CLI araç durumu — bu obje tipleri için
Kaynak: `sap_adt_cli.py --list` + `%sap-adt-foundation` → `references/tool-catalog.md`. `--list` otoritedir (araç sayısı değişir).
`ttyp`/`ddls`/`enqu`/`msag` kabuk yolları, `adt_activate` `enqu`, `adt_msgclass_write` ve `adt_domain_create` ön kontrolü 2026-09-13'te eklendi: **çevrimdışı test edildi, canlı DOĞRULANMADI**
→ her adımda readback atlanmaz.

| Obje | Yaratma | Değiştirme | Okuma / doğrulama |
|---|---|---|---|
| Domain | `adt_domain_create` | **araç yok** (sabit değer ekleme = güncelleme) | `adt_get` `doma` |
| Data element | `adt_dtel_create` | **araç yok** (domain bağı değiştirme) | `adt_get` `dtel` |
| Structure | `adt_struct_create` → gerekirse `adt_push_source` `structure` | `adt_push_source` `structure` | `adt_get` `structure` + `DD03L` alan sayısı |
| Table type | `adt_post_shell` `ttyp` (`extra.row_type`) → `adt_activate` `ttyp` | **araç yok** (satır tipi düzeltme) | `adt_get` `ttyp` + `DD40L.ROWTYPE` |
| Z tablo | **araç yok** (kabuk; `adt_post_shell` `tabl` → `unsupported_type`) | `adt_push_source` `tabl` | `adt_get` `tabl` + `DD03L` alan sayısı |
| CDS (DDLS) | `adt_post_shell` `ddls` (yalnız metadata kabuğu) | `adt_push_source` `ddls` + `adt_activate` | `adt_get` `ddls` + `adt_inactive_objects` + satır sayımı |
| Lock object | `adt_post_shell` `enqu` (`extra`) → `adt_activate` `enqu` | **araç yok** | okuma aracı yok → `adt_search_objects` ENQUEUE_/DEQUEUE_ (tip filtresiz) — DOĞRULANMADI |
| Mesaj sınıfı | `adt_post_shell` `msag` (kabuk) | `adt_msgclass_read` → `adt_msgclass_write` (yalnız `s4_private`; birleştirir, değiştirme `allow_overwrite`, silme `delete_numbers`) | `adt_msgclass_read` |

**"araç yok" görünce:** DUR → kullanıcıya bildir. Yöntem ilgili referansta "protokol notu" olarak durur; **ham
REST ile SAP'ye yazan script yazılmaz** (yazma yolu yalnız CLI). Kaynak tabanlı objelerde: CDS kabuğu
`adt_post_shell` `ddls` → `adt_get` → `adt_push_source` → `adt_activate` → readback; Z tablo kabuğunu hâlâ **kullanıcı**
Eclipse ADT / SE11 ile açar, sonrası aynı zincir. XML tabanlı objelerde table type ve lock object kabuğu CLI ile açılıp aktive
edilir; mesaj ekleme `adt_msgclass_write` ile (başka profilde kullanıcı SE91'de); table type satır tipi düzeltme ve domain/DTEL güncelleme işini kullanıcı GUI'de yapar, sen sistemden
okuyarak doğrularsın. `adt_post_shell` `structure`/`tabl`/`doma`/`dtel` → `unsupported_type` (yapı/domain/DTEL için composite araçlar).

## How to use this skill

### 1. Önce oku
1. `%sap-dev` akışı: profil (`sap-project.json`), paket `.rules.md`, adlandırma. Paket kuralı bu skill'le çelişirse paket kazanır.
2. İş türünün referansı (aşağıdaki tablo) + `references/checklists.md` ilgili bölümü.
3. Değişecek obje varsa `adt_get` ile güncel hâlini çek; tüketicileri `adt_where_used` / `adt_impact_analysis` ile ölç.
4. Yeniden kullanım: released standart DTEL/CDS ya da mevcut Z obje var mı (`adt_search_objects`)? Yeni obje son çaredir.
   Standart tablo okuyacaksan önce released karşılığını ara (`references/cds.md` §5 — `#CHECK` tuzağıyla birlikte).

### 2. Tasarımı göster, açık onay al
| İş | Kullanıcıya gösterilecek |
|---|---|
| Yeni Z tablo | Tüm alanlar · her alanın DTEL'i · anahtar · uzunluk · delivery class · data maintenance · CURR/QUAN referans alanları |
| Yeni domain / DTEL | Ad (kullanıcıdan) · tip/uzunluk/ondalık · sabit değerler · 4 etiket (spesifikasyondan, `master_language`'de) |
| Yeni / değişen CDS | View türü · kaynak tablo/view listesi (released mi, `#CHECK` mi) · `sqlViewName` (classic) · tüketiciler |
| Alan silme / rename / tip değişikliği | Yazma yolu analizi (alana yazan kod var mı) · etkilenen CDS/servis/UI · veri kaybı riski |
| Lock object | Birincil tablo · kilit modu · kilit parametresi alanları |
| Mesaj sınıfı | **Nihai tam** mesaj listesi (yazma tüm listeyi değiştirir) |
| Value help CDS | Ortak paket mi, paket-yerel mi → **kullanıcıya sor**; generic master VH kopyalanmaz |

DTEL / append alanı adını önerme; açıklama ve etiketleri tahmin etme (kesin yasak A/D).

### 3. Yaz — bağımlılık sırasıyla
Sıra: **domain → DTEL → structure / table type → Z tablo → lock object → CDS (alt view'dan üste)**; mesaj sınıfı bağımsız.
Her yazma: `--sap-write --scope S0|S1|S2` + gerekçe/intake (`%sap-adt-foundation` §4). Guard reddi (çıkış 2) → DUR.

| Obje | Adımlar | Referans |
|---|---|---|
| Domain | `adt_domain_create` → readback: çıktı uzunluğu, sabit değerler | `domain-dtel.md` §1-§3 |
| DTEL | `adt_dtel_create` → readback: `typeName`, 4 etiket, `masterLanguage` | `domain-dtel.md` §1, §4 |
| Structure | `adt_struct_create` → yer tutucu kaldıysa `adt_get` → `adt_push_source` `structure` (tam DDL, yorumsuz) → `adt_activate` → readback | `tables-structures.md` §1 |
| Z tablo | Kabuk (kullanıcı) → `adt_get` `tabl` → `adt_push_source` `tabl` → `adt_activate` → readback | `tables-structures.md` §3 |
| CDS | `adt_post_shell` `ddls` ya da mevcut view → `adt_get` `ddls` → `adt_push_source` `ddls` → `adt_activate` (bağımlılar `also` ile) → readback | `cds.md` §1 |
| Table type | `adt_post_shell` `ttyp` (`extra.row_type`) → `adt_activate` `ttyp` → `DD40L.ROWTYPE`; boşsa düzeltmeyi kullanıcı SE11'de yapar | `tables-structures.md` §2 |
| Lock object | `adt_post_shell` `enqu` (`extra`: birincil tablo, kilit alanları, mod) → `adt_activate` `enqu` → ENQUEUE_/DEQUEUE_ + inaktif ölçümü | `lock-objects.md` §1, §4 |
| Mesaj sınıfı | Kabuk `adt_post_shell` `msag` → `adt_msgclass_read` (pull kaydı) → nihai listeyi kullanıcıya göster → `adt_msgclass_write` → readback (`s4_private` dışı: mesajları kullanıcı SE91'de girer) | `message-class.md` §2 |

Kırıcı alan değişikliği (rename/silme) varsa **tek tek aktive etme**: ya tüm tüketicilerle `adt_activate` + `also`,
ya da "ekle → tüketiciyi çevir → sil" üç turu (`cds.md` §4 T6/T11).

### 4. Sistemden okuyarak doğrula
- "HTTP 201 / 200 / activated / uploaded" kanıt değildir. `adt_get` ile canlı kaynağı oku, gönderdiğinle kıyasla
  (boyut + içerik; CRLF normalize). "Active source differs" uyarısını **ölç**: boyut farkı büyükse kaynak persist etmemiştir.
- DDIC: `adt_sql_query` ile `DD03L` alan sayısı (tablo/yapı) · `DD40L.ROWTYPE` (table type) · DTEL `typeName` + 4 etiket.
- CDS: `adt_inactive_objects` (bağımlı view/BDEF sessizce inaktif kalabilir) · classic view'da `COUNT(*)` ile satır say
  (replacement tablo tuzağı aktivasyonda görünmez) · abstract entity'de kaynakta `abstract entity` geçmeli.
- Yeni Z objede metadata'dan `masterLanguage` ve açıklama.

### 5. Kapanış
Paket `SESSION_NOTES.md` kaydı (`%sap-dev` §7) · önemli değişiklikte `%sap-code-review` · "tamam" demeden `%verify-done` ·
başarısız denemelerden sonra çalışan yeni yöntem → `%remember`.

## Referanslar
| Dosya | İçerik |
|---|---|
| `references/cds.md` | CDS yaratma/güncelleme yolu, inline-source boş kabuk tuzağı, `sqlViewName`, DCL `#CHECK` sessiz 0 satır, replacement tablo, 14 sözdizimi/aktivasyon tuzağı (union, cast, concat, currency_conversion, sanal element…) |
| `references/domain-dtel.md` | Domain ve DTEL yaratma, çıktı uzunluğu formülü, built-in tipli DTEL, güncelleme protokolü, başarısız yollar |
| `references/tables-structures.md` | Structure (yer tutucu ve yorum tuzakları), table type (`ROWTYPE` boş), Z tablo DDL kuralları, CURR/QUAN referansı, alan ekleme/silme |
| `references/lock-objects.md` | Lock object protokolü, üretilen ENQUEUE/DEQUEUE fonksiyonları, aktivasyonsuz obje tuzağı |
| `references/message-class.md` | Mesaj sınıfı okuma, mesaj ekleme protokolü, yerine-yazma semantiği, başarısız yollar |
| `references/checklists.md` | Tip bazında "yazmadan önce" kontrol listeleri |
| `references/packing-instruction.md` | Ambalajlama talimatı tüketimi (released CDS + belirleme FM'i), S/4 |

## Rules
- Tahmin yok: annotation, sözdizimi, alan adı ve CDS fonksiyon desteği mevcut çalışan artefakttan ya da referanstan
  doğrulanır; yetenek iddiası **canlı aktivasyonla** verilir, sürüm numarasından çıkarılmaz.
- `adt_syntax_check` bu tiplerde güvenilir sözdizimi kapısı değildir ve yazma sınıfıdır; tek güvenilir kapı aktivasyondur.
- Veri önizlemenin/SQL ucunun 400'ü uç sınırıdır, CDS dil sınırı değildir; kararı aktivasyonla ver.
- Yazma yolu yalnız CLI'dir; "araç yok" satırındaki REST akışları teşhis ve araç aktarımı bilgisidir.
- Alan silme, rename, tip değişikliği: yazma yolu analizi + tüketici listesi + kullanıcı kararı; CLI `ack_drop` kabul etmez.
- Profil: kaynak deneyim `s4_private` (S/4HANA) sistemlerde ölçüldü. `ecc`'de released CDS ve DCL/replacement tuzakları
  yoktur; `define view entity`'nin `ecc`'de varlığı ve `s4_public`/`btp_abap`'ta klasik DDIC akışları **DOĞRULANMADI** — canlı teyit et.
