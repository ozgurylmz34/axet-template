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
#   cd <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/ui-smoke && npm install
#   + ya `--channel chrome|msedge` (kurulu tarayıcı, indirme yok) ya da `npx playwright install chromium`
# Uygulama lokal çalışıyor olmalı (deploy-and-local-run.md §1); kimlik geliştiricinin kabuğunda:
#   FIORI_TOOLS_USER / FIORI_TOOLS_PASSWORD
python <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/ui-smoke/run_ui_smoke.py --port <port> [--spec ui.smoke.spec.ts] [--no-auth] [--channel chrome|msedge] [--dry-run]
```
- Koşucu Playwright'ı **kurmaz**; yoksa kurulum komutunu yazıp çıkış 2.
- `--channel chrome|msedge`: indirilmiş Chromium yerine kurulu Chrome/Edge. aXet.code'da tarayıcı indirmesi izin kuralıyla
  yasak olduğu için orada bu biçim kullanılır. Ölçüm (2026-09-22, normal kabuk = Claude Code Git Bash, aXet DIŞINDA,
  `@playwright/test` 1.63.0, indirilmiş Chromium YOK, yerel HTTP'de UI5 sayfası): `--channel chrome` ve
  `--channel msedge` çıkış 0; kanalsız kontrol çıkış 1 `Executable doesn't exist`. Bu koşucunun **aXet bash'inde**
  koştuğu **ÖLÇÜLMEDİ**.
- `--no-sandbox` seçeneği bilinçli olarak YOK: Playwright test runner `chromiumSandbox: true` verilmedikçe Chromium'a
  `--no-sandbox`'ı kendisi ekler (playwright-core kaynağı; `DEBUG=pw:browser` başlatma satırında görüldü — normal
  kabukta, chrome ve msedge). §4.6'daki
  playwright-cli çökmesi bu farktan doğuyor olabilir — DOĞRULANMADI.
- `--dry-run`: ön koşullara bakmadan komutu ve tarayıcı ayarını basar (çıkış 0); hiçbir şey koşmaz.
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

### 4.6 aXet.code içinde tarayıcıyı sürmek (playwright-cli)
aXet'in yerleşik tarayıcı aracı yok; `bash` + `@playwright/cli` ile etkileşimli olarak açılır, tıklanır, konsol/ağ okunur,
ekran görüntüsü `view` ile modele gösterilir. **Ölçüm:** 2026-09-22, aXet.code 1.3.0 (Windows), `@playwright/cli`
0.1.21, kurulu Chrome ve Edge. Kanıt yöntemi: tıklama anında üretilen rastgele işaret, **sunucu erişim logunda**
görüldü (modelin beyanına dayanılmadı). Yeni sürümde yeniden ölçülmeden güvenilmez.

**Neler ölçüldü (aXet içinde çalıştı):** arka planda yerel HTTP sunucusu + `job_kill` ile kapatma · `open` (config ile) ·
`snapshot` · `find` · ref ile `click` · `console` · `requests` · `eval` · `close` · `view` ile PNG okuma ·
CDP `attach`/`goto`/`detach` · UI5 `sap.m.Button` için hem `click` hem `firePress()`.

