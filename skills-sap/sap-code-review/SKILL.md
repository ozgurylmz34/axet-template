---
name: sap-code-review
description: >
  Use when an SAP ABAP backend change must be reviewed before it is reported done or written to SAP: ABAP
  classes, programs, includes, function modules, AMDP, CDS views, RAP behavior definitions and handlers, DDIC
  objects, classic OData (SEGW, DPC_EXT) and clean core or released API questions. Selects the object-type
  checklists for the changed files, runs the offline checks (CLI reviewer chain, abaplint, released successor
  map) and briefs an independent reviewer through the agent tool with the checklist text pasted in. Triggers:
  "SAP kodunu incele", "ABAP review", "CDS'i gözden geçir", "RAP incele", "bug gate", "clean core kontrol",
  "released halef", "abaplint", "ATC bulgusu". Do not use for UI5 apps (sap-ui5-fiori), FS/TS documents
  (sap-fs-ts-docs) or non-SAP code (code-review).
---

# SAP kod incelemesi — kontrol listeli bağımsız inceleme

> **Profil:** clean core satırları `ecc`'de uygulanmaz, `s4_public`/`btp_abap`'ta zorunludur, `s4_private`'ta `cleancore_policy`'ye
> bağlıdır (`references/clean-core.md` §1); profil yeteneği varsayımı SR-03 satırıdır.

> Genel akış `%code-review`'dadır; bu skill SAP backend'ine özgü parçaları ekler: obje tipi kontrol listeleri
> (kimlikli satırlar), çevrimdışı kontroller ve inceleyici brifingi.
> İnceleyen alt ajan SAP çekirdeğini, bu skill'i, proje/paket kurallarını ve hafızayı **görmez**: kullanılan her kural
> brifinge **metin olarak** girer. aXet'te özel ajan tanımı yoktur; "bug gate" rolü = yerleşik `agent` aracıyla açılan
> **taze** bir alt ajan + `references/reviewer-brief.md`.

## When to use this skill
- SAP backend değişikliği bitti; "tamam" demeden ve SAP'ye yazmadan önce (yazan ile inceleyen aynı bağlam olmasın).
- Kullanıcı SAP kodu incelemesi, clean core / released halef, abaplint ya da ATC bulgusu sorduğunda.
- **Kullanma:** UI5 uygulaması → `%sap-ui5-fiori` · FS/TS/kullanıcı dokümanı → `%sap-fs-ts-docs` · SAP dışı kod → `%code-review`.

## How to use this skill

### 1. Kapsamı topla: diff + etki alanı
1. `git diff` (ya da değişen yerel dosyalar) + değişikliğin amacı (spesifikasyon `dosya:satır`).
2. Değişen her obje için canlı kaynağın çekildiği kanıt (`adt_get`, zaman). Yoksa önce çek (`%sap-adt-foundation`).
3. Etki alanı: `adt_where_used` / `adt_impact_analysis` / yerel `grep`; kapsam alanlarını (`coverage_complete`, `truncated`) yaz.
   Kapsam = değişen satırlar + dokundukları (çağıran/çağrılan, veri akışı, sözleşme). İlgisiz eski kod kapsam dışıdır.

### 2. Dosya → kontrol listesi
Her değişiklikte `references/checklist-common.md` + tablodakiler. Obje tipi skill'inin **yazma-öncesi** listesi de yürünür;
inceleme satırları onun yerine geçmez.

