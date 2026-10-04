# Reçete — form objesi olmadan PDF: XDP + `CL_FP_ADS_UTIL=>RENDER_PDF`

> **Kanıt düzeyi:** "✅" işaretli maddeler **çekirdekte canlı ölçüldü (S/4 private 2025, DEV, 2026-10-04)**: 1 sayfalık bir
> sevk belgesi (başlık ızgarası, Code39 barkod, tekrarlı kart, gruplu kalem tablosu + ara/genel toplam, altbilgi) render
> edildi, mail eki olarak dış posta kutusuna gönderildi ve açıldı; çok belge → tek PDF 5 belgeyle ayrıca ölçüldü.
> aXet'te bu yol canlı **DOĞRULANMADI**. "⚠ ölçülmedi" maddeleri öyle okunur; aktarılırken genişletilmez.

## 1. Yol seçimi

| Yol | Ne yapar | Durum |
|---|---|---|
| **D — XDP + `RENDER_PDF`** (bu skill) | Yerleşim ve veri birer string; form objesi yok, standart tabloya yazım yok | ✅ — önerilen |
| A — SFPF/SFPI'yi programatik yarat (`CL_FP_WB_FORM`/`CL_FP_WB_INTERFACE=>CREATE`) | Designer'da açılabilen gerçek form | released DEĞİL · context XML'i GUID'li nesne grafı · form deposuna SAP API'siyle yazar ⇒ kesin yasaklar yorumu kullanıcı kararıdır · ⚠ denenmedi |
| SmartForms → OTF → `CONVERT_OTF` → PDF | Klasik | yerleşim yeniden çizilir; Türkçe/barkod ⚠ ölçülmedi |
| Spool/liste → PDF, SALV PDF dışa aktarımı | Düz liste | yerleşim yok → elenir |
| Saf ABAP PDF kütüphaneleri | — | yerleşik 3 font: Ğ İ Ş yok → elenir |
| Tarayıcıda PDF (jsPDF vb.) | — | font gömme + büyük yük (HTTP 414) → elenir |

ADT'de SFPF/SFPI düzenleme koleksiyonu yok (çekirdekte discovery'de ölçüldü) ⇒ Yol A ADT'den yürütülemez; Yol D'nin hiçbir
adımı form objesi yazmaz.

**Ön koşul — ADS ayakta mı:** `TSP01`'de ADS'in ürettiği güncel spool var mı (çekirdekte `ADSP` biçimli spool'lar sayıldı;
son tarihine bak). Yoksa Basis'e ADS bağlantı testini sor; ADS yoksa bu yol çalışmaz.

## 2. API (✅ başarılı yol; hata yolu kaynak okuması)

```abap
DATA ls_opt TYPE cl_fp_ads_util=>ty_gs_options_pdf.
ls_opt-embed_fonts = abap_true.                     " Türkçe glifler için ŞART (§5.4)
TRY.
    cl_fp_ads_util=>render_pdf( EXPORTING iv_xml_data     = lv_data_x   " XML veri, UTF-8 xstring
                                          iv_xdp_layout   = lv_xdp_x    " XDP şablon, UTF-8 xstring
                                          iv_locale       = 'tr_TR'     " sayı/tarih biçimi
                                          is_options      = ls_opt
                                IMPORTING ev_pdf          = lv_pdf      " xstring
                                          ev_pages        = lv_pages    " int4
                                          ev_trace_string = lv_trace ). " ADS izi — hatada oku
  CATCH cx_fp_ads_util INTO DATA(lx).
    " iz ve (varsa) hata PDF'i istisnadan ÖNCE dolar — çekirdekte kaynak okuması; ⚠ canlı hata koşusu yapılmadı
ENDTRY.
```
- String → UTF-8 xstring: `cl_web_http_utility=>encode_utf8( )` (✅). `cl_abap_conv_codepage=>create_out( )->convert( )` ⚠ denenmedi.
- `ev_pages`'i her koşuda yaz: yerleşim kusurunun en ucuz sinyali beklenmeyen sayfa sayısıdır (§5.1).
- Released durumu: sınıf ARS'de released (C1) listelenmişti (çekirdek araştırması; ⚠ yeniden ölçülmedi) → hedef sistemde
  metodun imzasını `adt_get` ile oku.

## 3. XDP iskeleti ve bağlama kuralları

Tam iskeletler: `templates/tek-belge.xdp` (başlık, barkod, kalem tablosu, toplam, altbilgi) ve `templates/cok-belge.xdp`;
eşleşen örnek veri `templates/tek-belge-veri.xml`, `templates/cok-belge-veri.xml`. Şablonlar SAP'de render **edilmedi** —
subform/field/bind/occur/barcode öğeleri çekirdekte render edilen şablonun kısaltılmış iskeletinden; sabit metin
`draw`/`value`/`text` yazımı aXet'in XFA 3.3 yazımıdır (çekirdekte örneği yok).

