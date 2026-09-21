# Tablo tipi (TTYP) — ne zaman, nasıl yaratılır, nasıl doğrulanır

> Kaynak: ekip ADT playbook'unun tablo tipi bölümü (yaratma + zorunlu doğrulama + düzeltme), "`TABLES p TYPE <yapı>` gizli hatası"
> dersi, arka uç hata kontrol listesinin iki maddesi (FM `TABLES` tipi · `EMPTY KEY` ↔ `DEFAULT KEY` uyumu) ve RAP RFC sarıcı notu;
> aXet CLI'ye uyarlandı. Araç: `%sap-adt-foundation` → `tool-catalog.md` → `adt_ttyp_create`.
> **Durum (2026-09-21):** `adt_ttyp_create` çevrimdışı test edildi (sahte istemci; boş satır tipi → düzeltme yolu ve "düzeltme sonrası hâlâ boş →
> FAIL" dahil). **Canlı DOĞRULANMADI.** Okuma kalibrasyonu canlı yapıldı: standart bir tablo tipinde (mesaj tablosu tipi) iki ölçüm kanalının
> eşlemesi (aşağıda §4.2) okundu. Bu dosya kendi başına okunur; başka dosyaya bakmadan iş yapılabilir.

---

## 1. Tablo tipi ne zaman gerekir — önce gerekmediğinden emin ol

Yeni tablo tipi **yeni bir DDIC objesidir**: adı ve kısa metni kullanıcıdan gelir, transporta girer, bakımı vardır. Önce şunlara bak:

| Durum | Tablo tipi gerekir mi |
|---|---|
| Fonksiyon modülünde `TABLES p TYPE x` | **Evet** — `x` tablo tipi olmak zorunda (§5.1). `STRUCTURE` yazımı ADT yüklemesinde reddedilir. |
| RFC ile çağrılacak FM'in tablo parametresi | **Evet** (yukarıdakiyle aynı; hata ancak RFC işaretlenince çıkar — §5.1). |
| Sınıf / arayüz metodunda `RETURNING VALUE(r) TYPE <tablo>` ya da `TYPE <tablo>` parametresi | Çoğunlukla **hayır**: sınıf/arayüzde `TYPES tt_x TYPE STANDARD TABLE OF <yapı> WITH DEFAULT KEY.` yeter. `RETURNING` tam tipli ister → anahtar ifadesi (`WITH DEFAULT KEY` / `WITH EMPTY KEY`) **yazılmalı**. Birden çok programda paylaşılacaksa DDIC tipi düşün. |
| Mesaj tablosu (BAPI dönüşü) | **Hayır** — standart `BAPIRET2_T` hazır. Yeni tip yaratma. |
| Yalnız bir programın içinde | **Hayır** — yerel `TYPES`. |
| RAP / CDS tarafında `[0..*]` sonuç | **Hayır** — koleksiyon döner. |

Karar kuralı: **hazır standart tip var mı** (`adt_search_objects` ile `*_T` / `*_TAB` ara, satır tipini `adt_get` ile gör) → yoksa ve
DDIC seviyesi gerçekten gerekiyorsa yeni tip.

## 2. Ad — öner, canlıda yokluğunu ölç, onay al

- Kalıp: `<gövde>_TT_<AD>` (ör. `ZSD001_TT_ORDER`; gövde = paketin adlandırma gövdesi — `%sap-dev` → `naming.md`).
- Satır tipiyle aynı konu adını kullan (yapı `ZSD001_S_ORDER` → tip `ZSD001_TT_ORDER`).
- **Canlı kontrol:** `cli adt_get '{"name":"ZSD001_TT_ORDER","object_type":"ttyp","include_source":false}'` → `exists:false` olmalı.
  `exists:null` = ölçülemedi, "yok" değildir.
- Adı, kısa metni (master_language'de), satır tipini, erişim türünü ve anahtarı **kullanıcıya göster, açık onay al**. Onaysız yaratma yok.

## 3. Yaratma — tek komut

Satır tipi (yapı / tablo / DTEL) **önce aktif** olmalı (`adt_get` ile gör).

```
cli adt_ttyp_create --args-file ttyp.json --sap-write --scope S1 --reason "<gerekçe>"
```

`ttyp.json` — sözlük satır tipi, varsayılan tanım (standart tablo + standart anahtar):
```
{"name":"ZSD001_TT_ORDER","description":"<master_language metni>","package":"<PAKET>","transport":"<TRANSPORT>",
 "row_type":"ZSD001_S_ORDER"}
```
İlkel satır tipi:
```
{"name":"ZSD001_TT_DOCNO","description":"<metin>","package":"<PAKET>","transport":"<TRANSPORT>",
 "builtin":{"data_type":"CHAR","length":10}}
```
Sıralı / anahtarlı:
```
{..., "row_type":"ZSD001_S_ORDER","access_type":"sorted","key_definition":"keyComponents",
 "key_kind":"unique","key_components":["ORDER_NO"]}
```

### 3.1 Parametreler — neyi destekler, neyi desteklemez
| Parametre | Değerler | Not |
|---|---|---|
| `row_type` | yapı / tablo / DTEL adı | `typeKind=dictionaryType`. `builtin` ile birlikte verilmez. |
| `builtin` | `{"data_type":"CHAR"\|"NUMC","length":N}` · `{"data_type":"DEC","length":N,"decimals":D}` · `{"data_type":"STRING"\|"INT4"\|"DATS"}` | `typeKind=predefinedAbapType`. Bu altı tip canlı okumada görüldü; başkası reddedilir. |
| `access_type` | `standard` (varsayılan) · `sorted` · `hashed` | |
| `key_definition` | `standard` (varsayılan) · `rowType` · `keyComponents` | `keyComponents` → `key_components` listesi zorunlu; ilkel satırda verilmez. |
| `key_kind` | `nonUnique` · `unique` | Verilmezse: `hashed` → `unique`, diğerleri `nonUnique`. **`standard` + `unique` ve `hashed` + `nonUnique` reddedilir** (canlı DD40L'de bu iki bileşim hiç yok). |
| `transport` | İSTEK numarası | `$TMP` paketinde verilmeyebilir. |

**Desteklenmez (`preflight_blocker`, SAP'ye gidilmez):** aralık tablosu (`rangeTypeOnPredefinedType` / `rangeTypeOnDataelement`) · referans
satır tipi (`refTo…`) · satırı tablo tipi olan iç içe tip · boş anahtar (`notSpecified`) / genel tip · ikincil anahtar. Bunlar gerekirse
kullanıcı SE11'de yaratır; sen §4 doğrulamasını elle koşarsın.

### 3.2 Aracın yaptığı sıra
1. Ağsız ön kontrol (yukarıdaki kurallar). 2. Canlı varlık sondası (var → `already_exists`; ölçülemedi → `exists_unmeasured`, yaratma yok).
3. `POST /sap/bc/adt/ddic/tabletypes?corrNr=<TRANSPORT>` — `Content-Type: application/vnd.sap.adt.tabletype.v1+xml`, namespace
   `http://www.sap.com/dictionary/tabletype`. 4. Aktivasyon + metadata `version=active`. 5. **İki kanallı readback** (§4). 6. Gerekirse düzeltme (§4.3).

## 4. Doğrulama — neden iki kanal

SAP tablo tipini yaratıp satır tipini XML'den **sessizce almayabilir**: obje oluşur, aktive olur, `ROWTYPE` boş kalır. ABAP'ta tip
kullanılınca anlaşılmaz bir çalışma zamanı hatası çıkar. "Yaratıldı / aktive edildi" mesajı bunu göstermez.

### 4.1 Kanallar
- **DD40L (birincil):** `SELECT typename, rowtype, rowkind, datatype, leng, decimals, accessmode, keydef, keykind FROM dd40l WHERE typename = '<AD>' AND as4local = 'A'`
- **ADT XML:** `GET /sap/bc/adt/ddic/tabletypes/<ad>?version=active` → `rowType/typeName` (sözlük) ya da `builtInType/dataType` (ilkel), `accessType`, `primaryKey/definition`, `primaryKey/kind`.

### 4.2 Eşleme (canlı okumayla ölçüldü, 2026-09-21)
| XML | DD40L |
|---|---|
| `accessType` standard / sorted / hashed | `ACCESSMODE` T / S / H |
| `definition` standard / rowType / keyComponents | `KEYDEF` D / T / K |
| `kind` nonUnique / unique | `KEYKIND` N / U |
| `typeKind` dictionaryType | `ROWKIND` S (yapı/tablo) ya da E (DTEL); `ROWTYPE` = ad |
| `typeKind` predefinedAbapType | `ROWKIND` boş, `ROWTYPE` boş; `DATATYPE` + `LENG` (+ `DECIMALS`) |
| `dataType` STRING | `DATATYPE` STRG |

Kalibrasyon (kontrol grubu): standart mesaj tablosu tipi → `ROWTYPE=BAPIRET2 · ROWKIND=S · DATATYPE=STRU · ACCESSMODE=T · KEYDEF=D · KEYKIND=N`.
İlkel satırda "satır tipi dolu" ölçüsü `ROWTYPE` değil `DATATYPE`'tır (ROWTYPE ilkelde zaten boştur).

### 4.3 Karar tablosu (araç bunu uygular)
| DD40L | XML | Sonuç |
|---|---|---|
| okunamadı / aktif satır yok | — | `readback_unmeasured` (`ok:false` — ölçülemedi "doğru" değildir) |
| boş | boş ya da okunamadı | **düzeltme:** GET ile ETag → **aynı XML** ile `PUT` + `If-Match: <etag>` → yeniden aktivasyon → yeniden iki kanal (`repair.trigger:"bos"`) |
| boş | dolu | `readback_channels_disagree` (FAIL; kanallardan biri kör — kullanıcıya bildir) |
| dolu | boş | `readback_channels_disagree` |
| dolu | okunamadı | `readback_unmeasured` |
| dolu | dolu | tanım kıyası: erişim / anahtar tanımı / anahtar türü / satır tipi / ilkel uzunluk + **ondalık** (DEC: DD40L `DECIMALS`) → fark yoksa OK; fark varsa **aynı düzeltme** (`repair.trigger:"uyumsuz"`) → yeniden iki kanal → hâlâ farklıysa `readback_mismatch` |

İlkel tipte uzunluk/ondalık yalnız tip onu **istiyorsa** kıyaslanır (CHAR/NUMC uzunluk · DEC uzunluk + ondalık). DD40L `LENG`/`DECIMALS`
her zaman kıyaslanır (okunamazsa fark yazılır). XML `builtInType/length`·`decimals` yalnız **sayı olarak okunabildiyse** kıyaslanır;
etiket yok / boş / sayı değil = o kanalda ölçülemedi → fark **uydurulmaz** (birincil ölçü DD40L). ⚠ XML `length` ile DD40L `LENG`'in
aynı birimde olduğu canlıda ÖLÇÜLMEDİ (yalnız yazım gövdesi aynı değeri gönderir) — ilk canlı ilkel tipte XML `length` farkı çıkarsa
önce bu varsayımı sorgula.

Düzeltme **bir kez** denenir. Sonrasında hâlâ boşsa `row_type_empty_after_repair`, hâlâ farklıysa `readback_mismatch` → **FAIL; asla "OK" denmez.** Obje silinmez;
kullanıcıya bildir (SE11'de bakar). Düzeltme PUT'u düşerse (ya da ETag alınamazsa — If-Match'siz PUT denenmez)
`row_type_empty_repair_failed` (boş satırda) / `readback_mismatch_repair_failed` (farklı tanımda). Düzeltme PUT'u geçip yeniden aktivasyon
düşerse `activation_failed_after_repair`. Onarım sonrası nihai `ok` **ikinci** aktivasyonun metadata doğrulamasından gelir (`steps.verify_2`;
`active` değilse `verify_failed`).

**Canlı ölçüm (2026-09-21, DEV, `$TMP`) — neden `uyumsuz`da da onarılır:** dört yaratımın DÖRDÜNDE de POST gövdesindeki satır tanımı
DÜŞTÜ; SAP varsayılanı kaldı: `DATATYPE=CHAR · LENG=000001 · DECIMALS=000000 · ACCESSMODE=T · KEYDEF=D · KEYKIND=N` (ROWTYPE NULL; XML'de
`predefinedAbapType` + `CHAR` + `000001`). Yapı satırlıda bu `bos` olarak yakalandı ve If-Match PUT onarımı tanımı kabul ettirdi — sıralı +
`keyComponents` + tekil kombinasyonunda erişim ve anahtar da PUT ile geldi (`ACCESSMODE=S · KEYDEF=K · KEYKIND=U`). İlkel satırda (CHAR 10 ·
DEC 15,2) varsayılan CHAR "dolu" göründüğü için `uyumsuz` çıktı ve o sürümde onarım denenmedi (`readback_mismatch`).
- ⚠ **İlkel satırda PUT onarımı canlıda henüz ÖLÇÜLMEDİ** — bu düzeltme sonrası ilk canlı koşu ölçer.
- ⚠ **POST gövdesindeki satır tanımı (`<ttyp:rowType>` … `<ttyp:components>`) canlıda KANITLANMADI** — ölçülen dört yaratımın hepsinde düştü;
  kanıtlı yol yalnız **PUT** (If-Match) yoludur. POST'un tek işlevi bugün kabuğu yaratmaktır.
- XML `length` ile DD40L `LENG` bu turda aynı değeri gösterdi (varsayılan CHAR'da ikisi de `000001`; tek örnek).
⚠ Düzeltme PUT'unda `If-Match` **gönderilir** — Z tablo kaynağı PUT'unda gönderilmez; bu fark bilinçlidir (farklı uç, farklı içerik tipi;
kaynak ekip bu uçta ETag yolunun çalıştığını ölçtü). Genelleme yapma.

### 4.4 Elle doğrulama (araç dışı yaratılan tipler için)
```
cli adt_sql_query '{"query":"SELECT typename, rowtype, rowkind, datatype, accessmode, keydef, keykind FROM dd40l WHERE typename = '\''ZSD001_TT_ORDER'\'' AND as4local = '\''A'\''","row_limit":5}'
cli adt_get '{"name":"ZSD001_TT_ORDER","object_type":"ttyp"}'
```
Tablo tipinin kaynak ucu (`source/main`) **yoktur**; okuma obje XML'inden yapılır.

## 5. Anahtar tanımı ↔ ABAP ve RFC'de ortaya çıkan gizli hatalar

### 5.1 `TABLES p TYPE <yapı>` — FM RFC yapılana kadar sessiz
- FM'de `TABLES p TYPE x`, `x` yapı ya da transparan tabloysa normal işlem türünde **tolere edilir** (aktive olur, kontrol temiz).
  FM **Remote-Enabled** işaretlenince aktivasyon `FL 387 — Type <X> is not a table type` ile düşer → "çalışıyordu, RFC bozdu" sanılır; kusur baştan vardı.
- Kural **yalnız `TABLES`'a** özgüdür: aynı imzada `IMPORTING VALUE(x) TYPE <transparan tablo>` hata vermedi (kaynak ekip ölçtü).
- İki kısıt birden: `STRUCTURE` yazımı ADT yüklemesinde `400 FUNC_ADT 015 "Parameter <P> declares no type"` ile reddedilir; `TYPE`
  sonrasında da tablo tipi gerekir ⇒ tek geçerli biçim `TABLES p TYPE <tablo_tipi>`.
- Önlem: FM yazarken `TABLES` satırlarındaki her tipin `DD40L`'de satırı olduğunu ölç (`%sap-classic-abap` → `fugr-fm.md` §2.1).

### 5.2 Standart anahtar = `DEFAULT KEY`, `EMPTY KEY` değil
- DDIC "standart anahtar" (`KEYDEF = D`) ABAP'taki **`WITH DEFAULT KEY`**'dir.
- FM, aldığı `TABLES` tablosunu içeride DDIC tablo tipiyle yazılmış bir `CHANGING` (ya da referansla geçen `IMPORTING`) parametresine
  devrederse ABAP **uyumluluk** arar (dönüştürülebilirlik yetmez). Çağıranın aktüeli yerel `TYPES … WITH EMPTY KEY` ise
  sözdizimi denetimi, aktivasyon ve statik kontroller **geçer**, hata **çalışma zamanında** `CX_SY_DYN_CALL_ILLEGAL_TYPE` olur.
- Önlem: böyle bir FM'e tablo veren çağıranda yerel tipi DDIC tipiyle aynı anahtarla tanımla (`WITH DEFAULT KEY`) ya da doğrudan DDIC tipini kullan.
- `rowType` anahtar tanımının (`KEYDEF = T`) ABAP karşılığı bu evde ölçülmedi — **DOĞRULANMADI**; kullanmadan önce çağıranla birlikte dene.

### 5.3 `RETURNING` tam tip ister
`RETURNING VALUE(r) TYPE tt_x` için `tt_x` anahtar ifadesiz (`TYPES tt_x TYPE STANDARD TABLE OF x.`) tanımlıysa aktivasyon "fully typed"
reddi verir → `WITH DEFAULT KEY` ya da `WITH EMPTY KEY` yaz, ya da DDIC tablo tipi kullan.

## 6. DENENEN — BAŞARISIZ (tekrar deneme)
| Deneme | Sonuç |
|---|---|
| Kaynak ekibin eski tablo tipi yaratma script'i (genel CSRF yolu) | `403` CSRF — CSRF yalnız `/sap/bc/adt/discovery`'den alınınca geçti (aXet kütüphanesi on-prem'de zaten oradan alır) |
| `Content-Type` `…tabletype.v2+xml` ya da başka tip | `415` |
| Başka XML namespace | `415` |
| `corrNr`'ı başlıkta göndermek | reddedilir → sorgu parametresi |
| Yaratma + aktivasyon sonrası "tamam" demek | `ROWTYPE` **sessizce boş** kalabildi → iki kanal readback zorunlu |
| Satır tipini `adt_push_source` ile yazmak | tablo tipinin kaynak ucu yok (`source/main` 404) → XML PUT (§4.3) |
| FM'de `TABLES p STRUCTURE <yapı>` | `400 FUNC_ADT 015` |
| FM'de `TABLES p TYPE <yapı>` + RFC | `FL 387` (RFC işaretlenince) |
| `400 ExceptionResourceAlreadyExists` | obje zaten var — tekrar yaratma; `adt_get` ile incele (araç `already_exists` döner) |

## 7. Kapsam beyanı
- Araç **mevcut** tablo tipini değiştirmez (yalnız kendi yarattığında satır tipi düzeltmesi yapar).
- `keyComponents` için yazılan XML biçimi okuma sonucundan türetildi (`<ttyp:components>` + `<ttyp:component ttyp:name="…"/>`); POST'ta canlı DOĞRULANMADI.
- Ad-alanlı (`/ns/`) satır tipleri denenmedi.
- Eski kabuk yolu `adt_post_shell` `ttyp` (yalnız sözlük satır tipi, düzeltme yok) duruyor; yeni işte `adt_ttyp_create` kullan.
