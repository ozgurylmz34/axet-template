# Tuzaklar — belirti → sebep → çözüm

> Yalnız ekran çekimi ve mock ortamına özgü tuzaklar burada. HTML/PDF kurma tuzakları (içindekiler bağlantısı, görsel
> kod bloğunda, Mermaid, `marp`, konsol kodlaması) tekrarlanmaz: `%sap-fs-ts-docs` → `references/pdf-with-screenshots.md`
> "Tuzaklar" tablosu. "Ölçüldü" = 2026-09-21'de bu makinede gözlendi; diğerleri önceki kanıtlı KD üretim turlarından.

## A. Araç ve ortam
| # | Belirti | Sebep | Çözüm |
|---|---|---|---|
| T1 | Aracı kullanan model `npx playwright-cli install-browser chromium` ve `install-browser firefox` çalıştırdı; yaklaşık **1,06 GB** indirildi (`%LOCALAPPDATA%\ms-playwright`). İndirilen Chromium açılışta çöktü, Firefox hata verdi. **Ölçüldü** | tarayıcı açıkça verilmemişti; etkileşimsiz kipte araç izin sormadı | global `~/.playwright/cli.config.json` kurulu Chrome/Edge'e sabit (`tarayici_hazirla.py` otomatik yazar; proje istisnası `kd_ortam.py config`) + her `open`'da `--browser chrome`; tarayıcı indirmesini reddeden izin kuralı template yapılandırmasındadır. İndirme yapılmışsa silme kararı kullanıcınındır |
| T2 | `Unknown option: --o` (`screenshot -o x.png`). **Ölçüldü** | seçenek yok | `screenshot --filename <f>` |
| T3 | `Error: Access to "file:" protocol is blocked`. **Ölçüldü** | playwright-cli varsayılanı | sayfayı yerel HTTP'den aç; `file:` erişimini yapılandırmada açma |
| T4 | Tarayıcı başka uygulamaya/porta kaydı; `Element.registry` iki uygulamanın kontrollerini döndürüyor | aynı anda iki mock sunucu + paylaşılan tarayıcı; mock portu her yeni sunucuda artar | tek uygulama, tek mock; `-s=<ad>` ile ayrı oturum; senaryoda `expect_port`; keşifte her ekrandan sonra `eval "location.port"` |
| T5 | Windows Güvenlik Duvarı izin penceresi; yönetici olmayan kullanıcı izin veremiyor, sunucu dışarıdan erişilemez kalıyor ya da iş duruyor. **Ölçüldü** (`python -m http.server <port>` bind adresi verilmeden) | sunucu tüm arabirimlere (`0.0.0.0`) bağlandı | her yerel sunucu `127.0.0.1`'e: `python -m http.server <port> --bind 127.0.0.1`; `ui5 serve`'e `--accept-remote-connections` verme. `fiori run` / `start-mock` için host davranışı DOĞRULANMADI — pencere çıkarsa DUR, kullanıcıya bildir |
| T6 | `http://localhost:<port>` 404 ya da başka bir sayfa döndü, oysa sunucu çalışıyor. **Ölçüldü** | `localhost` IPv6 `::1`'e çözüldü; aynı portta tüm arabirimlere bağlı başka bir süreç yanıt verdi (Windows iki bağlanmaya da izin verdi) | adresi `127.0.0.1:<port>` yaz; `netstat -ano` çıktısında portun sahibini (PID) gör |
| T7 | `capture_kd_screens.js` beklenmeyen `playwright-core` sürümüyle koştu | script `PLAYWRIGHT_CORE_PATH` yoksa önce global npm köklerine bakar; makinede eski bir global kurulum bulunabilir (ölçüldü: global 0.1.20, yerel 0.1.21) | `PLAYWRIGHT_CORE_PATH=<ui workspace kökü>/node_modules/playwright-core` açıkça ver |
| T8 | Ref'e tıklama yanlış öğeye gitti / bulunamadı | ref'ler son snapshot'a bağlı | her gezinmeden sonra yeni `snapshot` (`kesif-playwright-cli.md` §4) |
| T9 | Model "ekran görüntüsünü aldım, doğruladım" dedi ama dosya yok ya da içerik farklı | modelin beyanı kanıt değildir; komut listesi ile gerçek çağrılar farklı olabilir (ölçüldü: hatalı `-o` denemesi beyandan düşmüştü) | dosyanın varlığı/boyutu + `view` ile bakış; çekim özetindeki OK/FAIL sayısı |
| T10 | Kurulum komutu PowerShell'de çalışmadı ama `which`/araç "bulundu" dedi | kısıtlı betik politikası npm `.ps1` kabuğunu bloklayabilir | kullanıcının kabuğunda `<araç> --version` koş; bu makinede (RemoteSigned) iki kabuk da çalıştı |
| T23 | aXet.code bash'inde `playwright-cli open` → `Error: Session closed` ya da `Error: Target crashed`; aynı komut başka kabukta açılıyor. `--browser chrome`/`msedge` tek başına düzeltmedi. **Ölçüldü** (2026-09-22, playwright-cli 0.1.21) | playwright-cli Windows'ta her kanalda Chromium sandbox'ını AÇIK başlatır (kaynak: playwright-core `validateBrowserConfig` Windows'ta koşulsuz `chromiumSandbox = true`; kanala bağlı ifade yalnız Linux dalında). Normal kabukta (aXet DIŞINDA) süreç komut satırında `--no-sandbox` yok, ölçüldü. aXet bash'i kısıtlı bir Windows job içinde koşuyor; sandbox'ın orada çöktüğü DOĞRULANMADI, yalnız tutarlı | v0.5.4'ten beri OTOMATİK: `install.py`/`%guncelle` → `<TEMPLATE>/scripts/tarayici_hazirla.py` global `~/.playwright/cli.config.json`'a `--no-sandbox` yazar; proje klasöründe `.playwright/` yokken aXet'te açıldı (ölçüldü 2026-09-22, Z60; global dosya yokken `Target crashed`). Proje-düzeyi istisna: `python $S/kd_ortam.py config --proje $APP --no-sandbox` (Edge: `--kanal msedge --no-sandbox`) → aXet'te açıldı; proje dosyasında `args` varsa global `--no-sandbox`'ı ezer (kaynak: `mergeConfig` sığ birleşim). `open --browser chrome`/`msedge` config'teki `args`'ı korur (normal kabukta ölçüldü; aXet içinde ölçülmedi). `--no-sandbox` yalnız yerel/güvenilir sayfada. `capture_kd_screens.js` doğrudan `playwright-core` ile başlattığı için `--no-sandbox` varsayılan olarak zaten eklenir (kaynak); aXet'te ÖLÇÜLMEDİ |

