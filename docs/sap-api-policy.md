# SAP API Policy — konum beyanı

> **Bu bir hukuki görüş değildir.** Bu belge, bu template'in SAP'ye hangi yüzeyden dokunduğunu ve
> hangi sorunun açık olduğunu kayda geçirir. Bağlayıcı yorum yalnız SAP'den ve kendi sözleşmenizden gelir.
>
> **Son gözden geçirme:** 2026-09-15 · **Dayandığı sürüm:** SAP API Policy v.4.2026a (ikincil kaynaklardan
> okundu; politika metninin kendisi bu template tarafından arşivlenmiyor).

## 1. Neden bu belge var

Bu template SAP'ye **ADT REST uçlarından** (`/sap/bc/adt/*`) bağlanır ve bir modelin planladığı çağrı
dizilerini yürütür. SAP'nin API politikası tam olarak bu deseni adlandıran maddeler içeriyor. Bugün
hiçbir teknik engel yok ve olması da beklenmiyor — konu teknik değil **sözleşmesel**. Bu belgenin amacı,
soru sorulduğunda cevabın hazır olması; araştırmayı o gün baştan yapmamak.

## 2. Politika ne diyor

| Madde | Özet |
|---|---|
| §1.1–1.2 | Yalnız **yayımlanmış** API'ler kullanılabilir (SAP Business Accelerator Hub'da ya da ürün dokümantasyonunda listeli olanlar). Doğrulama yükümlülüğü müşteride ve iş ortağında. |
| §2.2.2 | "API çağrı dizilerini **planlayan, seçen ya da yürüten** (yarı-)otonom veya üretken yapay zekâ sistemleri" ile entegrasyon, SAP'nin onayladığı mimariler dışında kısıtlı. |
| §3 | Proxy, gateway ya da kimlik taklidi ile bu kısıtları dolanmak yasak. |

Politika metni **okuma ile yazmayı ayırmıyor**; **geliştirme ile üretim sistemini de ayırmıyor.**
Yani "biz yalnız okuyoruz" ya da "burası sadece geliştirme sistemi" cümleleri politika metninde
karşılığı olan savunmalar değildir.

## 3. Çözülmemiş olan ne

ADT uçlarının durumu **belirsiz**, ve bu belirsizlik dürüstçe kaydedilmelidir:

- ADT, Business Accelerator Hub'da **yayımlanmış API olarak listeli değil.**
- Ama gizli ya da kapalı da değil: üçüncü parti araçlar on yılı aşkın süredir bu uçların üstüne inşa
  ediyor (ADT köprüsü kullanan git istemcileri, `abap-adt-api`, statik analiz araçları, CI zincirleri).
- **SAP'nin kendi güncel araçları da aynı uçları kullanıyor:** ABAP Development Tools for VS Code ve
  onun içinde dağıtılan ADT MCP Server. SAP'nin geliştirici tarafındaki yapay zekâ asistanı da ABAP
  geliştirmede ajanlı çalışıyor.

Dolayısıyla dürüst konum şudur: **ne açıkça yasaklanmış ne de açıkça serbest bırakılmış.** Bunu ancak
SAP teyit edebilir. Bu belge bir taraf seçmez; belirsizliği ve onunla nasıl yaşadığımızı yazar.

> ⚠ Piyasada bu konuda **"ADT'nin ajanla kullanımı uyumlu değildir"** diye kesin hüküm veren
> yayınlar var. Bu template o hükmü **benimsemez**: politika metninin açıkça söylemediği bir sonucu
> kesinmiş gibi aktarmak, belirsizliği gizlemenin bir başka biçimidir.

## 4. Bu template'in yüzeyi (ölçüldü)

`python skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py --list` → **42 araç: 26 okuma · 16 yazma**
(ölçüm 2026-09-25; `--list` çıktısındaki `counts` alanı).

- **Kaynak kod ve tanım nesneleri** (sınıf, program, DDIC, CDS, RAP) — araçların çoğu burada. Bu,
  geliştirici aracı davranışıdır; iş verisi değildir.
- **İş verisine dokunan iki araç:** `adt_sql_query` (serbest OpenSQL SELECT) ve `adt_table_read`
  (tablo önizleme). **En keskin kenar budur** — yayımlanmamış bir uç üzerinden iş verisine ajanla
  erişim, politikanın yazılma sebebine en yakın duran şeydir.
  Bu iki araç zaten `acknowledge_risk` + `approval_text` onayı ister ve PII/KVKK guard'ına tabidir;
  bu koruma **politika için değil, veri koruması için** konmuştu, ama burada da işe yarar.
- Araç katmanı **kimlik taklidi ya da proxy ile dolanma yapmaz**; bağlantı kullanıcının kendi SAP
  kimliğidir ve sunucu tarafında normal yetki denetimine tabidir (§3 ile ilgili).

## 5. İşletme kuralı

1. **Kendi geliştirme sisteminde** — devam. Bu belgenin bugünkü işe etkisi yoktur.
2. **Müşteriye ait herhangi bir sisteme** (geliştirme dahil) bağlanmadan önce — **yazılı onay** al ve
   müşterinin kendi SAP sözleşmesi açısından bir sakınca olup olmadığını sor.
3. **Üretim sistemi ya da gerçek iş verisi** — ayrıca değerlendir; `adt_sql_query` ve `adt_table_read`
   için tek tek onay. "Yalnız okuyoruz" gerekçe değildir (§2).
4. **Yaygın/ürünleşmiş kullanım** düşünülüyorsa — yaymadan önce SAP'ye sor. Politika bu sorunun
   sorulmasını müşteriden ve iş ortağından bekliyor (§1.2).

## 6. Kapsam beyanı — bu belge neye BAKMAZ

- **Politika metninin kendisi okunmadı.** Maddeler ikincil kaynaklardan derlendi; madde numaraları ve
  özetleri o kaynaklara dayanıyor. Birebir alıntı gerekiyorsa SAP'nin yayınına gidin.
- **Hukuki yorum yok.** "Uyumludur" ya da "uyumlu değildir" hükmü bu belgede **bilinçli olarak yoktur**.
- **Sözleşmeniz okunmadı.** Sizin SAP anlaşmanız bu politikadan farklı hüküm taşıyor olabilir.
- **Diğer yüzeyler kapsam dışı:** SAP GUI scripting, RFC/SOAP kanalı ve OData tüketimi burada
  değerlendirilmedi; yalnız ADT REST yüzeyi ele alındı.
- **Tarih duyarlı.** Politika sürüm alıyor ve SAP'nin kendi araçları bu alanda hızlı değişiyor;
  yukarıdaki "çözülmemiş" tespiti 2026-09-15 itibarıyladır.
