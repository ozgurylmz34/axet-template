---
name: aralikli-hata-avina-butce
description: Aralıklı (flaky) hata ya da yarış avına baştan deneme/süre bütçesi koy; her yeni ölçümde "kararı değiştirdi mi?" diye sor, değiştirmiyorsa ölçümü kes ve bilinen kısıt olarak raporla
type: feedback
---

Aralıklı bir hatayı (yarış, ara sıra boş gelen tablo) avlarken baştan bütçe konur: "en çok N deneme / X dakika; kök neden
bulunmazsa dur, bilinen kısıt olarak raporla". İş alt göreve verilirse bütçe brifin içine yazılır.

**Neden:** Ekip dersinde bir rapordaki aralıklı UI yarışı ("bağlama dolu, tablo boş") bütçesiz bir alt göreve verildi; görev
saatlerce aynı yarışı canlı açılışla saydı. Ara sonuçlar erkenden şunu söylüyordu: hata nadir (3 denemede 1), kendiliğinden
düzelebiliyor, kod kusuru kanıtlanamıyor. Her yeni ölçüm "biraz daha veri" gibi göründüğü için iş kendiliğinden durmadı;
kullanıcı "neden bu kadar bekledin" diye sordu.
**Nasıl uygulanır:**
- Aralıklı hata avının brifine bütçe yaz (deneme sayısı ya da süre + durma koşulu).
- Ara sonuçta şunu sor: "son ölçüm kararı değiştirdi mi?". Hayırsa ölçümü kes.
- Kendi kodumuzun kusuru kanıtlanamayan, nadir ve kendiliğinden düzelen bir hata kullanıcı testini bekletmez; bilinen kısıt
  olarak yazılır ve kullanıcı testine gidilir.
Önceki kayıt: bulundu [[performans-onerisi-de-iddiadir]] (önce maliyeti ölç) — bu kayıt ölçümün kendisine bütçe ekler;
aranan: `memory/`, `skills/diagnosing-bugs` (aralıklı, flaky, bütçe)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: canlı ölçüm/teşhis turları (UI5 yarışları dahil), alt göreve verilen teşhis
