---
name: performans-onerisi-de-iddiadir
description: Bir hızlandırma önerisi de ölçülmemiş bir iddiadır; maliyetin nerede olduğunu ölçmeden kaldıraç önerme, göze çarpan kalem çoğu zaman maliyetli kalem değildir
type: feedback
---

"Şunu kısarsak hızlanır" cümlesi bir iddiadır ve ölçüm ister. Göze çarpan kalem (uzun rapor, "yavaş" görünen araç) ile
maliyetli kalem (asıl üretim işi, tur sayısı, bekleme) çoğu zaman aynı şey değildir. Ölçmeden önerilen kaldıraç doğru
görünen ama etkisiz bir değişiklik yaptırır ve gerçek kaldıracı gizler.

**Neden:** Ekip dersinde "bu iş neden 25 dakika sürüyor" sorusuna ölçmeden "rapor uzunluğunu kısarsak maliyetin üçte biri
gider" cevabı verildi. Ölçüm öneriyi çürüttü: maliyetin yaklaşık %95'i asıl ürünü yazan araç çağrılarıydı, serbest
anlatı %5'in altındaydı; süreyi belirleyen tur sayısıydı. "Yavaş" sanılan tarayıcı aracı da 16 ekran görüntüsünü 27
saniyede üretiyordu — toplam sürenin yaklaşık %2'si.
**Nasıl uygulanır:**
- Önce maliyet dağılımını çıkar (zaman damgaları, çıktı boyutları, adım başına süre; repoda zaten bir ölçüm aracı olabilir
  — önce ara), sonra kaldıraç öner.
- Duvar saatini ve diğer maliyeti (token, CPU) ayrı raporla; biri düşerken öteki değişmeyebilir.
- Ölçüm önerini çürütürse öneriyi açıkça geri çek; ölçülmemiş bir gözlemi doğrudan iş listesine yazma.
- SAP tarafında da aynıdır: bir sorgu/program hızlandırma önerisinden önce süreyi neyin aldığını ölç (ör. SQL izi); tahmini
  darboğaza optimizasyon yazma.
Önceki kayıt: yok (aranan: `memory/`, `core/` — performans, hızlandırma, maliyet, kaldıraç)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — hız/maliyet iyileştirmesi öneren her iş
