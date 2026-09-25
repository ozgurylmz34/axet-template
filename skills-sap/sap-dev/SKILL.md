---
name: sap-dev
description: >
  Entry point for any SAP ABAP development work: decides what to read first (project profile,
  package rules, naming, coding patterns, ADT operations) and in which order to proceed. Use when
  creating or changing Z objects (CDS, RAP, domain, data element, structure, table, class, program,
  include, function module, OData service, message class), writing ABAP code, naming an object or
  package, or starting work in an SAP package. Triggers: "CDS yarat", "RAP", "tablo yarat",
  "program yaz", "sınıf ekle", "ABAP kodu", "obje adı ne olmalı", "paket aç", "pakette çalış",
  "SAP geliştirmesi". Do not use for triaging a NEW request (use sap-intake-triage first) or for
  non-SAP code.
---

# SAP geliştirme — giriş ve yönlendirme

> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde (`core/sap/00-sap.md`) her oturum yüklüdür; burada tekrarlanmaz.
> Bu skill bilgi taşımaz, **ne zaman neyi okuyacağını** söyler. Referans dosyaları bu skill'in klasöründedir.

## When to use this skill
- Bir SAP geliştirmesine başlarken ya da iş türü değiştiğinde (ör. DDIC'ten sınıfa geçerken).
- Obje ya da paket adı verilecekken, ABAP kodu yazılacakken.
- **Kullanma:** yeni talebin ilk ele alınışı → önce `%sap-intake-triage`; tek başına okuma/indirme/aktivasyon
  soruları → `%sap-adt-foundation`.

## How to use this skill

### 1. Talep sınıflandı mı?
Yeni geliştirme, revizyon, rapor, alan ya da ekran talebiyse ve kapsam sınıfı (S0/S1/S2) yazılı değilse önce
`%sap-intake-triage`. İş sırasında büyürse yeniden sınıfla.

### 2. Proje bağlamı
1. Proje kökündeki `sap-project.json`: `sap_profile`, `release`, `master_language`, `source_root`. Yoksa DUR,
   kullanıcıya `new_project.py --sap` ile kurmasını söyle.
2. Profil yeteneği varsayma: `s4_public` ve `btp_abap`'ta klasik obje (program, include, fonksiyon grubu, SE11
   tablo ekranı) yoktur; `ecc`'de RAP ve released CDS yoktur. Emin olmadığın yeteneği canlı sistemde okuyarak
   doğrula; matris rehberdir, kanıt değildir.

### 3. Paket
1. Aktif paket proje `AGENTS.md`'sinde yazar; yoksa ya da iş başka pakete aitse **kullanıcıya sor** (paket
   rastgele seçilmez).
2. `<source_root>/<MODÜL>/<PAKET>/` altında oku: `.rules.md` (ad önekleri, bağımlılık, bilinen istisnalar,
   transport) → `SESSION_NOTES.md` son kayıt → `SPEC.md` açık kararlar. `ref_docs/` spesifikasyon kaynağıdır,
   canlı teslimat değildir.
3. Yerel paket klasörü yoksa: `python <TEMPLATE>/scripts/new_package.py <PAKET> --title "<başlık>"`. **SAP'de
   paketi kullanıcı yaratır**; transport numarasını kullanıcı verir.

### 4. İş türüne göre önce oku
Her şeyi değil, ilgili olanı oku.

