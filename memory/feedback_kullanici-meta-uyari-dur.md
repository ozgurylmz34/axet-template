---
name: kullanici-meta-uyari-dur
description: Kullanıcı "yine yapıyorsun", "kaç defa söyledim", "okudun mu", "kontrol et", "bi dur" gibi meta-uyarı verirse ileri gitmeyi durdur, atlanan dersi ara, yapısal önlem öner, onayla devam et
type: feedback
---

Bu ifadeler içerik talebi değil, çalışma biçimine yönelik uyarıdır. Geldiği anda ilerleme durur.

| İfade | Anlamı | Tepki |
|---|---|---|
| "yine yapıyorsun" | tekrar eden hata | hangi kayıtlı ders ihlal edildi, bul |
| "sürekli aynı hata" | çoklu ihlal | not yetmiyor → yapısal önlem öner |
| "kaç defa hatırlatmama rağmen" | yazılı kural uygulanmıyor | kuralın konumu/tetiği ([[kural-yazim-konum-ve-kosul]]); kontrol listesi satırı öner |
| "kuralı atlama" | ileri gitme eğilimi | atlanan doğrulamayı/kapıyı çalıştır |
| "anladım, yapma" | davranış değişikliği isteniyor | o işi yapma, onay bekle |
| "doğrudan ileri gidiyorsun" | geriye dönük doğrulama atlandı | önce yapılanı denetle, sonra ilerle |
| "okudun mu" | doküman atlandı | ilgili dosyayı oku, sonra cevapla |
| "kontrol et" / "test et" | doğrulama eksik | kodda/sistemde doğrula, çıktıyı göster |
| "geçmişte yapılmış bir iş için neden uğraşıyorsun" | çalışan örnek atlandı | repoda/sistemde çalışan artefaktı bul, desenini kopyala |
| "ne yapmaya çalıştığını söyle" / "bi dur" | körlemesine deneme | dur; hipotez + denenenler + ham hatayı yaz, işi atomik adımlara böl |

**Neden:** Kaynak ekipte bu ifadelerin geldiği vakalarda her seferinde kayıtlı bir ders atlanmıştı: çalışan FM imza push
yöntemi başka bir dosyada duruyordu ve iş "yapılamaz" sanılıp saatlerce denendi; satır numarasız bir kaydetme hatasında
kullanılan bir özellik suçlanıp tahminle defalarca push edildi, kullanıcı "önce aktif sürüme eşitle, sonra değişiklikleri tek
tek ekle" dediğinde ilk atomik adımda gerçek suçlu çıktı.
**Nasıl uygulanır:**
1. İleri gitmeyi durdur; o turdaki işi bitirmeye çalışma.
2. `%recall` ile ilgili dersi ara.
3. Ders varsa hangisinin atlandığını kullanıcıya söyle; yoksa yeni ders olarak `%remember` akışını öner.
4. Yapısal önlem öner: skill referansı, kontrol listesi satırı; yeni doğrulayıcı/kapı ayrıca onay ister.
5. Kullanıcı onayından sonra devam et.
Önceki kayıt: yok (aranan: tüm repo — "yine yapıyorsun", "okudun mu", "kaç defa" → 0 eşleşme)
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler
