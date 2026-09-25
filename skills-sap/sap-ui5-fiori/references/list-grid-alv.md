# Liste / rapor ekranı — grid (`sap.ui.table.Table`) + ALV paritesi + filtre ekranı

> Üst ilke SAP çekirdeğindedir (her liste/rapor ekranı, kullanıcı istemese de sıralama, operatörlü filtre, kolon
> göster/gizle, varyant, Excel sunar; UI5'te grid). Bu dosya **UI5 mekaniğini** verir. Backend (salt-okunur rapor
> servisi, DCL, ortak VH expose) `%sap-rap`; Gateway `$filter` davranışı `%sap-odata-backend` → `references/filter-search.md`.

---

## 1. Karar

| Ekran | Tablo |
|---|---|
| Masaüstü, çok kolonlu liste/rapor (ALV benzeri) | **`sap.ui.table.Table` (grid)** — yatay + sanal scroll, kolon genişlet/sürükle/dondur, **native** sort/filter menüsü |
| Mobil öncelikli, hücresi zengin (wrap, değişken yükseklik) | `sap.m.Table` **istisna** (§7) |

- **Reddedilen:** `sap.m.P13nDialog` / `P13nFilterPanel` (eklenen koşul modele yazılmıyordu → "75 ile başlar" filtresi
  uygulanmadı); `sap.m.TablePersoController` (native Promise ile route çöktü). Grid ve m.Table'da ikisi de kullanılmaz.
- **SmartTable/SmartFilterBar** kullanılmaz (freestyle standardı).
- Otomatik: `python scripts/check_list_view_grid.py <app>` — dosya adı `list|report|liste|rapor` olan view'da
  `sap.m.Table` → ihlal. Adı başka olan liste ekranını **görmez** (KAPSAM satırı).

## 2. Grid kurulumu — beş parça

1. **manifest** libs'e `"sap.ui.table": {}` + `"sap.ui.export": {}`; view'da `xmlns:table="sap.ui.table"`.
2. **`table:Table`**
   ```xml
   <table:Table id="tblList" rows="{/OrderSet}" threshold="200"
                visibleRowCountMode="Auto" minAutoRowCount="10"
                selectionMode="None"
                enableColumnReordering="true" enableColumnFreeze="true"
                rowsUpdated=".onRowsUpdated">
     <table:extension>
       <OverflowToolbar>
         <Title text="{i18n>list.title}"/>
         <ToolbarSpacer/>
         <Button text="{i18n>btn.cols}" press=".onColumns"/>
         <Button text="{i18n>btn.excel}" icon="sap-icon://excel-attachment" press=".onExportExcel"/>
         <Button icon="sap-icon://refresh" press=".onRefresh" tooltip="{i18n>btn.refresh}"/>
       </OverflowToolbar>
     </table:extension>
     <table:columns> … </table:columns>
   </table:Table>
   ```
   - `selectionMode="None"` saf liste; `"Single"` master-detail.
   - `threshold="200"` OData lazy okuma.
   - ⚠ `visibleRowCountMode` yeni UI5 sürümlerinde yerini `rowMode` aggregation'ına bırakıyor (kaynak araç
     envanterindeki UI5 notu: 1.119+). Proje UI5 sürümünde hangisinin **deprecated** olduğunu API referansından
     doğrula — DOĞRULANMADI; kaynak uygulamalar `visibleRowCountMode` ile çalışıyordu.
