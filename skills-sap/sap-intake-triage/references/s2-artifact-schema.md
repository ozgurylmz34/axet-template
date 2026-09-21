# S2 intake artefaktı — şema, doldurma kuralları, mutabakat işareti

> Yer: proje kökünde `.axet-code/intake/<id>.md`. Boş şablon: `templates/intake-artifact.md`.
> Bu biçim, S2 kontrol script'inin (`scripts/check_intake_signoff.py`; alan adları değiştirilmeden kaynak ekip ortamındaki
> intake kapısından uyarlandı) **aradığı** biçimden türetildi ve script'e karşı ölçüldü (boş şablon → çıkış 1 ·
> doldurulmuş ama işaretsiz → 1 · doldurulmuş + işaretli → 0). Aşağıdaki "script ne arar" satırları o script'in desenlerinin
> açıklamasıdır. Script değişirse bu dosya script'e göre güncellenir.

## Kimlik (`<id>`)
Öneri: `YYYYMMDD-<kisa-ad>` (küçük harf, tire; ör. `20260913-siparis-kalem-raporu`). Ne script ne yazma kapısı dosya adını
denetler; kapı yalnız yolu denetler: proje-göreli, `.axet-code/intake/` altında, `.md`, dosya mevcut (aşağıda "Kontrolü çalıştırma").

## Şema — 8 alan (sabit)

```
# INTAKE — <kısa-ad>  (<tarih>)
- Modül / iş-tipi / KAPSAM: <modül> / <iş tipi> / S2  (gerekçe: <tek cümle>)
- İstenen (özet): <kullanıcının talebi, kendi cümlelerinle>
- Çıkan domain-konuları: <konu → araştırma özeti (a) domain / (b) canlı sistem / (c) hafıza>
- Etkilenen objeler (canlı-doğrulanmış): <obje → reuse | yeni | değişir → blast-radius → doğrulama kanıtı>
- Prior-art: <bulundu: `<yol ya da kayıt>`  |  yok (arandı: <nerede>)>
- Kabul kriterleri (EARS): <"<olay> olduğunda sistem <sonuç> yapmalı" …>
- Açık kararlar / riskler: <karar bekleyenler, riskler>
- MUTABAKAT: [ ] kullanıcı sign-off
```

| # | Alan | Script zorunlu mu | Doldurma kuralı |
|---|---|---|---|
| 1 | Modül / iş-tipi / **KAPSAM** | ✅ (`kapsam:` + değer dolu) | Sınıf + bir cümle gerekçe. `KAPSAM` kelimesinden sonra **iki nokta şart** |
| 2 | İstenen (özet) | — | Talep; varsayım eklenmez |
| 3 | Çıkan domain-konuları | — | Her konu için üç eksenin kısa özeti |
| 4 | **Etkilenen objeler** (canlı-doğrulanmış) | ✅ (başlık + değer dolu) | Her obje: ad · reuse/yeni/değişir · tüketiciler · kanıt (araç + argüman). Hafızadan gelen obje canlı doğrulanmadan yazılmaz (manuel kontrol) |
| 5 | **Prior-art** | ✅ (değer dolu + kabul edilen biçim) | Arayıp bulduğun şeyin izi ya da açık olumsuz — aşağıdaki kurallar |
| 6 | **Kabul kriterleri** (EARS) | ✅ (başlık + değer dolu) | Test edilebilir EARS cümleleri (manuel kontrol: uyarı) |
| 7 | Açık kararlar / riskler | — | Karar bekleyen her madde; yoksa "yok" |
| 8 | **MUTABAKAT** | ✅ (işaretli) | Kullanıcı onayından sonra işaretlenir |

**Ek bölümler (şablonda var, script bakmaz — manuel kontrol; kurallar `protocol.md` §6 S2 adım 1):** Sistem sürümü ·
Etkilenen objeler altındaki ad/canlı kontrol/`ONAY: [ ]` tablosu · Tablo yönetim alanları · Kural taraması · Öz-tutarlılık.
Tablo satırları (`|` ile başlayan) alan değerine katılmaz; zorunlu alanın **ilk satırı** yine doldurulmalıdır.
⚠ Bu bölümlerdeki kutulara (`[ ]`) `mutabakat` ya da `sign-off` kelimesi yazma: o satırda `[x]` olursa script onu kullanıcı
onayı sayar.

