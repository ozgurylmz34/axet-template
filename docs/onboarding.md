# Yeni geliştirici: ilk gün rehberi

Makineyi hazırlamaktan ilk projede günlük çalışmaya kadar her adımı sırayla anlatır. Her adımın **nasıl
doğrulanacağı** da yazılıdır. Kurulumdan sonra etkileşimli rehber istersen aXet oturumunda `%onboard` yaz:
model aynı adımları senin makinende kontrol ederek yürütür.

Bu belgedeki yollar template'in varsayılan yere, `%USERPROFILE%\axet` klasörüne kurulduğunu varsayar
(PowerShell'de `$HOME\axet`). Başka yere kurduysan yolu değiştir.

> Kimlik bilgilerini (kullanıcı adı, şifre, token, bağlantı ayrıntısı) **sohbete yazma**. Prompt'lar kurumsal
> denetime gider. Bu belgede kimlik bilgisi isteyen her adım senin kendi terminalinde yapılır.

---

## 0. Makine ön koşulları

| Gerekli | Kontrol | Nasıl sağlanır |
|---|---|---|
| aXet.code (girişi yapılmış) | `axet-code -v` | şirket kanalından; kurulum aracı aXet'i kurmaz |
| Git | `git --version` | şirketinin yazılım merkezinden (Software Center / Company Portal) ya da BT'den |
| Python ≥ 3.12 | `python --version` | şirketinin yazılım merkezinden (Software Center / Company Portal) ya da BT'den |
| Windows PowerShell | Windows ile gelir | — |

Kurulum aracı Git ve Python'u **kurmaz**: eksikse durur ve yazılım merkezini gösterir. Şirket makinesinde başka
yoldan (winget, internetten indirme) kurma; şirketin izin verdiği sürüm yazılım merkezindekidir. Yalnız şirket
dışı, kişisel bir makinede `kur.cmd -Winget` eksikleri winget ile kurmayı sorar.

**Git kimliği (bir kez):** Git kurulduktan sonra adını ve iş e-postanı tanıt:

```powershell
git config --global user.name "Ad Soyad"
git config --global user.email "ad.soyad@sirket.com"
git config --global user.email    # kontrol: adresini basmalı
```

Değer `git config --global` dosyasına (genelde `%USERPROFILE%\.gitconfig`) yazılır ve bu makinedeki tüm
repolarda geçerlidir. Girmezsen kurulum ve aXet etkilenmez; ama commit'lerin hata vermeden Windows'un türettiği adresle atılır ve proje uzak sunucuya push edilirse
o adres geçmişe girer (sonradan silinemez). Kimlik tanımsızsa `doctor.py` projede remote varsa uyarır (WARN),
yoksa bilgi verir (INFO). **GitHub hesabı gerekmez:** template herkese açık klonlanır.

Önerilen: `rg` (ripgrep). Yoksa aXet'in arama aracı yavaşlar; kurulum aracı hatırlatır ama durmaz.
Bir şey kurulduktan sonra **yeni terminal ve yeni aXet oturumu** aç: PATH ancak o zaman görünür.

İsteğe bağlı paketler (yalnız ilgili iş gelince kur; kurmak senin kararın):

| Paket | Hangi iş |
|---|---|
| `python-docx` | `%office-docs` ile Word çıktısı |
| `python-pptx` | `%office-slides` ile PowerPoint çıktısı |
| `openpyxl` | `%office-excel report` (biçimli Excel raporu) |
| Microsoft Edge ya da Chrome | `%office-docs` ile PDF çıktısı (Windows'ta Edge standart) |

Kurulum biçimi: `python -m pip install --user <paket>`.

## 1. Kurulum

En kolayı: `aXet-Kur.cmd` dosyasını (template deposunun kökünde; ya da ekibinden) indir ve **çift tıkla**. Windows
"internetten geldi" uyarısı verirse **Daha fazla bilgi → Yine de çalıştır**. Terminal yolu aynı işi yapar —
PowerShell'i aç ve şu satırı yapıştır:

```powershell
$f = Join-Path $env:TEMP 'axet-kur.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/ozgurylmz34/axet-template/main/kur.ps1' -OutFile $f; powershell -NoProfile -ExecutionPolicy Bypass -File $f
```

Kurulum aracının yaptıkları:
1. aXet'i arar; bulamazsa durur.
2. Git ve Python'u arar; eksikse durur ve yazılım merkezinden (ya da BT'den) kurmanı söyler, resmi indirme
   adresini de yazar (çıkış kodu 2). Kurduktan sonra yeni bir PowerShell aç ve aynı satırı tekrar yapıştır.
3. Template'i `%USERPROFILE%\axet` klasörüne klonlar (makinede **bir kez**; tüm projeler aynı klonu kullanır).
4. `install.py --sap` çalıştırır: global aXet config'ine yalnız kendi yollarını ve izin kurallarını ekler, önce yedek alır.
5. `doctor.py` ile kontrol eder.

Durursa ekrandaki mesaj ne yapacağını söyler. "Yeni terminal aç" derse (çıkış kodu 3), yeni bir PowerShell
penceresinde `& $HOME\axet\kur.cmd` komutunu çalıştır. Çıkış kodu 3 değilse aynı başlatma satırını tekrar yapıştır.

Planı önce görmek istersen: `& $HOME\axet\kur.cmd -DenemeModu` (klon varsa). Geri almak için:
`& $HOME\axet\kur.cmd -Kaldir` (config kayıtlarını çıkarır, klasörü silmez).

**SAP'ye yazma varsayılan kapalıdır ve kapalı kalmalıdır.** Yazma yalnız sandbox (DEV) sistemi için ve yalnız
ekip kararıyla, **kendi terminalinde** açılır: `python $HOME\axet\scripts\install.py --sap --sap-write`
(kapatmak için: `--no-sap-write`). aXet oturumu bu komutu çalıştıramaz. Normal teslim yolu 5.4'teki abapGit ZIP'idir.

## 2. İlk oturum doğrulaması

Sırayla:

1. **Statik kontrol:** `python $HOME\axet\scripts\doctor.py` → FAIL satırı olmamalı. Proje dışında çalıştırınca
   proje kontrolleri atlanır; bu normaldir.
2. **Yeni aXet oturumu aç.** Kurulumdan önce açılmış oturum yeni ayarları görmez. İlk yanıtın ilk satırı şu
   kalıptadır:
   ```
   [AXET-CORE-… · SAP: … · proje: … · proje hafızası: …]
   ```
   Satır yoksa çekirdek yüklenmemiştir; `doctor.py` çıktısındaki global config satırlarına bak.
3. **Canlı ölçüm (isteğe bağlı, 1 model çağrısı):** `python $HOME\axet\scripts\doctor.py --live` → aXet'in
   çekirdeği fiilen yüklediğini ölçer.

## 3. İlk proje

### 3.1 Proje kur
Projede çalışacağın klasörde aXet'i aç ve **`%yeni-proje`** yaz. Model şunları sırayla sorar:
- proje klasörü ve adı;
- SAP sistem profili, sürümü, master dili, clean core politikası;
- projenin amacı, depo adresi, test ve çalıştırma komutları.

Model önce ne yapacağını gösterir. Onay verince klasörü kurar, alanları doldurur ve `doctor.py` ile kontrol eder.
Terminali tercih edersen aynı işi `& $HOME\axet\yeni-proje.cmd` yapar.

`master_language` tüm Z nesnelerinin metin dilidir; emin değilsen ekip sorumlusuna sor. Var olan dosyalarda
senin yazdığın değerler ezilmez; araç farkı raporlar.

### 3.2 SAP kimlik bilgileri
Her SAP sistemi `conn\<AD>.env` dosyasıdır; aktif bağlantı proje kökündeki `.conn_adt`'dir. `conn/` ve `.conn_adt`
git'e girmez, aXet ajanına kapalıdır (denylist), içeriği sohbete yazılmaz.

1. **Proje klasöründeki `KURULUMU-TAMAMLA.cmd`'ye çift tıkla** (`%yeni-proje` yazar; yoksa
   `& $HOME\axet\proje-tamamla.cmd <klasör>`). Pencere SAP bilgisi sormaz:
   - `conn\DEV.env` ve `conn\QA.env` şablonlarını yazar (var olanı ezmez) ve Notepad'de açar. Dil
     (`sap-project.json` master_language), tier ve sistem adı (`<proje>_DEV`) hazır gelir.
   - `<...>` yerleri doldur, kaydet, kısayola tekrar çift tıkla. Hatalı alanlar adıyla gösterilir (değer basılmaz),
     boş şablon atlanır; QA sistemi yoksa `QA.env`'e dokunma. Geçerli DEV aktif sistem olur.
   - Parola dosyada düz metin durur. Dosyaya yazmak istemezsen terminal yolu:
     `python $HOME\axet\skills-sap\sap-adt-foundation\scripts\setup_credentials.py --slot <AD>` (parola ekrana
     yansımaz; etkileşimsiz çağrıyı reddeder).
   - Sistem değiştirmek: aXet'te `%sistem` ya da "QA'ya geç". QA/PRD salt-okunurdur.
