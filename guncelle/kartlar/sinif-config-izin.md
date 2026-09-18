# sinif-config-izin — izin ve yapılandırma (`config/**`, `.axetcode-denylist`)

## Tetik
Plandaki dosya `config/permissions.json`, `.axetcode-denylist` ya da proje şablonunun config dosyası. `kritik_yol`.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `config-izin-kok` | `install-sonra-yeni-oturum` | komut | python scripts/install.py |
| `proje-sablon-config` | `null` | manuel | değişiklik mevcut projelere ancak %guncelle-proje ile ulaşır |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir.
2. **Özel adım alt sınıfa göre değişir (yukarıdaki tablo):** `config-izin-kok` için özel adım bir
   KOMUTTUR — `guncelle.py ozel-adim config-izin-kok` → `python scripts/install.py`; bu koşmadan
   kapanış 0 dönmez. `proje-sablon-config` için özel adım MANUEL'dir (`%guncelle-proje`) ve
   `install.py` koşmaz — o satırı kullanıcıya aynen aktarmak yeter.
3. `python tests/run_tests.py -k install` koş.
4. **Etkinleşme de alt sınıfa göre değişir (yukarıdaki tablo):** `config-izin-kok` için
   (`etkin = install-sonra-yeni-oturum`) kullanıcıya söyle: önce `install.py`, sonra **aXet'i
   kapatıp aç** — izinler oturum başında okunur. `proje-sablon-config` için ayrı bir etkinleşme
   anı YOKTUR (`etkin = null`): kapat-aç İSTEME; o dosya şablondur, değişiklik mevcut projelere
   ancak `%guncelle-proje` ile ulaşır.

## DUR
Kullanıcının kendi izin kuralı template'in bir `deny` satırını eziyorsa bu RAPOR'a yazılır,
ama güncelleme engellenmez. Kullanıcı adına izin gevşetme kararı VERME.
