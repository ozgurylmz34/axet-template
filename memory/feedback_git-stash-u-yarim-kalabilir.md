---
name: git-stash-u-yarim-kalabilir
description: Dal açmadan önce değişikliği taşımak için `git stash -u` kullanma — salt-okunur boş dizinli ağaçta stash YARIM kalır, izlenmeyen dosya diskten silinir, `&&` zinciri kırılır ve `stash pop` hiç koşmaz; HEAD origin/main'e eşitse stash'siz dal aç
type: feedback
---

İş dalı açmadan önce çalışma ağacındaki değişikliği taşımak için `git stash -u` kullanılmaz. Önce `git rev-parse HEAD`
ile `git rev-parse origin/main` karşılaştırılır; eşitse değişiklikler olduğu yerde kalır ve `git checkout -b <dal>`
doğrudan yeterlidir (checkout commit'siz değişikliği taşır).

**Neden:** Ekip dersinde (Windows) `git stash -q -u && git checkout -b … origin/main && git stash pop` zinciri koşuldu.
Ağaçta salt-okunur boş dizinler vardı: stash commit'i YARATILDI, izlenmeyen dosya stash'e alınıp diskten SİLİNDİ, ardından
boş dizinleri silme adımı `Permission denied` ile düştü ⇒ çıkış kodu sıfırdan farklı ⇒ `&&` zinciri kırıldı, `stash pop`
hiç koşmadı. Dosya yalnız `stash@{0}^3` ağacındaydı ve çıktı "failed to remove" uyarılarına gömülüydü; sonraki push
"src refspec does not match" ile düştü. Veri kaybı olmadı ama yalnız elle kontrol edildiği için.
**Nasıl uygulanır:**
- Dal açmadan önce `HEAD == origin/main` ölç; eşitse stash'siz `checkout -b`.
- Değilse stash yerine izlenmeyen dosyaları geçici bir klasöre KOPYALA, sonra dal aç.
- Bir stash beklenmedik düştüyse `pop`'u körlemesine koşma; önce içeriği ölç: `git stash list` +
  `git show --name-only --format= stash@{0}^3` (izlenmeyenler) + `git stash show --name-only` (izlenenler). Kurtarma:
  `git show stash@{0}^3:<yol> > <yol>`, ardından `git hash-object <yol>` ile blob eşliğini doğrula, sonra `git stash drop`.
Önceki kayıt: yok — aranan: `memory/` (stash, dal açma, izlenmeyen); komşu [[git-diff-ve-satir-sonu]] başka konu
Son-doğrulama: 2026-10-19 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: Windows, salt-okunur dizin içeren proje ağaçları — dal açma ve commit'siz değişikliği taşıma