3. **`table:Column`** (her biri)
   ```xml
   <table:Column id="colOrder" width="8rem" sortProperty="OrderId" filterProperty="OrderId">
     <Label text="{i18n>col.order}"/>
     <table:template><Text text="{OrderId}" wrapping="false"/></table:template>
   </table:Column>
   ```
   Genişlik tipe göre: tarih `7rem` · saat `6rem` · tutar/miktar `8rem` + `hAlign="End"` · kısa kod `8rem` ·
   ad/uzun/birleşik metin `16rem` · varsayılan `10rem`. **Anahtar kolonlar başta.** Her kolona sabit `id`
   (kişiselleştirme meta'sı `colId` ile eşleşir).
4. **Sort/filter = grid native kolon menüsü** (`sortProperty`/`filterProperty` verilince gelir). m.Table'daki özel
   `columnmenu.Menu` + aktif filtre `infoToolbar` gerekmez. Native kolon filtresi ile filtre ekranının temel filtresi
   AND'lenir (temel filtre `binding.filter(aFilters, "Application")`).
5. **Kolon göster/gizle + varyant + Excel** = kişiselleştirme yardımcısı (§3).

**Binding:** `oTable.getBinding("rows")` (m.Table'da `"items"`); sayım `rowsUpdated` → `getBinding("rows").getLength()`.
Master-detail: `selectionMode="Single"` + anahtar kolonda `Link press` ya da `rowActionTemplate` (Navigation) → `navTo`.

**Saat alanı:** `Edm.Time` → `type: 'sap.ui.model.odata.type.Time'`; Excel kolonunda `EdmType.Time`.
**Birleşik alan** ("kod-tanım", ham kod yok): F4 kod verir → filtre birleşik alana `StartsWith "<kod>-"`.

## 3. Kişiselleştirme yardımcısı (`TablePersonalizer`) — davranış sözleşmesi

Kaynak ekip bunu uygulamalar arasında birebir kopyalanan **ortak bir util** olarak tutuyordu. **Util kodu bu skill'le
gelmez** (müşteriye ait). Projede böyle bir util varsa kopyalanır ve yalnız kolon meta'sı doldurulur; sıfırdan
sort/filtre/export yazılmaz. **Yoksa** aşağıdaki sözleşme bir kez yazılır, projede ortak util olarak tutulur
(`%remember` ile yeri kaydedilir). Adı ilk kullanan ekranın adı değil, amacı olur.

Kurucu (kaynaktaki imza):
```javascript
new TablePersonalizer({ table: oTable, persoKey: "zxx001.orderList",
    columns: [{ key: "order", path: "OrderId", colId: "colOrder", text: sText, type: "string" }, …],
    bundle: oResourceBundle, baseFilters: aFilters });
```

| Yetenek | Beklenen davranış |
|---|---|
| **Kolonlar** | Geniş, ortalanmış `sap.m.Dialog`: arama + Tümünü seç/kaldır + scroll; kolon adları **tam** görünür |
| **Varyant** | Tam yerleşim: `Config = { cols: [{ key, visible, width, index }] }` (görünürlük + genişlik + sıra). **Farklı kaydet** (ad ≤ 14 karakter — kaynakta varyant adı CHAR14), **Sil** (`MessageBox.confirm`), **Varsayılan yap (★)** → ekran açılışında otomatik uygulanır |
| **Varyant deposu** | Kaynakta ortak bir OData varyant servisi (`ZCA000_UI_VARIANT_O2` demo adı) + `localStorage` yedeği. Servis yoksa / yayında değilse / 401 veriyorsa **yalnız localStorage** (`LOCAL_VARIANTS_ONLY = true`) — servis model'i kurulduğu anda `$metadata` çeker ve lokal çalıştırmada 401 popup'ı tetikler |
| **Excel** | `sap.ui.export.Spreadsheet`, gerçek `.xlsx`; OData binding'den **filtreye uyan tüm satırlar** (ekrandaki sayfa değil); kapsam sorulur: **Görünür / Tüm kolonlar** (`getColumnsForExport(bAll)`) |
| **Kolon filtresi** | Native filtre olayında `preventDefault` + string kolonda düz `Contains` (**`caseSensitive` yok**) + wildcard (§6.2) |
| **i18n** | `btn.cols`, `btn.excel`, `var.*`, `flt.*`, `exp.*`, `op.*` anahtarları **iki dosyada** (`freestyle-odata-v2.md` §9) |

- ⚠ **Kopyalamadan önce:** util'in varyant modeli (`new ODataModel(<varyant servisi>)`) ana modelin `sap-client`'ını
  taşımalı — eski kopyalar taşımıyordu ve iki client aynı tarayıcıda açıkken öbür client'ın varyantlarını okudu
  (`freestyle-odata-v2.md` §7.4, FE-48). Kopyaladığın sürümde §7.4'teki `_mainClientParams` karşılığı yoksa ekle; ana
  modeli util'e verilen kontrolün sahip bileşeninden al — `Component.getOwnerComponentFor(<kontrol>).getModel()`
  (onInit'te tablonun modeli henüz `undefined`). Aynı util birden çok uygulamada kopyaysa hepsini tara.
- Grid seçimi indeks bazlıdır; native menüden sıralama/filtre binding'i uygulama kodundan geçmeden yeniden kurabilir →
  seçim temizliği `delete-flow-ui.md` §1'e göre değerlendirilir.
- **Alternatif (DOĞRULANMADI):** yeni UI5 sürümlerinde `sap.m.p13n.Engine` standart kişiselleştirme sağlar; kaynak
  ekip denemedi, reddedilen `P13nDialog`'dan farklı bir API'dir. Kullanılacaksa önce proje UI5 sürümünde canlı dene
  (varyant + Excel + kolon filtresi davranışı yukarıdaki tabloyla) ve sonucu kaydet.

## 4. Grid seçimi ve dialog içinde grid

| Konu | Kural |
|---|---|
| Seçim API'si | `getSelectedIndices()` → `getContextByIndex(i)` → `getObject()`; temizlik `clearSelection()` |
| Düzenlenebilir hücreli grid | `selectionBehavior="RowSelector"` (hücreye tıklama satır seçmesin) |
| `sap.m.Dialog` içinde grid | Dialog `verticalScrolling="false" horizontalScrolling="false"` (grid kendi scroll'unu yönetir) |
| Seçim sayımı | Gözle değil `getSelectedIndices().length` ile |

## 5. Görsel kurallar (liste)
- İlk açılışta **6–8 görünür kolon**; kalanı kolon göster/gizle ile.
- Sıra: tanımlayıcı → ana bilgi → durum → ana metrik (sağa hizalı) → ikincil → üçüncül.
- Ham kod (A/B/X) yerine okunur metin (formatter + i18n); teknik alan (GUID, MANDT) gösterilmez.
- Boş tablo: yönlendirici boş durum (`IllustratedMessage` + eylem butonu). Ayrıntı `fiori-elements-ux.md` §2.

## 6. Filtre / seçim ekranı = SELECT-OPTIONS pariteli

Rapor/liste seçim ekranı ABAP SELECT-OPTIONS gibi davranır, **kullanıcı istemese de**.

### 6.1 Kontroller
- Her filtre alanı **`sap.m.MultiInput` + `sap.ui.comp.valuehelpdialog.ValueHelpDialog`** (değer tablosu + "Koşul
  tanımla" / aralık sekmesi). Tek değerli `<Input>` kullanılmaz.
- İstisnalar: tarih = `DateRangeSelection`; durum/bayrak = `SegmentedButton`.
- Manifest libs'te `sap.ui.comp`.

### 6.2 Arama: harf-duyarsız "içeren", `caseSensitive:false` YOK
```javascript
// ⛔ new Filter({ path: "Name", operator: FilterOperator.Contains, value1: q, caseSensitive: false })
new Filter("Name", FilterOperator.Contains, q);            // düz substringof
```
- `caseSensitive:false` UI5 V2'de `$filter`'a `toupper()`/`tolower()` enjekte eder; SAP Gateway (`/IWBEP`) bunları
  desteklemez → **HTTP 400 "Function toupper/tolower is not supported"** (SAP Note 1797736) → arama hiç sonuç
  döndürmez. Düz `substringof` ölçülen sistemde harf-duyarsızdı (DB collation) — başka sistemde bir kez ölç.
- Wildcard yardımcısı (tek ortak fonksiyon; F4 araması, kolon filtresi, düz token aynı yardımcıyı kullanır):
  ```javascript
  _parseSearchTerm: function (sPath, sRaw, sDefaultOp) {
      var s = (sRaw || "").trim(), bStart = s.charAt(0) === "*", bEnd = s.length > 1 && s.charAt(s.length - 1) === "*";
      var v = s.replace(/^\*+|\*+$/g, "");
      if (!v) { return null; }                                       // literal yıldız aranmaz
      if (bStart && bEnd) { return new Filter(sPath, FilterOperator.Contains, v); }
      if (bEnd)           { return new Filter(sPath, FilterOperator.StartsWith, v); }   // x*
      if (bStart)         { return new Filter(sPath, FilterOperator.EndsWith, v); }     // *x
      return new Filter(sPath, FilterOperator[sDefaultOp || "Contains"], v);            // x
  }
  ```
  `startswith`/`endswith` Gateway'de desteklenir (toupper'ın aksine). Kod/serbest metin alanında düz token varsayılanı
  `Contains` (`defaultOp` yapılandırılabilir).
- Yardımcının gövdesi kaynak kurala göre bu dosyada yazıldı (kaynakta yalnız davranışı tarif ediliyordu) — birim
  davranışını ilk uygulamada dört girdiyle ölç (`x`, `x*`, `*x`, `*x*`).
- Aynı alan birden çok değer → `and: false` (OR); farklı alanlar → `and: true`.
- Otomatik: `python scripts/check_filter_search_pattern.py <app>` → `caseSensitive:false` **BLOCKER**; filtre
  view'ında `valueHelpRequest` olup `MultiInput` olmaması **WARNING**.

### 6.3 Filtre ekranı yerleşimi
- Hızlı filtre (`IconTabBar` ya da `SegmentedButton`, durum bazlı sayaçlı) + arama her liste sayfasında.
- Filtre ekranı ile grid arasında `baseFilters` sözleşmesi: filtre ekranı temel filtreyi kurar, kişiselleştirme
  yardımcısı kolon filtrelerini onun üstüne AND'ler.

## 7. `sap.m.Table` istisnası
Mobil öncelikli ya da hücre içeriği değişken ekran: `sap.m.Table` + `sap.m.table.columnmenu.Menu` (kolon başlığında
sırala + tipe duyarlı operatörlü filtre: metin Contains/EQ/StartsWith/EndsWith/NE; sayı/tarih EQ/NE/GT/GE/LT/LE/BT;
bool EQ) + `infoToolbar` aktif filtre çubuğu (`Alan op değer ✕` + "Tümünü temizle") + kolon göster/gizle popover +
Excel (aynı kapsam sorusu) + `localStorage` durum. Yatay/sanal scroll yoktur; `importance` + `minScreenWidth` +
`demandPopin` ile dar ekranda pop-in. Binding `"items"`, seçim `removeSelections(true)`.

## 8. Kontrol listesi (liste ekranı)
- [ ] Grid; `sap.ui.table` + `sap.ui.export` libs; `check_list_view_grid.py` PASS
- [ ] Kolon genişlikleri tipe göre, anahtarlar başta, sabit kolon `id`'leri, `sortProperty` + `filterProperty`
- [ ] Kolon göster/gizle + varyant (varsayılan ★) + Excel (Görünür/Tüm, filtreye uyan tüm satırlar)
- [ ] Varyant servisi yoksa localStorage-only; lokal çalıştırmada 401 popup'ı yok
- [ ] Filtre ekranı MultiInput + ValueHelpDialog; `caseSensitive` hiç yok; wildcard yardımcısı; `check_filter_search_pattern.py` PASS
- [ ] Seçim temizliği tek giriş noktasında (`delete-flow-ui.md` §1)
- [ ] Kişiselleştirme i18n anahtarları iki dosyada (`check_i18n_keys.py`)
- [ ] Runtime: sırala, filtrele, kolon gizle, varyant kaydet/varsayılan/yeniden aç, Excel (`runtime-verification.md`)

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Müşteri rapor uygulamalarının yolları ("kopyala" referansları) ve util dosyasının kendisi alınmadı; yerine davranış
  sözleşmesi (§3) yazıldı. Ortak varyant servisinin adı demo adla değiştirildi; servis bu template'le gelmez.
- Karar kaydının ilk (m.Table + columnmenu + infoToolbar) gövdesi kanonik değil, §7 istisnasına indirildi.
- `_parseSearchTerm` gövdesi kaynakta yoktu (yalnız eşleme tablosu); eşleme tablosuna göre yazıldı ve ölçüm notu eklendi.
- Salt-okunur rapor backend reçetesi (wrapper view entity + DCL + SRVD/SRVB, conversion exit'li alan `cast`) alınmadı →
  `%sap-rap`.
- Dialog içinde grid, `RowSelector`, `Edm.Time`, `rowMode` notları kaynaktaki plugin/araç envanteri ve UI standart
  güncelleme notlarından eklendi; `rowMode` sürüm sınırı DOĞRULANMADI.
