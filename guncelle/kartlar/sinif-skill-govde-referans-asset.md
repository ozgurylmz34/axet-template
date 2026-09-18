# sinif-skill-govde-referans-asset — skill gövdesi, referansı ve örnek dosyaları

## Tetik
Plandaki dosya bir `SKILL.md`, skill `references/**` ya da `templates/**`/`assets/**` dosyası.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `skill-govde` | `skill-cagrisi` | komut | skill klasörü YENİ eklendiyse python scripts/install.py |
| `bilinen-hata-referans` | `skill-cagrisi` | yok | skill'in bir sonraki çağrısında |
| `skill-referans` | `skill-cagrisi` | yok | skill'in bir sonraki çağrısında |
| `skill-asset-template` | `skill-cagrisi` | yok | skill'in bir sonraki çağrısında |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir.
2. `python scripts/doctor.py --skills` koş: ad çakışması, bozuk frontmatter, eksik referans
   buradan görünür.
3. **Özel adım KOŞULSUZDUR.** Plan, `skill-govde` alt sınıfından bir dosya içeren her kalemde bu
   adımı listeler: `guncelle.py ozel-adim skill-govde` → `python scripts/install.py`. Bu adım
   koşmadan `kapanis` 0 dönmez (`özel adım koşmadı: skill-govde`, çıkış 1). **Atlama.**
   ⚠ Kapsam tablosunun 4. sütunundaki "skill klasörü YENİ eklendiyse" ibaresi `harita.json`'daki
   `ozel_adim` metninin AYNEN alıntısıdır; motor o cümleyi OKUMAZ — ölçüldü (`scripts/guncelle.py`,
   kalem kurulumu: alan doluysa sınıf adı doğrudan `ozel_adimlar` listesine girer; vaka koduna ya
   da klasörün yeni olup olmadığına BAKILMAZ). Gövdesi yalnızca güncellenmiş, klasörü çok önceden
   var olan bir skill'de de adım koşar.
4. Etkinleşme: skill bir sonraki çağrısında yeni gövdeyi okur — aXet'i kapatıp açmak gerekmez.

## DUR
Örnek dosyalar (`.conn_adt.example` gibi) YALNIZ örnektir: gerçek `.conn_adt` dosyasına
dokunma, okuma, içeriğini isteme.
