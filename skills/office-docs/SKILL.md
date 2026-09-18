---
name: office-docs
description: >
  Use when the user wants a Word (.docx) or PDF deliverable produced from Markdown: a report, a memo, a
  step-by-step user guide with screenshots, turning an analysis or a note into a shareable document,
  one Markdown source rendered to both Word and PDF, optionally masking Turkish ID, tax and IBAN
  numbers before the file is written. Triggers: "Word dosyası hazırla", "docx yap", "PDF'e çevir",
  "rapor PDF'i", "kullanım kılavuzu", "ekran görüntülü doküman", "yönetime PDF", "kimlik numaralarını
  maskele". Do not use for spreadsheets (office-excel), slide decks (office-slides), or SAP development
  documents: FS, TS and the end-user guide (KD) of an SAP program go to sap-fs-ts-docs.
---

# office-docs — Markdown → Word / PDF

## When to use this skill
- Kullanıcı düzenlenebilir bir Word belgesi ya da paylaşılacak bir PDF istiyor.
- Adım adım kılavuz: her adım bir başlık + açıklama + ekran görüntüsü.
- **Kullanma:** tablo/Excel işi → `%office-excel` · sunum → `%office-slides`.
- Bu skill **biçim dönüştürür**; bir belgenin içerik yapısını (ör. SAP fonksiyonel/teknik spesifikasyon şablonu)
  belirlemez. Öyle bir şablon/standart varsa önce onu uygula, son adımda burayı kullan.

## Araçlar (`<TEMPLATE>` = template klonu)
| Script | Ne yapar | Gerekir |
|---|---|---|
| `scripts/md_to_pdf.py --input X.md --output X.pdf` | Markdown → HTML → PDF | Edge ya da Chrome (Windows'ta Edge standart); Python paketi yok |
| `scripts/md_to_docx.py --input X.md --output X.docx` | Markdown → düzenlenebilir Word | **python-docx** (isteğe bağlı) |
| `scripts/pii_redact.py --in X.md --out Y.md` | TR IBAN, TC kimlik no, VKN maskeleme | yok |

Ortak seçenekler: `--title`, `--redact-pii` (+ `--pii-mode akilli|genis`), `--force`. PDF'e özel: `--keep-html`,
`--browser`, `--timeout`. Çıkış: `0` başarı · `1` dönüştürme hatası · `3` kullanım · `4` bağımlılık/tarayıcı yok.

## How to use this skill
1. **Kaynağı Markdown olarak yaz** (`.tmp/` ya da kullanıcının verdiği klasöre). Desteklenen alt küme:
   başlık, paragraf, iç içe liste, GFM tablo (hizalama dahil), kod bloğu, alıntı, `---` çizgi,
   tek başına satırda `![alt metin](goruntu.png)`, `<!-- pagebreak -->` sayfa sonu, satır içi kalın/italik/kod/bağlantı.
   Görsel yolu Markdown dosyasına görelidir; alt metin altyazı olur.
2. **Kılavuz deseni:** her adım `## Adım N — <iş>` + 1-3 cümle + `![Adım N](ekran/adim-N.png)`. Ekran görüntülerini
   kullanıcı alır; SAP GUI ekranları için model bir GUI script'i yazabilir, çalıştıran geliştiricidir.
   Görüntüde kişisel veri varsa kullanıcıya hatırlat: maskeleme görüntünün içine uygulanmaz.
3. **Maskeleme gerekiyorsa** `--redact-pii`. Varsayılan `akilli` mod SAP belge numaralarına (10 hane) dokunmaz;
   bağlamsız yazılmış 10 haneli vergi numarası da maskelensin isteniyorsa `--pii-mode genis` (tüm 10-11 haneli sayılar).
   Script'in bastığı sayıları (`iban=… tckn=… vkn=…`) kullanıcıya aktar.
4. **Üret:** aynı kaynaktan Word ve/veya PDF.
   ```
   python <TEMPLATE>/skills/office-docs/scripts/md_to_docx.py --input .tmp/rapor.md --output rapor.docx --title "Aylık Rapor"
   python <TEMPLATE>/skills/office-docs/scripts/md_to_pdf.py  --input .tmp/rapor.md --output rapor.pdf
   ```
5. **Bağımlılık yoksa** (`4`): python-docx için kurulum komutunu kullanıcıya öner, onayını bekle
   (`python -m pip install --user python-docx`). Tarayıcı yoksa `--keep-html` ile HTML üret; kullanıcı tarayıcıda
   Yazdır → PDF yapar.
6. **Doğrula:** script'in bastığı sayılara bak (başlık/tablo/görsel, PDF sayfa sayısı, UYARI satırları).
   Görsel "eklenmedi" uyarısı varsa kullanıcıya bildir, "tamam" deme.

## Rules
- Var olan çıktı yalnız kullanıcı isterse `--force` ile ezilir.
- Kişisel veri içeren kaynak Markdown ve çıktılar repoya commit edilmez (çekirdek güvenlik kuralı).
- Uzak (http) görseller indirilmez; belgeye yer tutucu yazılır.

## Sınırlar
- PDF: sayfa numarası ve üst/alt bilgi yok (tarayıcının başsız yazdırması); mermaid diyagramı çizilmez (kod
  bloğu olarak basılır). Arka plan renkleri CSS ile korunur.
- Word: numaralı listelerin numarası belge boyunca devam edebilir (python-docx varsayılan şablonu); bağlantılar
  tıklanabilir değil, altı çizili metindir.
- Maskeleme yalnız rakam desenlerine bakar: ad, adres, e-posta maskelenmez.
- Doğrulama sınırı: test ortamında python-docx ile yeniden açma ve Edge ile PDF üretimi ölçüldü; Word/Acrobat
  uygulamasında görsel kalite DOĞRULANMADI.
