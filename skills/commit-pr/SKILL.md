---
name: commit-pr
description: Use when the user asks to commit, push, create a branch, open a pull request or merge a branch into main — including local repos without a remote ("commit et", "push et", "dal aç", "PR aç", "değişiklikleri gönder", "main'e birleştir", "merge et").
---

# Commit, push ve PR disiplini

## When to use this skill
Yalnız kullanıcı commit / push / PR / dalı `main`'e birleştirme istediğinde. Kendiliğinden commit, push ya da birleştirme yapma.

## How to use this skill
1. **Oku:** `git status`, `git diff` ve `git diff --staged`. Alakasız değişiklik varsa hangilerinin girmesi gerektiğini sor.
2. **Kimlik bilgisi taraması:** eklenecek dosyalarda `password|passwd|secret|token|api[_-]?key|BEGIN .*PRIVATE KEY` desenlerini `rg` ile ara (aXet `bash` aracında `grep` yok); `.conn*`, `*.env` gibi dosyalar eklenmesin. Şüphe varsa DUR ve kullanıcıya göster.
3. **Dal:** `main` üzerindeysen yeni dal aç ve başlangıç noktasını açık yaz. Remote var mı önce ölç: `git remote` — çıktı boşsa **yerel repo** (remote yok; push, PR ve CI yoktur).
   - remote varsa: `git fetch origin` → `git switch -c <dal> origin/main`
   - yerel repo: `git switch -c <dal> main`
   - **Başka günün `wip/` dalındaysan** (dal adı `wip/<YYYY-AA-GG>-…` ve bu tarih bugün değil; `%gun-sonu` açar): bu dala
     sormadan commit etme. Adım 4'teki soruda yeni dal öner: `git switch -c <yeni-dal> origin/main` (yerel repo: `main`).
     Commit'lenmemiş değişiklikler yeni dala taşınır, eski WIP commit'leri eski dalda kalır. `switch` çakışma derse DUR.
4. **Ekle ve göster:** dosyaları adıyla ekle. Commit'ten önce (onay soruyorsan sorunun içinde) yalnız dosya listesini
   değil şunları da göster:
   - dal adı: `git branch --show-current`;
   - `main`'e göre ileri/geri: `git rev-list --left-right --count <taban>...HEAD` → `<geri> <ileri>` (taban: remote varsa
     `origin/main`, yerel repoda `main`). İleri > 0 ise o commit'leri de listele (`git log --oneline <taban>..HEAD`): bu dal
     `main`'e taşınırsa onlar da gelir;
   - eklenenler: `git diff --staged --stat`.
   Başka günün `wip/` dalındaysan ya da ileri > 0 ve o commit'leri bu konuşmada sen yazmadıysan commit'ten önce SOR: `ask_user`
   seçenekleri `Yeni dal aç (önerilen)` · `Bu dala commit et` · `İptal`. Cevap gelmezse commit yok.
