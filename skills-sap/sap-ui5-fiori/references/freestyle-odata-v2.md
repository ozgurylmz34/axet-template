# Freestyle UI5 + OData V2 (RAP ya da SEGW tüketen) — plumbing, tuzaklar, value-help

> Kapsam: tarayıcı tarafı. Backend (CDS/BDEF/SRVD, early numbering, `to_` adının kaynağı) `%sap-rap`; SEGW/DPC
> `%sap-odata-backend`. İskelet `app-skeleton.md`, liste ekranı `list-grid-alv.md`, silme akışı `delete-flow-ui.md`.
>
> **Sınır — plumbing reuse, iş içeriği bespoke:** save / navigation adı / `setData` şekli / master-detail seçim
> bağlantısı / MERGE'de boş tarih **uygulamadan bağımsız tek doğru yoldur** → aşağıdaki desen referans alınır, sıfırdan
> icat edilmez (icat = çözülmüş hatayı geri getirmek). Entity/servis, alan listesi, ekran yerleşimi, iş kuralları,
> value-help hedefleri, etiketler **her uygulamada ayrıca yazılır** — hiçbir ekran başka ekranın kopyası değildir.
> Kaynak ekipte bir uygulama bu mekaniği çalışan desenden almayıp sıfırdan yazdı; aynı altı hata (§4 T1–T7) geri geldi.

---

## 0. PRE-FLIGHT — kod yazmadan karara bağla

1. **İskelet** `app-skeleton.md` §13 listesiyle kuruldu (sabit UI5 sürümü, `language=tr`, manifest modelleri
   `i18n` + `""` (TwoWay, `useBatch:false`, Inline) + `ui` JSON `{busy, filter:{}}`, kanonik host).
2. **Düzenlenebilir alt grid var mı?** (composition kalemleri ekrandan eklenip/silinip/düzenlenecek mi?) → **varsa en
   baştan JSON edit-buffer** (§1.3). V2 nav-binding + `createEntry` ile düzenlenebilir grid **denenmez** — kaynak
   ekipteki ilk uygulamada patinajın büyük kısmı buydu.
3. **Save şablonu** (§1) baştan konur.
4. Her sayısal/tarih OData binding'ine **OData tipi** (§5.1); CHAR1 bayrak → CheckBox deseni (§5.2).
5. **Value-help** için tek yardımcı (§3); ad alanı (`<X>Name`) backend'de expose edilir. Ortak mı yerel VH mi →
   kullanıcıya sor (`%sap-rap` → `references/value-help.md`).
6. **Liste ekranı = grid + ALV paritesi** (`list-grid-alv.md`), kullanıcı istemese de.
7. Her alan adı / navigation adı / function import adı **canlı `$metadata`**'dan (§8). Tahmin yok.
8. Zararsız konsol gürültüsü kovalanmaz (`runtime-verification.md` §5).

## 1. Save akışı (kanıtlanmış desen)

```
onSave : document.activeElement.blur()  →  setTimeout(_save, 0)          // son düzenlenen alan modele commit olsun
_save  : isNew → oModel.create("/Root", {...h, to_Child: {results: [...]}}, {success:_ok, error:_err})   // TEK nested POST
         mevcut → SIRALI (_runSeq), paralel DEĞİL:
             1) oModel.update(<başlık entity yolu>, hBody, {merge:true})
             2) her yeni kalem      → oModel.create(<başlık yolu> + "/to_Child", body)      // nav yolu
             3) her değişmiş kalem  → oModel.update(<kalem entity yolu>, body, {merge:true}) // KEY gövdede yok
             4) her silinmiş kalem  → oModel.remove(<kalem entity yolu>)
           → hepsi bitince tek _ok / ilk hatada tek _err
_ok    : MessageBox.success(<belge no'lu metin>, { onClose: navigasyon/yenileme })          // §6
_err   : MessageBox.error(<genel metin> + "\n" + _parseError(oErr))                          // §6.2
```

