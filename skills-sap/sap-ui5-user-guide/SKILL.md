---
name: sap-ui5-user-guide
description: >
  Use to produce an end-user guide (KD, kullanıcı kılavuzu) with real screenshots for a freestyle
  SAPUI5 app on OData V2 (RAP backend, built with sap-ui5-fiori), from mock data only. Checks local
  tools with Chrome pinned and no browser download, prepares the fe-mockserver with fictitious Turkish
  data incl. value help, explores the app with playwright-cli, writes a versioned capture scenario with assert steps,
  captures, inspects every image, writes the KD from the sap-fs-ts-docs template, builds HTML and PDF
  and verifies counts with an independent read. Triggers: "ekran görüntülü kullanıcı kılavuzu", "KD
  için ekran görüntüsü al", "UI5 uygulamasının kılavuzunu çıkar", "mock veriyle ekran çek",
  "kılavuzu PDF ve HTML yap", "playwright ile kılavuz". Not for FS or TS, KD review only
  (sap-fs-ts-docs), building the app (sap-ui5-fiori), Fiori elements apps or live system screenshots.
---

# UI5 kullanıcı kılavuzu — mock veriyle ekran görüntülü KD (freestyle, OData V2)

> **Kapsam:** ekibin UI standardı olan **freestyle SAPUI5 + OData V2** uygulaması (RAP backend, V2 UI servis
> binding'i; `%sap-ui5-fiori` ile kurulmuş: `ui/` npm workspace, `ui5-mock.yaml`, `webapp/localService/mainService/`).
> SAP bağlantısı **gerekmez**, veri yalnız yerel mock sunucudan gelir. **Kapsam dışı:** Fiori elements (V4) uygulaması
> (akış büyük ölçüde aynı olabilir ama ölçülmedi) ve klasik GUI programı (`%sap-fs-ts-docs` + `%sap-classic-abap`).
> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde yüklüdür; bu akışta SAP'ye hiçbir şey yazılmaz.

> **Özü (kırpılırsa bu kalsın):** ① ÖNCE `kd_ortam.py check` + `config` — tarayıcı **Chrome**'a sabit, tarayıcı
> **indirme yok** ② veri YALNIZ kurgusal mock ③ sayfa `file:` değil yerel **HTTP**'den, arayüz `?sap-ui-language=tr`
> ④ çekim senaryosu `ekranlar.json` dosyasındadır (git'e girer), elle tıklama dizisi değildir ⑤ **her kareye `view`
> ile bak** — "çekim OK" görüntünün doğru olduğunu söylemez ⑥ KD yazımı ve HTML/PDF üretimi `%sap-fs-ts-docs`
> boru hattıyla yapılır, yeniden yazılmaz ⑦ bitti demeden sayılarla doğrula + taze bağlamda bağımsız oku.

## When to use this skill
- Geliştirmesi bitmiş bir freestyle UI5 (OData V2) uygulamasına **ekran görüntülü kullanıcı kılavuzu** gerekiyorsa.
- Mevcut bir KD'nin ekran görüntüleri arayüz değiştiği için **yeniden çekilecekse** (senaryo dosyası zaten varsa adım 5'ten).
- Kılavuzun uygulama içi yardım kopyası (`webapp/help/`) güncellenecekse.
- **Kullanma:** FS/TS yazımı ya da yalnız KD incelemesi → `%sap-fs-ts-docs` · uygulamayı kurma/değiştirme, lokal
  çalıştırma sorunu, deploy → `%sap-ui5-fiori` · klasik Dynpro/ALV ekranı → `%sap-fs-ts-docs` + `%sap-classic-abap` ·
  canlı sistemden (gerçek veriyle) ekran görüntüsü → bu skill kapsamında **yapılmaz**.

## How to use this skill
Dokuz adım sırayla yürür; bir adımın çıkış ölçütü tutmadan sonrakine geçilmez. Komutların tam biçimi ve beklenen
çıktılar `references/akis.md`'dedir. Yollar: `S=<TEMPLATE>/skills-sap/sap-ui5-user-guide/scripts`,
`D=<TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts`, `APP=<paket>/ui/<app>` (içinde `webapp/`, `package.json`,
`ui5-mock.yaml`; npm bağımlılıkları workspace kökü `<paket>/ui/`'dadır).

1. **Ön kontrol.** `python $S/kd_ortam.py check --proje $APP` → eksik varsa yazdığı kurulum komutunu kullanıcıya göster,
   **onay almadan kurma** (çıkış 2 = eksik var). Sonra `python $S/kd_ortam.py config --proje $APP` → Playwright CLI
   yapılandırması Chrome kanalına sabitlenir. ⛔ `install-browser` / `playwright install` **çalıştırılmaz** (yaklaşık
   1 GB indirir; ölçüldü). Tarayıcı açılmıyorsa DUR ve kullanıcıya sor.
2. **Mock ortamı.** Uygulamanın `ui5-mock.yaml`'ı **doğru servise** bakıyor mu (manifest `dataSources` ↔ `urlPath`),
   `metadata.xml` güncel mi → `python $S/mock_veri.py --metadata <metadata.xml> --cikti <mockdata klasörü>` ile
   kurgusal Türkçe veri (değer yardımı varlıkları dahil) → `npm run start-mock` arka planda, **portu logdan al**.
   Sunucu yalnız `127.0.0.1`'e bağlanır. Ayrıntı: `references/mock-ortam.md`.
3. **Keşif.** `playwright-cli -s=<oturum> open <url> --browser chrome` → `snapshot --filename=…` → ekranın
   erişilebilirlik ağacından seçici ve düğme adlarını çıkar; alt ekranları (diyalog, F4, açılır panel) tek tek aç.
   Freestyle seçici deseni `[id$='--<id>']`; erişilebilir adı olmayan kontrol `Element.registry` + `firePress()` ile.
   Ekran envanterini (`webapp/view` + `webapp/fragment` → KD bölümü) bu adımda yaz. Ayrıntı: `references/kesif-playwright-cli.md`.
4. **Senaryo.** Keşfin sonucunu `docs/ekranlar.json` dosyasına yaz (biçim: `capture_kd_screens.js` yapılandırması +
   `assert_no_busy` / `assert_text` / `assert_in_viewport` adımları). Bu dosya **git'e girer**: bir sonraki çekim aynı
   senaryoyla tekrarlanır.
5. **Çekim.** `node $D/capture_kd_screens.js docs/ekranlar.json --dry-run` → sonra gerçek koşum. Özet satırında
   FAIL 0 olmalı (çıkış 1 = en az bir adım tutmadı; assert adımı tutmayan kare de FAIL'dir).
6. **Görsel kontrol.** Her PNG'yi `view` aracıyla **aç ve bak**; `references/gorsel-kontrol.md` listesini kare kare uygula
   (boş liste, meşgul göstergesi, İngilizce metin, kesik diyalog, anlamsız ya da tutarsız veri, kişisel veri görünümü,
   gereksiz beyaz alan). Bulgu → senaryoyu ya da veriyi düzelt → 5'e dön.
7. **Yazım.** `%sap-fs-ts-docs` → `references/kd-authoring.md` bölüm yapısı + `templates/KD-template.md` iskeleti;
   görsel adları `ekranlar.json`'daki `shot` adlarıyla birebir.
   Yazar öz kontrolü: `%sap-fs-ts-docs` → `references/doc-checklist.md` §A.
8. **Üretim.** `python $D/build_kd_pdf.py <KD.md> <KD.html> --map <eşleme.json> --trim-from <ham klasör> --pdf
   --help-dir $APP/webapp/help` → `.html` + `.pdf` ve uygulama içi yardım kopyası. Ayrıntı (eşleme dosyası, manifest
   biçimi, kırpma): `%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` §B.
9. **Doğrulama.** `python $D/verify_doc_html.py <KD.html> --expect-images <N> --pdf <KD.pdf>` → ölü bağlantı 0, görsel
   sayısı = senaryodaki çekim sayısı, PDF sayfa sayısı makul. Sonra `agent` aracıyla **taze bir inceleyici**: brifinge
   `%sap-fs-ts-docs` → `references/doc-checklist.md` §E bloğu ve §A metni yapıştırılır, HTML/PDF/PNG yolları verilir.
   BLOCKER varken "bitti" denmez.

## Önce oku — referanslar ve script'ler
| Dosya | Ne zaman | İçerik |
|---|---|---|
| `references/akis.md` | her koşumda | dokuz adımın komutları, çıkış ölçütleri, ara ürünlerin yerleri |
| `references/kesif-playwright-cli.md` | adım 3 | ölçülmüş komutlar, oturum ayırma, ref'lerin ömrü, tuzaklar |
| `references/mock-ortam.md` | adım 2 | freestyle V2 uygulamada mock sunucu, doğru servis, veri dosyaları, değer yardımı verisi |
| `references/gorsel-kontrol.md` | adım 6 | kare kontrol listesi, bulgu → yapılacak iş |
| `references/tuzaklar.md` | takılınca | belirti → sebep → çözüm (ölçülmüş) |
| `scripts/kd_ortam.py` | adım 1 | `check` (bağımlılık tablosu, eksikte kurulum komutu, çıkış 2) · `config` (Chrome'a sabit yapılandırma) |
| `scripts/mock_veri.py` | adım 2 | metadata'dan her EntitySet için kurgusal Türkçe `<EntitySet>.json` (tohumlu, var olanı ezmez) |
| `%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` | adım 5, 8, 9 | `capture_kd_screens.js` yapılandırması, HTML/PDF kurma, doğrulama tablosu |
| `%sap-fs-ts-docs` → `references/kd-authoring.md` · `templates/KD-template.md` | adım 7 | KD bölümleri, alt ekran kuralı, içindekiler kuralı |
| `%sap-fs-ts-docs` → `references/doc-checklist.md` | adım 7, 9 | DOC-KD maddeleri, bağımsız inceleme brifingi (§E) |
| `%sap-ui5-fiori` → `references/app-skeleton.md` | adım 1, 2 | workspace düzeni, `start-mock` script'i (§4), `localService/` (§11) |
| `%sap-ui5-fiori` → `references/freestyle-odata-v2.md` · `references/list-grid-alv.md` | adım 3, 7 | ekranların nasıl kurulduğu (save, value-help, grid araçları) — kılavuzda anlatılan davranışın kaynağı |
| `tests/test_skill_structure.py` | skill değişince | frontmatter, açıklama uzunluğu, atıf yapılan dosyaların varlığı |

Her script başta **KAPSAM** satırı basar (neye bakıp neye bakmadığı); "0 bulgu" yalnız o kapsamda anlamlıdır.

## Rules
- **Yalnız mock/kurgusal veri.** Canlı sistem, gerçek müşteri/kişi/tutar ekrana girmez; uydurma veri anlamlı ve kendi
  içinde tutarlı olur (toplam = kalemlerin toplamı, anahtarlar tekil, ilişkili kayıtlar eşleşir).
- ⛔ **Tarayıcı indirme yok:** `install-browser`, `playwright install`, `npx playwright install` çalıştırılmaz; sistem
  Chrome'u kullanılır. Chrome açılmıyorsa başka tarayıcı indirerek "çözme"; DUR, kullanıcıya sor.
- Global kurulum yok (`npm -g`, PATH değişikliği). Eksik araç `kd_ortam.py check`'in yazdığı proje-içi komutla ve
  kullanıcı onayıyla kurulur.
- Sayfa `file:` ile açılmaz (bloklu); yerel HTTP sunucusundan açılır. Adres `127.0.0.1:<port>` biçiminde verilir,
  arayüz dili `?sap-ui-language=tr`.
- ⛔ **Her yerel sunucu 127.0.0.1'e bağlanır** (`python -m http.server <port> --bind 127.0.0.1`; `ui5 serve`'e
  `--accept-remote-connections` verilmez). Bind'siz sunucu güvenlik duvarı izin penceresi açar, yönetici olmayan
  kullanıcı izin veremez (ölçüldü). Pencere çıkarsa DUR, kullanıcıya bildir.
- Senaryo elle tıklama dizisi olarak bırakılmaz; `ekranlar.json`'a yazılır ve git'e girer.
- "Çekim OK" / "PDF üretildi" mesajı kanıt değildir: her kareye bakılır, HTML/PDF sayılarla doğrulanır, bağımsız okuma yapılır.
- Kurulum, mock verisi ya da senaryo sorunu çözülünce yeni tuzak `references/tuzaklar.md`'ye önerilir (kullanıcı onayıyla).
