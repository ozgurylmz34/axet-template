# sinif-bakim-ic — bakım/iç dosyalar (`maintenance/**`)

## Tetik
Plandaki dosya `maintenance/` altında. Normalde bu dosyalar public yayına GİRMEZ; tüketici klonunda görünmesi beklenmez.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `bakim-ic` | `null` | yok | ayrı etkinleşme anı yok |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir (vaka kartına göre); aXet'e yüklenen bir şey değildir, etkinleşme anı
   yoktur.
2. Bu yolda bir kalem görürsen kullanıcıya bildir: bakım dosyalarının yayına girmesi beklenmez,
   yayın paketinde bir sapma olabilir.

## DUR
Bu dosyaları "nasılsa iç dosya" diye sessizce atlama; planda görünüyorsa kapanış onları da
ister.
