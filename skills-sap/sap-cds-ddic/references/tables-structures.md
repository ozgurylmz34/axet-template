# Structure, table type ve Z tablo

> Kaynak: ekip ADT playbook'unun yapı/table type/Z tablo bölümleri + yapı ve tablo güncelleme kontrol listeleri + ilgili ekip dersleri;
> aXet CLI'ye uyarlandı. ADT geneli: `%sap-adt-foundation` (`foundation-ops.md` §3.2 `adt_struct_create` uyarısı).
> Adlandırma: tablo `ZSD001_T_<AD>`, yapı `ZSD001_S_<AD>`, table type `ZSD001_TT_<AD>` (`%sap-dev` → `naming.md` §4.7).
> Ölçümler S/4HANA (`s4_private`) sistemlerde yapıldı. REST akışları teşhis/araç aktarımı içindir.

---

## 1. Structure (TABL/DS)

### 1.1 CLI yolu
1. `cli adt_struct_create '{"name":"ZSD001_S_REPORT","fields":[{"name":"ORDER_NO","type":"ZSD001_E_ORDNO"},{"name":"FLAG","type":"char1"}],"description":"<metin>","package":"<PAKET>","transport":"<TRANSPORT>"}' --sap-write ...`
2. ⚠ Araç "created/activated" deyip SAP'de yalnız yer tutucu bırakabilir (önceki araç setinde ölçüldü):
   ```
   define structure zsd001_s_xxx {
     component_to_be_changed : abap.string(0);
   }
   ```
   `steps.verify.ok:false` / `content_verify.ok:false` / üst `ok:false` → "aktif" diye raporlama.
3. Yer tutucu kaldıysa ya da annotation gerekiyorsa: `cli adt_get '{"name":"ZSD001_S_REPORT","object_type":"structure"}'` →
   `cli adt_push_source '{"name":"ZSD001_S_REPORT","object_type":"structure","source":"<tam DDL>","transport":"<TRANSPORT>"}'` →
   `cli adt_activate '{"name":"ZSD001_S_REPORT","object_type":"structure"}'`.
4. Doğrula (§1.4).

- `artifact_path` gömülü incelemeyi başlatır; önceki araç setinde 120 sn zaman aşımına düştü (`reviewer_timeout`). aXet'te süresi **DOĞRULANMADI**.
- `@AbapCatalog.foreignKey`, `with foreign key`, `with value help`, `@Semantics.amount.currencyCode` **yalnız kaynak push'uyla** yazılır; `fields[]` bunları atlar.

### 1.2 DDL biçimi
```
@EndUserText.label : '<master_language metni>'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
define structure zsd001_s_report {
  order_no : zsd001_e_ordno;
  flag     : abap.char(1);
}
```

### 1.3 Yapıya özgü tuzaklar
**① Kaynak push'u sessiz sahte-OK verebilir.** Önceki araç setinde genel push yardımcısı yapı için "Object activated successfully"
dedi, kaynak **persist etmemişti**: blue-DDIC objelerinde genel kaynak yazımı sessizce yazmıyor, deterministik ham PUT gerekiyordu.
aXet `adt_push_source` `structure` yolunun bu tuzağa düşüp düşmediği **DOĞRULANMADI** → §1.4 readback'i atlanmaz.

**② `adt_post_shell` `structure` desteklenmez** (önceki araç seti `Unsupported object type: TABL/DS`; aXet CLI `unsupported_type` → `adt_struct_create`).

**③ Yapı DDL'i `//` yorumu kabul etmedi.** Yorumlu gövde → `HTTP 400 · ExceptionResourceAlreadyExists · "Can't save due to errors in source"`
(mesaj yanıltıcı: obje var demiyor, kaynak hatalı diyor).

| Varyant | Sonuç |
|---|---|
| annotation + yorum | 400 |
| annotation yok, yorum var | 400 |
| **annotation var, yorum yok** | **200** |
| yorumlar ASCII-only (aynı uzunluk) · 60 karaktere kırpık | 400 |
| yalnız tam-satır yorum · yalnız satır-içi yorum | ikisi de 400 |

