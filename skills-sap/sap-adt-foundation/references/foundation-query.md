# ADT sorgu ve analiz — SQL, tablo okuma, where-used / blast-radius, ATC, OData metadata

> Kaynak: ekip ADT playbook'u (SQL · where-used · ATC · OData metadata bölümleri) + araç docstring'lerindeki
> ölçülmüş biçim sınırları + tekrarlanan hata kataloğundaki kapsam dersleri; aXet CLI'ye uyarlandı.
> Argümanlar için otorite: `sap_adt_cli.py --list`. Çağrılar kısaca `cli <tool> '{…}'` diye yazıldı.

---

## 1. SQL sorgusu (`adt_sql_query`)

```
cli adt_sql_query '{"query":"SELECT vbeln, posnr FROM vbap WHERE vbeln = '\''0000012345'\''","row_limit":200}'
```
(Tırnak kaçışı kabukta zorsa JSON'u dosyaya yaz.)

- Yalnız `SELECT`/`WITH`. Yazma/DDL anahtar kelimesi reddedilir (Yasak B'nin araç katmanı). `INTO` / `UP TO` **yazma** — SAP kendi ekler.
- **KVKK:** QA/PRD'de hassas tablo/alan/released CDS (müşteri, satıcı, adres, BP, personel, banka, vergi no,
  `BSEG/BKPF/ACDOCA`, `VBAK/VBAP/LIKP/LIPS/VBRK/VBRP` …) okumak için önce kullanıcıya hangi tablo/alanın neden
  okunacağını söyle, net onay al; araçta `acknowledge_risk=true` + `approval_text` (onay kelimesi içerir).
  Takma ad, JOIN, şema öneki, `V_` sarmalayıcı görünümler ve `I_Customer` gibi released CDS'ler de hassas sayılır.
  Tier okunamıyorsa DEV muafiyeti uygulanmaz.

### 1.1 Kırpma — en pahalı tuzak
- `row_limit` varsayılanı 100. Kırpma artık **görünür**: araç `row_limit + 1` satır ister, fazlası gelirse
  `truncated:true` + `truncated_notice` döner (kesin; tam `row_limit` satır kırpık sayılmaz). `total_rows` SAP'nin
  `totalRows` değeridir ve aggregate sorguda alttaki satır sayısıdır → kırpma ondan okunmaz.
- **Ölçülmüş vaka:** limitsiz muhatap tablosu çekimi 551 satırın ilk 100'ünü getirdi → "119 belgenin 80'inde
  muhatap yok" + "10 satır mükerrer riski" diye **yanlış bulgu**; limit büyütülünce 17/17 belgede muhatap vardı,
  gerçek risk 3 satırdı. Başka ölçüm: `row_limit=10` → 10 satır, gerçek 249; `row_limit=300` → 300, gerçek 994.
- **Kural:** `row_limit`'i DAİMA açıkça ver; `truncated:true` ise sonuç eksiktir; sayı gerekiyorsa
  önce `SELECT COUNT(*) AS cnt FROM …` ile beklenen büyüklüğü ölç.

### 1.2 HTTP 400 = "sorgu kabul edilmedi", "tabloya erişemem" DEĞİL

> Buraya gelmeden önce **§1.4**'e bak: 400'lerin bir kısmı standart SQL alışkanlığından doğar
> (`DESC`, nokta ile nitelenmiş kolon, `TRUE`, noktalı virgül). Sözdizimi düzeltmek ölçmekten ucuzdur.
SAP'nin 400/500 sebep metni `sap_error.message` alanındadır (ham ilk 500 bayt `sap_error.body_excerpt`; `message`'a da
`SAP: <sebep>` olarak eklenir). Önce onu oku; körlemesine tekrarlama;
aşağıdaki ölçülmüş biçimlerle **tek değişken** değiştirerek daralt:

