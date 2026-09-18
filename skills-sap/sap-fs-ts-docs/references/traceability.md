# İzlenebilirlik, numaralandırma, değişiklik ve veri kaybı kontrolü

## 1. Numara, dosya adı, durum
```
No    : <TİP>-<MODÜL>-<SIRA>          FS-SD-001 ↔ TS-SD-001 ↔ KD-SD-001 = aynı geliştirme
Dosya : <TİP>-<MODÜL>-<SIRA>_<Ad>_v<Sürüm>.md   (PDF/HTML aynı gövde adıyla)
        FS-SD-001_Siparis_Onay_Ekrani_v1.0.md · TS-SD-001_<ANA_OBJE>_v1.0.md · KD-SD-001_Siparis_Kullanici_Kilavuzu_v1.0.md
F1    : DOCU-<MODÜL>-<SIRA>_<Uygulama>_GUI_Yardim.md   (yalnız klasik GUI KD'sinde)
Yer   : <source_root>/<MODÜL>/<PAKET>/docs/     (kaynak/dönüşüm belgeleri ref_docs/ altında; canlı teslimat değil)
```
- İlk `_` öncesi doküman kimliğidir; üretici (Mermaid PNG ön eki) buna dayanır. Aynı klasörde iki doküman aynı kimliği taşımaz.
- **Durum akışı:** `Taslak → İncelemede → Revize Gerekli → Onaylandı → Arşivlendi` (Revize Gerekli → İncelemede döngüsü).
- **Modül kodları:** SD · MM · FI · CO · PP · PM · QM · HR · WM/EWM · PS · BC (temel/modüller arası).

## 2. İzlenebilirlik matrisi (TS'te zorunlu)
| FS gereksinim | FS açıklaması | TS bölümü | TS obje/metot | Test |
|---|---|---|---|---|
| FR-001 | <kısa> | §5.3 | `<SINIF>=>METOT` | UT-001, IT-001 |

- FS'teki **her** FR/KR bir satırdır; boş hücre = eksik TS (İlke 3).
- Kabul kriteri → test bağlantısı ters yönde de kontrol edilir: her test bir kabul kriterine, her kabul kriteri bir teste (DOC-CR-01 ④).
- Matris kaynağa bağlıdır: "N gereksinim karşılandı" yerine "FS §4.1'deki tüm FR'ler" yazılır (DOC-CR-02).
- KD tarafında: FS'teki her kullanıcıya görünen işlev (ekran, buton, mesaj) KD'de bir bölüme karşılık gelir.

## 3. Değişiklik kuralları
- FS değişirse → TS güncellenir → versiyon artar → yeniden onay.
- TS değişirse → FS değişikliği gerekmeyebilir → teknik lider onayı yeter; FS'i etkiliyorsa FS §11-A/§11-B'ye döner.
- Arayüz değişirse → KD aynı revizyonda güncellenir; klasik GUI'de F1 yardımı da.
- Build sırasında yeni mesaj ya da alan doğarsa TS **önce** revize edilir, sonra kodlanır.
- Belgeler proje kapanışına kadar güncel tutulur.

## 4. Karar yayılımı ve ikinci kapı
Bir karar birden çok yerde yaşar (gövde kuralı, ekran tablosu, sözde kod, test, ek belge, onay listesi). Her karar kaydında
**yayılım tablosu** tutulur: `Karar no | Dokunulacak yer | Durum | Kim / ne zaman`. Liste tamamlanmadan karar kapanmış sayılmaz;
boş tablo kayıt geçersizdir. Düzeltme turu **ikinci kapıdan** geçer (`doc-checklist.md` — değişen satırlar, değişen sayı/adın
diğer geçtiği yerler, yayılım listesi; başka taze inceleyici).
Değişen bir sayı/adın eski değeri teslimden önce doküman **genelinde** aranır (`grep` ya da `doc_equivalence_check.py --closed-decision`).

## 5. Yeniden yazımda veri kaybı — `doc_equivalence_check.py`
FS gövdesi temizlenirken (İlke 2b) ya da doküman yeniden düzenlenirken çıkan her bilgi EK'e taşınır; kayıp ölçülür:
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/doc_equivalence_check.py --old ESKI.md --new YENI.md --new EK-KARAR.md \
       [--closed-decision <kapanmış kararın eski değeri> …] [--report RAPOR.md]
```
| Ölçüm | Ne | Geçme koşulu |
|---|---|---|
| 0 Kapsam | taranan dosyalar + aynı klasörde **taranmayan** `.md` uyarısı | paket dosyaları eksiksiz verildi |
| 1 Kimlikler | FR-/BR-/AC-/TC-/SCR-/S-/K… kimlik kümeleri | eski \ yeni = boş |
| 2 Mockup/kod blokları | eski bloğun satırlarının ≥ %90'ı yeni kümede | kayıp blok yok |
| 3 Değerler | BÜYÜK_HARF obje/alan adları, 4+ haneli sayılar, tarihler, `kod` tokenları | eski \ yeni = boş (harf duyarsız) |
| 4 Cümleler | eski her cümle (≥ 40 karakter) yeni kümede bulanık eşleşmeyle | kayıp oranı ≤ eşik (varsayılan %3) |
| 5 Ters yön | `--closed-decision` değeri yeni pakette hâlâ geçiyor mu | geçiş yok ya da her geçiş "reddedilen alternatif" diye açıkça yazılı |

Çıkış: `0` denk · `1` kayıp var ya da kapanmış karar yaşıyor · `2` girdi okunamadı (bu "denk" **değildir**).
Rapor inceleyiciye kanıttır. **Aracın ölçmedikleri** (rapor §6): yeni içeriğin doğruluğu, belgeler arası tutarlılık, korunmuş ama
geçersiz değer (`--closed-decision` verilmezse), kapsam seçimi. Yeşil = "kayıp yok", "doküman doğru" değil.

## 6. Mevcut kaynaktan taslak spesifikasyon — `program_to_spec.py`
Eski ya da mevcut bir ABAP/CDS kaynağından yalnız **kaynakta gerçekten olan** teknik olguları (tablolar, seçim parametreleri,
çağrılan FM/BAPI, FORM/METHOD, ekran numaraları, sınıf/CDS varlıkları) çıkarır; anlatı bölümlerini `<TODO: …>` bırakır.
```
python <TEMPLATE>/skills-sap/sap-fs-ts-docs/scripts/program_to_spec.py <kaynak.abap> [<kaynak2.abap> …] [--out docs/TASLAK_<ad>.md]
```
- Kaynak yerelde yoksa önce `%sap-adt-foundation` ile okunur (`adt_get … include_source=true`); sistemden okunan kaynak taze kabul edilir.
- Çıktı **taslaktır**: `<TODO>`'lar kullanıcı spesifikasyonu ve çalışan uygulama davranışından doldurulur (tahmin yok), sonra
  şablona taşınır ve **spec mutabakatı** yapılır; mutabakatsız build yok.
- Regex tabanlıdır: yorum satırları (`*`) atılır, satır içi `"` yorumları ve makro/dinamik çağrılar ayrıştırılmaz; standart tablo
  listesi "Z/Y ile başlamayan" ipucudur, sistemde varlığı teyit edilir. "Tespit edilemedi" = "yok" değildir.
