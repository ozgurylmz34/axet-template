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
- Paket ve transport **kullanıcıdan** gelir; model transport yaratmaz, paket yaratmaz (kesin yasak C). Paket `$TMP`
  değilse `deploy` transport'suz reddeder (`ADR_0005_C`, §3.2a); `prepare` aynı kuralla (yalnız TAM `$TMP` muaf,
  `$tmp` dahil değil) "deploy bunu REDDEDER" **UYARI**sı basar — ihlal saymaz, çıkış kodunu değiştirmez.
- `null`, `~` ve yalnız yorum (`transport: # TODO`) YAML'da **boş** değerdir; script de öyle okur (tırnaklı `'null'` dizedir).
- Hedef URL alias değil kanonik host (aksi hâlde başka sistemin repository'sine gider).
- ⚠ `builder.resources.excludes` şablondur, kural değildir: canlıda `localService/**` (ya da başka dışlanan klasör)
  taşıyan bir uygulamada dışlama dist'i canlı listeden eksik bırakır. Kaynağı SAP'den indirilen uygulamada dışlama
  konmaz — §7.2.
- Validation'daki **"application name must be prefixed with [ZZ1_]"** kaynak sistemde **yumuşak uyarıydı**: `Z…` adlı
  uygulamalar deploy oldu. Başka sistemde davranış DOĞRULANMADI.

## 3. `scripts/deploy_ui.py` — üç alt komut

```bash
S=<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/deploy_ui.py
python $S prepare <app> [<app2> …] [--no-build]      # ağ YOK: yaml + dosya kontrolü + build + dist parmak izi
python $S verify  <app> [<app2> …] [--ignore-cert]   # salt okuma: canlı Component-preload.js ↔ dist
python $S deploy  <app> --user-ok "<kullanıcının sohbetteki onay cümlesi>" \
         --sap-write --scope S1 --reason "<tek satır gerekçe>" --project-dir <proje_kökü> [--ignore-cert]   # SAP YAZMA KAPISI (§3.2a)
```

| Alt komut | Ne yapar | Ne yapmaz |
|---|---|---|
| `prepare` | `ui5-deploy.yaml` `deploy-to-abap` görevi, BSP adı (`Z`, ≤ 15), yer tutucu kalmış mı, URL/client/paket (yalnız boşluk da boş); `$TMP` dışı pakette boş transport **WARN** ("deploy reddeder"); `webapp/` ve `dist/`'te gizli/stray dosya, `.svg`/`.woff` **ERROR**, `.woff2/.ttf/.otf/.eot` **WARN** (exclude desenleri düşülür); `npm run build` (`--no-build` ile atlanır ve `dist` bayat mı bakılır); dist `Component-preload.js` sha256; koşulmamış deploy komutunu basar | Ağa çıkmaz, deploy etmez, transport'un açık/sahibi olduğunu doğrulamaz |
| `verify` | Env kimliğiyle canlı `…/sap/bc/ui5_ui5/sap/<bsp>/Component-preload.js?sap-client=…&cb=<ts>` çeker, modül bazında dist ile karşılaştırır: `OK` · `OK~` (yalnız kaçışlı `\r\n` farkı) · `STALE` · `ÖLÇÜLEMEDİ`. `--tam` ile canlının tüm dosya listesini de kıyaslar (§7.4) | `--tam`'sız statik dosyaları (`webapp/help/**`) kanıtlamaz → §5 |
| `deploy` | `--user-ok` metni yoksa ya da yer tutucuysa **çıkış 3 (REDDEDİLDİ)**; env kimliği yoksa çıkış 3; **SAP yazma kapısı** reddederse çıkış 3 (§3.2a — build dahil hiçbir şey koşmaz); sonra build + `npx --no-install fiori deploy --config ui5-deploy.yaml --yes` (çıktıda parola maskelenir) + "Deployment Successful" araması + **katı** canlı kıyas + canlı tam liste kıyası; `.canli/` varsa build'den önce **drift** (§7.4) | `--user-ok` bir **beyandır**, onayın kanıtı değildir — kodla zorlanan koruma §3.2a'daki yazma kapısıdır |

Çıkış kodları: `0` tamam · `1` ihlal / fark · `2` ölçüm yok (kimlik, ağ, 404) · `3` deploy reddedildi (onay, kimlik ya da SAP yazma kapısı).

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

### 3.2a SAP yazma kapısı (kodda — Z106, 2026-09-24)
`deploy` SAP'ye (BSP) yazar ⇒ onay ve kimlik kontrolünden sonra, **build'den ve ağdan önce** `sap_adt_cli.py` yazmalarıyla
**aynı** kapıdan geçer: `sap-adt-foundation/scripts/sapadt/gate.py::check_write` (araç adı `deploy_ui`). Kapı ayrı bir kopya
değildir; red kodları ve anlamları `sap-adt-foundation` SKILL'deki red tablosundadır (yalnız deploy'a özgü
`write_target_mismatch` ve `gate_unavailable` dahil). Tek fark çıkış kodudur: CLI reddi çıkış 2, deploy reddi çıkış 3.
- `config/sap-write.local` yok → `write_not_optin_global` (anahtarı kullanıcı `install.py --sap-write` ile açar) · `--sap-write`
  yok → `write_flag_missing` · proje kökünde (`--project-dir`, yoksa cwd) `sap-project.json` yok/bozuk → `sap_project_*`.
