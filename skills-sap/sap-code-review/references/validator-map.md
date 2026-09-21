# Satır ↔ validator haritası — yazma kapısı zinciri, inceleme araçları, kapsam

> **Otorite koddur:** `run_review.py` `TASK_VALIDATORS` ve `_reviewer.py` eşlemeleri. Bu dosya onların okunur özetidir.
> §1 ve §2'nin kodla eşitliğini `tests/test_checklists.py` zorlar: kod değişir de tablo bayatlarsa test kırılır.
> Kısaltma: `<F>` = `<skills-sap>/sap-adt-foundation/scripts/sapadt`.

## 1. Push → görev: yazma kapısı hangi zinciri koşar
`adt_push_source`, `object_type`'ı `<F>/_reviewer.py` `OBJECT_TYPE_TO_TASK` ile göreve çevirir. `ddls` için kaynak
`define [root] view entity` ya da `as projection on` içeriyorsa görev `rap_cds_creation` olur (`task_for_push`).
`—` = zincir yok: push'ta hiçbir validator koşmaz (kayda geçmiş boşluk). Bu tiplerde inceleme `run_review`'u elle koşar.

| object_type | görev | not |
|---|---|---|
| `ddls` | `cds_update` | view entity / projection → `rap_cds_creation` |
| `cds` | `cds_update` | eşanlamlı |
| `tabl` | `table_update` | tablo ya da yapı |
| `table` | `table_update` | |
| `structure` | `table_update` | |
| `class` | `class_push` | |
| `clas` | `class_push` | |
| `ccimp` | `class_push` | behavior pool yerel sınıfları |
| `ccau` | `class_push` | test sınıfları |
| `bdef` | `rap_bdef_creation` | |
| `srvd` | `rap_service_binding` | boş zincir (§2) |
| `prog` | `program_push` | abaplint · released_objects · decimal_write_to (2026-09-14) |
| `program` | `program_push` | |
| `report` | `program_push` | eşanlamlı |
| `include` | `program_push` | abaplint include'u ölçemez → SKIP = WARNING, yanıtta `unmeasured` / ÖLÇÜLEMEDİ |
| `incl` | `program_push` | eşanlamlı |
| `prog/i` | `program_push` | klasik include'un ADT tip kodu (eşanlamlı) |
| `intf` | `interface_push` | method_param_type_c (BLOCKER) · decimal_write_to · released_objects |
| `interface` | `interface_push` | |
| `fugr` | — | fonksiyon grubu zinciri yok; push yalnız FG ana include'unu (`FUNCTION-POOL`) yazar, FM gövdesini kapsamaz |
| `func` | — | FM gövdesi: gömülü inceleme yok → yazmadan önce elle `run_review --task class_push --artifact <fm>.abap` |
| `doma` | — | tekil push; bileşik araç aşağıda |
| `dtel` | — | |
| `dcl` | — | erişim kontrolü zinciri yok |
| `ddlx` | — | metadata extension zinciri yok |
| `srvb` | — | yayın yolu ayrı |
| `msag` | — | |
| `tabletype` | — | |
| `ttyp` | — | |
| `enqu` | — | |

Bileşik araçlar (`COMPOSITE_TOOL_TO_TASK`):

| araç | görev | not |
|---|---|---|
| `adt_struct_create` | `struct_creation` | yazılacak `fields[]` DDL'i (yazma yolunun aynı render'ı) her çağrıda `struct_fields_dtel` ile yazmadan önce denetlenir; `artifact_path` verilirse artefaktın `struct_creation` zinciri de koşar, hükümler birleşir; verilen yol yoksa `artifact_not_found` → BLOCKER |
| `adt_domain_create` | `domain_creation_csv` | artefakt yolu verilmezse reviewer SKIP; formül kuralları araç içinde ayrıca koşar |
| `adt_dtel_create` | `dtel_creation` | artefakt yolu verilmezse reviewer SKIP |
| `adt_table_create` | `table_creation` | (2026-09-21) araç `fields[]`'ten kurduğu ve SAP'ye PUT edeceği DDL'in kendisini her çağrıda zincirden geçirir (dosya yazılamazsa BLOCKER); artefakt argümanı yok |