Sıralı koşucu (her adım garantili `done` ya da `fail` çağırır):
```javascript
_runSeq: function (aSteps, fnDone, fnFail) {
    var i = 0;
    (function next() {
        if (i >= aSteps.length) { fnDone(); return; }
        var fnStep = aSteps[i++];
        fnStep(next, fnFail);                 // adım: function (done, fail) { oModel.update(p, b, {merge:true, success: done, error: fail}); }
    })();
}
```
Entity yolu: `"/" + oModel.createKey("ItemSet", { OrderId: sId, ItemNo: sNo })`.
Busy: `ui>/busy` bayrağı `_save` başında `true`, `_ok`/`_err` içinde `false` — her yol (0 kalem / yalnız update /
yalnız create / karışık) `_ok` ya da `_err`'e ulaşmalı.

### 1.1 Kurallar (her biri gerçek bir patinaj turu)

| # | Kural | Belirti (ihlal edilince) |
|---|---|---|
| S1 | Save **`oModel.create/update/remove`** ile, anında gönderilir. `setProperty` + `submitChanges` değişiklik algılamasına güvenilmez | Programatik atanan değer (otomatik doldurma, cascade) **kaydedilmez** — "kaydetmiyor" |
| S2 | İşlemler **sıralı**; `Promise.all`/`jQuery.when`/döngüde ardışık çağrı yok | RAP `lock master` BO'da kilit çakışması → "Kaydedilemedi" / "bloke edildiği için düzenlenemez" ama işlem yine de kısmen olur |
| S3 | Deep nav yoluna **`createEntry` kullanılmaz**; yeni kayıt + kalemler **tek nested POST** | `createEntry` ertelenir (submitChanges ister); nav yolunda istisna atıp akışı sessizce keser → "Kaydet'e basınca tepki yok" |
| S4 | **Değişmiş mevcut kalemler için de UPDATE** gönderilir (yalnız create + delete değil) | Kalemde değiştirilen değer kaydedince eski hâline döner |
| S5 | Kalem UPDATE gövdesine **anahtar alanı konmaz** (anahtar URL'de) | 400 |
| S6 | Gövdeye **yalnız düzenlenebilir alanlar**; salt-okunur `*Name`/`*Text`/hesaplanan alanlar konmaz | Tüm MERGE 400 ile reddedilir |
| S7 | **Boş tarih = `null`**, `""` değil (`oBody.DateField = v || null`) | `Edm.DateTime`'da 400 |
| S8 | Dolu tarih **JS `Date` nesnesi**, string değil (§5.3) | `Conversion error for property '<X>' at offset N` |
| S9 | `hasPendingChanges()` ön kontrolü **kullanılmaz** | İki yönlü binding gecikmesinde `false` döner → ilk Kaydet yutulur, ikincide çalışır |
| S10 | Kısmi hata sonrası **`_reload()` ile model ↔ DB yeniden eşitlenir** | Tekrar denemede aynı `remove` yeniden üretilir → 404 → save kalıcı kilitlenir |
| S11 | Sıralı adımları "thunk"a çevirirken **build anında hesaplanan değer thunk'ın dışında sabitlenir** | Örn. `ItemNo: ("00000" + maxNo).slice(-6)` thunk içinde hesaplanırsa birden çok yeni kalem **aynı anahtarla** create edilir |
| S12 | Create ve Change controller'ları ortak base'den; biri düzeltilince ikizi de aynı satırda kontrol edilir | Hata birinde düzelir, ikizde kalır (alan listesi, cascade, VH haritası) |

### 1.2 Commit bariyeri
`onSave`/`onCreate` doğrudan `_save()` çağırmaz: önce `document.activeElement.blur()`, sonra `setTimeout(_save, 0)`.
Yoksa son düzenlenen `Input`/`DatePicker` değeri modele yazılmadan gönderilir.

### 1.3 JSON edit-buffer (düzenlenebilir alt grid)
- Düzenleme oturumu **istemci JSON modelinde**: `{ header:{}, items:[] }`.
- OData yalnız **yükleme** (`read` + `$expand: "to_Child"` → buffer) ve **açık save** (§1) için kullanılır.
- Ekle/sil anında buffer'da görünür (V2 nav-binding yeni/transient ebeveyn altında `createEntry` satırını göstermez —
  "satır ekle'ye basınca gelmiyor, kaydedince geliyor" belirtisi).