| # | Belirti | Sebep (ölçülmüş) | Çare |
|---|---|---|---|
| 1 | Uzun `IN (...)` ya da 5'ten fazla `OR` → 400 | uzun WHERE | 5'erli parçalara böl, sonuçları birleştir |
| 2 | Tahmin edilen kolon adı → 400 | kolon yok | önce küçük `row_limit` ile `SELECT *` → kolonları keşfet, sonra daralt |
| 3 | `tadir.object`, `seoclass.state` → 400 | bağlama göre anahtar kelime çakışması (aynı turda `e071.object` çalıştı; kapsamı ÖLÇÜLMEDİ) | şüpheli kolonu çıkarıp tekrar ölç |
| 4 | `SELECT lgnum, COUNT(*) … GROUP BY lgnum` → 400 | başka kolonla aggregate'te alias şart | `COUNT(*) AS cnt` → 200 |
| 5 | `WHERE vrkme <> meins` → 400 ("must be escaped using @") | çıplak kolon adı host değişkeni sanılıyor | `WHERE vrkme <> lips~meins` → 200 |
| 6 | Tek seferlik 500 (HTML "Application Server Error"), hemen ardından 400 "Session Timed Out" | sorguya ait değil | aynı sorguyu BİR kez tekrarla |
| 7 | `FROM "/SCWM/AQUA"` → 400 | namespace'li ad tırnaklı | tırnaksız yaz: `FROM /scwm/aqua` |
| 8 | `WHERE <kolon> LIKE '%x%'` (sol-joker) → 400; aynı tabloda sağ-joker `LIKE 'S%'` ve eşitlik çalıştı | joker konumu (tek terimde bile) | sağ-jokere çevir ya da kesin değerle daralt |
| 9 | `WHERE datum < '19000101'` → 400 "A Boolean expression was expected" | sorgu mantığı değil; kaynak ders araç katmanında `<`/`>` kaçışını gösterdi (mekanizma DOĞRULANMADI — satır 5'te `<>` 200 döndü) | `BETWEEN` / `NOT BETWEEN` |
| 10 | `DATS` kolonda `LIKE` (`WHERE datum LIKE '%.%'`) → tip uyumsuzluğu | `LIKE` DATS'e uygulanamaz | bozuk tarih araması: `NOT BETWEEN '19000101' AND '99991231'` |
| 11 | Art arda `SELECT *` sonrası 500; `adt_dump_list` → `GENERATE_SUBPOOL_DIR_FULL` (dump, veri önizleme işleyicisinin adına) | aracın geçici subroutine havuzu tükendi; sorgu/view bozuk DEĞİL | açık kolon listesi ver; kolon keşfi için bir kez küçük `SELECT *`; 500'de önce `adt_dump_list` — dump aracın adınaysa biçim değiştirmek işe yaramaz, bekle/seyrelt |

- Çalışan ama "desteklenmiyor" sanılabilen biçim (ölçüldü): `NOT EXISTS ( SELECT * FROM <t2> AS v WHERE v~k = m~k … )`
  alt sorgusu 400 vermez → "X'te olup Y'de olmayan" sorusu iki liste çekip elde fark almadan tek sorguda cevaplanır.
- Bir kez ölçülüp sonraki ölçümde tekrarlanamayanlar (kural DEĞİL): `COUNT(*) AS CNT` → 500 · belirli alanda `<>` → 400 ·
  `SELECT * FROM T320` → 400 · "terim bütçesi" (7 alan + WHERE → 400). Bunların madde 6 kaynaklı olup olmadığı DOĞRULANMADI.
- Genel ders: ADT 400'lerinde sebep gövdededir; "araç bu tipi vermiyor" sonucuna ham sebebi görmeden varma
  (dört ardışık 400'ün dördü de "yanlış biçim" çıktı).

### 1.3 LCHR / uzun metin alanları (ör. `EDID4.SDATA`)
LCHR alanı tek başına okunamaz; **kendinden önceki INT2 uzunluk alanıyla birlikte** ve **açık alan listesiyle** seçilir.
```sql
-- ✅ ÇALIŞIR
SELECT segnum, segnam, dtint2, sdata FROM edid4 WHERE docnum = '<IDOC>'
```
| Deneme | Sonuç |
|---|---|
| `SELECT *` | ⛔ 400 |
| `sdata` (`dtint2` olmadan) | ⛔ 400 |
| `SUBSTRING( sdata, 1, 20 )` | ⛔ 400 — LCHR ifadede kullanılamaz |
| `SELECT segnum, segnam, dtint2, sdata` | ✅ |
- ⛔ Z sınıfı / `adt_classrun` / `IDOC_READ_COMPLETELY` GEREKMEZ (bir kez "ADT bu tipi veremiyor" diye yanlış teşhis edilip gereksiz Z sınıfı yaratıldı).
- `adt_table_read` bu alanda düşer (`SELECT *` yaptığı için) → SQL'i elle yaz.
- IDoc segment ağacı için `SDATA` gerekmez: `segnum`/`segnam`/`psgnum` yeter.
- `SDATA`'yı alanlara kesmek için ofset kaynağı `EDSAPPL`'dir; kolon adlarını tahmin etme (`extlen`/`offset` diye kolon YOK → 400).

### 1.4 ABAP SQL ≠ standart SQL — sık yapılan sözdizim hataları

⚠ **KAYNAK: dış paket belgesi; bu satırlar BU SİSTEMDE ÖLÇÜLMEDİ.** Aşağıdakiler bir üçüncü parti
ABAP SQL referansının iddialarıdır; §1.2'deki 400 sebepleri gibi kendi ölçümümüz DEĞİLDİR. Biri
tutmazsa §1.2'nin daraltma yöntemiyle ölç ve bu tabloyu düzelt (tuttuğunu ölçtüğün satırı
"ölçüldü <tarih>" diye işaretle).

| Standart SQL alışkanlığı | ABAP SQL'de doğrusu |
|---|---|
| `ORDER BY vbeln DESC` | `ORDER BY vbeln DESCENDING` (`DESC` kısaltması yok) |
| `vbap.posnr` (nokta ile niteleme) | `vbap~posnr` (**tilde**) — §1.2 satır 5'teki `lips~meins` çaresi bunun örneğidir |
| `LIKE '%\_%' ESCAPE '\'` | `LIKE '%#_%' ESCAPE '#'` (kaçış karakteri açıkça verilir) |
| `WHERE flag = TRUE` / `false` | `WHERE flag = 'X'` (boş = `' '`) — boolean tipi yok |
| Deyim sonunda `;` | Noktalı virgül YOK |

Zaten §1 başındaki kuralda olanlar (tekrar yazılmasın diye burada değil): `INTO` ve `UP TO`
**yazılmaz** — SAP kendi ekler; satır sınırı `row_limit` argümanıyla verilir (`LIMIT`/`TOP` değil).

### 1.5 Ham `COUNT(*)` ≠ iş nesnesi sayısı
Aynı fiziksel tablo teknik/temsilî kayıtlar da taşıyabilir (gösterge satırı, bir belgenin iki kategoride iki satırı).
Ayırt edici tip/gösterge kolonu filtrelenmezse sayı katlarca şişer ve rapora "ölçüldü" diye girer.
- **Ölçülmüş vakalar (ekip dersi):** bir depo birimi başlık tablosunda ham 5108 satırın ≈266'sı gerçek birimdi
  (gösterge kolonu `'A'` = temsilî satır → 19× şişme); bir referans belge tablosunda her belge iki kategoride iki satır
  taşıyordu (1886 → 994, 2×).
- `COUNT(*)`'dan ÖNCE küçük `row_limit` ile 3-5 satır oku ve sor: bu satırların hepsi gerçekten aynı tip nesnem mi?
  Tip/gösterge/kategori kolonu ara.
- Sayıyı filtresiyle raporla: "5108 (ham) / 266 (`<gösterge> = 'A'` hariç)". Çıplak sayı niteleyiciyi düşürür.
- Gösterge kolonunda `<>` reddedilirse (§1.2) `=` ile ölçüp toplamdan çıkar; sonucu "aritmetik fark" diye nitele.
- Aynı anahtar üçlüsü tekrar ediyorsa kopya sanma: görünmeyen bir anahtar boyutu (parti, UUID) olabilir; `SUM`'dan
  önce onu bul, yoksa aşırı toplama olur.

## 2. Tablo okuma (`adt_table_read`)
```
cli adt_table_read '{"table":"T000","row_limit":50,"columns":"MANDT,MTEXT"}'
```
- WHERE yoktur (`SELECT * FROM tablo`); filtre gerekiyorsa `adt_sql_query`.
- Satırları DAİMA `data.rows_labeled`'dan (kolon→değer) oku. Pozisyonel dizi gözle hizalamada kaydırma hatası üretti (üst üste 3 kez).
- `{ok:false, error:"tablo_okunmadi"}` → okuma koşmadı; "boş tablo" değil.
- KVKK kuralları §1 ile aynı.

---

## 3. Where-used ve blast-radius

### 3.1 Araçlar
| Araç | Neye bakar | Boş sonucun anlamı |
|---|---|---|
| `adt_where_used` | ADT kullanım indeksi (derleyicinin gördüğü) | obje yoksa `OBJECT_NOT_FOUND` ve `count` hiç dönmez; `count:0` yalnız obje varken "doğrudan referans yok" |
| `adt_impact_analysis` | özyinelemeli where-used (`max_depth`, `max_nodes`) | `truncated:true` ise eksik |
| `adt_grep_source` | indirilen kaynak metninde regex | `match_count:0` yalnız `coverage_complete:true` iken "geçmiyor"; aksi hâlde DOĞRULANAMADI |
| `CROSS` tablosu (SQL) | statik FM/program/sınıf çapraz referansı | pozitif kontrolle kalibre edilmeden "yok" yazılmaz |
| yerel `git grep` | repo | canlı sistemi temsil etmez |

### 3.2 `0` "yok" değildir, `>0` "var" değildir
- **Yokluk ≠ tüketicisizlik:** SAP silinmiş obje için de kullanım ucunda `200` + boş liste döner. Orphan
  temizliğinde `count=0` "silinebilir" diye okundu; obje zaten silinmişti. Araç artık varlığı doğruluyor —
  yine de silme kararından önce `adt_get` + `adt_search_objects` ile varlığı ayrıca gör.
- **Arama kapsamı:** `adt_grep_source` fonksiyon grubunda yalnız iskelet ana include'u çeker, FM gövdesini
  **taramaz**; geçmişte `truncated:false` + `scope_verified:true` basıp "temiz" görünüyordu. Bugün bu durumu
  `partial_objects: fugr_skeleton_only` ve `coverage_complete:false` ile bildirir. Sınıf alt-include'ları
  (behavior pool gövdesi `CCIMP`) artık taranır; okunamazsa `class_includes_not_scanned`.
- **Altın sinyal:** `adt_where_used` objeyi listeliyor, `adt_grep_source` 0 diyor → çelişki veri değil **kapsam
  farkıdır; çelişkide indeks haklıdır.** Şüphede tek objeyi elle indir, gözle bak.
- **Ayna hâli:** grep isabeti de kanıt değildir. "Emsal buldum" denen eşleşme bir **yorum satırında**, üstelik
  "X YOK" diyen cümlenin içindeydi. Varlık iddiasını tanımlayıcı satırdan doğrula (`define view` ↔
  `define view entity`, `CLASS … DEFINITION`); çelişkide farklı mekanizmalı üçüncü ölçüm (ör. `adt_get` metadata).
- "Riski kapattım" haberini "risk var" haberinden daha sıkı doğrula: kabul edilirse bir güvenlik ağı kaldırılır.
- **İnceleme zincirinde şiddet kelimesi hüküm değildir:** validator'ın bastığı `BLOCKER`/`WARNING` metni kararı vermez;
  `run_review` her kontrolü zincirdeki şiddetle sayar (`run_review.py` `TASK_VALIDATORS`). Ör. `check_decimal_write_to`
  ve `check_audit_fields_autofill` zincirde WARNING'dir, inceleme kontrol listesinde (`%sap-code-review`) aynı bulgu
  BLOCKER'dır. Karar için verdict'i ve zincir şiddetini oku (2026-09-14 kod okuması; canlı koşum DOĞRULANMADI).

### 3.3 FM çağıranı — kanonik ölçüm `CROSS`
```sql
SELECT * FROM cross WHERE type = 'F' AND name = '<FM_ADI>'
```
- `type='F'` = fonksiyon modülü; sınıf metotlarındaki çağrıları da yakalar.
- **Pozitif kontrol ZORUNLU:** sıfırı raporlamadan önce **çağıranı bilinen** bir FM ile aynı sorguyu koş
  (ölçülen kalibrasyon: bilinen Z FM → 3 satır, üçü doğru). Tablonun dolu olduğunu da ölç:
  `type='F' AND name LIKE 'Z%'` (ölçümde 130 kayıt).
- ⛔ Kalıntı sınır: `CROSS` yalnız statik `CALL FUNCTION '<literal>'` kaydeder. Dinamik çağrı
  (`CALL FUNCTION lv_name`) görünmez → bu senaryoda sonuç **DOĞRULANAMADI**, "yok" değil.
- `adt_where_used(object_type="func")`: yok → `OBJECT_NOT_FOUND` + `probe` · var ama çağıransız →
  `ok:true, count:0, existence_verified:true` · arama/uç hatası → `ok:false` (var olmayan FM ucunda 500).
  `count` yalnız obje referanslarıdır; paket (`DEVC/K`) düğümleri çağıranların atalarıdır ve `package_count` /
  `package_references`'ta ayrı durur (eskiden "4" = 1 çağıran + 3 paket okunuyordu). Yalnız paket düğümü dönerse
  `ok:false, error:"where_used_belirsiz"` — "çağıranı yok" sonucuna varılmaz.
- **Kural:** "çağıranı yok" negatif iddiası tek enstrümana dayanmaz ve pozitif kontrolle kalibre edilmeden yazılmaz.

### 3.4 Kopya/obje silmeden önce
Aynı içerik ≠ aynı kullanım. Silmeden önce her kopyanın tüketicisini ölç (where-used, import/yol dizgesi araması);
referansı olan silinmez (ekip hafızası: "Kopya silmeden önce referans ölç"). Silme yazma sınıfıdır ve onay ister.

---

## 4. ATC ve sözdizimi
```
cli adt_atc_check '{"name":"ZCL_DEMO_CLASS","object_type":"class"}'
```
- Okuma sınıfı; varyant verilmezse `.conn_adt`'deki ATC varyantı, o da yoksa `DEFAULT`.
- Proje politikası (hangi öncelik zorunlu) proje `AGENTS.md`'sindedir; yoksa kullanıcıya sor.
- `adt_syntax_check` **yazma sınıfıdır** (temiz bekleyen sürümü aktive eder; ölçüm: inaktif sayısı 1→0).
  Push zaten sözdizimi kontrolü içerir → ayrı tur gereksiz. `valid:null` = "bakamadım", `valid:false` yalnız `ok:true` iken "hatalı".
- Sözdizimi kontrolü tek otorite değildir: CDS/sınıf etkileşiminde yanlış hata raporlayabilir → aktivasyon sonucuyla
  çapraz doğrula. Ama `parser_error` / "Statement does not exist"i körü körüne yanlış-pozitif sayma: çalışan bir
  referans kaynakla kıyasla.
- ABAP Unit: `adt_unit_run` varsayılan yalnız `harmless` testleri koşar; `allow_risky_tests=true` kalıcı veri
  değiştirebilen testleri de koşar → yazma sınıfı + onay. `method_count:0` → `risk_notice`'u oku.

---

## 5. OData servis ve `$metadata`

- SRVD/CDS değişince yayınlanmış metadata'nın tazelenmesi: `adt_publish_service` (yazma sınıfı).
  `published` üç değerlidir: `true` / `false` / `null` (ÖLÇÜLEMEDİ). Sonuç doğrulaması = `$metadata` okumak.
- Klasik SEGW servisinde Generate + Activate yapılmadan metadata güncellenmez.
- `$metadata` okuma: `GET /sap/opu/odata/SAP/<SERVIS>/$metadata`. ADT CLI'de bunun için araç **yok** (`--list`, 30 araç,
  2026-09-13). Z144 (2026-09-26): `%sap-ui5-fiori` `scripts/fetch_ui_source.py metadata <SERVIS> --alan <Ad> --tip <EntityType>`
  salt okuma okur ve §5.1'deki tip-kapsamlı kontrolü yapar; kimlik geliştiricinin kabuğunda set ettiği env
  `FIORI_TOOLS_USER`/`FIORI_TOOLS_PASSWORD`'dan (deploy_ui ile aynı). Env yoksa kullanıcıdan tarayıcıda açıp ilgili
  `EntityType` bloğunu paylaşmasını iste. Kimlik bilgisi içeren bir script yazma/çalıştırma (aXet çekirdeği §11).

