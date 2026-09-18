# Doğrulama — "done" kriteri, statik kontroller, runtime ölçümü

> Kural: **"node --check OK / XML well-formed / script PASS" runtime ve fonksiyonel hatayı yakalamaz.** UI işi ancak
> statik kontroller **ve** runtime ölçümü birlikte geçince bitmiştir. Kaynak ekipte altı bug-gate turu + sözdizimi +
> grep geçen bir değişiklikte bozuk dil ve yazım hatası yine de ancak ekranda görüldü.

---

## 1. Dört katman

| Katman | Ne | aXet karşılığı |
|---|---|---|
| **Plumbing reuse** | Save/nav/setData/master-detail mekaniği kanonik desenden, icat edilmez | `freestyle-odata-v2.md` §1–2 |
| **Statik tuzak kontrolü** | Deterministik, saniyeler | §2 script'leri |
| **Done kriteri** | Statik PASS + runtime smoke + tam kapsam | §3 |
| **Runtime smoke** | Uygulama açılır, konsol yakalanır, ana akış çalışır | §4 (`scripts/ui-smoke/`) ya da kullanıcıyla elle |

## 2. Statik kontroller (hepsi stdlib Python, ağa çıkmaz)

```bash
S=<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts
python $S/check_ui5_freestyle_traps.py   <app> [--strict]     # T1 _X nav, T4 Form içi container = ERROR; T2 type=Number, T3 core:Title = WARN
python $S/check_list_view_grid.py        <app>                # liste/rapor adlı view'da sap.m.Table
python $S/check_filter_search_pattern.py <app>                # caseSensitive:false BLOCKER; filtre VH'si MultiInput değil WARNING
python $S/check_i18n_keys.py             <app> [--js-helper _txt] [--locale-optional]
python $S/check_ui_odata_refs.py --app <app> --metadata <main.xml> [--metadata-for SERVIS=dosya.xml]
python $S/deploy_ui.py prepare <app> --no-build               # deploy öncesi yapı (ağ yok)
```
- Çıkış: `0` bulgu yok · `1` bulgu · `2` **ölçüm yok** (yol yanlış, `webapp` yok, metadata EDMX değil). `2` temiz değildir.
- Her script sonunda **KAPSAM** satırı basar: neye bakmadığı. "0 bulgu" = "aracın baktığı yüzeyde bulgu yok"; özellikle
  sıfır bulguda KAPSAM satırı okunur ve rapora yazılır.
- UI5 linter (`@ui5/linter`) proje devDependency'si olarak kuruluysa `npx --no-install ui5lint` ek katmandır (deprecated
  API, eksik bağımlılık). Bu template'te kurulu değildir ve çıktısı DOĞRULANMADI; kurulum projede kullanıcı kararıdır.
- Kontrol API'si / property / aggregation adı şüphesinde tahmin edilmez: UI5 API referansı (proje sürümü) okunur.

## 3. Done kriteri

1. Statik kontroller çalıştı, bulgular düzeltildi ya da gerekçeli istisna yazıldı; KAPSAM satırları raporda.
2. **Runtime smoke** geçti: uygulama açılır, **sıfır gerçek konsol hatası** (render crash yok), `$metadata` 200, ana akış
   (liste yükle → filtrele → detay → kaydet/aksiyon) en az bir kez. Dialog/view'ı **açarak** (Form içi container gibi
   hatalar yalnız render'da çıkar).
3. **Tam kapsam:** çıktı istenen işin her maddesine karşı tek tek doğrulandı. Spesifikasyondaki bir kural (gating,
   cascade, zorunlu alan) **UI'da gerçekten kodlandı mı** — bir analiz/recon belgesi implementasyon değildir. Bilinçli
   ertelenen parça açıkça yazılır.
4. **Kör hata düzeltme yok:** "Kaydedilemedi" gibi opak hatada deneme-yanılma yapılmaz → önce gerçek hata alınır:
   tarayıcı F12 Network (status + yanıt gövdesi) / Console, ya da `_parseError` çıktısı. Kanıtsız tek satır bile
   değiştirilmez. Bir çare ilk denemede tutmadıysa tekrarlanmaz, dayandığı teşhis sorgulanır.
5. Alt ajandan gelen "done/verified" raporu kanıt (komut + çıktı) olmadan kabul edilmez → `%verify-done`.

## 4. Runtime ölçüm teknikleri

### 4.1 `scripts/ui-smoke/` — Playwright smoke
Tekrarlanabilir, başsız, commit'lenebilir smoke seti (config + genel spec + koşucu).
```bash
# Ön koşul (bir kez, proje kararıyla; global kurulum değil):
#   cd <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/ui-smoke && npm install && npx playwright install chromium
# Uygulama lokal çalışıyor olmalı (deploy-and-local-run.md §1); kimlik geliştiricinin kabuğunda:
#   FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD
python <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/ui-smoke/run_ui_smoke.py --port <port> [--spec ui.smoke.spec.ts] [--no-auth]
```
- Koşucu Playwright'ı **kurmaz**; yoksa kurulum komutunu yazıp çıkış 2.
- **Hesap kilidi önlemi:** testten önce **tek** kimlik denemesi (`/sap/opu/odata/sap/`); 401 → çıkış 3, **tekrar denemez**
  (tekrarlı başarısız logon kullanıcıyı kilitler). `retries: 0`.
