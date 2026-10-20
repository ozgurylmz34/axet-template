# Clean ABAP + OO tasarım — seçilmiş alt küme (stil rehberi, kapı DEĞİL)

> **Kaynak ve atıf:** SAP/styleguides — *Clean ABAP* rehberinden (https://github.com/SAP/styleguides, lisans
> Creative Commons Attribution 3.0) **seçilmiş ve değiştirilmiş** bir alt küme; metin rehberden kopyalanmadı,
> kurallar ekip standartlarıyla çeliştiği yerde ayıklandı (§1) ve daraltıldı. Atıf ve lisans kaydı:
> `THIRD_PARTY_NOTICES.md` §5. Burada yazılı OLMAYAN bir Clean ABAP kuralı bu template'te **bağlayıcı değildir**.
>
> **Profil:** `s4_private` için yazıldı. `ecc`'de UYGULANMAZ (7.40 öncesi sürümde `DATA(...)`, 7.40 SP08 öncesinde
> `xsdbool` sözdizimi hatasıdır). `s4_public` / `btp_abap`'ta ABAP Cloud kuralları platformca zorlanır; bu sayfanın
> ayıklamaları (ALV, klasik dialog) orada anlamsızdır — o profillerde uygulanabilirliği DOĞRULANMADI.

## 0. Kapsam ve öncelik (önce bunu oku)
1. **Yalnız YENİ yazılan ya da bu iş kapsamında DEĞİŞTİRİLEN satıra uygulanır.** Mevcut kodu düzeltme gerekçesi
   DEĞİLDİR: dokunmadığın satırda stil bulgusu açılmaz, "hazır açmışken temizleyeyim" toplu düzenlemesi yapılmaz;
   değiştirdiğin metodun bile yalnız değiştirdiğin satırları bu sayfaya tabidir. (Stil düzeltmesi davranış
   değişikliği riski taşır ve kapsamı işin sahibinden habersiz büyütür.)
2. **Çelişkide mevcut kural üstündür.** Öncelik: SAP kesin yasakları (`core/sap/00-sap.md`) > paket `.rules.md` >
   `coding-patterns.md` · `%sap-classic-abap` · `%sap-rap` referansları > **bu sayfa**. Bu sayfa hiçbir yukarıdaki
   kuralı gevşetmez.
3. **Kapı değildir:** ihlal `%sap-code-review` raporunda `ÖNERİ` düzeyindedir; aynı konu bir kontrol listesi
   satırında daha yüksek önemle varsa o satırın önemi geçerlidir.
4. **Test zorunluluğu eklemez ya da kaldırmaz.** Test yazımı projenin test politikasına tabidir (bazı projeler yeni
   testi açık onaya bağlar); CLN-13 yalnız test yazılan işte uygulanır.

## 1. Ayıklananlar — Clean ABAP önerir, burada GEÇERLİ DEĞİL
| # | Clean ABAP önerisi (özet) | Buradaki kural |
|---|---|---|
| A1 | Hata bildiriminde dönüş kodu değil yalnız istisna | **Daraltıldı:** yeni OO iç mantıkta istisna tercih edilir; ama BAPI/FM/RFC arayüzünde `BAPIRET2`, RAP/EML'de `failed`/`reported` **korunur** — sınırdaki çevirici katman mesajı taşır, yutmaz (`write-api-selection.md`) |
| A2 | Test edilebilirlik için constructor injection / test double varsayılan tasarım | **Alınmadı** — varsayılan tasarım test-double'a göre şekillenmez (§0 madde 4, §3 "Alınmayanlar") |
| A3 | Liste çıktısında `CL_SALV_TABLE` tercihi | **Alınmadı** — ALV aracı senaryoya göre seçilir: `%sap-classic-abap` `references/alv-report.md` §2 + kanonik şablon |
| A4 | Ad ön eki (`lv_`, `lt_`, `gs_` …) kullanmama | **Alınmadı** — ön ekler kullanılır: `coding-patterns.md` §5 "Değişken ve sabit ön ekleri" tablosu (paket `.rules.md` farklı öneki öngörüyorsa o geçerlidir) |
| A5 | `DEFAULT KEY`'den kaçın + tek sonuçta `RETURNING` | **Birlikte yazılır:** `RETURNING` tercih edilir **ama** dönen tablo tipi tam tiplidir (key ifadesi şart — aksi aktivasyon reddi); `WITH EMPTY KEY` seçilirse ölçütsüz `SORT` / `DELETE ADJACENT DUPLICATES` anlamsızdır. Yeni tipte anahtarı bilinçli seç |

