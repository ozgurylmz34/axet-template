# GUNCELLE.md — `%guncelle` akışı (aXet ajanı bunu izler)

> Bu belge **talimattır**: `%guncelle` çalışırken ajan bu dosyayı template klonunun doğrulanmış
> `origin`'inden okur ve adımları sırayla uygular. Çekirdek kuralları, kesin yasakları ve izin
> kurallarını **gevşetemez**; çelişki görürsen DUR ve kullanıcıya bildir.

**Ne yapar:** merkezi klonu (`%USERPROFILE%\axet`) yeni template yayınına **seçmeli** olarak
günceller. Senin değiştirdiğin dosyalar izinsiz ezilmez, her adım ölçülür, her şey geri alınabilir.
**Ne yapmaz:** projelerini güncellemez (o `%guncelle-proje`), SAP'ye dokunmaz, hiçbir şeyi push
etmez, hiçbir şeyi zorla (`--force`) yapmaz.
**Klonda İKİ commit atar** (yerel kalır, push edilmez): ① `hazirla` adımı, güncelleme öncesi
izlenen değişikliklerini `guncelle: yerel anlık <tarih>` commit'ine alır — geri dönüş noktan budur;
② `kapanis` adımı uygulanan kalemleri `guncelle: <yayın> kalemler <id…>` commit'ine yazar.
Kullanıcıya bunu BAŞTAN söyle: klonun git geçmişinde bu iki commit görünecek.

Motor: `scripts/guncelle.py`. Akış boyunca **yeni sürümden** çalışır (yerel kopyası eski ya da
bozuk olabilir). Durum dosyaları klonun `.axet-guncelleme/` klasöründedir ve git tarafından
izlenmez.

---

## Akış (sırayla, atlama)