- `.conn_adt` `ADT_SAP_TIER` DEV değil (QA/PRD, satır yok, çakışık) → `tier_not_writable` · ortam `.conn_adt`'yi eziyor →
  `conn_env_mismatch` · kapsam beyanı (`--scope S0|S1 --reason` ya da `S2 --intake`) · BSP adı Z/Y (`ADR_0005_A`) · bağlantı
  dili ≠ `master_language` → `language_mismatch`.
- Ardından `gate.check_target_system`: `ui5-deploy.yaml` `target.url`/`target.client` ≠ `.conn_adt` `ADT_SAP_URL`/`ADT_SAP_CLIENT`
  (ya da boş) → `write_target_mismatch`. Gerekçe: deploy hedefi `.conn_adt`'den değil `ui5-deploy.yaml`'dan gelir; eşlik
  denetimi olmadan tier kapısı başka bir sistemi doğrulamış olurdu. URL `şema://host:port/yol` biçiminde karşılaştırılır
  (host küçük harf; `:443` yazılıp yazılmaması FARK sayılır).
- Hedef URL'si ayrıştırılamıyorsa (ör. şablondaki `<PORT>` yer tutucusu kalmış, geçersiz port) bu da `write_target_mismatch`
  (fail-closed, çıkış 3, loglanır) — traceback değil.
- Ardından **paket ve transport** (Kesin Yasak C): `app.package` boş, yalnız boşluk, `null`/`~` ya da yer tutucu
  (`<SAP_PAKET>`) → `ADR_0005_C` (paketi kullanıcı verir). `app.package` `$TMP` DEĞİLSE `app.transport` zorunlu; boş,
  satır yok, yalnız boşluk, `null`/`~`, yalnız yorum (`# TODO`) ya da yer tutucu (`<TRANSPORT_NO>` gibi `<`/`>` içeren)
  → `ADR_0005_C`. Her iki red de çıkış 3, loglanır, build yok. Kural
  foundation'ın kanonik `guardrails.require_transport`'udur (CLI yazmalarıyla aynı): istisna yalnız TAM `$TMP`;
  `$tmp`, `$TMP2`, `" $TMP"` istisna DEĞİL (fail-closed). Transport numarasını **kullanıcı** verir ve
  `ui5-deploy.yaml`'daki `app.transport` alanına yazılır (`deploy_ui`'nin transport argümanı yok); model transport
  yaratmaz. Transport'un açık/sahibi olup olmadığı ve biçimi denetlenmez — yalnız varlığı. Paketin SAP'de var olup
  olmadığı da denetlenmez.
- Red → `[REDDEDİLDİ] SAP yazma kapısı (<kod>): <mesaj>`, çıkış 3, stderr'de CLI ile aynı hatırlatma. Kapı yüklenemezse de
  red (`gate_unavailable`, fail-closed). Red dahil her deneme ve sonuç (`ok`, `prepare_failed`, `deploy_failed`,
  `verify_stale`, `verify_unmeasured`) proje `.axet-code/sap-write-log.jsonl`'a yazılır.
  **Tek istisna `gate_unavailable`:** log yazıcısı kapı modülünün parçasıdır; kapı yüklenemediyse log da yazılamaz ⇒ bu red
  yalnız ekrana (stdout, çıkış 3) basılır, write-log'da **iz bırakmaz**. Deploy yine koşmaz (build dahil).
