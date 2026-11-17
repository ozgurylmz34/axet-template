---
name: is-parametresini-koda-gomme
description: Kullanılan bir iş parametresini (eşik, yüzde, süre) koda sabit gömmeyi önerme — kullanılıyorsa ayar tablosunda kalır, kullanılmıyorsa alan ve mantık birlikte kaldırılır
type: feedback
---

Bir ayar tablosunu sadeleştirirken "bu değerler kodda sabit olsun" seçeneği önerilmez. Alan gerçekten kullanılıyorsa
tabloda kalır; kullanılmıyorsa ya da tasarımı hatalıysa alan ve onu okuyan mantık birlikte kaldırılır.

**Neden:** Ekip dersinde bir rapor paketinin ayar tablosu sadeleştirilirken "karşılaştırma kartının üç ayarı (%8, %25,
8 hafta) kodda sabit olsun" önerildi. Kullanıcı: "koda gömme, kullanılacaksa tabloda kalsın". Aynı turda gerçekten hatalı
olan alanın kaldırılmasını ise onayladı. İş değerini koda gömmek her ayar değişikliğini geliştirme işine çevirir;
spesifikasyondaki "iş değerleri kodda sabit değil" kuralı kullanıcının bilinçli tercihidir, "az kullanılıyor" gerekçesi onu
gevşetmez.
**Nasıl uygulanır:** Sadeleştirmede her alan için önce "gerçekten kullanılıyor mu?" sorusunu cevapla (kod + canlı veri).
Kullanılmıyor → kaldırmayı öner. Kullanılıyor → tabloda kalır; "koda sabit" seçeneğini seçenek listesine koyma.
Önceki kayıt: bulundu [[is-kurali-sessizce-gomulmez]] (build sırasında kaynaksız kural gömme) — bu kayıt iş DEĞERİNİN
yerini ekler; aranan: `memory/` (sabit, ayar tablosu, koda gömme)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — ayar tabloları, spesifikasyondaki iş parametreleri
