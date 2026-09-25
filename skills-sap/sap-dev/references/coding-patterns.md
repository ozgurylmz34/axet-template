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
- `TYPES … WITH EMPTY KEY` tanımlı iç tabloda ölçütsüz `SORT itab.` ve `DELETE ADJACENT DUPLICATES FROM itab.`
  birincil anahtara dayanır — ve o anahtar boştur; ATC "check the semantics of the statement" der. Etki bağlama göre
  değişir (sıralama bir doğruluk kuralıysa, ör. kilitleri artan sırada alma, kural sessizce delinmiş olabilir; yalnız
  `FOR ALL ENTRIES` girdisi hazırlıyorsa etki verimliliktir), ama düzeltme her durumda aynı ve güvenlidir:
  `SORT itab BY table_line ASCENDING.` · `DELETE ADJACENT DUPLICATES FROM itab COMPARING table_line.` "Bugün no-op
  muydu" sorusunu ölçmeden koda yazma. Yerel kontrol bunu görmez; ATC koşunca görünür (ekip dersi).

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
- **İki Z sınıfı karşılıklı referans (A→B sabit okur, B→A metot çağırır) aktivasyonu kilitlemeyebilir.** Önce statik
  çağrıyı yaz, yalnız DEĞİŞEN sınıfı push + aktive et (öteki zaten aktif olsun), readback ve `adt_inactive_objects` ile
  doğrula; ancak başarısızsa dinamik `CALL METHOD`'a geç — dinamik çağrı where-used zincirini koparır, ad/imza hatasını
  çalışma zamanına iter. Kanıtın sınırı (ekip dersi): tek taraf değişikliği ölçüldü; iki sınıfın aynı anda yeni
  yaratılıp birlikte aktive edilmesi ve boş hedef sisteme ilk taşıma ÖLÇÜLMEDİ — taşımada ikisi aynı transportta gitsin.
