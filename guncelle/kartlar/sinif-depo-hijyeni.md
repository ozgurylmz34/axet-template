# sinif-depo-hijyeni — depo hijyeni (`.github/**` — CI, kod sahipliği)

## Tetik
Plandaki dosya `.github/` altında (iş akışı, CODEOWNERS, şablon).

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `ci-codeowners` | `null` | yok | ayrı etkinleşme anı yok |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir; aXet oturumuna yüklenmez, etkinleşme anı yoktur.
2. Bu dosyalar template deposunun kendi CI'ı içindir: kendi klonunda bir şey çalıştırmaz.
3. Ölçüm gerekiyorsa kök takım yeter: `python tests/run_tests.py`.

## DUR
Kendi CI kurallarını (kendi fork'unda) ezmek istemiyorsan `--karar yerel` seç; kararı
kullanıcı versin.
