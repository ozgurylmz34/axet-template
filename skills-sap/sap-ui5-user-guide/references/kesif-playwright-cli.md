# Keşif — playwright-cli ile uygulamayı gezme

> **Neden playwright-cli:** keşif etkileşimlidir (aç → bak → tıkla → tekrar bak); her komut ayrı bir kabuk çağrısıdır
> ve tarayıcı oturumu komutlar arasında açık kalır. Çekimin kendisi ise tekrarlanabilir olsun diye
> `capture_kd_screens.js` + `ekranlar.json` ile yapılır — keşifte bulunan seçiciler senaryoya taşınır.

## 1. Ölçülen ortam
| Parça | Değer | Kaynak |
|---|---|---|
| `@playwright/cli` | 0.1.21 (bağımlılığı `playwright-core` 1.64.0-alpha) | yerel `npm install @playwright/cli`, `--version` |
| Kabuk | Git Bash ve PowerShell'den `npx playwright-cli --version` rc=0 | 2026-09-21 ölçümü |
| Tarayıcı | sistem Chrome, `--browser chrome` (headless); indirme gerekmedi | aynı gün ölçüldü |
| Tarayıcı | sistem Edge, `--browser msedge` | aynı gün ölçüldü |

Başka sürümde alt komut adları değişebilir: şüphede `playwright-cli --help` ve `playwright-cli <komut> --help`.
Paketle gelen kendi rehberi `node_modules/@playwright/cli/skills/playwright-cli/SKILL.md`'dedir — ⚠ oradaki
`npm install -g` önerisi bu template'te **uygulanmaz** (global kurulum yok).

## 2. Ölçülmüş komutlar
`PW` = yerel kopya (`<APP>/node_modules/.bin/playwright-cli`, ya da uygulama klasöründe `npx playwright-cli`).

| Komut | Ne yapar | Ölçüm notu |
|---|---|---|
| `$PW -s=kd open "<url>" --browser chrome` | adlı oturumda tarayıcıyı açar, sayfaya gider | çıktıda sayfa başlığı, HTTP durumu, konsol hata sayısı |
| `$PW -s=kd goto "<url>"` | aynı oturumda başka adrese gider | |
| `$PW -s=kd snapshot --filename=<f>.yml` | erişilebilirlik ağacını dosyaya yazar (rol, ad, `ref`) | çıktı YAML benzeri metin |
| `$PW -s=kd find "<metin>"` | snapshot'ta metni arar, çevresiyle döner | uzun ağaçta ref bulmak için |
| `$PW -s=kd click <ref>` | ref'e tıklar | çıktıda karşılık gelen Playwright kodu (`getByRole(...)`) yazılır — senaryoya seçici olarak taşınabilir |
| `$PW -s=kd --raw eval "<ifade>"` | sayfada JS değerlendirir, yalnız sonucu basar | `location.port`, UI5 kimlikleri |
| `$PW -s=kd screenshot --filename=<f>.png` | görünür alanın görüntüsü | `--full-page`, `--hires` seçenekleri var |
| `$PW -s=kd screenshot "<seçici>" --filename=<f>.png` | tek öğenin görüntüsü | seçici ya da ref |
| `$PW -s=kd close` | oturumu kapatır | `$PW list` → "(no browsers)" ile doğrula |

Oturum ayırma `-s=<ad>` her komutta tekrarlanır; verilmezse varsayılan oturum kullanılır ve başka bir işin
tarayıcısıyla karışabilir. Oturum bitince `close`; asılı kalanlar için `$PW list` → `$PW -s=<ad> close`
(`kill-all` son çaredir, başka oturumları da öldürür).

## 3. UI5 uygulamasında seçici çıkarma
1. `snapshot` → hedefin rolü ve adı (`button "Oluştur"`, `link "Örnek Müşteri A.Ş."`). Senaryoda `button:has-text('Oluştur')`.
2. UI5 kimliği gerekiyorsa (panel, tablo, diyalog):
   ```
   $PW -s=kd --raw eval "sap.ui.core.Element.registry.filter(e => e.isA('sap.m.Dialog') && e.isOpen()).map(e => e.getId())"
   ```
   ⚠ Bu ifadenin UI5 sürümüne göre değişebilen `Element.registry` API'sine dayandığını unutma; yeni sürümde çalışmazsa
   UI5 API referansına bak — DOĞRULANMADI (canlı UI5 uygulamasında bu turda ölçülmedi).
   Kimliğin sonu (`--createDialog`) senaryoda `[id$='--createDialog']` olur; ön ek (bileşen/görünüm kimliği) her
   açılışta değişebilir, tam kimlik yazılmaz.
3. F4 ikonu gibi erişilebilir adı olmayan öğeler snapshot'ta görünmeyebilir → `eval` ile kontrolü bulup
   `fireValueHelpRequest()` (`%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` tuzak tablosu).
4. Her ekrandan sonra `--raw eval "location.port"` → beklenen mock portu mu (paralel mock tuzağı).

## 4. Tuzaklar (bu araca özgü, ölçülmüş)
| Belirti | Sebep | Yapılacak |
|---|---|---|
| `Error: Access to "file:" protocol is blocked` | varsayılan yapılandırma `file:`'ı kapatır | sayfayı yerel HTTP'den aç (`127.0.0.1`); yapılandırmada `file:` erişimini açma |
| `Unknown option: --o` | `screenshot`'ın `-o` seçeneği yok | `--filename <f>` |
| `click e3` "bulunamadı" ya da yanlış öğeye tıklar | ref'ler snapshot'a bağlıdır; aynı düğme bir koşuda `e3`, `open` + `goto` yapılan başka koşuda `f1e3` geldi (ölçüldü; eski ref'e tıklamanın sonucu ayrıca ölçülmedi) | her gezinmeden sonra yeni `snapshot`, ref'i oradan al |
| Tarayıcı verilmeden `open` → aracı kullanan model kendi kararıyla `install-browser chromium`/`firefox` koştu, yaklaşık 1 GB indirdi | tarayıcı yapılandırılmamıştı | `kd_ortam.py config` + her `open`'da `--browser chrome`; `tuzaklar.md` T1 |
| `http://localhost:<port>` beklenmeyen sayfa / 404 döner | `localhost` IPv6 `::1`'e çözüldü; aynı portta tüm arabirimlere bağlı başka bir süreç yanıt verdi (ölçüldü) | adresi `127.0.0.1:<port>` yaz; `netstat -ano` ile portun sahibini gör |
| Çalışma klasöründe `.playwright-cli/` klasörü (snapshot ve konsol günlükleri) | araç ara çıktıları cwd'ye yazar | keşfi repo dışı ya da gitignore'lu bir klasörden koş |
| Her çağrıda ağ trafiği (npm registry) | `@playwright/cli` sürüm denetimi yapar (indirme değil) | `NO_UPDATE_NOTIFIER=1` ile kapanır (ARAÇ şeridi ölçümü; bu dosyanın yazarı ayrıca ölçmedi) |
| `%LOCALAPPDATA%\ms-playwright` altında boş `daemon`/`b` klasörleri | oturum durum klasörleri | tarayıcı indirmesi değildir (0 bayt ölçüldü); silmek gerekmez |

## 5. Keşifte yapılmayanlar
- Veri değiştiren aksiyonu (kaydet, sil) keşif sırasında denemek mock veriyi değiştirir; çekimden önce mock'u
  yeniden başlat ya da senaryoyu bu duruma göre kur.
- Keşif çıktısı (snapshot dosyaları) KD'ye ya da git'e girmez; kalıcı olan yalnız `ekranlar.json`'dur.
