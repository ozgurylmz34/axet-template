# Lokal çalıştırma ve BSP deploy — hazırlık, kullanıcı OK kapısı, canlı doğrulama

> **Değişmez akış:** geliştirme → statik kontroller + `%code-review` → **lokal çalıştır** → kullanıcıya "yerelde hazır,
> test edebilirsin" de → **BEKLE** → kullanıcı sohbette açıkça "OK / deploy et" derse deploy.
> Model **hazırlar ve doğrular**; kullanıcı OK'u olmadan deploy komutu koşulmaz, "zaten hazırdı" gerekçesi yoktur.
> Deploy SAP repository'sine ve transport'a yazar (geri alınması ayrı iştir).

---

## 1. Lokal çalıştırma

```bash
cd <paket>/ui/<app>
npm run start-noflp          # index.html açar (flp.html değil)
```
- Kurulum yalnız `ui/` kökünde (`app-skeleton.md` §2). `npm install` ağdan indirir → kullanıcıya söyle, onayla koş.
- Sunucu arka planda başlatılır; **port** (varsayılan 8080; çakışırsa fiori tools başka port seçer) çıktıdan okunur ve
  kullanıcıya adres olarak verilir.
- Canlı backend'e **proxy** üzerinden bağlanır: tarayıcı kullanıcıdan SAP kullanıcı/parolasını ister (basic auth
  popup'ı). `FIORI_TOOLS_USER`/`FIORI_TOOLS_PASSWORD` ortam değişkenleri **yalnız deploy** içindir; çalıştırma
  proxy'sinde kullanılmaz.

### 1.1 Kullanıcı/parola popup'ı — iki ayrı tuzak (karıştırma)

| Durum | Sunucu logu | Sebep | Yapılacak |
|---|---|---|---|
| **(a)** Popup döngüsü, doğru parola da geçmiyor | `/sap/bc/lrep/flex/settings`, `/flex/data` 401 **ve/veya** varyant servisi `$metadata` 401 | UI5 flexibility (LREP) çağrısı + kişiselleştirme yardımcısının varyant servis modeli canlı backend'den 401 alıyor. `manifest flexEnabled:false` bunu tek başına durdurmaz | `index.html` bootstrap'a `data-sap-ui-flexibility-services="[]"`; util'de `LOCAL_VARIANTS_ONLY = true`; `start-noflp` (ya da `index.html` açan `start-mock`); tarayıcıda Ctrl+Shift+R. Doğrulama: logda `lrep|VARIANT|401` sayısı 0 |
| **(b)** Teknik tuzaklar kapalı, popup **ısrarla** geri geliyor | Yalnız uygulamanın kendi `$metadata`'sı 401 tekrar ediyor, `lrep` yok | **SAP kullanıcısı büyük olasılıkla kilitli** — popup denemelerinin kendisi başarısız logon sayacını doldurur | **Başka deneme YAPMA** (kilidi uzatır). Kullanıcıya söyle: kilidi SU01'de kontrol ettirsin / Basis açsın; parola süresi dolduysa sıfırlansın |

- ⚠ Başka bir kanalın (ADT bağlantısı) 200 dönmesi tarayıcı logon'unun açık olduğunu **kanıtlamaz**: ADT önbellekli
  oturum/SSO cookie kullanıyor olabilir, tarayıcı basic auth ise kilitli sayaca takılır. Kaynakta tam bu yaşandı; kilit
  SU01'de açılınca popup kalktı.
- (b) sınıfı bilinmediği için kaynak ekipte ~1 saat kaybedildi. Per-app bir `RUN.md` (başlatma komutu + bu karar
  ağacı) tutmak önerilir.
- Kimlik doğru ama sonsuz 401 ve yukarıdakilerden hiçbiri değil → `ui5*.yaml` host'u kanonik mi (`app-skeleton.md` §6).

### 1.2 Backend'siz istemci davranışı denemesi
Proxy auth'u engelliyken istemci davranışı (sütun genişliği, yatay scroll, formatter, guard) ölçülecekse backend
beklenmez: JSON modeline sahte satır verilir, gerçek render yolu çalışır, sayıyla ölçülür (`runtime-verification.md`
§4.4). Bu mekanizma teyididir; gerçek OData ile son smoke kullanıcının kimlikli ortamında.