- `--user-ok` kalır; kapı ona **ektir**. `prepare` (ağsız) ve `verify` (salt GET) kapıdan geçmez.
- Red geldiyse kapı ayarını, `.conn_adt`'yi, `ui5-deploy.yaml` hedefini ya da izinleri **model değiştirmez**; reddi ve
  sebebini kullanıcıya bildirir.

### 3.3 Kimlik — ortam değişkeni, CLI argümanı değil
| Yöntem | Sonuç |
|---|---|
| `--username X --password Y` | ❌ 401 — `fiori` argümanları kaçışsız alt sürece geçirir; özel karakterli parola cmd.exe'de bozulur; parola loga düşer |
| `FIORI_TOOLS_USER` / `FIORI_TOOLS_PASSWORD` | ✅ doğrudan `process.env`'den |

- Değişkenleri **geliştirici** kendi kabuğunda set eder; model parolayı okumaz, yazdırmaz, dosyaya yazmaz, komut
  satırına koymaz. Script değer yoksa `set değil` deyip durur; değerleri maskeler ve sonundaki `\r`'yi temizler
  (CRLF'li bir kaynaktan kopyalanan parolanın sonunda `\r` kalınca kimlik doğrulama bozuluyordu).
- `keyring.getPassword is not a function` / `@zowe/secrets-for-zowe-sdk` uyarıları **ölümcül değil**; env kimliği kullanılır.

### 3.4 Elle komut (yalnız geliştirici, kapısız — script çalışmazsa, yine kullanıcı OK'undan sonra)
> ⛔ **Bu yol SAP yazma kapısını (§3.2a) ATLAR** — `sap-write.local` anahtarı, `.conn_adt` tier DEV denetimi,
> `ui5-deploy.yaml` hedefi == `.conn_adt` eşliği ve write-log bu komutlarda **yoktur**.
> - Yalnız **geliştirici kendi terminalinde** koşar. **Model bu komutu önermez ve koşmaz**; `deploy_ui.py` çalışmıyorsa
>   model durur ve hatayı kullanıcıya bildirir.
> - Kapı **reddettiyse bu yol KULLANILMAZ**: önce red sebebi (`<kod>` + mesaj) kullanıcıya bildirilir; reddi aşmak için
>   elle komuta geçmek kapıyı delmektir.

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
- **Kıyas tabanını build kirletmesin (ekip dersi):** `verify` ve bu script salt okurdur, build koşmaz; `prepare` (varsayılan)
  ve `deploy` ise `npm run build` koşar ve `dist/`'i yeniden yazar. "Canlıya giden dist bayat mıydı" sorusunu ölçeceksen
  ölçümü build'den ÖNCE al ve çalışma ağacını önce commit et; aksi hâlde taban silinir (vakada build koşan bir doğrulama
  komutu tabanı yeniden yazdı ve "şu tarihten beri ne değişti" sorusu cevapsız kaldı).

## 6. Önerilen izin kuralları (proje/kurulum yöneticisi için)
Model tarafında sessiz deploy yolu kalmasın diye (ayrıntı skill raporunda):
- deny: `*fiori deploy*` · `*npm run deploy*` · `*npm --prefix * run deploy*` · `*fiori undeploy*`
- deny (paket yöneticisi yolları, 2026-09-24): `npm`/`pnpm` `run`/`run-script` (bayraklı, `-w`/`--prefix`/`.cmd`
  biçimleri; `rum`/`urn` takma adı yalnız ad ile arasında bayrak/tırnak yoksa, tırnaklı ad yalnız `run` ile — `npm rum deploy`, `npm run "deploy"`; `run-script "deploy"` yakalanmaz) · `yarn`/`bun` ile `deploy` ve her `undeploy` script'i · `ui5 build … ui5-deploy.yaml` (özel görev
  `deploy-to-abap` build içinde koşar — belge kanıtı, canlı ölçülmedi). Desen listesi ve bilinen açıklar:
  `config/permissions.json` `_aciklama` + [`docs/izin-kurallari.md`](../../../docs/izin-kurallari.md). `deploy_ui.py`'yi **zincirsiz** çağır: bayraklı
  bir paket yöneticisi komutuyla zincirlenirse (`npm run -s build && … deploy_ui.py deploy`) deny'a düşer.
