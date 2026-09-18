# sinif-kurulum-araci — kurulum araçları (`kur.ps1`, `kur.cmd`, `yeni-proje.cmd`)

## Tetik
Plandaki dosya `kur.ps1`, `kur.cmd` ya da `yeni-proje.cmd`.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `kurulum-araci-kok` | `null` | yok | ayrı etkinleşme anı yok |

## Zorunlu ek adımlar
1. Yalnız dosyayı al/birleştir — **bu araçları güncelleme sırasında ÇALIŞTIRMA**.
2. Test: `python tests/run_tests.py -k kur`.
3. Raporda şu satırın çıktığını doğrula: değişiklik **bir sonraki `kur.cmd` çalıştırmasında**
   etkin olur; aXet oturumunu ilgilendirmez.

## DUR
`kur.cmd -Sifirla` bir güncelleme adımı DEĞİLDİR: klonu tamamen template'e eşitler ve yerel
değişiklikleri yalnız yedek dalında bırakır. Bu akışta çalıştırılmaz.
