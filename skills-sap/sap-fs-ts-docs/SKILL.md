---
name: sap-fs-ts-docs
description: >
  Use when writing, converting, reviewing or publishing SAP development documents: functional
  specification (FS), technical specification (TS) and end-user guide (KD, kullanıcı kılavuzu).
  Covers FS from requirements without invented facts, FS to TS with an FS audit, clean-core level
  choice and a full message inventory, KD with clean mock-data screenshots and every sub-screen,
  the document checklist with an independent reviewer, FS-TS-KD traceability and rewrite loss
  check, Markdown to HTML/PDF with screenshots, and the live confirmation tour before a TS goes to
  build. Triggers: "FS yaz", "FS'ten TS çıkar", "teknik spesifikasyon", "kullanıcı kılavuzu
  hazırla", "KD yaz", "dokümanı PDF yap", "spec'i incele", "ekran görüntülü kılavuz". Not for triage
  (sap-intake-triage), building objects (sap-dev) or non-SAP Word/PDF documents (office-docs).
---

# SAP dokümanları — FS, TS, KD

> **Profil:** FS ve KD profilden bağımsızdır. TS'in önerdiği çözüm seviyesi ve obje tipleri `sap_profile`'a göre sınırlıdır
> (`references/ts-authoring.md` profil bölümü).

> **Özü (kırpılırsa bu kalsın):** FS = NE/NEDEN (kullanıcı isteği kanondur, uydurma yok) → TS = NASIL (FS'in her
> maddesine çözüm + FS denetimi, fonksiyonel karar TS'te kapanır) → KD = NASIL KULLANILIR (gerçek ekran + temiz
> örnek veri + her alt ekran). Her doküman **bağımsız bir gözle** kontrol listesine karşı incelenir; TS build'e
> girmeden önce içindeki canlı-sistem iddiaları **ölçülür**.
> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde yüklüdür; dokümanda da geçerlidir (standart objeye/tabloya yazan çözüm yazılmaz).

