---
name: engellenen-silmeyi-komut-olarak-verme
description: Araç ya da izin sisteminin engellediği silmeyi kullanıcıya kopyala-yapıştır komutu olarak verme; kullanıcıya verilen komutta `$` içeren yolu çift tırnağa koyma — bir vakada tüm proje kök dizini silindi
type: feedback
---

Bir silme işlemi araç ya da izin sistemi tarafından engellendiyse (korumalı yol, sistem yolu, `deny` kuralı) o silmeyi
kullanıcıya hazır komut olarak verme. Bu, denetimi kullanıcının eliyle dolanmaktır. Durumu, hedefi ve neden engellendiğini
anlat; kullanıcı silmek isterse dosya gezgininden kendisi yapar ya da güvenli biçim birlikte konuşulur.

**Neden:** Ekip dersinde bir döngüde ters eğik çizgili yol kurulurken `$P` değişkeni genişlemedi ve araçlar `<KOK>$P` adlı
artık bir klasöre yazdı. Model artığı silmeye çalıştı, sistem silmeyi engelledi; model kullanıcıya
`powershell -NoProfile -Command "Remove-Item -LiteralPath '<KOK>$P' -Recurse -Force"` komutunu verdi. Kullanıcı çalıştırdı:
dış kabuk çift tırnak içindeki `$P`'yi tanımsız değişken olarak boşa açtı, komut `Remove-Item -LiteralPath '<KOK>'` oldu ve
kök dizindeki tüm projeler gitignore'lu dosyalarıyla (bağlantı dosyaları, yerel ayarlar) silindi. Repolar yeniden klonlandı;
commit'lenmemiş ve gitignore'lu dosyaların bir kısmı kalıcı kayboldu. Koruma doğru çalışmıştı; kaza onu kullanıcıya
devretmekle oldu.
**Nasıl uygulanır:**
- Engellenen yıkıcı işlemde: dur, açıkla, komut verme.
- Kullanıcıya hiçbir yıkıcı komut (`Remove-Item -Recurse`, `rm -rf`) verme; önce hedefi `Get-Item` / `ls` ile göstermeyi öner.
- Kullanıcıya verilen her komutta `$` içeren literal yol çift tırnak içinde olmaz: tek tırnak ve `-LiteralPath` kullan, dış
  kabuğun da onu açmadığını kontrol et (PowerShell de bash de çift tırnakta `$`'ı açar).
- Döngüde yol kurarken düz eğik çizgi kullan (`"C:/<KOK>/$P"`; ters eğik çizgi `$`'ı kaçırabilir) ve yolu kullanmadan önce
  `echo` ile gör.
Önceki kayıt: yok (aranan: `memory/`, `core/` — silme, engellenen, `$` tırnak; yakın: [[powershell-bom-ve-tirnak]] tırnak
sınıfı, çekirdek §3 izin önerisi)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — kullanıcıya verilen komutlar, Windows (PowerShell / Git Bash)
