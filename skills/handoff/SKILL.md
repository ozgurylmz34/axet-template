---
name: handoff
description: Use when a large chunk of work is finished, the topic changes, the conversation has become long, before ending a session, or when the user says "devir notu", "handoff", "yeni oturuma geçelim", "kaldığımız yeri yaz", "devam".
---

# Oturum devir notu

## When to use this skill
- Uzun oturumda bağlam şiştiğinde (otomatik özetleme ayrıntı kaybettirir) ya da iş dilimi bittiğinde.
- Kullanıcı yeni oturumda "devam" / "kaldığımız yerden" dediğinde: önce proje hafızası indeksindeki devir notunu `view` ile oku.

## How to use this skill
1. **Dosya:** proje kökünde `.axet-code/memory/project_devir-<kisa-konu>.md` (aynı konuda eski not varsa onu güncelle — aynı iş için ikinci devir notu açma).
2. **İçerik:**

```markdown
---
name: devir-<kisa-konu>
description: <iş> — devam noktası (<YYYY-AA-GG>)
type: project
---

**Amaç:** <tek cümle>
**Durum:** <yapılanlar> — doğrulama: <komut → sonuç>
**Yarım kalan:** <dosya / adım / neden durdu>
**Kararlar:** <karar — gerekçe>
**Denenip çalışmayan:** <yol — neden çalışmadı>
**Açık sorular:** <kullanıcıya sorulacaklar>
**Sonraki ilk adım:** <yeni oturumda yapılacak ilk somut iş>
```

3. **Kurallar:** ölçülen sayıları birimi ve kaynağıyla yaz; doğrulanmamış bilgiyi `DOĞRULANMADI` diye etiketle; kullanıcının cevaplarını özetleme, aynen aktar; kimlik bilgisi yazma.
4. **İndekse ekle:** `.axet-code/memory/MEMORY.md` → "Kararlar ve durum" altına `- [Devir: <konu>](project_devir-<kisa-konu>.md) — <tek satır durum>`.
5. **Kullanıcıya söyle:** notun yolunu ve yeni oturumda "devam" demesinin yeterli olduğunu.

## Rules
- İş bitince devir notunu sil ve indeksten çıkar (bayat devir notu yanlış yönlendirir); kalıcı ders varsa `%remember` ile ayrı kaydet.
- Proje hafızası yoksa (`.axet-code/memory/` klasörü) oluşturmadan önce kullanıcıya sor.
