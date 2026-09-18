# ABAP kodlama desenleri ve tuzakları

> ABAP kodu yazmadan önce ilgili bölümü oku. ADT protokol tuzakları (yaratma dili, kilit, 409, aktivasyon
> doğrulaması) `%sap-adt-foundation` referanslarındadır; burada tekrarlanmaz.
> Profil notu: §4 ve §7'deki released CDS'ler S/4HANA içindir (`s4_private`, `s4_public`); `ecc`'de yoktur.

## 1. Range parametresi — imzada `RANGE OF` yok

Method ya da fonksiyon parametresinde `TYPE RANGE OF xyz` yazılamaz (aktivasyon hatası). `RANGE OF` yalnız
yerel `DATA` tanımında geçerlidir.

| Durum | Yapılacak |
|---|---|
| Standart alan için range parametresi | SAP'de hazır range table type vardır ama adını tahmin etme: `adt_search_objects` / where-used ile bul ya da kullanıcıya sor, sistemde doğrula |
| Z alan için range parametresi | Yapı (`SIGN` `DDSIGN`, `OPTION` `DDOPTION`, `LOW`/`HIGH` Z data element) + table type yarat (adlar kullanıcı onaylı), imzada table type kullan |
| Metot içi yerel range | `DATA lt_range TYPE RANGE OF xyz.` sorunsuz |

```abap
METHODS constructor
  IMPORTING it_price_list TYPE zsd001_tt_sel_price.   " doğru
"           it_price_list TYPE RANGE OF zz1_price_code. " yanlış — aktivasyon hatası
```

Aynı aile: source-based sınıf imzasında `TYPE c LENGTH n` kaydetme taramasını bozabilir → `TYPE string` ya da
data element kullan.

## 2. `FOR ALL ENTRIES` ile `GROUP BY` birlikte kullanılamaz

**Yol A (önerilen, S/4HANA 1909+):** iç tabloyu `FROM` içinde join et; iki pragma zorunlu.

```abap
TYPES: BEGIN OF ty_filter,
         order_no TYPE vbeln,
         item_no  TYPE posnr,
       END OF ty_filter.
DATA lt_filter TYPE HASHED TABLE OF ty_filter WITH UNIQUE KEY order_no item_no.

lt_filter = VALUE #( FOR ls IN mt_orders ( order_no = ls-order_no item_no = ls-item_no ) ).

IF lt_filter IS NOT INITIAL.
  SELECT l~vgbel AS order_no,
         l~vgpos AS item_no,
         SUM( l~lfimg ) AS total_qty
    FROM lips AS l
    INNER JOIN @lt_filter AS fil
      ON  fil~order_no = l~vgbel
      AND fil~item_no  = l~vgpos
    GROUP BY l~vgbel, l~vgpos
    INTO TABLE @DATA(lt_result)
    ##db_feature_mode[itabs_in_from_clause] ##itab_db_select.
ENDIF.
```

**Yol B:** ham satırları çek, ABAP'ta topla (`LOOP` + hashed tablo `ASSIGN`).

| Durum | Yöntem |
|---|---|
| Hedef alan küçük tip | Yol A |
| Hedef alan büyük tip (ör. CURR 34,2 — `SUM` sığmaz) | Yol B zorunlu |
| İç tablo çok büyük (100 bin+ satır) | Yol B daha güvenli |

Standart tabloyu **okumak** yasak değildir; released CDS varsa onu tercih et (§7). Yazmak kesin yasak B'dir.

## 3. İç tablo boş kontrolü — `FOR ALL ENTRIES` öncesi zorunlu

`FOR ALL ENTRIES IN lt_x` içinde `lt_x` boşsa SAP `WHERE` koşulunu yok sayar ve **tüm tabloyu çeker** (hem
performans hem yanlış veri).

```abap
IF lt_customers IS NOT INITIAL.
  SELECT matnr, netpr FROM a004
    FOR ALL ENTRIES IN lt_customers
    WHERE kunnr = lt_customers-kunnr
    INTO TABLE @lt_prices.
ENDIF.
```

