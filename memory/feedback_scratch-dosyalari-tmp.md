---
name: scratch-dosyalari-tmp
description: Geçici dosyalar (ekran görüntüsü, deneme çıktısı, döküm) repo köküne değil gitignore'lu .tmp/ klasörüne yazılır
type: feedback
---

Ekran görüntüsü, deneme çıktısı, döküm gibi geçici dosyalar proje köküne yazılmaz; `.tmp/` altına yazılır ve
`.tmp/` `.gitignore`'da olur.

**Neden:** Bir doğrulama oturumunda repo köküne 7 ekran görüntüsü bırakıldı; kök kirlendi ve geçici dosyalar
commit'e girme riskine düştü. Geçici artefakt versiyonlanmaz.
**Nasıl uygulanır:** Geçici dosya gerekince `.tmp/` yoksa oluştur ve `.gitignore`'da olduğunu kontrol et (yoksa
kullanıcıya ekleme öner). İş bitince kalıcı olması gereken bir script çıktıysa `.tmp/`'de bırakma; repo içinde uygun
klasöre gerekçesiyle taşı.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
