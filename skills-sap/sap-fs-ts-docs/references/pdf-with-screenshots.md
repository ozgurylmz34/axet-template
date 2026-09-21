# Markdown → ekran görüntülü HTML/PDF (KD, FS, TS)

> **Kanıtlı yöntem:** temiz Markdown kaynağı → python-markdown (`toc` + Türkçe slug) → HTML + CSS → Chromium tabanlı tarayıcı
> (`page.pdf`) → PDF. Alternatifler (WeasyPrint, pandoc) Windows'ta kurulum yükü ve Türkçe/tablo sorunları nedeniyle seçilmedi.
> Tanıdık olmayan üretim işinde deneme-yanılma yerine bu reçete uygulanır; çıktı **sayılarak** doğrulanır.

## 0. Bağımlılıklar
| Parça | Gerekli olduğu yer | Kurulum (kullanıcı onayıyla; global kurulum kullanıcı kararıdır) |
|---|---|---|
| Python `markdown` | `build_doc_pdf.py`, `build_kd_pdf.py` | `python -m pip install markdown` |
| Python `Pillow` | yalnız `build_kd_pdf.py` görsel kırpma (`--trim-from`) | `python -m pip install Pillow` |
| Node.js + `playwright-core` | `html_to_pdf.js`, `capture_kd_screens.js` | proje klasöründe `npm install playwright-core` ya da `PLAYWRIGHT_CORE_PATH` ile mevcut kuruluma yönlendir |
| Chrome (sistem kurulumu) | PDF ve ekran çekimi (varsayılan kanal `chrome`; tarayıcı indirilmez) — marp slaytı Edge kuruluysa Edge'i kullanır | sistemde kurulu olmalı; `DOC_TOOLS_BROWSER` / `PDF_BROWSER_CHANNEL` ile değiştirilir (ör. `msedge`) |
| `mmdc` (Mermaid CLI) | yalnız Markdown'da ```` ```mermaid ```` bloğu varsa | `npm i -g @mermaid-js/mermaid-cli` |
| `marp` | yalnız eğitim slaytı | `npm i -g @marp-team/marp-cli` |

Durum: `python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/doc_tools.py check`. Eksik parçada script'ler kurulum komutunu yazıp
**çıkış 2** ile durur; eksik bağımlılığı sessizce atlamaz.

## A. Ekran görüntüsü — gerçek arayüz, temiz örnek veri (UI5)
1. **Mock sunucuyu doğru servise bağla.** `ui5-mock.yaml` içindeki mock sunucu çoğu zaman eski/kopyalandığı servise işaret eder:
   `urlPath` = manifest `dataSources.mainService.uri`; `metadataPath` → servisin güncel `$metadata`'sı
   `webapp/localService/mainService/metadata.xml` olarak (sistemden okuma kullanıcı ya da mevcut araçla); `generateMockData: true`
   (elle hazırlanmayan varlıklar için).
2. **Temiz veri hazırla:** `webapp/localService/mainService/data/<EntitySet>.json` (dizi). Alan adlarını mock'tan teyit et
   (`…/<EntitySet>?$top=1&$format=json`). **F4 değer yardımı varlıklarına da** veri dosyası koy; yoksa açılır pencere boş görünür.
3. Mock'u başlat (`npm run start-mock`); **portu logdan al**. Veri değişince yeniden başlat (mock veriyi açılışta okur).
   `start-mock` yoksa uygulamada mock sunucu geliştirme bağımlılığı yoktur → eklenmesi kullanıcıyla kararlaştırılır.
4. **Türkçe arayüz şart:** URL'ye `?sap-ui-language=tr`.
5. **Çekim:** `capture_kd_screens.js` yapılandırma dosyasıyla (aşağıda). Açılır/kapanır alanları iki durumda çek. Pasif düğmeyi ya da
   diyaloğu `eval` adımıyla açabilirsin (kontrol kaydından düğmeyi bul, `firePress()`); mock'ta olmayan dolu durumları (fiyat, bakiye)
   **model verisi enjeksiyonu** ile doldur. Sayıları tutarlı tut (toplam = kalemlerin toplamı).