- ⚠ Sınıf olarak: desenler yalnız listelenen yazımları yakalar; takma ad/bayrak/tırnak BİRLEŞİMLERİ (ör. `npm rum "deploy"`, `npm urn -s deploy`, `npm run -s "deploy"`, `npm run-script 'deploy'`) yakalanmaz — izin kuralı güvenlik sınırı değildir, SAP'ye yazmanın güvenli yolu deploy_ui.py kapısıdır. Ayrıntı: [`docs/izin-kurallari.md`](../../../docs/izin-kurallari.md).
- ask: `*deploy_ui*` (deploy her seferinde kullanıcıya sorulsun). Desen bilerek kısa: aynı komuta bir ask ve bir deny
  uyunca uzun desen kazanır, eşitlikte ask (ölçüldü 2026-09-14, tek seri); eski `*deploy_ui.py*deploy *` zincirli bir
  komutta deny kurallarını ezebilirdi. Bedeli: `prepare`, `verify` ve `--help` de onay ister.
- Not: harness yalnız modelin yazdığı komutu denetler; `deploy_ui.py deploy` içinden çağrılan `npx fiori deploy`
  deny'a takılmaz — bu yüzden ask kuralı `deploy_ui` üzerindedir.
- ⛔ **Etkileşimsiz `axet-code run` modunda `ask` sormadan onaylar** (ölçüldü 2026-09-14, aXet 1.3.0): SAP'ye yazan deploy
  bu modda yaptırılmaz; TUI'de sorması beklenir (DOĞRULANMADI).
- ⚠ **`ask` ikincil katmandır (Z106, 2026-09-24):** TUI'de oturum izni ("Allow for Session") verilince bash `ask` komutları
  sorulmadan geçer (ölçüldü, log `grant_for_session`). Kodla zorlanan koruma §3.2a'daki yazma kapısıdır; `ask` kuralı
  yerinde kalır (değiştirilmedi).

## 7. Kaynak yerelde yoksa — SAP'den indir, eşliği ölç, sonra düzenle (Z144)

Uygulama yalnız SAP'ye deploy edilmiş, kaynağı repoda/diskte yoksa kullanıcıdan kaynak istemeden önce bu yol denenir.
Yöntem bir müşteri projesinde tek freestyle BSP'de (41 dosya) uçtan uca ölçüldü: indir → geri kur → değiştirmeden build
== canlı (41/41) → değişiklik → salt-okur yerel test → kullanıcı OK → deploy → canlı tam liste == dist (41/41).

```bash
F=<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/fetch_ui_source.py
python $F indir <BSP> --out <paket>/ui/<app> --project-dir <proje_kökü> [--ignore-cert]   # salt okuma
cd <paket>/ui/<app> && npm install                                                       # kullanıcı onayıyla (ağ)
python $F eslik <paket>/ui/<app>          # DEĞİŞTİRMEDEN build == canlı mı? Değilse DÜZENLEME YOK
# … düzenle …
python <TEMPLATE>/skills-sap/sap-ui5-fiori/scripts/ui_local_proxy.py <paket>/ui/<app> --ignore-cert   # §7.3
# kullanıcı OK → deploy_ui.py deploy (drift + tam liste kendiliğinden, §7.4)
```

### 7.1 İndirme (`indir`) — ne yapar
- **Yol:** OData `GET /sap/opu/odata/UI5/ABAP_REPOSITORY_SRV/Repositories('<BSP>')?$format=json&CodePage='UTF8'&DownloadFiles='RUNTIME'`
  → `d.ZipArchive` (tek istek). Yedek: ADT `GET /sap/bc/adt/filestore/ui5-bsp/objects/<BSP>/content` (Atom, klasörler
  özyinelemeli, `id`'ler URL-kodlu). İkisi ölçüldü: **bayt bayt aynı** (41/41). ICF `/sap/bc/ui5_ui5/sap/<bsp>/…`
  KULLANILMAZ: dizin listelemez ve HTML'e runtime meta enjekte eder (§5).
- **BSP'de derlenmiş dist durur; özgün kaynak `*-dbg.js`'tir** (`X.js.map` `sources` → `X-dbg.js`). Geri kurma:
  `X-dbg.js` → `X.js`, `X-dbg.controller.js` → `X.controller.js`; `Component-preload.js(.map)`, `*.js.map` ve `-dbg`
  karşılığı olan küçültülmüş `.js` atılır; metin dosyaları **LF**'e çevrilir (SAP CRLF saklar; CRLF bırakılırsa
  preload yalnız kaçışlı satır sonu farkı verir). İkili dosyaya dokunulmaz.
