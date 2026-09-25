# aXet.code Template

aXet.code'un Claude Code'a olabildiğince yakın çalışması için ortak kurallar, skill'ler, hafıza düzeni ve
kurulum araçları. Repo makinede **bir kez** klonlanır; kurulum aracı kullanıcının global aXet config'ini
bu klasöre bağlar. Güncelleme tek komutla tüm projelere birden yansır.

> Sürüm: v0.5.9 · Sürüm notları: `CHANGELOG.md` · Ölçüldüğü aXet.code sürümü: 1.3.0 · Lisans: [MIT + ek koşullar](#lisans)

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
Şirket portalından (Software Center / Company Portal) üç program: **aXet**, **Git**, **Python 3.12 ya da üstü**.
Portalda bulamazsan BT'den iste. Başka bir şey kurman gerekmez: SAP bağlantısının Python paketlerini ve tarayıcı
testini kurulum kendisi hazırlar. GitHub hesabı gerekmez.

İsteğe bağlı, yalnız ilgili skill'i kullanırken (skill kendi kurulum satırını söyler):

| Paket | Kullanan |
|---|---|
| `python-docx`, `python-pptx`, `openpyxl` (`pip install --user …`) | `%office-docs`, `%office-slides`, `%office-excel` |
| `markdown`, `Pillow` + Edge/Chrome (PDF baskısı) | `%sap-fs-ts-docs` (PDF, ekran görüntüsü) |
| Chrome ya da Edge + `@playwright/cli` — **kendiliğinden kurulur**: kurulum aracı ve `%guncelle`, Node.js varsa `@playwright/cli`'yi klonun `.araclar/` klasörüne kurar ve `~/.playwright/cli.config.json`'u yazar (`scripts/tarayici_hazirla.py`; tarayıcı indirilmez, ayrı komut gerekmez) | aXet içinde tarayıcı testi (`%sap-ui5-fiori`), `%sap-ui5-user-guide` |
| `@sap-ux/ui5-middleware-fe-mockserver` (proje `ui/` workspace'inde) | `%sap-ui5-user-guide` (ekran görüntülü kullanıcı kılavuzu) |
| Node.js + `playwright-core` (proje içinde), `@abaplint/cli` (npx önbelleği) | `%sap-ui5-fiori` ui-smoke, `%sap-code-review` abaplint |

## Kurulum
1. **Önce kur:** aXet, Git ve Python 3.12+ — şirket portalından.
2. **[`aXet-Kur.cmd`](https://github.com/ozgurylmz34/axet-template/blob/main/aXet-Kur.cmd)'yi indir** (açılan sayfada **Download raw file**) ya da ekibinden al ve **çift
   tıkla**. Soruları cevapla (git adın ve e-postan). Eksik program varsa pencere listesini verir: onları portaldan
   kur ve dosyaya **tekrar çift tıkla**. Sonunda "Kurulum TAMAM — aXet'i aç." yazar.
3. **aXet'i aç** (açıksa kapatıp yeniden aç). İlk yanıtın ilk satırı `[AXET-CORE-…` ile başlar. Sonraki
   güncellemeler için aXet içinde **`%guncelle`** yaz.
4. **Proje:** aXet içinde **`%yeni-proje`** (yeni proje) ya da **`%guncelle-proje`** (var olan proje) → proje
   klasöründeki **`KURULUMU-TAMAMLA`**'ya çift tıkla → pencerenin gösterdiği **`conn\DEV.env`** dosyasını doldur →
   **tekrar çift tıkla**.

Bu kadar. Takılırsan (pencere durdu, Windows uyarısı, paket indirilemedi, `python` bulunamadı, yeniden kurma ya da
kaldırma, terminal yolu): [`docs/onboarding.md` → Sorun giderme](docs/onboarding.md#5-sorun-giderme).

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
aXet içinde **`%yeni-proje`** yaz: sorular sohbette tek tek sorulur, önce ne yapılacağı gösterilir, onayınla kurulur
(klasör, git reposu, proje iskeleti, `AGENTS.md` ve `sap-project.json` alanları, kontrol). Var olan değerler ezilmez.

Sonra **proje klasöründeki `KURULUMU-TAMAMLA`'ya çift tıkla** (aXet bu dosyayı yazar ama çalıştırmaz):
1. Pencere SAP bağlantı dosyalarını hazırlar ve hangisini dolduracağını tam yoluyla söyler: `conn\DEV.env`
   (zorunlu) ve `conn\QA.env` (QA sistemin yoksa dokunma). Dosyayı aç, `<...>` yazan yerleri (adres, kullanıcı,
   parola, client) doldur, kaydet. Pencere soru sormaz, dosyayı da kendisi açmaz.
2. **Tekrar çift tıkla:** dosya denetlenir (hatalı alan adıyla gösterilir, değer basılmaz), DEV aktif sistem olur,
   proje ayarlarının onayı sorulur, kontrol (`doctor`) koşar ve aXet'i projede açmayı önerir — ilk satırda
   `proje: <ad>` görünmeli.

Parola dosyada düz metindir; `conn/` git'e girmez ve aXet ajanına kapalıdır. Sistem değiştirmek için aXet'te
`%sistem` (ya da "QA'ya geç"). Var olan projeyi şablona getirmek için `%guncelle-proje`; bitince yine
`KURULUMU-TAMAMLA`'ya çift tıkla (ayar onayını o sorar).

SAP projesinde `AGENTS.md` içindeki kesin yasak bloğunu elle değiştirme: template güncellenince
`new_project.py --sap` bloğu yeniler, `doctor.py` eski ya da değiştirilmiş damgayı FAIL olarak gösterir.
Terminal yolu, elle kurulum ve bağlantı teşhisi: [`docs/onboarding.md`](docs/onboarding.md) §3.

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
Belirti → çözüm tablosu: [`docs/onboarding.md` → Sorun giderme](docs/onboarding.md#5-sorun-giderme).

## Güncelleme
aXet içinde **`%guncelle`** yaz. Klonu yeni yayına seçmeli olarak taşır (senin değişikliklerin korunur), SAP Python
paketlerini denetleyip eksikse kurar ve tarayıcı testini hazırlar. Yeni kurallar ve skill'ler bir sonraki aXet
oturumunda yüklenir. Projelerin için ayrıca `%guncelle-proje`.

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

## Bilinen sınırlar
aXet.code 1.3.0'da ölçüldü. Bilmen gerekenler:

- **Bash izninde "Allow for Session" verme.** Tek bir komuta verilen oturum onayı o oturumdaki bütün bash
  komutlarını kapsar; "sor" kuralları da sorulmadan geçer (yasaklar geçerli kalır; ölçüldü 2026-09-18). Her komutu
  tek tek onayla.
- **`axet-code run` ve `-y` izin sormaz:** "sor" kuralları sormadan onaylanır, yalnız yasaklar bloklar. SAP'ye yazan
  işi bu kipte yaptırma. Betikten çağırırken stdin kapatılmalı. Etkileşimli ekranda (TUI) "sor"un gerçekten
  sorması beklenir; bu DOĞRULANMADI.
- **İzin kuralları bir güvenlik sınırı değildir.** Kazaya karşı frendir: farklı yazım, takma ad ya da kabuk
  dolaylamasıyla atlatılabilir. Desen metni komutun herhangi bir yerinde geçerse zararsız bir komutu da
  engelleyebilir (ör. `echo "git reset --hard notu"`). SAP'ye yazmanın güvenli yolu kapılı araçlardır.
  Eşleşme kuralları, ölçümler, bilinçli açıklar ve yanlış pozitifler: [`docs/izin-kurallari.md`](docs/izin-kurallari.md).
- **Hook yok:** kurallar talimat, izin kuralı ve betikle uygulanır; mekanik zorlama sınırlıdır.
- **Özel ajan tanımı çalışmaz** (`.axet-code/agents`, `agent create`): iş devri yerleşik `agent` aracıyla yapılır.
- **Merkezi klon yazmaya kapalı değildir.** Sapmayı `doctor.py` git'e karşı raporlar: klonun davranış yüzeyindeki
  (`core/`, `skills/`, `skills-sap/`, `AGENTS.md`, `config/permissions.json`, `.axetcode-denylist`) senden gelen
  değişiklik WARN olur, `%guncelle`'nin kendi commit'leri bilgi satırı olur. Eski yazma koruması (config'e yazılan
  `edit` yasakları) 2026-09-18'de kaldırıldı: `%guncelle` klonun içine yazdığı için kendi akışını engelliyordu, bash
  ve farklı harf karışımıyla da atlatılabiliyordu. Yeniden kurulum eski sürümlerin yazdığı bu yasakları config'ten siler.
- **Aynı adlı skill uyarısız çoğalır:** marketplace ya da proje skill'i template skill'iyle aynı adı taşırsa aXet
  ikisini de listeler ve hangisinin okunacağını model seçer (`doctor.py` bunu FAIL olarak gösterir).
- **Bağlam dosyaları kesilmez:** `context_paths` dosyaları tamamen gönderilir. Toplam 1M token aşılınca oturum
  uyarısız hatayla biter (Türkçe metinde yaklaşık 1,9 MB); ~940K token civarında satır hatırlama bozuldu. Projenin
  listesi global listeyi ezmez, ona eklenir. `doctor.py` toplamı 200 KB'ta WARN, 1 MB'ta FAIL verir; alt klasörler ve
  `.md` dışı dosyalar ölçülmediği için yalnız üst sınır olarak raporlanır.
- **Yerel MCP yok sayılır:** entegrasyonlar betikle ya da kurumsal Connector ile yapılır.
- **Koşullu kural yükleme yok:** çekirdek her oturumda yüklenir, bu yüzden kısa tutulur.

## Yapı
```
aXet-Kur.cmd     çift tıkla kurulum          kur.cmd · kur.ps1  kurulum ve güncelleme aracı (terminal yolu)
yeni-proje.cmd   terminalden proje kurulumu  proje-tamamla.cmd  projedeki KURULUMU-TAMAMLA'nın hedefi
GUNCELLE.md      %guncelle adımları          guncelle/          güncelleme kataloğu (yayinlar.json), sınıf haritası, kartlar
CHANGELOG.md     yayın notları               AGENTS.md          template reposunun bakım talimatı (projelere gitmez)
.axetcode-denylist  aXet'in okumadığı ve yazmadığı yollar (.conn_adt, .env, secrets; bash'te garanti değil)
core/            çekirdek kurallar (00-temel.md) · sap/ SAP paketi
skills/          genel skill'ler            skills-sap/   SAP skill'leri
memory/          ekip hafızası (indeks + kayıtlar)
templates/project/  proje iskeleti (+ project-sap/)   templates/package/  new_package.py'nin kurduğu paket iskeleti
config/          install.py'nin birleştirdiği izin kuralları
scripts/         install.py · doctor.py · session_brief.py · guncelle.py · guncelle_proje.py · yeni_proje.py
                 new_project.py · new_package.py · conn_sablon.py · tarayici_hazirla.py · sap_stamp.py
                 project_precommit.py · check_package_naming.py · behavior_manifest.py · merge_pr.py
tests/           template script'lerinin testleri: python tests\run_tests.py (skill testleri skill klasöründe)
docs/            onboarding.md (kurulum ve sorun giderme) · izin-kurallari.md · sap-api-policy.md
.github/         CI iş akışı
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
  dersi; template köküne `.axetcode-denylist`. (Klon yazma koruması 2026-09-18'de kaldırıldı.)
- **0.1.0** — Faz 1 iskeleti: çekirdek, SAP kuralları, hafıza düzeni, `remember` skill'i, kurulum/proje/doğrulama script'leri.
