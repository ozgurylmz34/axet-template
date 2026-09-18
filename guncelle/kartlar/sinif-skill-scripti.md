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
3. Skill'in kendi test takımını koş (harita `test` alanı: ilgili `tests/run_tests.py`).
4. Etkinleşme anında: değişiklik bir sonraki çağrıda geçerlidir.

## DUR
Script değişti ama eş `SKILL.md` planda yoksa (ya da tersi) kullanıcıya uyumsuzluk riskini
söyle; testi kırmızı bırakıp kapanışa geçme.
