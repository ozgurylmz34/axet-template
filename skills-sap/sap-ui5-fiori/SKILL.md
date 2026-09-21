---
name: sap-ui5-fiori
description: >
  Use for freestyle SAPUI5 / Fiori apps on OData V2 that consume RAP or SEGW services: app skeleton (npm
  workspace, manifest, pinned bootstrap, proxy), save plumbing (sequential update, to_X navigation, JSON
  edit buffer), value help, ALV-parity list screens with sap.ui.table grid, select-options filter screens,
  i18n, UI side of delete flows, local run, BSP deploy after user OK and runtime verification. Triggers:
  "UI5 ekranı", "Fiori uygulaması", "freestyle UI", "liste ekranı", "rapor filtre ekranı", "F4 value help",
  "kaydetmiyor", "Kaydedilemedi", "i18n etiketi", "lokal çalıştır", "logon popup", "UI deploy", "BSP
  deploy", "manifest.json". Do not use for CDS, RAP or BDEF backend (sap-rap), SEGW or DPC (sap-odata-backend),
  classic Dynpro or ALV (sap-classic-abap) or triaging a new request (sap-intake-triage).
---

# Freestyle UI5 / Fiori — iskelet, plumbing, liste ekranı, deploy, doğrulama

> **Profil:** kaynak dersler `s4_private` sistemde, OData V2 (RAP ve SEGW) tüketen freestyle uygulamalarda ölçüldü.
> `ecc`'de SEGW servisine bağlı uygulamada ortak kurallar geçerlidir, RAP'e özgü satırlar (`to_X` kaynağı, BO kilidi)
> değil. `s4_public` / `btp_abap`'ta tüketilen servis türü ve BSP deploy yolu farklı olabilir — **DOĞRULANMADI**:
> `sap-project.json` `sap_profile` bunlardan biriyse DUR, kullanıcıya sor.
> Kesin yasaklar (A/B/C/D) ve liste ekranı ALV paritesi SAP çekirdeğinde (`00-sap.md`) yüklüdür; burada tekrarlanmaz.
> Backend: `%sap-rap` (CDS/BDEF/SRVD, value-help yerleşimi, silme guard'ı) · `%sap-odata-backend` (SEGW/DPC, `$filter`, serileştirme).

## When to use this skill
- Yeni bir freestyle UI5 uygulaması kurulacak ya da mevcut bir ekrana özellik eklenecekken.
- Liste/rapor ekranı, filtre ekranı, value-help, kaydet/sil akışı, i18n metni işi.
- "Kaydetmiyor", "Kaydedilemedi", "F4 yansımıyor", "arama sonuç vermiyor", "ekran açılmıyor", "logon popup'ı geçmiyor",
  "deploy oldu ama canlıda eski" gibi UI belirtileri.
- Uygulamayı lokal çalıştırma, BSP'ye deploy hazırlığı ve deploy sonrası doğrulama.
- **Kullanma:** backend objesi (CDS, BDEF, behavior sınıfı, SRVD/SRVB) → `%sap-rap` · SEGW/DPC → `%sap-odata-backend` ·
  klasik Dynpro/ALV → `%sap-classic-abap` · yeni talebin ilk ele alınışı → `%sap-intake-triage`.

## How to use this skill

### 0. Her UI işinde ortak akış
1. Talep sınıflandı mı → değilse `%sap-intake-triage`. Paket `.rules.md` ve `SESSION_NOTES.md` son kaydı (`%sap-dev`).
2. Tanıdık bir belirtiyse önce `%recall`, sonra `references/known-errors-ui5.md`.
3. **Kullanıcıdan gelir, uydurulmaz:** servis adı, alan listesi ve etiketler (spesifikasyondan), BSP adı, SAP paketi,
   transport, ortak VH mı yerel mi, varyant servisi var mı.
4. Alan/navigation/function import adı **canlı `$metadata`**'dan: kullanıcıdan servisin `$metadata`'sını tarayıcıdan
   kaydetmesini iste → `scripts/check_ui_odata_refs.py`. Kontrol API'si şüphesinde UI5 API referansı. Tahmin yok.
5. Plumbing (save, nav, `setData`, master-detail) `references/freestyle-odata-v2.md` §1–2'den; iş içeriği her ekranda ayrıca yazılır.
6. Kapanış: statik kontroller (§5) → `%code-review` → lokal çalıştır → **kullanıcı testi** → (OK ise) deploy → `verify`
   → `%verify-done` → paket `SESSION_NOTES.md`.

### 1. Yeni uygulama iskeleti
- **Önce oku:** `references/app-skeleton.md` (§13 kontrol listesi) · `references/checklists.md` Faz 1–2.
- **Yap:** `ui/` workspace, minimal uygulama `package.json`, `ui5.yaml` (kanonik host), sabit sürümlü `index.html`,
  manifest, Component, `App.view`, `localService/metadata.xml`, i18n iki dosya.
- **Karara bağla (kod yazmadan):** düzenlenebilir alt grid var mı (→ JSON edit-buffer), liste ekranı var mı (→ grid).
- **Doğrula:** `check_i18n_keys.py`, `check_list_view_grid.py`, `deploy_ui.py prepare <app> --no-build`.

### 2. Kaydet / oluştur / aksiyon (OData V2)
- **Önce oku:** `references/freestyle-odata-v2.md` §0–2, §5–7.
- **Yap:** `blur` + `setTimeout(0)` → `isNew ? tek nested create : başlık MERGE + kalem create(nav yolu)/update/remove`
  → `_runSeq` sıralı → `MessageBox.success` / `_parseError`. Boş tarih `null`, dolu tarih `Date`, Boolean `true/false`.
- **Doğrula:** `check_ui5_freestyle_traps.py` + `check_ui_odata_refs.py`; runtime'da 0 kalem / yalnız update /
  yalnız create / karışık yolların hepsi başarı ya da hata mesajına ulaşıyor.
- "Kaydedilemedi" → önce gerçek hata (F12 Network gövdesi / `_parseError`), sonra tek düzeltme.

### 3. Value-help
- **Önce oku:** `references/freestyle-odata-v2.md` §3 · ortak/yerel VH kararı `%sap-rap` → `references/value-help.md` (kullanıcıya sor).
- **Yap:** onayda kontrol + model birlikte; hedef çağıran input'un binding yolundan; kod + ad; elle girişte doğrulama + save guard.
- **Doğrula:** her F4'ten sonra **kendi** alanı doldu mu; boş listede servis `$metadata`'sında VH set var mı.

### 4. Liste / rapor ekranı ve filtre ekranı
- **Önce oku:** `references/list-grid-alv.md` · görsel kurallar `references/fiori-elements-ux.md` §2.
- **Kullanıcıdan:** kolonlar ve sırası, filtre alanları, projede ortak kişiselleştirme util'i / varyant servisi var mı.
- **Yap:** grid beş parça; kolon göster/gizle + varyant + Excel (§3 sözleşmesi); filtre MultiInput + ValueHelpDialog,
  `caseSensitive` yok, wildcard yardımcısı.
- **Doğrula:** `check_list_view_grid.py`, `check_filter_search_pattern.py`; runtime'da sırala/filtrele/varyant/Excel.

### 5. Statik kontroller (her değişiklikten sonra)
```bash
S=<TEMPLATE>/skills-sap/sap-ui5-fiori/scripts
python $S/check_ui5_freestyle_traps.py <app>
python $S/check_list_view_grid.py <app>
python $S/check_filter_search_pattern.py <app>
python $S/check_i18n_keys.py <app>
python $S/check_ui_odata_refs.py --app <app> --metadata <kaydedilen $metadata> [--metadata-for SERVIS=dosya]
```
Çıkış 2 = ölçüm yok (temiz değil). Her çıktının **KAPSAM** satırı rapora yazılır — "0 bulgu" yalnız o yüzey içindir.

### 6. Silme akışı (UI)
- **Önce oku:** `references/delete-flow-ui.md` · backend guard `%sap-rap` → `references/delete-guard.md`.
- **Duruma bağlı pasiflik** (onaylı kayıtta Düzenle/Sil/aksiyon kapalı): kural backend'de feature control'dür
  (`%sap-rap` → `references/feature-control.md` §6); freestyle UI `$metadata`'daki path özelliğine (`sap:updatable-path` …)
  `enabled`/`editable` bağlar — kendiliğinden uygulanmaz, UI'da gizlemek tek başına kural değildir.
- **Yap:** seçim temizliği tek giriş noktasında (`rowsUpdated` değil); pending guard = `onSave` payload'ı (başlık dahil);
  sıralı `remove`; çok satırlı mesaj; onay dialogu.
- **Doğrula:** §5 minimum runtime testi; **test verisi yaratma**, guard'ı kanıtlanmamış kayıtta silme deneme.

### 7. Lokal çalıştırma
- **Önce oku:** `references/deploy-and-local-run.md` §1.
- **Yap:** `npm run start-noflp` (arka planda, port çıktıdan); kullanıcıya adres ver. Kurulum yalnız `ui/` kökünde ve onayla.
- **Popup:** logda `lrep`/varyant 401 → flexibility kapat + localStorage varyant; yalnız `$metadata` 401 ısrarlı →
  **hesap kilidi**, deneme yapma, kullanıcıya söyle. Kapatırken PID ile.

### 8. Deploy (kullanıcı OK'undan sonra)
- **Önce oku:** `references/deploy-and-local-run.md` §2–6.
- **Kullanıcıdan:** BSP adı, SAP paketi, transport; lokal testten sonra sohbette açık **OK**.
- **Sıra:** `deploy_ui.py prepare <app>` → lokal test kullanıcıya gösterildi → OK → (geliştirici kabuğunda
  `FIORI_TOOLS_USER`/`FIORI_TOOLS_PASSWORD` set) → `deploy_ui.py deploy <app> --user-ok "<onay cümlesi>"` →
  sonuç + `verify` aynı mesajda. Statik yardım sayfaları varsa `verify_ui_static_assets.py`.
- Parola okunmaz, yazdırılmaz, komut satırına konmaz. Yalın `fiori deploy` / `npm run deploy` koşulmaz.

### 9. Runtime doğrulama
- **Önce oku:** `references/runtime-verification.md`.
- **Yap:** `scripts/ui-smoke/run_ui_smoke.py --port <port>` (Playwright proje içi kuruluysa; kurulumu kullanıcı onaylar)
  ya da kullanıcıyla elle konsol + ana akış. Ölçüm model API'siyle ve sayıyla (`firePress`, `getModel().getData()`,
  `getSelectedIndices().length`); DOM satır sayısı ya da `click()` sonucu kanıt değil.

