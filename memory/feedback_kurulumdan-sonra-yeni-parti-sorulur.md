---
name: kurulumdan-sonra-yeni-parti-sorulur
description: Bir kurulum ya da kapanış talimatı bitince plandaki sonraki partiyi sormadan başlatma — plan dosyasında yazılı olmak o anki onay değildir; kısa öneriyle sun, "evet"i bekle
type: feedback
---

Kullanıcının verdiği talimat ("bitince incelemeden geçir ve DEV'e kur") tamamlanınca dur. Planda sıradaki parti yazılı olsa
da onu kendiliğinden başlatma; ne yapılacağını, nedenini ve süresini kısaca sun, kullanıcının "evet" demesini bekle.

**Neden:** Ekip dersinde bir rapor geliştirmesinde kurulum biter bitmez plandaki sonraki parti (sayı biçimi + kullanıcı
kılavuzu) sorulmadan başlatıldı ve yeni bir alt görev açıldı. Kullanıcı "neden tekrar başladı" diye sordu, sonra "devam
etsin, bitince kur, yeni bir şey başlatma" dedi. Kullanıcı süre ve maliyete duyarlıdır; kurulum talimatı yalnız o kurulumun
kapsamını verir.
**Nasıl uygulanır:**
- Talimatın kapsamı bitince DUR; sıradaki partiyi öneri olarak sun (ne · neden · tahmini süre) ve bekle.
- Talimatın parçası olan zorunlu adımlar (bağımsız inceleme, kurulum doğrulaması) bu kuralın dışındadır; onlar istenen işin
  kendisidir.
Önceki kayıt: bulundu [[kararlari-once-topla]] (kararları işe başlamadan topla) — bu kayıt bir işin bitişindeki sınırı
ekler; aranan: `memory/` (parti, sonraki adım, sormadan başlatma)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: çok partili build/deploy turları