- Fiori dev proxy'si basic auth'u SAP'ye iletir → `httpCredentials` ile gerçek veri akışı test edilir (kaynakta ölçüldü).
- Spec: sayfa açılır, `$metadata` 200 + gövde boş değil, bilinen zararsız mesajlar (§5) dışında **sıfır konsol hatası**.
  Uygulamaya özel akış için spec kopyalanıp genişletilir (`--spec`).
- Etkileşimli tarayıcı otomasyonu (bir ajan için canlı tarayıcı sürmek) **gate değildir**: yavaştır ve taze bağlamda SAP
  oturumu olmadığından yalnız render görülür. Hata ayıklamada kullanılabilir.

### 4.2 Tıklama yerine UI5 API'si
Playwright `click()` bir `sap.m.Button`'da press handler'ını **tetiklemeyebilir** (koordinat/overlay/header artefaktı) —
buton enabled + visible + press bağlı olsa bile. "Düzeltme çalışmıyor" sanılır. Kaynakta: `click()` sonrası grid temizlenmedi
(5 satır kaldı); `firePress()` ve controller metodunun doğrudan çağrısı 5 → 0 yaptı.
```javascript
// page.evaluate içinde
sap.ui.core.Element.registry.get("<tam-id>").firePress();                     // gerçek press eşdeğeri
sap.ui.core.Element.registry.get("<view-id>").getController().onClearFilters(); // doğrudan çağrı
```
Buton sağlığı: `getEnabled()`, `getVisible()`, `mEventRegistry.press`, `getDomRef().offsetParent`.
`Element.registry` API'si yeni sürümlerde değişebilir — proje UI5 sürümünde DOĞRULANMADI.

### 4.3 Durumu DOM'dan değil modelden, sayıyla oku
- `view.getModel("<ad>").getData()` / `getProperty("/items").length` — `sap.ui.table` sanal satır DOM'u satır sayısında
  yanıltır.
- Seçim: `getSelectedIndices().length` (grid) / `getSelectedItems().length` (m.Table).
- Genişlik/hiza/scroll: `getBoundingClientRect()`, `scrollLeft` — piksel olarak ölç.
- "Backend doğru, UI boş/yanlış": model verisi ile OData sonucunu **aynı evaluate'te** yan yana oku (ör. iki koleksiyonun
  birleşim anahtarları) → sıfır dolgusu gibi sessiz uyumsuzluk anında görünür; aday düzeltme canlı denenir
  (`freestyle-odata-v2.md` §5.6).

### 4.4 Backend'siz mekanizma teyidi
Proxy auth'u engelliyken istemci davranışı için: `oModel.setProperty("/pool", [/* 30 geniş satır */]); oModel.refresh();`
→ gerçek render/autofit yolu çalışır, sonuç sayıyla ölçülür (kaynakta yatay scroll sıçraması 0 → 898 px ölçüldü, düzeltme
sonrası 0). Gerçek OData ile son smoke yine kimlikli ortamda.

### 4.5 Test verisi
- **Test verisi yaratılmaz** (SAP'de kayıt açma yok). Senaryoya uygun kayıt yoksa "DOĞRULANAMADI (sebep)" yazılır.
- Geri alınamaz işlem (silme) guard'ı canlıda var ve güncel olduğu kanıtlanmadan denenmez (`delete-flow-ui.md` §5).
- Her denemenin öncesi ve sonrası veri okunarak (OData GET / tablo okuma) "değişmedi" iddiası ölçülür.

## 5. Zararsız konsol gürültüsü — kovalanmaz
Build yapılmadan dev modda:
- `Component-preload.js` 404
- `favicon` 404
- `fallbackLocale 'en' not in supported locales` (locale uyarısı)
- "Defining object type 'Object' is deprecated"

Yalnız gerçek `Error` / kırmızı stack incelenir. Smoke spec'indeki IGNORE listesi bunlardır.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynakta "runtime gate aracı yalnız playwright-cli" kararı vardı; aXet'te bu CLI kurulu değil ve genel skill'i
  alınmadı. Yerine Node Playwright tabanlı `scripts/ui-smoke/` (proje içi kurulum) + elle konsol kontrolü.
- Kaynak koşucu kimliği proje bağlantı dosyasından okuyordu; aXet'te geliştiricinin ortam değişkeninden.
- Kaynaktaki özel bir akış spec'i (müşteri sevkiyat ekranı) ve yardımcı self-test'i alınmadı.
- Lider/alt ajan rol ayrımı (UI'ı kim sürer) aXet'te yok; kural "kanıtsız done kabul edilmez" olarak kaldı.
- UI5 linter'ın kaynaktaki araç entegrasyonu alınmadı; proje devDependency'si olarak opsiyonel bırakıldı.
