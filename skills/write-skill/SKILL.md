---
name: write-skill
description: Use when the user asks to create, update or improve a skill, or when a recurring task type or pitfall should be captured as a reusable procedure ("skill yaz", "bunu skill yapalım", "skill'i güncelle").
---

# Skill yazma

## When to use this skill
- Kullanıcı skill istediğinde.
- Aynı iş türü ya da tuzak tekrar ettiğinde: önce kullanıcıya skill önerisi sun, onaylarsa yaz.

## How to use this skill
1. **Önce ara:** var olan skill'lerde (`<template>/skills`, `<template>/skills-sap`, proje `.axet-code/skills`) aynı işi yapan var mı? Varsa onu güncelle.
2. **Kapsamı seç:**
   - Her projede geçerli → template reposu `skills/` (SAP'ye özel ise `skills-sap/`); değişiklik ekibe git ile gider, commit/PR gerekir.
   - Yalnız bu projeye özel → proje `.axet-code/skills/`.
3. **Ad:** küçük harf, rakam ve tek tire (`^[a-z0-9]+(-[a-z0-9]+)*$`). Klasör adı frontmatter `name` ile **aynı** olmalı.
4. **Dosya:** `<kapsam>/<ad>/SKILL.md`

```markdown
---
name: <ad>
description: >
  Use when <tetikleyici durum>…
  Triggers: "<Türkçe tetik ifadeleri>".
---

# <Başlık>

## When to use this skill
## How to use this skill
## Rules
```

   - `description` NE ZAMAN kullanılacağını söyler, ne yaptığını değil; model skill'i buna bakarak seçer.
     **En fazla 1024 karakter, hedef ≤ 900:** aşarsa aXet skill'i **yüklemez** (logda `description exceeds 1024
     characters`, ekranda hata yok). Tetik ifadelerini seçici tut; ayrıntıyı gövdeye yaz.
   - ⚠ `description`'ı daima yukarıdaki `>` blok biçiminde yaz. Tırnaksız tek satırlık bir değerin içinde `: ` (ör. `Triggers: "…"`) geçerse YAML bozulur ve aXet skill'i **sessizce düşürür** — ekranda hata çıkmaz, yalnız logda `Failed to parse skill file` görünür. Yazdıktan sonra `python <template>/scripts/doctor.py` çalıştır.
   - Gövde kısa tutulur; uzun başvuru bilgisi `references/` altına, script'ler `scripts/` altına konur ve SKILL.md'den yollarıyla anılır.
   - Script yolları skill klasörüne göre yazılır; kullanıcıya özel mutlak yol yazılmaz.
   - Kimlik bilgisi, müşteri adı, sistem adresi yazılmaz.
5. **Test:** YENİ bir aXet oturumu aç (skill'ler oturum başında bulunur) → `%<ad>` ile çağır → modelin `SKILL.md`'yi okuyup adımları izlediğini gör.
6. Template seviyesindeyse README'deki skill listesine ekle.

## Kural yazarken
Skill kuralı, kontrol listesi satırı, çekirdek ya da `AGENTS.md` maddesi, hafıza dersi — yazarken **ve** var olan
kuralın metnine dokunurken (dokunulmayan eski kurallar toplu yeniden yazılmaz). Kural çoğu zaman yokluğundan değil
yazılışından kaçar: uygulayacak kişinin o an açtığı dosyada değildir ya da hangi eylemde uygulanacağını söylemez.
- **Dört alan:** **NE** — tek anlamlı, ölçülebilir eşik ("ya da eşdeğeri" gibi ölçütsüz ifade yok) · **NEDEN** — önlediği
  hata: mekanizma tek cümle + vaka (tarih; müşteri/sistem adı yok) · **NE ZAMAN** — hangi eylemde, hangi dosya türünde
  ateşler ("`.clas.abap`'a yeni metot yazarken"; yalnız semptom — "push 400 verirse" — yetmez, o an iş olmuştur) ·
  **NEREDE** — uygulayacak kişi ya da model onu o an hangi dosyada okuyor (o işin skill'i/referansı, kontrol listesi,
  çekirdek). Yalnız hafıza ya da iş listesi yetmez. Kanonik metin tek yerde durur; öbür kanala ateşleme anını taşıyan
  tek cümle + atıf yazılır, ayrıntı kopyalanmaz.
- **Olumsuz iddia koşuluyla:** "X çalışmaz / yasak / yok" cümlesine profil/sürüm, obje tipi, araç, bağlam ve ölçüm
  tarihi yazılır; ölçülmeyen komşu bağlam `ÖLÇÜLMEDİ` diye anılır. Koşulsuz çürütme, X'in geçerli olduğu yerde de kullanılmaz.
- **Üç test (birleştirmeden önce):** **netlik** — yazmayan, bağlamsız bir okura (salt-okur inceleme ajanı, çekirdek §7)
  yalnız kural metni + 2-3 senaryo ver (biri istisna); beklenen cevabı önceden yaz, ayrışırsa metni düzelt ·
  **ulaşım** — kural → onu okuyan rol → dosya → satır zincirini `rg` çıktısıyla göster · **çelişki** — anahtar terimi ve
  eşanlamlılarını Türkçe harf varyantlarıyla (çekirdek §2) `rg` ile tara, sayısal sınırlarda koddaki değeri de; çelişeni
  hizala ya da iki tarafa gerekçeli istisna yaz.
- Ayrıntı ve vakalar: `<template>/memory/feedback_kural-yazim-konum-ve-kosul.md`.