- Yeni satır işareti: `__new: true`; save'de create/update/remove ayrımı buna ve yükleme anındaki anlık görüntüye göre.

### 1.4 Kaynaktaki ikinci desen — karışık kullanma
Kaynak playbook'un "kanonik desen" bölümündeki bir örnek başlık/kalem MERGE'lerini sıralı `update` ile yapıp **yeni
kalemi `createEntry` + sonda `submitChanges`** ile gönderiyordu. Aynı kaynağın hata listesi bu karışımı "busy sonsuz
döner, save hiç bitmez" sınıfı olarak işaretliyor ve S3 ile çelişiyor. **Bu skill yalnız §1 desenini (nav yoluna
`create` + `_runSeq`) önerir.**

## 2. `setData`, master-detail, navigation adı

### 2.1 V2 navigation adı = `to_X`
RAP composition/association `_Item` → OData V2 metadata'da **`to_Item`**. `createEntry("_Item")`,
`$expand: "_Item"`, `read(".../_Item")` **sessizce kırılır** (Create kaydı boş, Change kalemleri yüklenmez).
Belirti: `Resource not found for segment '_Item'`. Adı `$metadata` `NavigationProperty Name=` ile doğrula.
Otomatik: `scripts/check_ui5_freestyle_traps.py` **T1 = ERROR**.

### 2.2 `setData` tam şekil
`_load` başarısında `setData({ header, items })` yazılırsa `sel`/`hasSel`/`messages` düşer → detay paneli seçim
yapılmadan açık kalır, seçince dolmaz. Daima tam şekil:
```javascript
oBuf.setData({ header: h, items: a, sel: {}, hasSel: false, messages: [] });
```

### 2.3 Master-detail (kalem tablosu → detay panel)
```xml
<Table id="tblItems" mode="SingleSelectMaster" selectionChange=".onSel" items="{bk>/items}"> … </Table>
<VBox visible="{bk>/hasSel}"> … </VBox>
```
```javascript
onSel: function (oEvt) {
    var oCtx = oEvt.getParameter("listItem").getBindingContext("bk");
    this._buf().setProperty("/sel", oCtx.getObject());
    this._buf().setProperty("/hasSel", true);
},
_load: function () {
    this.byId("tblItems").removeSelections(true);   // bayat seçim sonraki tıkta selectionChange'i yutmasın
    …
}
```
Grid'de (`sap.ui.table.Table`) karşılığı `clearSelection()`; seçimin **nerede** temizleneceği (tek giriş noktası,
`rowsUpdated` değil) → `delete-flow-ui.md` §1.

### 2.4 Composition kalem anahtarı
Kayıtlı kalemde anahtar alanı **salt-okunur**; değiştirmek = satırı sil + yeni ekle. Backend `field ( readonly : update )`
(`%sap-rap`); UI:
```xml
<Input value="{v>KeyField}" editable="{= ${ui>/edit} &amp;&amp; !!${v>__new} }"/>
```

### 2.5 İstemciye özel `_` alanları OData context'e yazılmaz
Hesaplanan yardımcı alanı (`_miktarPak` gibi) `setProperty` ile **OData entity context'ine** yazmak entity'yi pending
change yapar; aynı model `submitChanges`/`createEntry` kullanıyorsa bilinmeyen `_x` backend'e gider → 400. Yardımcı
alanlar **ayrı JSON modelde** (yol anahtarlı) tutulur.

## 3. Value-help (F4)

