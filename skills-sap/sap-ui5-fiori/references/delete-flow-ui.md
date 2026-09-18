# Silme akışı — UI tarafı (seçim, pending guard, sıralı remove, mesaj, i18n, kabul testi)

> Backend tarafı (guard'ın beş katmanı, iş kuralının tek kaynağı, ön yüz kapısını kaldırmadan önce backend ölçümü,
> cascade, RAP mesajının 50 karakterde kesilmesi, validation kodlama tuzakları) `%sap-rap` → `references/delete-guard.md`.
> Bu dosya yalnız tarayıcı tarafıdır ve backend dosyasını tekrar etmez.

---

## 1. Liste daralınca / yeniden sıralanınca seçim bayatlar → YANLIŞ KAYIT SİLİNİR

**Mekanizma:** `setData` / binding yenileme satırları **yeniden indeksler**.
- `sap.m.Table`: `rememberSelections` varsayılan `true` → seçim binding-context yolundan geri yüklenir.
- `sap.ui.table.Table`: seçim **indeks bazlı** (`getSelectedIndex()`/`getSelectedIndices()`), kayıt `aList[iIdx]` ile okunur.

→ A silinir, B "seçili" görünür → sonraki Sil **B'yi** siler. Silme anında DB'ye gidiyorsa geri alınamaz.

**Çözüm — temizliği çağrı yerlerine dağıtma, ortak giriş noktasına al:**
```javascript
_reload: function () {
    this._clearSelection();                // ilk satır: bugünkü ve gelecekteki tüm çağrı yolları kapsanır
    …
},
_clearSelection: function () {
    var oT = this.byId("tblItems");
    if (oT.clearSelection) { oT.clearSelection(); }           // sap.ui.table.Table
    else if (oT.removeSelections) { oT.removeSelections(true); } // sap.m.ListBase — bAll=true şart
    this._buf().setProperty("/sel", {}); this._buf().setProperty("/hasSel", false);
}
```
Kaynakta bir turda 7 dağıtık temizlik → 2 giriş noktası (net kod azaldı).

| Dikkat | Neden |
|---|---|
| `removeSelections(true)` — `bAll` şart | Hatırlanan seçim kümesini de siler; yoksa `setData` sonrası seçim geri gelir |
| ⛔ **`rowsUpdated`'a bağlama** | `sap.ui.table` bu olayı `VerticalScroll`, `FirstVisibleRowChange`, `Resize`, `Zoom`, `Render` sebepleriyle de fırlatır → **scroll ederken ve pencere boyutlanırken seçim silinir** |
| Temizlik `remove()` sonrasına değil **`success` callback'ine** | `refreshAfterChange` otomatik yenileme senkron değil |
| **Sınıf sınırı:** `Child._reload`'a koyup `Parent._reload`'a koymamak | Değişmez tek sınıfta kalır, Parent'a eklenecek yeni çağrı korumasız olur (maliyeti bir satır) |
| Giriş guard'ı **o fonksiyondan geçmeyen** yolu kapsamaz | Modeli doğrudan güncelleyen bir başarı yolu varsa oradaki temizlik kaldırılmaz (asimetri gerçektir). "Bu yol gerçekten `_reload`'dan geçiyor mu" → ölç |
| Kalem tablosu **dışını da tara** | Atama/ilişkili kayıt tablolarında da seçim bazlı silme olabilir; listeyi **yeniden sıralayan** her yer (filtre + yeniden ekle) aynı sınıftır |
| Grid native kolon menüsü | Sort/filtre binding'i uygulama kodundan geçmeden yeniden kurabilir → kişiselleştirme katmanı ayrı değerlendirilir |
| Seçim anahtarı indeks değil **belge no** ise | Bu sınıf yapısal olarak yok (en kötü "kayıt yok"); yine de `_loadData` girişinde seçim durumu null'lanır |

Kabul: seçim regresyonu **sayıyla** — `getSelectedIndices().length` / `getSelectedItems().length`.

## 2. Model-only silme → anında DB silme: yeni sözleşme

Önce: silme yalnız istemci modelinden çıkarıyordu, gerçek DELETE Kaydet'teydi → kullanıcı kaydetmeden çıkarsa hiçbir şey
olmamıştı. Sonra: silme **anında ve geri alınamaz**. Bu üç şeyi zorunlu kılar:

1. **Pending-change guard'ı TÜM düzenlenebilir alanları kapsar — BAŞLIK DAHİL.** Kapsamazsa: kullanıcı başlığı değiştirir
   → kalem siler → `_reload()` başlığı DB'den geri kurar → **düzenleme sessizce kaybolur**; tek geri bildirim başarı mesajıdır.
2. **Detektörün diff'lediği alan kümesi = `onSave`'in MERGE payload'ı, 1:1** (başlık ve kalem ayrı ayrı) + eklenmiş
   (anahtarı boş) + çıkarılmış (anlık görüntü farkı) kayıtlar. Payload'da olup detektörde olmayan her alan = sessiz veri
   kaybı. **Uygulamalar arası kopyalanmaz** — her uygulamanın kendi payload'ından ve kendi view'ındaki düzenlenebilir
   kontrollerden ölçülür (kaynakta kardeş uygulamalarda 4+3 / 3+2 / 3+1 alan çıktı).
