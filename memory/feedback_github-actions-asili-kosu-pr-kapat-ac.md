---
name: github-actions-asili-kosu-pr-kapat-ac
description: GitHub Actions PR koşusu saatlerce "queued" ve 0 job ile asılı kalırsa cancel/rerun çelişkili döner; tetiğin yansıdığını run_attempt/updated_at ile ölç, yansımadıysa PR'ı kapatıp aynı adımda yeniden aç (GitHub CI'lı repolar ve aXet bakımı)
type: feedback
---

Bir PR kontrol koşusu `queued` durumda ve `jobs total_count=0` ile saatlerce asılıysa cancel/rerun ile uğraşma. Önce yeniden
tetiklemenin gerçekten yansıyıp yansımadığını ölç: `gh api repos/<ORG>/<REPO>/actions/runs/<id>` çıktısında `run_attempt` ve
`updated_at`. Değişmemişse PR'ı kapatıp hemen yeniden aç (`gh pr close <no> --repo <ORG>/<REPO>` ardından `gh pr reopen <no>
--repo <ORG>/<REPO>`; PR kapalı kalmasın). `reopened` olayı taze bir koşu doğurur.

**Neden:** Ekip dersinde iki koşu sabahtan gece yarısına kadar `queued`, 0 job'da kaldı. `gh run cancel` "tamamlanmış koşu
iptal edilemez", `gh run rerun` "zaten çalışıyor" döndü: GitHub tarafında çelişkili, asılı bir durum. Kullanıcı arayüzden
"yeniden tetikledim" dedi ama API'de `run_attempt=1` ve `updated_at` değişmemişti. PR kapatılıp açılınca yeni koşu 20 saniye
içinde doğdu ve başarılı bitti. Workflow dosyası çalışan bir kopyayla birebir aynıydı; kusur dosyada değil asılı koşudaydı.
**Nasıl uygulanır:**
- "Tetikledim" beyanı kanıt değildir; `run_attempt`/`updated_at` ile ölç.
- Kapat/aç'tan önce workflow dosyasının çalışan bir kontrol grubuyla aynı olduğunu gör; farklıysa sorun dosyada olabilir.
- `gh` yoksa aynı iki adım PR sayfasından yapılır; ölçüm REST ucundan (`/repos/<ORG>/<REPO>/actions/runs/<id>`).
- Yeni koşu yeşil bitince birleştirme yine CI koşullu (`%commit-pr` "Merge:" kuralı).
Önceki kayıt: yok (aranan: `memory/`, `maintenance/`, `skills/` — queued, asılı, reopen, run_attempt)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: GitHub Actions kullanan proje repoları ve aXet template bakımı — PR kontrol koşuları
