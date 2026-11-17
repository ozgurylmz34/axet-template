---
name: python-yerinde-duzenleme-bayt-kipi
description: Var olan bir repo dosyasını Python'la yerinde düzenlerken bayt kipi (rb/wb + bytes.replace) kullan; metin kipi CRLF'yi LF'ye çevirir ve tek başına CR'yi yeni satıra böler, diff tüm dosyaya yayılır
type: feedback
---

Var olan bir dosyada Python ile bul-değiştir yaparken bayt kipi kullan:
`b = open(f, 'rb').read(); assert b.count(eski) == 1; open(f, 'wb').write(b.replace(eski, yeni))`
(`eski`/`yeni` = `'…'.encode()`; dosya CRLF ise eklenen metindeki `\n`'yi `\r\n` yap). Yazdıktan sonra `git diff --stat <f>`
değişen satır sayısının düzenlemeyle orantılı olduğunu, `git ls-files --eol <f>` satır sonu bilgisinin önce/sonra aynı
olduğunu göstermeli.

**Neden:** Metin kipinde okuma (`newline=None`) `\r\n`'yi ve tek başına `\r`'yi `\n`'ye çevirir; `newline=''` ile yazınca
dosya LF'ye döner. Ekip dersinde çoğu CRLF, bazı satırları LF ve metninde bir literal `\r` olan 8.684 satırlık bir kayıt
dosyasında 15/6 satırlık düzenleme sonrası `git diff --stat` 17.345 satır gösterdi; tek CR yüzünden git dosyayı ikili saydı,
`--ignore-cr-at-eol` maskesi de güvenilmez oldu. Onarım için satır sonları eski sürümden eşlenerek geri yazıldı.
**Nasıl uygulanır:** Yerinde düzenleme için önce `edit` aracı; olmuyorsa (çok sayıda eşleşme, bayt düzeyi iş) Python bayt
kipi. Yeni dosya yazarken bu kural geçerli değildir. Özellikle büyük kayıt/iş listesi dosyalarında ve Windows'ta uygula.
Önceki kayıt: bulundu [[git-diff-ve-satir-sonu]] (CRLF diff'i şişirir — okuma tarafı) — bu kayıt yazma tarafını ekler;
aranan: `memory/` (CRLF, satır sonu, newline, bayt)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — Python ile yerinde dosya düzenleme, Windows
