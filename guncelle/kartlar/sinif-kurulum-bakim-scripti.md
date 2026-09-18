# sinif-kurulum-bakim-scripti — kurulum ve bakım script'leri (`scripts/*.py`)

## Tetik
Plandaki dosya `scripts/install.py`, `scripts/doctor.py`, `scripts/new_project.py` ya da başka bir kök script.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `kurulum-script-install` | `install-sonra-yeni-oturum` | komut | python scripts/install.py --dry-run, sonra python scripts/install.py |
| `kurulum-araci-script` | `aninda` | yok | anında geçerli |
| `bakim-script-kok` | `aninda` | yok | anında geçerli |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir.
2. `scripts/install.py` değiştiyse ÖNCE `python scripts/install.py --dry-run` (çıkış 0 olmalı),
   SONRA gerçek `python scripts/install.py` — ikisi de `guncelle.py ozel-adim` ile koşar.
3. Eş test dosyalarını koş (harita `esler`: ilgili `tests/test_*.py`); pratikte
   `python tests/run_tests.py`.
4. Etkinleşme: script'ler anında geçerlidir; `install.py` için önce install, sonra kapat-aç.

## DUR
`install.py --dry-run` hata verirse dosyayı geri al (`guncelle.py geri-al <yol>`) ve DUR:
bozuk bir kurulum aracı bir sonraki oturumu da bozar.
