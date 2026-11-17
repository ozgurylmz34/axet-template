---
name: uygulama-testi-onayla-yazilir
description: Yeni uygulama testi (ABAP Unit, karakterizasyon, UI testi) yazmadan önce kullanıcıya maliyet ve gerekçeyle sor, açık onay al — test işi uzatır; mevcut testleri koşmak onay istemez
type: feedback
---

Uygulamaya yeni test yazmadan önce kullanıcıya sor ve açık onay al: ABAP Unit, karakterizasyon testi, yeni test metodu, UI
testi dahil. Alt göreve verilen brifte de "yeni test yazma (kullanıcı onayı yok)" maddesi bulunur.

**Neden:** Ekip dersinde bir paketin ATC düzeltme turunda kullanıcıya sorulmadan iki aşamalı karakterizasyon testi (5 test,
~446 satır, ~16 dk ek iş) yazdırıldı. Kullanıcı: "benden açık onay almadan test yazma, test işi uzatıyor; karmaşık senaryo
fazla olduğunda ben isterim. Bu uygulama için teste gerek yok, iç yazışma maili; yanlış olsa bile testte görünür, düzeltiriz."
Kritiklik değerlendirmesini kullanıcı yapar.
**Nasıl uygulanır:**
- Varsayılan: davranışı korunması gereken düzeltmede bile yeni test yazılmaz; doğrulama mevcut testler, salt-okur
  karşılaştırma ve kullanıcı testiyle yapılır. Test gerekli görünüyorsa maliyet + gerekçeyle sor.
- Mevcut testleri koşmak (regresyon) onay gerektirmez; yalnız YENİ test yazmak gerektirir.
- Kapsam: SAP/uygulama testleri. aXet'in kendi araç ve betik değişikliklerindeki testler bu kuralın dışındadır; orada test
  teslimin parçasıdır.
Önceki kayıt: yok (aranan: `memory/`, `skills/diagnosing-bugs` — "test politikası", yeni test, onay)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: SAP uygulama geliştirme (tüm profiller), uygulama testi yazımı