- Yazar: `webapp/` + (yoksa) `package.json` · `ui5.yaml` (`metadata.name` = manifest `sap.app.id`) · `ui5-deploy.yaml`
  (ad/paket/açıklama canlıdan, **transport BOŞ** — kullanıcı verir, `builder.resources.excludes` **YOK**, §7.2) ·
  `.gitignore` · canlı anlık görüntü `.canli/` (git'e girmez; drift ölçümünün tabanı).
- Klasörde `webapp/` varsa **üzerine yazmaz** (exit 1). Kimlik env `FIORI_TOOLS_USER`/`FIORI_TOOLS_PASSWORD` (§3.3).
- Uyarılar: `-dbg` karşılığı olmayan `.js` (küçültülmüş kaynak alındı) · map'in TS kaynağına işaret etmesi (sunucuda
  TS YOK, geri kurulan JS özgün kaynak değildir → kullanıcıya sor) · `manifest.json` yok.

### 7.2 Eşlik kapısı (`eslik`) — atlanamaz
- Kaynak **değiştirilmeden** `npm run build` → `dist/` ile `.canli/dist` **tam dosya listesi** kıyaslanır (preload modül
  modül). Eşit değilse kaynak güvenilir değildir (TS, özel build, farklı ui5-tooling, eksik dosya) → **düzenleme
  yapılmaz**, farklar kullanıcıya gösterilir. Çıkış: 0 eşlik · 1 fark (dosya ya da kaynak haritası sapması) · 2 ölçüm
  yok (anlık görüntü yok, build başarısız, `dist/` yok) — 1 ve 2'de düzenleme kapısı kapalıdır.
- ⚠ **Şablon dışlaması tuzağı:** §2 şablonundaki `builder.resources.excludes: /localService/**`, canlıda `localService/**`
  taşıyan bir uygulamada dist'i canlı listeden **eksik** bırakır (ölçülen BSP'de 4 dosya). İndirilen uygulamanın
  `ui5-deploy.yaml`'ına bu yüzden dışlama konmaz; eşlik kapısı bu farkı `yalnız-2` olarak gösterir. Deploy'un canlıdaki
  fazla dosyayı silip silmediği **DOĞRULANMADI**; deploy sonrası tam liste ölçümü (§7.4) ikisini de yakalar.

