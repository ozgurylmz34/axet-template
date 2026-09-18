---
name: powershell-bom-ve-tirnak
description: Windows PowerShell 5.1 dosyaya UTF-8 BOM ekler (JSON/YAML kırılır) ve native komuta giden argümandaki gömülü çift tırnağı parçalar (git commit -m pathspec hatası)
type: feedback
---

İki sessiz PowerShell 5.1 tuzağı:

1. **BOM.** `Set-Content -Encoding utf8` ve `Out-File -Encoding utf8` dosyanın başına UTF-8 BOM (`EF BB BF`) yazar;
   5.1'de `utf8NoBOM` yoktur. Dosya ekranda doğru görünür ama JSON/Node/UI5 araçları `Unexpected token` ile çöker.
2. **Gömülü çift tırnak.** `git commit -m @'...'@` içinde `"kelime"` geçerse PowerShell native komut satırını
   yeniden kurarken tırnağı kaçışlamaz; git kalan kısmı pathspec sanar: `error: pathspec '...' did not match`.

**Neden:** Bir vakada `package.json`'a BOM girdi ve yerel sunucu açılmadı. Başka bir vakada çift tırnaklı 2 commit
mesajı 2 kez pathspec hatası verdi, tırnaksız 3 mesaj temiz geçti.
**Nasıl uygulanır:**
- Araçların okuyacağı dosyaları (json, yaml, properties, abap) aXet'in `write`/`edit` araçlarıyla yaz — BOM eklemedikleri
  ölçüldü (aXet 1.3.0: yazılan dosyanın ilk baytı doğrudan içerik). PowerShell mecburiyse:
  `[IO.File]::WriteAllText($p, $c, (New-Object System.Text.UTF8Encoding $false))`.
- Şüphede ilk baytlara bak: `[IO.File]::ReadAllBytes($p)[0..2]` → `239,187,191` = BOM.
- PowerShell'den verilen commit/PR mesajında çift tırnak kullanma (tek tırnak ya da tırnaksız yaz) ya da mesajı
  dosyaya yazıp `git commit -F <dosya>` kullan.
- Sınır: ölçümler PowerShell 5.1 + Git for Windows; pwsh 7 ölçülmedi.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (BOM'suz yazım aXet'te ölçüldü; PowerShell davranışı ekip dersinden, burada yeniden ölçülmedi)
