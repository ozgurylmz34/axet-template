# sinif-proje-sablonu — proje ve paket şablonları (`templates/**`)

## Tetik
Plandaki dosya `templates/project/**`, `templates/project-sap/**` ya da `templates/package/**`.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `proje-sablon-diger` | `null` | manuel | değişiklik mevcut projelere ancak %guncelle-proje ile ulaşır |
| `proje-sablon-sap-json` | `null` | yok | ayrı etkinleşme anı yok |
| `paket-sablon` | `null` | yok | ayrı etkinleşme anı yok |

## Zorunlu ek adımlar
1. Dosyayı klonda al/birleştir.
2. Kullanıcıya açıkça söyle: **bu değişiklik mevcut projelere kendiliğinden ULAŞMAZ**; her proje
   için ayrıca `%guncelle-proje` çalıştırılır. Bu uyarı plana yalnız `proje-sablon-diger` alt
   sınıfında MANUEL özel adım olarak girer (`guncelle.py ozel-adim proje-sablon-diger` →
   `MANUEL ADIM (...)` satırı; o satırı AYNEN aktar). `proje-sablon-sap-json` ve `paket-sablon`
   alt sınıflarında özel adım YOKTUR — yine de aynı uyarıyı sözlü olarak yap.
3. Test: `python tests/run_tests.py -k new_project` (paket şablonu için `-k new_package`).
4. `templates/package/**` `%guncelle-proje` kapsamı DIŞINDADIR: raporda yalnız bilgi satırı olur.

## DUR
Proje dosyalarına bu akış içinde dokunma. Klon güncellemesi ile proje güncellemesi ayrı
komutlardır ve ayrı onay ister.
