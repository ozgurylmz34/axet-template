---
name: commit-pr
description: Use when the user asks to commit, push, create a branch or open a pull request ("commit et", "push et", "dal aç", "PR aç", "değişiklikleri gönder").
---

# Commit, push ve PR disiplini

## When to use this skill
Yalnız kullanıcı commit / push / PR istediğinde. Kendiliğinden commit ya da push yapma.

## How to use this skill
1. **Oku:** `git status`, `git diff` ve `git diff --staged`. Alakasız değişiklik varsa hangilerinin girmesi gerektiğini sor.
2. **Kimlik bilgisi taraması:** eklenecek dosyalarda `password|passwd|secret|token|api[_-]?key|BEGIN .*PRIVATE KEY` desenlerini `grep` ile ara; `.conn*`, `*.env` gibi dosyalar eklenmesin. Şüphe varsa DUR ve kullanıcıya göster.
3. **Dal:** `main` üzerindeysen yeni dal aç ve başlangıç noktasını açık yaz:
   - remote varsa: `git fetch origin` → `git switch -c <dal> origin/main`
   - yerel repo: `git switch -c <dal>`
4. **Ekle:** dosyaları adıyla ekle; ne eklediğini `git diff --staged --stat` ile göster.
5. **Commit mesajı:** ilk satır ≤ 72 karakter, ne değişti; boş satır; neden ve etkisi. Projenin kendi mesaj kuralı varsa (`AGENTS.md`) ona uy.
6. **Doğrula:** `git log -1 --stat`. Pre-commit kontrolü başarısız olduysa `--no-verify` ile atlatma; nedeni düzelt.
7. **Push (istenmişse):** hedefi açık yaz: `git push -u origin <dal>`. Sonucu oku.
8. **PR (istenmişse):** ayrı adım. `gh` varsa hedef repo açık: `gh pr create --repo <org>/<repo> --base main --head <dal>`; gövde: özet · değişiklikler · doğrulama (komut → sonuç) · riskler. `gh` yoksa kullanıcıya dal adını ve PR açma adresini ver.

## Rules
- `--force`, `--no-verify`, `reset --hard`, `clean -f` kullanılmaz (izin kurallarıyla da engellenir).
- Commit, push ve PR aynı komut zincirine konmaz; her adımın sonucu okunur.
- **Hedef açık:** repoyu değiştiren `gh` komutlarında hedef daima yazılır — `pr`/`issue`/`release`/`label` → `--repo <org>/<repo>`; `repo create|edit|delete` → konumsal `<org>/<repo>`; `gh api` → yolun kendisi `repos/<org>/<repo>/…` (`{owner}`/`{repo}` yer tutucusu çalışma dizininden çözülür, kullanılmaz). Başka bir repoda `git` işi → `git -C <repo-kökü> …`. Yanlış repoya yayın geri alınamaz ve `gh` başarı döner.
- **Merge:** yalnız kullanıcının açık onayıyla. Önce CI durumunu oku (`gh pr checks <no> --repo <org>/<repo>`); kırmızı ya da bekleyen kontrolle merge yok. `--admin` yalnız "onaylayan yok" şartını aşmak içindir, CI'yi atlatmak için kullanılmaz.