## B. Mock ve veri
| # | Belirti | Sebep | Çözüm |
|---|---|---|---|
| T11 | Liste boş, hata yok | veri dosyasının adı entity set adıyla birebir değil (büyük/küçük harf, `Set` son eki) ya da `mockdataPath` yanlış | `mock-ortam.md` §3; `curl .../<EntitySet>?$top=1` |
| T12 | Mock boş ya da başka servisin verisi | `ui5-mock.yaml` `urlPath` eski/kopyalanmış servise bakıyor | `urlPath` = manifest `dataSources.<ad>.uri`; `metadata.xml` güncel |
| T13 | `npm run start-mock` yok / sunucu başlamıyor | uygulamada mock middleware geliştirme bağımlılığı yok (yalnız deploy edilmiş uygulamalarda sık) | `kd_ortam.py check` komutu yazar; ekleme kullanıcı onayıyla |
| T14 | F4 penceresi boş açılıyor | ana varlık mock'landı ama F4'ün beslendiği değer yardımı varlığının verisi yok | her VH varlığına `<VH EntitySet>.json` (`mock-ortam.md` §4) |
| T15 | Ekranda "Sample Text", "Item 1" | `generateMockData` genel değer üretti | kareye giren her varlığa kurgusal veri dosyası (`mock_veri.py`) |
| T16 | Veri dosyasını düzelttim, ekran değişmedi | mock veriyi açılışta okur | mock'u yeniden başlat ya da `watch: true` |
| T17 | Fiyat/bakiye gibi dolu alanlar boş, hata diyaloğu | değer fonksiyon içe aktarımından/aksiyondan geliyor, mock'ta yok | model verisi enjeksiyonu (`set_model`) ya da arayüzü sürerek doldur; hata diyaloğunu kapat; sayıları tutarlı tut |
| T18 | Pasif düğme yüzünden diyalog açılamıyor | başlık koşulu vb. düğmeyi pasif tutuyor | `eval` ile kontrolü bul, etkinleştir, `firePress()` (`%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` §A madde 5) |

## C. Görüntü
| # | Belirti | Sebep | Çözüm |
|---|---|---|---|
| T19 | Arayüz İngilizce | dil parametresi yok | `?sap-ui-language=tr` (senaryo `url`'inde) |
| T20 | Kadrajda büyük beyaz alan | tam sayfa çekim | öğe seçicili `shot` + `build_kd_pdf.py --trim-from` |
| T21 | Aç/kapa alanının yalnız bir durumu var; kullanıcı ikisini de ister | tek çekim | iki kare: kapalı + açık |
| T22 | Bir alt ekran (diyalog, seçim penceresi) kılavuzda yok; kullanıcı yakaladı | ekran envanteri çıkarılmadan çekildi | adım 3'te view/fragment envanteri → her giriş bir bölüm (DOC-KD-03) |
