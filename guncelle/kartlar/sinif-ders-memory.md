# sinif-ders-memory — dersler ve hafıza (`memory/**`)

## Tetik
Plandaki dosya `memory/MEMORY.md` ya da bir `memory/feedback_*.md`.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `ders-memory` | `yeni-oturum` | yok | aXet'i kapat-aç |
| `ders-memory-proje-sablon` | `null` | yok | ayrı etkinleşme anı yok |

## Zorunlu ek adımlar
1. `MEMORY.md` indeksi satır bazında birleşir; ekleme çakışması nadirdir (V4c çıkarsa iki
   tarafın satırlarını da koru — indeks bir listedir, seçim değil).
2. Yeni `feedback_*.md` dosyaları aynı kalemde gelir; indeks ile dosyaların eşleştiğini doğrula
   (indekste adı geçen her dosya var mı, her dosya indekste mi). Uyuşmazlık RAPOR'a WARN satırı
   olarak yazılır, kapanışı engellemez.
3. Etkinleşme alt sınıfa bağlıdır (yukarıdaki tablo): `ders-memory` (`memory/**`) oturum başında
   yüklenir ⇒ **aXet'i kapat-aç**. `ders-memory-proje-sablon` bir şablon dosyasıdır; klonda
   güncellenir ama mevcut projelere ancak `%guncelle-proje` ile ulaşır, ayrı etkinleşme anı yoktur.

## DUR
Kullanıcının kendi yazdığı dersi silen bir birleşme önerme; hafıza eklenerek büyür.
