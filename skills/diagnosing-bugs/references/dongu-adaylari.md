# Geri bildirim döngüsü adayları (`%diagnosing-bugs` Faz 1)

Kabaca bu sırayla dene. SAP araçları `sap_adt_cli.py <araç>` ile çağrılır (`%sap-adt-foundation`); araç adı, argümanı
ve sınıfı için otorite `sap_adt_cli.py --list` ve `sap-adt-foundation/references/tool-catalog.md`'dir.

| Bağlam | Döngü | Dikkat |
|---|---|---|
| ABAP dump | `adt_dump_list` → `adt_dump_read` (`summary=true`): aynı dump'ı yeniden üreten çağrı | Liste yalnız bağlantının client'ını gösterir; gizlenen sayı "dump yok" değildir (`foundation-query.md` §6) |
| Yanlış veri | `adt_sql_query` ile **kontrol grubu**: sorunlu kayıt + doğru çalışan kayıt yan yana, açık kolon listesiyle | Kırpma ve `COUNT(*)` tuzakları: `foundation-query.md` §1.1, §1.5 |
| Mevcut sınıf/FM davranışı | Mevcut testler için `adt_unit_run` (varsayılan okuma; `allow_risky_tests=true` yazma sınıfına geçer) | Yeni test yazmak projenin test politikasına bağlı (SKILL Faz 5) |
| `IF_OO_ADT_CLASSRUN` sınıfı | `adt_classrun` | **Kod çalıştırır, yazma yapabilir** → yazma sınıfı (`--sap-write --scope …`) + kullanıcı onayı. 200 dışı yanıt / zaman aşımı "koşmadı" demek değildir; yan etkili sınıfı etkisini kontrol etmeden yeniden koşma (K-28). Push/aktivasyon sonrası **eski kodun çıktısını** dönebilir: çıktıda yeni koda özgü bir imza satırı ara (K-13) |
| OData / Gateway | `$metadata`: `%sap-ui5-fiori` `scripts/fetch_ui_source.py metadata <SERVIS>` (salt okuma, tip-kapsamlı kontrol). Entity seviyesinde dar teşhis: `$top=1&$skip=0,1,2…` ikili arama → tek alan `$select` (`%sap-odata-backend` `references/segw-service.md` teşhis reçetesi) | Entity GET için CLI aracı yok: kullanıcı URL'yi tarayıcıda açar, maskelenmiş sonucu paylaşır. Kimlik bilgisi içeren betik yazma/çalıştırma (çekirdek §11). Git Bash'te URI argümanında `MSYS_NO_PATHCONV=1` |
| Freestyle UI5 | Playwright smoke = kapı (model API'siyle sayısal ölçüm, konsol, ağ) — `%sap-ui5-fiori` §9 + `references/runtime-verification.md` | DOM satır sayısı ya da `click()` sonucu kanıt değildir |
| Proje script'i / template aracı | Script'i gerçek giriş noktasından, küçük bir girdi dosyasıyla koş; template aracının testi `%testler` ile koşulur: önce `python <TEMPLATE>/scripts/testler.py --liste` (takım adları, son süre, borç), sonra `python <TEMPLATE>/scripts/testler.py --takim <ad>`. Takımların gerçek komutu `guncelle/harita.json`'dadır; her skill'in kendi `run_tests.py`'si yoktur, yolu tahmin etme. Tam kök takım ve `--hepsi` dakikalar sürer: kullanıcı onayı olmadan başlatma | Çıkış kodu 0 "temiz" demek değildir; stderr'i ve aracın kapsam satırını oku |
| Bağlantı / yetki | `sap_adt_cli.py sap_doctor` → ardından hedef objeye `adt_get include_source=false` | `.conn_adt` / `conn/*.env` okunmaz, basılmaz; `not_checked` listesi "doğrulandı" değildir |
| Yakalanmış iz | Gerçek istek/IDoc/dosya diske alınır (kişisel veri maskelenir), aynı kod yolundan yeniden oynatılır | Diske alınan iz git'e girmeyen bir yerde durur (gitignore'lu geçici klasör); commit'e girmez |
| İki durum arası regresyon | Fark ekseni: eski/yeni sürüm (`adt_revisions`), iki client, iki kullanıcı. Aynı girdi iki tarafta koşulup çıktı karşılaştırılır | Fark eksenini tek tut; iki ekseni aynı anda değiştirme |

## Yazma gerektiren döngü
Geçici sınıf, iz satırı ya da test verisi SAP'ye **yazmadır**: `%sap-adt-foundation` §4 ön koşulları (kullanıcının
`install.py --sap-write` kurulumu, DEV tier, `--sap-write`, kapsam beyanı, kullanıcı onayı) ve SAP kesin yasakları
aynen geçerlidir. Standart tabloya teşhis amaçlı bile doğrudan yazılmaz (B). Yazmayan bir döngü bulunabiliyorsa
yazan döngü kurulmaz; kurulduysa Faz 6'da aynı etiketle geri alınır.