- **ST05 SQL izi iki sessiz tuzak taşır (ekip dersi).** ① Tamponlu tablo izde hiç görünmez: yokluk "okunmadı" demek
  değildir — sonuç çıkarmadan önce tampon durumunu `DD09L-PUFFERUNG` ile ölç (tamponsuz tablonun yokluğu anlamlıdır).
  ② Varlık da kanıt değildir: o tabloyu standart akış da okuyor olabilir. Yalnız size özel okumaları ayırt edici say;
  izi `PROGRAM` kolonuyla kendi sınıf/programına filtrele, ham `STATEMENT_WITH_VALUES` + `USER_NAME` kolonlarını oku
  (vakada kanıt, WHERE'e enjekte edilmiş CDS yetki reddi koşuluydu). Kullanıcıya özgü farklarda kontrol grubu için
  `%sap-cds-ddic` `references/cds.md` CDS-DCL-03.
- Yerel yardımcı Python script'i yazıyorsan Windows konsolu (`cp1252`) Unicode basamayabilir:
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` ya da ASCII çıktı. Geçici script `.tmp/`'ye.

## 7. Clean core — standart obje yerine ne kullanılır
Standart tabloyu okumak yasak değildir; yeni okuma modelinde released CDS/API tercih edilir. Yazma hiçbir durumda
doğrudan SQL değildir (kesin yasak B); hangi yol (released RAP BO/EML → released BAPI → released OData → BAPI/RFC FM → BDC →
manuel) ve hangi canlı teyitle: `write-api-selection.md`.

| Standart obje | Yerine (released) |
|---|---|
| `MARA` | `I_Product` |
| `TCURR` | `I_ExchangeRate` |
| `BSEG` | doğrudan eşdeğer yok — released API / CDS araştır |
| `VBAK` / `VBAP` | released satış belgesi CDS (okuma); yazma `write-api-selection.md` (ölçülmüş: `I_SalesOrderTP` EML) |
| `LIKP` / `LIPS` | released teslimat CDS (okuma); yazma `write-api-selection.md` (released BO kapsamı ölçülmedi) |
| `T001` | released organizasyon CDS |
| `CL_GUI_ALV_GRID` | `CL_SALV_TABLE` (klasik) / UI5 grid (RAP) |
| `CL_GUI_ALV_TREE` | `CL_SALV_TREE` |

Released CDS adını tahmin etme: sistemde `adt_search_objects` ile ara, `adt_get` ile oku. Emin olunamayan
durumda ATC "Usage of APIs" kontrolü (`%sap-adt-foundation` → `foundation-query.md`). Released alternatifi
kullanılmayacaksa gerekçeyi kullanıcıya bildir; uyarıyı sessiz geçme.

## 8. Kanıt ve tasarım tuzakları (ekip dersleri)

**Uyarlama/kontrol tablosu alan anlamını kısaltmadan tahmin etme.** İkili alanlarda (ör. satış belge türü tablosunda
"siparişe bağlı" ↔ "teslimata bağlı" fatura türü) data element etiketini oku (`adt_get` `dtel` ya da DDIC etiketi) ve
rapora/koda ikisini de etiketiyle yaz; mümkünse aynı türden gerçek bir belge zinciriyle çapraz kontrol et. Vakada yön ters
yazıldı ve FS üç sürüm boyunca yanlış fatura türünü taşıdı; yanlış yön fiyatlandırma, hesap tayini ve çıktı uyarlamasını da
bozar.

**Yoruma sayılmış küme yazma, kümeyi üreten kuralı yaz.** "Şu 7 malzeme" gibi bir liste metni canlı verinin fonksiyonu
yapar ve sessizce bayatlar (vakada aynı gün yeni bir malzeme doğdu, listenin kapsamı değişti). Yerine ölçütü yaz ("bölüm X
dışındaki her malzeme, adı ne olursa olsun, kapsam dışıdır"). Sayı kalacaksa yalnız büyüklük mertebesi olarak kalsın,
gerekçe ona dayanmasın; bir sayıyı tazelerken sınıflandırmanın hâlâ geçerli olduğunu ayrıca ölç.

**DEV'de ölçülen YAPI geçerlidir, DAĞILIM/HACİM değildir.** Alan var mı, anahtarda mı, domain sabit değerleri, sorgu
400 mü veriyor gibi yapı ölçümleri üretime taşınır. Yüzde, oran, p95, "kaç kayıt açık" gibi dağılım ölçümleri yalnız
DEV'in o anki hâlidir: tasarım eşiği, tavan, varsayılan ya da kapasite kararı bunlardan TÜRETİLEMEZ. Dağılıma bağlı eşik
gerekiyorsa kullanıcıya sor ya da tasarımı dağılımdan bağımsız kur ("sabit N, yetmezse genişle"). Raporda dağılım
sayısının yanına "DEV verisi — üretimi temsil etmez" yaz.

**"Yanlış olursa gürültülü düşer" ölçülmemiş bir olgu iddiasıdır.** Bu cümle bir izleme kararını belirler: yanlışsa
kimse bakmaz. SAP'de domain sabit değer listesinde BOŞ değer çoğu zaman meşru bir değerdir; "geçersiz değer reddedilir"
demeden önce `DD07L`/`DD07T` ile ve değeri okuyan kontrolün kendisiyle ölç (vakada boş değer listede olduğu için geçti ve
satır sessizce yanlış işlendi). Ölçemiyorsan `[DOĞRULANMADI]` yaz ve kararı ona dayandırma. Güvenliği metne değil kapıya
bağla (kapsanmayan girdi gelirse üretim dursun) ve kapıyı negatif testle doğrula.

**Senkron çağrı ardıl belgeyi senkron yapmaz.** "Bu FM senkrondur, dönüşten sonra bekleme ekleme" kapsamı gizler:
senkron olan çağrının KENDİ çıktısıdır (ör. teslimatın dağıtım statüsü alanı), ardıl sistemde doğan belge değil (vakada
ardıl belge 8 sn sonra doğdu; tek vaka, DEV — eşiğe çevrilemez). Senkronluk iddiasını hangi ALANIN güncel olduğuyla yaz.
Ardıl belgeyi okuyacaksan sabit bekleme değil bütçeli poll yaz (aralık + tur sayısı kullanıcı kararı, bulunca derhal
çık); bütçe dolunca bekleme mesajı hata mesajından farklı olsun. Poll'ü ters yönde test et: kaldırınca hata geri geliyor
mu. Aynı akışta kendi yarattığın belgeyi commit sonrası okurken: `%sap-code-review` `checklist-abap.md` BE-73.

**Çok adımlı zincirde ön kontrolün kapsamını ÇAĞIRAN verir.** Sipariş → teslimat → mal çıkışı → fatura zincirinde ön
kontrol koşulsuz ve tam kümeyle, zincir durumu okunmadan koşarsa, tamamlanmış adımların tükettiği kaynak (stok, kredi,
miktar) yeniden denemede hata olarak döner: başarılı zincir kendi yeniden denemesini kalıcı olarak düşürür (vakada dört
belgenin dördü canlıdaydı, kayıt "stok yetersiz" hatasındaydı). "Hangi kontrol düşsün" diye sorma; önce her kontrol
grubunun hangi adımdan sonra anlamsızlaştığını `dosya:satır` ile çıkar, kapsam tablosunu kullanıcıya sun. Kapsam çağırandan
OPTIONAL parametreyle gelir; boş ya da okunamayan durum ve `WHEN OTHERS` = tam küme (fail-closed). Aynı belgeyi iki düğme
kontrol ediyorsa ikisi de daralsın; daraltma bir kod şerhini yalanlıyorsa şerhi sessizce silme, düzeltmeyi görünür yaz.
