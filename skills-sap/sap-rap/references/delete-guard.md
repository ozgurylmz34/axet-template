# Silme kontrolü (delete guard) — backend kuralından kullanıcının gördüğü mesaja

> Kaynak: ekip silme kontrolü nasıl-yapılır dokümanı (gerçek bir tur: 7 uygulama, 13 backend guard) ve RAP hata teşhisi kontrol
> listesinin delete validation maddesi; aXet'e uyarlandı. Profil: RAP maddeleri `s4_*`/`btp_abap`.
> Bu skill backend'dir; ön yüz maddelerinin (seçim bayatlaması, bekleyen değişiklik guard'ı, paralel silme, hata ayrıştırıcı,
> i18n) ayrıntısı UI skill'inin kapsamıdır. Kabul ölçütü yine **kullanıcının gördüğü metindir**.

## 1. Guard beş katmandır — biri eksikse kural ölü koddur

```
(1) backend validation VAR mı
 → (2) BDEF'te KABLOLU mu      validation <ad> on save { delete; }
 → (3) DOĞRU ENTITY'de mi      root mu child mı
 → (4) mesaj BELGE NO taşıyor mu ve 50 karaktere sığıyor mu
 → (5) ön yüz o yola GİDİYOR mu ve mesajı BASIYOR mu
```
Ölçülen vaka: 13 guard canlı, kablolu, belge numaralıydı — ama ön yüz backend'i hiç çağırmadığı için kullanıcı hiçbirinde numarayı
görmüyordu. "Backend doğru" ≠ "kullanıcı görüyor".

## 2. İş kuralı tek kaynakta: backend

Ön yüzde "sil'e basmayı engelleyen" iş kuralı kontrolü backend mesajını hiç ürettirmez (kural ulaşılamaz kod olur), bayat veriye
dayanır ve mesajı iki yerde bakıma böler. Satır seçimi, düzenleme modu, kilit, veri kaybı uyarısı ve gösterim kontrolleri iş
kuralı değildir; kalır.

## 3. Ön yüz kapısını kaldırmadan önce backend karşılığını ÖLÇ

Kapı kaldırmak, arkasında backend kuralı yoksa **koruma silmektir**. Ölçülen vaka: "backend zaten reddeder" gerekçesiyle
kaldırılacak kapının BDEF alt bloğunda `delete;` vardı ama **validation yoktu** — kaldırılsaydı silme sessizce başarılı olacak,
bağlı kayıt yetim kalacaktı.

Dördü de EVET olmalı; biri HAYIR ise kapı kalır, önce backend kuralı yazılır:
1. validation var mı · 2. doğru entity'de mi · 3. `on save { delete; }` ile kablolu mu · 4. mesajı belge numarası taşıyor mu.

⚠ Kandırıcı komşular: root'u koruyan validation child'ı korumaz; `on save { create; update; }` delete'i kapsamaz.

## 4. Envanter — `delete;` olup validation'ı olmayan her entity korumasız yoldur

BDEF taraması (sistemdeki BDEF'leri `adt_get bdef` ile oku; CCIMP için `adt_grep_source`):

| entity | `delete;` | validation | kablolu | handler (CCIMP satırı) | mesajda belge no | canlıda aktif | tüketen uygulama |
|---|---|---|---|---|---|---|---|

Ölçülen örnek: bir pakette 19 entity `delete;` taşıyordu → 13 korumalı, 6 korumasız. Korumasız her biri için veri kaybı
senaryosunu SQL ile doğrula (hangi tablo hangi alan üzerinden yetim referansa düşer); "teorik risk" yazma.

## 5. Cascade delete child validation'ı tetikler mi — BO BAZINDA ölçülür

Bir BO'da "cascade'de kalem validation'ı tetikleniyor" ölçümü başka bir BO'ya taşınmaz; her BO ayrı runtime testi ister.
Kesin boşluk: 0 kalemli başlıkta tetiklenecek child guard yoktur.

## 6. RAP mesajı 50 karakterde sessizce kesilir

`new_message_with_text` metni OData'da hem `error.message.value` hem `errordetails[].message` alanında **tam 50 karakterde**
kesilir (canlı ölçüm); tam metin hiçbir yerde yok, ön yüz kurtaramaz.

- Belge numarası mesajın sonuna değil **öneğin hemen ardına** konur.
- Toplam uzunluk hesaplanır (sabit "ilk 3 numara" varsayımı yok); sığmayan adet `+N` ile görünür yapılır — sessiz kırpma yok.
- Önek bütçesi ≤ 34 = 50 − 1 (boşluk) − 10 (belge no) − 1 (boşluk) − 4 (`+999`).
- Birim testi iki sözleşmeyi de kanıtlar: **uzunluk** (her N için ≤ 50) ve **fayda** (numara sığıyorsa metinde gerçekten
  görünüyor — kullanılan her önek × birkaç N). Yalnız uzunluk test edilirse numarasız mesaj da yeşil geçer.
- Metin `master_language`'de ve spesifikasyondan.

## 7. Delete validation kodlama tuzakları

- **`READ ENTITIES` ile başlayan delete validation hiç koşmaz:** validation anında örnek tamponda silinmiştir → READ boş →
  erken `RETURN` ya da boş döngü; hata/uyarı yok, statik kontrollerin hiçbiri görmez. Doğrudan `keys` üzerinde çalış (yalnız
  key alanları; başka alan için veritabanından oku). Ölçülen vakada 10 delete validation'ın 9'u bu hatayı taşıyordu → sistemde
  doğru örneği bul ve hizala (`behavior-impl.md` §7).
- `field …` listesi `create;`/`update;` tetikleyicisini daraltmaz; muafiyet handler içinde.
- Silme engeli birden fazla sebep üretebilir → her engel ayrı `reported` satırı (`errordetails[]`'e düşer).

## 8. Kabul ölçütü — statik doğrulama runtime'ın yerine geçmez

Ölçülen turda sözdizimi kontrolü, grep, kablolama doğrulaması ve altı bağımsız inceleme turu geçti; runtime testinde yine kusur
çıktı ve asıl kabul kanıtı ("mesaj silme anında ve belge numarasıyla çıkıyor") ancak çalışan uygulamada alındı.

Backend tarafı minimum runtime seti:
1. Engellenmesi **kanıtlı** bir kayıtta silme → mesaj görünüyor mu · belge numarası var mı · 50 karakter altında mı · **silme
   anında** mı (kaydetme anında değil).
2. Her denemenin önü ve ardı veritabanı sorgusuyla (`adt_sql_query`) doğrulanır — "veri değişmedi" iddiası ölçülür.

⛔ **Test verisi yaratma.** Engellenecek kayıt yoksa "DOĞRULANAMADI (sebep)" yaz.
⛔ **Engellenmesi kanıtlanmamış kayıtta gerçek silme deneme.** Guard'ın canlıda var, güncel ve kablolu olduğu doğrulanmadan
silme denenmez — guard eski sürümdeyse silme başarılı olur ve geri alınamaz. Silme denemesi yazma sınıfıdır, açık onay ister.

## 9. Araç sınırı ≠ yokluk

- Behavior pool'un `source/main`'i boştur; CCIMP araması yalnız main'e bakan bir araçla **0** döner — "metot yok" değildir
  (ölçüm: main 166 bayt, CCIMP 21.264 bayt). `adt_grep_source` sonucunda `coverage_complete`'e bak.
- `adt_lock_check` bazı tiplerde `locked:null` döner → "kilit yok" değil, araç sınırı.
- Genel kural: araç boş dönünce önce aracın kapsamını doğrula.