## Script ne arar
Tüm kontroller koşar ve **bütün bulgular birlikte**, adlarıyla raporlanır (kaynak kapı ilk bulguda duruyordu; aXet script'i
durmaz). Herhangi bir bulgu = çıkış 1. İstisna: dosya yoksa yalnız o bulgu döner; prior-art biçimi yalnız alan varsa ve doluysa denetlenir.
1. **Dosya var mı.**
2. **Başlık varlığı** (tüm metinde, büyük/küçük harf duyarsız):
   - `kapsam` + boşluk + `:` → `kapsam\s*:` **ya da** `KAPSAM` kelimesi geçen bir markdown başlığı (`## 1. KAPSAM`)
   - `etkilenen` + (satır ve `:` aşmayan en fazla 24 karakter) + `obje` → "Etkilenen objeler", "ETKİLENEN / İLGİLİ OBJELER" geçerli
   - `prior-art` ya da `priorart`
   - `kabul` + boşluk + `kriter`
3. **Değer doluluğu** — değer iki biçimden biriyle okunur:
   - **Satır biçimi (önce denenir):** `Alan: değer`. Değer = aynı satırda `:`'dan sonrası + devam satırları; devam boş satırda ya da
     yeni madde (`- `, `* `, `+ `), başlık (`#`), kod çiti (```` ``` ````) veya tablo satırı (`|`) ile biter.
     ⚠ **İlk eşleşen satır kazanır:** artefaktın üst kısmında (açıklama, not) `Kapsam: …`, `Prior-art: …` gibi bir satır varsa
     alanın değeri o satırdan okunur. Açıklama satırlarında bu kelimeleri iki noktayla yazma.
   - **Başlık biçimi (satır biçimi yoksa):** `## 3. ETKİLENEN OBJELER` → değer, bir sonraki **aynı ya da üst seviye** başlığa kadarki
     blok; başlık satırının kendisi değere dahil değildir. (Kaynak kapıda KAPSAM yalnız `KAPSAM:` biçiminde tanınıyordu;
     aXet script'i başlık biçimini de kabul eder. Karışıklık olmasın diye şablondaki `KAPSAM:` satır biçimini kullan.)
   - **Boş sayılan:** harf/rakam içermeyen değer (`—`, `[ ]`, `...`) ya da şablonun kendi yer tutucusu (boşluklar tekleştirilip küçük harfle
     **birebir** karşılaştırılır): `sd / rapor / s2 (gerekçe: ...)` · `[obje → reuse/yeni/değişir → blast-radius]` ·
     `[obje -> reuse/yeni/degisir -> blast-radius]` · `[bulundu: <ref> / yok]` ·
     `"<olay> olduğunda sistem <sonuç> yapmalı" / "<durum> ise ..."` · `[konu → araştırma özeti (a/b/c eksen)]`.
     **Açılı parantezli yer tutucu** da boş sayılır (aXet eki): değerde boşlukla başlamayıp bitmeyen tek bir `<…>`
     (ör. `<modül>`, `<tek cümle>`, `<nerede>`) kalmışsa alan doldurulmamıştır. ⚠ Gerçek içerikte de bu biçimden kaçın:
     `<EntityType>` gibi bir XML etiket adı yazacaksan backtick yerine düz ad kullan (`EntityType`); karşılaştırma işleci
     (`a <> b`, `a < b`) etkilenmez.
     Hafifçe düzenlenmiş yer tutucu **geçer** — kontrol "boş şablon"u yakalar, "kötü içerik"i değil.
4. **Prior-art biçimi** — değer ya:
   - **açık olumsuz** içerir: `yok`, `yoktur`, `none`, `bulunamadı`, `not found`; ya da
   - **referans izi** içerir: backtick'li metin (`` `…` ``) · uzantılı dosya adı (`.md .abap .cds .py .json .yaml .yml .txt .pdf`) ·
     `ADR|KAYIT|PR|core` + numara · URL · `a/b` biçiminde yol · `bulundu` / `found`.
   - Düzyazı bir cümle ("benzer bir iş yapmıştık") **geçmez**.
   - ⚠ Tolerans kanıt değildir: `a/b` deseni `S1/S2` gibi herhangi bir eğik çizgiyi de iz sayar. Kurala "geçmek" için değil,
     aradığını ve bulduğunu göstermek için yaz.
5. **Mutabakat işareti:** tek bir satırda `mutabakat` ile `[x]`/`[X]` birlikte (hangi sırada olursa) ya da `sign-off` sonrası `[x]`.
   - İşaretsiz: `MUTABAKAT: [ ] …` → "satır var ama işaretsiz".
   - ⚠ Aynı satırda açıklama olarak `[x]` yazmak (ör. "onaylanınca [x] yap") da işaret sayılır → talimatı o satıra yazma.

Başarı çıktısı: `✓ INTAKE S2 SIGNOFF: intake artefaktı tam + MUTABAKAT işaretli (dosya adı)`, çıkış 0.
Başarısızlıkta stderr: `⛔ INTAKE S2 SIGNOFF: artefakt kapıdan geçmedi.` + her bulgu ayrı satırda + eksik başlıkların denenen desenleri.

## Mutabakat işaretinin biçimi
```
- MUTABAKAT: [x] kullanıcı sign-off — <tarih> · onay: "<kullanıcının onay mesajından kısa alıntı>"
```
- Script yalnız `mutabakat` + `[x]`'i arar; tarih ve onay alıntısı aXet uyarlamasıdır (kimin, ne zaman, neyi onayladığının izi) —
  script bunları kontrol etmez.
- İşareti **model kendi kararıyla koymaz.** Sıra: artefaktı kullanıcıya göster → madde madde mutabakat (değişiklikler artefakta işlenir)
  → kullanıcı açıkça onaylar ("onaylıyorum", "tamam, mutabıkız") → işareti koy.
- Mutabakattan sonra kapsam, etkilenen obje ya da kabul kriteri değişirse işareti `[ ]`'e geri al, değişikliği göster, yeniden onay al.

## Kontrolü çalıştırma
```
python <TEMPLATE>/skills-sap/sap-intake-triage/scripts/check_intake_signoff.py .axet-code/intake/<id>.md
```
(Tek konumsal argüman: artefakt yolu. Çıkış 0 temiz · 1 bulgu.)
Çıkış 1 ise stderr'deki mesaj eksik alanı ve denenen deseni söyler; artefaktı düzelt, işareti koymak için kontrolü "geçirmeye"
çalışma.

**Yazma CLI'si S2 beyanında** aynı denetimi içeriden çağırır; ek olarak yolu denetler. Red kodu `intake_missing` ya da
`intake_invalid`, çıkış 2:
- `--intake` verilmedi → `intake_missing`
- yol mutlak → `intake_invalid` (proje-göreli olmalı)
- `.axet-code/intake/` altında değil ya da `.md` değil ya da dosya yok → `intake_invalid`
- artefakt denetimden geçmedi → `intake_invalid` + bulgular
- denetleyici koşamadı → `intake_invalid` (fail-closed)

## Manuel kontroller (script bakmaz)
| Kontrol | Önem |
|---|---|
| Etkilenen Z objeler canlı doğrulandı mı (hafıza hipotezi değil)? Her obje için araç çıktısı referansı var mı? | engelleyici |
| Kabul kriterleri EARS kalıbında ve test edilebilir mi? | uyarı |
| Her yeni Z obje adı canlıda kontrol edildi ve `ONAY` kutusu kullanıcı onayıyla işaretli mi? | engelleyici |
| Kural taraması dolu mu; sapan her karar kullanıcıya soruldu mu? | engelleyici |
| Sistem sürümü karşılaştırıldı mı (fark / okunamadı → soruldu)? | uyarı |
| Öz-tutarlılık: riskler ve kabul kriterleri son kararlarla uyumlu mu? | engelleyici |

## Script'in kapsam beyanı (neye bakmaz)
İçeriğin doğruluğu · objelerin gerçekten canlı doğrulandığı · EARS kalitesi · mutabakatın gerçekten kullanıcıdan geldiği ·
hangi işin S2 olduğu (bunu model sınıflar, kullanıcı görür). "Script geçti" = "artefakt üretilmiş ve işaretli", "iş doğru tanımlanmış" değil.
