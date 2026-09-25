# Clean core — released CDS/API tercihi, politika, ATC ve halef haritası

> **Kaynak:** ekip SAP profil matrisi (politika ekseni), adlandırma standardındaki clean core seviye tablosu, clean core
> dersleri ("released CDS proaktif", "ATC öncelik 1 zorunlu", fail-open harita vakası), yazma kapısı validator'ının
> kodu ve bu skill'deki ölçümler. İnceleme satırları: `checklist-clean-core.md`. Standart obje → released karşılık
> örnekleri: `%sap-dev` references/coding-patterns.md §7 (burada tekrarlanmaz).

## 1. Profil ve politika — önem buradan gelir
Proje kimliği `sap-project.json`'dadır (`sap_profile`, `cleancore_policy`).

| Profil | Released CDS/API | Clean core satırlarının önemi |
|---|---|---|
| `ecc` | kavram yok | uygulanmaz |
| `s4_private` | tercih edilir, zorunlu değil | `cleancore_policy`'ye göre (aşağıda) |
| `s4_public` | zorunlu; derleyici/çalışma zamanı reddeder | satırlar erken yakalama içindir; ihlal zaten yazılamaz |
| `btp_abap` | zorunlu; S/4 verisine yalnız uzak released API | aynı |

`s4_private` politika ekseni:

| `cleancore_policy` | Anlamı | İncelemede |
|---|---|---|
| `strict` | Yalnız released API; yeni klasik Dynpro politika gereği yasak | `WARNING · strict: BLOCKER` satırları BLOCKER; CC-02 uygulanır |
| `balanced` | Profil varsayılanı: released tercih, klasik meşru | WARNING; released kullanılmayacaksa gerekçe kullanıcıya bildirilir (sessiz geçiş yok) |
| `classic` | RAP tercih baskısı kalkar; released tercihi değişmez | `balanced` ile aynı önem |
| boş / tanımsız değer | Ölçülemez | önem DOĞRULANMADI, kullanıcıya sor |

Not: CLI `cleancore_policy`'yi yalnız metin olarak doğrular (`sap-adt-foundation` `project.py`); yazım hatası sessizce
"tanımsız" olur → incelemede boş gibi ele al.

## 2. Clean core seviyeleri (SAP genişletme modeli)
| Seviye | Ne | Örnek |
|---|---|---|
| A | ABAP Cloud ile sistem içinde ya da BTP'de yan yana; yalnız released API | RAP, released CDS, released sınıf/BAdI |
| B | SAP önerilerine uyan klasik ABAP ve klasik API'ler | klasik program, SAP'nin klasik API sınıflandırması |
| C | SAP iç objelerine dayanır; yükseltme öncesi kontrol gerekir | released olmayan standart tablo/sınıf/FM okuma |
| D | Modifikasyon, önerilmeyen obje, implicit enhancement | standart kod değişikliği (kesin yasak A zaten engeller) |

İnceleme raporunda yeni objenin seviyesi A değilse gerekçesiyle yazılır. D daima BLOCKER'dır (kesin yasak A).

## 3. Karar akışı — standart obje okunacaksa
1. **Yazma mı?** Bu okuma akışı değil: kesin yasak B — released API (released RAP BO/EML · released BAPI · released OData) →
   BAPI → RFC FM → BDC → kullanıcıdan manuel; hangi yol ve hangi canlı teyitle: `%sap-dev` → `write-api-selection.md` (BE-79).
2. **Halef var mı?** `released_successors.py lookup <OBJE>`. "Haritada yok" released demek değildir (§4).
3. **Halef adını ve alanlarını tahmin etme:** `adt_search_objects` ile bul, `adt_get` ile oku; kullanılan her alan adını
   halef kaynağında doğrula (BE-25).
4. **Yetki kontrolü:** halefin `@AccessControl.authorizationCheck` değerini canlı oku. `#CHECK` halef bir kontrolü/guard'ı
   besliyorsa yetki reddi hata değil 0 satır döner → kontrol fail-open (BE-68; `%sap-cds-ddic` cds.md CDS-DCL-01/02).
5. **Halef işi yapamıyorsa** (eksik alan, eksik ilişki) standart tabloya düş ve gerekçeyi kullanıcıya bildir.
6. **Kullanıcı "şu tabloyu kullan" dediyse** çoğunlukla veriyi kasteder, released karşılığı yasaklamaz: halef varsa onu kullan,
   yapamıyorsa 5. adım.
7. **Birim semantiği tuzağı:** released görünümlerde birim çevrim alanları `@Semantics.quantity` taşıyabilir; aritmetik ya
   da `case` içinde doğrudan kullanım "UNIT-reference" aktivasyon hatası verir → önce `cast( … as abap.dec(n,m) )`.
8. **Sınıf, arayüz, FM:** tablo haritası yalnız ipucudur; otorite ATC "Usage of APIs" (§5, CC-01).
9. **Eski kod:** mevcut koddaki ham tablo tek başına bulgu değildir (envanter); migrasyon proje kararıdır.

## 4. Otomasyon — neyi yakalar, neyi kaçırır
Yazma kapısı validator'ı `check_released_objects.py` (`<skills-sap>/sap-adt-foundation/scripts/sapadt/lib/validators/`):
- Zincirler: `cds_creation`, `cds_update`, `rap_cds_creation`, `class_push`; önem WARNING (bloklamaz). Kendi `--strict`
  bayrağı bilinçli olarak etkisizdir; `run_review --strict` ise tüm WARNING'leri BLOCKER karara çevirir.
- Yalnız haritanın `tables` bölümünü okur; `classes`/`functions`/`interfaces` kullanılmaz.
- Satır bazlı `from|join <ad>` araması; `//`, `*` ya da `"` ile başlayan satırı atlar.

