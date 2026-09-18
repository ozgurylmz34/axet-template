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