2. **Davranış yüzeyini onayla:** aynı pencere onaylanacak dosyaları listeler ve sorar (`behavior_manifest.py
   generate`). Proje kuralları (`AGENTS.md`, `.axet-code.json`, denylist, `.githooks/`) her değiştiğinde kısayola
   tekrar çift tıkla; değişenler `!` ile gösterilir.
   Çift tıklanan pencerede Notepad'in açılışı ve `axet-code -c` açılışı DOĞRULANMADI.
3. **Doğrula** (proje kökünde):
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
4. **SAML/SSO ile giriş yapılan sistemler** (ör. S/4HANA Cloud, BTP ABAP): kurulum adımı **planlı**, bu tür ilk
   projede eklenecek. O zamana kadar bu sistemlere bağlanmaya çalışma, ekip sorumlusuna bildir.

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
  `%commit-pr` · `%skill-audit` · `%write-skill`.
- **Ofis işleri:** `%office-excel` (profil, dönüştürme, karşılaştırma, rapor) · `%office-docs` (Markdown → Word/PDF,
  ekran görüntülü kılavuz) · `%office-slides` (PowerPoint).
- **SAP işleri:** iş alımı `%sap-intake-triage`, okuma `%sap-adt-foundation`, teslim `%sap-abapgit-delivery`;
  nesne tipine özel skill'leri model seçer.