6. **Beyaz kenarı kırp:** `build_kd_pdf.py --trim-from <ham klasör>` (Pillow; eşik 242, kenar payı 14 px).

### `capture_kd_screens.js` yapılandırması
```json
{
  "url": "http://localhost:8080/index.html?sap-ui-language=tr",
  "out_dir": "docs/screenshots",
  "viewport": {"width": 1680, "height": 1050},
  "steps": [
    {"do": "wait_ui5"},
    {"do": "shot", "selector": "[id$='listPage']", "name": "kd-01-liste.png"},
    {"do": "eval", "script": "sap.ui.core.Element.registry.filter(e => /--filterPanel$/.test(e.getId()))[0].setExpanded(true)"},
    {"do": "wait", "ms": 1000},
    {"do": "shot", "selector": "[id$='filterPanel']", "name": "kd-02-filtre-acik.png"},
    {"do": "click", "selector": "button:has-text('Yeni')"},
    {"do": "set_model", "view_pattern": "Create", "model": "viewModel", "data_file": "docs/mock-state.json"},
    {"do": "shot", "selector": ".sapMDialog", "name": "kd-05-diyalog.png", "optional": true}
  ]
}
```
Adımlar: `goto` · `wait_ui5` · `wait` (`ms` ya da `selector`) · `click` · `eval` · `set_model` (görünüm adı deseni + model adı +
`data` ya da `data_file`) · `assert_no_busy` (açık meşgul göstergesi yok) · `assert_text` (`text`, isteğe bağlı `selector`) ·
`assert_in_viewport` (`selector` görünür alanda) · `shot` (`selector` ya da tam sayfa; `optional:true` başarısızlığı durdurmaz).
Tutmayan `assert_*` adımı FAIL sayılır. Script sonunda her çekimi
`OK/FAIL` listeler ve **FAIL varsa çıkış 1** verir. Seçiciler `[id$='--<id>']` biçiminde yeniden çizime dayanıklıdır; kimliksiz
paneller önce `eval` ile `data-kd` özniteliğiyle etiketlenir.
**Çok uygulamalı paralel mock tuzağı:** aynı anda iki mock sunucu + paylaşılan tarayıcı → sekme başka porta kayar. Her çekimde
`location.port` beklenenle aynı mı diye `eval` ile kontrol et; tek uygulama, ayrı port kullan.

