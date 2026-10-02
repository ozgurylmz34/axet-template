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
3. Ölçüm (`python tests/run_tests.py` ya da skill'in kendi `run_tests.py`'si): güncelleme içinde KOŞMA (Z162) — CI'nın kefil olmadığı ağaçta bu takım adım 10'da **test borcuna** yazılır; kapanıştan sonra kullanıcı isterse `%testler` koşar.

## DUR
Kırmızı testi "zaten testti" diye geçiştirme: `%testler` kırmızı verirse raporun dört giderme
seçeneğini kullanıcıya AYNEN sun, kendin düzeltme. Koşulmamış takımı "yeşil" diye raporlama —
ölçülmedi ≠ yeşil.
