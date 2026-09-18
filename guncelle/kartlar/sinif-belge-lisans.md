# sinif-belge-lisans — belgeler, lisanslar ve depo talimatı

## Tetik
Plandaki dosya `README.md`, `docs/**`, `LICENSE`/`NOTICE`, `CHANGELOG.md`, `AGENTS.md` ya da bir skill indeksi.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `lisans` | `null` | yok | ayrı etkinleşme anı yok |
| `bakim-repo-agents` | `yeni-oturum` | yok | aXet'i kapat-aç |
| `belge-kok` | `null` | yok | ayrı etkinleşme anı yok |
| `belge-docs` | `null` | yok | ayrı etkinleşme anı yok |
| `skill-index-belge` | `null` | yok | ayrı etkinleşme anı yok |
| `skill-implementation-belge` | `null` | yok | ayrı etkinleşme anı yok |
| `belge-changelog` | `null` | yok | ayrı etkinleşme anı yok |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir.
2. Bu sınıfın çoğu üyesi aXet'e hiç yüklenmez (etkinleşme anı yok) — kullanıcıya "bir şey yapman
   gerekmiyor" de. TEK istisna kök `AGENTS.md`: yalnız bu template deposu üzerinde çalışılırken
   yüklenir ve oturum başında okunur ⇒ değiştiyse aXet'i kapat-aç.
3. Lisans dosyaları yayın paketinde bulunması ZORUNLU dosyalardır: silinmelerini önerme.

## DUR
Kullanıcının kendi notlarını içeren bir belgede (V4c) bizim metnimizi tümden üste yazma;
belge birleşmesi de iki tarafı korur.
