# İzin kuralları: davranış ayrıntıları ve ölçümler

`config/permissions.json` kurallarının aXet.code 1.3.0'da nasıl eşleştiğine dair ölçümler, bilinçli açıklar ve bilinen
yanlış pozitifler. Kurallar `scripts/install.py` ile global aXet config'ine birleştirilir. Kuralların kendisi ve tam
kapsam sayımı `config/permissions.json` içindeki `_aciklama` alanındadır; bu belge onu okunur biçimde özetler.

> **Önce bunu bil:** izin kuralları bir güvenlik sınırı değildir. Kazaya karşı bir frendir; farklı yazım, takma ad ya da
> kabuk dolaylamasıyla atlatılabilir. SAP'ye yazmanın güvenli yolu kapılı araçlardır (`sap_adt_cli.py`, `deploy_ui.py`).
> Kısa kullanıcı özeti: [README → Bilinen sınırlar](../README.md#bilinen-sınırlar).

## Eşleşme ve öncelik

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
  uzunlukta desen yazma.** Statik dosyada (`config/permissions.json`) `allow` deseni yoktur; `install.py` klon yoluna
  bağlı iki **jokersiz, birebir** `allow` üretir (aşağıda "Açılış özeti komutu"). Uzunluk testi ask **ve** allow ↔ deny
  çiftlerini denetler; üretilen jokersiz allow'lar bu kuraldan bilinçli muaftır, joker girerse muafiyet düşer
  (`tests/test_install.py::uretilen_izin_ihlalleri`).
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
  `ask` SORMADAN onaylar** (README → Bilinen sınırlar). Yani bu beş komut bugün **bloklanmıyor**.
  `bash -c` ve değişkenle kurulan komut ölçülmedi; desenler güvenlik sınırı değildir.
- **Eşleşme BÜYÜK/KÜÇÜK HARFE DUYARLIDIR** (ölçüldü 2026-09-17, aXet.code 1.3.0, lab config; kanıt motor tarafından,
  model beyanı değil): `echo "RD /S x"` **çalıştı** (kontrol: `echo "rd /s x"` reddedildi), `echo "RM -RF /tmp/x"` de
  çalıştı. Desenlerin tamamı komutu ve bayrağı TEK yazımla yazar (kanonik küçük harfli biçim; `-R`/`-D`/`-xdf` gibi
  bayraklar kendi kanonik harfleriyle) ⇒ harf yazımı değiştirilen komut desene uymaz. Varyantlar kombinatoryal olduğu
  için desen ekleyerek kapatılamaz — bilinen sınırdır. Kaynak ölçüm kaydı: `config/permissions.json` `_aciklama`.
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
- **Paket yöneticisi ile kapısız deploy/undeploy (Z106-EK, 2026-09-24, kullanıcı onayı).** SAP'ye yazan tek meşru yol
  kapılı `deploy_ui.py deploy`dır (`*deploy_ui*` ask). Eski 4 desen `npm run undeploy`, `npm run-script deploy`,
  `npm run --silent deploy`, `npm -w app run deploy`, `npm.cmd run deploy`, `yarn deploy`, `pnpm undeploy`,
  `bun run deploy` ve `ui5 build --config ui5-deploy.yaml` biçimlerini kaçırıyordu (simülasyon). 16 deny eklendi:
  `*npm*run deploy*`, `*npm*run-script deploy*`, `*npm*run -* deploy*`, `*npm*run-script -* deploy*`, `*npm*undeploy*`,
  `*yarn deploy*`, `*yarn.cmd deploy*`, `*yarn*run deploy*`, `*yarn --cwd * deploy*`, `*yarn workspace * deploy*`,
  `*yarn*undeploy*`, `*bun deploy*`, `*bun run deploy*`, `*bun run -* deploy*`, `*bun *undeploy*`,
  `*ui5 build*ui5-deploy*`. Bug gate sonrası (gerçek npm 10.9.3'te koştuğu ölçüldü) 4 deny daha: npm'in `run-script`
  takma adları `*npm*rum deploy*`, `*npm*urn deploy*` ve tırnaklı ad `*npm*run "deploy*`, `*npm*run 'deploy*`.
  `ui5 build` deseninin dayanağı **belgedir** (ui5-deploy.yaml'daki `deploy-to-abap` özel
  görevi build içinde koşar — UI5 CLI + `@sap-ux/deploy-tooling` belgeleri), canlı ölçülmedi. `deploy` desenleri **bitişik**
  metin taşır (`run deploy`): daha geniş `*npm*run* deploy*` taslağı kapılı yolun kendisini (`npm run build && …
  deploy_ui.py deploy …`, hatta onay cümlesinde "npm run" geçen zincirsiz çağrıyı) deny'a düşürdüğü için seçilmedi.
  ⚠ `undeploy` desenleri **bitişik DEĞİLDİR** (`*npm*undeploy*`, `*yarn*undeploy*`, `*bun *undeploy*` araya `*` alır):
  paket yöneticisi adından sonra herhangi bir yerde `undeploy` geçen metin de düşer — `yarn test undeploy`,
  `npm run test -- --grep undeploy`, `npm pkg get scripts.undeploy`, `rg -n "npm.*undeploy" .`,
  `npm run build && rg undeploy .`, `bun test src/undeploy.test.ts` (simülasyon, testte kilitli).
  Kontrol grubu (`npm run build/start/lint`, `npm install/test`, `yarn build/install`, `pnpm install`,
  `npm run build -- --dest deploy`, `npm run start:deploy-preview`, `npm run lint && echo deploy`, `yarn test deploy`)
  ve kapılı yol düşmez (`tests/test_install.py::PaketYoneticisiDeployTest`). **Canlı ölçüldü** (2026-09-24,
  `axet-code run`, lab config, motor kanıtı: DB `denied … rule bash:<desen>=deny` + işaret dosyası): `npm run undeploy`,
  `yarn deploy`, `ui5 build --config ui5-deploy.yaml`, `npm run --silent deploy` (echo biçimleri) reddedildi; `npm run build`,
  `npm run lint && echo deploy`, `npm run build && python deploy_ui.py deploy app` çalıştı. İkinci koşumda
  `npm rum deploy`, `npm urn deploy`, `npm run "deploy"` reddedildi; `docker run ubuntu ls /srv/undeploy` ve
  `rg -n "run deploy" .` çalıştı. Kalan 13 yeni desen yalnız simülasyon (`config/permissions.json` `_aciklama`
  "GÜNCEL KAPSAM SAYIMI" tam listeyi verir). *Bilinen yanlış pozitif:* `npm run deploy-config`,
  `npm run "deploy-config"`, `npm ci && echo return deploy` (`*npm*urn deploy*`), Türkçe metinde sık geçen
  **"-rum" ile biten bir kelime + "deploy"** (ör. durum/yorum/forum/spectrum deploy; `*npm*rum deploy*`: `npm run build && echo "durum deploy hazir"`; kapılı yol zincirinde
  onay cümlesi `--user-ok "forum deploy onayı"` ise deny `*deploy_ui*` ask'ını ezer — onay cümlesinde deny desen metni geçmesin: ör. `fiori deploy`, `yarn deploy`, `npm run deploy`, "deploy"dan hemen önce -rum/-urn ile biten kelime); bayraklı zincir
  (`npm run -s build && … deploy_ui.py deploy …`, `yarn --cwd x build && …`) — `deploy_ui.py` build'i kendisi yapar,
  **zincirsiz çağır**; `ui5 build --config ui5-deploy.yaml --exclude-task deploy-to-abap`. *Bilinen açık:* `pnpm deploy`
  (pnpm'in yerleşik komutu, script koşmaz — DOĞRULANMADI), `npx deploy`/`undeploy` ve `node_modules/.bin/deploy`
  (`@sap-ux/deploy-tooling` bin'leri; iskelette doğrudan bağımlılık değil), `node …/fiori.cjs deploy`, başka adla
  eklenmiş deploy script'i (`npm run ship`) ya da başka adlı deploy config'i, `yarn --silent deploy`, çift boşluk, harf varyantı,
  takma adın bayraklı biçimi (`npm rum -s deploy`), `npm run-script "deploy"`, kabuk dolaylaması (`X=deploy; npm run $X`,
  `npm run $(echo deploy)` — script adı komut metninde geçmez, desenle kapatılamaz), PowerShell
  `Start-Process npm -ArgumentList "run","deploy"`, `npx @ui5/cli build --config ui5-deploy.yaml`,
  `.exe`/`.cmd` uzantısı bayrakla birlikteyse (`bun.exe run deploy`, `yarn.cmd --cwd app deploy`), `bun --cwd app run deploy`,
  `pnpm --dir app deploy`. ⚠ **Sınıf olarak:** desenler yalnız listelenen yazımları yakalar; takma ad/bayrak/tırnak BİRLEŞİMLERİ (ör. `npm rum "deploy"`, `npm urn -s deploy`, `npm run -s "deploy"`, `npm run-script 'deploy'`) yakalanmaz — izin kuralı güvenlik sınırı değildir, SAP'ye yazmanın güvenli yolu deploy_ui.py kapısıdır. Ölçülen (gate, npm 10.9.3, deploy script'i
  ÇALIŞTI): `npm run -s "deploy"`, `npm rum "deploy"`, `npm urn "deploy"`, `npm urn -s deploy`, `npm rum --silent deploy`,
  `npm run-script 'deploy'`. yarn/bun tırnaklı biçimler (`yarn "deploy"`, `yarn run "deploy"`, `bun run "deploy"`) de desensiz;
  araç kurulu olmadığı için script'i çalıştırdıkları DOĞRULANAMADI. Hepsi testte "hâlâ açık" diye kilitli.
- **Açılış özeti komutu — üretilen `allow` kuralları (Z12 2026-09-20 · Z140 2026-09-26, kullanıcı onayı).** Şablonun
  tek `allow` kaynağı `install.py` `session_brief_allow()`dur: klon yolundan `python "<klon>/scripts/session_brief.py"`
  (çıplak; `%basla` ve çekirdek §0) ile `python "<klon>/scripts/session_brief.py" --no-fetch` (`%gun-sonu`,
  `%onboard`) desenlerini **jokersiz** üretir; yol makineye bağlı olduğu için statik dosyada durmazlar. Güvenlik
  dayanağı jokersizliktir: desen komut metninin tamamına uyduğundan yalnız o tek metne uyar; zincire uzatılmış metin
  (`… --no-fetch && git reset --hard`) eşleşmez ⇒ "uzun allow kısa deny'ı ezer" tırmanışı yapısal olarak kapalıdır.
  Çıplak biçim canlı ölçüldü (2026-09-20, S0-S4: `install.session_brief_allow` docstring'i); `--no-fetch` biçimi
  yalnız **simülasyonla** testlidir (`fnmatchcase`): ek argüman, sonda ya da çift boşluk, bitişik metin, `&&`, `;`,
  `|`, satır sonu, önden `cd … &&` ve `py` yazımı izin almaz (`tests/test_install.py::OturumOzetiNoFetchAllowTest`).
  Komşu biçimler **sorulur** (fail-safe). Kurulu makinede yeni desen `install.py` yeniden koşulana kadar config'te
  yoktur; o arada `doctor.py` "eksik/farklı izin kuralı" WARN'ı verir.
  ⛔ **`--project-dir "<yol>"` biçimine kural YOK — bilinçli.** Yol değişkendir ⇒ birebir yazılamaz; yazılabilecek
  tek desen jokerli `python "<klon>/scripts/session_brief.py" --project-dir "*"` olurdu ve `*` tırnağı da yuttuğu için
  `… --project-dir "x" && git reset --hard HEAD~1 && echo "y"` metnine de uyar (simülasyon: eşleşti) — uzun allow
  kısa deny'ı ezer. Bu biçim (`%basla` proje kökü dışındayken, `%guncelle-proje` adım 7) onay sormaya devam eder.
- **Yanlış pozitif: desen metni komutun herhangi bir yerinde geçerse eşleşir.** Ölçülen: `echo "rm -rf notu"`,
  `python x.py "rd /s metni"`, `git commit -m "git push --force notu"`, `echo "git reset --hard açıklaması"`.
  Simülasyonla beklenen (ölçülmedi): `rg -n "git reset --hard" .` ve `grep -rn "git reset --hard" docs` (deny),
  `git log --grep="git clean -xdf"` (deny), `git push -u origin dal && gh pr create -f` (deny),
  `git -C x push origin main --force-with-lease` (deny), `git rm -r --cached build` ve `git rm -R x` (ask),
  `rg -n "rm -fr" docs` ve `rg "rmdir /s" docs` (ask), `rg "yarn deploy" .` (deny, `*yarn deploy*`). Aramada çıkış yolu:
  aranan metinden paket yöneticisi/komut adını çıkar — `rg -n "run deploy" .` hiçbir desene uymaz (canlı çalıştı
  2026-09-24). Commit mesajında bu metinler geçecekse mesaj dosyasını bash `echo`
  ile değil düzenleme aracıyla yaz (echo komutu da eşleşir) ve `git commit -F <dosya>` ile ver (`-F` yolu ölçülmedi).