| # | Kural | Neden |
|---|---|---|
| C1 | Onayda değer **kontrole doğrudan** yazılır: `oInput.setValue(sCode); oInput.setDescription(sName);` **ve** model property'sine | Yalnız binding'e güvenmek (yol/context farkı) seçimi yansıtmayabilir; yalnız `setValue`'ya güvenmek de OneWay yenilemede silinir — ikisi birlikte |
| C2 | Kod + ad: backend projeksiyonunda `<X>Name` expose; UI `description="{…Name}"`; onayda ad anında basılır | Association salt-okunur, yenilemeye kadar boş kalır |
| C3 | Tek `_openVH` hem başlık hem satır için: `oInput.getBindingContext("v")` varsa satır (göreli yol + context), yoksa başlık (mutlak yol) → `setProperty(sPath, v, oCtxOrUndefined)` | Başlık/satır karışınca yanlış kayda yazar |
| C4 | Yazma hedefi **çağıran input'un binding yolundan** türetilir: `oEvt.getSource().getBinding("value").getPath()` | Aynı tipte iki alan (örn. iki muhatap) tek handler'ı paylaşınca sabit hedef hep aynı alana yazar, diğeri boş kalır. Her F4'ten sonra **kendi** alanı doluyor mu ölç |
| C5 | Değer yazılmıyorsa üç nokta birebir eşleşmeli: (1) Input value binding'i `{model>/path}` + context, (2) `valueHelpRequest` → dialog `confirm` → `setProperty`, (3) aynı model adı + aynı yol. Item şablonu `title/description` VH entity'sinde **olan** property'lere bağlı | Yanlış model adı (`v` ↔ `ui`), mutlak/göreli yol uyumsuzluğu, olmayan property (`getTitle()` boş) |
| C6 | VH listesi **boş geliyorsa** önce servis: VH entity set'i tüketen servisin `$metadata`'sında **var mı** | Ortak VH yeniden adlandırıldıktan sonra bir tüketici serviste `expose` atlanmıştı; UI kodu doğruydu. Düzeltme backend'de (`%sap-rap`), UI redeploy gerekmez |
| C7 | **Elle girilen değer VH'de yoksa** reddedilir: `change` handler değeri VH entity'sine karşı doğrular → `setValueState("Error")` + `valueStateText` + veri modelinde `<X>Invalid = true`; save/create bu bayrağı kontrol edip **bloklar**. Geçerli yol (VH'de var / F4 seçimi / boş) → `None` + bayrak temizlenir | Yalnız `valueState`'e güvenilmez (satır/context değişiminde kaybolur) |
| C8 | Alt tanım (ad/açıklama) her VH alanında gösterilir: input + altında `<Text class="zxx001FieldDesc">` | Kod çalışır ama standart eksik |

Rapor/liste **filtre ekranındaki** VH deseni farklıdır (MultiInput + ValueHelpDialog, çoklu değer + aralık) →
`list-grid-alv.md` §6.

## 4. Tuzak listesi (T1–T7) ve otomatik yakalananlar

| # | Tuzak | Belirti | Çözüm | Yakalayan |
|---|---|---|---|---|
| T1 | V2 navigation `_X` | Create kaydı boş / `$expand` boş | `to_X` (§2.1) | `check_ui5_freestyle_traps.py` **ERROR** |
| T2 | Düzenlenebilir miktar `Input type="Number"` | Ok tuşu değeri değiştirir, grid gezinmesi bozulur | `type="Text"` + `onNumericLiveChange` (§5.4) | aynı script **WARN** (filtre sayacı gibi meşru istisna var) |
| T3 | `core:Title` VBox/HBox/CSSGrid çocuğu | View render çöker "not valid for aggregation" | `sap.m.Title` | aynı script **WARN** (Form içinde meşru) |
| T4 | `f:Form`/`SimpleForm` + `ColumnLayout` içinde form içeriğine HBox/VBox/FlexBox/Panel | Dialog/view **hiç açılmaz**; konsol "Element sap.m.HBox is not a valid Form content" | Kontrolleri doğrudan kardeş `f:fields` ya da ayrı `f:FormElement` | aynı script **ERROR** — yalnız `<f:fields>` içini tarar; `SimpleForm`'un doğrudan içeriği taranmaz (runtime) |
| T5 | Save `setProperty` + `submitChanges` | Programatik değer kaydedilmez | §1 S1 | runtime (yok) |
| T6 | Eşzamanlı `update` | "Kaydedilemedi" (BO kilidi) | §1 S2 | runtime (yok) |
| T7 | MERGE'de boş tarih `""` · `setData` eksik şekil | 400 · detay paneli açık/dolmaz | §1 S7 · §2.2 | runtime (yok) |

- T4 **XML olarak geçerlidir**: `node --check`, XML doğrulama ve kod incelemesi yakalamaz; aynı HBox deseni VBox/CSSGrid
  içinde geçerli olduğu için başka ekrandan kopyalanınca çıkar → view/dialog **açılarak** doğrulanır.
- Script kapsamı: çıktıdaki `KAPSAM` satırı; bakmadığı her şey (runtime, semantik) bu tabloda "runtime".

## 5. Binding tipleri ve sayısal girdiler

### 5.1 OData tipleri
Sayısal/tarih OData binding'inde tip zorunlu:
```xml
<Text text="{ path: 'Quantity', type: 'sap.ui.model.odata.type.Decimal', constraints: { scale: 3 } }"/>
<Text text="{ path: 'OrderDate', type: 'sap.ui.model.odata.type.DateTime', constraints: { displayFormat: 'Date' } }"/>
```
Tipsiz binding'de parse/serileştirme hataları (`CX_SXML_PARSE_ERROR` gibi) görüldü. `Decimal` `constraints` değerleri
servis metadata'sındaki `Precision`/`Scale`'e göre — DOĞRULANMADI: örnekteki `scale: 3` temsili.

### 5.2 CHAR1 bayrak → CheckBox
```xml
<CheckBox selected="{= ${v>Blocked} === 'X' }" select=".onBlockedSelect"/>
```
`select` handler'ı `'X'`/`''` değerini buffer'a geri yazar. Doğrudan `selected="{Blocked}"` → `"" is of type string,
expected boolean`. **Önce Edm tipine bak:** alan metadata'da `Edm.Boolean` ise bayrak deseni değil `true/false`
kullanılır (§5.3).

### 5.3 Payload Edm tipi canlı metadata ile birebir
| Canlı Edm tipi | Gönderilen |
|---|---|
| `Edm.Boolean` | `true`/`false` (`'X'`/`''` değil → `Failed to read property '<X>' at offset N`) |
| `Edm.DateTime` / `DateTimeOffset` | `Date` nesnesi. `DatePicker value="{…}" valueFormat="yyyy-MM-dd"` modeli **string** tutar → payload'da `new Date(Date.UTC(y, m - 1, d))` (saat dilimi kaymasına karşı UTC parçaları) ya da `DatePicker dateValue="{…}"` |
| `Edm.Decimal` | model değeri ne ise; decimal'in backend'de string'e çevrilmesi `%sap-odata-backend` → `references/serialization.md` §1 |
| boş tarih | `null` |

Okuma tarafı da: `Edm.Boolean` alanı `=== 'X'` varsayan formatter yanlıştır. **Yerel `localService/metadata.xml`
bayat olabilir** — kaynakta mock "String" derken canlı alan Boolean'dı. Create ↔ Change paritesi ayrıca kontrol edilir
(biri `dateValue` doğru, ikizi `value`-string kırıktı).

### 5.4 Düzenlenebilir sayısal Input — `type="Number"` yok
Tarayıcı `<input type="number">` yukarı/aşağı ok tuşuyla değeri artırır/azaltır → kullanıcı satırlar arasında gezinirken
**miktar sessizce değişir**; UI5'te bunu kapatan property yok.
```xml
<Input value="{v>Quantity}" type="Text" textAlign="End" change=".onItemQtyChange" liveChange=".onNumericLiveChange"/>
```
```javascript
onNumericLiveChange: function (oEvent) {
    var oInput = oEvent.getSource(), sVal = oEvent.getParameter("value");
    if (sVal == null) { return; }
    var sClean = sVal.replace(/[^0-9.,]/g, "").replace(/,/g, ".");
    var p = sClean.split("."); if (p.length > 2) { sClean = p[0] + "." + p.slice(1).join(""); }
    if (sClean !== sVal) { oInput.setValue(sClean); var oB = oInput.getBinding("value"); if (oB) { oB.setValue(sClean); } }
}
```
`change`'de üst sınır/doğrulama `parseFloat` ile ayrıca yapılır.

### 5.5 Miktar gösterimi — formatter
QUAN alanı `"14.000"` gelir; `<Text text="{v>Qty} {v>Unit}"/>` düz birleştirme `14.000 ADT` basar. Grid hücresi
formatter'lıyken detay paneli ham kalabiliyor (kopyalarken atlanıyor). Her miktar `Text`/`Label` binding'i formatter
kullanır: `{ parts: ['v>Qty', 'v>Unit'], formatter: '.formatter.qty' }` (sondaki sıfırları kırpan; `String(Math.round(q * 1000) / 1000)`).

### 5.6 İki koleksiyonu anahtarla birleştirirken sıfır dolgusu
OData entity okuması conversion exit uygular (`OrderItem = "10"`), ham CDS/RAP façade uygulamayabilir (`"000010"`).
`no + "|" + item` birleştirmesi **sessizce %100 eşleşmez** → tüm birleşen alanlar null, UI boş; hiçbir hata yok.
```javascript
var keyOf = function (no, it) { var n = parseInt(it, 10); return no + "|" + (isNaN(n) ? it : n); };
```
Aynı tuzak VBELN/POSNR/MATNR gibi her dolgulu alanda. Tespit statik analizle yapılamadı; runtime'da iki tarafın
anahtarları model API'siyle okunup karşılaştırıldı (`runtime-verification.md` §4). Backend tarafı:
`%sap-odata-backend` → `references/serialization.md` §3.

## 6. Kullanıcı geri bildirimi ve hata metni

### 6.1 Save/create/aksiyon başarısı
```javascript
MessageBox.success(this._t("msg.saved", [sDocNo]), { onClose: function () { this._nav(); }.bind(this) });
```
- Modal, garantili görünür; navigasyon kullanıcı **OK** deyince. Belge numarası varsa metinde.
- ⛔ `MessageToast.show()` + hemen `navTo` → toast sayfa geçişinde kaybolur ("mesaj gelmedi"). Toast yalnız
  **navigasyonsuz** anlık bilgi için (satır seçildi, kopyalandı).

### 6.2 `_parseError` — gerçek SAP mesajı
Sabit i18n metni ("Kaydedilemedi") kök nedeni gizler → kör deneme-yanılma. Her error callback gerçek yanıtı basar:
```javascript
_parseError: function (oErr) {
    var aOut = [];
    try {
        var o = JSON.parse(oErr.responseText).error;
        if (o && o.message && o.message.value) { aOut.push(o.message.value); }
        var aDet = (o && o.innererror && o.innererror.errordetails) || [];
        aDet.forEach(function (d) {                         // severity alanı yoksa atlama (Gateway bazen göndermez)
            if (d.message && aOut.indexOf(d.message) < 0) { aOut.push(d.message); }
        });
    } catch (e) { /* JSON değil */ }
    return aOut.length ? aOut.join("\n") : (oErr.message || this._t("msg.errGeneric"));
}
```
- Çok satırlı: bir validation birden fazla engeli `innererror.errordetails[]` içinde birlikte döndürebilir; yalnız
  `error.message.value` okumak ikinciyi yutar. Mükerrer satır elenir, çözümlenemezse genel metne düşülür.
- `useBatch:true` kullanan istisnai akışta `__batchResponses`/`__changeResponses` içindeki ≥ 400 yanıtlar da basılır.
- ⚠ Paylaşılan bir yardımcıyı **tek tüketici için değiştirme**: önce kullanım yerlerini grep'le; başka çağıranı ya da
  kardeş uygulamada ayna kopyası varsa yalnız çağrı yerini yeni parser'a çevir.
- Form doğrulama hataları (çoklu) için `MessagePopover` (`fiori-elements-ux.md` §4) — başarı geri bildiriminin yerine geçmez.

## 7. Function import

### 7.1 Sonuç sarmalayıcısı ve `Success`
```javascript
success: function (oData) {
    var oRes = oData.ReleaseOrder || oData;                         // [1] sonuç FI adıyla sarmalanabilir
    var bOk = oRes.Success === true || oRes.Success === "true" || oRes.Success === "X";
}
```
`[0..*]` sonuç → `oData.results`. Sonuç property adları metadata'dakiyle **birebir** (büyük/küçük harf).

### 7.2 `read` mi `callFunction` mi
- SEGW'de function import'un **EntitySet**'i olabilir ve eski UI `read("/XxxResultSet", {urlParameters})` yapar;
  RAP'e taşınınca bu bir FI'dır → `callFunction("/Xxx", { method: "GET", urlParameters })`.
- Tersi de: servis `read` bekleyen bir set sunarken `callFunction(... method: "POST")` → **405 Method Not Allowed**.
- **Hangisi olduğunu `$metadata` söyler** (`EntitySet` mi `FunctionImport` mu, `m:HttpMethod`); tahmin edilmez.
- RAP V2 metadata'da olmayan parametre → `400 Invalid parameter` (SEGW gevşekti); fazla parametre çıkarılır.
- Uzun JSON parametresi URL'ye gidiyorsa kısa anahtarlar (`I`/`Q`/`M`/`U`) URL uzunluğunu düşürür — URL sınırı
  sistemden sisteme değişir, DOĞRULANMADI.

## 8. Canlı `$metadata` ile statik çapraz kontrol

Her binding, MERGE/CREATE payload alanı, navigation, function import ve parametresi **aktif servisin canlı
`$metadata`'sına** karşı doğrulanır. Kaynaklarda bir alan projeksiyonda yeniden adlandırılmıştı; eski ad yerel
`metadata.xml`'de ve eski spesifikasyonda duruyordu → başlık kaydı geçti, o alanı içeren kalem MERGE'i 400 verdi (deep
insert'te SADL bilinmeyen property'yi **sessizce düşürür**).

**Araç (çevrimdışı):**
```bash
# 1) Geliştirici tarayıcıda açar ve kaydeder: https://<SAP_HOST>:<PORT>/sap/opu/odata/sap/<SERVIS>/$metadata?sap-client=<CLIENT>
# 2) Çok servisli uygulamada her ikincil servis için de
python <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/check_ui_odata_refs.py --app <app> --metadata <main.xml> \
       --metadata-for ZCA000_VH_O2=<vh.xml>
```
- `callFunction` → FunctionImport (+parametre), `read`/binding → EntitySet, `Filter`/`$orderby`/`$select` → Property.
- **Çıkış 0 tek başına "temiz" değildir — hüküm satırını ve `BAKILMAYANLAR` bloğunu oku:** değişkenli
  `new Filter(sProp, …)`, view'daki göreli `{Prop}`, Component/util dosyaları ölçülmez; modeli statik çözülemeyen
  referans ana servise karşı ölçülür (yanlış KIRMIZI olabilir).
- Çıkış 2 = ölçüm yok (metadata EDMX değil — çoğunlukla kaydedilen dosya bir logon sayfasıdır — ya da ikincil servis
  metadata'sı verilmedi). Kırmızı değildir, temiz de değildir.
- aXet CLI'sinde `$metadata` okuma aracı yoktur; ikinci bir bağlantı yolu kurulmaması için script ağa çıkmaz.

### 8.1 Kopya UI'ı yeni servise taşırken (ör. SEGW → RAP) görülen tuzaklar
| Tuzak | Belirti | Çözüm |
|---|---|---|
| Namespace'in eğik çizgi biçimi değişmemiş | Component yüklenemedi (`failed to resolve 'com/.../model/models'`) | `app-skeleton.md` §1 |
| FI-as-EntitySet | `Resource not found for segment 'XxxResultSet'` | §7.2 |
| Geçersiz FI parametresi | `400 Invalid parameter` | §7.2 |
| `[1]` sonuç sarmalama | `oData.Field` undefined | §7.1 |
| Sonuç property harf farkı | UI'da boş alan | metadata'daki ad birebir |
| VH/entity set başka pakete taşınmış | VH `Resource not found` | yeni ad + tüketici servis `expose` (§3 C6) |

## 9. i18n

- `i18n/i18n.properties` = İngilizce (varsayılan), `i18n/i18n_tr.properties` = Türkçe; manifest
  `supportedLocales ["", "tr"]`, `fallbackLocale ""`.
- **Etiket/metin değişikliği ve yeni anahtar HER İKİ dosyada.** `language=tr` ile TR dosyası yüklenir ve varsayılanı
  ezer → yalnız birini değiştirmek TR'de eski metni bırakır. `grep -n "<key>" webapp/i18n/i18n*.properties` →
  bulunan tüm dosyalar. Sonra kullanıcıya **hard refresh (Ctrl+F5)** (bundle önbelleklenir).
- TR dosyası kısmi olabilir: eksik anahtar varsayılana düşer; varsayılan ASCII-translit ise kullanıcı diyakritiksiz metin
  görür (kaynakta silme onayı "Secili 1 kalem silinsin mi?" çıktı; aynı yerde bir yazım hatası altı inceleme turunda
  görülmedi, ekranda görüldü).
- `{0}` yer tutucu kümeleri iki dosyada birebir; MessageFormat'ta yer tutuculu metinde tek kesme işareti (`'`) kaçış
  karakteridir → `''` yazılır.
- Kardeş uygulamadan metin kopyalamadan önce anlam kontrol edilir (aynı anahtar farklı anlam taşıyabilir).
- Kopyalanan util'in (`TablePersonalizer` gibi) çağırdığı anahtarlar diff'te olmasa da kontrol edilir (kaynakta ham
  anahtar "btn.cols" ekranda göründü).
- Otomatik: `python scripts/check_i18n_keys.py <app> [--js-helper _txt]` (değişken anahtarları göremez — KAPSAM satırı).

## 10. `$batch` (yalnız bilinçli istisna)
Varsayılan `useBatch:false`: her işlem anında gider, **changeset yoktur → kısmi başarı mümkündür** (S10). `useBatch:true`
seçilen akışta deferred group + tek `submitChanges`, sonuç `oData.__batchResponses` içinde her işlem için ayrı kontrol
edilir (≥ 400 olan var mı). İki mod aynı ekranda karıştırılmaz.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Müşteri uygulama/servis adları, commit numaraları, müşteri iş örnekleri (liman, konteyner, sevkiyat) jenerik
  örneklere çevrildi.
- Kaynak playbook'taki save kutusu başarıda `MessageToast` + navigasyon diyordu; aynı kaynağın kodlama standardı ve hata
  listesi bunu yasaklıyor → §6.1 `MessageBox.success` desenine hizalandı (çelişki raporlandı).
- Kaynak "kanonik desen" örneğindeki `createEntry` + `submitChanges` karışımı alınmadı (§1.4).
- `_parseError` kaynakta tek satırlıydı; aynı kaynağın silme akışı dersi çok satırlı olmasını istiyor → birleştirildi.
- `check_ui_odata_refs` kaynakta canlı `$metadata`'yı bağlantı dosyasından kimlikle çekiyordu; aXet'te çevrimdışı dosya
  alır. `check_ui5_freestyle_traps` T4 (Form içinde container) kaynakta aday satırdı; aXet script'inde ERROR olarak var.
- Belge kilidi (uygulama kilidi, heartbeat) ve denetim alanı otomatik doldurma kuralları bu skill'e alınmadı: backend
  sözleşmesi `%sap-rap`/`%sap-cds-ddic`; UI kontrol satırı `checklists.md`'de.