### 7.3 Salt-okur yerel test (`ui_local_proxy.py`)
- İndirilen uygulamada fiori tools proxy yapılandırması yoktur. `ui_local_proxy.py` `dist/`'i sunar ve `/sap/*`
  isteklerini hedef sisteme **yalnız okuma** olarak iletir. `$batch` için model **ayrıştır → doğrula → yeniden
  kur**dur: gövde sınırla parçalara bölünüp her parça tek tek doğrulanır (emin olunamayan → 403), kabul edilen batch
  SAP'ye **istemcinin baytlarıyla değil, proxy'nin kurduğu kanonik gövdeyle** gider:
  - GET/HEAD geçer.
  - POST yalnız yol `/sap/opu/odata/…/$batch` ya da `/sap/opu/odata4/…/$batch` ise değerlendirilir (başka ICF yolu,
    ör. `/sap/bc/soap/…/$batch`; `%` kodlu, boş, `..` ya da `..;`/`.;` segmentli yol → 403).
  - `Content-Type` başlığı **tam bir kez** gelmeli (0 ya da çift → 403) ve `multipart/mixed; boundary=<sınır>`
    olmalı: tek parametre, adı tam `boundary=` (`BOUNDARY=`, `boundary = B` → 403), tek tırnaklı değer (`'B'`) → 403;
    sınır RFC 2046 karakterleri, 1-70. JSON batch → 403.
  - Gövde: satır sonu yalnız CRLF (tek `\r` / tek `\n` → 403); BOM, `\t` dışı kontrol baytı ya da `0x7f` → 403.
    `--<sınır>` gövdenin **herhangi bir yerinde** (prolog/epilog dahil, harfe duyarsız, satır ortasında) geçiyorsa o
    satırın tamamı tam sınır ya da tam kapanış olmalı — `x--<B>`, `--<B BÜYÜK HARF>`, sonunda boşluklu sınır → 403.
    Sınırla ≥1 parçaya bölünür; kapanış sınırı (`--<sınır>--`) şart, kapanıştan sonra sınır satırı → 403. Bunun
    dışında prolog/epilog serbest metindir ve istek sayılmaz (UI5 V4'ün `Group ID: …` epilog'u geçer); yeniden
    kurmada SAP'ye hiç taşınmaz.
  - **Her** parça: `Content-Type: application/http` tam bir kez; `Content-Transfer-Encoding` varsa yalnız `binary`;
    başlıklar katlanmamış, ASCII; `X-HTTP-Method*` ve iç `multipart` (changeset) yok; boş satırdan sonraki ilk satır
    tam olarak `GET <hedef> HTTP/1.1` (küçük harf, baştaki boşluk, `HTTP/1.0` → 403). Hedefte boşluk ve UTF-8
    olabilir, kontrol baytı olamaz: uygulama yolu elle birleştirince UI5 hedefi kodlamaz (`GET Items('Ö ş') HTTP/1.1`
    — UI5 1.120.23 gerçek tarayıcıda ölçüldü, V2 ve V4). Hedef katı UTF-8 çözülmeli ve Unicode kontrol / satır
    karakteri içermemeli: NEL (U+0085), C1 (U+0080-009F), U+2028/2029, geçersiz ya da yarım UTF-8 → 403. İç istek başlıkları aynı kurallarla; GET'in gövdesi yok.
  - **Yeniden kurma:** SAP'ye giden gövde = proxy'nin ürettiği yeni sınır (`batch_axet_<rastgele hex>`), prolog/epilog
    yok, kabul edilen her GET parçası **aynı sırayla** (`Content-Type: application/http` + `Content-Transfer-Encoding:
    binary` [+ parça `Content-ID`] + `GET <hedef> HTTP/1.1` + yalnız beyaz liste iç başlıkları: Accept,
    Accept-Language, DataServiceVersion, MaxDataServiceVersion, OData-Version, OData-MaxVersion, sap-cancel-on-close,
    sap-contextid-accept, X-Requested-With, Content-ID). Üst `Content-Type` = `multipart/mixed; boundary=<yeni>`.
    Listede olmayan iç başlık (X-Method-Override, GET'te Content-Length / Content-Type, If-Match, Prefer …) SAP'ye
    **yapısal olarak ulaşmaz**. Bu, uygulamanın kendi özel başlıklarını da kapsar (V2 `setHeaders` /
    `read({headers})`): `$batch` içinde artık SAP'ye iletilmez, üst düzey istekte zaten iletilmiyordu — arka ucu özel
    başlığa göre dallanan bir uygulamada yerel önizleme canlıdan farklı veri gösterebilir. Kurulan gövde kendi denetiminden geçmezse → 403.
  - Yanıt: SAP'nin yanıtı istemciye olduğu gibi döner; UI5 onu **yanıtın** Content-Type sınırıyla ayrıştırır ve
    parçaları sırayla eşler. Ölçüldü (UI5 1.120.23 gerçek tarayıcı → proxy → sahte SAP, V2 + V4): 4/4 okuma başarılı;
    negatif kontrolde tekil parçalar 404 dönünce yalnız o okumalar hata aldı (eşleme parça parça çalışıyor).
    **Canlı SAP'de de ölçüldü (2026-09-26, DEV, salt-okur):** UI5 V2 `useBatch:true` okuma (değer yardımı listesi
    `$top=3` + `$count`) proxy'nin kanonik gövdesiyle gitti → `$batch` 202, 3 satır + sayım döndü, `REDDEDİLDİ` 0.
    V4 kanonik gövde canlı SAP'de ölçülmedi (DOĞRULANMADI).
  - Diğer her POST (create, function import), PUT/MERGE/PATCH/DELETE → **403**.
  - Reddedilen istek SAP'ye gitmez, konsola `REDDEDİLDİ` yazılır. Negatif test canlıda ölçüldü (3/3 yazma 403, SAP'ye
    istek 0; o ölçüm changeset kuralı dönemindeydi — yazma reddinin yeni kuralla canlı ölçümü yapılmadı, çevrimdışı testle ölçüldü).
- Hedef `ui5-deploy.yaml`'dan, kimlik env'den. Yalnız 127.0.0.1'e bağlanır; `/sap/*` isteğinde Host başlığı
  `localhost:<port>` / `127.0.0.1:<port>` değilse 403 (DNS rebinding). Adres: `http://localhost:<port>/index.html`.
