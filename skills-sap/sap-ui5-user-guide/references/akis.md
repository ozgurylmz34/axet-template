# Akış — dokuz adım, komutlarıyla

> Kısaltmalar: `S=<TEMPLATE>/skills-sap/sap-ui5-user-guide/scripts` · `D=<TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts` ·
> `APP=<paket>/ui/<app>` (freestyle V2 uygulaması; içinde `package.json`, `webapp/`, `ui5-mock.yaml`) ·
> `UI=<paket>/ui` (npm workspace kökü; `node_modules` burada — `%sap-ui5-fiori` → `references/app-skeleton.md` §2) ·
> `PW=` playwright-cli: merkezi kurulum `node "<TEMPLATE>/.araclar/playwright-cli/node_modules/@playwright/cli/playwright-cli.js"`
> (`C:/…` biçiminde; yolu `kd_ortam.py check` yazar; projede yerel kurulum varsa o önce gelir).
> Hedef uygulama `%sap-ui5-fiori` ile kurulmuş freestyle SAPUI5 + OData V2 uygulamasıdır; Fiori elements kapsam dışıdır.
> Her adımın **çıkış ölçütü** tutmadan sonrakine geçilmez. Takılınca önce `tuzaklar.md`.

## Ara ürünlerin yeri
| Ürün | Yer | Git'e girer mi |
|---|---|---|
| Mock verisi | `mockdataPath` klasörü (iskelette `webapp/localService/mainService/data/`) | evet (kurgusal veri) |
| Playwright CLI yapılandırması | global `~/.playwright/cli.config.json` (`tarayici_hazirla.py` yazar); istisna: `$APP/.playwright/cli.config.json` (`kd_ortam.py config` yazar) | global: hayır (kullanıcı klasörü) · proje dosyası: ekip kararı; kişisel yol içermez |
| Keşif snapshot'ları | geçici klasör (ör. `$APP/.kd-kesif/`, repo dışı ya da gitignore'lu) | hayır |
| Çekim senaryosu | `$APP/docs/ekranlar.json` | **evet** |
| Ham ekran görüntüleri | `ekranlar.json` → `out_dir` (ör. `docs/screenshots-ham/`) | hayır (kırpılmış kopya girer) |
| KD kaynağı + eşleme | `$APP/docs/KD-<MODÜL>-<NNN>_<Ad>_v<sürüm>.md` + `docs/kd-eslesme.json` | evet |
| HTML + PDF + kırpılmış görseller | `$APP/docs/` + `docs/screenshots/` | evet |
| Uygulama içi yardım | `$APP/webapp/help/kullanici-kilavuzu.html` + `webapp/help/screenshots/` | evet (canlıda görünmesi yeniden deploy ister) |

Dosya adı kuralı `%sap-fs-ts-docs` → `references/traceability.md` §1'dedir.

## 1. Ön kontrol
```
python $S/kd_ortam.py check --proje $APP
```
- `check` bağımlılık tablosu basar: node · Chrome · yerel playwright-cli · playwright-core yolu · Python `markdown` ·
  uygulamada `@sap-ux/ui5-middleware-fe-mockserver` geliştirme bağımlılığı + `start-mock` script'i.
  **Çıkış 0** = tam · **çıkış 2** = eksik var, eksik satırda kurulum komutu yazılıdır. Komutu kullanıcıya göster,
  onay gelirse proje klasöründe koş, sonra `check`'i tekrarla. Script kendisi hiçbir şey kurmaz.
- playwright-cli **merkezi** kurulumdur (`<TEMPLATE>/.araclar/playwright-cli`) ve tarayıcı ayarı **global**
  `~/.playwright/cli.config.json`'dadır (kanal chrome/msedge + `--no-sandbox`). İkisini `install.py` ve `%guncelle`
  `<TEMPLATE>/scripts/tarayici_hazirla.py` ile kendisi hazırlar; proje başına kurulum ve `config` adımı YOKTUR. `check` iki
  `BİLGİ` satırında global dosyanın durumunu yazar. Eksikse önce `python <TEMPLATE>/scripts/tarayici_hazirla.py`
  (idempotent, çıkış daima 0; ilk satırı durumu söyler).
