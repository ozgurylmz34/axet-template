# Yeni geliştirici: ilk gün rehberi

Makineyi hazırlamaktan ilk projede günlük çalışmaya kadar her adımı sırayla anlatır. Kurulum **3 adımdır**:
① `aXet-Kur.cmd`'ye çift tıkla · ② aXet içinde `%guncelle` (sonraki güncellemeler) · ③ proje için `%yeni-proje`
ya da `%guncelle-proje`, sonra proje klasöründeki `KURULUMU-TAMAMLA`'ya çift tıkla. Kurulumdan sonra etkileşimli
rehber istersen aXet oturumunda `%onboard` yaz: model aynı adımları senin makinende kontrol ederek yürütür.

Bu belgedeki yollar template'in varsayılan yere, `%USERPROFILE%\axet` klasörüne kurulduğunu varsayar
(PowerShell'de `$HOME\axet`). Başka yere kurduysan yolu değiştir.

> Kimlik bilgilerini (kullanıcı adı, şifre, token, bağlantı ayrıntısı) **sohbete yazma**. Prompt'lar kurumsal
> denetime gider. Bağlantı bilgisini kendin, proje klasöründeki `conn\DEV.env` dosyasına yazarsın.

---

## 0. Makine ön koşulları

| Gerekli | Nasıl sağlanır |
|---|---|
| aXet.code (girişi yapılmış) | şirket portalından (Software Center / Company Portal) |
| Git | şirket portalından |
| Python ≥ 3.12 | şirket portalından |

Portalda bulamazsan BT'den iste. Şirket makinesinde başka yoldan (winget, internetten indirme) kurma; şirketin izin
verdiği sürüm portaldakidir. Bir şeyin eksik olup olmadığını kendin kontrol etmen gerekmez: kurulum aracı üçüne
birden bakar ve eksikleri **tek listede** söyler.

Python ya da Git kurulu ama `python`/`git` komutu çalışmıyorsa (PATH'te değil ya da Windows mağaza kısayolu çıkıyor)
elle ayar yapma: kurulum aracı onları bilinen kurulum klasörlerinde ve Windows kayıt defterinde de arar, bulduğu
klasörü **kullanıcı** PATH'ine kendisi ekler (yönetici gerekmez).

**Git kimliğini** (adın ve iş e-postan) kurulum aracı sorar ve kaydeder; zaten tanımlıysa gösterip "doğru mu?" diye
sorar. **GitHub hesabı gerekmez:** template herkese açık klonlanır. `rg` (ripgrep) isteğe bağlıdır; yoksa kurulum
penceresi yalnız "rg yok (isteğe bağlı)" diye bilgi verir ve devam eder; kurmanı istemez, adres göstermez.

İsteğe bağlı paketler (yalnız ilgili iş gelince kur; kurmak senin kararın; ilgili skill kurulum satırını söyler):

| Paket | Hangi iş |
|---|---|
| `python-docx` | `%office-docs` ile Word çıktısı |
| `python-pptx` | `%office-slides` ile PowerPoint çıktısı |
| `openpyxl` | `%office-excel report` (biçimli Excel raporu) |
| Microsoft Edge ya da Chrome | `%office-docs` ile PDF çıktısı (Windows'ta Edge standart) |

## 1. Kurulum

1. [`aXet-Kur.cmd`](../aXet-Kur.cmd) dosyasını (template deposunun kökünde; açılan sayfada **Download raw file**) indir
   ya da ekibinden al ve **çift tıkla**. Windows "internetten geldi" uyarısı verirse **Daha fazla bilgi → Yine de
   çalıştır**.
2. Soruları cevapla: git adın ve e-postan (tanımlıysa yalnız "doğru mu?"). Sorular iş başlamadan, tek seferde sorulur.
3. Eksik program varsa pencere durur ve **tek bir liste** verir ("Şirket portalından şunları kur…"). Listedekileri
   portaldan kur, pencereyi kapat ve dosyaya **tekrar çift tıkla**. Portaldan yeni kurduğun program aynı çift
   tıklamada görünür (kurulum aracı PATH'i kayıttan tazeler).
4. Sonunda "**Kurulum TAMAM — aXet'i aç.**" yazar. Son kontrol (doctor) sorun bulursa ne yapacağını sade cümleyle
   söyler; ekran görüntüsünü destek ekibine gönderebilirsin.

Kurulum aracının yaptıkları (senin ayrıca bir şey çalıştırman gerekmez):
- aXet, Git ve Python'u birlikte arar; eksik olanların hepsini tek mesajda söyler (çıkış kodu 2).
- Git kimliğini sorar ve `git config --global` ile kaydeder (pencere etkileşimsizse sormaz, hiçbir şey yazmaz).
- Template'i `%USERPROFILE%\axet` klasörüne klonlar (makinede **bir kez**; tüm projeler aynı klonu kullanır).
- Global aXet config'ine yalnız kendi yollarını ve izin kurallarını ekler, önce yedek alır. SAP paketi açık kurulur;
  SAP'ye yazma **kapalı** kalır.
- Python paketlerini (SAP bağlantısı için) ve tarayıcı testini hazırlar; ağ/proxy engeli kurulumu durdurmaz (§5).
- Son kontrolü (`doctor.py`) koşar.
- `python`/`git` komutu yeni pencerede çalışmıyorsa bulduğu klasörü kullanıcı PATH'ine ekler (§5 "PATH").

Sonraki güncellemeler için aXet içinde **`%guncelle`** yaz; kurulum aracını yeniden çalıştırman gerekmez (yalnız
sorun gidermede, §5).

**SAP'ye yazma varsayılan kapalıdır ve kapalı kalmalıdır.** Yazma yalnız sandbox (DEV) sistemi için ve yalnız
ekip kararıyla, **kendi terminalinde** açılır: `python $HOME\axet\scripts\install.py --sap --sap-write`
(kapatmak için: `--no-sap-write`). aXet oturumu bu komutu çalıştıramaz. Normal teslim yolu 3.5'teki abapGit ZIP'idir.

## 2. İlk oturum doğrulaması

1. **aXet'i aç.** Kurulumdan önce açılmış oturum yeni ayarları görmez; açıksa kapatıp yeniden aç. İlk yanıtın ilk
   satırı şu kalıptadır:
   ```
   [AXET-CORE-… · SAP: … · proje: … · proje hafızası: …]
   ```
   Satır yoksa çekirdek yüklenmemiştir: §5 "İlk satırda AXET-CORE yok".
2. İstersen aXet'te `%onboard` yaz: model kurulumu senin makinende kontrol eder.

## 3. İlk proje

### 3.1 Proje kur
Projede çalışacağın klasörde aXet'i aç ve **`%yeni-proje`** yaz. Model şunları sırayla sorar:
- proje klasörü ve adı;
- SAP sistem profili, sürümü, master dili, clean core politikası;
- projenin amacı, depo adresi, test ve çalıştırma komutları.

Model önce ne yapacağını gösterir. Onay verince klasörü kurar (git reposu değilse `git init -b main`; pre-commit
denetimi ancak böyle kablolanır), proje iskeletini (`AGENTS.md`, `.axet-code.json`, proje hafızası, denylist,
`sap-project.json`, kesin yasak damgası) kurar, alanları doldurur ve `doctor.py` ile kontrol eder. Terminali tercih
edersen aynı işi `& $HOME\axet\yeni-proje.cmd` yapar.

`master_language` tüm Z nesnelerinin metin dilidir; emin değilsen ekip sorumlusuna sor. Var olan dosyalarda
senin yazdığın değerler ezilmez; araç farkı raporlar.

Var olan bir projeyi şablona getirmek için aXet'te **`%guncelle-proje`** yaz; bitince yine proje klasöründeki
`KURULUMU-TAMAMLA`'ya çift tıkla (değişen proje ayarlarının onayını o pencere sorar).

### 3.2 SAP kimlik bilgileri
Her SAP sistemi `conn\<AD>.env` dosyasıdır; aktif bağlantı proje kökündeki `.conn_adt`'dir. `conn/` ve `.conn_adt`
git'e girmez, aXet ajanına kapalıdır (denylist), içeriği sohbete yazılmaz.

1. **Proje klasöründeki `KURULUMU-TAMAMLA`'ya çift tıkla** (`%yeni-proje` yazar; yoksa
   `& $HOME\axet\proje-tamamla.cmd <klasör>`). Pencere SAP bilgisi **sormaz** ve dosyayı kendisi **açmaz**:
   - `conn\DEV.env` ve `conn\QA.env` şablonlarını yazar (var olanı ezmez) ve hangisini dolduracağını **tam yoluyla**
     söyler: `DEV.env` zorunlu, `QA.env` isteğe bağlı (QA sistemin yoksa dokunma; boş şablon atlanır).
   - Doldurulacak alanlar: `ADT_SAP_URL` (sistem adresi), `ADT_SAP_USER`, `ADT_SAP_PASSWORD`, `ADT_SAP_CLIENT`
     (3 hane). Dil (`sap-project.json` master_language), tier ve sistem adı (`<proje>_DEV`) hazır gelir.
   - Dosyayı Not Defteri ile aç, `<...>` yerleri doldur (köşeli parantezleri de sil), kaydet, **tekrar çift tıkla**.
     Hatalı alanlar adıyla gösterilir (değer basılmaz). Geçerli DEV aktif sistem olur.
   - Parola dosyada düz metin durur. Dosyaya yazmak istemezsen terminal yolu:
     `python $HOME\axet\skills-sap\sap-adt-foundation\scripts\setup_credentials.py --slot <AD>` (parola ekrana
     yansımaz; etkileşimsiz çağrıyı reddeder).
   - Sistem değiştirmek: aXet'te `%sistem` ya da "QA'ya geç". QA/PRD salt-okunurdur.
2. **Davranış yüzeyini onayla:** aynı pencere onaylanacak dosyaları listeler ve sorar (`behavior_manifest.py
   generate`; onay yalnız çift tıklanan gerçek pencerede verilir). Proje kuralları (`AGENTS.md`, `.axet-code.json`,
   denylist, `.githooks/`) her değiştiğinde kısayola tekrar çift tıkla; değişenler `!` ile gösterilir.
   Çift tıklanan pencerede `axet-code -c` açılışı DOĞRULANMADI.
3. **Doğrula** (isteğe bağlı; `%onboard` bunları senin yerine koşar — proje kökünde):
   ```powershell
   git check-ignore .conn_adt                                        # dosya adını basmalı
   python $HOME\axet\scripts\doctor.py                               # ".conn_adt git'e kapalı" PASS
   python $HOME\axet\skills-sap\sap-adt-foundation\scripts\sap_adt_cli.py ping
   ```
   Ardından bilinen bir Z nesnesiyle okuma testi yap. Argümanları dosyaya yaz; böylece PowerShell'de JSON
   tırnaklamasıyla uğraşmazsın:
   ```powershell
   Set-Content .tmp\get.json '{"name": "<BİLİNEN_Z_SINIF>", "object_type": "class", "include_source": false}'
   python $HOME\axet\skills-sap\sap-adt-foundation\scripts\sap_adt_cli.py adt_get --args-file .tmp\get.json
   ```
   Beklenen: `exists: true`. SAP CLI yalnız `ping` açıyorsa `sap-project.json` eksik ya da geçersizdir; `%yeni-proje`'yi tekrar çalıştır.
   Bağlantı teşhisi: `sap_adt_cli.py sap_doctor`.
4. **SAML/SSO ile giriş yapılan sistemler** (ör. S/4HANA Cloud, BTP ABAP): kurulum adımı **planlı**, bu tür ilk
   projede eklenecek. O zamana kadar bu sistemlere bağlanmaya çalışma, ekip sorumlusuna bildir.

Elle proje kurulumu (ayrıntılı denetim isteyenler için):
```powershell
cd C:\projeler\benim-projem
git init -b main
python $HOME\axet\scripts\new_project.py --sap   # sonra AGENTS.md ve sap-project.json'daki <…> alanlarını doldur
```
Davranış yüzeyi (`AGENTS.md`, `.axet-code.json`, denylist, `.githooks/`, `validators-local/`) her değiştiğinde
onayı `KURULUMU-TAMAMLA` ile ya da kendi terminalinde `behavior_manifest.py generate` ile ver.

### 3.3 Paket
```powershell
python $HOME\axet\scripts\new_package.py <PAKET> --title "<başlık>"
python $HOME\axet\scripts\new_package.py --index --check
```
Bu komutlar yerel paket klasörünü kurar. **Paketi SAP'de SE21 ile sen yaratırsın**; aXet paket ya da transport yaratmaz.

### 3.4 Kabul kontrolü
1. Projede yeni aXet oturumu aç (`axet-code -c <klasör>`) → ilk satırda `proje: <ad>` görünmeli.
2. Proje kökünde `python $HOME\axet\scripts\doctor.py` → 0 FAIL.
3. Proje klasöründe `python $HOME\axet\scripts\session_brief.py --no-fetch` hatasız çalışmalı.
4. SAP projesinde 3.2'deki `ping` ve `adt_get` testleri başarılı olmalı.

### 3.5 Değişiklik SAP'ye nasıl gider
Model SAP'yi okur, yazmaz. Kod değişikliği `%sap-abapgit-delivery` ile hazırlanır:
1. SAP'de abapGit ile paketin ZIP'ini dışa aktar, modele ver.
2. Model dosyaları düzenler, kesin yasak denetimlerinden geçirir ve içe aktarma ZIP'i üretir.
3. ZIP'i SAP'de abapGit ile içe aktarırsın; transport'u sen seçersin. Aktivasyon sonucunu modele verirsin.

SAP GUI otomasyonu gerekiyorsa model script'i yazar, **sen** çalıştırırsın.

## 4. Günlük kullanım

- **Açılış:** model ilk yanıttan önce oturum özetini çalıştırır; eksik iş ve devir notları oradan gelir.
- **Gün sonu:** `%gun-sonu` · devir notu `%handoff` · iş listesi `.axet-code/memory/project_is-listesi.md`.
- **Genel skill'ler:** `%yeni-proje` · `%recall` · `%remember` · `%verify-done` · `%explore` · `%code-review` ·
  `%commit-pr` · `%skill-audit` · `%write-skill` · `%hata-bildir` (aXet'e hata/öneri bildirimi; GitHub hesabı gerekmez).
- **Ofis işleri:** `%office-excel` (profil, dönüştürme, karşılaştırma, rapor) · `%office-docs` (Markdown → Word/PDF,
  ekran görüntülü kılavuz) · `%office-slides` (PowerPoint).
- **SAP işleri:** iş alımı `%sap-intake-triage`, okuma `%sap-adt-foundation`, teslim `%sap-abapgit-delivery`;
  nesne tipine özel skill'leri model seçer.
- **Marketplace skill'i:** kurmadan önce `%skill-audit`; proje kapsamında kur. Template skill'iyle aynı ad
  `doctor.py`'de FAIL olarak görünür.
- **Güncelleme:** aXet içinde `%guncelle` — tek güncelleme yolu. Klonu yeni yayına seçmeli taşır, SAP Python
  paketlerini denetler, tarayıcı testini hazırlar. Yeni kurallar bir sonraki oturumda yüklenir. Projeler için
  `%guncelle-proje`.

## 5. Sorun giderme

İlk bakılacak yer her zaman kurulum penceresindeki mesajdır; sonra `python $HOME\axet\scripts\doctor.py` çıktısı.

### Kurulum penceresi (`aXet-Kur.cmd`)
- **Windows uyarısı** ("bu dosya internetten geldi" / SmartScreen): **Daha fazla bilgi → Yine de çalıştır**.
- **Çıkış kodları:** `0` tamam · `1` durdu (mesaj sebebini söyler) · `2` ön koşul eksik (listedekileri portaldan kur,
  tekrar çift tıkla) · `3` yeni kurulan program bu pencerede görünmüyor (pencereyi kapat, tekrar çift tıkla) · `4`
  son kontrol (doctor) FAIL.
- **Sorular sorulmadı** ("Pencere etkileşimsiz"): dosya çift tıklamayla değil, yönlendirilmiş girdiyle (otomasyon)
  çalıştırıldı; git kimliği yazılmadı. Dosyaya çift tıklayarak tekrar çalıştır.
- SAP bağlantısının Python paketleri (`requests`, `urllib3`, `python-dotenv`) — **kendiliğinden kurulur**: kurulum
  aracı (`install.py`) eksik olanı bulduğu Python'un pip'iyle (`--user`) kurar ve **her `%guncelle` de** aynı denetimi
  koşar (`install.py --paketler`; config'e yazmaz). Paket sonradan eksik kalırsa `doctor` (ve oturum açılışı) SAP
  açıkken WARN verir: aXet'te `%guncelle` yaz ya da `aXet-Kur.cmd`'ye tekrar çift tıkla (terminal yolu: `kur.cmd`).
  İnternet ya da şirket proxy'si engellerse kurulum **durmaz**, sade bir UYARI verir: BT'den bu makine için pip proxy
  ayarını (ya da şirket paket aynasını) iste. "pip bulunamadı" diyorsa Python pip olmadan kurulmuştur: BT'den pip ile
  kurmasını iste. Çıktıdaki `BT için elle kurulum komutu (sen çalıştırma)` satırı BT'nin aynı işi elle yapması içindir.
- **PATH:** `python` ya da `git` komutu yeni pencerede çalışmıyorsa kurulum aracı bulduğu klasörü **kullanıcı**
  PATH'ine ekler (yönetici gerekmez, mevcut girdilerin metnini değiştirmez): Python'unkini (ve `Scripts`) başa, Git'inkini
  sona. Python klasörü PATH'inde zaten var ama önünde çalışmayan bir `python` (ör. Windows mağaza kısayolu) duruyorsa
  klasörü başa taşır; `-Kaldir` taşınan girdiyi silmez (o senin girdindi). Ekleme kaydı klonun içinde
  durur; `kur.cmd -Kaldir` yalnız bu eklediklerini geri alır — klonu silmeden ÖNCE çalıştır. Araç "UYARI: yeni
  terminalde 'python' hâlâ başka bir yere gidiyor" derse makine PATH'inde önde eski bir Python vardır: BT'den o
  girdiyi kaldırmasını iste. Birden çok klon kullanıyorsan PATH'e yalnız ilk kuran klon ekler ve yalnız onun
  `-Kaldir`'ı geri alır.

### Terminal yolu ve kurulum aracı seçenekleri
Çift tıklama yerine **PowerShell**'de aynı iş (betiği geçici klasöre indirip çalıştırır):
```powershell
$f = Join-Path $env:TEMP 'axet-kur.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/ozgurylmz34/axet-template/main/kur.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```
Klonun kendisi bozulduysa (yerel `kur.ps1` dahil) aynı satırın **sıfırlayan** varyantı: klonu template ile birebir
aynı hâle getirir, önce her şeyi `yedek/<tarih-saat>` dalına alır:
```powershell
$f = Join-Path $env:TEMP 'axet-kur.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/ozgurylmz34/axet-template/main/kur.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f -Sifirla
```
Tek satır komutlar klonu varsayılan yere (`%USERPROFILE%\axet`) kurar: `-Hedef` ile başka bir yere kurduysan
aynı `-Hedef`'i bu komuta da ver, yoksa ikinci bir klon kurulur.

Aynı araç klondan da çalışır:
```powershell
& $HOME\axet\kur.cmd                 # kurulumu yenile (git pull --ff-only + install.py + doctor)
& $HOME\axet\kur.cmd -DenemeModu     # hiçbir şey yazmadan ne yapacağını göster
& $HOME\axet\kur.cmd -Sifirla        # klonu template ile birebir aynı hâle getir (önce yedek dalı açılır)
& $HOME\axet\kur.cmd -Kaldir         # config'ten template kayıtlarını ve eklenen PATH girdilerini çıkar (klasör silinmez)
& $HOME\axet\kur.cmd -Hedef D:\araclar\axet   # başka klasöre kur
```
Araç yerel değişikliği olan bir klonu **kendiliğinden** güncellemez, `reset` ya da `stash` yapmaz; durur ve iki
yolu söyler: değişikliklerini korumak istiyorsan onları kendin commit ya da stash et ve `kur.cmd`'yi tekrar
çalıştır; korumak istemiyorsan `kur.cmd -Sifirla`.

`-Sifirla` hiçbir şeyi silmeden önce yerel değişiklikleri, izlenmeyen dosyaları ve yerel commit'leri `yedek/<tarih-saat>`
dalına alır ve yedeği doğrular; onayı senden ister (`SIFIRLA` yazarsın; `-DenemeModu` yalnız durumu gösterir).
gitignore'lu dosyalarına dokunmaz (`.axet-guncelleme/` hariç: o yalnız **içindeki her şey yedek dalından geri
alınabilir hâlde** yedeğe girdiyse silinir; giremediyse olduğu gibi bırakılır ve sana sebebiyle birlikte adıyla
bildirilir) ve klon klasörünün dışına çıkmaz.
Tek istisna: klonun içine dışarıyı gösteren bir bağ (junction/symlink) koyduysan git o bağın içine girer ve
oradaki dosyaları da yedeğe alır — böyle bir bağın varsa önce kaldır. Klonun içindeki **ayrı bir git deposunu**
araç silmez; bu `.axet-guncelleme/` içindekiler için de geçerlidir: git böyle bir klasörü yedeğe yalnız bir bağ
(gitlink — 40 baytlık commit kimliği) olarak alır, dosyaları ve geçmişi yedek dalına GİRMEZ; silinseydi yedekten
geri getirilemezdi. Araç kalanı sana adıyla bildirir. Klon işlem sonunda `main` dalında olur
(güncellemenin çalışması için gerekli); klonun dalı başkaysa o dalın işi yedek dalında durur.
Tek bir dosyayı geri almak için son mesajdaki komutu kullan:
`git -C "$HOME\axet" restore --source yedek/<...> -- <yol>`.

Yalnız şirket dışı, kişisel bir makinede: `kur.cmd -Winget` eksik Git/Python'u winget ile kurmayı sorar.

Elle kurmak istersen:
```powershell
git clone https://github.com/ozgurylmz34/axet-template.git $HOME\axet
python $HOME\axet\scripts\install.py --sap      # --dry-run önce gösterir, --uninstall geri alır
python $HOME\axet\scripts\doctor.py             # statik kontroller
python $HOME\axet\scripts\doctor.py --live      # aXet'in çekirdeği fiilen yüklediğini ölçer (1 model çağrısı)
```
`install.py` yalnız kendi eklediği yolları ve kuralları yönetir, diğer ayarlarına dokunmaz; yazmadan önce yedek alır.

### Belirti → çözüm
| Belirti | Bak |
|---|---|
| Kurulum penceresi aXet, Git ya da Python eksik dedi (çıkış 2) | Listedekileri şirket portalından (Software Center / Company Portal) kur ya da BT'den iste, sonra `aXet-Kur.cmd`'ye **tekrar çift tıkla**. Python en az 3.12 olmalı |
| Kurulum aracı `PAKETLER: EKSİK` dedi ya da SAP aracı `No module named 'requests'` (ya da `'dotenv'`) diyor | Yukarıdaki "SAP bağlantısının Python paketleri" maddesi: çoğunlukla şirket proxy'si; BT'den pip proxy ayarını iste, sonra aXet'te `%guncelle` yaz |
| `python` ya da `git` "bulunamadı" diyor ama kurulu | `aXet-Kur.cmd`'ye tekrar çift tıkla: kullanıcı PATH'ine kendisi ekler. Sonra **yeni** pencere / yeni aXet oturumu aç. `yeni-proje.cmd` ve `proje-tamamla.cmd` bu arada `py -3` ile de çalışır |
| Kurulum aracı yeni pencere istedi (çıkış 3) | Pencereyi kapat, `aXet-Kur.cmd`'ye tekrar çift tıkla |
| Başka bir klonun kayıtlı olduğu uyarısı (çoğunlukla çıkış 4) | Config eski bir klonu da gösteriyor (ör. önceki sürümle `C:\axet`'e kurulmuş). Doctor'daki skill ad çakışması FAIL'leri bundan gelir: skill'leri yeniden adlandırma. Uyarıdaki `--uninstall` komutunu o klon için kendin çalıştır (o klonun `config/sap-write.local` dosyası da silinir), sonra kurulumu tekrar çalıştır. Eski yerde kalmak istersen `kur.cmd -Hedef C:\axet`. Uyarıdaki klon klasörü artık yoksa (silinmiş ya da taşınmış) araç "kayıt bayat" der ve `--uninstall` önermez: sondaki BAYAT KAYIT listesindeki girişleri config dosyasından elle sil (araç config'e kendisi yazmaz), sonra yeni aXet oturumu aç |
| Kurulum aracı "klon karşılaştırması ÖLÇÜLEMEDİ" dedi | Hedef yol (junction/symlink) Python ile çözülemedi. Config'teki kayıtlı klonun bu klonun kendisi olup olmadığını elle kontrol et; araç bu durumda hiçbir kaydı kaldırmayı önermez |
| Kurulum aracı "git çalıştırılamadı" dedi | Listelenen git.exe kendi terminalinde `git --version` ile çalışıyor mu bak. "unable to access …/git/config" görüyorsan XDG_CONFIG_HOME değerindeki geçersiz karakteri düzelt |
| Kurulum aracı "son kontrol (doctor) sorun buldu" dedi (çıkış 4) | Kurulum yazıldı ama doğrulama geçmedi: çıktıdaki `[FAIL]` satırları; başka klon uyarısı varsa bir üst satır |
| `KURULUMU-TAMAMLA` "YAPMAN GEREKEN" deyip durdu | Pencerenin tam yoluyla gösterdiği `conn\DEV.env`'i doldur, kaydet, tekrar çift tıkla (§3.2) |
| İlk satırda `proje: YOK` | Oturum proje kökünde mi açıldı; `AGENTS.md`'de `PROJECT-ID` satırı var mı |
| İlk satırda `AXET-CORE` yok | Kurulum tamamlandı mı; `python $HOME\axet\scripts\doctor.py` çıktısındaki global config satırları |
| SAP CLI yalnız `ping` açıyor | `sap-project.json` yok ya da `sap_profile` / `master_language` geçersiz |
| Yazma reddi `tier_not_writable` | `.conn_adt` içindeki sistem tipi DEV değil ya da okunamıyor |
| Skill listede yok | `doctor.py` (frontmatter biçimi, açıklama ≤ 1024 karakter); aXet logu `.axet-code/logs/axet-code.log` |
| Skill ad çakışması FAIL | Çakışan skill başka bir template klonundaysa: yukarıdaki "başka bir klon" satırı. Dış skill ise yeniden adlandır ya da kaldır (marketplace kurulumu: `skill_uninstall <ad>`) |
| Denylist değişikliği etkisiz | Yeni oturum aç |

## 6. Kontrol listesi

- [ ] aXet, Git ve Python 3.12+ şirket portalından kurulu
- [ ] `aXet-Kur.cmd` "Kurulum TAMAM — aXet'i aç." dedi (git kimliği soruldu ya da doğrulandı)
- [ ] Yeni oturumun ilk satırında `AXET-CORE` görünüyor
- [ ] İlk proje `%yeni-proje` ile kuruldu; projede `proje: <ad>` görünüyor
- [ ] (SAP) `KURULUMU-TAMAMLA`: `conn\DEV.env` dolduruldu, ayarlar onaylandı, doctor 0 FAIL
- [ ] (SAP) `.conn_adt` git'e kapalı; `ping` ve `adt_get` başarılı
- [ ] (SAP) Paket SAP'de SE21 ile açıldı, yerelde `new_package.py` ile kuruldu
- [ ] Teslim yolunu biliyorum: abapGit ZIP, içe aktarımı ben yaparım