3. Kullanıcının "Kaydet'e basmadan hiçbir şey yazılmaz" zihin modeli kırıldığı için "demek diğerleri de işlendi" varsayımı
   makul hâle gelir → uyarı metni bunu açıkça söyler.

Kıyas tuzakları:
```javascript
var same = function (a, b) {
    if (a instanceof Date || b instanceof Date) { return +new Date(a) === +new Date(b); } // DatePicker dateValue = Date nesnesi; ham !== eşit tarihte true der
    if (typeof a === "boolean" || typeof b === "boolean") { return !!a === !!b; }          // Edm.Boolean undefined vs false
    return (a == null ? "" : String(a)) === (b == null ? "" : String(b));
};
```
**Yanlış pozitif kontrolü:** `_populate` sonrası asenkron yazıcılar (otomatik doldurma, açıklama çekme) diff'lenen alanlara
yazıyorsa detektör **her silmeyi** bloklar — o zaman düzeltmenin kendisi hatadır; anlık görüntü o yazıcılardan sonra alınır.

## 3. Çoklu `remove`/`update` paralel çalışırsa kilit çakışır

`Promise.all(ops)` + `new Promise` executor'ı **senkron** çalışır → istekler dizi kurulurken uçar. `useBatch:false` →
changeset yok → **kısmi silme mümkün**, paralellik gerçek ağ paralelliğidir ve aynı BO'da kilit çakıştırır.
→ Sıralı koşucu + thunk (`freestyle-odata-v2.md` §1 `_runSeq`):
```javascript
var aSteps = aDel.map(function (oRow) {
    var sPath = "/" + oModel.createKey("ItemSet", { OrderId: oRow.OrderId, ItemNo: oRow.ItemNo }); // build anında sabit
    return function (done, fail) { oModel.remove(sPath, { success: done, error: fail }); };
});
this._runSeq(aSteps, fnOk, fnErr);
```
- ⚠ **Kapanış tuzağı:** build anında hesaplanması gereken değer (yol, yeni anahtar `("00000" + maxNo).slice(-6)`) thunk'ın
  **içine** alınırsa son değere kayar → birden çok kayıt **aynı anahtarla** create/delete edilir. `ops` içindeki her dış
  değişken kapanış açısından izlenir.
- Bilinçli sonuç: sıralıda ilk hatadan sonraki adımlar çalışmaz → kısmi başarıdan sonra `_reload()` (aksi hâlde tekrar
  denemede aynı `remove` 404 verir ve save kilitlenir).

## 4. Mesaj ve dil

- Hata parser'ı **çok satırlı**: ana mesaj + `innererror.errordetails[]` (bir validation birden fazla engeli birlikte
  döndürebilir). Gövde `freestyle-odata-v2.md` §6.2. Paylaşılan util tek tüketici için değiştirilmez.
- Engel mesajının **belge numarası taşıyıp taşımadığı** ölçülür (mesaj biçiminin amacı buydu; numarasız mesaj da
  "görünüyor" testinden geçer). Uzunluk sınırı backend'dedir (`%sap-rap` delete-guard §6).
- Silme/onay/uyarı metinleri **iki i18n dosyasında**; yer tutucu kümeleri birebir; tek kesme tuzağı
  (`freestyle-odata-v2.md` §9). Kardeş uygulamadan metin kopyalamadan önce anlam kontrolü.
- Onaysız silme yok: `MessageBox.confirm`; geri alınamaz işlemde uyarı tipi.

## 5. Kabul ölçütü — minimum runtime test seti

1. **Engellenmesi kanıtlı** bir kayıtta silme → mesaj görünüyor mu · **belge numarası var mı** · uzunluk sınırın altında mı ·
   **silme anında mı** (kaydetme anında değil).
2. **Seçim regresyonu:** silme/red sonrası satır seçili kalıyor mu → sayıyla.
3. **Pending guard:** düzenle → kaydetme → sil → uyarı çıkıyor mu · **düzenleme korunuyor mu**.
4. Her denemenin **öncesi ve sonrası** veri okunarak doğrulanır ("değişmedi" iddiası ölçülür).

- ⛔ **Test verisi yaratılmaz.** Engellenecek kayıt yoksa "DOĞRULANAMADI (sebep)" yazılır — bu değerli bilgidir.
- ⛔ **Engellenmesi kanıtlanmamış kayıtta silme denenmez.** Guard'ın canlıda var, güncel ve kablolu olduğu doğrulanmadan
  gerçek silme yapılmaz — guard eski sürümdeyse silme **başarılı olur** ve kayıt geri gelmez. Silme denemesi SAP'de veri
  değiştirir → kullanıcıya açıklanır, onay alınır.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynak "silme kontrolü" playbook'unun §1–6 ve §12–13 backend bölümleri `%sap-rap`'ta; burada yalnız UI bölümleri (§7–11)
  ve kabul testinin UI yarısı.
- Müşteri uygulama adları ve tarihli vaka referansları çıkarıldı; ölçülen sayılar (7 → 2 giriş noktası, alan sayıları)
  bağlam olarak kaldı.
- Karşılaştırma yardımcısı (`same`) ve `_clearSelection` gövdesi kaynaktaki kurallardan yazıldı (kaynakta kod yoktu) —
  ilk kullanımda runtime'da ölçülür.