| İş | Önce oku |
|---|---|
| Obje ya da paket adı | `references/naming.md` + paketin `.rules.md` Naming tablosu (paket kuralı önceliklidir) |
| ABAP kodu (sınıf, program, FM, SELECT, range, kur) | `references/coding-patterns.md` |
| SAP'de okuma, indirme, push, aktivasyon, silme, where-used, kilit, transport | `%sap-adt-foundation` ve referansları |
| Yeni DDIC tablo / yapı / DTEL | `references/naming.md` §5 alan tipleme sırası; tablo öncesi alan + DTEL + anahtar tasarımını göster, açık onay al |
| "Standart tablo yerine ne kullanılır" (clean core) | `references/coding-patterns.md` §7 + ATC (`%sap-adt-foundation` → `foundation-query.md`) |
| Liste / rapor ekranı | SAP çekirdeği ALV paritesi kuralı; UI5 mekaniği → `%sap-ui5-fiori` (`list-grid-alv.md`) |
| UI5 freestyle / Fiori ekranı, filtre ekranı, value-help, lokal çalıştırma, BSP deploy | `%sap-ui5-fiori` |
| Standart tabloya veri yazma ihtiyacı | Kesin yasak B: BAPI → RFC FM → BDC → kullanıcıdan manuel |
| CDS view, domain, data element, structure, table, table type, lock object, mesaj sınıfı | `%sap-cds-ddic` |
| RAP (view entity katmanları, BDEF, behavior sınıfı, SRVD/SRVB, EML, draft/kilit, value-help) | `%sap-rap` |
| Klasik sınıf, program + include, fonksiyon grubu, rapor/ALV, Dynpro, e-posta, form | `%sap-classic-abap` |
| Klasik OData (SEGW, DPC_EXT/MPC_EXT, deep insert, function import), dış API çağrısı | `%sap-odata-backend` |
| SAP backend değişikliğini "tamam" demeden incelemek; clean core / released halef; abaplint; ATC bulgusu | `%sap-code-review` |
| Veri yalnız SAP GUI ekranında görünüyor (ALV, tablo kontrolü, ekran alanı); önce CLI okuması denenir | `%sap-gui-scripting` (script'i geliştirici çalıştırır) |
| Web/doküman araştırması (SAP Help, not, public kod) | `%research` |
| SAP'ye CLI ile yazılmayacak teslim (abapGit ZIP; içe aktarımı geliştirici yapar) | `%sap-abapgit-delivery` |
| FS/TS/KD yazımı, doküman incelemesi, kullanıcı kılavuzu PDF'i, TS build öncesi canlı teyit | `%sap-fs-ts-docs` |
| Freestyle UI5 (OData V2) uygulamasının ekran görüntülü kullanıcı kılavuzu (mock veriyle çekim, HTML + PDF) | `%sap-ui5-user-guide` |

**Araç sınırı (otorite `--list` + `%sap-adt-foundation` → `tool-catalog.md`):** 2026-09-13'te eklenen yollar — kabuk
`ddls`/`srvd`/`bdef`/`fugr`/`func`/`msag`/`enqu`/`ttyp`, push `bdef`/`ccimp`/`ccau`/`func`, klasik ekran
`adt_screen_generate`, mesaj yazma `adt_msgclass_write` ve açıklama değiştirme `adt_set_description` (ikisi yalnız `s4_private`),
okuma `adt_revisions`/`adt_object_structure`/`adt_system_info`, bağlantı teşhisi `sap_doctor`, domain ön kontrolü — çevrimdışı test edildi, canlı
DOĞRULANMADI (`fugr`/`func`/ekran yalnız `ecc`/`s4_private`). 2026-09-21 eki (yalnız `s4_private`, çevrimdışı test edildi, canlı
DOĞRULANMADI): Z tablo `adt_table_create`, tablo tipi `adt_ttyp_create` (satır tipi düzeltmesi dahil), metin havuzu `adt_textpool_write`,
push `ccdef`/`ccmac`. Hâlâ yok: DDLX/DCL/SRVB, FM RFC-enable, metin havuzu başlıkları,
`$metadata` okuma. İlgili skill'in araç tablosu yolu söyler; araç yoksa işi kullanıcı SAP GUI/ADT'de yapar,
okuma/doğrulama CLI ile yapılır.

**Obje tipine özgü skill** (ör. Adobe Forms, IDoc) bu template'te henüz yoksa:
yöntemi **varsayma**. Paketteki çalışan kaynak dosyalarından ve sistemdeki benzer Z objeden oku, `adt_get` ile
doğrula; çalışan yöntemi bulduğunda `%remember` ile kaydet.

### 5. ADT işlem sırası
DDIC (domain → data element → structure → table) → CDS → behavior definition + behavior sınıfı **birlikte** →
service definition → service binding publish. Her adımda `%sap-adt-foundation` akışı: önce güncel kaynağı çek,
kapsam beyanıyla yaz, sistemden tekrar okuyarak doğrula, inaktif obje kalmadığını ölç.

### 6. Kullanıcıdan gelmesi gerekenler
| Konu | Kural |
|---|---|
| Transport | Yaratılmaz, uydurulmaz; kullanıcıdan istenir. İş bir transporta bağlıysa aynısıyla devam edilir. |
| Paket | Yaratılmaz; hangisinin kullanılacağı sorulur. |
| Yeni program / include | Yaratmadan önce TITLE istenir; include TITLE'ına tip soneki eklenir (`references/naming.md` §6). |
| Yeni DDIC tablo | Alanlar, her alanın data element'i, anahtar ve uzunluklar gösterilir; açık onay alınır. İstemci alanı `mandt : mandt`. Yönetim alanları (oluşturan/zaman, son değiştiren/zaman, RAP'ta ETag için yerel son değişiklik zamanı) tasarımda listelenir. |
| Yeni Z DDIC objesinin adı (domain, data element, tablo, yapı, tablo tipi, kilit objesi, arama yardımı…; NR objesi dahil) | Öneri sunabilirsin, ama sırayla: ① önce yeniden kullanım — released/standart ya da mevcut Z obje yeterli mi (`references/naming.md` §5) ② değilse adlandırma standardına ve paket `.rules.md` öneklerine uygun ad (`references/naming.md` §4; uzunluk: genel ≤ 30, tablo ≤ 16, NR objesi ≤ 10) ③ **her adı canlıda kontrol et** (`adt_search_objects` / `adt_get`; NR objesi için sistemdeki NR tanımı) — varsa başka ad öner ④ tablo hâlinde sun (ad · tip · amaç · canlı kontrol sonucu) ⑤ kullanıcının **açık onayı** olmadan o adla yaratma. Genel mutabakat ("devam et") ad onayı sayılmaz: tablo açıkça onaylanır, intake'te ad başına `ONAY` kutusu. |
| Standart objeye append alanı / append yapı adı | AI önermez, append'i ve append alanının Z DTEL'ini/domain'ini de yaratmaz; kullanıcı belirler, kendisi yaratır, sonucu bildirir (kesin yasak A — standart objeler yalnız okunur). |
| Z obje açıklama ve etiketleri | Spesifikasyondan ya da eski sistemden alınır; tahmin edilmez. |
| Spesifikasyon ↔ eski sistem kaynağı | Spesifikasyon karar otoritesidir; eski kaynak yalnız yapı deseni (join, formül) için okunur. Spesifikasyonda silinen alan kaynağa girmez. Spesifikasyon yoksa eski sisteme kendiliğinden dönme: kullanıcıdan onay iste. |