### 1.3 Sunucuyu kapatma — PID ile
`taskkill /F /IM node.exe /T` **kullanılmaz**: o ada sahip **tüm** süreçleri öldürür (kullanıcının kendi dev
sunucusu, başka bir işin build'i). Doğru biçim:
```bash
netstat -ano | findstr :<port>        # → PID
taskkill /F /PID <pid>
```
Git Bash'te arka planda başlatılan sürecin PID'i `$!` ile saklanıp aynı PID kapatılır. Alt ajana lokal sunucu açtırılan
brifinge de yazılır.

## 2. `ui5-deploy.yaml`

```yaml
specVersion: "4.0"
metadata:
  name: com.example.<alan>.<uygulama>
type: application
builder:
  resources:
    excludes:
      - /test/**
      - /localService/**
  customTasks:
    - name: deploy-to-abap
      afterTask: generateCachebusterInfo
      configuration:
        ignoreCertErrors: true       # çoğul; tekil 'ignoreCertError' eski
        target:
          url: https://<SAP_HOST>:<PORT>   # kanonik host (ADT bağlantısıyla aynı)
          client: '<CLIENT>'
        app:
          name: ZXX001_ORDER               # Z…, ≤ 15
          description: <Açıklama>
          package: <SAP_PAKET>             # kullanıcı verir
          transport: <TRANSPORT_NO>        # kullanıcı verir
        exclude:
          - /test/
```
- Paket ve transport **kullanıcıdan** gelir; model transport yaratmaz, paket yaratmaz (kesin yasak C).
- Hedef URL alias değil kanonik host (aksi hâlde başka sistemin repository'sine gider).
- Validation'daki **"application name must be prefixed with [ZZ1_]"** kaynak sistemde **yumuşak uyarıydı**: `Z…` adlı
  uygulamalar deploy oldu. Başka sistemde davranış DOĞRULANMADI.

## 3. `scripts/deploy_ui.py` — üç alt komut

```bash
S=<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/deploy_ui.py
python $S prepare <app> [<app2> …] [--no-build]      # ağ YOK: yaml + dosya kontrolü + build + dist parmak izi
python $S verify  <app> [<app2> …] [--ignore-cert]   # salt okuma: canlı Component-preload.js ↔ dist
python $S deploy  <app> --user-ok "<kullanıcının sohbetteki onay cümlesi>" [--ignore-cert]
```

| Alt komut | Ne yapar | Ne yapmaz |
|---|---|---|
| `prepare` | `ui5-deploy.yaml` `deploy-to-abap` görevi, BSP adı (`Z`, ≤ 15), yer tutucu kalmış mı, URL/client/paket; boş transport **WARN**; `webapp/` ve `dist/`'te gizli/stray dosya, `.svg`/`.woff` **ERROR**, `.woff2/.ttf/.otf/.eot` **WARN** (exclude desenleri düşülür); `npm run build` (`--no-build` ile atlanır ve `dist` bayat mı bakılır); dist `Component-preload.js` sha256; koşulmamış deploy komutunu basar | Ağa çıkmaz, deploy etmez, transport'un açık/sahibi olduğunu doğrulamaz |
| `verify` | Env kimliğiyle canlı `…/sap/bc/ui5_ui5/sap/<bsp>/Component-preload.js?sap-client=…&cb=<ts>` çeker, modül bazında dist ile karşılaştırır: `OK` · `OK~` (yalnız kaçışlı `\r\n` farkı) · `STALE` · `ÖLÇÜLEMEDİ` | Statik dosyaları (`webapp/help/**`) kanıtlamaz → §5 |
| `deploy` | `--user-ok` metni yoksa ya da yer tutucuysa **çıkış 3 (REDDEDİLDİ)**; env kimliği yoksa çıkış 3; sonra build + `npx --no-install fiori deploy --config ui5-deploy.yaml --yes` (çıktıda parola maskelenir) + "Deployment Successful" araması + **katı** canlı kıyas | `--user-ok` bir **beyandır**, onayın kanıtı değildir — koruma §3.2'deki akış ve izin kurallarıdır |

Çıkış kodları: `0` tamam · `1` ihlal / fark · `2` ölçüm yok (kimlik, ağ, 404) · `3` deploy reddedildi.

### 3.1 Neden yalın `fiori deploy` değil
`fiori deploy` **build yapmaz**: `dist/`'i arşivleyip gönderir. `dist` eskiyse **"Deployment Successful" der ama
canlıya bayat içerik gider**. Kaynak ekipte üç deploy turu sessizce bayat gitti; kullanıcı değişikliği canlıda
göremeyince fark edildi. Script build'i gömer ve başarı mesajına değil **içeriğe** bakar.

### 3.2 Deploy kapısı (model davranışı)
1. `prepare` temiz (çıkış 0) + statik kontroller + `%code-review` + lokal çalıştırma **kullanıcıya gösterildi**.
2. Kullanıcı sohbette açıkça OK dedi → aynı mesajdaki cümle `--user-ok` değerine yazılır. Belirsiz onay ("bakarız",
   "sonra") OK değildir; iş listesine gömülü genel onay ("hepsini yap") deploy onayı değildir.
3. Backend değişikliği (yeni CDS alanı vb.) gerektiren bir UI özelliğinde yerel test ancak backend sistemde aktifse
   çalışır; backend aktivasyonu da SAP'ye yazmadır → ayrıca açıklanır, ayrıca onay alınır.
4. Deploy sonrası `verify` sonucu **aynı mesajda** raporlanır (OK / STALE).

### 3.3 Kimlik — ortam değişkeni, CLI argümanı değil
| Yöntem | Sonuç |
|---|---|
| `--username X --password Y` | ❌ 401 — `fiori` argümanları kaçışsız alt sürece geçirir; özel karakterli parola cmd.exe'de bozulur; parola loga düşer |
| `FIORI_TOOLS_USER` / `FIORI_TOOLS_PASSWORD` | ✅ doğrudan `process.env`'den |

- Değişkenleri **geliştirici** kendi kabuğunda set eder; model parolayı okumaz, yazdırmaz, dosyaya yazmaz, komut
  satırına koymaz. Script değer yoksa `set değil` deyip durur; değerleri maskeler ve sonundaki `\r`'yi temizler
  (CRLF'li bir kaynaktan kopyalanan parolanın sonunda `\r` kalınca kimlik doğrulama bozuluyordu).
- `keyring.getPassword is not a function` / `@zowe/secrets-for-zowe-sdk` uyarıları **ölümcül değil**; env kimliği kullanılır.

### 3.4 Elle komut (script çalışmazsa — yine kullanıcı OK'undan sonra)
```bash
cd <app_mutlak_yol>
npm run build                                                        # ui5 build → dist/
npx --no-install fiori deploy --config ui5-deploy.yaml --yes         # FIORI_TOOLS_* geliştiricinin kabuğunda set
python <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/deploy_ui.py verify <app_mutlak_yol>
```
- `--yes` "Start deployment (Y/n)?" sorusunu atlar; yoksa etkileşimsiz kabukta takılır.
- **Build ile deploy ayrı adım**: uygulama npm workspace altındayken `npm run deploy` (build && deploy zinciri) Windows'ta
  **native çökme** verdi: `code 3221226505` (0xC0000409 STATUS_STACK_BUFFER_OVERRUN) — build başarılı, deploy çöker.
  Zincirsiz `npx` ile koşunca geçti.
- Mutlak yol (çalışma dizini kayması).
- Önce kuru deneme istenirse `npx --no-install fiori deploy --config ui5-deploy.yaml --testMode true --yes` → "Test run has
  indicated no problems" (bu da kullanıcı OK'u ister: sistemde doğrulama isteği yapar).

## 4. Deploy hataları

| Belirti | Sebep | Çözüm |
|---|---|---|
| `400 "Type of file X is unknown"` (Application Index) | `dist`'e BSP repository'nin tanımadığı dosya karışmış: araç/editör önbelleği gibi **gizli stray dosya**, ya da `.svg`/`.woff` | Stray'i sil + `builder.resources.excludes: /<klasör>/**` + görev `exclude: /<klasör>/`. Logo/ikon inline SVG ya da base64. `prepare` ikisini de listeler. Gerçek hatayı ayrıntılı çıktıda ara: `… --yes --verbose 2>&1 \| grep -i unknown` |
| Lokal çalışıyor, deploy 400 | Lokal sunucu her uzantıyı sunar; BSP yükleme sınıflandırır | aynı |
| "Deployment Successful" ama canlıda eski | `dist` bayat | `deploy_ui.py` akışı; `verify` → `STALE` |
| 401 | CLI argümanıyla kimlik / `\r` / kilitli kullanıcı | §3.3 / §1.1 (b) — tekrar tekrar deneme yapma |
| Canlı değişmedi ama `verify` OK | Tarayıcı/ICF önbelleği | `cb=` parametreli adres; kullanıcıya hard refresh |

## 5. Statik varlıklar — `scripts/verify_ui_static_assets.py`

`Component-preload.js` karşılaştırması `webapp/help/**` gibi **preload'a girmeyen** dosyaları (uygulama içi kullanıcı
kılavuzu, ekran görüntüleri) kanıtlamaz: kılavuz bayat kalsa da `verify` OK der.
```bash
python <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/verify_ui_static_assets.py <app> [--subdir help] [--ignore-cert]
```
- Her dosyayı canlı BSP'den çeker; iki eksen: **canlı ↔ dist** ve **canlı ↔ webapp** (`webapp ≠ dist` = build unutulmuş).
- Çıkış `0` aynı · `1` fark/eksik · `2` ölçüm yok.
- ⛔ **Ham bayt kıyası yanlış pozitif verir:** BSP/ICF sunduğu HTML'in `<head>`'ine üç meta enjekte eder
  (`sap-client`, `sap-ui-fesr`, `sap.whitelistService`). Ham kıyas kaynakta **12/12 uygulamayı bayat** gösterdi, ayıklanınca
  **0/12**. Script bunu ve CRLF'yi ayıklar; `.properties` için build'in `\uXXXX` dönüşümünü hesaba katar.
  📌 Dokunulmamış bir uygulama da kırmızıysa kusur ölçümdedir, deploy'da değil.

## 6. Önerilen izin kuralları (proje/kurulum yöneticisi için)
Model tarafında sessiz deploy yolu kalmasın diye (ayrıntı skill raporunda):
- deny: `*fiori deploy*` · `*npm run deploy*` · `*npm --prefix * run deploy*` · `*fiori undeploy*`
- ask: `*deploy_ui*` (deploy her seferinde kullanıcıya sorulsun). Desen bilerek kısa: aynı komuta bir ask ve bir deny
  uyunca uzun desen kazanır, eşitlikte ask (ölçüldü 2026-09-14, tek seri); eski `*deploy_ui.py*deploy *` zincirli bir
  komutta deny kurallarını ezebilirdi. Bedeli: `prepare`, `verify` ve `--help` de onay ister.
- Not: harness yalnız modelin yazdığı komutu denetler; `deploy_ui.py deploy` içinden çağrılan `npx fiori deploy`
  deny'a takılmaz — bu yüzden ask kuralı `deploy_ui` üzerindedir.
- ⛔ **Etkileşimsiz `axet-code run` modunda `ask` sormadan onaylar** (ölçüldü 2026-09-14, aXet 1.3.0): SAP'ye yazan deploy
  bu modda yaptırılmaz; TUI'de sorması beklenir (DOĞRULANMADI).

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynakta deploy script'i kimliği proje bağlantı dosyasından kendisi okuyordu ve git'te değişen uygulamaları otomatik
  seçiyordu; ikisi de alınmadı: kimlik yalnız geliştiricinin set ettiği ortam değişkeninden, uygulama listesi açıkça verilir.
- Kaynaktaki "yalın deploy'u otomatik engelleyen kapı" aXet'te yok; yerine önerilen izin kuralları (§6) ve `--user-ok` beyanı.
- Elle komut kaynakta parolayı bağlantı dosyasından `grep | cut | tr -d '\r'` ile okuyordu; alınmadı (kimlik dosyası
  okunmaz). `\r` temizliği script'e taşındı.
- Stray dosya örneği kaynakta belirli bir araç klasörüydü; genel "gizli stray dosya" kuralına çevrildi.
- Sistem adı, kullanıcı adı, müşteri uygulama adları ve port numaraları çıkarıldı.
