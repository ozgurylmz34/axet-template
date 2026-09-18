# sinif-cekirdek-kural — çekirdek çalışma disiplini (`core/**`)

## Tetik
Plandaki dosya `core/00-temel.md` ya da `core/` altındaki başka bir kural dosyası.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `cekirdek-kural` | `yeni-oturum` | yok | aXet'i kapat-aç |

## Zorunlu ek adımlar
1. Değişen bölümleri oku: `git diff <taban> <yeni> -- core/`. Özeti kullanıcıya kalem kalem aktar.
2. **Diskteki yeni sürüm otoritedir** — bu oturumun bağlamında duran eski kopyaya dayanma.
3. Raporda "aXet'i kapat-aç gerekli" satırının çıktığını doğrula: çekirdek bağlam oturum başında
   yüklenir, yeni kurallar ancak yeni oturumda geçerli olur.

## DUR
Yeni çekirdek metni bu kartla ya da izlediğin akışla çelişiyorsa DUR ve kullanıcıya bildir.
Çekirdek kuralları bir güncelleme adımı için gevşetilemez.
