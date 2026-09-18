---
name: yeni-teknoloji-once-arastir
description: İlk kez kullanılan teknoloji, araç ya da üretim görevinde deneme-yanılma yerine önce kanıtlı yöntemi araştır, kural setini hazırla, çıktıyı sayarak doğrula
type: feedback
---

- **Tanıdık olmayan iş** (yeni dosya formatı dönüşümü, resimli PDF üretimi, yeni bir araç): önce "bunun kanıtlı
  yöntemi/aracı ne" diye araştır (`fetch`/`agentic_fetch`, var olan skill'ler, marketplace), sonra tek seferde uygula.
- **Yeni bir SAP teknolojisiyle** (ör. RAP) projede ilk kez SAP'ye yazmadan önce kural seti hazırlanır: çalışan
  yöntem + denenip başarısız olanlar (skill referansı), inceleme checklist'i, adlandırma kuralı. "Deneme" olması bunu
  atlatmaz. Kanıtlanmamış adım `KANITLANMADI` diye işaretlenir, çalışıyormuş gibi sunulmaz.
- **Çıktıyı say:** "üretildi" demeden içeriği ölç (ör. PDF'teki resim sayısı beklenenle aynı mı).

**Neden:** Ardışık tahminle yapılan yamalar pahalıdır ve güven kaybettirir. Bir vakada iki aramada bulunan kanıtlı
yöntem deneme-yanılmayı gereksiz kıldı ve sorunun araçta değil kaynak dosyada olduğunu gösterdi; aynı vakada
"üretildi" denen PDF'te 9 resim yerine 1 resim vardı.
**Nasıl uygulanır:** Kural setinin boyutu belirsizse kullanıcıya seçenek sun (hafif pilot / tam kural seti).
Araştırma bulgusunu uygulamadan önce kaynağıyla birlikte raporla.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
