---
name: kural-yazim-konum-ve-kosul
description: Kural ya da ders yazarken dört tuzak — doğru kural yanlış yerde durur ve ateşlemez, yanlış kural eksik kuraldan tehlikelidir, koşulsuz çürütme geçerli yerde de kullanılmaz, kaynakta duran yanlış iddia dokümanla çürümez
type: feedback
---

1. **Konum:** Kural yazılıdır, ekip daha önce uygulamıştır, yine de o tur atlanır. Sebep çoğu zaman metnin gücü değil
   konumudur: kural bir *duruma* bağlanmıştır ("X demeden önce") ama yapılan *eylem* başkadır ("ders yazmak"); ya da kural o
   adımda okunmayan bir dosyadadır.
2. **Yanlış kural:** Doğru yerde duran yanlış kuralı okuyan uygular ve doğru davrandığını sanır.
3. **Koşulsuz çürütme:** "X çürüdü / X çalışmaz" koşulsuz yazılırsa X'in hâlâ geçerli olduğu bağlamda da kullanılmaz; fazla
   genelleme bilgiyi silmekle aynı sonucu verir.
4. **Kaynakta duran yanlış:** Yanlış iddia kod açıklamasında ya da aracın yardım metnindeyse, dokümana not düşmek onu
   çürütmez, yanına ikinci bir "gerçek" koyar; her okuyan yeniden yanılır.

**Neden:** (1) Kaynak ekipte "önce ara" kuralı yazılı olduğu hâlde bir sınıf iddiası önceki kayıt aranmadan yazıldı:
tetikleyici durum-bazlıydı ve yazma yolundaki hedef seçme adımı "zaten yazılı mı" diye sormuyordu. Aynı turda başka bir "önce
ara" kuralı uygulandı, çünkü az önce okunan dosyada duruyordu. (2) Bir referans RFC sarmalayıcı için `TABLES p TYPE <yapı>`
diyordu; alt görev kuralı okudu, uyguladı ve tam o hatayı (`FL 387`) üretti. (3) SOAP-RFC kanalının commit isteyen BAPI
zincirinde çalışmadığı notu koşullu yazıldığı için, kanalın hâlâ uygun olduğu tek çağrılık FM senaryosunda doğru yöntem
seçilebildi. (4) Bir aracın açıklaması "aktive etmeden kontrol eder" diyordu; ölçüm temiz bekleyen sürümü aktive ettiğini
gösterdi ve düzeltme açıklamanın kendisine yapıldı. Ayrıca iki ders "sonra kalıcı yere taşırım" diye proje notunda bekledi;
birkaç gün içinde aynı sınıfın kardeşi başka bir pakette tekrar ısırdı.
**Nasıl uygulanır:**
- Tetikleyiciyi eylem-bazlı yaz ("şunu yazacaksan / şu aracı çağıracaksan"), durum-bazlı değil.
- Kuralı eylemin geçtiği yere koy: o işte okunan skill referansı, `references/checklists.md` satırı, şablon yorumu. aXet ilgili
  dersi kendiliğinden getirmez; hafıza notu tek başına tetik değildir (`%recall` elle çalışır).
- "Kuralı sertleştirelim / kapı açalım" demeden önce kuralın o anda okunup okunmadığını ölç.
- Bir kuralı düzeltirken aynı yanlışın kopyalandığı diğer yerleri `grep` ile bul ve hepsini düzelt.
- Çürütme notuna koşulu yaz: hangi obje tipi, bağlam, sürüm/uç nokta; kanıtın kapsamadığı alanı "sınır" diye ekle.
- Yanlış iddia kodda/araç metnindeyse önce orayı düzelt (davranışı değiştirmeden iddiayı düzeltmek de altyapı değişikliğidir →
  onay), sonra dokümandan ona bağla.
- Kalıcı ders aynı gün kalıcı yerine yazılır (`%remember` ya da skill referansı önerisi); kaydedilmeyen ders öğrenilmemiş sayılır.
Önceki kayıt: yok (aranan: `memory/`, `skills/remember`, `skills/recall`, `core/` — konum, koşul, çürüdü; yakın: [[inceleme-bulgusu-kontrol-listesine]], [[bayat-sayi-referans]])
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — kural, skill referansı, kontrol listesi, hafıza kaydı ve kod yorumu yazımı
