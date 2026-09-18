---
name: git-diff-ve-satir-sonu
description: git diff A...B ile A..B farklı sorular sorar; satır sonu (CRLF/LF) farkı diff'i şişirir — "büyük fark / kayıp iş" demeden önce doğru ölç
type: feedback
---

İki ayrı tuzak, aynı sonuç: gerçekte olmayan "büyük fark" alarmı.

1. **Üç nokta ↔ iki nokta.** `git diff A...B` = ortak atadan B'ye: "bu dal kendi ömründe ne yaptı?". `git diff A..B`
   = A'dan B'ye: "bugün aralarında ne fark var?". Squash-merge'de dalın commit'leri ana dala yeni SHA ile girer; bu
   yüzden `A...B`, `git log main..dal` ve `git branch --merged` birlikte "merge edilmemiş iş var" der ve birbirini
   doğruluyormuş gibi okunur.
2. **Satır sonu.** Ham `diff` ya da `git diff --stat`, CRLF↔LF farkını her satırda fark sayar.

**Neden:** Bir denetimde tamamen ana dala girmiş dallar "kayıp iş" gibi göründü; başka bir vakada 614 + 408 satırlık
"drift" CR-nötr ölçülünce 16 + 26 satıra indi. İkisinde de kullanıcıya yanlış alarm verildi.
**Nasıl uygulanır:** Dal silme / kayıp iş kararı: `git diff main..<dal>` + PR durumu (`gh pr list --state merged
--json headRefName`). Büyüklük ölçümü: `git diff --ignore-cr-at-eol --stat` ya da `diff --strip-trailing-cr`.
Hangi soruyu sorduğunu komutu yazmadan önce söyle.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