### 5.1 Alan doğrulaması TİP-KAPSAMLI olmalı
- Belge geneli düz metin araması sahte-pozitif verir: metadata iş entity'lerinin yanında altyapı tiplerini
  (`SAP__Signature`, parametre/aksiyon/complex type) de taşır; aynı adlı altyapı property'si "alan var" sandırır
  (iki ajan aynı servis için çelişen sonuç verdi).
- Ters yüz: entity izole edilmeden "yok" hükmü de güvenilmez (projeksiyon farklı adla expose ediyor olabilir).
- **DOĞRU YÖNTEM:** ① ilgili `<EntityType Name="…">…</EntityType>` bloğunu ayır ② alanı yalnız o blokta ara
  ③ `Type`, `MaxLength`, `sap:sortable`, `sap:filterable` değerlerini de oku.
- `sap:sortable="false"` / `sap:filterable="false"` ise UI'da o alana `sortProperty`/`filterProperty` verilmez
  (servis 400 döner).

---

## 6. Kısa dump ve inaktif obje listesi
- `adt_dump_list` (ST22 muadili): çalışma zamanı 500/dump kök nedeni. Dump kaydı kullanıcı adı taşır → DEV dışında `acknowledge_risk`.
- `adt_inactive_objects`: aktive-bekleyen obje listesi. Silinmiş objeler de listede kalabilir (`ioc:deleted` bunu
  söylemez) → araç TADIR `DELFLAG` ile çapraz kontrol eder. `ok:false, error:"tadir_kontrolu_belirsiz"` dalında `count`
  hiç basılmaz; gerçek sayı `confirmed_live_count` ile `confirmed_live_count + unverified_count` arasındadır.
- HTTP 200 = "obje var", "aktif" değil. Kök CDS'e alan eklemek ona bağlı behavior definition'ı (ve servis
  bağlamasını) sessizce inaktif bırakabilir; CDS aktivasyonu onları birlikte aktive etmez. İş bitiminde paket
  bazında inaktif listeyi oku; WIP olabilecek inaktifleri otomatik aktive etme/atma — raporla.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- `run_sql_query.py` / `run_data_preview.py` / `where_used.py` / `run_atc_check.py` → CLI araçları.
- Python `urllib` ile kimlik bilgili `$metadata` okuma şablonu çıkarıldı (düz metin şifre içeriyordu; aXet'te kimlik bilgili script yazılmaz).
- Proje-lokal JSON türevleri, ekip içi validator/checklist kimlikleri, ajan-takımı dili çıkarıldı.
- 2026-09-25 eşitleme (ekip dersleri): §1.2 satır 8-11, `NOT EXISTS` notu ve §1.5 eklendi; kaynaktaki sistem/paket
  adları ile "WHERE terim bütçesi" ve "paralel gönderim" ölçümleri alınmadı (kaynakta çelişen ya da sebebi DOĞRULANMADI).