Ölçülmüş sınırlar (`tests/test_released_successors.py` bunları çalıştırarak doğrular):
| Durum | Sonuç |
|---|---|
| `from` bir satırda, tablo adı sonraki satırda | kaçırır |
| `association … to <tablo>` | kaçırır |
| `"` ile başlayan ABAP yorum satırı | atlar (doğru) |
| `/* … from <tablo> … */` blok yorum | bulgu verir (yanlış pozitif) |
| Harita dosyası yok ya da boş | `SKIP` + durum satırı `status=SKIPPED measured=false` basar, çıkış 0 → `run_review` SKIP (WARNING) sayar; 2026-09-14 öncesi durum satırı yoktu ve PASS sayılıyordu |

Son satır nedeniyle CC-03 vardır: `released_successors.py status` haritayı doğrular (yok/boş/bozuk → çıkış 2).
Yazma kapısının bu durumu ölçmeden geçmesi foundation tarafında açık bir kalemdir (kapıya dokunulmadı).

## 5. ATC — tüm obje tipleri için otorite
```
python <TEMPLATE>/skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py adt_atc_check --args-json '{"name":"<OBJE>","object_type":"class"}' --project-dir <PROJE_KÖKÜ>
```
- Okuma sınıfı araç; varyant verilmezse bağlantı ayarındaki varyant, o da yoksa `DEFAULT` (`%sap-adt-foundation`
  foundation-query.md §4). `object_type` değerleri: `sap_adt_cli.py --list`.
- ATC yalnız sistemde derlenmiş obje üzerinde koşar: push/aktivasyon öncesi yerel dosya için sonuç yoktur.
- Öncelik 1 bulgu kapatılır; öncelik 2/3 yalnız açık kullanıcı onayıyla geçer. Sessiz geçiş yok.
- ATC koşamadıysa raporda "ATC temiz" yazılmaz: DOĞRULANMADI.

## 6. Halef haritası — konum, şema, yenileme
**Konum (tek kaynak):** `<skills-sap>/sap-adt-foundation/scripts/sapadt/lib/data/released_successors.json`.
Yazma kapısı validator'ı ve `released_successors.py` aynı dosyayı okur (eşitliğini test zorlar).

**Şema:**
```json
{
 "_meta": {"generated": "YYYY-MM-DD", "source": "…", "counts": {"tables": 0}},
 "tables":     {"MARA": {"successors": ["I_PRODUCT", "…"], "state": "notToBeReleased",
                         "classification": "multipleObjects", "app": "LO-MD-MM"}},
 "classes": {}, "functions": {}, "interfaces": {}
}
```
Bölüm = TADIR obje tipi (TABL → tables · CLAS → classes · FUGR/FUNC → functions · INTF → interfaces). Alınan durumlar:
`notToBeReleased`, `deprecated`, `released_with_restrictions`, yalnız halefi olan kayıtlar. Harita "released olmayan ve
halefi olan" objelerin listesidir; bir objenin burada olmaması released olduğunu göstermez.

Dağıtılan harita (ölçüm 2026-09-13): üretim 2026-07-26 · tables 261 · classes 24 · functions 258 · interfaces 16.

**Ne zaman yenilenir:** 90 günden eskiyse (`status` çıkış 1) ya da S/4 sürüm yükseltmesinden sonra (script yükseltme
tarihini bilemez → kullanıcıya sor).

**Nasıl (ağ erişimi script'te yok):**
1. Kullanıcı SAP'nin açık reposundan (`https://github.com/SAP/abap-atc-cr-cv-s4hc`, `src/` klasörü) on-premise / Private
   Cloud için `objectReleaseInfo_PCELatest.json` dosyasını tarayıcıyla indirir.
2. `python <TEMPLATE>/skills-sap/sap-code-review/scripts/released_successors.py refresh --source <dosya> --dry-run` → sayılar.
3. Sayılar makulse `--dry-run` olmadan koş. Script yazdığı dosyayı geri okuyup doğrular.
4. `released_successors.py status` → TAZE.
5. `python -m unittest discover -s <TEMPLATE>/skills-sap/sap-code-review/tests -v` (validator uyumluluğu dahil).
6. Harita template reposundadır ve ekibe gider: değişikliği kullanıcıya göster, onayla commit/PR.

**Fail-open'a karşı script davranışı:** bozuk ya da yanlış biçimli kaynak → çıkış 2, hedef değişmez · tablo bölümü boş →
yazılmaz · tablo sayısı yarıdan fazla düşerse → çıkış 3 (`--allow-shrink` ile bilinçli geçilir) · hedef klasör yoksa
yaratılır · yazım atomiktir · `lookup`/`status` veri yoksa çıkış 2.
Public Cloud için farklı dosya adı ve içeriği DOĞRULANMADI; o profilde platform zaten reddettiği için harita gerekmez.

## 7. Uygulanmayan clean core kural aileleri
ABAP dil sürümü ("ABAP for Cloud Development") ve "klasik yasak" aileleri `s4_private` projelerinde uygulanmaz: iki yol
yan yana meşrudur ve SAP bu aileleri klasik geliştirme için dışarıda bırakır (validator açıklaması). `s4_public` ve
`btp_abap`'ta platformun kendisi zorlar.

## Bu dosyada ÇIKARILAN / DEĞİŞTİRİLEN
- Kaynaktaki ağdan indiren yenileme script'i alınmadı; yerel dosyadan yenileme + fail-open korumaları yazıldı.
- Müşteri sistem/varyant adları ve gerçek vaka obje adları çıkarıldı.
- Kaynakta HIGH olan "released yerine standart tablo" önemi politikaya bağlandı (§1).
