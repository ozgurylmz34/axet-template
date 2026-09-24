# aXet.code Template

aXet.code'un Claude Code'a olabildiğince yakın çalışması için ortak kurallar, skill'ler, hafıza düzeni ve
kurulum araçları. Repo makinede **bir kez** klonlanır; kurulum aracı kullanıcının global aXet config'ini
bu klasöre bağlar. Güncelleme tek komutla tüm projelere birden yansır.

> Sürüm: 0.3.0 · Ölçüldüğü aXet.code sürümü: 1.3.0 · Lisans: [MIT + ek koşullar](#lisans)

## Ne sağlar

| Claude Code'da | Bu template'te | Mekanizma |
|---|---|---|
| `CLAUDE.md` + çekirdek kurallar | `core/00-temel.md` (+ SAP: `core/sap/`) | global `context_paths` |
| Proje talimatı | proje kökünde `AGENTS.md` | aXet otomatik yükler |
| Skills | `skills/` (+ SAP: `skills-sap/`) | global `skills_paths`, `%ad` ile çağrı |
| Auto-memory | `memory/` (ekip) + `<proje>/.axet-code/memory/` (proje), `%remember` | `context_paths` ile yüklenen indeksler |
| Hook/guard ile engelleme | `config/permissions.json` deny kuralları (`bash`) + `.axetcode-denylist` | aXet izin kuralları (run modunda da bloklar) |
| Alt ajanlar | skill içindeki rol brifingleri + yerleşik `agent` aracı | aXet'te özel ajan tanımı çalışmaz |
| Yükleme kanaryası | ilk yanıtın ilk satırı `[AXET-CORE-… · SAP · proje · hafıza]` | çekirdek §0 |

## Gereksinimler
- **aXet.code** — şirket kanalından kurulmuş ve girişi yapılmış (`axet-code -v` çalışıyor). Kurulum aracı aXet'i kurmaz.
- Git ve Python ≥ 3.12 — kurulum aracı bunları **kurmaz**. Eksikse durur ve ne yapacağını söyler: şirketinin
  yazılım merkezinden (Software Center / Company Portal) kur ya da BT'den iste, sonra yeni bir PowerShell'de
  komutu tekrar çalıştır. (Yalnız şirket dışı, kişisel bir makinede: `kur.cmd -Winget` eksikleri winget ile
  kurmayı sorar.)
- Git kimliği — bir kez, bu makinede: `git config --global user.name "Ad Soyad"` ve
  `git config --global user.email "ad.soyad@sirket.com"` (değer `git config --global` dosyasına — genelde
  `%USERPROFILE%\.gitconfig` — yazılır, tüm repolarda geçerlidir; kontrol: `git config --global user.email`). Girmezsen kurulum ve aXet etkilenmez; ama
  commit'lerin Windows'un türettiği adresle atılır ve proje uzak sunucuya push edilirse o adres geçmişe girer
  (geri alınamaz). Kimlik tanımsızsa `doctor.py` projede remote varsa uyarır (WARN), yoksa bilgi verir (INFO).
  **GitHub hesabı gerekmez** (template herkese açık klonlanır).
- Windows PowerShell (Windows ile gelir).
- Önerilen: `rg` (ripgrep) — yoksa aXet'in arama aracı yavaşlar. Kurulum aracı hatırlatır ama durmaz; yazılım
  merkezinden kurabilirsin.
- İsteğe bağlı, yalnız ilgili skill'i kullanırken (skill kendi kurulum satırını söyler):

| Paket | Kullanan |
|---|---|
| `python-docx`, `python-pptx`, `openpyxl` (`pip install --user …`) | `%office-docs`, `%office-slides`, `%office-excel` |
| `markdown`, `Pillow` + Edge/Chrome (PDF baskısı) | `%sap-fs-ts-docs` (PDF, ekran görüntüsü) |
| Chrome ya da Edge + `@playwright/cli` — **kendiliğinden kurulur**: kurulum aracı ve `%guncelle`, Node.js varsa `@playwright/cli`'yi klonun `.araclar/` klasörüne kurar ve `~/.playwright/cli.config.json`'u yazar (`scripts/tarayici_hazirla.py`; tarayıcı indirilmez, ayrı komut gerekmez) | aXet içinde tarayıcı testi (`%sap-ui5-fiori`), `%sap-ui5-user-guide` |
| `@sap-ux/ui5-middleware-fe-mockserver` (proje `ui/` workspace'inde) | `%sap-ui5-user-guide` (ekran görüntülü kullanıcı kılavuzu) |
| Node.js + `playwright-core` (proje içinde), `@abaplint/cli` (npx önbelleği) | `%sap-ui5-fiori` ui-smoke, `%sap-code-review` abaplint |

İlk kez kuruyorsan adım adım rehber: [`docs/onboarding.md`](docs/onboarding.md) (kurulumdan sonra aXet içinde `%onboard`).

## Kurulum
**En kolay yol:** [`aXet-Kur.cmd`](aXet-Kur.cmd) dosyasını indir (açılan sayfada **Download raw file** düğmesi) ya da
ekibinden al ve **çift tıkla**. Aşağıdaki tek satırın aynısını yapar; sonunda sonucu sade bir mesajla yazar ve
pencereyi açık tutar. Windows "bu dosya internetten geldi" uyarısı verirse **Daha fazla bilgi → Yine de çalıştır**.

Terminal tercih edenler için: **PowerShell**'i aç ve şu satırı yapıştır. Komut kurulum betiğini geçici klasöre indirip çalıştırır:
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

Kurulum aracı sırayla şunları yapar:
1. aXet'in kurulu olduğunu kontrol eder. Kurulu değilse durur.
2. Git ve Python'u kontrol eder. Eksikse durur ve şirketinin yazılım merkezinden (ya da BT'den) kurmanı söyler;
   kendisi bir şey kurmaz.
3. Template'i `%USERPROFILE%\axet` klasörüne klonlar. Klasör zaten varsa günceller.
4. `install.py --sap` ile global aXet config'ini bu klona bağlar.
5. `doctor.py` ile kontrol eder.

Bitince **yeni** bir aXet oturumu aç. İlk yanıtın ilk satırı `[AXET-CORE-…` ile başlamalıdır. Görünmüyorsa
kurulum çalışmıyordur; `python $HOME\axet\scripts\doctor.py` çıktısına bak.

Aynı araç klondan da çalışır:
```powershell
& $HOME\axet\kur.cmd                 # güncelle (git pull --ff-only + install.py + doctor)
& $HOME\axet\kur.cmd -DenemeModu     # hiçbir şey yazmadan ne yapacağını göster
& $HOME\axet\kur.cmd -Sifirla        # klonu template ile birebir aynı hâle getir (önce yedek dalı açılır)
& $HOME\axet\kur.cmd -Kaldir         # config'ten template kayıtlarını çıkar (klasör silinmez)
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
Çıkış kodları: `0` tamam · `1` durdu · `2` ön koşul eksik · `3` yeni terminal açıp tekrar çalıştır · `4` doctor FAIL.

Elle kurmak istersen:
```powershell
git clone https://github.com/ozgurylmz34/axet-template.git $HOME\axet
python $HOME\axet\scripts\install.py --sap      # --dry-run önce gösterir, --uninstall geri alır
python $HOME\axet\scripts\doctor.py             # statik kontroller
python $HOME\axet\scripts\doctor.py --live      # aXet'in çekirdeği fiilen yüklediğini ölçer (1 model çağrısı)
```
`install.py` yalnız kendi eklediği yolları ve kuralları yönetir, diğer ayarlarına dokunmaz; yazmadan önce yedek alır.

**SAP'ye yazma varsayılan kapalıdır.** Açmak için komutu **kendi terminalinde** çalıştır (aXet oturumu bu
komutu çalıştıramaz):
```powershell
python $HOME\axet\scripts\install.py --sap --sap-write      # kapatmak: --no-sap-write
```
Bu yalnız makine düzeyindeki ilk koşuldur. SAP araçları ayrıca şunları ister: projenin `.conn_adt` dosyasında
sistem tipi `DEV`, çağrıda `--sap-write` ve kapsam beyanı (S0/S1 gerekçe, S2 mutabakatlı intake artefaktı).

> Bu belgedeki komutlar klonun `%USERPROFILE%\axet` (PowerShell'de `$HOME\axet`) altında olduğunu varsayar.
> `-Hedef` ile başka yere kurduysan yolu değiştir.

## Yeni proje
En kolay yol **aXet içinde `%yeni-proje`**: sorular sohbette tek tek sorulur, önce deneme çıktısı gösterilir,
onayınla kurulur. Terminalde aynı işi `& $HOME\axet\yeni-proje.cmd` yapar (sorular terminalde). İkisi de aynı
betiği (`scripts/yeni_proje.py`) çalıştırır:
- klasörü açar, git reposu değilse `git init -b main` yapar (pre-commit denetimi ancak böyle kablolanır);
- proje iskeletini kurar (`AGENTS.md`, `.axet-code.json`, proje hafızası, denylist, `sap-project.json`, kesin yasak damgası);
- `sap-project.json` ve `AGENTS.md` alanlarını cevaplarınla doldurur; var olan değerleri ezmez;
- `doctor.py` ile kontrol eder.

Sonra **proje klasöründeki `KURULUMU-TAMAMLA.cmd`'ye çift tıkla** (araç bu kısayolu yazar ama çalıştırmaz).
Kısayol klondaki `proje-tamamla.cmd`'yi çağırır; tekrar çalıştırmak güvenlidir, var olanı ezmez:
1. SAP bağlantı şablonları `conn\DEV.env` ve `conn\QA.env` yazılır ve Notepad'de açılır. `<...>` yerleri doldur,
   kaydet, kısayola tekrar çift tıkla. Dosyalar denetlenir (hatalı alan adıyla gösterilir, değer basılmaz; boş şablon
   atlanır); geçerli DEV aktif sistem (`.conn_adt`) olur. QA sistemi yoksa `QA.env`'e dokunma. Parola dosyada düz
   metindir; `conn/` git'e girmez ve aXet ajanına kapalıdır (denylist).
2. Davranış yüzeyi onayı sorulur (onaylanacak dosyalar listelenir).
3. `doctor.py` koşar; FAIL varsa durur.
4. aXet'i projede açmayı sorar → ilk satırda `proje: <ad>` görünmeli.

Sistem değiştirmek için aXet'te `%sistem` (ya da "QA'ya geç"). Kısayol olmadan elle:
`& $HOME\axet\proje-tamamla.cmd <klasör>`. Parolayı dosyaya yazmak istemeyen için terminal yolu:
`python $HOME\axet\skills-sap\sap-adt-foundation\scripts\setup_credentials.py` (`--slot <AD>` ile `conn\<AD>.env`).

Bağlantı teşhisi: `sap_adt_cli.py sap_doctor`.
SAP projesinde `AGENTS.md` içindeki kesin yasak bloğunu elle değiştirme: template güncellenince
`new_project.py --sap` bloğu yeniler, `doctor.py` eski ya da değiştirilmiş damgayı FAIL olarak gösterir.

Elle kurulum (ayrıntılı denetim isteyenler için):
```powershell
cd C:\projeler\benim-projem
git init -b main
python $HOME\axet\scripts\new_project.py --sap   # sonra AGENTS.md ve sap-project.json'daki <…> alanlarını doldur
```
Davranış yüzeyi (`AGENTS.md`, `.axet-code.json`, denylist, `.githooks/`, `validators-local/`) her değiştiğinde
onayı yine kendi terminalinde `behavior_manifest.py generate` ile ver.

## Yeni paket (SAP projesi)
```powershell
python $HOME\axet\scripts\new_package.py ZSD001_CLC --title "Sevkiyat raporu"   # modül addan çıkar (SD)
python $HOME\axet\scripts\new_package.py --index --check                        # paket listesi güncel mi
```
`<source_root>/<MODÜL>/<PAKET>/` altına obje tipi klasörlerini, `.rules.md` (ad önekleri, bağımlılık, transport),
`SPEC.md`, `SESSION_NOTES.md` ve `ref_docs/` kurar; `<source_root>/PAKETLER.md` listesini yeniler. `source_root`
`sap-project.json`'dadır (yoksa `SOURCE_CODES`). **SAP'de paketi SE21 ile sen yaratırsın** — aXet paket yaratmaz.

## Yeni projede kabul kontrolü
1. Projede yeni aXet oturumu aç: ilk satırda `proje: <PROJECT-ID>` görünür ve oturum özeti (`session_brief.py`) aktarılır.
2. Proje kökünde `python $HOME\axet\scripts\doctor.py` → 0 FAIL (`.conn_adt` git'e kapalı dahil).
3. SAP projesinde: `sap_adt_cli.py ping` ve bilinen bir objeyle `adt_get include_source=false` → `exists:true`.
4. `git check-ignore .conn_adt` dosya adını basar.

## Marketplace skill'leri
aXet marketplace'inden skill kurulabilir. Template skill'leriyle çakışmaması için:
- Kurmadan önce `%skill-audit` ile incele; ad kontrolü: `python $HOME\axet\scripts\doctor.py --skills --ad <ad>`.
- Proje kapsamında kur; globale ancak incelemeden sonra.
- `doctor.py` template skill'iyle aynı adda bir skill görürse FAIL verir (aXet ikisini birden listeler), SAP işine
  dokunan dış skill'i ve global kurulumu WARN olarak gösterir. Çelişkide template skill'i ve kesin yasaklar geçerlidir.

## Sorun giderme
| Belirti | Bak |
|---|---|
| Kurulum aracı aXet'i bulamadı (çıkış 2) | aXet'i şirket kanalından kur, girişi yap, yeni PowerShell aç |
| Kurulum aracı Git ya da Python eksik dedi (çıkış 2) | Şirketinin yazılım merkezinden (Software Center / Company Portal) kur ya da BT'den iste. Kurduktan sonra **yeni** bir PowerShell aç ve komutu tekrar çalıştır. Python en az 3.12 olmalı |
| Kurulum aracı yeni terminal istedi (çıkış 3) | Yalnız `-Winget` ile olur: winget kurulumu PATH'i bu pencereye yansıtmadı. Yeni PowerShell'de `kur.cmd`'yi tekrar çalıştır |
| Başka bir klonun kayıtlı olduğu uyarısı (çoğunlukla çıkış 4) | Config eski bir klonu da gösteriyor (ör. önceki sürümle `C:\axet`'e kurulmuş). Doctor'daki skill ad çakışması FAIL'leri bundan gelir: skill'leri yeniden adlandırma. Uyarıdaki `--uninstall` komutunu o klon için kendin çalıştır (o klonun `config/sap-write.local` dosyası da silinir), sonra `kur.cmd`'yi tekrar çalıştır. Eski yerde kalmak istersen `kur.cmd -Hedef C:\axet`. Uyarıdaki klon klasörü artık yoksa (silinmiş ya da taşınmış) araç "kayıt bayat" der ve `--uninstall` önermez: sondaki BAYAT KAYIT listesindeki girişleri config dosyasından elle sil (araç config'e kendisi yazmaz), sonra yeni aXet oturumu aç |
| Kurulum aracı "klon karşılaştırması ÖLÇÜLEMEDİ" dedi | Hedef yol (junction/symlink) Python ile çözülemedi. Config'teki kayıtlı klonun bu klonun kendisi olup olmadığını elle kontrol et; araç bu durumda hiçbir kaydı kaldırmayı önermez |
| Kurulum aracı "git çalıştırılamadı" dedi | Listelenen git.exe kendi terminalinde `git --version` ile çalışıyor mu bak. "unable to access …/git/config" görüyorsan XDG_CONFIG_HOME değerindeki geçersiz karakteri düzelt |
| Kurulum aracı doctor FAIL ile bitti (çıkış 4) | Kurulum yazıldı ama doğrulama geçmedi: çıktıdaki `[FAIL]` satırları; başka klon uyarısı varsa bir üst satır |
| İlk satırda `proje: YOK` | Oturum proje kökünde mi açıldı; `AGENTS.md`'de `PROJECT-ID` satırı var mı |
| İlk satırda `AXET-CORE` yok | Kurulum tamamlandı mı; `doctor.py` global config satırları |
| SAP CLI yalnız `ping` açıyor | `sap-project.json` yok ya da `sap_profile` / `master_language` geçersiz |
| Yazma reddi `tier_not_writable` | `.conn_adt` içindeki sistem tipi DEV değil ya da okunamıyor |
| Skill listede yok | `doctor.py` (frontmatter biçimi, açıklama ≤ 1024 karakter); aXet logu `.axet-code/logs/axet-code.log` |
| Skill ad çakışması FAIL | Çakışan skill başka bir template klonundaysa: yukarıdaki "başka bir klon" satırı. Dış skill ise yeniden adlandır ya da kaldır (marketplace kurulumu: `skill_uninstall <ad>`) |
| Denylist değişikliği etkisiz | Yeni oturum aç |

## Güncelleme
```powershell
& $HOME\axet\kur.cmd
```
Klonu günceller ve kurulumu yeniler. Yeni kurallar ve skill'ler bir sonraki aXet oturumunda yüklenir.

## Günlük kullanım
- Oturum açılışı: model ilk yanıttan önce `scripts/session_brief.py`'yi çalıştırır (proje `AGENTS.md` "Oturum" bölümü) —
  dal ve değişiklikler, template güncelliği, doctor uyarıları, aktif paketin son kaydı, iş listesi, devir notları
- `%yeni-proje` — yeni projeyi sorarak kur
- `%gun-sonu` — kaldığın yeri yaz (SESSION_NOTES, iş listesi, devir notu), çalışma dalını commit + push et
  (projenin uzak deposu yoksa push yapılmaz)
- İş listesi: `.axet-code/memory/project_is-listesi.md` (açık maddenin tek yeri)
- `%recall` — işe başlarken ekip/proje hafızası ve skill'lerde ilgili kayıtları ara
- `%skill-audit` — dışarıdan skill/script almadan ya da tanımadığın projede çalışmadan önce inceleme
- `%remember` — kalıcı ders/karar kaydet
- `%verify-done` — "tamam" demeden tam kapsam doğrulaması
- `%explore` — salt-okur araştırmayı alt ajana devret
- `%code-review` — bağımsız inceleyiciyle kod incelemesi
- `%handoff` — oturum devir notu / "devam"
- `%commit-pr` — commit, push, PR disiplini; uzak deposu olmayan projede dalı `main`'e yerel birleştirme
  (onayınla; cevapsız onay = hayır)
- `%write-skill` — yeni skill yazma
- `%onboard` — yeni ekip üyesine kurulum ve ilk oturum rehberi
- `%guncelle` — merkezi klonu yeni template yayınına seçmeli olarak taşı (kendi değişikliklerin korunur)
- `%guncelle-proje` — açık projenin template kaynaklı dosyalarını (AGENTS.md, denylist, .githooks,
  sap-project.json …) klondaki şablona getir; doctor ya da oturum özeti "proje şablonu eski" dediğinde
- `%research` — web/doküman araştırması (kaynaklı, aXet'in web araçlarıyla)
- `%office-excel` · `%office-docs` · `%office-slides` — Excel, Word/PDF, sunum üretimi ve okuma
- `%sistem` — projenin `conn/` altında tanımlı SAP sistemlerini listele, aktif olanı değiştir ("QA'ya geç")
- SAP işi: giriş `%sap-dev` (yeni talepte önce `%sap-intake-triage`); SAP skill listesi [`skills-sap/README.md`](skills-sap/README.md)
- `ctrl+p` → **User** sekmesi — projeye özel komutlar (`.axet-code/commands/`)
- Kimlik bilgilerini (kullanıcı adı, şifre, token) sohbete **yazma**: prompt'lar kurumsal denetime gider.

## Bilinen sınırlar (aXet.code 1.3.0, ölçülmüş)
- **Hook yok:** kurallar talimat + izin kuralı + script ile uygulanır; mekanik zorlama sınırlıdır.
- **Merkezi klonun `edit` yazma koruması YOK** (2026-09-18'de kaldırıldı; önce `install.py` global config'e klon
  klasörleri için `edit` deny yazıyordu). Gerekçe: `%guncelle` klonun içine yazar, koruma kendi akışını
  engelliyordu; zaten kazara değişikliğe karşı bir hatırlatmaydı — `bash` üzerinden ve farklı harf
  karışımıyla atlatılabiliyordu (güvenlik sınırı değildi). Yerine **görünürlük** var: `doctor.py` klonun
  davranış yüzeyindeki (`core/`, `skills/`, `skills-sap/`, `AGENTS.md`, `config/permissions.json`,
  `.axetcode-denylist`) değişiklikleri git'e karşı raporlar; `%guncelle`'nin kendi commit'leri bilgi satırı,
  kullanıcı kaynaklı sapma WARN olur. Yeniden kurulum eski `edit` deny'larını config'ten siler.
- **Özel ajan tanımı çalışmaz** (`.axet-code/agents`, `agent create`): devir yerleşik `agent` aracıyla yapılır.
- **Bash izninde "Allow for Session" bütün bash'e yayılır** (ölçüldü 2026-09-18): tek bir komuta verilen oturum onayı
  o oturumdaki TÜM bash komutlarını kapsar; `ask` kuralları da sorulmadan geçer (`deny` geçerli kalır). Bash için
  oturum onayı verme; her komutu tek tek onayla.
- **`axet-code run` ve `-y` izin sormaz:** `ask` kuralları run modunda sormadan onaylanır (ölçüldü); deny run modunda
  da bloklar. Betikten çağırırken stdin kapatılmalı. `ask`'ın TUI'de sorması beklenir (DOĞRULANMADI).
- **İki desen aynı komuta uyunca uzun olan kazanır.** ⚠ Devamı olan *"eşitlikte ask kazanır, kural sırası etkisizdir"*
  (2026-09-14, ask↔deny, tek seri) **en azından eksiktir**: 2026-09-17'de allow↔deny çiftlerinde eşit uzunlukta kazanan
  **değişti** — anahtar sırasına (ya da alfabetik sıraya; ikisi ayırt edilemedi) göre bir vakada `allow`, diğerinde `deny`
  kazandı. İki ölçüm farklı karar çiftlerine bakıyor ve **hangisinin genel olduğu ÖLÇÜLMEDİ**; ikisi de tek koşumdur.
  Güvenli okuma: **eşitlikte kazananı öngöremeyiz ⇒ eşit uzunlukta desen yazma.** Bu yüzden izin-verici desenler
  (`ask` **ve** `allow`) deny'lardan kısa tutulur ve eşitlik de ihlal sayılır
  (testli: `tests/test_install.py` her izin-verici/deny çiftini denetler). Yeniden kurulum ve
  `--uninstall` önceki sürümlerin eski desenlerini kullanıcı config'inden siler; karar değiştirilmişse dokunmaz, uyarır
  (testli). Yeniden kurulum yapılmamış makinede `doctor.py` global config'te kalan eski deseni WARN ile ve
  `install.py` tarifiyle gösterir; kararı kullanıcı değiştirmişse yalnız bilgi satırı basar (testli). Eski uzun `*Remove-Item*-Recurse*` ask'ı `git reset --hard HEAD~1; powershell … Remove-Item … -Recurse`
  zincirinde `*git reset --hard*` deny'ını ezdi ve komut sorulmadan çalıştı. Kısa ask'ın dayanağı öncelik ölçümü (deny
  uzunsa deny kazandı) ve uzunluk testidir; yeni kurallarla aynı zincirin reddedilmesi yalnız deny'ın o zincirde
  kazandığını gösterir, `*Remove-It*`'in eşleştiğini göstermez.
  Tek ölçüm serisidir (2026-09-14); uzunluğun sabit karakterle mi toplam uzunlukla mı sayıldığı DOĞRULANMADI (test ikisini
  birden ister). Proje ya da kullanıcı config'ine eklenen uzun bir desen de template kuralını ezebilir. **`allow` için ölçüldü**
  (2026-09-17, tek koşum, nötr belirteç): uzunluk kuralı allow'da da işliyor — **uzun `allow` kısa `deny`'ı ezdi**
  (komut çalıştı), uzun `deny` kısa `allow`'u ezdi. ⚠ **Eşitlikte sonuç tutarsız çıktı:** eşit uzunlukta iki
  allow/deny çiftinde kazanan değişti (anahtar sırasıyla — ya da alfabetik sırayla; ikisi ayırt EDİLEMEDİ),
  yani eşitlikte kazananı karar türü belirlemiyor ve sonuç nondeterministik olabilir. **Pratik kural: eşit
  uzunlukta desen yazma.** Şablonda `allow` deseni yoktur; uzunluk testi bugün yalnız ask↔deny çiftlerini denetler.
- **Kısa ask desenleri geniş sorar:** `*deploy_ui*` deploy dışı çağrılarda da onay ister (`deploy_ui.py --help`, `prepare`,
  `verify`); `*Remove-It*` özyinelemesiz `Remove-Item` ve `Remove-ItemProperty`'yi de kapsar.
- **`rm` ailesinde karar asimetrisi (bilinçli, ölçüme dayalı):** `*rm --recursive*` **deny**'dir ama `*rm -rf *` ve
  `*rm -r *` **ask**'tır (yani `run` kipinde sormadan onaylanır). Uzun biçim yeni ve dar olduğu için deny yazıldı;
  kısa biçimler eski, geniş eşleşmeli ve uzunluk-ezme yüzeyini büyüttükleri için ask kaldı. *"Özyinelemeli silme
  deny'dir"* diye genelleme YAPMA.
- **İzin deseni komut metninin tamamına glob olarak uyar:** baştaki `*` yoksa desen metnin başına bağlıdır ve
  `echo x; rm -rf …` ya da `cmd /c "rd /s …"` gibi zincirli/sarmalanmış komutları kaçırır (ölçüldü). Silme ve git
  desenleri bu yüzden `*` ile başlar: başa bağlı hâlleri `cd … && git reset --hard`, `echo x; git clean -fd` ve
  `cmd /c "git reset --hard"` biçimlerini geçirdi, `*` önekli hâlleri reddetti. `Remove-Item` eşleşmesi yalnız
  `powershell -Command` ile sarmalanmış biçimde görüldü; `*Remove-It*` ve `*deploy_ui*` desenlerinin kendi eşleşmesi
  ölçülmedi. Yeni desenlerden `echo x; git clean -xdf …` reddedildi ve `cmd /c "rd /q /s …"` eşleşti (ölçüldü).
  **2026-09-17'de canlı ölçüldü** (aXet.code 1.3.0, lab projesi; kanıt motor tarafından: `BgJob started` log satırı +
  işaret dosyası — model beyanı kanıt sayılmadı): `git clean -df`/`-fdx`/`-d -f`/`--force`, `git -C x push --force`,
  `rm -fr`, `rm -R`, `del /q /s`, `rmdir /s`, `rd /s ` desenlerinin **hepsi eşleşti**; kontrol grubu
  (`git clean --dry-run`, `git push origin main`, `git status --short`, `rm -i`, `rmdir empty`) yanlış pozitif vermedi.
  ⚠ **"Eşleşti" ≠ "reddetti":** son beş desenin (`rm -fr`, `rm -R`, `del /q /s`, `rmdir /s`, `rd /s `) dosyadaki
  gerçek kararı **`ask`**'tir; eşleşmeyi ölçebilmek için lab config'inde GEÇİCİ olarak `deny` yapıldılar. Ölçülen şey
  *"desen bu komut metnine uyuyor"*dur, *"`ask` ne yapar"* DEĞİL — o ayrı ve zaten ölçülü: **`axet-code run` kipinde
  `ask` SORMADAN onaylar** (yukarı bkz.). Yani bu beş komut bugün **bloklanmıyor**.
  `bash -c` ve değişkenle kurulan komut ölçülmedi; desenler güvenlik sınırı değildir.
- **`git -C <yol> …` KAÇIŞI — ölçüldü ve KISMEN KAPATILDI (2026-09-17, kullanıcı kararı).**
  `git` ile alt-komut arasına giren her global seçenek (`-C`, `--git-dir=`, `-c ayar=değer`) `*git <altkomut>…*`
  kalıbındaki desenleri ATLAR. Ölçüldü (simülasyon, `fnmatch.fnmatchcase`, 40 desenin tamamına karşı):
  `git -C <yol>` ile `branch -D`, `checkout -- .`, `stash drop`, `push origin +`, `reset --hard`, `clean -xdf`
  biçimlerinin **hiçbiri** kurala uymuyordu; kontrol `-C`siz `git branch -D f` → deny. Bu, aXet'in kendi
  belgesinin önerdiği biçimdir (`kur.ps1` çıktısı `git -C "$hedef" branch -D …` önerir) ⇒ sınır teorik değildi.
  **Eklenen 6 dar desen:** `*git -C * branch -D*`, `*git -C * checkout -- .*`, `*git -C * stash drop*`,
  `*git -C * push origin +*`, `*git -C * reset *--hard*`, `*git -C * clean -*f*`. Eklendikten sonra 13 hedef
  biçimin 13'ü de deny; 12 komutluk kontrol grubunda (`status`, `log`, `push`, `push origin main`, `branch -d`,
  `checkout -- src/foo.py`, `checkout main`, `stash list`, `stash pop`, `reset --soft`, `clean -n`,
  `clean --dry-run` — hepsi `git -C <yol>` önekli) **yanlış pozitif yok**.
  *Bilinen yanlış pozitif:* `git -C <yol> clean -n <içinde 'f' geçen yol>` — `clean -*f*` bilinçli olarak
  `-f`/`-df`/`-xdf`/`-fdx`/`-d -f`/`--force` ailesinin tamamını **tek** desenle tutar; altı ayrı desen yazmak
  uzunluk-ezme yüzeyini gereksiz büyütürdü.
  ⚠ **HÂLÂ AÇIK** (bilinçli, `tests/test_install.py::test_git_c_disi_kacis_bicimleri_hala_acik` ile kilitli):
  `git -c ayar=değer <altkomut>` biçimi (kombinatoryal, desenle kapatılamaz; **istisna:** dal silme ailesi Z75'te
  `*git *branch* …*` biçimiyle global seçenekten bağımsız kapatıldı — aşağıya bkz.) ·
  `git --git-dir=<yol>` yalnız yol `.git` ile bitiyorsa **kazara** eşleşir (koruma değil, tesadüf) ·
  ve bu 6 desenin tamamı **simülasyonla** ölçüldü, canlı `axet-code run` ile **DOĞRULANMADI**
  (kardeşi `*git -C * push -f*` canlı ölçülmüştü, biçim birebir aynı).
- **Yeni deny desenleri (2026-09-17, kullanıcı onayı):** `*git -C * push -f*`, `*git push origin +*`, `*git reset *--hard*`,
  `*rm --recursive*`, `*git stash drop*`, `*gh repo delete*`, `*git branch -D*`, `*git checkout -- .*`. Sekizi de eklendikten
  sonra canlı ölçüldü: hepsi reddedildi; kontrol grubu (`git -C x push`, `git reset --soft HEAD~1`, `rm --interactive`,
  `git stash list`, `gh repo view`, `git branch -d`, `git checkout -- src/foo.py`) çalıştı. `*git checkout -- .*` **dar**
  seçildi: yalnız `--` ayıraçlı nokta-biçimini tutar, **tek dosya geri alma çalışmaya devam eder**;
  ⚠ ayıraçsız kardeşleri **kapsam dışıdır**: `git checkout .`, `git checkout -f .`, `git restore .`,
  `git restore --staged .` hiçbir kurala uymuyor (ölçüldü 2026-09-17, simülasyon) — oysa `git checkout .` de
  tam olarak "tüm ağacı geri alan nokta biçimi"dir. Kapatılmadı, **belgelendi**; bilinen yanlış
  pozitifi `git checkout -- .gitignore` ve `git checkout -- ./yol`. Seçim ölçütü "daha geri alınamaz olan"dı: commit'siz iş
  için reflog YOKTUR ⇒ `checkout -- .` bu setin en geri alınamazıdır, `branch -D`/`stash drop` reflog/fsck ile kurtarılabilir.
- **Zorla dal silme eşdeğerleri (Z75, 2026-09-23, kullanıcı onayı).** Yalnız `*git branch -D*` vardı. Gerçek gitte
  (scratch repo, birleşmemiş dal) ölçüldü: `-d -f`, `-df`, `-fd`, `-fD`, `-Df`, `-d --force`, `--force -d`, `--delete -f`,
  `--delete --force`, `-f -d`, `-f --delete`, `--force --delete`, **sondaki** bayrak (`-d <dal> -f`) ve tekil önek
  kısaltması (`--delete --forc`) birleşmemiş dalı **sildi**; düz `-d` reddetti. 12 deny eklendi — bayrak sırasından
  bağımsız, `*git *branch*` önekli (`-C`/`-c`/`--git-dir=` de tutulur): `*git *branch* -d* -f*`, `*git *branch* -d* --forc*`,
  `*git *branch* --d* -f*`, `*git *branch* --d* --forc*`, `*git *branch* -f* -d*`, `*git *branch* -f* --d*`,
  `*git *branch* --forc* -d*`, `*git *branch* --forc* --d*`, `*git *branch* -df*`, `*git *branch* -fd*`, `*git *branch* -fD*`,
  `*git *branch* -D*`. Meşru `git branch -d <dal>` (adında `-f` geçen dallar dahil) ve okuma biçimleri (`--list`, `-a`, `-v`,
  `--show-current`, `--format=…`) ile adında/mesajında "branch" geçen başka git komutları **düşmez**
  (`tests/test_install.py::ZorlaDalSilmeTest`). **Bilinçli açık:** `git branch -f/--force <dal> <ref>` (zorla taşıma —
  dalın kendi reflog'u korunur, `<dal>@{1}` ile geri alınır; ölçüldü) ve `-M`. `-D` ise dalın reflog'unu da siler
  (ölçüldü); kurtarma yalnız HEAD reflog'u ya da `git fsck` dangling commit ile, gc'ye kadar. Bilinen yanlış pozitif:
  `git branch …` ile **zincirlenmiş** ve sonrasında ` -d…`/` -f…` bayrakları geçen başka komut. Bilinen açık: harf
  varyantı, `-d`/`-f` ilk harf olmayan kümeler (`-vdf`), çift boşluk.
- **Yanlış pozitif: desen metni komutun herhangi bir yerinde geçerse eşleşir.** Ölçülen: `echo "rm -rf notu"`,
  `python x.py "rd /s metni"`, `git commit -m "git push --force notu"`, `echo "git reset --hard açıklaması"`.
  Simülasyonla beklenen (ölçülmedi): `rg -n "git reset --hard" .` ve `grep -rn "git reset --hard" docs` (deny),
  `git log --grep="git clean -xdf"` (deny), `git push -u origin dal && gh pr create -f` (deny),
  `git -C x push origin main --force-with-lease` (deny), `git rm -r --cached build` ve `git rm -R x` (ask),
  `rg -n "rm -fr" docs` ve `rg "rmdir /s" docs` (ask). Commit mesajında bu metinler geçecekse mesaj dosyasını bash `echo`
  ile değil düzenleme aracıyla yaz (echo komutu da eşleşir) ve `git commit -F <dosya>` ile ver (`-F` yolu ölçülmedi).
- **Yerel MCP yok sayılır:** entegrasyonlar script ya da kurumsal Connector ile yapılır.
- Koşullu (dosya türüne göre) kural yükleme yok: çekirdek her oturum yüklenir, bu yüzden kısa tutulur.
- **Bağlam dosyaları kesilmez:** `context_paths` ile verilen dosyalar tamamen gönderilir. Toplam 1M token aşılınca
  oturum uyarısız hatayla biter; Türkçe metinde bu yaklaşık 1,9 MB'a denk gelir (ölçüldü). ~940K token civarında satır
  hatırlama bozuldu. Proje listesi global listeyi ezmez, birleşir. `doctor.py` toplamı 200 KB'ta WARN, 1 MB'ta FAIL
  olarak raporlar; alt klasör ve `.md` dışı dosyalar yalnız üst sınıra katılır.
- **Klon koruması kazaya karşıdır, güvenlik sınırı değildir:** başka bir projede açılan aXet oturumu bu klonun
  `core/ skills/ skills-sap/ scripts/ config/ templates/` klasörlerine yazamaz (`memory/` serbest). aXet yolu
  harfe duyarlı eşleştirir; beklenmedik bir harf karışımı ya da bash komutu kuralı atlatabilir. Klonun kendi
  içinde açılan oturumda kural devreye girmez (bakım bu yüzden serbesttir).
- **Aynı adlı skill uyarısız çoğalır:** marketplace ya da proje skill'i template skill'iyle aynı adı taşırsa aXet
  ikisini de listeler ve model hangisini okuyacağını kendisi seçer (`doctor.py` bunu FAIL olarak gösterir).

## Yapı
```
kur.cmd · kur.ps1  kurulum ve güncelleme aracı      yeni-proje.cmd  terminalden proje kurulumu
core/            çekirdek kurallar (00-temel.md) · sap/ SAP paketi
skills/          genel skill'ler            skills-sap/   SAP skill'leri
memory/          ekip hafızası (indeks + kayıtlar)
templates/project/  proje iskeleti (+ project-sap/)   templates/package/  new_package.py'nin kurduğu paket iskeleti
config/          install.py'nin birleştirdiği izin kuralları
scripts/         install.py · yeni_proje.py · new_project.py · new_package.py · doctor.py · session_brief.py
                 sap_stamp.py · project_precommit.py · check_package_naming.py · behavior_manifest.py
tests/           template script'lerinin testleri: python tests\run_tests.py (skill testleri skill klasöründe)
docs/            onboarding rehberi
LICENSE · NOTICE · THIRD_PARTY_NOTICES.md · LICENSES/
```

## Lisans
Kendi içeriğimiz [MIT](LICENSE) lisanslıdır. İzinle eklenen bazı bölümler ek koşullara tabidir: [NOTICE](NOTICE).
Açık kaynak projelere dayanan kod ve veriler: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
SAP, ABAP ve S/4HANA SAP SE'nin ticari markalarıdır; bu proje SAP SE ile bağlantılı değildir.

## Değişiklik notu
Public yayınların (v0.1.0 ve sonrası) sürüm notları **`CHANGELOG.md`** dosyasındadır: her yayında
`guncelle/yayinlar.json` kataloğundan üretilir; kalem başına neden, dosyalar ve test komutu yazar. `%guncelle`
aynı katalogdan hangi kalemlerin bekleyip beklemediğini gösterir. Aşağıdaki kayıtlar public yayın öncesi iç
sürümlerdir; yeni kayıt buraya eklenmez.

- **0.3.0 (hüküm dürüstlüğü, 2026-09-14)** — SAP temel araçları ölçemediği sonucu başarı saymaz: aktivasyon hükmü
  üç değerli (gövde hüküm taşımıyorsa bağımsız worklist sondası; sonda ölçemezse `success:false`), `adt_syntax_check`
  kontrol koşmadıysa `valid:null`, push ön kontrolü ölçülemediyse `syntax_precheck:"olculemedi"`. Sorgu araçları SAP
  hata gövdesini (`sap_error`) ve kesin `truncated` alanını döndürür; `adt_inactive_objects` TADIR kontrolünü 5'li
  parçalarla yapar, `adt_where_used` paket düğümlerini obje sayısına katmaz, FM araması `FUNC` takma adını çözer.
  Reviewer'da biçimi bozuk `AXET-GATE-STATUS` satırı ölçüm yok sayılır. Kaynak metodoloji çekirdeğiyle senkron
  (`maintenance/sync-lock.json`). install.py tekrar gerekmez. Canlı SAP doğrulaması DOĞRULANMADI.
- **0.3.0 (2026-09-14)** — Son kullanıcı kurulumu: `kur.cmd`/`kur.ps1` (tek satırla kurulum, winget ile Git/Python,
  güncelleme, `-DenemeModu`, `-Kaldir`). Sorarak proje kurulumu: `%yeni-proje` skill'i ve `yeni-proje.cmd`
  (`scripts/yeni_proje.py`). `doctor.py` skill envanteri: template, proje, `AXET_SKILLS_DIR` ve marketplace kaydı
  taranır; aynı ad FAIL, SAP konulu dış skill ve global kurulum WARN; `--skills --ad` kurulum öncesi ad kontrolü.
  Çekirdeğe skill öncelik kuralı ve marketplace yerleşim politikası (`AXET-CORE-0.3.0`). Lisans dosyaları.
  Ekran üreteci kiti ve ALV şablonları nötr `ZBC000` önekine taşındı. Kurulum aracı ve `%yeni-proje` canlı aXet
  oturumunda ve gerçek winget kurulumuyla DOĞRULANMADI.
- **0.2.0 (partiler 4-7, 2026-09-13/14)** — Yeni SAP skill'leri: `sap-ui5-fiori`, `sap-code-review`, `sap-fs-ts-docs`,
  `sap-gui-scripting`, `sap-abapgit-delivery`. Genel skill'ler: `onboard`, `research`, `office-excel`, `office-docs`,
  `office-slides`. Proje pre-commit denetimi (`.githooks/`, `project_precommit.py`, paket adı denetimi, davranış
  manifesti), `tests/`. SAP CLI: mesaj sınıfı yazma, domain ön kontrolü, yeni kabuk/push tipleri. İzin kurallarına
  UI5 deploy ve manifest onayı eklendi — **install.py tekrar çalıştırılmalı**. Yeni araçların canlı SAP ve aXet
  çalışma zamanı doğrulaması bakımcıların canlı test planındadır; o plan koşulana kadar DOĞRULANMADI.
- **0.2.0 (parti 3)** — `new_package.py` + `templates/package/` (paket klasörü, `.rules.md`,
  `PAKETLER.md`); `sap-dev` yönlendirici skill'i (adlandırma standardı, ABAP desenleri); SAP CLI yazma kapısında
  kesin yasak B kaynak taraması (`ADR_0005_B`) ve düzenlemeden önce çekme zorunluluğu (`adt_get` olmadan
  `adt_push_source` yazmaz). `sap-project.json`'a `source_root` alanı eklendi. Obje tipi skill'leri: `sap-cds-ddic`,
  `sap-rap`, `sap-classic-abap` (dört ALV şablon programı + ekran üreteci kiti, `templates/screen-gen/DEPLOY.md`),
  `sap-odata-backend`. `doctor.py` 1024 karakteri aşan skill açıklamasını FAIL verir (aXet böyle skill'i yüklemez).
- **0.2.0** — **install.py tekrar çalıştırılmalı.** SAP çekirdeğine yazma yolu, hassas veri (KVKK), kimlik
  bilgisi ve ALV paritesi kuralları (`AXET-SAP-0.2.0`); merkezi klon yazma koruması; ekip hafızasına 10 çalışma
  dersi; template köküne `.axetcode-denylist`. (Klon yazma koruması 2026-09-18'de kaldırıldı — bkz. Bilinen sınırlar.)
- **0.1.0** — Faz 1 iskeleti: çekirdek, SAP kuralları, hafıza düzeni, `remember` skill'i, kurulum/proje/doğrulama script'leri.