**Adımlar**
1. **Kurulum OTOMATİK — kullanıcı ve ajan komut çalıştırmaz (v0.5.4):** `install.py` (kurulum) ve `%guncelle`'nin son
   adımı `scripts/tarayici_hazirla.py`'yi koşar. O betik: kurulu Chrome'u (yoksa Edge'i) bulur · template klonunda
   **merkezi** `<AXET_HOME>/.araclar/playwright-cli` dizinine `@playwright/cli@0.1.21` kurar (proje başına kurulum YOK;
   dizin gitignore'lu) · **global** `~/.playwright/cli.config.json`'u yazar · duman testi yapar. İlk satırı
   `TARAYICI: HAZIR|ATLANDI|EKSİK — …`. Durumu `doctor.py`'nin `tarayıcı testi:` satırı da gösterir. HAZIR değilse
   betiği kullanıcıya **sormadan bir kez** koşmak serbesttir (idempotent: hazır ortamda hiçbir şeyi değiştirmez); yine
   HAZIR değilse satırı AYNEN kullanıcıya aktar. Tarayıcı **indirilmez**: `install-browser` aXet'in izin kuralıyla
   reddedildi (ölçüldü) ve gerekmez; `npx playwright-cli install` da gerekmez (bir denemede `ffmpeg` indirdi).
2. **Config — global dosya, proje dosyası GEREKMEZ:** betiğin yazdığı `~/.playwright/cli.config.json`:
   ```json
   {"browser":{"browserName":"chromium","launchOptions":{"channel":"chrome","args":["--no-sandbox"]}}}
   ```
   (Chrome yoksa `"channel":"msedge"`). playwright-cli bu dosyayı her çalışma klasöründe okur (kaynak: playwright-core
   `resolveCLIConfigForCLI` → `PWTEST_CLI_GLOBAL_CONFIG ?? os.homedir()` + `.playwright/cli.config.json`).
   **Ölçüldü (2026-09-22, aXet.code 1.3.0, Z60):** proje klasöründe `.playwright/` YOKKEN aXet bash'inde merkezi
   kurulumla `open` → `snapshot` → `close` rc 0, tarayıcı süreç komut satırında `--no-sandbox` VAR; global dosya yokken
   aynı `open` → `Error: Target crashed` (kontrol grubu). Kullanıcının kendi global dosyası farklıysa betik onu
   **EZMEZ** (yalnız kanal uygun ve `--no-sandbox` eksikse onu ekler).
   **Proje-düzeyi istisna:** bir uygulamaya özel ayar gerekiyorsa `%sap-ui5-user-guide`'daki
   `kd_ortam.py config --proje <dizin> [--kanal msedge] --no-sandbox` o klasöre `.playwright/cli.config.json` yazar.
   Proje dosyası global dosyanın ÜSTÜNE birleşir ve `launchOptions` sığ birleştiği için (kaynak: `mergeConfig`) proje
   dosyasına yazılan bir `args` global `--no-sandbox`'ı **ezer** — proje dosyasında `args` varsa `--no-sandbox` orada da
   olmalı (bu birleşim aXet'te ÖLÇÜLMEDİ, kaynaktan).
   **Neden `--no-sandbox`:** aXet bash'inde config'siz `open` → `Error: Session closed` ya da
   `Error: Target crashed`. `--browser chrome` / `--browser msedge` tek başına düzeltmedi. Aynı komut normal kabukta
   açılıyor. `--no-sandbox` içeren config ile Chrome'da ve Edge'de açıldı. playwright-cli Windows'ta her kanalda
   sandbox'ı açık başlatır (kaynak: playwright-core `validateBrowserConfig` Windows'ta koşulsuz `chromiumSandbox = true`;
   kanala bağlı ifade yalnız Linux dalında). Süreç komut satırında `--no-sandbox` yok — normal kabukta (aXet DIŞINDA)
   ölçüldü. `open --browser chrome|msedge` config'teki `args`'ı korur (normal kabukta ölçüldü). aXet bash'i kısıtlı bir Windows job içinde koşuyor; çökmenin sebebinin bu olduğu **DOĞRULANMADI**
   (`--no-sandbox` ile düzelmesiyle yalnız tutarlı). `--no-sandbox` süreç izolasyonunu kapatır: **yalnız yerel/güvenilir
   sayfa**.
3. **Sunucuyu başlat:** aXet `bash` aracını **arka plan** özelliğiyle çağır (`run_in_background: true`; `&` kullanma).
   Araç bir `shell_id` döner; durum/log `job_output`. Adresi `127.0.0.1:<port>` yaz (`localhost` IPv6'ya çözülüp başka
   sürece gidebilir). Ölçülen sunucu `python -m http.server <port> --bind 127.0.0.1 --directory <klasör>` (OpenUI5
   CDN'li sayfa). `npm start` / `fiori run` / `ui5 serve` ile gerçek uygulamanın aXet'te arka planda açılması
   **ÖLÇÜLMEDİ** (komutlar: `deploy-and-local-run.md` §1).
4. **Tarayıcı akışı** (her satır ayrı `bash` çağrısı olabilir; aynı `axet-code run` içinde oturum yaşar):
   ```bash
   export NO_UPDATE_NOTIFIER=1
   PW='node "<AXET_HOME>/.araclar/playwright-cli/node_modules/@playwright/cli/playwright-cli.js" -s=ui'
   #   <AXET_HOME> = template klonu, `C:/…` biçiminde (tam yolu doctor.py / tarayici_hazirla.py basar).
   #   `/c/…` biçimi aXet bash'inde node'a `C:\c\…` olarak gitti → MODULE_NOT_FOUND (ölçüldü). -s=<ad> her komutta.
   $PW open http://127.0.0.1:<port>/index.html
   $PW snapshot                            # rol + ad + ref (e1, e2 …). UI5 async: kontrol yoksa bir kez daha snapshot
   $PW find "Kaydet"                       # uzun ağaçta ref bulmak için
   $PW click e3                            # ref ile. `click -e=e3` YANLIŞ → "Unknown option: --e" (ölçüldü)
   $PW console error                       # konsol; argümansız `console` ölçüldü, seviye argümanı --help'ten
   $PW requests                            # ağ istekleri; başarısızlar durum koduyla ([404] vb.)
   $PW eval "() => { sap.ui.getCore().byId('<id>').firePress(); return 'ok'; }"   # UI5 API (ölçüldü)
   $PW screenshot --filename=ekran.png     # sonra aXet `view ekran.png`
   $PW close
   ```
   `--config` verilmez: global dosya okunur (ölçüldü, Z60). Proje-düzeyi dosya varsa (istisna, adım 2) o da otomatik
   okunur (`--help`: varsayılan yol `.playwright/cli.config.json`).
   Sonunda sunucuyu `job_kill <shell_id>` ile kapat (ölçülen çıktı: `Background shell <id> terminated successfully`).
5. **UI5 tıklaması:** `sap.m.Button`'da `click` press'i tetikledi, `eval` ile `firePress()` da tetikledi (ölçüldü).
   Diğer kontroller (ikon butonu, `sap.ui.table` satırı, SmartField, F4) **ÖLÇÜLMEDİ** → `click` sonuç vermezse §4.2'deki
   `firePress()` / controller çağrısı yedeği kullanılır; durum §4.3 gibi modelden sayıyla okunur.
6. **Görsel kontrol:** `view` bir PNG'yi modele görüntü olarak verir (ölçüldü: tek görüntü, büyük puntolu bir sayı
   doğru okundu). Küçük yazı ya da yoğun UI ekranının okunma kalitesi **ÖLÇÜLMEDİ**. aXet içinde `screenshot` komutunun
   kendisi **ÖLÇÜLMEDİ** (ölçülen PNG normal kabukta playwright-cli ile alınmıştı; komut normal kabukta ölçülüdür,
   `%sap-ui5-user-guide` → `kesif-playwright-cli.md`).

**CDP yolu (kullanıcının açık/oturum açılmış tarayıcısı)** — Chrome aXet'in **dışında**, ayrı bir geçici profille başlatılır
(kullanıcının kendi profili kullanılmaz):
```bash
chrome.exe --headless=new --remote-debugging-port=9222 --user-data-dir=<geçici-profil>    # aXet dışında
npx playwright-cli -s=c attach --cdp=http://127.0.0.1:9222
npx playwright-cli -s=c goto <url>   # … snapshot / click / console / requests …
npx playwright-cli -s=c detach       # Chrome'u kapatmaz
```
- `--headless=new` ile aXet içinden attach → goto → click → requests → detach çalıştı. Dışarıda başlatılan Chrome aXet'in
  job'ında olmadığı için `--no-sandbox` gerekmedi.
- Görünür (headed) pencere arkada/örtülü kalınca sayfa `document.visibilityState = "hidden"` oldu ve `click`
  "visible, enabled and stable" beklerken zaman aşımına düştü — normal kabukta da aynı. Çare: `--headless=new`, pencereyi
  öne almak ya da `eval` ile JS tıklaması.
- aXet'in CDP Chrome'unu **kendisinin başlatması ÖLÇÜLMEDİ** (oturum sonunda süreçlerin öldürülmesi nedeniyle sorunlu
  olması beklenir).

**Sınırlar**
- Tarayıcı oturumu `axet-code run` bitince ölür (ölçüldü: `list` → `(no browsers)`). Aynı `run` içinde ardışık `bash`
  çağrıları arasında yaşar. Etkileşimli TUI oturumundaki ömrü **ÖLÇÜLMEDİ**.
- `file:` URL'leri engelli (`Access to "file:" protocol is blocked`) → daima yerel HTTP sunucusu.
- `.playwright-cli/` klasörüne snapshot ve konsol logları yazılır (sayfa metni içerir) → `.gitignore`'a ekle.
- aXet bash'inde `netstat` engelli (`command is not allowed for security reasons`); port kontrolü için başka yol
  (`curl` vb.) aXet'te **denenmedi**.
- Model "tıkladım, çalıştı" diyebilir: kanıt sunucu logu, `requests` çıktısı, model verisi ya da `view` ile bakılan
  görüntüdür.
- `%sap-ui5-user-guide`'ın ekran çekim betiği ve bu dosyanın `ui-smoke` koşucusu aXet'te **ÖLÇÜLMEDİ**.

## 5. Zararsız konsol gürültüsü — kovalanmaz
Build yapılmadan dev modda:
- `Component-preload.js` 404
- `favicon` 404
- `fallbackLocale 'en' not in supported locales` (locale uyarısı)
- "Defining object type 'Object' is deprecated"

Yalnız gerçek `Error` / kırmızı stack incelenir. Smoke spec'indeki IGNORE listesi bunlardır.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynakta "runtime gate aracı yalnız playwright-cli" kararı vardı; aXet'te gate Node Playwright tabanlı
  `scripts/ui-smoke/` (proje içi kurulum) + elle konsol kontrolüdür. playwright-cli etkileşimli hata ayıklama için
  §4.6'daki ölçülmüş reçeteyle kullanılır (proje içi kurulum; genel skill'i alınmadı).
- Kaynak koşucu kimliği proje bağlantı dosyasından okuyordu; aXet'te geliştiricinin ortam değişkeninden.
- Kaynaktaki özel bir akış spec'i (müşteri sevkiyat ekranı) ve yardımcı self-test'i alınmadı.
- Lider/alt ajan rol ayrımı (UI'ı kim sürer) aXet'te yok; kural "kanıtsız done kabul edilmez" olarak kaldı.
- UI5 linter'ın kaynaktaki araç entegrasyonu alınmadı; proje devDependency'si olarak opsiyonel bırakıldı.