- `WHERE … IN @lt_range` boş range'de tümünü çeker: bu beklenen davranıştır ("kriter yok").
- `INNER JOIN @lt_itab` boşsa sonuç boştur; gereksiz veritabanı çağrısını önlemek için yine kontrol et.

## 4. Kur dönüşümü — `TCURR` yerine `I_ExchangeRate`

`TCURR` doğrudan kullanılmaz: `GDATU` ters tarih (`99999999 - YYYYMMDD`) karakter alanıdır, `FFACT`/`TFACT` sıfır
olabilir, `UKURS` tek başına yetmez. `I_ExchangeRate` düz tarih ve hazır efektif kur verir.

```abap
IF lt_all_waers IS NOT INITIAL AND lt_target_waers IS NOT INITIAL.
  SELECT SourceCurrency        AS fcurr,
         TargetCurrency        AS tcurr,
         EffectiveExchangeRate AS exchrate
    FROM I_ExchangeRate AS er
    INTO TABLE @lt_rates
    WHERE er~ExchangeRateType = 'M'
      AND er~SourceCurrency IN @lt_all_waers
      AND er~TargetCurrency IN @lt_target_waers
      AND er~ExchangeRateEffectiveDate =
            ( SELECT MAX( e2~ExchangeRateEffectiveDate )
                FROM I_ExchangeRate AS e2
               WHERE e2~ExchangeRateType          = er~ExchangeRateType
                 AND e2~SourceCurrency            = er~SourceCurrency
                 AND e2~TargetCurrency            = er~TargetCurrency
                 AND e2~ExchangeRateEffectiveDate <= @sy-datum ).
ENDIF.
```

Uygularken sıfır kur kontrolü: `IF sy-subrc = 0 AND <rate>-exchrate <> 0.` Kur tipi `M` standart ortalama
kurdur; projede farklıysa spesifikasyondan al.

## 5. ABAP yazım tuzakları
- Obje ve sınıf adı en fazla 30 karakter; uzun ad sessizce kesilip aktivasyonu bozabilir.
- Deyim sonu nokta (`.`), noktalı virgül değil.
- `OBLIGATORY` yalnız seçim ekranında geçerlidir; sınıf `IMPORTING` parametresinde yoktur.
- `CONDENSE` karakter/`string` ister; `lines( )` dönüşü `TYPE i`'dir.
- Seçim ekranı başlık/açıklamasını `TEXT-xxx = '…'` ile değiştirme; serbest değişken (`tit1`, `com01`) kullan,
  `INITIALIZATION`'da ata.
- Sistemde olmayabilecek tip ya da alan (sürüme göre değişen standart alanlar) kullanmadan önce sistemde oku.
- Eski sistemden kopyalanan standart tablo/alan adlarını hedef sistemde doğrula.
- Klasik program tek gövde yazılmaz: ana program yalnız `INCLUDE` satırları ve olay blokları; kod include'lara
  (`references/naming.md` §4.1).
- Metot silinince önündeki ABAP Doc yorumunu da sil: sahipsiz yorum sınıf push'unda 400 döndürebilir.

**Ekip kodlama kuralları:**
- `CHECK sy-subrc = 0.` yazma; `IF sy-subrc = 0. … ENDIF.` kullan (akış görünür kalır).
- Sabit değer listesini SELECT içine gömme; bir range değişkeninde (`sign`/`option`/`low`) topla, aynı range'i birden
  fazla SELECT'te kullan.
- Toplam ve aritmetiği SQL'de yap (`SUM … GROUP BY`, JOIN ile birim fiyat); ABAP döngüsünde toplama yapma
  (büyük tipte `SUM` sığmıyorsa §2 Yol B).
- Başta belli olan sonuç tablosunu döngüde `READ` + `INSERT` ile değil `VALUE #( FOR … )` ile kur. Satır içi
  `FIELD-SYMBOL(<x>)` aynı kapsamda iki kez tanımlanamaz; gerekiyorsa DATA bloğunda tanımla.

