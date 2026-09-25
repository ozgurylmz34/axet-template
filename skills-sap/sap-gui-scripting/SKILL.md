---
name: sap-gui-scripting
description: >
  Use when a classic SAP GUI screen fact cannot be read with the ADT CLI read tools: field values,
  status bar or popup text of an open Dynpro screen, an ALV grid or table control dumped to a file,
  or a developer-recorded GUI flow that must become a reviewed script. The model writes a VBScript
  that attaches to the developer's already open SAP GUI session, checks it with the offline checker
  and hands it over; the developer reviews and runs it, then the model reads the output file. The
  model never runs SAP GUI scripts itself. Triggers: "GUI script yaz", "ekrandaki alanı oku",
  "ALV'yi dosyaya dök", "table control oku", "SAP GUI scripting", "kaydı script'e çevir". Do not use
  for anything the ADT CLI can read (use sap-adt-foundation), changing standard table data,
  transports, packages or lock entries.
---

# SAP GUI scripting — model yazar, geliştirici çalıştırır

> **Profil:** klasik SAP GUI ekranları yalnız `ecc` ve `s4_private` profillerinde vardır. `sap-project.json` `sap_profile`
> değeri `s4_public` ya da `btp_abap` ise DUR, kullanıcıya bildir.
> **Kullanıcı kararı (değişmez):** model SAP GUI'yi kendisi sürmez. Script'i `bash` ile çalıştırmaz, `cscript`, `wscript`
> ya da `powershell` ile başlatmaz. Script'i yazar, denetler, teslim eder; geliştirici okur ve kendi terminalinde çalıştırır.
> Kesin yasaklar (A/B/C/D) SAP çekirdeğinde yüklüdür ve GUI yolunda da aynen geçerlidir: GUI, API'de yasak olanı
> yapmanın arka kapısı değildir.

## When to use this skill
- Bilgi yalnız ekranda: klasik Dynpro alan değeri, durum çubuğu mesajı, açılır pencere metni, ALV'nin ekranda
  gösterdiği kolon ve satırlar, table control içeriği.
- Geliştiricinin SAP GUI'de kaydettiği bir akışın gözden geçirilmiş, tekrar çalıştırılabilir script'e çevrilmesi.
- **Kullanma:** kaynak kod, obje metadata'sı, tablo okuma, where-used, aktivasyon durumu → `%sap-adt-foundation`
  (CLI okuma araçları önce denenir). Standart tablo verisini değiştirme (yasak B), transport, paket ya da kilit işlemi
  (yasak C), standart obje değişikliği (yasak A) için GUI script'i YAZILMAZ: DUR, kullanıcıya açıkla.

## How to use this skill

### 0. Ön koşullar (model yapmaz, yalnız kontrol ettirir)
| Koşul | Kim yapar | Eksikse ne görülür |
|---|---|---|
| Windows + SAP GUI for Windows; geliştirici sisteme **kendisi** giriş yapmış, okunacak ekran açık | geliştirici | çıktıda `# HATA` satırı: bağlantı ya da oturum yok |
| Sunucuda scripting açık: profil parametresi `sapgui/user_scripting` (RZ11) | Basis / yetkili kullanıcı | scripting motoru ya da oturum alınamaz (API hata tipi `Gui_Err_Scripting_Disabled_Srv`) |
| Kullanıcının scripting yetkisi (`S_SCR`) ve istemci tarafında scripting seçeneği açık | Basis / geliştirici | aynı; istemci seçeneğinin menü yolu DOĞRULANMADI |

#### 0.1 Ön-teşhis: script yazmadan ÖNCE hangi yolda olduğunu belirle

