# sinif-skill-scripti — skill'lerin çalıştırdığı script'ler

## Tetik
Plandaki dosya bir skill klasörü altındaki `.py`/çalıştırılabilir dosya.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `skill-script` | `aninda` | yok | anında geçerli |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir.
2. Eş dosya olarak skill gövdesi (`SKILL.md`) aynı kalemde mi bak — script'in sözleşmesi orada
   anlatılır; yalnız biri gelirse ikisi ayrışır.
3. Skill'in kendi test takımı (harita `test` alanı: ilgili `tests/run_tests.py`): güncelleme içinde KOŞMA (Z162) — CI'nın kefil olmadığı ağaçta bu takım adım 10'da **test borcuna** yazılır; kapanıştan sonra kullanıcı isterse `%testler` koşar.
4. Etkinleşme anında: değişiklik bir sonraki çağrıda geçerlidir.

## DUR
Script değişti ama eş `SKILL.md` planda yoksa (ya da tersi) kullanıcıya uyumsuzluk riskini
söyle; testi kırmızı bırakıp kapanışa geçme.
