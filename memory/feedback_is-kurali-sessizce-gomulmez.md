---
name: is-kurali-sessizce-gomulmez
description: Tasarım ya da build sırasında senin koyduğun bir iş kuralı (hangi kayıt dışlanır, neye izin verilir) koda/süzgece sessizce gömülmez — kaynağı yoksa ayrı karar maddesi olarak kullanıcıya sunulur ve karar artefakta yazılır
type: feedback
---

Tasarım ya da build sırasında bir iş kuralı koyduysan ("şu tipteki kayıt hedef olamaz", "şu durumdaki belge listelenmez")
bu kural koda ya da CDS süzgecine sessizce gömülmez. Kaynağı (kullanıcı kararı · FS · TS) yoksa kullanıcıya "bu benim
kararım, onaylıyor musun?" diye ayrı bir karar maddesi olarak sunulur; karar intake/FS artefaktına yazılır.

**Neden:** Ekip dersinde hedef listesinden bir kayıt tipini dışlayan kural, kullanıcının değil uygulayanın onaysız
kararıydı. Kullanıcı "hedef liste boş geliyor, bir sebebi var mı?" diye sorunca "benim kararımdı" denebildi; kullanıcı
tersini seçti ve DDIC + sınıf + iki CDS yeniden yazıldı. Onay ilk seferde alınsaydı tek tur yeterdi.
**Nasıl uygulanır:** Tasarımda ve brifte "şunu dışla / yasakla / sınırla" türü her satırı işaretle; kaynağı yoksa onay
listesine koy (toplu sorma zamanı: [[kararlari-once-topla]]). Kullanıcı sorduğunda kural onaysızsa bunu açıkça söyle.
Önceki kayıt: bulundu [[kararlari-once-topla]] (kararları ne zaman toplayacağın) — bu kayıt build sırasında kendi doğan
kuralı ekler; aranan: `memory/` (iş kuralı, onay, karar, sessiz)
Son-doğrulama: 2026-10-19 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: iş kuralı içeren her tasarım/build turu
