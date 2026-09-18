# sinif-guncelleme-motoru — güncelleme motorunun kendisi (`GUNCELLE.md`, `guncelle/**`, `scripts/guncelle.py`)

## Tetik
Plandaki dosya bu akışı yürüten motorun bir parçası.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `guncelleme-motoru` | `aninda` | yok | anında geçerli |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir. Şunu bil: **şu anda koşan motor zaten yeni sürümdendir** (akış
   `origin/main`'den geçici bir kopya çıkarıp onu çalıştırır); klona almak yalnız bir sonraki
   sefer ve yerel inceleme içindir.
2. Test: `python tests/run_tests.py -k guncelle_harita` (harita değişmezleri) — harita
   güncellenmeden yeni klasör eklenmişse burada FAIL alırsın.
3. Raporda kalemi "bir sonraki `%guncelle` koşusunda görünür" diye anlat.

## DUR
`plan.json` / `durum.json` dosyalarını ELLE düzenleme — bu akışın tek hüküm kaynağı onlardır.
Motorun kendi dosyalarında V4c çıkarsa birleşmeyi çok dikkatli yap: bozuk motor bir sonraki
güncellemeyi imkânsızlaştırır.