## When to use this skill
- İsterlerden, toplantı notlarından ya da intake artefaktından **FS** yazılacakken.
- Onaylı FS'ten **TS** çıkarılacakken; mevcut TS gözden geçirilecek, build'e hazır mı sorulacakken.
- Geliştirme bitince **KD** (kullanıcı kılavuzu), ekran görüntüsü ya da PDF üretilecekken.
- Bir FS/TS/KD **incelenecek**, yeniden yazılacak (veri kaybı kontrolü) ya da FS↔TS↔KD tutarlılığı sorulacakken.
- Mevcut bir ABAP/CDS kaynağından **taslak spesifikasyon** (tersine mühendislik) çıkarılacakken.
- **Kullanma:** yeni talebin ilk ele alınışı (`%sap-intake-triage`) · objeleri yaratma/kodlama (`%sap-dev` ve iş türü
  skill'leri) · klasik F1/SE61 yardımını SAP'ye yazma (`%sap-classic-abap` → `references/forms-f1-help.md` §B).

## How to use this skill

### 0. Her dokümanda ortak
1. **Kapsam sınıfı yazılı mı?** Değilse önce `%sap-intake-triage`. Derinlik sınıfa bağlıdır: **S0** FS yok (değişiklik
   notu yeter) · **S1** hafif FS (etkilenen alan/ekran + kabul kriteri + risk) · **S2** tam FS + intake artefaktı
   (`.axet-code/intake/<id>.md`) + EARS kabul kriterleri. Intake artefaktı FS'in girdisidir; kopyalanmaz, bağlanır.
2. **Girdiler:** kullanıcı isteği (kanon) · intake artefaktı · analiz notları · paket `ref_docs/` (kaynak, canlı teslimat
   değil) · varsa eski/çalışan kaynak. Girdide olmayan iş kuralı, süreç, standart SAP obje adı **uydurulmaz**.
2b. **Girdiler çelişirse** (aynı workshop'tan kalan birden çok not, transkript, özet ve eski belge sık sık
   çelişir): çelişkiyi **sessizce çözme**. Öncelik sırası: ① kullanıcı isteği (kanon) ② canlı sistemden
   ölçülen olgu ③ intake artefaktı ④ tarihi belli ve daha yeni olan not ⑤ tarihsiz not. Bu sıra bir
   çelişkiyi kapatıyorsa gövdeye **yalnız sonucu** yaz (hangi kaynağın elendiği gövdeye girmez —
   DOC-FS-05). Sıra çelişkiyi kapatMIYORsa bu bir **açık karardır**: §11-B'ye (FS) ya da §2-A'ya (TS)
   satır aç, kullanıcıya sor, cevap gelmeden o bölümü "kapanmış" sayma. Çelişkiyi ortalama alarak ya da
   ikisini birden yazarak çözme.
3. **Yer ve ad:** paket `docs/` altında `FS-<MODÜL>-<NNN>_<Ad>_v<sürüm>.md` (TS-/KD- aynı no) → `references/traceability.md` §1.
4. **Bağımsız ve tam:** her doküman kendi başına okunur; "X dokümanına göre farklar" biçiminde yazılmaz.
5. Doküman diliyle proje `master_language` aynıdır (Türkçe projede Türkçe; teknik terim İngilizce kalabilir).

### 1. Hangi doküman → ne okunur, ne kullanılır
| İş | Önce oku | Şablon | Script |
|---|---|---|---|
| FS yaz / revize et | `references/fs-authoring.md` | `templates/FS-template.md` | `check_fs_no_analysis_log.py` (gövdede analiz günlüğü izi, İlke 2b) |
| FS'ten TS çıkar / TS gözden geçir | `references/ts-authoring.md` | `templates/TS-template.md` | `gen_field_table.py` (CDS→alan tablosu), `check_fm_signature_doc_sync.py` (FM imzası ↔ doküman, §5.3) |
| KD yaz | `references/kd-authoring.md` | `templates/KD-template.md` | `capture_kd_screens.js`, `build_kd_pdf.py` |
| İnceleme (her tip) | `references/doc-checklist.md` | brifing bloğu aynı dosyada §E | `verify_doc_html.py` (yalnız mekanik kısım) |
| FS↔TS↔KD izlenebilirlik, yeniden yazımda kayıp | `references/traceability.md` | — | `doc_equivalence_check.py` |
| HTML/PDF, ekran görüntüsü, diyagram | `references/pdf-with-screenshots.md` | — | `build_doc_pdf.py`, `html_to_pdf.js`, `doc_tools.py` |
| TS build'e girmeden canlı teyit | `references/live-confirmation-tour.md` | rapor tablosu aynı dosyada | `%sap-adt-foundation` CLI okuma araçları |
| Kaynaktan taslak spesifikasyon | `references/traceability.md` §6 | — | `program_to_spec.py` |

Script çağrısı: `python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/<script> …` (Node olanlar `node …`). Her script
başta **KAPSAM** satırı basar (neye baktığı / bakmadığı); "0 bulgu" yalnız o kapsamda anlamlıdır.

### 2. FS akışı
1. Girdileri oku; şablonun bölüm yapısını ve istenen kapsamı kullanıcıya bir paragrafta geri söyle.
2. Girdi yetersizse **dur**: eksikleri araştırmayla bilgilendirilmiş sorulara çevir, **tek seferde, seçenekli ve önerili**
   `ask_user` ile sor; yanıt gelmeden tam FS üretme. Kullanıcı "taslak olarak ilerle" derse boşluklar `[Varsayım]` etiketiyle.
3. Şablonu bölüm bölüm doldur; kullanıcının yazdığı her istek bir FR/KR'ye izlenebilir (İlke 1). Danışman katkısı
   `[Öneri]` → §11-A; karar verilemeyen nokta seçenek + öneri ile → §11-B (İlke 2). Gövdede süreç/sürüm anlatısı yok (İlke 2b).
4. §4 kontrol listesi + bağımsız inceleme (§5 aşağıda) → kullanıcıyla **madde madde mutabakat** (11-A boş, 11-B kapalı).

### 3. TS akışı
1. **FS onaylı mı?** Değilse TS başlamaz. FS'teki her FR/KR'yi izlenebilirlik matrisine satır olarak al.
2. **FS denetimi (§2-A):** her madde için uygulanabilir / alternatif gerek / fizibil değil / başka yeri bozar / FS hatalı.
   Etki alanı iddiası `%sap-adt-foundation` okumasıyla kanıtlanır (`adt_where_used`, `adt_impact_analysis`).
3. **Genişletme seviyesi:** her madde için en düşük uygun seviye (anahtar kullanıcı → geliştirici/released API →
   yan uygulama → klasik); 4. seviyede istisna gerekçesi zorunlu (`references/ts-authoring.md` §4).
4. **Developer geri-soru simülasyonu** yap; fonksiyonel kararları topla ve kullanıcıya tek seferde sor (eşleştirme,
   dönüşüm, birim, kenar durumlar, kilit). Bunlar "build'de netleşir"e ertelenmez; §11-A yalnız teknik teyittir.
5. TS'i yaz (tek dosya ya da beş parça + birleştirme). Obje adları `%sap-dev` → `references/naming.md`; DTEL/append
   adını kullanıcı verir; **mesaj envanteri tam** ve metinleri kullanıcıdan (≤ 73 karakter).
6. **Canlı teyit turu** (§6) → düzeltme varsa ikinci kapı → kontrol listesi + bağımsız inceleme → teknik onay.

### 4. KD akışı
1. Geliştirme bitmiş ve kullanıcı testinden geçmiş olmalı. Uygulamanın **ekran envanterini** çıkar (UI5: `webapp/view/*.xml` +
   `webapp/fragment/*.xml`; klasik: ekran numaraları + açılır pencereler) ve her birini KD'de bir bölüme eşle.
2. Ekran görüntülerini **gerçek arayüz + temiz örnek veriyle** üret (`references/pdf-with-screenshots.md` §A).
   Freestyle UI5 (OData V2) uygulamasında mock ortamı, keşif, çekim senaryosu ve kare kontrolü dahil uçtan uca akış: `%sap-ui5-user-guide`.
   Kirli test kaydı, gerçek müşteri/kişi verisi görüntüye girmez.
3. Şablonu doldur: arka plan sonucu, adım adım akışlar, alan rehberi, butonlar, mesajlar + aksiyon, grid varsa §4-A.
4. Klasik GUI programıysa ikinci ayak F1 yardımıdır: KD'den türetilir, SAP'ye yazımı `%sap-classic-abap` işidir.
5. HTML/PDF üret → `verify_doc_html.py` → kontrol listesi + bağımsız inceleme → anahtar kullanıcı onayı.

### 5. Kontrol listesi + bağımsız inceleme (her doküman, her değişiklik turu)
1. Yazar önce kendi kontrolünü yapar — **bu yetmez**.
2. `agent` aracıyla taze bir inceleyici çalıştır. Alt ajan skill dosyalarını ve konuşmayı **görmez** (ölçüldü): brifinge
   `references/doc-checklist.md` §E bloğunu, ilgili tip bölümünün (§A KD · §B FS · §C TS) ve §D çapraz kontrollerin
   **metnini yapıştır**; dokümanın yolunu ve (varsa) HTML/PDF/ekran görüntüsü yollarını ver.
3. Dönen her BLOCKER'ı kendin dokümanda okuyarak doğrula; doğrulanamayanı NOT'a indir.
4. Düzeltme turu **ikinci kapıdan** geçmeden kapanmaz: dar kapsam (değişen satırlar + değişen sayı/adın diğer geçtiği
   yerler + kararın yayılım listesi), **başka** bir taze inceleyiciyle.
5. Hüküm PASS / WARNING / BLOCKER; BLOCKER varken "bitti" denmez.

### 6. PDF ve canlı teyit
- **PDF:** `build_doc_pdf.py <md> <html> ["Başlık"] [--also parça.md …] [--pdf]` → `verify_doc_html.py <html> [--pdf <pdf>]`.
  Eksik bağımlılıkta script kurulum komutunu yazıp çıkar; kurulum kullanıcı onayıyla yapılır.
- **Canlı teyit turu (TS → build kapısı):** C-1 ad çakışması (pozitif kontrollü) · C-2 reuse iddiaları (kaynak + imza) ·
  C-3 uyarlama durumu · C-4 paket/inaktif · C-5 transport (`E070`/`E071`). Yalnız okuma sınıfı CLI araçları; ölçülemeyen
  başlık "ÖLÇÜLEMEDİ" yazılır. SAP bağlantısı yoksa tur koşulamaz ve TS "canlı teyit bekliyor" durumunda kalır.

## Referanslar, şablonlar, script'ler
| Dosya | İçerik |
|---|---|
| `references/fs-authoring.md` | FS derinliği, görsel ilkesi, İlke 1/2/2b, kaynağa bağlılık etiketleri, bölüm yapısı, kalite listesi, sık hatalar |
| `references/ts-authoring.md` | İlke 3/4/5, FS→TS adımları, genişletme seviyesi ağacı, bölüm yapısı (§2-A, §4.5, §10.1, §11-A), beş parçalı üretim, kalite listesi |
| `references/kd-authoring.md` | KD bölümleri, §4-A grid araçları, alt ekran kuralı, temiz veri, içindekiler kuralı, F1 ikinci ayağı, kalite listesi |
| `references/doc-checklist.md` | DOC-KD/FS/TS/CR maddeleri, ikinci kapı, hüküm, bağımsız inceleme brifingi |
| `references/traceability.md` | numaralandırma, dosya adı, teslim biçimi, durum akışı, donmuş kod ve teslim paketi kuralları, izlenebilirlik matrisi, yayılım tablosu, veri kaybı kontrolü, tersine mühendislik |
| `references/pdf-with-screenshots.md` | bağımlılıklar, temiz ekran görüntüsü, HTML/PDF, doğrulama, Mermaid/Marp, alan tablosu, tuzaklar |
| `references/live-confirmation-tour.md` | C-1…C-5 ölçüm başlıkları, CLI çağrıları, rapor biçimi |
| `templates/FS-template.md` · `TS-template.md` · `KD-template.md` | zorunlu bölümleri taşıyan boş iskeletler |
| `scripts/build_doc_pdf.py` · `html_to_pdf.js` · `doc_tools.py` | Markdown → HTML (TR slug'lı içindekiler, Mermaid → PNG) → PDF |
| `scripts/build_kd_pdf.py` | KD: ekran görüntüsü kırpma, yer tutucu blokları görüntüyle değiştirme (eşleme dosyası) **ya da** adım manifestinden Markdown üretme (`--manifest`), uygulama yardım kopyası |
| `scripts/capture_kd_screens.js` | yapılandırma dosyasıyla adım adım ekran çekimi + model verisi enjeksiyonu (UI5 mock) |
| `scripts/verify_doc_html.py` | ölü içindekiler bağlantısı, ham Mermaid sızıntısı, görsel sayısı/eksik dosya, PDF bağlantı sayısı |
| `scripts/doc_equivalence_check.py` | yeniden yazımda veri kaybı (kimlik, mockup, değer, cümle) + kapanmış karar ters yönü |
| `scripts/check_fs_no_analysis_log.py` | FS gövdesinde analiz günlüğü izi sayımı (sürüm etiketi, inceleme kimliği, süreç ifadesi, kullanıcı alıntısı, önceden→şimdi) + §1.1 satır uzunluğu (DOC-FS-05/06a); uyarıdır, kapı değil |
| `scripts/check_fm_signature_doc_sync.py` | dokümandaki `<!-- FM-IMZA: <FM> -->` bloğu ↔ FM kaynağındaki imza parametreleri, iki yönde (EKSİK · HAYALET); kaynak kökü `sap-project.json` `source_root` (DOC-TS-08); uyarıdır, kapı değil |
| `scripts/gen_field_table.py` | CDS (+ interface CDS, BDEF, CSV) → alan tablosu |
| `scripts/program_to_spec.py` | ABAP/CDS kaynağından taslak FS/TS (yalnız kaynakta olan) |
| `tests/run_tests.py` | çevrimdışı testler (SAP'ye ve tarayıcıya bağlanmaz) |

## Rules
- **Uydurma yok:** iş kuralı, süreç, alan adı, standart SAP obje adı, mesaj metni, DTEL/Z obje etiketi girdiden gelir; yoksa
  sorulur ya da `[Açık Konu]`/`[Varsayım]` diye etiketlenir. Öneri gerçek gibi yazılmaz (`[Öneri]`).
- **Alıntı onay turu açmaz:** metin kanonik bir kaynaktan (onaylı spesifikasyon, DDIC etiketi, emsal uygulama) alınıyorsa
  kaynağına atıfla yazılır ve geçilir; onaya yalnız kaynağı olmayan **yeni iş kavramının** görünen metni ve Z objenin
  DDIC etiketleri gider. Öneri o an sorulur, biriktirilmez. Kaynak damgası ("bunu şuradan aldım") bir onay kuyruğu
  değildir; alıntıyı onaya götürmek her turda kuyruğu büyütür ve işi bitirmez.
- Kullanıcının açık isteği atlanmaz, gölgelenmez, sessizce yeniden yorumlanmaz; çelişki soru olarak getirilir.
- Fonksiyonel açık nokta build'e ertelenmez (FS §11-B'de kapanır, TS gövdesinde çözülür).
- FS ve TS'e ham ekran görüntüsü konmaz (mockup + yapısal tablo); KD'de gerçek arayüz + temiz örnek veri zorunludur.
- Dokümanda standart objeyi değiştiren ya da standart tabloya doğrudan yazan çözüm yazılmaz (Yasak A/B); transport ve
  paket numarası kullanıcıdan gelir, uydurulmaz (Yasak C).
- Kalıcı metne sayı yazarken kaynağa bağla ("onay listesindeki tüm adlar"), sabit sayıya değil; değişen sayı/ad
  dokümanın **her** geçtiği yerde güncellenir.
- Yazar kendi dokümanının son hakemi değildir: inceleme ve ikinci kapı ayrı, taze bağlamda yapılır.
- İncelemede tekrar edebilecek yeni bir doküman tuzağı bulunursa `references/doc-checklist.md`'ye madde önerilir (kullanıcı onayıyla).