- XFA 3.3 düz XML'dir: `xdp:xdp` → `template` → kök `subform` (`layout="tb"`, `locale`) → `pageSet/pageArea`
  (`contentArea` + `medium`) → akışlı içerik. `tb` = yukarıdan aşağı, `lr-tb` = soldan sağa, sonra alt satır.
- Veri: kök eleman adı XDP'nin kök subform adıyla aynı (`<data>…</data>`), altında `HDR`, `ITEMS/ROW` …
- `$record.A.B` = veri kökünden mutlak yol · `$.A` = en yakın **bağlı** ata subform'un veri düğümüne göre (✅).
- `X[*]` + `<occur min="0" max="-1"/>` = tekrarlı subform, her veri örneği bir kopya (✅).
- **Adsız** subform ya da `<bind match="none"/>` veri bağlamını değiştirmez — görsel gruplama için güvenli (✅).
  **Adlı + bind'siz** subform ad eşlemesi yapar ⇒ bağlam kayabilir: adlı subform'a daima açık `bind` ver
  (⚠ XFA davranışına dayanan önlem; kayma gözlenmedi).
- Sabit metin `draw`, veriye bağlı metin `field`. Etiket + değer = `draw` + `field` içeren küçük adsız subform.
- Barkod (✅ Code39 okundu): `<ui><barcode type="code3Of9" dataLength="10" moduleWidth="0.25mm" wideNarrowRatio="3.0"
  textLocation="none" checksum="none"/></ui>` — numarayı barkodun altına ayrı bir `field` olarak yaz.

## 4. Çok belge → TEK PDF (✅ 5 belgeyle)

Gövde tekrarlı bir belge subform'una (`DOC`) sarılır; veri `<data><DOC>…</DOC><DOC>…</DOC></data>`, belge içindeki bütün
bağlar **göreli** (`$.HDR`, `$.ITEMS` …). Kırılım: `<breakBefore targetType="auto"/>` + `initialize` olayında
`if (this.index > 0) { this.breakBefore.targetType = "pageArea"; }` — ilk belge kırılım almaz, sonrakiler yeni sayfadan.
Belge içi "Sayfa n / N": `pageArea`'daki altbilgi alanında `<event activity="ready" ref="$layout">` betiği, belgenin
başladığı sayfayı (`xfa.layout.page`) ve kapladığı sayfa sayısını (`xfa.layout.pageSpan`) sorar; API hata verirse tüm
dosyanın numarasına düşer. Birebir biçim: `templates/cok-belge.xdp`.
- ✅ her belge yeni sayfadan, baştaki boş sayfa yok · ✅ numara belge içinde başlıyor (ikisi de kullanıcı görsel kontrolü) ·
  tek render, tek CL_BCS eki, 144.264 bayt (en büyük tek belgelik PDF 102.554).
- ⚠ **ÖLÇÜLMEDİ:** belge içi `n / N`'de N > 1 dalı ve tablo başlığının sonraki sayfada tekrarı (`<overflow leader="TH[0]"/>`).
- Tek belgede sarmalayıcıyla çıktı sarmalayıcısız hâli gibi **görünür** (görsel kontrol; bayt düzeyinde aynı değil).
- Aynı mailde N ayrı PDF eki denemesi 2. `add_attachment`'ta ~130 sn sonra `cx_bcs` ile düştü; teşhis edilmedi (tek vaka).
  Tek PDF hata semantiğini de "hepsi ya da hiçbiri" yapar (tek render).

## 5. Tuzaklar (hepsi çekirdekte bu yolda yaşandı)

### 5.1 Çok kolonlu `lr-tb` satırında kolon toplamı = kapsayıcı ⇒ son kolon alt satıra kayabilir
11 kolonlu kalem satırında (ve 8 hücreli toplam satırında) toplam 192 mm, kapsayıcı 192 mm: son kolon **her satırda** alt
satıra düştü, belge 1 yerine **2 sayfa** oldu. Hata, uyarı ya da ADS iz satırı **yok** — sinyal yalnız `ev_pages` ve gözle
bakış. Toplamı tam 192 olan 2-4 elemanlı satırlar kaymadı ⇒ mekanizma ve eşik **ölçülmedi**.
**Kural:** çok kolonlu satırda toplam = kapsayıcı − 1 mm (191/192); toplam satırları da aynı toplamı izler. Kasıtlı sarılan
kart dizileri bu kuralın konusu değildir. ✅ Bir kolonu 1 mm daraltmak belgeyi 1 sayfaya indirdi.
Denetim: `scripts/xdp_denetle.py` kuralı XDP-03.

