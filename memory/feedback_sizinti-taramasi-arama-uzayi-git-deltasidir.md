---
name: sizinti-taramasi-arama-uzayi-git-deltasidir
description: Gerçek veri, müşteri adı ya da kimlik bilgisi sızıntısı taramasında arama uzayı "teslim ettiğim dosyalar" değil, dalın hedefe taşıyacağı TÜM farktır (commit'li + commit'siz); kirli çıktının üreticisi de o uzaydadır
type: feedback
---

Sızıntı taraması (gerçek müşteri adı, kişisel veri, canlı ana veri, parola/token) yaparken arama uzayı bir rol tanımı
("teslim dokümanları", "eklediğim dosyalar") değildir. Uzay şudur:
`git diff --name-only origin/main...HEAD` ∪ `git status --porcelain` — yani dalın `main`'e taşıyacağı her dosya.
Birleştirme, dosyanın rolüne bakmadan farkın tamamını hedefe yazar. Remote yoksa `origin/main` yerine yerel `main` kullan.

**Neden:** Ekip dersinde bir doküman incelemesi "gerçek müşteri verisi" bulgusu verdi; düzeltmeden sonra tarama "0 eşleşme"
dedi, çünkü yalnız belge dosyalarına bakılmıştı. İkinci tur yan klasördeki test verisi üretiminde gerçek müşteri unvanı ve
cari numarası buldu. Doğru uzay kurulunca (101 dosya) gerçek kirlilik 7 dosyadaydı; kalan 8 eşleşme zararsızdı (dizin adı,
mühendislik notu, hedefte zaten olan dosya). Üreten script gerçek müşteri kaydını canlı tablodan okuduğunu yorumunda
yazıyordu: yalnız çıktıyı temizlemek bir sonraki koşumda kirliliği geri getirirdi. Aynı vakada `??` işareti "henüz
commit'lenmedi" sanıldı; oysa 14 dosyanın 14'ü dalda zaten commit'liydi.
**Nasıl uygulanır:**
- Taramadan önce uzayı git'e ürettir ve dosya sayısını yaz ("N dosya tarandı"); sayı yoksa uzay beyan edilmemiştir.
- `%commit-pr` adım 2'deki kimlik bilgisi taraması eklenen dosyalara bakar; birleştirmeden önce aynı taramayı bu uzayda koş.
- Her eşleşmeyi ayır: dizin adı / genel anlatı ≠ teslim verisi; ham eşleşme sayısı bulgu sayısı değildir.
- PDF/HTML gibi türetilmiş çıktıda metni çıkarıp tara. Kirli çıktı bulursan üreticiyi aç, düzeltmeyi orada yap, çıktıyı
  yeniden üret ([[kanit-kapsam-ve-zaman-korunur]] madde 4).
- Bir dosyanın hedefte olup olmadığını `??` işaretinden değil `git cat-file -e origin/main:<dosya>` ile ölç.
Önceki kayıt: bulundu [[kanit-kapsam-ve-zaman-korunur]] (üreticinin girdisi) ve `skills/commit-pr/SKILL.md` adım 2 (eklenen
dosyalarda kimlik taraması) — bu kayıt uzayın tanımını ekler; aranan: `memory/`, `core/`, `skills/` — sızıntı, origin/main,
kimlik taraması, genericize
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — PR/birleştirme öncesi veri ya da kimlik sızıntısı taraması; özellikle dışa açık repolar
