---
name: bash-heredoc-turkce-kacis
description: Kabuk aracına verilen komut metni (heredoc, python -c) Türkçe karakterleri ve ters bölü kaçışlarını hedef programa ulaşmadan bozabilir; Türkçe/kaçışlı içeriği write aracıyla dosyaya yaz, düzeltmeyi kendi print'inle değil dosyayı yeniden okuyarak doğrula
type: feedback
---

Kabuk aracına verilen komut metni hedef programa (Python vb.) ulaşmadan önce bozulabilir: Türkçe/diyakritik karakterler
mojibake olur, tırnaklı heredoc içindeki `\n` gerçek satır sonuna döner. Bozulma kabuk katmanında olur; hedef programda ne
yaparsan yap kaynak metin zaten yanlıştır. Kendi `print("OK")` satırın da aynı kaçış yolundan geçtiği için çıktı da yanıltır.

**Neden:** Ekip dersinde (Windows, Git Bash tabanlı bir kabuk aracı) üç vaka ölçüldü: `python -c` içindeki Türkçe metin
`SyntaxError: invalid character` verdi; tırnaklı heredoc içindeki `'\\n'` Python'a gerçek satır sonu olarak ulaştı, "iki
satırı birleştir" düzeltmesi satırı yeniden böldü ve betik "birleştirildi" yazdı; bir kaçış hatası deneme betiğinin yeniden
üretilmesini engelledi, önceki adımdan kalan ve gerçek yolu taşıyan eski deneme betiği zincirde koşup gerçek dosyaya yazdı.
**Sınır:** vakalar başka bir aracın Git Bash katmanında ölçüldü. aXet'in `bash` aracı Go tabanlı bir emülasyondur (çekirdek
"Kabuk ortamı"); heredoc ve `python -c` davranışı aXet'te ölçülmedi — davranışa dayanmadan önce bir kez ölç. Aşağıdaki
uygulama motordan bağımsız olarak güvenlidir.
**Nasıl uygulanır:**
- Türkçe/diyakritik ya da ters bölü içeren dosya içeriğini, betiği ve düzenlemeyi `write`/`edit` araçlarıyla yaz; kabuk
  heredoc'u ve `python -c` ile değil. Betiği dosyaya yazıp `python <dosya>` ile koş.
- Ters bölü gerekiyorsa betik içinde üret (`chr(92)`), kaynak metne koyma.
- `PYTHONIOENCODING=utf-8` çıktı tarafını düzeltir, girdi bozulmasını düzeltmez; ikisini karıştırma. Çekirdek §4 "Kabuk ortamı"ndaki `python -c` + `PYTHONIOENCODING` önerisi **çıktı** içindir; betiğin kendisi Türkçe metin ya da `\` kaçışı taşıyorsa (girdi tarafı) betiği dosyaya yaz.
- Düzeltmeyi dosyayı yeniden okuyup ölçerek doğrula ([[yesil-sinyal-kapsamini-sor]]).
- Deneme betiği türetiyorsan önce eskisini sil, koşmadan önce gerçek yolu taşımadığını kontrol et, gerçek dosyanın hash'ini
  önce/sonra ölç.
Önceki kayıt: yok (aranan: `memory/`, `core/` — heredoc, mojibake, kaçış, `python -c`; yakın ama farklı:
[[powershell-bom-ve-tirnak]] PowerShell BOM ve tırnak sınıfı, çekirdek "Kabuk ortamı" maddesi çıktı kodlaması)
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'in `bash` aracında ölçülmedi)
Applies-to: tüm projeler — kabuk aracıyla dosya yazan ya da betik koşan iş, Windows