## Referanslar, şablonlar ve script'ler
| Dosya | İçerik |
|---|---|
| `references/app-skeleton.md` | adlandırma (BSP ≤ 15), npm workspace, devDeps, scripts, `ui5.yaml`, kanonik host, `index.html` sürüm sabitleme, manifest şablonu + kuralları (`settings.data` tuzağı, annotation), Component, App.view, localService, CSS/kütüphaneler, iskelet kontrol listesi |
| `references/freestyle-odata-v2.md` | PRE-FLIGHT, save deseni + `_runSeq` + S1–S12, JSON edit-buffer, `to_X`, `setData` şekli, master-detail, value-help C1–C8, T1–T7 tuzakları, OData tipleri, Edm payload tipleri, sayısal input, miktar formatter, sıfır dolgusu, `MessageBox.success`, çok satırlı `_parseError`, function import, canlı `$metadata` çapraz kontrolü, i18n, `$batch` |
| `references/list-grid-alv.md` | grid kararı ve reddedilenler, grid beş parça, kişiselleştirme util sözleşmesi (kolonlar/varyant/Excel), grid seçimi ve dialog, SELECT-OPTIONS filtre ekranı + `_parseSearchTerm`, m.Table istisnası |
| `references/delete-flow-ui.md` | seçim bayatlaması, pending guard = save payload'ı, sıralı `remove` + kapanış tuzağı, mesaj/i18n, minimum runtime testi |
| `references/deploy-and-local-run.md` | lokal çalıştırma, popup iki tuzak (flex ↔ hesap kilidi), PID ile kapatma, `ui5-deploy.yaml`, `deploy_ui.py` akışı ve kullanıcı OK kapısı, env kimlik, elle komut, deploy hataları, statik varlık doğrulaması, önerilen izin kuralları |
| `references/runtime-verification.md` | dört katman, statik kontroller ve KAPSAM okuma, done kriteri, Playwright smoke, `firePress`/model API ölçümü, backend'siz mekanizma teyidi, test verisi kuralı, zararsız konsol gürültüsü |
| `references/fiori-elements-ux.md` | UI yaklaşımı kararı, zorunlu UX kuralları ve yapma listesi, on ilke, mesajlar, durum gösterimi, tema, erişilebilirlik, bilinen çelişkiler (`sap.f`, form yerleşimi, toast), Fiori Elements annotation'ları, tasarım kontrol listesi |
| `references/checklists.md` | oluşturma 6 faz + FE inceleme listesi; her satırda otomatik karşılık (script ya da `yok`) |
| `references/known-errors-ui5.md` | belirti → bölüm indeksi |
| `scripts/check_ui5_freestyle_traps.py` | T1 `_X` nav + T4 `f:fields` içi container = ERROR; T2 `type=Number` + T3 `core:Title` = WARN |
| `scripts/check_list_view_grid.py` | liste/rapor adlı view'da `sap.m.Table` |
| `scripts/check_filter_search_pattern.py` | `caseSensitive:false` BLOCKER; filtre VH'si MultiInput değil WARNING |
| `scripts/check_i18n_keys.py` | kullanılan anahtar iki dosyada mı, yer tutucu kümesi, tek kesme |
| `scripts/check_ui_odata_refs.py` | kaydedilmiş `$metadata`'ya karşı entity set / function import / property (çok servisli), çevrimdışı |
| `scripts/deploy_ui.py` | `prepare` (ağ yok) · `verify` (canlı preload ↔ dist) · `deploy` (`--user-ok` + env kimlik zorunlu) |
| `scripts/verify_ui_static_assets.py` | canlı BSP statik dosyaları ↔ dist ↔ webapp (enjekte meta ayıklanır) |
| `scripts/ui-smoke/` | Playwright smoke: config, genel spec, hesap kilidi güvenli koşucu |
| `tests/run_tests.py` | script'lerin çevrimdışı pozitif/negatif testleri (örnek uygulamalar + sahte yerel sunucu) |

