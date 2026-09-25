# abapGit ZIP teslimi — başvuru

Bu dosya `sap-abapgit-delivery` skill'inin dayandığı bilgileri, geliştiricinin SAP GUI adımlarını ve sorun giderme
tablosunu toplar. Kaynaklar abapGit resmî dokümantasyonudur (docs.abapgit.org, okunma tarihi 2026-09-13);
kaynaksız her iddia §5'te **DOĞRULANMADI** olarak listelenir.

## 1. Doğrulanmış bilgiler

| Konu | Bilgi | Kaynak |
|---|---|---|
| Repo ayarı | Kökteki `.abapgit.xml`: `MASTER_LANGUAGE` tek harfli SAP dil kodu (`E` = İngilizce); abapGit bir nesnenin ana dilini değiştiremez | https://docs.abapgit.org/user-guide/repo-settings/dot-abapgit.html |
| Başlangıç klasörü | `STARTING_FOLDER` genelde `/src/`; dışındaki dosyalar yok sayılır | aynı sayfa |
| Klasör mantığı | `FOLDER_LOGIC` = `PREFIX`, `FULL` ya da `MIXED`; klasörler alt paketlere karşılık gelir | aynı sayfa · https://docs.abapgit.org/user-guide/reference/packages.html |
| Dosya adı | `<nesne adı>.<nesne tipi>[.<parça>].<uzantı>`; `/NS/` ad alanı XML dosya adında `#ns#`, JSON dosya adında `(ns)` | https://docs.abapgit.org/user-guide/reference/folders-filenames.html |
| Dosya biçimi | Her nesne en az bir XML dosyasıyla temsil edilir; yeni tiplerde JSON; boş parça dosyası yazılmaz | https://docs.abapgit.org/development-guide/serializers/file-formats.html |
| Satır sonu | abapGit yalnız LF satır sonunu içe aktarır | aynı sayfa |
| Paketler | İçe aktarımda paket ve alt paketler otomatik yaratılır | https://docs.abapgit.org/user-guide/reference/packages.html |
| Çevrimdışı dışa aktarma | "Export ZIP" sayfası: ZIP indirilir; dosya adları ve klasör yerleri değiştirilmemelidir (çevrimdışı ve çevrimiçi repo aynı dosyaları içersin diye) | https://docs.abapgit.org/user-guide/projects/offline/export-zip.html |
| Çevrimdışı içe aktarma | New Offline → mevcut paketi seç (ya da yeni yarat) → Import zip → Pull zip; pull sırasında transport istenir | https://docs.abapgit.org/user-guide/projects/offline/import-zip.html |

Proje kuralı karşılığı: paket otomatik yaratıldığı için yeni klasör ve `*.devc.xml` teslimde FAIL'dir (Kesin Yasak C).
TR→`T` eşlemesi foundation kütüphanesindeki T100 örneğine (`sprsl = 'T'`) dayanır.

## 2. Geliştirici adımları (SAP GUI)

**Dışa aktarma (taban çizgisi):**
1. abapGit'i aç, paketin çevrimdışı reposunu seç (yoksa New Offline ile paketi bağla — yeni paket yaratma).
2. Repoyu ZIP olarak indir (dokümantasyon başlığı "Export ZIP"; SAP GUI'deki düğme etiketi sürüme göre değişebilir —
   DOĞRULANMADI), modele ver. Model `unpack` çalıştırır. Dosya adlarını ve klasörleri değiştirme.

**İçe aktarma (teslim):**
1. Aynı çevrimdışı repoda Import zip → modelin verdiği `dist/…zip` dosyasını seç.
2. Pull zip; farkları gözden geçir; transport'u sen seç (model transport yaratmaz, önermez).
3. Aktivasyon hata listesi ya da log'u metin olarak kaydet (kopyala-yapıştır `.txt` yeterli) ve modele ver.
4. Nesneyi SAP'de aç, aktif sürümün beklenen değişikliği içerdiğini gör.
5. Silinecek nesne varsa SAP'de elle sil: ZIP bunu yapmaz (bkz. §5).

İçe aktarımı projenin ana dilinde oturum açarak yap; dil uyuşmazlığında metinler yanlış dile yazılır (Kesin Yasak D).

## 3. Çalışma alanı düzeni

```
<source_root>/<MODÜL>/<PAKET>/abapgit/
  .abapgit.xml                  SAP'den gelir, elle değiştirilmez
  .abapgit-baseline.json        unpack yazar (dosya özetleri + tarih)
  src/…                         abapGit dosyaları (model burada düzenler)
  dist/                         pack çıktıları            (commit edilmez)
  .abapgit-status/              SAP dönüş kayıtları        (commit edilmez)
```

## 4. Sorun giderme

| Belirti | Olası neden | Ne yapılır |
|---|---|---|
| `pack` → `metadata_missing` | yeni nesnenin `<ad>.<tip>.xml` dosyası yok | aynı tipte SAP'den gelmiş nesnenin XML'ini örnek al, alanları uydurma |
| `ADR_0005_C_subpackage` | yeni klasör → abapGit alt paket yaratır | alt paketi geliştirici SE21'de açar, sonra `--subpackages-exist` |
| `language_mismatch` | repo dili ile proje dili farklı | ZIP'i doğru dilde bağlanmış repodan yeniden dışa aktar |
| `baseline_stale` | taban çizgisi eski | SAP'den güncel ZIP al, `unpack` (yerel değişiklik varsa önce pack) |
| `std_dml_scan_unavailable` · `std_ext_scan_unavailable` | foundation tarayıcısı bulunamadı | template klonu eksik; `doctor.py` çalıştır |
| `ADR_0005_A` + "genişletme" mesajı | Z objenin kaynağı standart objeyi genişletiyor (append/extend/annotate/BDEF extension) | DUR: append/extend'i kullanıcı SAP'de yaratır, sonucu bildirir; teslimden çıkar |
| Pull sırasında satır sonu hatası / fark | CRLF | `pack` LF'ye çevirir; ZIP'i elle yeniden paketleme |
| Aktivasyon hatası | sözdizimi/bağımlılık (araç denetlemez) | çıktıyı `status-in` ile al, satırı dosyaya eşle, düzelt, yeniden `pack` |

## 5. DOĞRULANMADI

- ZIP içe aktarımında çalışma alanından silinen dosyanın SAP'de silinip silinmediği (dokümantasyonda bulunamadı);
  araç `deleted_locally` uyarısı verir ve silmeyi geliştiriciye bırakır.
- DTEL XML'inde dört etiketin alan adları (`REPTEXT`, `SCRTEXT_S`, `SCRTEXT_M`, `SCRTEXT_L`): repoda örnek yok.
  Etiket bulunamazsa araç FAIL değil WARN verir.
- SAP'nin boş XML elemanlarını hiç yazmadığı varsayımı: bu yüzden "etiketlerin hepsi yok" WARN, "bir kısmı var"
  ya da "boş" FAIL'dir.
- İçe aktarım için oturum dilinin zorunlu olarak İngilizce olması gerekip gerekmediği (kurulum sayfasındaki öneri
  içe aktarıma genellenemedi).
- EN ve TR dışındaki diller için tek harfli dil kodu.