Elenen sebepler: annotation, Türkçe/emoji, satır uzunluğu, yorumun konumu. **Sınır:** "`//` hiç kabul edilmez" kesin kanıtlanmadı
(çalışan gövdeye tek `// test` ekleyen minimal deneme koşulmadı; `/* */` denenmedi). **Pratik kural:** yapı DDL'ini yorumsuz tut,
gerekçeyi kardeş `<AD>.README.md` dosyasında sakla → repo ↔ canlı bayt-birebir kalır, readback anlamlı olur.

**④ "Active source differs" — "normaldir" deme, ÖLÇ.** Aynı uyarıyı iki şey üretir:
zararsız SAP normalizasyonu (girinti, yorum/gereksiz annotation atılması — ör. `UNIT` tipli alanda `@Semantics.unitOfMeasure : true` saklanmaz)
**ya da** kaynağın hiç persist etmemesi (canlıda boş/eksik kabuk). Ayırt et: **boyut kıyası** (yüklenen 8.745 karakter ↔ canlı 159 karakter
= sessiz kayıp, pretty-print değil) + `DD03L` alan sayısı.

### 1.4 Doğrulama
1. `adt_get` `structure` → yer tutucu yok, alanlar gönderilen DDL'le aynı, aktif sürüm.
2. `cli adt_sql_query '{"query":"SELECT COUNT(*) AS cnt FROM dd03l WHERE tabname = '\''ZSD001_S_REPORT'\'' AND as4local = '\''A'\''","row_limit":5}'`
   → beklenen alan sayısı (`.INCLUDE` satırları da sayılır; tahmin değil karşılaştırma yap).
3. Kullanılan Z DTEL'lerin aktif olduğu (`adt_get` `dtel`).

### 1.5 Bağımlı obje "inconsistent in active version"
DTEL'in domain'i değişirse (ör. sil-yeniden-yarat) bağımlı tablo + CDS + yapı zinciri yeniden aktivasyon ister. Kaynağın ölçülmüş sırası:
**tablo → CDS → DTEL → yapı**. Yapı aktive olmuyor + `X and Y point to different domains` → Z DTEL'lerin domain'i yabancı anahtar hedefiyle uyumsuz → DTEL tasarımını kullanıcıyla düzelt.

### 1.6 DENENEN — BAŞARISIZ (yapı, önceki araç seti)
| Yöntem | Hata |
|---|---|
| `adt_push_source` `object_type=tabl` ile yapı | `423 Invalid lock handle` → `structure` kullan |
| Genel kaynak push'unda `TABL/DS` tip kodu | `Unsupported object type: TABL/DS` → takma ad `structure` |
| Yaratma XML gövdesinde alan listesi | `400 System expected element blueSource` |
| Transport'u header'da göndermek | `400 Parameter corrNr could not be found` → query parametresi |
| `.../ddic/structures/<ad>?_action=LOCK` | `406` (tüm Accept kombinasyonları); push kendi kilit yolunu kullanır |
| `POST /sap/bc/adt/locks` · merkezi obje kilidi ucu (`/sap/bc/adt` altında `core` → `objectlock`) | `404` |
| Kilitsiz `PUT /source/main` | `400 Parameter lockHandle could not be found` |
| Yapı yaratma script'i / yardımcı fonksiyonu | `CSRF token expired` (3 retry) |
| PowerShell'de heredoc / `--fields` JSON'u komut satırında | ayrıştırma hatası / JSON bozulur → `--args-file` |

---

## 2. Table type (TTYP)

### 2.1 CLI yolu
**Yaratma CLI'de var (2026-09-13; çevrimdışı test edildi, canlı DOĞRULANMADI)** — `%sap-adt-foundation` → `tool-catalog.md` → `adt_post_shell` (`ttyp`):
1. Satır tipi (yapı/DTEL) önce aktif olmalı.
2. `cli adt_post_shell '{"object_type":"ttyp","name":"ZSD001_TT_ORDER","package":"<PAKET>","transport":"<TRANSPORT>","description":"<metin>","extra":{"row_type":"ZSD001_S_ORDER"}}' --sap-write ...`
   → yanıtta `row_type_live` (canlı `typeName` okuması) ve `exists_after`.
