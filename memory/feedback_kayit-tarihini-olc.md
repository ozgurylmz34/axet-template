---
name: kayit-tarihini-olc
description: Kayda yazılan tarih çıkarımla yazılmaz — o anda `date` ya da `git log` çıktısından alınır; bir oturumda yanlış gün 15 dosyada 102 kez yazıldı
type: feedback
---

Bir kayda (karar günlüğü, iş listesi, devir notu, SESSION_NOTES, doküman notu) tarih yazarken tarihi o anda ölç:
`date +%F` ya da `git log -1 --format=%ad --date=short`. Tarihi bağlamdaki "bugün" algısından, özetten ya da bir önceki
kaydın tarihinden türetme.

**Neden:** Ekip dersinde bir oturumda kararlar, ölçümler ve notlar ertesi günün tarihiyle yazıldı; commit'lerin hepsi bir
önceki gündü. Yanlış tarih 15 dosyada 102 geçişe yayıldı; bağımsız inceleme "tarih farkı" diye işaretledi ama fark ancak
kullanıcıya rapor yazılırken görüldü. Kök neden: özetteki tarih sorgulanmadan kopyalandı, her yeni kayıt bir öncekini
örnek aldı. Ayrıca ilk sayım `grep -c` ile yapıldı: `grep -c` geçişi değil satırı sayar (73 satır, 102 geçiş).
**Nasıl uygulanır:**
- Kayda tarih koymadan önce `date +%F` çalıştır; bağlam özetlendikten sonraki ilk kayıtta tarihi mutlaka yeniden ölç.
- Toplu sayımda aracın neyi saydığını yaz: `grep -o … | wc -l` geçiş sayar, `grep -c` satır sayar.
Önceki kayıt: bulundu [[kanit-kapsam-ve-zaman-korunur]] (ölçümde zaman damgası) — bu kayıt kaydın kendi tarihini ekler;
aranan: `memory/` (tarih, date, gün)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — kayıt, günlük ve not yazımı