Amaç **patinajı kesmek**: "GUI scripting çalışmıyor" durumunda arka arkaya script varyantı denemek
hipotezi test etmez, yalnız ona duyulan güveni büyütür (çekirdek: kontrol grubu / PATTERN #19).
Aşağıdaki tablo tek bir belirtiden hangi yola gidileceğini söyler. **Bu bir teşhistir, bir eylem değil:**
model GUI'yi sürmez ve aşağıdaki hiçbir düzeltmeyi kendisi YAPMAZ — kullanıcıya ne yapacağını söyler.

| Belirti (geliştiricinin gördüğü) | Teşhis | Yol |
|---|---|---|
| Script çalıştı, ekran okundu | scripting açık ve oturum var | **devam** — normal akış (§1 ve sonrası) |
| `Gui_Err_Scripting_Disabled_Srv` | sunucuda scripting kapalı | **kullanıcıya metin ver:** Basis'ten `RZ11` → `sapgui/user_scripting` = `TRUE` istenir. ⚠ Bu bir **sistem durumu** değişikliğidir (Yasak C komşuluğu) — model `RZ11`'e girmez, parametreyi değiştirmez, değiştiren script yazmaz |
| `GetScriptingEngine` düşüyor ya da 0 bağlantı/oturum dönüyor, ama SAP Logon açık | istemci tarafında scripting kapalı ya da oturum yok | **kullanıcıya metin ver:** SAP Logon → Options → Accessibility & Scripting → Scripting → "Enable scripting" işaretli olmalı; sonra sisteme giriş yapıp okunacak ekranı aç. ⚠ menü yolu **DOĞRULANMADI** (sürüme göre değişebilir) |
| `Gui_Err_AccessDenied` / `Gui_Err_Permission_Denied` | kullanıcı yetkisi yok (`S_SCR`) | **kullanıcıya metin ver:** yetki Basis'ten istenir; script tarafında çare yok |
| `Gui_Err_Disconnected` | oturum koptu (script yazıldıktan sonra) | geliştirici yeniden bağlanır; script'i değiştirme — aynı script tekrar koşulur |
| `Gui_Err_FindById` | ekran beklenen ekran değil ya da id yanlış | **script hatası** — id'yi doğrula (§`references/api-objects.md`), ekranın gerçekten açık olduğunu geliştiriciye teyit ettir |
| Klasik SAP GUI hiç yok (yalnız tarayıcı/Fiori) | GUI scripting yolu **kapalı** | `%sap-fs-ts-docs` → `capture_kd_screens.js` (WebGUI/tarayıcı yolu). Bu skill'i kullanma |
| Profil `s4_public` ya da `btp_abap` | klasik GUI yok | DUR, kullanıcıya bildir (yukarıdaki profil notu) |

⚠ **KAPSAM BEYANI — bu tablo neye BAKMAZ:** hata tipi adları `references/api-objects.md:99-100`'den
alınmıştır ve orada **DOĞRULANMADI** olarak işaretlidir (tip kütüphanesinden okundu, canlı sistemde
tetiklenmedi). Yani "bu belirti bu hatayı verir" eşlemesi **ölçülmemiştir**; belirti tutmuyorsa hatanın
ham metnini oku ve bu tabloyu düzelt. Tabloda olmayan bir hata tipi "sorun yok" demek DEĞİLDİR.

⛔ **ALINMAYAN parça (bilinçli, 2026-09-15):** Bu teşhisin geldiği dış pakette bir de "tek koşuda bir
işlemi gezip her adımı yakalayan" toplu sürücü var. **Alınmadı** — modelin GUI'yi sürmesi anlamına
gelirdi ve bu, yukarıdaki değişmez kullanıcı kararına aykırıdır.

Model bu parametreyi değiştirmeyi önermez, script'le değiştirmez; yalnız "kapalı olabilir, Basis'e danışın" der.

### 1. Önce ADT
Aynı bilgi `sap_adt_cli.py` okuma aracıyla alınabiliyorsa GUI kullanılmaz. GUI yalnız ekran gerçeği içindir.

### 2. İhtiyacı netleştir (tek seferde sor)
- Hangi işlem kodu ve ekran. **Ekranı geliştirici açar, seçim değerlerini kendisi girer**; varsayılan şablonlar
  gezinmez, alana yazmaz, düğmeye basmaz.
- Hangi çıktı (ekran alanları · ALV · table control) ve satır sınırı.
- Sistem QA/PRD ise ve ekranda kişisel veri varsa SAP çekirdeğindeki hassas veri kuralı: önce açık onay.

### 3. Şablondan script üret
| İhtiyaç | Şablon (`templates/`) | Çıktı |
|---|---|---|
| Açık ekranın alanları + durum çubuğu | `read-screen.vbs` | satır başına `id<TAB>tip<TAB>metin` |
| ALV grid dökümü | `dump-alv-grid.vbs` | CSV (`;` ayraç, UTF-8): 1. satır teknik kolon adları, 2. satır başlıklar |
| Klasik table control dökümü | `dump-table-control.vbs` | CSV: 1. satır kolon başlıkları |

- Şablonu projede **git'e kapalı** klasöre kopyala: `<proje>/.tmp/gui/<ad>.vbs` (proje şablonunun `.gitignore`'unda
  `.tmp/` var; projede yoksa kullanıcıya sor). Çıktı dosyası da aynı klasöre yazılır; ekran verisi repoya girmez.
- Başlık bloğunu doldur (`AMAC`, `MOD`, `GERI-ALINAMAZ`, `CIKTI`). Şablon mantığını değiştirme. ALV ya da table control
  ID'si gerekiyorsa geliştiriciden al (kayıt dosyasından ya da ekrandan): **ID uydurma**.
- Yeni bir nesne/metot/özellik adı gerekiyorsa `references/api-objects.md`'deki doğrulanmış listeden al. Listede yoksa
  kullanma ya da teslim notunda DOĞRULANMADI diye işaretle.
- Çıktının ilk satırı `# BASLANGIC`, son satırı `# BITTI`'dir. Hata olursa script `# HATA` satırını yazıp durur.
  Çıktı dosyası zaten varsa script üzerine yazmaz, durur.

