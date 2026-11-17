---
name: belge-incelemesi-iki-tur
description: Büyük ve çok kez revize edilmiş FS/TS'te kontrol listesi turu tek başına yetmez; ayrıca bağımsız, senaryo odaklı bir tasarım incelemesi koşulur ve ilk turun raporu ona verilmez
type: feedback
---

Büyük ve çok kez revize edilmiş bir spesifikasyonun (FS/TS) incelemesi iki ayrı turdur:
1. Kayıt düzeni / kontrol listesi turu.
2. Bağımsız, senaryo odaklı tasarım incelemesi. Eksenler: durum geçişleri, hata ve yeniden deneme, eşzamanlılık, sessiz
   yanlış veri, yetki, tahminsiz kodlanabilirlik, hedef sürüm uyumu, standart veriye yazma. Senaryolar kurulur (en az ~25)
   ve ilk turun raporu bu incelemeye verilmez.

**Neden:** Ekip dersinde kontrol listesi turu WARNING verdi (0 BLOCKER/HIGH; 9 bulgunun 8'i sayım, etiket ya da eşleme).
Kullanıcı az bulguyu şüpheli buldu ve ikinci inceleme istedi. İlk raporu görmeyen senaryo odaklı inceleme 1 BLOCKER (yedek
yol yalnız son kaydı kaydediyordu, satırlar başarılı görünüyordu — sessiz eksik fiyat), 3 HIGH ve 6 MEDIUM buldu. Kontrol
listesi turu yalnız "baktığım yüzeyde bulgu yok" der; durum geçişi, commit sınırı, eşzamanlılık ve birim/ölçek açıkları
senaryo kurulmadan görünmez. Sınır: tek vaka, tek belge; vakada model ve brif birlikte değişti — "daha güçlü model her
zaman daha çok bulur" iddiası ölçülmedi. Ders tur türüne bağlıdır, model adına değil.
**Nasıl uygulanır:** Belge kapısında iki turu ayrı planla; "0 BLOCKER"ı tasarımın doğru olduğu diye okuma, turun kapsam
beyanına bak. Belge incelemesi yöntemi `%sap-fs-ts-docs` referanslarındadır; bu kayıt yalnız tur sayısını ve bağımsızlığı ekler.
Önceki kayıt: bulundu [[yesil-sinyal-kapsamini-sor]] ("0 bulgu" ≠ doğru) — bu kayıt belge incelemesine ikinci tur türünü
ekler; aranan: `memory/`, `skills-sap/sap-fs-ts-docs` (inceleme turu, senaryo)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: FS/TS belge incelemesi (tüm profiller)
