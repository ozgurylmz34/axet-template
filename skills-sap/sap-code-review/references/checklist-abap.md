# ABAP inceleme satırları — sınıf, arayüz, program, include, fonksiyon modülü, AMDP

> **Kaynak:** ekibin backend kod-inceleme kontrol listesi (kimlikler korunmuştur) + klasik ABAP ve ADT dersleri; aXet'e uyarlandı.
> Önem eşlemesi, tip ve otomasyon açıklaması: `checklist-common.md` başlığı. Yazma-öncesi liste: `%sap-classic-abap` checklists.
> "Aktivasyonda çıkar" işaretli satırlar yerel kontrolleri (run_review, abaplint) **geçer**; statik okumayla aranır, kesin kanıt
> push/aktivasyondur. "Çalışma zamanında çıkar" satırları aktivasyonu da geçer.

## A. Sınıf ve metot imzası — kaydetme taraması (push anında reddedilir)

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-10a | Source-based sınıfta metot imzasında `TYPE c LENGTH n`, CURR tipli DTEL ya da key-user alanına `RANGE OF` → kaydetme taraması satır numarasız 400 | `METHODS`/`CLASS-METHODS` bildirimlerinde `TYPE c LENGTH` ara; `TYPE string` ya da isimli DTEL kullanılmalı | BLOCKER | `class_push` → `check_method_param_type_c.py` (BLOCKER) | Ekip dersi "source-based sınıf TYPE c tuzağı" |
| BE-10b | Yetim yorum: `CLASS … IMPLEMENTATION.` ile ilk `METHOD` arasında ya da `ENDMETHOD.` ile sonraki `METHOD` arasında yorum → push 400 `OO_SOURCE_BASED 012` (satır no yok). DEFINITION bölümünde ve metot gövdesinde yorum serbesttir | Bu iki aralıkta `"` ya da `*` ile başlayan satır ara. Düzeltme: yorumu sil ya da `METHOD x.` satırının altına taşı | BLOCKER | YOK — run_review ve abaplint yakalamaz (kaynakta ölçülmüş); yalnız push reddi | Ekip dersi "yetim yorum → push 400"; `%sap-adt-foundation` known-errors K-20 |
| BE-47 | String template içinde kaçışsız literal `\|` (ör. `}\|{`) → template erken kapanır, kaydetme reddi `OO_SOURCE_BASED 011` | Template içindeki literal `\|`, `{`, `}`, `\` kaçışlı mı (`\\\|`, `\{`, `\}`, `\\`); `}\|{` deseni ara | BLOCKER | Kısmi: `class_push` → `check_abaplint.py` (WARNING) `parser_error` sinyali; kesin: push | Ekip dersi (aynı sınıfta iki kaçak) |
| BE-48 | `METHODS` parametre eklerinin sırası bozuk (doğrusu IMPORTING → EXPORTING → CHANGING → RETURNING → RAISING) → kaydetme reddi `OO_SOURCE_BASED 011` | Çok ekli her imzayı oku; yalnız bildirim düzeltilir, çağrılar etkilenmez | BLOCKER | Kısmi: `class_push` → `check_abaplint.py` (WARNING) `parser_error` sinyali; kesin: push | Ekip dersi |
| BE-55 | Metot/FM/arayüz parametresinde satır içi `TYPE STANDARD TABLE OF …` (anonim tablo tipi) → kaydetme taraması reddi | Parametre eklerinde `TABLE OF` ara; isimli `TYPES tt_x TYPE STANDARD TABLE OF … WITH DEFAULT KEY` kullanılmalı | BLOCKER | YOK — abaplint yakalamaz (kaynakta ölçülmüş); push upload anında reddeder | Ekip dersi |

## B. Aktivasyonda çıkan tip ve sözdizimi tuzakları

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-57 | `RETURNING VALUE(x) TYPE tt_x` ve `tt_x` key ifadesiz tanımlı (`WITH DEFAULT KEY` / `WITH EMPTY KEY` yok) → "fully typed" aktivasyon reddi | Her `RETURNING … TYPE <tablo tipi>` için tip bildiriminde key ifadesi var mı | BLOCKER | YOK | Ekip dersi (aynı tip IMPORTING'de sorun çıkarmadığı için yanıltır) |
| BE-22 | Generic tablo parametresi (`TYPE STANDARD/INDEX/ANY TABLE`) üzerinde `LOOP AT … WHERE comp =` ya da `READ TABLE … WITH KEY comp =` → "row type must be identifiable statically" | Parametre tipi generic mi; somut isimli tablo tipiyle tiplenmeli | BLOCKER | YOK — abaplint yakalamaz | Ekip dersi |
| BE-23 | Somut tiplenmiş parametreye çağıranın farklı key'li yerel tablosu geçiyor → "not type-compatible with formal parameter" | BE-22 düzeltmesinden sonra çağıranların bildirimi aynı isimli tipe çevrildi mi | WARNING | YOK | Ekip dersi (BE-22 türevi) |
| BE-51 | Değişken metin sırasında `DATA` bildiriminden önce kullanılmış → SAP "Field is unknown"; abaplint bildirimi yukarı taşıyıp geçer | Her `CLEAR`/kullanım ile ilgili `DATA` satırının sırası | WARNING | YOK — abaplint yakalamaz | Ekip dersi |
| BE-29 | `COLLECT` hedef tablosunda sayısal olmayan non-key alan → "all non-key components must be numeric" | `COLLECT` ara → hedef satır tipindeki non-key alanlar sayısal mı; değilse key'e al ya da `READ TABLE` + manuel toplama | BLOCKER | YOK | Ekip dersi |
| BE-30 | Yabancı metot çağrısında parametre yönü imzadan doğrulanmamış; ör. `set_table_for_first_display`'de `it_outtab`, `it_fieldcatalog`, `it_sort` CHANGING'dir | Çağrılan metodun imzasını `adt_get` ile oku | WARNING | YOK | Ekip dersi |
| BE-35 | `TYPE char<N>` (N > 40, ör. `char150`) — DDIC'te yok → "Type CHARnnn is unknown" | `TYPE char` + üç haneli ya da 41-99 uzunluk ara; `c LENGTH n`, `string` ya da var olan DTEL | WARNING | YOK | Ekip dersi |
| BE-36 | Alt dize `obj+off(len)`'de `len` hesaplı ifade (`lv_len - 480`, `COND`, metot çağrısı) → ayrıştırma hatası | Önce değişkene hesapla, sonra `obj+off(lv_l)`; literal ve çıplak değişken geçerli | WARNING | Kısmi: `class_push` → `check_abaplint.py` (WARNING) `parser_error` sinyali | Ekip dersi ("parser_error gerçek olabilir") |
| BE-40 | CDS table function çağrısında `@Environment.systemField: #CLIENT` parametresine açık değer (`p_client = sy-mandt`) → "can only be bound by the compiler" | Table function çağrılarında `p_client =` ara; argüman atlanır | WARNING | YOK | Ekip dersi |
| BE-41 | `PERFORM <form> USING` aktüel parametresi string template ya da ifade → "Field \| is unknown" | `PERFORM … USING \|` ara; önce değişkene al ya da FORM yerine metot | WARNING | YOK | Ekip dersi |
| BE-46 | Eski program bağlamındaki user-exit / enhancement include'unda (fixed-point arithmetic kapalı) katı ABAP SQL: `@` host değişkeni, `@DATA(…)`, SELECT listesinde literal, satır içi bildirim → yalnız ana program aktivasyonunda hata | Exit include'unda `@` + ad, `@DATA` ara; klasik SQL + baştan `DATA:` bildirimleri. Tek include sözdizimi kontrolü bağlamsızdır, yanıltır | BLOCKER | YOK | Ekip dersi (kullanıcı kuralı: exit include'larında satır içi bildirim yok) |

## C. Çalışma zamanı mantığı ve performans

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-12 | ATC öncelik 1 bulgusu açık. En sık: `LOOP AT … ENDLOOP` ya da `FOR … IN` içinde `SELECT` (iç içe DB okuması) → toplu okuma + bellekte `READ TABLE`. ATC yalnız obje sistemde derlenince koşar | `adt_atc_check` (okuma aracı; varyant proje politikası) + statik: döngü gövdesinde `SELECT` ara. ATC koşamadıysa "ATC temiz" yazılmaz. Öncelik 2/3 yalnız açık kullanıcı onayıyla geçer | BLOCKER | Kısmi: `adt_atc_check` okuma aracı (zincirde değil, elle); statik kısım YOK | Ekip dersi "ATC öncelik 1 zorunlu"; `%sap-classic-abap` CLC-ATC |
| BE-44 | Döngü içi `SELECT SUM` toplu `FOR ALL ENTRIES` + `COLLECT`'e çevrilirken SELECT listesi kaynak tablonun tam anahtarını içermiyor → FAE örtük DISTINCT eşit satırları teke indirir, toplam sessizce eksik | FAE SELECT listesi ↔ tablo anahtarı; iki eşit miktarlı satır senaryosunu elle izle; COLLECT hedefi yalnız grup anahtarı + miktar | BLOCKER | YOK — ATC, sözdizimi geçer | Ekip dersi |
| BE-50 | Döngü içindeki `DATA` biriktirici/bayrak her iterasyonda sıfırlanmıyor (`DATA … VALUE` bir kez atanır) → önceki satırın değeri sonrakine sızar | LOOP gövdesindeki `DATA` bildirimleri + iterasyon başında `CLEAR` var mı | BLOCKER | YOK | Ekip dersi |
| BE-52 | UNIT tipli alanda dış birim kodu tutuluyor (ya da dış + iç çift birim alanı) → ALV `******` / BM302 ve RAP/EML kaydı genel "kaydetme başarısız" ile reddedilir | Birim alanını dolduran atama `CONVERSION_EXIT_CUNIT_INPUT`'tan geçiyor mu; çift birim alanı var mı | BLOCKER | YOK | Ekip dersi |

## D. Klasik program, include, ALV, seçim ekranı

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-39 | Include push + program aktivasyonu sonrası include hâlâ inaktif; aktif program eski include'u çalıştırır. Birbirine bağımlı tanım/uygulama include çifti tek tek aktive olmaz | Her include için `adt_inactive_objects` + aktif kaynağı `adt_get` ile oku, düzeltme işaretini ara | BLOCKER | YOK (inceleme) | Ekip dersi; `%sap-adt-foundation` known-errors K-10 |
| BE-56 | Programda `TEXT-xxx`, seçim metni ya da buton metni kullanılıyor ama metin havuzu teslim edilmemiş → push yalnız kaynağı taşır, başlıklar boş görünür | Kaynakta `TEXT-` ara + metin havuzunun sistemde dolu olduğunun kanıtı (kullanıcı SAP GUI/ADT'de doğruladı) | BLOCKER | YOK — CLI'de metin havuzu yazma aracı yok (`%sap-dev` araç sınırı) | Ekip dersi; `%sap-classic-abap` CLC-TXT |
| BE-58 | Seçim ekranı adı 8 karakteri aşıyor (`SELECT-OPTIONS` / `PARAMETERS`) → aktivasyon reddi | Seçim ekranı bildirimlerinde ad uzunluğu; `s_<ad>` / `p_<ad>` | BLOCKER | YOK | Ekip dersi; `%sap-classic-abap` CLC-SEL |
| BE-63 | ALV olayında satır `e_row-index` ya da `e_row_id-index` ile okunuyor → sıralı/toplamlı gridde yanlış satır | `INDEX e_row`, `e_row_id-index` ara; `es_row_no-row_id` kullanılmalı | BLOCKER | YOK | Ekip dersi; `%sap-classic-abap` CLC-ALV5 |
| BE-54 | `cwidth_opt` yalnız ilk `set_table_for_first_display`'deki veriye göre optimize eder; boş grid sonradan doldurulursa kolonlar dar kalır | İlk gösterim boş tabloyla mı; `outputlen` ile `cwidth_opt` birlikte mi | WARNING | YOK | Ekip dersi |
| BE-49 | Yeni ya da yeniden adlandırılan objenin adı adlandırma standardına uymuyor (önek; klasik include türetme `_P_` → `_I_` + sonek, kısaltma yok) | `%sap-dev` references/naming.md + paket `.rules.md` Naming tablosu | BLOCKER | YOK — kaynaktaki ad doğrulayıcısı aXet'e taşınmadı | Ekip dersi (router kuralı taşısa da build atladı; inceleme son savunma) |

## E. Fonksiyon modülü ve BAPI

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-69 | FM `TABLES <p> TYPE <x>`'te `<x>` tablo tipi değil (transparan tablo/yapı) → normal FM'de tolere edilir, RFC yapılınca `FL 387`; `STRUCTURE` yazılırsa push `FUNC_ADT 015` | `TABLES` satırları → tipin tablo tipi (TTYP) olduğunu `adt_get` ile doğrula; yeni tablo tipi adı kullanıcı onaylı (`%sap-dev` §6) | BLOCKER | YOK | Ekip dersi; `%sap-odata-backend` dpc-crud §4 |
| BE-34 | S/4 satış belgesi key-user alanları (`ZZ1_*`) BAPI `EXTENSIONIN`'de `BAPE_VBAK` ile geçirilmiş → alanlar sessizce kaybolur; doğru yapı `BAPE_SDSALESDOC` (key/data/datax, `datax` bayrağı zorunlu) | Uzantı yapısı adı ve `datax` atamaları; yapıyı `adt_get` ile oku | BLOCKER | YOK — yalnız belge yaratma + alan geri okuması kanıtlar | Ekip dersi |
| BE-37 | Key-user alanları `EXTENSIONIN`'e ham yapı imajıyla (`valuepart1..4`'e bölerek) geçirilmiş → S/4'te yok sayılır; serileştirme `CL_CFD_BAPI_MAPPING` ile | Mapping sınıfı kullanılıyor mu; imzayı `adt_get` ile doğrula, uydurma | BLOCKER | YOK — çalışma zamanı: yarat + alan geri okuması | Ekip dersi (BE-34'ü düzeltir) |

## F. AMDP

| ID | Ne kontrol edilir | Nasıl | Önem | Otomasyon | Kaynak ders |
|---|---|---|---|---|---|
| BE-28 | AMDP table function: (a) istemci bağımlılığı eksik (`@ClientHandling.type: #CLIENT_DEPENDENT` + `@Environment.systemField: #CLIENT` parametre + metotta `WHERE mandt = :clnt`) · (b) SQLScript gövdesinde (yorumlar dahil) 7-bit dışı karakter · (c) `--` yorumunda apostrof · (d) namespace'li tabloya AMDP içinden erişim | (b) gövdede ASCII dışı karakter ara · (c) `--` satırında `'` ara · (a)(d) okuyarak; kaynak kolon adlarını canlı tablodan doğrula | BLOCKER | Kısmi: `class_push` → `check_amdp_comment_apostrophe.py` (BLOCKER) yalnız (c); (a)(b)(d) YOK | Ekip dersi (yorum apostrofu dört kez tekrarladı) |

## abaplint bulguları — okuma notu
- `parser_error` modern sözdiziminde (EML, RAP, source-based sınıf) ayrıştırıcı kaymasından olabilir, ama BE-36/47/48 gibi **gerçek**
  hataları da gösterir. Körü körüne yanlış pozitif sayılmaz; kesin karar push/aktivasyondur.
- Ölçülmüş yanlış pozitifler (muafiyet değil, önce bunlara bak): CDS table function çağrısı `SELECT … FROM z…( )` → `parser_error`;
  klasik TOP include tek başına `Expected CLASSDEFINITION`.
- abaplint'in yakalamadığı ölçülmüş sınıflar: BE-10b, BE-22, BE-51, BE-55, BE-69. Ayrıntı: `abaplint.md`.

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Müşteri obje adları, vaka tarihleri ve ekip içi dosya yolları çıkarıldı; ders özü ve düzeltme korundu.
- Kaynaktaki HIGH önemler BLOCKER'a birleşti (inceleme kararı dili PASS/WARNING/BLOCKER).
- Commit yasağı (BE-26) RAP dosyasındadır: `checklist-rap.md`. Decimal serileştirme (BE-04): `checklist-odata-backend.md`.