## Rules
- **Tahmin yok:** alan/navigation/function import adı, Edm tipi, kontrol API'si; önce referans ve canlı `$metadata`,
  sonra kod. Belirsizse DUR, sor. "Böyle bir desen yok" demeden paketteki çalışan UI kaynaklarını oku.
- **Plumbing icat edilmez, iş içeriği kopyalanmaz.** Save = sıralı `update(merge)`/nav yoluna `create`; nav = `to_X`;
  `setProperty` + `submitChanges` save'i, paralel OData değişikliği, `createEntry` deep nav, `caseSensitive:false`,
  düzenlenebilir sayısal `type="Number"`, liste ekranında `sap.m.Table` (mobil istisna dışında) kullanılmaz.
- **Done = statik PASS + runtime ölçümü + tam kapsam.** `node --check`, XML geçerliliği ya da script "0 bulgu"su tek
  başına yeterli değil; KAPSAM satırı okunur.
- **Kör hata düzeltme yok:** önce gerçek HTTP hatası; bir çare tutmadıysa tekrarlanmaz, teşhis sorgulanır.
- **Deploy yalnız kullanıcı lokal testten sonra sohbette açıkça OK dediğinde**, `deploy_ui.py` ile. Parola okunmaz,
  yazdırılmaz; `fiori deploy`/`npm run deploy` doğrudan koşulmaz; transport ve paket kullanıcıdan (yasak C).
- SAP'ye yazan `deploy_ui.py deploy` etkileşimsiz `axet-code run` modunda yaptırılmaz: ask kuralları run modunda sormadan
  onaylar (ölçüldü, 1.3.0, eski `*deploy_ui.py*deploy *` deseniyle); `*deploy_ui*` deseninin kendi eşleşmesi ölçülmedi.
  TUI'de sorması beklenir (DOĞRULANMADI); desen kısa olduğu için `prepare`/`verify` da eşleşir (simülasyon).
- Lokal logon popup'ı ısrarlıysa **tekrar deneme yapılmaz** (hesap kilidi). Lokal sunucu PID ile kapatılır.
- `npm install` yalnız `ui/` kökünde ve kullanıcıya söylenerek; global kurulum yapılmaz.
- Test verisi yaratılmaz; SAP'de veri değiştiren deneme (silme, kaydetme) kullanıcı onayıyla ve öncesi/sonrası okunarak.
- i18n değişikliği iki dosyada. Paylaşılan util/yardımcı tek tüketici için değiştirilmez (önce kullanım yerleri).
- Denemelerden sonra çalışan yöntem bulunduysa ya da yeni bir UI tuzağı yaşandıysa `%remember`.