## B. HTML'i kur
1. **Kaynağı temizle (en kritik adım):**
   - Yer tutucu bir kod bloğunun (```` ``` ````) **içindeyse**, blok içine `![](…)` koyma — Markdown kod bloğunda görseli ayrıştırmaz.
     **Bloğun tamamı** görselle değiştirilir: `build_kd_pdf.py --map eşleme.json`.
   - Ham `<figure>` HTML'i yazma (Markdown içinde HTML ayrıştırması bozar). Markdown görseli `![cap](src)` + hemen altında `*cap*`;
     üretici bunu `<figure><figcaption>` ile sarar.
2. **Üret:**
   ```
   python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/build_doc_pdf.py docs/KD-SD-001_X.md docs/KD-SD-001_X.html "KD-SD-001 — X Kullanıcı Kılavuzu" [--also parça.md] [--pdf]
   ```
   - `toc` eklentisi + `slug_tr` **üreticide sabittir**; kaldırılmaz. `slug_tr`: Türkçe harf → ASCII, her boşluk ayrı tire
     ("Liste / Tablo" → `liste--tablo`), noktalama silinir ("4.2 Kalem" → `42-kalem`).
   - Mermaid blokları PNG'ye çevrilir; PNG adları **doküman kimliğiyle ön eklenir** (aynı klasördeki iki dokümanın diyagramları
     birbirini sessizce ezmesin). `mmdc` yoksa blok metin kalır ve uyarı basılır → DOC-KD-15 ihlali olur; `verify_doc_html.py` yakalar.
   - Görseller HTML'in yanındaki `screenshots/` klasöründen göreli yolla okunur.
3. **KD için eşleme dosyası** (`build_kd_pdf.py --map`):
   ```json
   {
     "fences": {"Liste ekranı": [{"img": "kd-01-liste.png", "caption": "Şekil 1 — Liste ekranı …"}]},
     "after_heading": {"### 5.6 Toplu ekleme": [{"img": "kd-06-toplu.png", "caption": "Şekil 6 — …"}]},
     "strip_circled_numbers": true
   }
   ```
   `fences`: içinde anahtar geçen kod bloğu tamamen görsel(ler)le değişir; bulunamayan anahtar raporlanır. `after_heading`: görsel
   başlığın hemen altına bir kez eklenir (tekrar koşumda eklenmez). Temizlenen Markdown `--write-clean` verilirse kaynağa geri yazılır.
3b. **Markdown yerine manifest** (`build_kd_pdf.py --manifest`, biçim B): KD adımları makine tarafından
   üretildiyse (ör. ekran yakalama akışından) Markdown elle yazılmaz; her adım manifestte bir kayıttır:
   ```json
   {
     "title": "Sipariş Onay — Kullanıcı Kılavuzu",
     "intro": "Bu kılavuz ... anlatır.",
     "heading_level": 2,
     "steps": [
       {"heading": "Liste ekranını açma", "text": "İşlem kodunu girin.",
        "img": "kd-01-liste.png", "caption": "Şekil 1 — Liste ekranı"}
     ]
   }
   ```
   ```
   python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/build_kd_pdf.py docs/KD-SD-001_X.html \
          --manifest docs/kd-manifest.json --write-md docs/KD-SD-001_X.md
   ```
   ⛔ **Araç adım metnini UYDURMAZ.** `text` yazılmamışsa markdown'a `**[AÇIKLAMA YAZILMADI]**` düşer ve
   çıkış **1** olur. Bu bilinçlidir: eksik açıklama sessizce geçilse kılavuz "tamamlandı" görünür ama boş
   olur — ve boş olduğunu yalnız okuyan son kullanıcı fark eder.
   · `steps` boş olamaz, her adımda `heading` zorunlu (yoksa çıkış **2** = şema hatası).
   · `img` isteğe bağlı; verilirse eksik görsel denetimi ve `--trim-from` biçim A ile aynı işler.
   · Biçim A ile B **birlikte verilmez** (`KD.md`/`--map` + `--manifest` → çıkış 2); hangisinin kazandığı
     sessizce belirlenmez.
   · ⚠ Görsel adlarının `capture_kd_screens.js` yapılandırmasındaki `{"do":"shot","name":...}` adlarıyla
     eşliğini araç **ÖLÇMEZ** — iki dosya birbirinden bağımsız yazılır, eşliği yazan sağlar.
4. **PDF:** `--pdf` ya da `node <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/html_to_pdf.js in.html out.pdf` (A4, arka plan açık,
   kenar 14/16/12/12 mm; `file://` Node Playwright'ta çalışır).
5. **Uygulama içi yardım kopyası:** `build_kd_pdf.py … --help-dir <app>/webapp/help` HTML'i `kullanici-kilavuzu.html` adıyla ve
   görselleri `screenshots/` altına kopyalar (canlıda görünmesi yeniden deploy ister).

## C. Doğrula — "bitti" demeden önce
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/verify_doc_html.py docs/KD-SD-001_X.html --expect-images 9 [--pdf docs/KD-SD-001_X.pdf]
```
| Kontrol | Script | Elle |
|---|---|---|
| Ölü içindekiler bağlantısı (`href#` \ (`id` ∪ `a name`)) | ✔ küme kıyası | PDF görüntüleyicide birkaç satıra tıkla |
| Ham Mermaid sızıntısı (`language-mermaid`, çıplak diyagram anahtar sözcüğü) | ✔ HTML | PDF metni |
| `<img>` sayısı = beklenen; yerel görsel dosyası var mı | ✔ | tarayıcıda gerçekten yüklendi mi (`naturalWidth > 0`) |
| PDF oluştu; bağlantı ek açıklaması sayısı | ✔ yaklaşık (sıkıştırılmış nesne akışında 0 okunabilir → ÖLÇÜLEMEDİ yazar) | sayfa sayısı ve boyut makul mü (görsel başına ~50-100 KB) |
| **Alt ekran kapsamı** (view + fragment envanteri ↔ KD bölümü) | ✗ | ✔ eşleme tablosu |
| Görüntüdeki veri temiz mi | ✗ | ✔ her görüntüye bak |

## D. Diyagram, slayt, alan tablosu
- **Mermaid** (akış, sıra, ER, durum): Markdown'a ```` ```mermaid ```` bloğu yaz; üretici PNG'ye çevirir. Tek dosya:
  `doc_tools.py mermaid girdi.mmd cikti.png`. FS/TS'te ASCII mockup yerine sürümlenebilir görsel.
- **Marp** (son kullanıcı eğitim slaytı): frontmatter `marp: true`, `paginate: true`, slayt ayracı `---`;
  `doc_tools.py marp deck.md pdf|pptx|html`.
- **Alan tablosu** (TS §4.5 (a), KD Bölüm 6): `gen_field_table.py <cds> [--ref-csv ref_docs/table_fields.csv] [-o out.md]`.
  Etiket sırası: `@UI.lineItem label` → `@EndUserText.label` → aynı klasördeki projeksiyon kaynağı CDS → CSV. Salt okunurluk
  kardeş `.bdef` `field ( readonly … )`. **Etiketsiz alan işaretlenir, uydurulmaz.** "Oluşturmada zorunlu" CDS'ten kesin çıkmaz → elle gözden geçir.

## Tuzaklar — denenmiş başarısız yollar
| Belirti | Sebep | Çözüm |
|---|---|---|
| İçindekiler satırına tıklayınca hiçbir şey olmuyor (HTML ve PDF) | üretici `toc` eklentisiz → başlıklarda `id` yok | `build_doc_pdf.py` kullan; `verify_doc_html.py` |
| Bağlantıların çoğu çalışıyor, birkaçı değil | elle yazılmış `#hedef` başlıkla uyuşmuyor | href'i bölüm numarası önekinden doğru slug'a çevir; başlığı değiştirme |
| Yalnız `id=` sayan denetim dokümanı "tümü ölü" gösteriyor | eski usul `<a name="x">` çıpaları geçerli hedeftir | küme kıyasında `name` çıpalarını da say |
| HTML'de alt yazı var ama `<img>` yok/az | ham `<figure>` HTML'i | Markdown görseli + alt yazı satırı |
| Görsel metin olarak çıkıyor | `![](…)` kod bloğu içinde | bloğun tamamını değiştir (`--map`) |
| İkinci dokümanın diyagramı birincinin yerine geçti | aynı klasörde aynı PNG adı | kimlik ön eki (varsayılan) ya da `--prefix` |
| Diyagram çıktıda kod olarak görünüyor | `mmdc` yok ya da render hatası | kur/düzelt; `verify_doc_html.py` raw-mermaid |
| Arayüz İngilizce | dil parametresi yok | `?sap-ui-language=tr` |
| Konsolda `UnicodeEncodeError` | Windows konsol kod sayfası | script'ler UTF-8'e ayarlar; çıktıyı dosyaya yaz |
| Mock boş ya da yanlış servis | `ui5-mock.yaml` eski | `urlPath` + `metadata.xml` güncelle |
| F4 penceresi boş | değer yardımı varlığının veri dosyası yok | her F4 varlığına `data/<Varlık>.json` |
| F4 ikonu seçiciyle bulunmuyor | ikon erişilebilir referans vermiyor | `eval` ile kontrolü bul → `fireValueHelpRequest()` |
| Dolu fiyat/bakiye alanları boş | fonksiyon içe aktarımı mock'ta yok | model verisi enjeksiyonu ya da arayüzü sürerek doldur |
| `marp --pdf` takılıyor | açık Chrome profiliyle çakışma | Edge (`doc_tools` marp için Edge'i tercih eder; diğer araçlar Chrome) |
| `mmdc` "Chrome bulunamadı" / JSON kaçış hatası | kendi tarayıcısını indirmemiş; Windows yolu ters bölü | `doc_tools` sistem tarayıcısını ileri eğik çizgiyle verir |
| `gen_field_table` 0 alan | başlık annotation'ındaki `{` gövde sanıldı | gövde araması `define`'dan sonra başlar (script'te düzeltili) |