### 4. Kayıttan akış (`MOD: akis`)
Geliştirici akışı SAP GUI'nin kendi kayıt özelliğiyle kaydedip `.vbs` dosyasını verir. Model giriş ve bağlantı açma
satırlarını çıkarır, şablonlardaki "mevcut oturuma bağlan" bloğunu koyar, sabit kimlik değerlerini siler, her ekran
geçişinden sonra hata kontrolü ekler, `MOD: akis` ve `GERI-ALINAMAZ:` satırlarını doldurur. Adımlar:
`references/handoff.md` §3.
Kayıttaki akış standart veriyi değiştiriyorsa (kaydet, sil, yeni belge) script YAZILMAZ; yasak B sırası geçerlidir:
released API (released RAP BO/EML · released BAPI · released OData) → BAPI → RFC FM → işlem kodu (BDC) → kullanıcıdan
manuel (`%sap-dev` → `references/write-api-selection.md`). `akis` modu yalnız kullanıcının açıkça onayladığı Z işlem
akışı içindir.

### 5. Çevrimdışı denetim (teslimden önce zorunlu)
```
python <TEMPLATE>/skills-sap/sap-gui-scripting/scripts/check_gui_script.py <script.vbs> [--mode okuma|akis]
```
Çıkış 0 = BLOCKER yok · 1 = BLOCKER var (teslim edilmez) · 2 = kullanım hatası. Mod başlıktaki `MOD:` satırından
okunur; `--mode` verilirse o geçerlidir. Çıktının sonundaki **BAKILMAYANLAR** listesini teslim notuna koy:
denetleyicinin "0 bulgu" demesi script'in doğru olduğu anlamına gelmez.
Denetleyici reddini aşmak için yazımı değiştirme (birleştirme, `Chr()`, değişkene bölme): DUR, kullanıcıya bildir.

### 6. Geliştiriciye teslim
`references/handoff.md` §1 şablonuyla: script yolu · ne yapacağı (adım adım) · çalıştırma komutu · beklenen çıktı ·
ekranda değişiklik · geri alınamaz adım · denetleyici sonucu ve bakılmayanlar · DOĞRULANMADI varsayımlar. Script'i model
çalıştırmaz, "çalıştırayım mı" diye de sormaz.

### 7. Sonucu oku
Geliştirici "çalıştı" dediğinde çıktı dosyasını `view` / `grep` ile oku (`references/handoff.md` §4). `# BITTI` yoksa
ya da `# HATA` varsa sonuç eksiktir, tam sayma. `# SATIR_TOPLAM` ile `# SATIR_YAZILAN` farklıysa raporda yaz. Büyük
çıktıyı bağlama dökme; ilgili kısmı `grep` ile oku. Kişisel veriyi rapora ya da hafızaya yazma.

## Referanslar
| Dosya | İçerik |
|---|---|
| `references/api-objects.md` | şablonlarda kullanılan GUI Scripting nesne/metot/özellik adları, okunur-yazılır bilgisi, kaynağı, canlı doğrulama durumu |
| `references/handoff.md` | teslim notu şablonu, çalıştırma komutu, kayıttan akış dönüşümü, sonuç okuma kontrol listesi |
| `templates/read-screen.vbs` · `dump-alv-grid.vbs` · `dump-table-control.vbs` | salt-okur şablonlar: mevcut oturuma bağlanır, her adımda kontrol eder, hata olursa durur, çıktıyı dosyaya yazar |
| `scripts/check_gui_script.py` | çevrimdışı statik denetleyici (VBScript, PowerShell, Python) |
| `tests/test_check_gui_script.py` | denetleyici testleri: `python -m unittest discover -s <TEMPLATE>/skills-sap/sap-gui-scripting/tests -v` |

## Rules
- Model SAP GUI script'ini **çalıştırmaz**. Her çalıştırma geliştiricinin kararıdır; bir çalıştırmanın onayı sonrakine taşınmaz.
- Script geliştiricinin açtığı mevcut oturuma bağlanır. Yeni bağlantı açma (`OpenConnection`,
  `OpenConnectionByConnectionString`), giriş ekranını doldurma, kullanıcı adı, şifre, sistem, client ya da sunucu adresi
  yazma YASAK: ne script'te ne teslim notunda.
- Varsayılan mod `okuma`: alana yazma, düğmeye basma, işlem kodu başlatma, tuş gönderme yok. `akis` modundaki her
  etkileşim teslim notunda tek tek listelenir.
- Kilit silme, transport ve paket işlem kodları (yasak C) ile standart tablo bakım ve düzenleme işlem kodları (yasak B)
  hiçbir modda script'e girmez.
- Script `GuiSessionInfo`'dan kullanıcı, client, sistem ya da sunucu bilgisi yazmaz; yalnız `Transaction`, `Program`,
  `ScreenNumber` (hangi ekranın okunduğunu doğrulamak için).
- Nesne/metot adı, element ID'si, tuş kodu tahmin edilmez: `references/api-objects.md`'de ya da geliştiricinin kayıt
  dosyasında yoksa kullanılmaz.
- Script ve çıktı git'e kapalı klasörde durur; silme kullanıcı onayı ister.
- Script hata verdiyse yeniden teslimden önce `# HATA` satırını oku ve nedeni yaz. Üçüncü başarısız denemede DUR.
