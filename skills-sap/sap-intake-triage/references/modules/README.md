# Modül paketleri

## Bugün ne var
| Modül | Dosya | Durum |
|---|---|---|
| SD (Satış ve Dağıtım) | `sd.md` | aktif |

**Başka modül paketi YOKTUR** (MM, FI, CO, PP, QM, PM, WM/EWM …).

## Paket yoksa
- Paket **UYDURULMAZ** — ne dosya olarak ne de "MM paketine göre şunlar kontrol edilir" diye sohbette. Olmayan bir kontrol
  listesine dayanmak, listesiz çalışmaktan kötüdür (yanlış güven).
- Genel protokolle ilerle (`../protocol.md`): sınıfla → isterlerden konu çıkar → 3 eksende araştır → kanıtlı değerlendir.
  Modüle özgü kontrol ve soruları o işin **kanıtından** türet ve "genel protokolle türetildi, modül paketi yok" diye belirt.
- İş bitince tekrar kullanılabilir bir ders çıktıysa yeni paket önerisi sun (aşağıdaki biçim).

## Yeni paket nasıl yazılır
- Dosya adı: modül kodu küçük harfle (`mm.md`, `fi.md`, `ewm.md`).
- Paket **bilgi deposu değildir**: domain olgusu gömülmez (eskir, yanıltır). Yalnız *nereye bakılır, ne kontrol edilir, ne sorulur*.
- `sd.md` ile aynı bölümler, aynı sırada:
  1. **Başlık notu** — ne bu / ne değil / nasıl büyür.
  2. **ZORUNLU KONTROL** tablosu — `<MOD>-K1…`: kontrol + dayandığı kural (kesin yasak, clean core, LUW …).
  3. **TETİK HARİTASI** — `T-<MOD>-n · "<ister ifadeleri>" → <DOMAIN KONUSU>`; her tetikte **ARAŞTIR** · **MEVCUT SİSTEMDE BAK** (reuse
     edilecek desen) · **TUZAK** (ölçülmüş hata; checklist kimliği varsa yanında kısa anlamı) · gerekiyorsa **SORU** / **FORMÜL DERSİ**.
  4. **SORULACAK** — numaralı, her soru neden önemli olduğuyla.
  5. **KAYNAK İŞARETÇİSİ** — domain / canlı sistem / proje kuralı / prior-art / teknik tip.
  6. **ÇIKARILAN DERSLER** — modüle özgü, satır satır büyür.
- Her tuzak satırı **gerçekten yaşanmış ve kanıtlı** olmalı; varsayım ya da "olabilir" satırı eklenmez.
- Standart SAP nesne adları (tablo, CDS, BAPI) aynen yazılır; müşteri/proje Z obje adları, kişi, firma, sistem adı yazılmaz
  (`Z<MOD>_…`, `ZDEMO_…` gibi nötr örnek kullanılır).
- Template seviyesindeki paket commit/PR ile girer (`%write-skill`, `%commit-pr`); yalnız bir projeye özgüyse proje hafızasına yazılır.
- Paketi ekledikten sonra bu README'deki tabloyu güncelle.