### 5.2 Büyük harfli sabit etiketlerde `İ` — yabancı sözcükte YANLIŞ
"Booking" büyük harfe **"BOOKİNG"** oldu. Türkçe sözcükte doğru (`SEVKİYAT`, `MÜŞTERİ`), yabancı sözcük/kısaltmada yanlış
(`BOOKING`, `INCOTERMS`, `BL NO`). Büyük harfli etiketleri elle yaz; `İ` geçen her etiketi tek tek oku (XDP-04 listeler).

### 5.3 Uzun metin alanı = `multiLine="1"` + `minH` (sabit `h` DEĞİL)
Sabit `h` uzun metni **keser**; `minH` + `multiLine` satırı büyütür. Tablo satırında tüm hücrelere `minH` (biri büyürse satır büyür).

### 5.4 Font: `typeface="Arial"` + `embed_fonts = abap_true` + projenin yerel ayarı (✅ TR projede `tr_TR`)
ADS sunucusunda Arial var; PDF'e ArialMT / Arial-BoldMT gömüldü, ş ğ ı İ Ş Ğ Ü Ö Ç doğru çıktı.
Gömme kapalıyken görüntüleyicinin yedek fontu Türkçe glifleri bozabilir (⚠ kapalı hâl ölçülmedi).

### 5.5 XDP'yi ABAP'a gömmek: üretici script, elle kopyalama DEĞİL
XDP ~35-40 KB'tır, elle literal'e çevrilemez. `.xdp` repoda kaynak olarak durur; `scripts/xdp_abap_uret.py` onu
`` rv_xml = rv_xml && `…` && nl. `` satırlarına çevirir (ters tırnak ikilenir, satır ≤ 255 karakter), yazmadan önce bağlama
simülasyonu yapar, `--check` ile ABAP kopyasının güncelliğini söyler. Ürün kodunda XDP'nin yeri (sınıf metodu / MIME
deposu / Z tablo) ayrı tasarım kararıdır (⚠ yalnız "sınıf metodu" ölçüldü).

### 5.6 Deneme koşusu: `IF_OO_ADT_CLASSRUN` + base64 çıktı
PDF base64'e çevrilip başlangıç/bitiş işaretleri arasında sabit uzunluklu satırlarla yazılır (`templates/deneme-classrun.clas.abap`),
yerelde `scripts/pdf_coz.py` ile çözülür. Sayfa sayısı yerelde **bağımsız** sayılır (`pypdf`): ADS sayfa nesnelerini
sıkıştırılmış nesne akışına koyar ⇒ ham `/Type /Page` regex'i **0** verir (ölçüldü) — o sayı hüküm değildir.
PDF'i **aç ve oku**: bayt/sayfa sayısı yerleşim kusurunu söylemez (§5.1'deki kusur ancak bakınca görüldü).

### 5.7 `layout:ready` bir `activity` değeri DEĞİLDİR — `activity="ready" ref="$layout"` yaz
✅ yanlış değerli şablon ADS'te **hata vermeden** render edildi · ✅ doğru biçimdeki betik koştu. ⚠ yanlış biçimde betiğin
koşmadığı ölçülmedi (çıkarım XFA şemasından). Yanlış değer **sessizdir** — XDP denetçisi bunu HATA sayar.

### 5.8 Veri XML'ine giden numaralarda `ALPHA = OUT` sondaki boşluğu bırakır
`|{ matnr ALPHA = OUT }|` alan genişliğini korur ⇒ `"ABC123 "` XML'e gider (ölçüldü). Çare
``shift_right( val = |{ f ALPHA = OUT }| sub = ` ` )`` ya da `condense( )`. Aynı tuzak mail konusunda da var
(`%sap-classic-abap` → `references/email.md`, "Konu" bölümü).

## 6. Ölçülmemiş / açık
- Çok belgede N > 1 dalı · `overflow leader` başlık tekrarı · 50 belgede süre/boyut (yalnız 5 belge ölçüldü).
- `embed_fonts = abap_false` davranışı · Yol A (programatik SFPF) · s4_public / BTP ABAP'ta `CL_FP_ADS_UTIL` erişimi
  (bu yüzden skill yalnız `s4_private`).

## 7. Çekirdek ölçüm geçmişi (özet)
- v1: 87.732 bayt, **2 sayfa** (beklenen 1) — §5.1 kolon kayması + §5.2 "BOOKİNG"; glifler ve Code39 doğru; ek dış posta kutusuna ulaştı.
- v2 (yalnız kolon toplamı 192 → 191 + etiket düzeltmesi): 87.271 bayt, **1 sayfa** (`ev_pages` 1 · `pypdf` 1; kontrol
  grubu v1 aynı yöntemle 2); ADS render 607 ms; SOST `718 I`, tek gönderi.
- Çok belge: 5 belge → tek PDF 144.264 bayt, tek ek, SOES `718`; render + gönderim 1.641 ms.