- **Proje-düzeyi istisna:** `python $S/kd_ortam.py config --proje $APP [--kanal msedge] --no-sandbox` →
  `$APP/.playwright/cli.config.json` (global dosyanın ÜSTÜNE birleşir; orada `args` yazılıysa global `--no-sandbox`'ı
  ezer, bu yüzden `--no-sandbox` o dosyada da olmalı → `tuzaklar.md` T23). Farklı içerikli bir kullanıcı dosyası
  varsa `--zorla` olmadan ezmez — farkı kullanıcıya göster.
- **Çıkış ölçütü:** `check` çıkış 0 · global dosya VAR (ya da proje dosyası yerinde) · KAPSAM satırı okundu (neye
  bakmadığını söyler).
- ⛔ Bu adımda ya da sonrakilerde `install-browser` / `playwright install` yok (`tuzaklar.md` T1).

## 2. Mock ortamı
Ayrıntı `mock-ortam.md`'de. Kısa sıra:
1. `manifest.json` → `sap.app.dataSources.<ad>.uri` ile `ui5-mock.yaml` → `services[].urlPath` **aynı mı**. Değilse düzelt.
2. `metadataPath`'teki `metadata.xml` güncel servisin mi (entity set adları uygulamanın kullandıklarıyla aynı mı).
3. Kurgusal veri:
   ```
   python $S/mock_veri.py --metadata <metadata.xml> --cikti <mockdataPath> [--adet 8] [--tohum 1]
   ```
   Her EntitySet için `<EntitySet>.json`; değer yardımı varlıkları dahil; aynı tohum aynı veriyi verir; var olan
   dosyayı `--zorla` olmadan ezmez (elle düzeltilmiş veri korunur).
