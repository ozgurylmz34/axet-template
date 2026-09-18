---
name: inceleme-bulgusu-kontrol-listesine
description: İncelemede yakalanan, tekrar edebilecek bir tuzak yalnız nota ya da hafızaya yazılmaz; inceleyenin okuduğu kontrol listesine madde olarak girer
type: feedback
---

Bir inceleme, karşılaştırma ya da hata sonrası analizde tekrar edebilecek bir tuzak bulunursa ders iki yere gider:
yazanın okuduğu yöntem referansı (çalışan desen) ve inceleyenin okuduğu kontrol listesi. Asıl koruma kontrol listesidir.

**Neden:** İnceleme kontrol listesi tabanlı çalışır; listeye girmeyen tuzak bir sonraki incelemede aranmaz ve tekrar
kaçar. Kaynak vakada bir kaydetme hatası serisinden 4 tuzak çıktı (metadata'dan kayan alan adı, hatayı genel mesajla
yutma, commit bariyeri, Create/Change ekranları arasında kopya kayması); bu yüzden yöntem notunun yanında inceleme
listesine de eklendi.
**Nasıl uygulanır:** Bulgu çıkınca: (1) düzelt, (2) ilgili skill referansına çalışan deseni/tuzağı yaz, (3) kontrol
listesine madde öner: kontrol + önem (BLOCKER/WARNING) + referans. aXet'te liste yerleri: SAP skill'lerinin
`references/checklists.md` dosyaları, genel incelemede `%code-review` kontrol listesi. Template reposundaki skill
değişikliği ekibe gider → kullanıcıya öner, onay ve commit/PR ile gir.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