- Kaydet/sil düğmeleri bu modda 403 alır — beklenen davranış; kullanıcıya söylenir.

### 7.4 Deploy — drift ve tam liste (kendiliğinden)
- `deploy_ui.py deploy`, uygulamada `.canli/` varsa **kapıdan sonra, build'den önce** canlıyı yeniden indirir ve anlık
  görüntüyle kıyaslar: canlı değişmişse (başkası deploy etmiş) **DURUR** (exit 1, log `drift`) — deploy o değişikliği
  ezerdi. Ölçülemezse de DURUR (exit 2, `drift_unmeasured`). `.canli/` yoksa ölçmez ve bunu yazar.
- Deploy sonrası preload kıyasına ek olarak canlının **tüm dosya listesi** dist ile kıyaslanır (ui5-deploy.yaml
  `exclude` regex'leriyle dışlananlar hariç): fark → exit 1 (`verify_stale_files`); eşitse `.canli/` yeni canlıyla
  güncellenir. Repo servisi okunamazsa UYARI basılır, hüküm preload'a kalır.
- `.canli/` hepsi-ya-hiç yazılır (`dist.yeni` + `bilgi.json.yeni`, tamamsa takas). Deploy sonrası güncelleme düşerse
  eski görüntünün BAYT BAYT yerinde olduğu ölçülür: yerindeyse exit 0 + UYARI (`ok_snapshot_not_updated`; sonraki
  drift eskiye göre ölçer, DEGISTI der ve sonraki deploy durur); korunamadıysa exit 2 (`ok_snapshot_broken`) — deploy
  doğrulanmıştır, **tekrar edilmez**; `.canli/` silinip `indir` ile yeniden alınır.
- `verify --tam`: aynı tam liste kıyasını salt okuma olarak yapar.
- Drift'i elle ölçmek: `python $F drift <app>`.

### 7.5 `$metadata` alan kontrolü (`metadata`)
- `python $F metadata <SERVIS> --alan <Ad> --tip <EntityType> [--app <app> | --project-dir <proje>]` — `$metadata`'yı
  salt okuma çeker, XML olarak ayrıştırır, alanı **yalnız verilen EntityType'ta** arar (tip-kapsamlı; belge geneli arama
  `SAP__Signature` gibi altyapı tiplerinden yanlış pozitif verir). `--tip` verilmezse alanın bulunduğu her tipi listeler.
- Kapsam: yalnız metadata metni; verinin dolu gelmesi ayrıca ölçülür.

### 7.6 Ölçülmeyenler
- Fiori Elements uygulamaları · TypeScript uygulamalar · `-dbg` üretmeyen/özel build · farklı ui5-tooling sürümüyle
  build edilmiş uygulama (küçültme çıktısı farklıysa eşlik kapısı durdurur) · `s4_public`/`btp_abap` (repo servisi ve
  ADT filestore'un varlığı) · deploy'un canlıdaki fazla dosyayı silme davranışı · FLP katalog/rol/hedef eşlemesi.

---

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynakta deploy script'i kimliği proje bağlantı dosyasından kendisi okuyordu ve git'te değişen uygulamaları otomatik
  seçiyordu; ikisi de alınmadı: kimlik yalnız geliştiricinin set ettiği ortam değişkeninden, uygulama listesi açıkça verilir.
- Kaynaktaki "yalın deploy'u otomatik engelleyen kapı" aXet'te yok; yerine önerilen izin kuralları (§6), `--user-ok` beyanı ve
  (Z106) `deploy_ui.py deploy`'un SAP yazma kapısı (§3.2a).
- Elle komut kaynakta parolayı bağlantı dosyasından `grep | cut | tr -d '\r'` ile okuyordu; alınmadı (kimlik dosyası
  okunmaz). `\r` temizliği script'e taşındı.
- Stray dosya örneği kaynakta belirli bir araç klasörüydü; genel "gizli stray dosya" kuralına çevrildi.
- Sistem adı, kullanıcı adı, müşteri uygulama adları ve port numaraları çıkarıldı.
- 2026-09-25 eşitleme (ekip dersi): §5'e "kıyas tabanını build kirletmesin" eklendi; kaynak ders `--verify-only`'nin build
  koştuğunu ölçmüştü — aXet'te `verify` build koşmaz, aynı risk `prepare`/`deploy` için yazıldı. Dersin 1. ve 2. maddesi
  (preload dışı dosyalar, enjekte meta) §5'te zaten vardı.