4. Mock'u **arka planda** başlat: `npm run start-mock` (uygulama klasöründe; bin workspace kökünden çözülür).
   Portu **logdan** oku; varsayma. İskeletteki script `fiori run ... --open ...` biçimindedir; `--open` kullanıcının
   varsayılan tarayıcısında pencere açması beklenir (bu turda ölçülmedi) — çekim buna bağlı değildir, script kullanıcı onayı olmadan değiştirilmez.
   ⛔ **Her yerel sunucu yalnız 127.0.0.1'e bağlanır.** Bind adresi verilmeyen sunucu tüm arabirimlere açılır ve
   Windows Güvenlik Duvarı izin penceresi çıkarır; yönetici olmayan kullanıcı izin veremez, iş orada durur
   (ölçüldü: `python -m http.server <port>` bind'siz). Statik dosya sunarken `python -m http.server <port> --bind 127.0.0.1`.
   `ui5 serve`: UI5 CLI dokümanına göre varsayılan yalnız localhost bağlantısını kabul eder;
   `--accept-remote-connections` **verilmez**. `fiori run` (`@sap/ux-ui5-tooling` 1.32.0, `--port` ile, host bayraksız)
   **127.0.0.1**'e bağlandı; canlı yenileme sunucusu da 127.0.0.1:35729+ (ölçüldü 2026-09-25, `netstat -ano`). Aynı
   anda birden çok mock açılırsa canlı yenileme portu çakışabilir (`EADDRINUSE 35730`) — önce eskisini kapat. Güvenlik
   duvarı ya da şirket güvenlik yazılımı penceresinin çıkmadığı **DOĞRULANMADI** — pencere çıkarsa DUR, kullanıcıya
   bildir (`tuzaklar.md` T5).
5. Duman testi (`mock-ortam.md` §6): `curl -s "http://127.0.0.1:<port>/<urlPath>/<EntitySet>?\$top=1"` → kayıt dönüyor
   mu; bootstrap `sap-ui-core.js` ve `cldr/tr.json` **200** mü (Git Bash'te `/sap/...` argümanı için
   `MSYS_NO_PATHCONV=1`).
- **Çıkış ölçütü:** ana entity set ve her F4 varlığı en az bir kayıt döndürüyor; iki bootstrap dosyası 200; log'da
  metadata/mockdata hatası yok.

## 3. Keşif (playwright-cli)
Ayrıntı ve ölçülmüş komutlar `kesif-playwright-cli.md`'de.
```
$PW -s=kd open "http://127.0.0.1:<port>/<giriş sayfası>?sap-ui-language=tr" --browser chrome
$PW -s=kd snapshot --filename=.kd-kesif/01-liste.yml
$PW -s=kd click <ref>            # ref en SON snapshot'tan
$PW -s=kd --raw eval "location.port"
$PW -s=kd close
```
- Giriş sayfası: `index.html` (FLP önizlemesi `test/flp.html` ek flex çağrıları yapar; backend'siz çalıştırmada
  `index.html` önerilir — `%sap-ui5-fiori` → `references/app-skeleton.md` §4). Script'teki yolu oku, tahmin etme.
- Freestyle ekranda kimliksiz ya da pasif kontrol: `Element.registry` ile bul → `firePress()` /
  `fireValueHelpRequest()` (`%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` §A madde 5).
- Ekran envanteri çıkar: `webapp/view/*.xml` + `webapp/fragment/*.xml` (diyalog, değer yardımı, seçim penceresi);
  liste ekranında grid araçları (sıralama, filtre, kolonlar, varyant, Excel —
  `%sap-ui5-fiori` → `references/list-grid-alv.md`). Her giriş bir KD bölümüne eşlenir (DOC-KD-03).
- Seçici çıkarma: snapshot'taki rol + ad (`button "Oluştur"`) → senaryoda `button:has-text('Oluştur')`; UI5 kimliği
  varsa `[id$='--<kimlik>']`. Kimlik `eval` ile de okunabilir (`kesif-playwright-cli.md` §3).
- **Çıkış ölçütü:** envanter tablosu yazıldı; her ekran için açılış yolu ve seçici belli.

## 4. Senaryo (`ekranlar.json`)
Biçim `capture_kd_screens.js` yapılandırmasıdır (alan listesi `%sap-fs-ts-docs` → `references/pdf-with-screenshots.md`
§A). Bu skill üç doğrulama adımı ekler; her `shot`'tan önce kullanılır:

| Adım | Parametre | Ne zaman FAIL |
|---|---|---|
| `assert_no_busy` | — | sayfada meşgul göstergesi hâlâ açık |
| `assert_text` | `text`, isteğe bağlı `selector` | metin (seçici içinde) yok |
| `assert_in_viewport` | `selector` | öğe görünür alanın dışında ya da kesik |

Örnek iskelet:
```json
{
  "url": "http://127.0.0.1:8080/index.html?sap-ui-language=tr",
  "channel": "chrome",
  "expect_port": 8080,
  "out_dir": "screenshots-ham",
  "viewport": {"width": 1680, "height": 1050},
  "steps": [
    {"do": "wait_ui5"},
    {"do": "click", "selector": "button:has-text('Git')"},
    {"do": "assert_no_busy"},
    {"do": "assert_text", "text": "Örnek Müşteri A.Ş."},
    {"do": "shot", "name": "kd-01-liste.png"},
    {"do": "click", "selector": "button:has-text('Oluştur')"},
    {"do": "assert_in_viewport", "selector": ".sapMDialog"},
    {"do": "shot", "selector": ".sapMDialog", "name": "kd-02-olustur-diyalog.png"}
  ]
}
```
- `assert_text`'e mock verisinden **bilinen bir değer** yaz: liste boş gelirse çekim FAIL olur, boş kare KD'ye girmez.
- `expect_port` + `channel: "chrome"` her senaryoda yazılır (paralel mock ve tarayıcı seçimi tuzakları).
- Aç/kapa alanları iki durumda çekilir (kapalı + açık); her alt ekran ayrı `shot`.
- ⚠ Bu üç adımın `capture_kd_screens.js`'teki uygulaması ayrı bir iş kalemidir; yoksa `--dry-run` "bilinmeyen do=…"
  der. O durumda DUR, adımı silerek geçme — araç sürümünü kullanıcıya bildir.
- **Çıkış ölçütü:** `--dry-run` çıkış 0 ("YAPILANDIRMA OK: N adım, M çekim").

## 5. Çekim
```
node $D/capture_kd_screens.js $APP/docs/ekranlar.json --dry-run
node $D/capture_kd_screens.js $APP/docs/ekranlar.json
```
- `playwright-core` bulunamazsa `PLAYWRIGHT_CORE_PATH=<yol>` ile göster: merkezi kurulumda
  `<TEMPLATE>/.araclar/playwright-cli/node_modules/playwright-core` (yolu `kd_ortam.py check` yazar).
- Mock veri değiştiyse önce mock'u yeniden başlat (veri açılışta okunur).
- **Çıkış ölçütü:** son satır `ÖZET: M OK, 0 FAIL`, çıkış 0, `out_dir`'de M adet PNG.

## 6. Görsel kontrol
Her PNG `view` aracıyla açılır; `gorsel-kontrol.md` listesi kare kare uygulanır ve sonucu bir tabloya yazılır
(kare · bakıldı · bulgu · yapılacak). Bulgu varsa senaryo/veri düzeltilir, adım 5 tekrarlanır.
- **Çıkış ölçütü:** her kare "bakıldı" ve bulgusuz; tablo KD dosyasının yanında (`docs/kd-gorsel-kontrol.md`) durur.

## 7. Yazım
- İskelet `%sap-fs-ts-docs` → `templates/KD-template.md`; bölüm kuralları `%sap-fs-ts-docs` → `references/kd-authoring.md`.
- Adım 3'teki ekran envanterinin her satırı bir bölüm; her bölümde görsel, adım adım akış, alan/buton tablosu.
- Görseller KD'ye `build_kd_pdf.py` eşleme dosyasıyla girer; eşleme dosyasındaki `img` adları `ekranlar.json`'daki
  `shot` adlarıyla aynıdır (araç bu eşliği ölçmez — yazan sağlar).
- Metin **uydurulmaz**: iş kuralı, mesaj metni, alan anlamı uygulamadan (i18n, annotation, FS) gelir; yoksa `[Açık Konu]`.
- **Çıkış ölçütü:** `%sap-fs-ts-docs` → `references/doc-checklist.md` §A yazar öz kontrolü yapıldı.

## 8. Üretim
```
python $D/build_kd_pdf.py $APP/docs/<KD>.md $APP/docs/<KD>.html --map $APP/docs/kd-eslesme.json \
       --trim-from $APP/docs/screenshots-ham --pdf --help-dir $APP/webapp/help
```
- Çıktı: `<KD>.html` + `<KD>.pdf` + `docs/screenshots/` (kırpılmış) + `webapp/help/kullanici-kilavuzu.html`.
- Eşleme dosyası ve manifest biçimi: `%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` §B.
- **Çıkış ölçütü:** çıkış 0; eşleme anahtarı "bulunamadı" uyarısı yok.

## 9. Doğrulama
```
python $D/verify_doc_html.py $APP/docs/<KD>.html --expect-images <M> --pdf $APP/docs/<KD>.pdf
```
- `<M>` = senaryodaki `shot` sayısı (eşleme dosyası bir kareyi iki kez kullanıyorsa ona göre).
- Çıktıda: ölü içindekiler bağlantısı 0 · ham Mermaid 0 · görsel sayısı = M · PDF baytı ve yaklaşık sayfa sayısı
  (görsel başına kabaca 50-100 KB; sayfa sayısı bölüm sayısıyla orantılı). "ÖLÇÜLEMEDİ" satırı temiz demek değildir.
- **Bağımsız okuma:** `agent` aracıyla taze bir inceleyici; brifinge `%sap-fs-ts-docs` → `references/doc-checklist.md`
  §E bloğu + §A metni yapıştırılır, HTML/PDF/PNG yolları verilir. Dönen her BLOCKER dokümanda okunarak doğrulanır.
- **Çıkış ölçütü:** verify bulgusuz + inceleyici hükmü PASS (ya da gerekçeli WARNING) → anahtar kullanıcı onayı.
