---
name: office-slides
description: >
  Use when the user wants an editable PowerPoint (.pptx) deck: a status or steering presentation from
  a short Markdown outline, a summary deck generated from a CSV/JSON table (one slide per group, long
  tables split across continuation slides), or a slide per screenshot for a walkthrough, optionally
  masking Turkish ID, tax and IBAN numbers first. Triggers: "sunum hazırla", "PowerPoint yap",
  "pptx", "slayt", "yönetim sunumu", "bu tablodan sunum", "ekran görüntülerinden sunum". Do not use
  for Word/PDF documents (office-docs) or spreadsheet work (office-excel).
---

# office-slides — düzenlenebilir PowerPoint

## When to use this skill
- Kullanıcı PowerPoint'te açıp düzenleyebileceği bir deste istiyor.
- **Kullanma:** Word/PDF → `%office-docs` · Excel analizi/karşılaştırma → `%office-excel`
  (Excel verisinden sunum gerekiyorsa önce `office-excel convert` ile CSV/JSON'a çevir).

## Araç (`<TEMPLATE>` = template klonu)
`scripts/build_pptx.py` — üç girdi biçiminden biri:

| Girdi | Ne üretir |
|---|---|
| `--md deste.md` | `---` slayt ayırır · `# başlık` · `## alt başlık` (ilk slayt kapak) · `- madde` (girinti = alt madde) · GFM tablo · tek satırda `![altyazı](goruntu.png)` |
| `--table veri.csv\|.tsv\|.json` | kapak + tablo slaytları; `--group-col Kolon` ile özet slaydı + grup başına slayt |
| `--spec deste.json` | slayt tipleri `title` · `bullets` · `table` · `image` (alanlar script başlığında) |

Seçenekler: `--output X.pptx`, `--title`, `--max-rows 12`, `--redact-pii` (+ `--pii-mode akilli|genis`),
`--dump-spec spec.json` (üretilen slayt planını yazar; python-pptx gerekmez), `--force`.
Çıkış: `0` başarı · `1` hata · `3` kullanım (xlsx girdi dahil) · `4` python-pptx yok.
Bağımlılık: **python-pptx** (isteğe bağlı; yalnız .pptx yazarken).

## How to use this skill
1. **Planı kısa yaz.** Slayt başına tek mesaj, en fazla ~6 madde. Metni Markdown olarak `.tmp/`'ye yaz.
2. **Önce planı göster:** `--dump-spec .tmp/plan.json` ile slayt listesini üret, başlıkları kullanıcıya özetle.
3. **Üret:**
   ```
   python <TEMPLATE>/skills/office-slides/scripts/build_pptx.py --md .tmp/deste.md --output sunum.pptx
   ```
4. **python-pptx yoksa** (`4`): `python -m pip install --user python-pptx` komutunu öner, kullanıcı onaylamadan
   kurma. Beklerken `--dump-spec` ile plan hazır tutulabilir.
5. **Doğrula:** scriptin bastığı slayt sayısını ve UYARI satırlarını (bulunamayan görsel, bölünen tablo) oku ve
   kullanıcıya aktar.

## Rules
- Kurumsal tema/logo uydurma; deste sade ve düzenlenebilir üretilir. Kullanıcı bir şablon isterse
  PowerPoint'te "Tasarım → tema uygula" adımını söyle.
- Görsellerdeki kişisel veri maskelenmez; kullanıcıya hatırlat.
- Var olan dosya yalnız kullanıcı isterse `--force` ile ezilir; kişisel veri içeren çıktılar commit edilmez.
- `scripts/pii_redact.py`, `office-docs` içindekiyle birebir aynı dosyadır (test eşitliği denetler); birini
  değiştirirsen diğerini de eşitle.

## Sınırlar
- Grafik (chart) slaydı yok: grafik gerekiyorsa `office-excel report --chart` ile Excel'de üret ya da görseli
  image slaydına koy.
- Konuşmacı notu, animasyon, geçiş yok.
- Doğrulama sınırı: python-pptx ile yeniden açılıp metin/tablo/görsel sayıldı; PowerPoint uygulamasında görünüm
  DOĞRULANMADI.
