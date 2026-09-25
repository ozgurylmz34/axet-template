---
name: kullanicinin-bildigini-olcme-sor
description: Kullanıcının bizzat yaptığı bir denemenin sonucu ya da iş tarafında bildiği bir gerçek için uzun canlı ölçüm başlatma; önce tek soru olarak kullanıcıya sor, beyanı kaynağıyla kaydet
type: feedback
---

Kullanıcının kendi denediği bir şeyin sonucunu ("çalıştı mı?") ya da iş tarafında zaten bildiği bir gerçeği ("bu alan
hangi müşteride dolu gelir?") sistemde uzun bir ölçümle ya da `agent` ile devredilen bir araştırmayla bulmaya çalışma;
önce tek bir soru olarak sor.

**Neden:** Ekip dersinde bir deneme sonucunu ve bir alan grubunun doluluğunu ölçmek için ayrıntılı bir canlı ölçüm
planlandı; kullanıcı araya girip "evet işe yaradı, bana sorabilirsin" ve "o alanlar genelde hepsinde var" dedi. Ölçüm
bütçesi kullanıcının bir cümlede verebileceği bir bilgiye harcanıyordu.
**Nasıl uygulanır:**
- Ölçüm planlarken ayır: (1) kullanıcının yaptığı ya da iş olarak bildiği → SOR; (2) kodun/verinin davranışı ve
  kullanıcının bilemeyeceği teknik değerler (tip kodu, tablo değeri, segment sayısı) → ÖLÇ.
- Bu, TAHMİN YASAK kuralını gevşetmez: soru da bir kanıt kaynağıdır. Cevabı "kullanıcı beyanı" diye kaynağıyla yaz;
  sonradan çelişen bir ölçüm çıkarsa bunu not düş.
- Soruyu çekirdek §3'teki gibi sor: tek seferde, bağlamıyla, önerinle (`ask_user`).
Önceki kayıt: yok (aranan: `memory/`, `core/` — kullanıcıya sor, beyan, ölçüm yerine; yakın ama farklı:
[[kararlari-once-topla]] kararların ne zaman toplanacağını söyler, bu kayıt bilginin ölçülmek yerine sorulmasını)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — iş kuralı ya da kullanıcı denemesi sonucu içeren analiz işleri