## 2. Görev → validator zinciri
Kaynak: `<F>/lib/validators/run_review.py` `TASK_VALIDATORS`. Önem = zincirdeki önem (verdict'e böyle sayılır).
"İlgili satır": bu skill'in inceleme satırı ya da obje tipi skill'inin yazma-öncesi satırı (içerik okunarak eşlendi).

| görev | validator | önem | ne kontrol eder | ilgili satır |
|---|---|---|---|---|
| `cds_creation` | `check_window_function_compatibility.py` | BLOCKER | `OVER (PARTITION BY …)` window fonksiyonu | `%sap-cds-ddic` CDS-WIN |
| `cds_creation` | `check_deprecated_annotations.py` | WARNING | deprecated annotation (ör. `preserveKey`) | CDS-DEPR |
| `cds_creation` | `check_cds_currency_reference.py` | BLOCKER | CURR/QUAN alanında nitelenmiş referans annotation'ı | CDS-CUR |
| `cds_creation` | `check_released_objects.py` | WARNING | `from`/`join`'de halefi olan standart tablo | BE-03 · CDS-FROM-3 |
| `cds_creation` | `check_standard_table_fields.py` | WARNING | standart tablo alanları hedef sistemde var mı (SAP okur) | CDS-FROM-2 |
| `cds_update` | `check_window_function_compatibility.py` | BLOCKER | window fonksiyonu | CDS-WIN |
| `cds_update` | `check_deprecated_annotations.py` | WARNING | deprecated annotation | CDS-DEPR |
| `cds_update` | `check_cds_currency_reference.py` | BLOCKER | CURR/QUAN referansı | CDS-CUR |
| `cds_update` | `check_released_objects.py` | WARNING | halefi olan standart tablo | BE-03 |
| `table_creation` | `check_struct_field_dtel_active.py` | BLOCKER | alan tipindeki Z/Y ve `/ad-alanı/` DTEL'ler sistemde var ve aktif mi (standart DTEL hariç; DTEL değilse yapı/tablo/tablo tipi sondası) | TBL-DTEL |
| `table_creation` | `check_cds_currency_reference.py` | BLOCKER | CURR/QUAN referansı (tablo kipi) | TBL-CUR |
| `table_creation` | `check_deprecated_annotations.py` | WARNING | deprecated annotation | — |
| `table_update` | `check_struct_field_dtel_active.py` | BLOCKER | Z/Y ve `/ad-alanı/` DTEL'ler var ve aktif mi | TBL-DTEL |
| `table_update` | `check_table_field_drop.py` | BLOCKER | mevcut alan silme / yeniden adlandırma / tip değişimi (canlı kaynakla fark) | BE-16 · TBL-DROP |
| `table_update` | `check_cds_currency_reference.py` | BLOCKER | yeni CURR/QUAN referansı | TBL-CUR |
| `table_update` | `check_deprecated_annotations.py` | WARNING | deprecated annotation | — |
| `table_update` | `check_standard_table_fields.py` | WARNING | standart alanlar hedef sistemde var mı | — |
| `struct_creation` | `check_struct_field_dtel_active.py` | BLOCKER | Z/Y ve `/ad-alanı/` DTEL'ler var ve aktif mi | STR-FIELD-2 |
| `struct_creation` | `check_cds_currency_reference.py` | BLOCKER | CURR/QUAN referansı | STR-CUR |
| `struct_creation` | `check_deprecated_annotations.py` | WARNING | deprecated annotation | STR-DEPR |
| `struct_creation` | `check_standard_table_fields.py` | WARNING | standart alanlar hedef sistemde var mı | STR-FIELD-3 |
| `struct_post_create` | `check_sap_struct_consistency.py` | BLOCKER | sistemdeki yapı yerel artefaktla tutarlı mı | STR-VERIFY |
| `struct_post_create` | `check_sap_active_version.py` | BLOCKER | sistemde aktif sürüm var mı | BE-15 |
| `sap_active_check` | `check_sap_active_version.py` | BLOCKER | sistemde aktif sürüm var mı | BE-15 |
| `sap_active_check` | `check_sap_master_language.py` | WARNING | obje ana dili = projenin `master_language`'i | DE-LANG |
| `domain_creation_csv` | `check_domain_output_length.py` | BLOCKER | domain çıktı uzunluğu formülü | DE-DOM |
| `dtel_creation` | `check_dtel_creation_labels.py` | BLOCKER | 4 etiket + açıklama dolu, uzunluk sınırında, domain bağı | DE-LABEL |
| `dtel_update` | — | — | boş zincir (bilinçli) | — |
| `class_push` | `check_method_param_type_c.py` | BLOCKER | metot parametresinde `TYPE c LENGTH n` | BE-10a |
| `class_push` | `check_decimal_write_to.py` | WARNING | API gövdesi kuran sınıfta `WRITE … TO` | BE-04 |
| `class_push` | `check_amdp_comment_apostrophe.py` | BLOCKER | AMDP `--` yorumunda apostrof | BE-28 (c) |
| `class_push` | `check_docu_itf_line_width.py` | BLOCKER | F1 dokümantasyon ITF satırı 72 karakteri aşıyor mu | `%sap-classic-abap` forms-f1-help.md |
| `class_push` | `check_released_objects.py` | WARNING | ABAP SQL'de halefi olan standart tablo | BE-03 |
| `class_push` | `check_abaplint.py` | WARNING | abaplint (yapısal/mantık + hijyen), sınıf/program | BE-36 · BE-47 · BE-48 (sinyal) |
| `program_push` | `check_abaplint.py` | WARNING | abaplint; `REPORT` satırlı program ölçülür, include ve `PROGRAM` modül havuzu ölçülemez (SKIP) | BE-36 · BE-47 · BE-48 (sinyal) |
| `program_push` | `check_released_objects.py` | WARNING | ABAP SQL'de halefi olan standart tablo | BE-03 |
| `program_push` | `check_decimal_write_to.py` | WARNING | API gövdesi kuran kodda `WRITE … TO` | BE-04 |
| `interface_push` | `check_method_param_type_c.py` | BLOCKER | arayüz metot parametresinde `TYPE c LENGTH n` | BE-10a |
| `interface_push` | `check_decimal_write_to.py` | WARNING | `WRITE … TO` | BE-04 |
| `interface_push` | `check_released_objects.py` | WARNING | halefi olan standart tablo | BE-03 |
| `struct_fields_dtel` | `check_struct_field_dtel_active.py` | BLOCKER | `adt_struct_create` her çağrıda: `fields[]`'ten kurulan (yazılacak) DDL'deki Z/Y ve `/ad-alanı/` DTEL'ler var ve aktif mi; süre bütçesi dolarsa ÖLÇÜLEMEDİ | STR-FIELD-2 |
| `rap_cds_creation` | `check_window_function_compatibility.py` | BLOCKER | window fonksiyonu | CDS-WIN |
| `rap_cds_creation` | `check_deprecated_annotations.py` | WARNING | deprecated annotation | CDS-DEPR |
| `rap_cds_creation` | `check_cds_currency_reference.py` | BLOCKER | CURR/QUAN referansı | CDS-CUR |
| `rap_cds_creation` | `check_rap_readonly_consumption.py` | BLOCKER | BO'suz salt okunur tüketim view'ında projection/root | CDS-CONSUME |
| `rap_cds_creation` | `check_reuse_gate.py` | WARNING | yerel kopya / ortak value-help yeniden kullanımı | `%sap-rap` checklists §A value-help satırı |
| `rap_cds_creation` | `check_released_objects.py` | WARNING | halefi olan standart tablo | BE-03 |
| `rap_cds_creation` | `check_standard_table_fields.py` | WARNING | standart alanlar hedef sistemde var mı | CDS-FROM-2 |
| `rap_bdef_creation` | `check_rap_managed_etag.py` | BLOCKER | managed BO'da `lock master` + `etag master` | `%sap-rap` checklists §B |
| `rap_bdef_creation` | `check_audit_fields_autofill.py` | WARNING | audit alanları var, doldurma determination'ı yok | BE-11 |
| `rap_bdef_creation` | `check_bdef_backtick.py` | BLOCKER | BDEF yorumunda ters tırnak | BE-62 |
| `rap_service_binding` | — | — | boş zincir (bilinçli) | BE-61 elle |
| `itg_s2_signoff` | `check_itg_signoff.py` | BLOCKER | S2 intake artefaktı tam + kullanıcı mutabakatı | `%sap-intake-triage` (dosya: `check_intake_signoff.py`) |

`struct_post_create` ve `sap_active_check` yazma sonrası kontrollerdir; hangi aracın çağırdığı bu dosyada ölçülmedi.

## 3. İnceleme satırlarının otomasyon durumu
Toplam 81 satır (`checklist-*.md`).

**Zincirdeki validator satırı tam karşılar (6):** BE-10a · BE-04 · BE-62 · BE-11 · BE-16 · BE-03.
Önem farkı: BE-04 ve BE-11 zincirde WARNING, incelemede BLOCKER; BE-03 politikaya bağlı.

**Kısmi — validator sinyali ya da kısmi kapsam (6):** BE-47 · BE-48 · BE-36 (abaplint `parser_error`) · BE-28 (yalnız (c)) ·
BE-15 (push içerik geri okuması + alan kaybı) · BE-01 (kapı kaynak taraması + Z/Y önek guardrail'i).

**Kısmi — okuma aracı ya da script, zincirde değil (5):** SR-02 (CLI önceden çekim ister) · BE-12, BE-31, CC-01 (`adt_atc_check`) ·
CC-03 (`released_successors.py status`).

**Otomasyon YOK — elle yürünür (64):**
- ortak: SR-01 · SR-03 · BE-02 · BE-18 · BE-66 · BE-64 · BE-70 · BE-65
- ABAP: BE-10b · BE-55 · BE-57 · BE-22 · BE-23 · BE-51 · BE-29 · BE-30 · BE-35 · BE-40 · BE-41 · BE-46 · BE-44 · BE-50 · BE-52 ·
  BE-39 · BE-56 · BE-58 · BE-63 · BE-54 · BE-49 · BE-69 · BE-34 · BE-37
- CDS/DDIC: BE-27 · BE-32 · BE-33 · BE-38 · BE-45 · BE-59 · BE-61 · BE-05 · BE-07 · BE-13 · BE-43
- RAP: BE-26 · BE-20 · BE-60 · BE-06 · BE-21 · BE-24 · BE-08 · BE-09 · BE-17 · BE-53 · BE-42
- OData: BE-14 · OD-01 · OD-02 · OD-03 · OD-04 · OD-05
- clean core: BE-68 · BE-67 · BE-25 · CC-02

Deterministik yakalanabilecek adaylar (açık kalem; kapıya eklemek araç değişikliğidir → kullanıcı onayı):
BE-26 (handler'da commit deyimleri) · BE-20 (`READ ENTITIES … BY \_assoc` anahtar dışı alan) · BE-61 (CDS `"` yorum, SRVD yorum) ·
BE-10b (yetim yorum) · BE-55 (satır içi `TABLE OF` parametre) · BE-49 (adlandırma) · BE-58 (seçim ekranı adı > 8).

## 4. Kaynak ekipte olup aXet'e taşınmayan deterministik kontroller
| Kontrol | Kaynakta | aXet'te |
|---|---|---|
| RAP handler'da commit/rollback deyimi | inceleme listesinde deterministik doğrulayıcıya bağlıydı | yok → BE-26 elle |
| `READ ENTITIES BY \_assoc` yalnız anahtar döner | doğrulayıcıya bağlıydı | yok → BE-20 elle |
| CDS/SRVD yorum sözdizimi | doğrulayıcıya bağlıydı | yok → BE-61 elle |
| Paket/obje adlandırma (klasik include türetme dahil) | doğrulayıcıya bağlıydı | yok → BE-49 elle |
| UI5 freestyle tuzakları, liste ekranı grid standardı | FE listesine bağlıydı | `%sap-ui5-fiori` kapsamı |

## 5. Elle koşum ve okuma
```
# proje kökünden (sap-project.json orada)
python <F>/lib/validators/run_review.py --task class_push --artifact <dosya> --json
```
Ölçüm (2026-09-13, bağlantısız, örnek dosyalarla; `class_push` elle koşuldu — o gün prog/intf push'unda zincir yoktu):
- `.prog.abap` (standart tablodan okuma içeren): `verdict WARNING` · blocker 0 · warning 1. `check_released_objects.py` FAIL
  (standart tablo → halef önerisi); abaplint programı ölçtü (`0 issue / 1 file`); diğer dört gate PASS.
- `.intf.abap` (`TYPE c LENGTH 10` parametreli): `verdict BLOCKER` · blocker 1 · warning 1. `check_method_param_type_c.py` FAIL;
  `check_abaplint.py` SKIP (arayüz desteklenmiyor) → WARNING sayıldı.

2026-09-14'ten beri yazma kapısı bu tiplerde kendi zincirini koşar: prog/include → `program_push`, intf → `interface_push` (§1, §2).
Ölçüm (çevrimdışı, geçici `.prog.txt`/`.include.txt`/`.intf.txt`): `REPORT` satırlı programda abaplint ölçtü; include ve `PROGRAM`
satırlı modül havuzunda `measured=false reason=unsupported-object-type` → SKIP = WARNING, engellemez. Yanıtta `reviewer.unmeasured`
ve `notice`/`gate.review` "ÖLÇÜLEMEDİ" yazar — WARNING'i "temiz" okuma. FM gövdesi (`func`) için elle koşum hâlâ geçerli.

Okuma kuralları:
- `verdict PASS` = zincirin baktığı yerde bulgu yok. `zincir_bos: true` ya da `kosan_gate_sayisi: 0` = hiç gate koşmadı.
- `results[].status == "SKIP"` = ölçülmedi; kendi önemiyle verdict'e sayılır. `message` nedenini yazar.
- `sessiz_bulgu_gates` = gate bulgu bastı ama çıkış 0 verdi; verdict'e sayılmaz, bulgu metni okunur.
- `--cevrimdisi`: SAP'ye ulaşamayan gate'lerin BLOCKER'ı WARNING'e iner; yalnız bağlantı yokken ve
  `offline_downgraded_gates` raporda yazılarak. Gerçek bulgu ve dosyası olmayan gate etkilenmez.
- `--strict`: WARNING'leri BLOCKER karara çevirir (`cleancore_policy: strict` projede clean core satırları için uygun).
- `check_released_objects.py` harita yoksa `SKIP` metni ve `status=SKIPPED measured=false` durum satırı basar, çıkış 0 → `run_review` SKIP (WARNING) sayar (2026-09-14; öncesinde durum satırı yoktu, PASS sayılıyordu).
  Harita durumunu ayrıca `released_successors.py status` ile ölç (CC-03).
- `run_review` `checklist_reference` alanı bugün hep `null`'dır (aXet'te görev → liste eşlemesi boş); inceleme listeleri bu skill'dedir.

## 6. Kaynak ↔ aXet eşlemesi ve alınmayanlar
| Kaynak | aXet'te | Not |
|---|---|---|
| Ekip backend kod-inceleme kontrol listesi (BE-01…BE-70) | `checklist-*.md` altı dosyaya obje tipine göre bölündü; kimlikler korundu | 69/70 satır alındı |
| BE-19 generic iş ortağı value-help | alınmadı | `%sap-rap` checklists §A muhatap value-help satırında (yazma-öncesi, BLOCKER); UI tarafı `%sap-ui5-fiori` |
| BE-43 müşteriye özgü konfigürasyon join vakası | genel kurala çevrildi | `checklist-cds-ddic.md` |
| Kaynaktaki HIGH önem | BLOCKER'a birleşti | inceleme karar dili PASS/WARNING/BLOCKER |
| Bağımsız inceleme ajanı tanımı | `reviewer-brief.md` (taze `agent` + yapıştırılan liste) | araç izin listesi, mesaj aracı, model seçimi alınmadı |
| FE kod-inceleme listesi | alınmadı | `%sap-ui5-fiori` |
| Doküman (KD/FS/TS) inceleme listesi | alınmadı | `%sap-fs-ts-docs` |
| "Review bulgusu → kontrol listesi satırı" ekip dersi | `SKILL.md` §6 | sıradaki kimlik + test zorlaması |
| Ağdan indiren halef haritası yenileme script'i | `scripts/released_successors.py` (yerel dosya, fail-open korumalı) | `clean-core.md` §6 |
| Gate devreye alma dersi (fail-open, yanlış pozitif seli, eski/yeni ihlal) | yenileme script'inin katı davranışı; §3 aday listesi "önce dar, önce uyarı" notuyla | |
| abaplint ayarı ve pin | yazma kapısıyla ortak dosya; `scripts/abaplint_run.py` | `abaplint.md` |
| Profil matrisi politika ekseni, clean core seviyeleri | `clean-core.md` §1-§2 | |
| Clean core karşılık tablosu | `%sap-dev` coding-patterns §7'de zaten var | tekrarlanmadı |
