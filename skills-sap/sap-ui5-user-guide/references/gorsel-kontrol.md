# Görsel kontrol — her kareye bak

> **Neden:** `capture_kd_screens.js`'in "OK"u yalnız "adım koştu, dosya yazıldı" demektir. Boş bir liste, dönen bir
> meşgul göstergesi ya da İngilizce bir düğme de "OK" çekimdir. Kullanıcıya giden hata çoğunlukla buradan geçer.
> `assert_*` adımları bir kısmını çekim anında yakalar; geri kalanı ancak görüntüye bakarak görülür.

## Yöntem
1. Her PNG'yi `view` aracıyla aç (toplu bakma yok: kare başına bir çağrı). Modelin "baktım" beyanı değil, `view`
   çağrısının kendisi kanıttır.
2. Aşağıdaki listeyi kare kare uygula; sonucu `docs/kd-gorsel-kontrol.md` tablosuna yaz:

   | Kare | Bakıldı | Bulgu (madde no) | Yapılacak | Tekrar çekimden sonra |
   |---|---|---|---|---|

3. Bulgu varsa düzelt → yalnız etkilenen kareleri değil **senaryoyu baştan** koş (bir düzeltme başka kareyi bozabilir)
   → değişen karelere tekrar bak.
4. Tablo tamamlanmadan adım 7'ye (yazım) geçilmez.

## Kontrol listesi
| # | Kontrol | Nasıl görünür | Yapılacak |
|---|---|---|---|
| G1 | **Boş liste / boş tablo** | "Veri yok", boş grid, sıfır satır sayacı | mock verisi eksik ya da yanlış dosya adı (`mock-ortam.md` §4); filtre varsayılanı veriyi dışlıyor olabilir. Senaryoya `assert_text` ile bilinen bir değer ekle |
| G2 | **Meşgul göstergesi** | dönen halka, gri örtü, iskelet satırlar | `assert_no_busy` ekle; `wait_ui5` sonrası `wait` ile kısa bekleme |
| G3 | **İngilizce metin** | "Go", "Create", "Adapt Filters", İngilizce tarih biçimi | URL'de `?sap-ui-language=tr` var mı; `i18n_tr.properties` eksikse bu uygulama kusurudur → kullanıcıya bildir, kılavuzda örtme |
| G4 | **Kesik diyalog / açılır pencere** | diyaloğun kenarı, alt düğme çubuğu ya da açılır listenin sonu kadrajda yok | `assert_in_viewport`; viewport'u büyüt ya da öğe seçicili `shot` al |
| G5 | **Anlamsız ya da tutarsız mock verisi** | "Sample Text", "Item 1", `0000000001`; toplam ≠ kalemlerin toplamı; başlıktaki müşteri ile kalemdeki müşteri farklı; tarih sırası ters | `generateMockData`'nın ürettiği genel değerler kareye girmiş → o varlık için `mock_veri.py` çıktısını kullan ya da elle düzelt; ilişkili alanları eşle |
| G6 | **Kişisel veri görünümü** | gerçek kişi adı, e-posta, telefon, IBAN, vergi no gibi görünen değer — kurgusal olsa bile gerçek sanılabilecek biçimde | değeri açıkça kurgusal olanla değiştir ("Örnek Müşteri A.Ş.", e-postada `example.invalid` alan adı); kullanıcı adı / oturum bilgisi görünüyorsa kadrajdan çıkar |
| G7 | **Gereksiz beyaz alan** | kadrajın büyük kısmı boş | `build_kd_pdf.py --trim-from` kırpar; öğe seçicili `shot` tercih et |
| G8 | **Hata / uyarı mesajı** | kırmızı mesaj şeridi, hata diyaloğu, "Servis kullanılamıyor" | mock'ta olmayan fonksiyon/aksiyon çağrısı; kılavuzda anlatılan bir hata değilse diyaloğu kapat ve durumu model verisi enjeksiyonuyla kur (`%sap-fs-ts-docs` → `references/pdf-with-screenshots.md` §A) |
| G9 | **Yanlış uygulama / yanlış ekran** | başka uygulamanın başlığı, beklenmeyen ekran | paralel mock / port kayması: `expect_port` + `eval "location.port"` (`tuzaklar.md` T4) |
| G10 | **Durum tutarlılığı** | aç/kapa alanının yalnız bir durumu çekilmiş; seçili satır vurgusu yok | iki durum ayrı kare; seçim gerekiyorsa senaryoda seçim adımı |
| G11 | **Gezinme izleri** | fare imleci, odak çerçevesi, yarım kalmış tooltip | çekimden önce odağı başka yere al ya da `wait` ile tooltip'in kapanmasını bekle |

## Sınırlar
- Bu liste görüntünün **kılavuza uygunluğunu** denetler; kılavuz metninin doğruluğu ve alt ekran kapsamı
  `%sap-fs-ts-docs` → `references/doc-checklist.md` §A (DOC-KD-01, DOC-KD-03) ile ayrıca denetlenir.
- Görüntüdeki metni modelin okuması OCR değildir: küçük yazıda yanlış okuma olabilir. Kritik bir değer (tutar, belge
  no) kılavuz metnine yazılacaksa mock verisi dosyasından alınır, görüntüden okunmaz.
