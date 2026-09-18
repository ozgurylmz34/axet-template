# sinif-test-fixture — testler ve fixture'lar (`tests/**`, `fixtures/**`)

## Tetik
Plandaki dosya bir test dosyası ya da test verisi.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `test-kok` | `aninda` | yok | anında geçerli |
| `skill-fixture-sample` | `aninda` | yok | anında geçerli |
| `skill-test` | `aninda` | yok | anında geçerli |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir.
2. Test ettiği dosya AYNI kalemde değilse testi almadan önce kullanıcıya söyle: yeni test eski
   koda karşı koşar ve haklı olarak kırmızı verebilir.
3. Ölçüm: ilgili takımı koş (`python tests/run_tests.py` ya da skill'in kendi `run_tests.py`'si).

## DUR
Kırmızı testi "zaten testti" diye geçiştirme. Sonra-ölçümde YENİ kırmızı varsa kapanış 0
dönmez; sebebini bul.
