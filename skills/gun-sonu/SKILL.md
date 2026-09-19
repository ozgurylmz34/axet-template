---
name: gun-sonu
description: >
  Use at the end of a working day, or when stopping mid-task, so the next session can resume from
  files instead of memory: writes a checkpoint, updates the package SESSION_NOTES, the project work
  list and the handoff note, commits the work in progress on a branch and pushes it. Triggers:
  "gün sonu", "günü kapat", "bugünlük bu kadar", "yarın devam ederiz", "çıkıyorum", "end of day".
  Do not use for a topic switch inside a running session (use handoff) or for publishing a finished
  change with a pull request (use commit-pr).
---

# Gün sonu — kaldığın yeri dosyaya yaz, commit et, push et

> Süreklilik modelin belleğinde değil dosyalardadır. Yarın yeni oturum `session_brief.py` ile bu dosyaları okur;
> buraya yazılmayan şey kaybolur.

## When to use this skill
- Kullanıcı gün sonu / ara verme / "yarın devam" dedi.
- Uzun bir iş yarım bırakılacak (bağlam dolmak üzere, oturum kapanacak).
- **Kullanma:** oturum içinde konu değişimi → `%handoff`; bitmiş işi PR ile yayınlama → `%commit-pr`.

## How to use this skill
1. **Durumu gör:** proje `AGENTS.md` "Oturum" bölümündeki komutla `session_brief.py --no-fetch`; ardından
   `git status` ve `git diff --stat`.
2. **Checkpoint:** biten (dosya yolları + doğrulama komutu ve sonucu) · yarım kalan (dosya/adım, neden durdu) ·
   yarın ilk somut adım · açık sorular. Doğrulanmamışı `DOĞRULANMADI` yaz. Sonucu beklenen bir alt görev varsa
   sonucunu al ya da "yarım" yaz.
   Bugün bir kural, denetim, regex, `.rules.md` ya da izin değiştiyse checkpoint'e NE OLDUĞUYLA yaz:
   "kural değişikliği: <dosya> <eski → yeni> · kullanıcı onayı: var/yok". "Hata düzeltildi" diye nötrleştirme.
3. **Paket `SESSION_NOTES.md`** (SAP projesinde bir pakette çalışıldıysa): `## Kayıtlar` altına **en üste** yeni kayıt —
   Yapıldı (SAP objesi: push / aktivasyon / sistemden okuma doğrulaması) · Sıradaki · Bloklayanlar · Yeni ders.
4. **İş listesi** `.axet-code/memory/project_is-listesi.md`:
   - Aktif maddeyi güncelle: `- <iş> — durum: <…> · sonraki adım: <…> · ayrıntı: <dosya>`.
   - Bugün kapanan maddeyi `## Arşiv`e tarihle taşı; `## Aktif işler`de bırakma.
   - Tetiğe bağlı ertelenen işi `## Ertelenmiş tetikler`e yaz: `- <tetik> → <iş> (kaynak, tarih)`.
   - Aynı madde başka yerde açık kalmasın: `AGENTS.md` "Açık işler" yalnız bu dosyaya işaret eder.
5. **Devir notu:** iş birden çok oturum sürecekse `%handoff` (aynı konuda not varsa güncelle). İş bittiyse notunu sil.
6. **Ders:** gün içinde kalıcı bir ders, karar ya da kullanıcı düzeltmesi çıktıysa `%remember`.
7. **WIP commit:**
   - `git diff` oku: kimlik bilgisi, `.conn*`, `.env`, geçici dosya, alakasız değişiklik girmeyecek.
   - Bozuk/yarım yazılmış dosyayı commit etme; checkpoint'e "commit edilmedi: <dosya>, <neden>" yaz.
   - `main` ya da `master` üzerindeysen önce `git switch -c wip/<YYYY-AA-GG>-<kisa-konu>` (değişiklikler yeni dalda kalır).
   - Dosyaları adıyla ekle (`git add <dosyalar>`; listeyi kullanıcıya göster) →
     `git commit -m "wip: <konu> — gün sonu <YYYY-AA-GG>"`.
8. **Push:** kullanıcının "gün sonu" demesi **bu projenin bu dalını** push etme talebidir:
   `git push -u origin <dal>`. `--force` yok. Remote yoksa ya da push reddedilirse DUR, çıktıyı aynen bildir.
   Kullanıcı "gün sonu" demeden bu skill'e girdiysen push'u sor.
   - Template reposunda (ekip `memory/` dersleri) değişiklik varsa o **ayrı depodur**: onayı oraya taşıma, ayrıca sor.
9. **Doğrula:** `git status` (temiz ya da bilinçli bırakılanlar listeli) · `git log -1 --oneline` · push çıktısı ·
   `session_brief.py --no-fetch` son hâli.
10. **Rapor:** commit ve dal · push sonucu · güncellenen dosyalar · yarın ilk adım. "Yeni oturumda açılış özeti bunları
    gösterecek; 'devam' demen yeter." de.

## Rules
- Push onayı yalnız bu projenin çalışma dalı içindir; merge, PR, template reposu push'u ayrı onaydır.
- Kimlik bilgisi commit edilmez; şüphede dur ve sor.
- Checkpoint'te sayıları birimi ve kaynağıyla yaz; kullanıcının cevaplarını özetleme, aynen aktar.
- Açık madde tek yerde yaşar (iş listesi); kapanan madde aynı turda arşive taşınır.