3. `cli adt_activate '{"name":"ZSD001_TT_ORDER","object_type":"ttyp"}' --sap-write ...`
4. §2.2 doğrulaması — `row_type_live` dolu olsa da atlanmaz.

**Hâlâ araç yok:** satır tipini düzeltme (If-Match'li PUT, §2.3 — reçete var, araç yok). `ROWTYPE` boş ya da yanlışsa kullanıcı
SE11'de düzeltir; sen §2.2'yi yeniden koşarsın. (Önceki araç setindeki yaratma script'i 403 CSRF veriyordu.)

### 2.2 ZORUNLU doğrulama — `ROWTYPE` boş kalabilir
SAP table type'ı yaratıp satır tipini XML'den **sessizce almayabilir**: obje oluşur, `ROWTYPE` boş kalır; ABAP'ta tip kullanılınca
anlaşılmaz bir çalışma zamanı hatası çıkar.
```
cli adt_sql_query '{"query":"SELECT typename, rowtype FROM dd40l WHERE typename = '\''ZSD001_TT_ORDER'\''","row_limit":5}'
```
Beklenen: `ROWTYPE` = doğru yapı adı. Boşsa kullanıcıya bildir (düzeltme = satır tipini yeniden yazıp aktive etmek). Ayrıca `adt_get` `ttyp` ile XML'de `rowType/typeName` dolu mu.

### 2.3 Protokol notu
- `POST /sap/bc/adt/ddic/tabletypes?corrNr=<TRANSPORT>`; `Content-Type`/`Accept`: `application/vnd.sap.adt.tabletype.v1+xml`
  (v2 ya da başkası 415); namespace `xmlns:ttyp="http://www.sap.com/dictionary/tabletype"` (başkası 415); CSRF yalnız `/sap/bc/adt/discovery`'den (başka uç 403).
- Gövde: `ttyp:rowType` (`typeKind=dictionaryType`, `typeName=<YAPI>`, `builtInType` sıfırlar, `rangeType`), `initialRowCount`,
  `accessType=standard`, `primaryKey` (`standard`, `nonUnique`).
- `400` + `ExceptionResourceAlreadyExists` → var, aktivasyona geç.
- Satır tipi düzeltme: GET ile ETag → aynı XML ile PUT **`If-Match: <etag>` İLE** → yeniden aktive → yeniden `DD40L`.
  ⚠ Bu, "DDIC PUT'ta If-Match gönderme" kuralının **istisnasıdır** (farklı uç ve içerik tipi; ETag yolu burada doğru çalışıyor).
- `TABLES p TYPE x`'te `x` table type olmalı (yapı verilirse RFC işaretlenince `FL 387` — `%sap-adt-foundation` → `known-errors-adt.md` K-15).

---

## 3. Z tablo (TABL/DT)

### 3.1 Önce onay
Yaratmadan önce kullanıcıya tabloyu göster ve açık onay al: tüm alanlar · her alanın DTEL'i · anahtar · uzunluk · delivery class ·
data maintenance · CURR/QUAN referansları. Onaysız yaratma yok (onaysız yaratılan tablo `client : abap.clnt` + ham `char60` alanlarla
çıktı ve düzeltilmek zorunda kalındı).
- İstemci alanı: `key mandt : mandt not null;` (DTEL `MANDT`), `client : abap.clnt` değil (SE11'de "CLIENT" görünür).
- Mümkün her alanda mevcut standart DTEL (ör. varyant adı `VARIANT`, kullanıcı `XUBNAME`, UUID `SYSUUID_X16`, zaman damgası `TIMESTAMPL`); ham `abap.char(n)` son çare.
- Tablo adı **en fazla 16 karakter** (uzunsa SAP "daha kısa ad seç" ile reddetti) — genel 30 karakter sınırından dardır.
- Audit alanları (`created_by` … `last_changed_at`) varsa bloğu **en sonda** tut; RAP tarafında otomatik doldurma ayrı konudur.

### 3.2 Yaratma — kabuk için aXet'te araç yok
**aXet'te araç yok:** yeni Z tablo kabuğu — `adt_post_shell` `tabl` → `unsupported_type` (`%sap-adt-foundation` → `tool-catalog.md`
→ `adt_post_shell` "Desteklenmez"). Önceki araç setindeki tablo yaratma script'i alınmadı.

**aXet'te ara yol:** kullanıcı onaylı tasarımla tabloyu Eclipse ADT'de (varsayılan iskeletle) doğru paket/transportta açar → `cli adt_get '{"name":"ZSD001_T_ORDER","object_type":"tabl"}'` →
`cli adt_push_source '{"name":"ZSD001_T_ORDER","object_type":"tabl","source":"<tam DDL>","transport":"<TRANSPORT>"}'` →
`cli adt_activate '{"name":"ZSD001_T_ORDER","object_type":"tabl"}'` → §3.5. (Varsayılan iskeletin içeriği DOĞRULANMADI; push tam kaynağı yazar.)

**DENENEN — BAŞARISIZ:**
| Yöntem | Sonuç |
|---|---|
| Kabuk POST gövdesine DDL gömmek | `201` ama DDL sessizce düşer, yalnız `client : abap.clnt` kalır |
| Genel kaynak yazma yardımcısı (`If-Match` ile) | `200` döner ama içerik kaydedilmez |
| PUT + `If-Match: <etag>` | `412` (ETag içerik tipine göre değişir, uyuşmazlık kaçınılmaz) |
| `@AbapCatalog.enhancement.category` eksik | `400 "Can't save due to errors in source"` |
| QUAN referansı nitelenmemiş (`'voleh'`) | aktivasyon `annotation uncomplete` |
| Anahtar olmayan alanda `not null` | bazı durumlarda aktivasyon çakışması |

**Protokol notu:** kabuk `POST /sap/bc/adt/ddic/tables?corrNr=<TRANSPORT>`, `application/vnd.sap.adt.tables.v2+xml; charset=utf-8`,
gövde `<blue:blueSource adtcore:type="TABL/DT" adtcore:masterLanguage="…">` + `packageRef` (DDL yok) → kilit
(`Accept: application/*,application/vnd.sap.as+xml;dataname=com.sap.adt.lock.result`, stateful) → `PUT .../tables/<ad>/source/main`
(`text/plain; charset=utf-8`, `lockHandle` + `corrNr`, **If-Match yok**) → kilidi bırak → aktivasyon.

### 3.3 DDL kuralları
```
@EndUserText.label : '<master_language metni>'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #ALLOWED
define table zsd001_t_order {
  key mandt    : mandt not null;
  key order_no : zsd001_e_ordno not null;
  @Semantics.unitOfMeasure : true
  meins        : meins;
  @Semantics.quantity.unitOfMeasure : 'zsd001_t_order.meins'
  menge        : menge_d;
  @Semantics.currencyCode : true
  waers        : waers;
  @Semantics.amount.currencyCode : 'zsd001_t_order.waers'
  netwr        : netwr;
  hu_ident     : /scwm/de_huident;
}
```
1. `@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE` zorunlu (eksikse 400).
2. `not null` **yalnız anahtar** alanda.
3. CURR → CUKY: `@Semantics.amount.currencyCode : '<tablo>.<alan>'` + CUKY alanında `@Semantics.currencyCode : true`.
   QUAN → UNIT: `@Semantics.quantity.unitOfMeasure : '<tablo>.<alan>'` + UNIT alanında `@Semantics.unitOfMeasure : true`.
   Referans **nitelenmiş** (`'tablo.alan'`) olmalı; yalnız `'waers'` → `annotation uncomplete`. Annotation adları büyük/küçük harf duyarlı.
   Referans alanı aynı tabloda olmalı.
4. Tip referansları küçük harf (`mandt`, `zsd001_e_ordno`); standart DTEL doğrudan adıyla (`vkorg`, `kunnr`, `ernam`).
5. **Namespace'li DTEL tırnaksız küçük harf:** `hu_ident : /scwm/de_huident;`. Tek tırnaklı yazım (`'/SCWM/DE_HUIDENT'`) sessizce düşer:
   push "activated" der, "Active source differs from uploaded content" uyarısı çıkar ve **alan tabloya eklenmez** → readback şart.
6. Miktar mı tutar mı kararını **DTEL'in veri tipinden** ver (`adt_get` `dtel` → CURR/QUAN). DTEL adına bakıp "`CURR` değil" demek yanlış:
   önceki üretici `type == 'CURR'` koşulunu DTEL adıyla kıyasladığı için para dalı hiç çalışmadı ve her tutar alanı yanlışlıkla quantity referansı aldı.

Tipik çiftler: `VOLUM`–`VOLEH` · `NTGEW`/`BRGEW`–`GEWEI` · `MENGE`/`KWMENG`/`LFIMG`–`MEINS`/`VRKME` · `NETWR`–`WAERS`/`WAERK` · `DMBTR`–`HWAER` · `KBETR`–`KONWA`.

### 3.4 Mevcut tabloyu değiştirme (ALTER)
1. `adt_get` `tabl` ile güncel DDL (pull-before-edit).
2. Yeni alanları **audit bloğunun üstüne** ekle; yeni DTEL'ler aktif olmalı; CURR/QUAN referansları §3.3.
3. **Alan silme / rename / tip değişikliği = veri kaybı riski.** Rename, silme + yeni alan olarak işler; DTEL değişikliği tip değişikliğidir.
   Önce **yazma yolu analizi**: alana *yazan* kod var mı (ekran bağlama, EML `MODIFY`, `UPDATE`/`MODIFY`, determination) —
   yalnız okuyan CDS exposure "kullanılıyor" demek değildir. `adt_where_used` + `adt_grep_source` ile analizi **sen** yaparsın,
   hükmü ve etkilenen CDS/servis/UI listesini kullanıcıya sunarsın; karar kullanıcınındır. CLI yazma kapısı alan silme BLOCKER'ını
   onaylı geçirmeyi (`ack_drop`) reddeder → silme gerekiyorsa DUR ve riski açıkla.
4. Delivery class değişimi genelde yapılmaz (uyar); standart tabloya append kesin yasak A.
5. Push → aktivasyon → §3.5.

### 3.5 Doğrulama
- `adt_get` `tabl` → gönderilen DDL'le içerik kıyası; "Active source differs" varsa §1.3 ④ ölçümü.
- `DD03L` aktif alan sayısı (§1.4 sorgusu, tablo adıyla).
- `adt_inactive_objects`; tabloya bağlı CDS'ler de aktif mi.
- Silip yeniden yaratma yaptıysan transportta silme kalıntısı: önceki araç setinde toplu "yeniden yarat" seçeneği aynı görevde her objeyi
  iki kez bıraktı (yaratma girdileri ve **sonrasında** silme girdileri, `OBJFUNC='D'`, 9 tablo ölçüldü). Kontrol:
  `SELECT trkorr, as4pos, pgmid, object, obj_name, objfunc FROM e071 WHERE trkorr = '<TRANSPORT>'` → `OBJFUNC='D'` varsa kullanıcıya bildir;
  temizlik SE09'da **kullanıcı işidir**, release edilmeden önce (kesin yasak C). aXet'te `adt_delete` + yeniden yaratmanın aynı izi bırakıp bırakmadığı DOĞRULANMADI.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Tam Python REST şablonları ve toplu CSV script komutları → protokol notu; CSV'nin anlamsal dersi (§3.3 madde 6) kaldı.
- Legacy `TYPE-POOL` yaratma script'i → alınmadı (aXet'te yok; yeni işte tipler sınıf/arayüzde tanımlanır).
- Ortak paket adları, gerçek tablo/yapı adları, sistem client'ı, iterasyon tarihçesi → nötr demo; inceleme zinciri ve kontrol script adları → `checklists.md`'de sade kontrol olarak.
