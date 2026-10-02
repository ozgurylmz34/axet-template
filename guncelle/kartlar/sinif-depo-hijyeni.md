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
3. Ölçüm kök takımdır (`python tests/run_tests.py`): güncelleme içinde KOŞMA (Z162) — CI'nın kefil olmadığı ağaçta bu takım adım 10'da **test borcuna** yazılır; kapanıştan sonra kullanıcı isterse `%testler` koşar.

## DUR
Kendi CI kurallarını (kendi fork'unda) ezmek istemiyorsan `--karar yerel` seç; kararı
kullanıcı versin.