### 7. Kapanış
1. Paket `SESSION_NOTES.md`'ye kayıt: yapılan (push / aktivasyon / sistemden okuma doğrulaması), sıradaki, bloklayan.
2. Pakete özgü karar netleştiyse `.rules.md`'ye yaz (ad istisnası, bağımlılık, transport).
3. Önemli değişiklikten sonra `%sap-code-review`; "tamam" demeden önce `%verify-done`.

### Yeni bilgi nereye yazılır
| Bilgi | Yer |
|---|---|
| Tek pakete özgü (istisna, bağımlılık, transport) | paket `.rules.md` |
| Paket günlüğü | paket `SESSION_NOTES.md` |
| Fonksiyonel açık karar | paket `SPEC.md` açık kararlar |
| Proje geneli karar / durum | proje hafızası (`%remember`, proje kapsamı) |
| Projede her işte uyulacak bağlayıcı kural (ör. Z tablo öneki) | proje hafızası + proje `AGENTS.md` "Proje kuralları"na kısa madde (davranış yüzeyi: onayı kullanıcı verir — `%remember` §1) |
| Her projede geçerli ADT yöntemi ya da ABAP tuzağı | `%remember` ekip kapsamı ya da template'e öneri |

## Rules
- Tahmin yok: alan adı, tip, annotation, syntax ve yöntem mevcut artefakttan ya da referanstan doğrulanır;
  yoksa sistemden okunur; hâlâ belirsizse DUR ve sor.
- Alt ajana SAP araştırması devredilirse brifinge kesin yasakları, "yazma sınıfı araç çağırma" kuralını ve
  paketin `.rules.md` önekleri **metin olarak** yazılır (alt ajan çekirdeği ve proje dosyalarını görmez).
  Hazır bloklar ve rol ekleri (araştırma, backend, UI5, koordinasyon kontrol listesi): `references/role-briefs.md`.
- Paket `.rules.md` bu skill'in referanslarıyla çelişirse paket kuralı geçerlidir; çelişkiyi kullanıcıya bildir.
