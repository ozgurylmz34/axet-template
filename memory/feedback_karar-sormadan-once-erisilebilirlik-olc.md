---
name: karar-sormadan-once-erisilebilirlik-olc
description: Bir bulguyu kullanıcıya karar sorusu olarak götürmeden önce arıza yolunun çalışma anında ERİŞİLEBİLİR olduğunu ölç; ulaşılamaz bir daldaki doğru bulgu karar değil temizlik notudur
type: feedback
---

Statik olarak doğru bir bulguyu (inceleme, `%code-review`, kendi okuman) kullanıcıya "hangi seçeneği istersin" diye
götürmeden önce tek soru sor: bu dala hangi veri/koşulla girilir ve o koşul bugün oluşabilir mi? Cevabı ölçerek ver:
çağıran zinciri yukarı doğru izle (guard, erken `RETURN`, zorunlu alan kapısı, kapsayan `IF`).

**Neden:** Ekip dersinde bir inceleme bulgusu (eşik tanımsızken mesajın yer tutucusu boş kalıyor) statik olarak doğruydu
ve kullanıcıya üç seçenekli karar sorusu olarak götürüldü; kullanıcı karar verdi, düzeltme yapıldı. Sonraki ölçüm dalın
ölü olduğunu gösterdi: eşik parametresi zorunlu alan listesindeydi, boşsa program erken `RETURN` ile hiç mail göndermeden
dönüyordu. Zarar yoktu ama kullanıcının karar bütçesi oluşamayacak bir senaryoya harcandı.
**Nasıl uygulanır:**
- Ulaşılamazsa bu bir karar sorusu DEĞİLDİR: "ölü savunma dalı" diye işaretle ya da sessiz temizliğe bırak.
- Ulaşılamazlık da bir iddiadır ve ölçülür. Bugün ölü olan dal bir guard gevşetilince canlanabilir; işaretlemeyi guard'ın
  adıyla yaz ("bugün `<guard>` yüzünden ulaşılamaz").
- Tersi de tuzaktır: "hiç ateşlenmemiş" ile "ateşlenemez" aynı şey değildir; ayrım guard'ın varlığıyla yapılır
  ([[yesil-sinyal-kapsamini-sor]]).
- Karar sorusu gerçekten gerekiyorsa çekirdek §3'teki beş unsurla sor.
Önceki kayıt: yok (aranan: `memory/`, `core/` — erişilebilir, ölü dal, karar sorusu, guard)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — inceleme bulgusunu kullanıcı kararına çeviren iş