5. **Commit mesajı:** ilk satır ≤ 72 karakter, ne değişti; boş satır; neden ve etkisi. Projenin kendi mesaj kuralı varsa (`AGENTS.md`) ona uy.
6. **Doğrula:** `git log -1 --stat`. Pre-commit kontrolü başarısız olduysa `--no-verify` ile atlatma; nedeni düzelt.
7. **Push (istenmişse):** hedefi açık yaz: `git push -u origin <dal>`. Sonucu oku. Yerel repoda push yoktur: "remote yok, push yapılmadı" de; remote eklemeyi kendiliğinden yapma.
8. **PR (istenmişse):** ayrı adım. `gh` varsa hedef repo açık: `gh pr create --repo <org>/<repo> --base main --head <dal>`; gövde: özet · değişiklikler · doğrulama (komut → sonuç) · riskler. `gh` yoksa kullanıcıya dal adını ve PR açma adresini ver. Yerel repoda PR yoktur; dalın `main`'e dönüşü adım 9'dur.
9. **Yerel birleştirme (remote yok, `git remote` boş) — kullanıcı dalı `main`'e birleştirmek istediğinde.** Bu adımdaki her soruda cevap gelmezse (ör. `ask_user` "No interactive user … Proceed using your best judgment" döndü) cevap HAYIR sayılır: "best judgment" onay değildir; birleştirme, durumu raporla ve dur.
   1. **Onay:** birleştirme `main`'i değiştirir. Önce göster: dal adı · `git log --oneline main..<dal>` · `git diff --stat main...<dal>` · sonra dalın silinip silinmeyeceği; ardından bu dal için açık onay iste (`ask_user`: `Birleştir` · `İptal`). İstem bu dalın birleştirilmesini açıkça onaylıyorsa yeniden sorma, onay cümlesini raporda aynen aktar. Commit, push ya da "gün sonu" onayı birleştirmeyi kapsamaz.
   2. **Ön koşul:** `git status` temiz olmalı; commit'lenmemiş değişiklik varsa DUR ve sor (birleştirmeye karışmasın).
   3. **Dalda doğrula:** proje `AGENTS.md` "Komutlar" bölümünde test/doğrulama komutu tanımlıysa (yer tutucu `<komut>` değilse) onu dalda koş; tanımlı değilse template klonunun `scripts/doctor.py`'sini proje kökünde koş. FAIL varsa birleştirme yok: DUR, çıktıyı göster. FAIL dalın değişikliğinden kaynaklanmasa da (ör. `main`'de de aynı) atlama kararı kullanıcınındır; birleştirme onayı bu kararı kapsamaz.
   4. **Birleştir:** `git switch main` → `git merge --no-ff <dal>`. `--no-ff` bir birleştirme commit'i yazar; dalın commit'leri geçmişte ayrı görünür kalır. Hızlı ileri (`--ff`, `--ff-only`) dalın izini geçmişten siler. `--squash` dal commit'lerini tek commit'e ezer; git dalı "birleşmemiş" sayar, `git branch -d` silmeyi reddeder ve zorla silmeye iter.
   5. **Çakışma** (`CONFLICT`, `Automatic merge failed`): DUR. Çakışmayı kendin çözme: dosyayı düzenleme, iki tarafı birleştirme, `--ours`/`--theirs`/`-X` kullanma, `git add` + `git commit` ile birleştirmeyi tamamlama. Çakışan dosyaları göster (`git diff --name-only --diff-filter=U`) ve iki seçenek sun: kullanıcı çözer, ya da `git merge --abort` ile `main` birleştirme öncesine döner. Kullanıcı seçene kadar başka git komutu çalıştırma. Cevap gelmezse (HAYIR): yalnız `git merge --abort` çalıştır (henüz çözüm yapılmadığı için kayıp yoktur), `git status` temiz olduğunu göster ve raporla.
   6. **Doğrula:** `git log --oneline --graph -5` (en üstte iki ebeveynli birleştirme commit'i) · `git status` temiz.
   7. **Dalı sil (onay kapsamındaysa):** yalnız `git branch -d <dal>`. Git birleşmemiş dalı silmeyi reddeder; bu bir güvencedir. Reddederse DUR ve bildir. Zorla silme yok: `-D`, `-d -f`, `--delete --force` aynı şeydir. Onay dal silmeyi kapsamıyorsa dalı bırak ve sor.

## Rules
- `--force`, `--no-verify`, `reset --hard`, `clean -f` kullanılmaz (izin kurallarıyla da engellenir).
- Commit, push ve PR aynı komut zincirine konmaz; her adımın sonucu okunur.
- **Hedef açık:** repoyu değiştiren `gh` komutlarında hedef daima yazılır — `pr`/`issue`/`release`/`label` → `--repo <org>/<repo>`; `repo create|edit|delete` → konumsal `<org>/<repo>`; `gh api` → yolun kendisi `repos/<org>/<repo>/…` (`{owner}`/`{repo}` yer tutucusu çalışma dizininden çözülür, kullanılmaz). Başka bir repoda `git` işi → `git -C <repo-kökü> …`. Yanlış repoya yayın geri alınamaz ve `gh` başarı döner.
- **Merge:** yalnız kullanıcının açık onayıyla. Yerel repoda (remote yok) adım 9 uygulanır. PR'da önce CI durumunu oku (`gh pr checks <no> --repo <org>/<repo>`); kırmızı ya da bekleyen kontrolle merge yok. Hükmü `--watch` ekran çıktısından değil durum alanından oku (`gh pr checks <no> --repo <org>/<repo> --json name,state`); `checks --watch ; merge` gibi koşulsuz zincir CI kırmızı bitse de birleştirir. Kolaylık: `scripts/merge_pr.py` CI'yi kendisi okur, bekleyen/başarısız kontrolde durur. `--admin` yalnız "onaylayan yok" şartını aşmak içindir, CI'yi atlatmak için kullanılmaz.
