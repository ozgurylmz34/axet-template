---
name: ortam-normal-hukmu-hata-metnini-oku
description: Tekrarlayan bir hatayı "bu ortamda normal / test sisteminde zaten çalışmaz / DEV'de hep böyle" diye beklenen saymadan önce hata kaydının TAM metnini oku ve aynı ortamda başarılı tek bir örnek ara; "ortamın doğası" bir sebep iddiasıdır, gözlem değil
type: feedback
---

Bir hata sürekli tekrar ediyor ve "test sisteminde X zaten çalışmaz" diye **beklenen** sayılıyorsa, hüküm bir kez
verildikten sonra hiçbir yeni olay onu sorgulatmaz: her yeni kayıt hükmü "doğrular". Oysa çoğu zaman hata satırının
kendisi sebebi söyler; kimse okumadığı için kök sebep aylarca saklanır.

**Neden:** Ekip derslerinde (S/4 private, geliştirme sistemi) SAPconnect gönderim kayıtlarında (SOES) aylardır yüzlerce
`XS 812` birikmişti; "test sisteminden dışarı mail çıkmaz, SOST'a düşmesi yeter" kuralı yazılmış, hafızaya bile
kaydedilmişti. Hata satırı sebebi söylüyordu: `554 5.2.252 SendAsDenied; <teknik-adres> not allowed to send as
<SAP-kullanıcısının-adresi>` — kurumsal relay yalnız yetkili bir teknik adresten gönderime izin veriyordu, mail ise SAP
kullanıcısının adıyla gidiyordu. Gönderen değişince aynı sistemden mail dış posta kutusuna ulaştı (SOES `718 I`
"Recipient OK"). Yan etki: "çıkmaz" varsayımı yüzünden test maili gerçek alıcıya gidebilir hâle geldi (gönderen düzelince relay artık reddetmiyor).
**Nasıl uygulanır:**
1. Hükmü vermeden önce hata kaydının **tam metnini** oku: kod + serbest metin (MSGV alanları, SMTP yanıtı, dump'ın
   "Hata analizi" bölümü). Durum kodu ya da sayaç (`812 × 300`) kanıt değildir; **metin** kanıttır.
2. **Kontrol grubu:** aynı ortamda başarılı olan tek bir örnek var mı? Varsa "ortam izin vermiyor" hükmü yanlıştır.
3. Hükmü yazacaksan dayandığı kanıtı da yaz ("812'nin metni şunu söylüyor"), yalnız sonucu değil.
4. Tetik cümleleri: "test sisteminde normal" · "DEV'de zaten çalışmaz" · "orada hep böyle". Bu cümleyi kurarken ya da
   kullanıcıdan duyarken 1-2'yi koş; kullanıcının beyanıysa ondan hata metnini birebir iste.
SAP e-posta özel karşılığı (gönderen politikası, SOST/SOES teşhis tablosu): `%sap-classic-abap` → `email.md` §1, §1.1.
Önceki kayıt: yok (aranan: `memory/`, `core/`, `skills-sap/` — "test sistem", "ortamda normal", "SendAs", "SOES";
yakın ama farklı: [[sifir-sonuc-kanitla-once-kontrol-grubu]] sıfır sonucun aracı mı olguyu mu gösterdiği,
[[yesil-sinyal-kapsamini-sor]] yeşil sinyalin kapsamı — bu ders kırmızı sinyalin "normal" diye susturulmasıdır)
Son-doğrulama: 2026-10-04 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — tekrarlayan hatayı ortamın doğasına bağlayan her hüküm; SAP'de özellikle SAPconnect/SOST, RFC, arka plan işi