- **Marketplace skill'i:** kurmadan önce `%skill-audit`; proje kapsamında kur. Template skill'iyle aynı ad
  `doctor.py`'de FAIL olarak görünür.
- **Güncelleme:** `& $HOME\axet\kur.cmd` klonu günceller ve kurulumu yeniler. Yeni kurallar bir sonraki oturumda yüklenir.

## 5. Sorun giderme

Belirti → çözüm tablosu: [README "Sorun giderme"](../README.md#sorun-giderme). İlk bakılacak yer her zaman
`python $HOME\axet\scripts\doctor.py` çıktısıdır.

## 6. Kontrol listesi

- [ ] `axet-code -v`, `git --version`, `python --version` çalışıyor
- [ ] `git config --global user.email` adresimi basıyor (git kimliği tanımlı)
- [ ] Kurulum aracı bitti; `doctor.py` 0 FAIL
- [ ] Yeni oturumun ilk satırında `AXET-CORE` görünüyor
- [ ] İlk proje `%yeni-proje` ile kuruldu; projede `proje: <ad>` görünüyor
- [ ] (SAP) `KURULUMU-TAMAMLA.cmd`: `conn\DEV.env` dolduruldu, ayarlar onaylandı, doctor 0 FAIL
- [ ] (SAP) `.conn_adt` git'e kapalı; `ping` ve `adt_get` başarılı
- [ ] `session_brief.py --no-fetch` hatasız
- [ ] (SAP) Paket SAP'de SE21 ile açıldı, yerelde `new_package.py` ile kuruldu
- [ ] Teslim yolunu biliyorum: abapGit ZIP, içe aktarımı ben yaparım