| # | Adım | Komut | Beklenen | FAIL'de |
|---|---|---|---|---|
| 0 | Başlangıç | `git -C <klon> fetch --tags`, bu dosyayı `origin/main`'den oku | 0 | ağ yoksa "şimdi güncellenemez" de, DUR |
| 1 | Etkileşim | kullanıcıdan "başlayalım mı" cevabını al | açık onay | etkileşimsiz koşuyorsan DUR |
| 2 | Ön kontrol | `guncelle.py onkontrol` | 0 | 2 → sebebi AYNEN göster, DUR |
| 3 | Geri dönüş noktası | `guncelle.py hazirla` — **yerel anlık commit** + `guncelle-oncesi-<tarih>` etiketi + `fetch --tags` | 0 | DUR (geri alınamayacak bir güncelleme başlatılmaz) |
| 4 | Plan | `guncelle.py plan` | 0 (1 = güncel, bitir) | 2 → DUR |
| 5 | Seçim | plan tablosunu göster → `guncelle.py sec --hepsi` ya da `--kalem/--cikar` | 0 | 2 → tutarsızlığı açıkla, yeniden sor |
| 6 | Önce-ölçüm | `guncelle.py olc --asama once` | 0 | 2 → DUR (ölçülemeyen güncelleme yapılmaz) |
| 6b | *(6'nın İÇİNDE, otomatik — ayrı komut değil)* **CI ikamesi:** planda **yargı vakası yoksa** ve yayının `guncelle/ci-durum.json` kaydı bu etiket için `hepsi_yesil: true` ise adım 6 **test koşmaz**, tabanı CI hükmünden alır ve `[İKAME]` + `KAPSAM` satırlarını basar. **Bu satırları kullanıcıya AYNEN aktar.** Her belirsizlikte (kayıt yok · etiket tutmuyor · tek takım kırmızı · CI hâlâ koşuyor) **normal ölçüme döner** — *ölçülemedi ≠ yeşil*. | 0 | — |
| 6c | *(6 ve 10'un İÇİNDE, otomatik — ayrı komut değil)* **Kapsanan komut ayıklaması:** aynı `cwd`'de hem `python tests/run_tests.py` hem `… -k <desen>` seçilmişse filtreli olan KOŞULMAZ (kapsamı filtresizin öz alt kümesidir) ve `[KAPSANDI] …` satırı basılır. **Bu satırı da kullanıcıya aktar** — atlanan komut sayısı ve adları oradadır. Filtresiz eş yoksa hiçbir şey atlanmaz. | 0 | — |
| 7 | Otomatik vakalar | `guncelle.py uygula --otomatik`, sonra yazılan her dosyanın plandaki `kart` alanındaki kartları (`V1`/`V2`/… + `sinif-…`) oku ve ek adımlarını uygula | 0 | 1 → `guncelle.py durum` göster, DUR |
| 8 | Yargı vakaları | her dosya için `guncelle.py kart <KOD>` → **kartın adımlarını uygula** (hangi komutun koşacağını KART söyler) → `guncelle.py isaretle <yol> --karar …` | her biri 0 | kartın DUR koşulu |
| 9 | Özel adımlar | `guncelle.py ozel-adim <ad>` | 0 | kart talimatı (ör. `install.py --dry-run` hata → `geri-al`) |
| 10 | Sonra-ölçüm | `guncelle.py olc --asama sonra` | 0 | 2 → DUR |
| 10b | *(10'un İÇİNDE, otomatik — ayrı komut değil)* **CI ikamesi (sonra):** 6b'nin şartları sağlanıyorsa **ve** disk ağacı yayın etiketinin ağacıyla **aynıysa** (plan beyanı değil, diskten ölçülür; karşılaştırma DIŞI: yayın meta dosyaları · gitignore'lu dosyalar · satır sonu farkı) adım 10 **test koşmaz** ve `[İKAME] sonra-ölçüm KOŞULMADI` + `KAPSAM` satırlarını basar. **AYNEN aktar.** Ağaç farklıysa `[ÖLÇ] … FARKLI (N yol: …)` basar ve normal ölçer. Yerel ortamın asgari kontrolü adım 12'de yine koşar. İkame RAPOR.md'ye de yazılır ("yerelde test KOŞULMADI"). | 0 | — |
| 11 | Kritik yol karşılaştırması | `kritik_yol` sınıfı V4 dosyaları: aynı örnekle önce/sonra hüküm | fark açıklanmış | açıklanamayan fark → DUR |
| 12 | Bütünlük turu | `guncelle.py butunluk` | 0 | 1 → adım 13 |
| 13 | Düzeltme döngüsü | FAIL'i düzelt → ilgili dosyayı yeniden `isaretle` → `butunluk` | en fazla **2 tur** | 2. turda da FAIL → DUR, üç seçenek sun |
| 14 | Kapanış | `guncelle.py kapanis` — hükmü verir, `RAPOR.md`'yi üretir ve **kalem commit'ini** atar | 0 | 1 → raporu göster, seçenek sun |
| 15 | Son | `RAPOR.md`'yi AYNEN göster; kapat-aç gerekip gerekmediğini `plan.json`'daki `yeniden_baslat` alanı söyler (`null` = gerekmez · `yeni-oturum` = kapat-aç · `install-sonra-yeni-oturum` = önce `install.py`, sonra kapat-aç) | — | — |
| 16 | Tarayıcı hazırlığı *(otomatik, soru SORMA)* | `python "<klon>/scripts/tarayici_hazirla.py"` — kurulu Chrome/Edge + merkezi `playwright-cli` + `~/.playwright/cli.config.json` + duman testi; idempotent. Betik klonda yoksa (kalem alınmadı) koşma, "tarayıcı hazırlığı: betik yok" de | ilk satır `TARAYICI: HAZIR …` · çıkış daima 0 | `ATLANDI`/`EKSİK` güncellemeyi BOZMAZ: güncelleme yine "tamamlandı"; ilk satırı AYNEN aktar (neyin eksik kaldığını o söyler), yeniden deneme, başka komut önerme. Betik sınırlı sürede döner; çıktıda `TARAYICI:` satırı yoksa bu adım başarısız sayılır ama güncelleme yine devam eder/tamamlanır |

**2. turda hâlâ FAIL varsa** üç seçeneği sun ve kullanıcı seçsin:
(a) hepsini geri al — `guncelle.py geri-al --hepsi` (**önerilen**) ·
(b) yalnız sorunlu kalemi geri al, kalanlarla kapan ·
(c) FAIL'i kabul et — `guncelle.py kapanis --kabul "<gerekçe>"` (çıkış 3, raporda kalıcı).

---

## Vaka kartları

Her dosya bir **vaka kodu** alır. Plana giren her kodun — otomatik uygulananların da — bir kartı
vardır: yargı kartları ne soracağını, otomatik kartlar ne olduğunu ve kullanıcıya nasıl
anlatacağını söyler. Dosyanın sınıf kartı (`sinif-…`) ise otomatik vakalarda da ZORUNLUDUR
(ör. `core/**` otomatik alınır ama `sinif-cekirdek-kural` kartı "yeni oturum gerekli" demeyi
emreder). Planın `kart` alanı hangi kartları okuyacağını dosya başına yazar:

```
guncelle.py kart <KOD>
```

Kartlar `guncelle/kartlar/` altındadır: `V1` · `V1R` · `V2` · `V4B` · `V4R` · `V4c` · `V4c+ESIK` · `V4t` · `V5` · `V6` · `V6d` · `V7` · `VTB`.
Dosyanın sınıfı için ayrıca bir `sinif-<ad>` kartı varsa (aşağıdaki tablo) vaka kartına **ek
olarak** o da uygulanır — plan her dosyanın `kart` alanında hangilerini okuyacağını yazar.

İşlem gerektirmeyen kodların (V0, V3, V2e, V4e, V5s, V6x, VKD) kartı YOKTUR: plan onları yalnız
sayar, hiçbir komut çalıştırılmaz.

**Hangi komutun koşacağına KART karar verir, akış tablosu değil.** Birleştirme isteyen kartlar
(`V4t`, `V4c`, `V4c+ESIK`, `V4B`, `V4R`) `guncelle.py oneri <yol>` komutunu kendi 1. adımlarında
çağırır. Silme (`V6d`), ad çakışması (`V7`) ve tabansız (`VTB`) vakalarında bu komut
ÇALIŞTIRILMAZ: ya birleştirilecek bir sürüm yoktur ya da ortak taban yoktur; yine de koşulursa
yanıltıcı bir öneri ya da yanlış vaka etiketi üretebilir (ölçüldü 2026-09-18, doküman gate'i).

## Sınıf özeti (harita.json'dan üretilmiştir)

`guncelle/harita.json` her dosya yolunu tam bir sınıfa bağlar; sınıf dosyanın nasıl etkinleştiğini,
hangi testlerin koşacağını ve özel adım gerekip gerekmediğini söyler.

| Üst sınıf | Kapsam | Alt sınıf | Etkinleşme | Risk | Özel adım | Kritik yol |
|---|---|---|---|---|---|---|
| `cekirdek-kural` | çekirdek kural core/** | 1 | aXet'i kapat-aç | yuksek | — | — |
| `kesin-yasak-kanonigi` | kesin yasak kanoniği core/sap/00-sap.md | 1 | aXet'i kapat-aç | yuksek | evet | evet |
| `skill-govde-referans-asset` | skill gövdesi/referans/asset | 4 | skill'in bir sonraki çağrısında | dusuk / orta | evet | — |
| `skill-scripti` | skill script'i | 1 | anında | orta | — | — |
| `validator-ailesi` | validator + zincir + gate motoru | 8 | anında / skill'in bir sonraki çağrısında | orta / yuksek | — | evet |
| `ders-memory` | ders/memory memory/** | 2 | aXet'i kapat-aç / ayrı etkinleşme anı yok | orta | — | — |
| `config-izin` | config/izin config/**, .axetcode-denylist | 2 | install.py + kapat-aç / ayrı etkinleşme anı yok | yuksek | evet | evet |
| `kurulum-bakim-scripti` | kurulum/bakım script'i scripts/*.py | 3 | install.py + kapat-aç / anında | yuksek | evet | evet |
| `kurulum-araci` | kurulum aracı kur.ps1, kur.cmd, yeni-proje.cmd | 1 | ayrı etkinleşme anı yok | orta | — | — |
| `proje-sablonu` | proje şablonu templates/project*/** | 3 | ayrı etkinleşme anı yok | dusuk / orta | evet | — |
| `test-fixture` | test / fixture | 3 | anında | dusuk | — | — |
| `belge-lisans` | belge / lisans | 6 | ayrı etkinleşme anı yok / aXet'i kapat-aç | dusuk / orta | — | — |
| `guncelleme-motoru` | güncelleme motoru GUNCELLE.md, guncelle/**, scripts/guncelle.py | 1 | anında | yuksek | — | — |
| `bakim-ic` | bakım/iç maintenance/** (public sürüme girmez) | 1 | ayrı etkinleşme anı yok | dusuk | — | — |
| `depo-hijyeni` | depo hijyeni .github/** (CI, kod sahipliği) | 1 | ayrı etkinleşme anı yok | orta | — | — |

## Ajanın YAPMAYACAKLARI

- `git reset --hard`, `git push`, herhangi bir `--force`, `git clean` (klonu sıfırlamak yalnız
  kullanıcının `kur.cmd -Sifirla` komutudur)
- `plan.json` ya da `durum.json`'u elle düzenlemek (hüküm oradan çıkar; elle yazılan hüküm sahtedir)
- `.conn_adt` dosyasını okumak ya da içeriğini istemek
- `install.py --sap-write` · `behavior_manifest.py generate` (ikisi de aXet'e kapalıdır; gerekiyorsa
  kullanıcı KENDİ terminalinde çalıştırır)
- testsiz "tamam" demek; planda olmayan bir dosyaya dokunmak
- kullanıcı cevap vermeden bir yargı vakasını işaretlemek

## Geri alma

`hazirla` adımı her şeyden önce bir `guncelle-oncesi-<tarih>` etiketi atar.
Tek dosya: `guncelle.py geri-al <yol>` · tümü: `guncelle.py geri-al --hepsi`.
Kapanıştan sonra bile klasik yol açıktır: `git -C <klon> restore --source guncelle-oncesi-<tarih> -- <yol>`.
