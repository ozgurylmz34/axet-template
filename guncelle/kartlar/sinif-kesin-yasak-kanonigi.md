# sinif-kesin-yasak-kanonigi — SAP kesin yasaklar kanoniği (`core/sap/00-sap.md`)

## Tetik
Plandaki dosya `core/sap/00-sap.md`. Bu sınıf `kritik_yol`'dur: asgari güvence raporuna girer.

## Kapsam (harita.json)
| Alt sınıf | `etkin` | Özel adım | Ne demek |
|---|---|---|---|
| `cekirdek-kural-sap-kanonik` | `yeni-oturum` | manuel | türemiş projelerde %guncelle-proje ile damga yenilenir |

## Zorunlu ek adımlar
1. Dosyayı al/birleştir (vaka kartına göre).
2. `python scripts/doctor.py` çıktısındaki damga satırlarını kullanıcıya göster.
3. Kullanıcıya söyle: **SAP projelerinde `%guncelle-proje` çalıştırılmalı** — proje `AGENTS.md`
   damgaları ancak o zaman yenilenir. Bu bir MANUEL özel adımdır: `guncelle.py ozel-adim <sinif>`
   koşacak komut bulamaz, `MANUEL ADIM (...)` satırını basar; o satırı kullanıcıya AYNEN aktar.
   Proje şablon dosyaları hiç değişmemiş olsa da (yalnız bu kanonik ilerlediyse) `%guncelle-proje`
   planı `DAMGA` kalemini gösterir. Onaydan sonra `kapanis` damgayı yeniden basar ve tam
   `behavior_manifest.py generate --project-dir …` komutunu verir; kullanıcı bu komutu KENDİ
   terminalinde koşar. ⚠ v0.5.0'da bu yol yoktu (Z55): şablon güncel olunca plan "işlem
   gerektiren dosya yok" deyip çıkıyor, damga ESKİ kalıyordu. v0.5.1'e güncelledikten sonra
   `%guncelle-proje` tekrar koşulur.
4. Ölçüm: `python scripts/doctor.py` bütünlük turunda (adım 12) koşar. Takım
   (`python tests/run_tests.py -k sap_stamp`): güncelleme içinde KOŞMA (Z162) — CI'nın kefil olmadığı ağaçta bu takım adım 10'da **test borcuna** yazılır; kapanıştan sonra kullanıcı isterse `%testler` koşar.

## DUR
Yerelde kanonik metin değiştirilmişse (V4c) birleştirmeyi kendi başına yapma: yasak metnini
gevşeten bir birleşme ÖNERİLEMEZ. İki tarafı göster, kullanıcı karar versin, sonuç asgari güvence
raporuna yazılsın.