**Bilinen tuzak — standart tablo alanını DDL metninde aramak.**
- **Belirti:** "`MARA.MATKL` yok", "`LIKP.WBSTK` yok" hükmü; alan gerçekte vardır. Elle yazılan bir kontrol script'i ya da
  `adt_get` kaynağında metin araması CDS/ABAP kodunda sahte "alan yok" bulgusu üretir.
- **Kök neden:** S/4'te standart tablo alanlarının çoğu DDL gövdesinde değil `include` zincirindedir. Ölçüm: `MARA` gövdesinde
  doğrudan yalnız `key mandt` ve `key matnr` durur, gerisi `include emara` zincirinden gelir; `LIKP` durum alanları
  `include likp_status` içindedir ve ham metinde `wbstk` hiç geçmez. Include tabanlı şemayı düz metin gibi okuyan araç
  "yok" derken aslında "bakmadım" der.
- **Doğru yol:** alan varlığını include zincirini özyineli çözerek ya da sözlük tablosundan doğrula
  (`SELECT fieldname FROM dd03l WHERE tabname = '<TABLO>' AND fieldname = '<ALAN>'`). ⚠ `DD03L`'in include'dan gelen alanları
  satır olarak listelediği aXet'te ölçülmedi — **DOĞRULANMADI**: ilk kullanımda kontrol grubuyla ölç (gövdedeki `MARA`-`MATNR` +
  include'dan gelen `MARA`-`MATKL`). Zincirin bir kısmı çözülemediyse sonuç "yok" değil **DOĞRULANAMADI**. CLI'nin gömülü
  `check_standard_table_fields` doğrulayıcısı zinciri özyineli çözer ve çözemediği alanları ayrı listeler (kaynak: script başlık notu).
- Kaynak vaka: 2026-07-30.

## 6. İşletim tuzakları
- **Hata mesajındaki transport numarasını kullanma.** "Obje şu transportta" mesajındaki numara başka
  geliştiriciye ait olabilir; DUR ve kullanıcıya sor.
- Push başarılı olunca SAP transportun altına görev (task) açabilir; bu normaldir.
- "Already exists" yanıtı başarı kanıtı değildir: `adt_get` ile objenin beklenen paket, tip ve açıklamada
  olduğunu doğrula (başka birinin objesi olabilir).
- Aktivasyondan sonra çalışma zamanında değişiklik görünmüyorsa sunucu tampon belleği eski olabilir: yeniden
  aktive etmeyi ya da tampon sıfırlamayı (`/$ABAP_BUFFER_RESET`, çok sunuculu sistemde her sunucuda) kullanıcıya
  öner; kendin yapma.
- Silme onaysız yapılmaz; where-used temiz olmadan silinmez.
- Yerel yardımcı Python script'i yazıyorsan Windows konsolu (`cp1252`) Unicode basamayabilir:
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` ya da ASCII çıktı. Geçici script `.tmp/`'ye.

## 7. Clean core — standart obje yerine ne kullanılır
Standart tabloyu okumak yasak değildir; yeni okuma modelinde released CDS/API tercih edilir. Yazma her durumda
BAPI / RFC FM / BDC ile yapılır (kesin yasak B).

| Standart obje | Yerine (released) |
|---|---|
| `MARA` | `I_Product` |
| `TCURR` | `I_ExchangeRate` |
| `BSEG` | doğrudan eşdeğer yok — released API / CDS araştır |
| `VBAK` / `VBAP` | released satış belgesi CDS (okuma); yazma BAPI |
| `LIKP` / `LIPS` | released teslimat CDS (okuma); yazma BAPI |
| `T001` | released organizasyon CDS |
| `CL_GUI_ALV_GRID` | `CL_SALV_TABLE` (klasik) / UI5 grid (RAP) |
| `CL_GUI_ALV_TREE` | `CL_SALV_TREE` |

Released CDS adını tahmin etme: sistemde `adt_search_objects` ile ara, `adt_get` ile oku. Emin olunamayan
durumda ATC "Usage of APIs" kontrolü (`%sap-adt-foundation` → `foundation-query.md`). Released alternatifi
kullanılmayacaksa gerekçeyi kullanıcıya bildir; uyarıyı sessiz geçme.
