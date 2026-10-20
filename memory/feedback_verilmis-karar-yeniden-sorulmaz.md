---
name: verilmis-karar-yeniden-sorulmaz
description: Yeni bir "onay al" kuralı ya da onay turu, kullanıcının daha önce açıkça verdiği kararları yeniden sordurmaz — önce karar kaydını tara; kararlı kalem sorulmaz, "zaten kararlı (K-n)" diye bildirilir
type: feedback
---

Bir onay listesi kurmadan önce kullanıcının daha önce verdiği kararlar taranır. Sorulacak liste = tasarımdaki kalemler −
kullanıcının zaten açıkça kararlaştırdıkları. Yeni bir onay kuralı geriye dönük karar sorgulatmaz.

**Neden:** Ekip dersinde mevcut-altyapı onay turunda bir tasarım kalemi (belli bir belge türünü dışlayan süzgeç) yeniden
soruldu; oysa kullanıcı karar kaydında "bu belgeler her zaman etkisizdir, hiçbir noktada dikkate alınmamalı" demişti.
Kullanıcı: "Bunu daha önce de sordun … sürekli sorman beni korkutuyor". Kararlı kuralı tekrar sormak "kural uygulanmıyor
olabilir" sinyali verir, güveni sarsar ve kullanıcının zamanını törene harcar.
**Nasıl uygulanır:**
- Onay listesinden önce karar kaydını tara (intake artefaktının karar tablosu, FS ekleri, paket kuralları); kalemi bağlayan
  karar varsa onu "zaten kararlı (K-n)" diye bildir, sorma.
- Sorulacak olan yalnız kararın kapsamadığı yeni boyuttur (ör. uygulama biçimi değişmişse); o zaman da kararı alıntıla,
  yalnız farkı sor.
Önceki kayıt: bulundu [[kararlari-once-topla]] (kararları tek seferde topla) — bu kayıt zaten verilmiş kararı listeden
düşürmeyi ekler; aranan: `memory/` (yeniden sor, karar kaydı, onay turu)
Son-doğrulama: 2026-10-19 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: onay/karar turu açan her iş
