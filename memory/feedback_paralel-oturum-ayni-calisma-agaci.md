---
name: paralel-oturum-ayni-calisma-agaci
description: Aynı çalışma ağacında paralel bir oturum varken commit'siz değişikliğin onun commit'ine girip checkout ile ağaçtan "kaybolmuş" görünebilir — kayıp sanmadan önce reflog + açık PR listesi ölç; uzun iş için ayrı worktree
type: feedback
---

Aynı çalışma ağacını paylaşan iki oturum (iki terminal, iki ajan oturumu) birbirinin commit'siz işini TAŞIR. Bir oturum
dal açıp `git add` yaptığında ötekinin değişikliklerini de kendi commit'ine alabilir; ardından `main`'e döndüğünde o
değişiklikler ağaçtan "kaybolmuş" görünür. Kayıp değildir: başka bir daldadır.

**Neden:** Ekip dersinde gün içinde düzenlenen not ve belge dosyaları commit'lenmemişti. Aynı ağaçta çalışan paralel bir
oturum kendi dalını açtı, `git add` ile bu değişiklikleri de kendi commit'ine aldı, push etti ve `main`'e döndü. Saatler
sonra dal açılıp `git add` yapıldığında dosyalarda fark yoktu. Yanlış teşhis ("dosyalar silindi") ya yeniden yazmaya (çift
iş, çakışan PR) ya da yanlış alarma götürür.
**Nasıl uygulanır:**
- Dal açmadan / commit'ten önce `git status` beklenenden boşsa önce ölç: `git reflog -15` +
  `gh pr list --repo <ORG>/<REPO> --state open` + `git show --stat <şüpheli commit>` — içerik başka dalda mı?
- İçerik başkasının açık PR'ındaysa o PR'ı onun işi say; merge kararını kullanıcıya sor (incelemediğin değişiklik taşır),
  kendi kopyanı yeniden yaratma.
- Ortak ağaçta `checkout` yaptıysan hemen geri dön ve kullanıcıya söyle (öteki oturum o anda git komutu koşuyor olabilir).
  Paralel oturum varken uzun iş için ayrı worktree kullan.
- Commit'e yalnız kendi dosyalarını adıyla ekle (`git add <yol>`); ortak ağaçta `git add -A` başka oturumun işini süpürür.
Önceki kayıt: yok — aranan: `memory/` (paralel oturum, aynı çalışma ağacı, worktree, reflog)
Son-doğrulama: 2026-10-19 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tek çalışma ağacını paylaşan birden çok oturum — her proje repo'su