| Değişen dosya | İnceleme listeleri (`references/`) | Yazma-öncesi liste | Çevrimdışı kontrol (§3) |
|---|---|---|---|
| `*.clas.abap` | `checklist-abap.md` + `checklist-clean-core.md` | `%sap-classic-abap`, `%sap-dev` coding-patterns | `run_review` görev `class_push` (push'ta da koşar) · `abaplint_run.py` |
| `*.intf.abap` | `checklist-abap.md` §A-§B + `checklist-clean-core.md` | `%sap-classic-abap` | push'ta zincir yok → `class_push` elle (kapıdaki abaplint arayüzü ölçmez) · `abaplint_run.py` |
| `*.ccimp.abap`, `*.ccau.abap` (behavior pool) | `checklist-rap.md` + `checklist-abap.md` + `checklist-clean-core.md` | `%sap-rap` checklists §B-§C | `class_push` · `abaplint_run.py` |
| DPC_EXT / MPC_EXT, dış API çağıran sınıf | `checklist-odata-backend.md` + `checklist-abap.md` | `%sap-odata-backend` | `class_push` · `abaplint_run.py` |
| `*.prog.abap` (program, include) | `checklist-abap.md` §B-§D + `checklist-clean-core.md` | `%sap-classic-abap` checklists | push'ta zincir yok → `class_push` elle · `abaplint_run.py` |
| `*.fugr.abap`, `*.func.abap` | `checklist-abap.md` §E + `checklist-clean-core.md` | `%sap-classic-abap` fugr-fm | zincir yok · abaplint kapsam dışı |
| `*.ddls.asddls` (RAP katmanı dahil) | `checklist-cds-ddic.md` + `checklist-clean-core.md` (RAP BO'daysa + `checklist-rap.md`) | `%sap-cds-ddic` §1 · `%sap-rap` §B | `cds_update`; view entity / projection → `rap_cds_creation` |
| BDEF | `checklist-rap.md` | `%sap-rap` §B | `rap_bdef_creation` |
| SRVD / SRVB | `checklist-rap.md` (BE-61) | `%sap-rap` service-publish | `rap_service_binding` (boş zincir) |
| `*.ddlx.asddlxs`, `*.dcls.asdcls` | `checklist-cds-ddic.md` | `%sap-cds-ddic` | zincir yok |
| Tablo / yapı (`*.tabl.xml` ya da DDL) | `checklist-cds-ddic.md` | `%sap-cds-ddic` §3-§4 | `table_update` · `table_creation` · `struct_creation` |
| Domain / DTEL (CSV, `*.doma.xml`, `*.dtel.xml`) | `checklist-common.md` (BE-02) | `%sap-cds-ddic` §2 | `domain_creation_csv` · `dtel_creation` |
| UI5 uygulaması | → `%sap-ui5-fiori` | — | — |
| FS / TS / KD dokümanı | → `%sap-fs-ts-docs` | — | — |

### 3. Önce deterministik kontroller
```
# proje kökünden; <TEMPLATE> = template reposunun mutlak yolu
python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sapadt/lib/validators/run_review.py --task <görev> --artifact <dosya> --json
python <TEMPLATE>/skills-sap/sap-code-review/scripts/abaplint_run.py <dosya|klasör> [...]
python <TEMPLATE>/skills-sap/sap-code-review/scripts/released_successors.py lookup <OBJE> [...]
python <TEMPLATE>/skills-sap/sap-code-review/scripts/released_successors.py status
python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py adt_atc_check --args-json '{"name":"<OBJE>","object_type":"class"}' --project-dir <PROJE_KÖKÜ>
python <TEMPLATE>/skills-sap/sap-code-review/scripts/quality_scorecard.py kaydet --kapi <kapı> --sonuc pass|fail|warn|not-run --artefakt <kanıt> --kapsam "..."
python <TEMPLATE>/skills-sap/sap-code-review/scripts/quality_scorecard.py karne [--kosum <id>] [--json]
```
Okuma kuralları:
- `run_review` `PASS` yalnız "zincirin baktığı yerde bulgu yok"tur. `zincir_bos: true` = hiç gate koşmadı; sonuçta `SKIP` = ölçülmedi.
- `--cevrimdisi` SAP'ye ulaşamayan gate'lerin BLOCKER'ını WARNING'e indirir: yalnız bağlantı yokken ve `offline_downgraded_gates` raporda yazılarak.
- "Push'ta zincir yok" satırlarında yazma kapısı hiçbir gate koşmaz; inceleme `run_review`'u elle koşar.
- `abaplint_run.py` çıkış 0 yalnız her dosya ölçülüp temizse; 3 = ölçülemedi (araç yok, çıktı doğrulanamadı), 4 = kısmi
  ölçüm. abaplint derleme kanıtı değildir.
- `adt_syntax_check` bir inceleme aracı değildir: yazma sınıfıdır (bekleyen sürümü aktive eder).
- `quality_scorecard.py` **bir kapı DEĞİL, rapordur**: koşan kapıları append-only bir deftere yazar ve tek bir karne
  üretir (`not-run` ayrı sütun · artefaktsız `pass` geçersiz · 0 test ya da dar kapsam `warn` · kaydedilmemiş kapı
  varken hüküm `KISMI`). Hiçbir akışa bloklayıcı olarak bağlanmaz; çıkış kodunu **insan** okur.

Ayrıntı: `references/validator-map.md` (satır ↔ validator, kapsam) · `references/clean-core.md` · `references/abaplint.md` · `references/quality-scorecard.md` (kapı defteri + karne).

### 4. Bağımsız inceleyici
`references/reviewer-brief.md`'deki brifingi doldur → `agent` aracıyla **taze** alt ajan. İlgili kontrol listesi tablolarını ve
§3 çıktılarını **kısaltmadan** yapıştır. Yazan oturum kendi işini inceleyici yerine onaylamaz.

### 5. Raporu doğrula, karar ver
1. Her BLOCKER'ı kendin okuyarak teyit et (`dosya:satır`, araç çıktısı); kanıtlanamayanı düşür ya da WARNING'e indir.
2. Karar: kanıtlı ≥ 1 BLOCKER → **BLOCKER** (düzeltmeden SAP'ye yazma ve commit yok) · yalnız WARNING → **WARNING** (düzelt ya da
   gerekçeyle geç, kullanıcıya bildir) · yoksa **PASS**. ÖNERİ kararı etkilemez.
3. Kontrol listesi satırına dayanan kanıtlı bulgu zorunlu düzeltmedir; "önemsiz" denerek geçilmez. İtiraz yalnız
   "bu ihlal değil, kanıt şu" biçiminde olur.
4. "ÖNCEDEN VAR" kritik bulgular ayrı raporlanır; bu değişikliği bloklamaz, açık kalem olur.
5. Ardından `%verify-done`.

### 6. Bulgu → kontrol listesi satırı
Listede olmayan ve tekrar edebilecek bir tuzak bulunduysa ders yalnız nota ya da hafızaya yazılmaz:
1. Düzelt (ana oturum).
2. Çalışan deseni ilgili obje tipi skill'inin referansına yaz.
3. İlgili `references/checklist-*.md`'ye satır **öner**: sıradaki boş kimlik (backend `BE-71`, OData `OD-06`, clean core `CC-04`,
   ortak `SR-04`'ten başlar), altı sütun dolu: ne · nasıl · önem · otomasyon · kaynak ders (tarih + kanıt).
   Otomasyon sütununa yalnız gerçekten var olan validator yazılır (`tests/test_checklists.py` zorlar); yoksa `YOK`.
4. Deterministik yakalanabiliyorsa validator adayı olarak açık kalem yaz. Yazma kapısına validator eklemek araç
   değişikliğidir → önce kullanıcıya açıkla, onay al.
5. Template reposundaki değişiklik ekibe gider → kullanıcıya öner, onayla commit/PR.
Kimlik yeniden kullanılmaz; kaldırılan satırın kimliği boş kalır.

## Rules
- İnceleyen değişiklik yapmaz, SAP'ye yazmaz. Düzeltme ana oturumda, SAP yazımı `%sap-adt-foundation` kapısından.
- Spekülatif BLOCKER yok: doğrudan okunabilen iddia okunmadan bulgu olmaz; hata senaryosu kurulamayan şüphe NOT'tur.
- Gate `PASS`/`SKIP`, abaplint "temiz", aktivasyon "başarılı" doğruluk kanıtı değildir; aktivasyonda ya da çalışma
  zamanında çıkan satırlar elle yürünür.
- Clean core bulgusunun önemi projenin `cleancore_policy`'sine göredir (`references/clean-core.md`).
- Kesin yasak (A/B/C/D) ihlali daima BLOCKER.

## Bakım
- Çevrimdışı testler: `python -m unittest discover -s <TEMPLATE>/skills-sap/sap-code-review/tests -v`
- Kaynak ↔ aXet eşlemesi ve kaynaktan alınmayanlar: `references/validator-map.md` §6.