## 2. Alınan kurallar (yeni/değişen satır için)
| ID | Kural | Ek şart / tuzak |
|---|---|---|
| **CLN-01** | Mantıksal değer `abap_bool` + `abap_true`/`abap_false`; koşuldan değer üretmek için `xsdbool( )` | — |
| **CLN-02** | Değişkeni ilk kullanıldığı yerde satır içi bildir (`DATA(...)`; release izin veriyorsa `FINAL(...)`) | ⚠ Döngü içinde **sayaç/bayrak/biriktirici** için satır içi bildirim YAZMA. Bildirim konumdan bağımsız bir kez yapılır: `DATA … VALUE` başlangıç değeri yalnız bir kez atanır, `INTO DATA(...)` hedefi bulunamayan kayıtta önceki turun değerini taşır (`checklist-abap.md`: döngü içi `DATA` biriktirici). Açık atama (`DATA(lv_x) = 0.`) her turda çalışır; yine de sayaç/biriktiricinin yeri döngünün dışıdır, okunurluk için orada bildir |
| **CLN-03** | Tek sonuç → `RETURNING`; az sayıda `IMPORTING`; davranışı ikiye ayıran mantıksal giriş parametresi yerine iki metot | `RETURNING` tipi tam tipli (A5). Biriktirilen tabloyu `EXPORTING` ile döndürme — çağrıda hedef tablo boşalır (`checklist-abap.md`: `EXPORTING et_msg`) |
| **CLN-04** | Sihirli sayı/dize yerine sabit | Zaten ekip kuralı: `coding-patterns.md` §5 "Değişken ve sabit ön ekleri" |
| **CLN-05** | Koşulu olumlu yaz; `IS NOT` biçimi; erken `RETURN` ile koruma cümlesi; tek değişken üzerindeki uzun `ELSEIF` zinciri yerine `CASE` | — |
| **CLN-06** | Tablo türünü erişim desenine göre seç (STANDARD/SORTED/HASHED); varlık sorgusu `line_exists( )`; SORTED/HASHED'e `INSERT … INTO TABLE` | A5 · `FOR ALL ENTRIES` öncesi boş tablo kontrolü: `coding-patterns.md` §3 |
| **CLN-07** | Dize birleştirmede şablon `\|…\|`; teknik literal için backtick | Kullanıcıya görünen metin literal DEĞİL: metin havuzu / mesaj sınıfı (`%sap-classic-abap`). Şablonda kaçışsız `\|` kaydetme reddi verir (`checklist-abap.md`) |
| **CLN-08** | Yorum **neden**i anlatır; yorum satırına alınmış kod silinir (tarih git'te) | Yorumun KONUMU SAP kaydetme kuralına tabidir — yetim yorum reddi: `%sap-classic-abap` `references/classes.md` §3 |
| **CLN-09** | Metot tek iş yapar, kısa ve tek soyutlama düzeyindedir | Büyüklük sezgisi §3 OO-2 |
| **CLN-10** | Modern ifadeler (`VALUE`, `CORRESPONDING`, `COND`, `SWITCH`, `FOR`, `REDUCE`) eski deyimlere tercih edilir; eskimiş deyim (`MOVE … TO`, `COMPUTE`, statik `CALL METHOD`) yeni satırda yazılmaz | ⚠ EML/kaynak tabanlı sınıfta abaplint modern sözdizimini tam okuyamayabilir → kesin karar push/aktivasyondur (`%sap-code-review` `references/abaplint.md`). Hesaplı alt dize uzunluğu, `PERFORM … USING` aktüelinde ifade, NUMC'ye karakter literali: `checklist-abap.md`. Klasik dialogda `FORM` kullanımı `%sap-classic-abap`'a tabidir |
| **CLN-11** | Düzenli ifadeden önce yerleşik dize fonksiyonları | PCRE deseninde çıplak boşluk sessizce 0 sonuç verir (`checklist-abap.md`) |
| **CLN-12** | Durum taşıyan iş için statik sınıf yerine örnek (instance) metodu; üyeler varsayılan `PRIVATE` | §3 OO-1 |
| **CLN-13** | *(Test yazılan işte)* test metodu adı davranışı söyler; düzen **verilen–yapılan–beklenen**; yalnız açık (public) davranış test edilir | Aktivasyon sonrası ilk koşuda sahte "0 test" görülebilir — beklenen test sayısı rapora yazılır |

**Otomatik kontrollerin karşılığı:** ATC öncelik 1 zorunlu (`%sap-code-review` `references/clean-core.md` §5) ·
`abaplint_run.py` (`%sap-code-review`) · sunucu tarafı biçimlendirme `adt_pretty_print` (`%sap-classic-abap`
`references/classes.md` §7). "0 bulgu" yalnız aracın baktığı yüzeyde temizliktir — bu sayfanın kurallarının çoğunu
hiçbir araç ölçmez.

## 3. OO tasarım alt kümesi
| ID | Kural | Not |
|---|---|---|
| **OO-1** | Sınıf varsayılan `FINAL`; kalıtım yerine **bileşim** (sınıf içinde başka sınıfın örneği) | Kalıtıma açık sınıf bilinçli bir tasarım kararıdır — TS'te gerekçesi yazılır |
| **OO-2** | Tek sorumluluk. "Her şeyi bilen sınıf" sezgisi: ~5'ten çok açık metot ya da ~800 satırı aşan sınıf **tartışma sinyalidir**, sınır değildir | Ortak (paylaşılan) sınıfları şişirme |
| **OO-3** | **YAGNI** — desen ihtiyaç doğmadan uygulanmaz; varsayılan cevap "uygulama"dır (aşağıdaki tablo) | Önce şablon, soyutlama sonra |
| **OO-4** | Arayüz önce (açık API'yi `IF_`/`ZIF_` arkasına koymak) **yalnız birden çok tüketicisi olan global ortak sınıflarda** önerilir | Klasik programın lokal sınıflarına (`LCL_*`) dayatılmaz |

**Desen ne zaman uygulanır — varsayılan "UYGULAMA":**

| Desen | Uygula, eğer… | Uygulama, eğer… |
|---|---|---|
| Factory | yaratılacak sınıf çalışma anında birden çok somut türden seçiliyorsa | tek somut tür var ve öngörülebilir ikinci tür yoksa |
| Strategy | aynı işin **bugün** ikiden çok değişkeni var ve seçim veriyle yapılıyorsa | tek `CASE` dalı yeterliyse (paket `.rules.md` dal/metot düzeni öngörüyorsa o geçerlidir) |
| Observer | bir olayın birden çok, birbirini bilmeyen dinleyicisi varsa | tek dinleyici varsa — doğrudan çağrı |
| Adapter | dış arayüz (BAPI/RFC/OData) iç modele çevrilecekse — sarmalayıcı sınıf | çağrı tek yerde ve çeviri yoksa |
| Decorator | davranışa çalışma anında katman eklenmesi gerçekten gerekiyorsa | ek davranış sabitse — doğrudan metot |

**Alınmayanlar (bilinçli):** test izolasyonu için constructor injection, `CREATE PRIVATE` + fabrika ve test double
(`cl_abap_testdouble`) **varsayılan tasarım olarak** alınmadı (§1 A2). Somut bir test gereksinimi doğarsa o iş
kapsamında ayrıca değerlendirilir.

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynak: ekip çekirdeğinin Clean ABAP alt küme standardı + `.abap` kısa işaretçi kuralı (ikisi tek dosyada birleşti).
- Kontrol listesi kimlikleri metne yazılmadı; tuzaklar `checklist-abap.md`'deki satırın konusuyla anıldı.
- Ekip ADR ve standart numaraları aXet'teki karşılık dosyalarla değiştirildi.
