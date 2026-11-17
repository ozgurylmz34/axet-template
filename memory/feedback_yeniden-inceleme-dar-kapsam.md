---
name: yeniden-inceleme-dar-kapsam
description: Düzeltme sonrası yeniden inceleme yalnız o turun değişen satırlarına ve çağıranlarına bakar; yalnız yüksek önemdeki bulgu yeni tur açar, orta/düşük bulgu aynı turda düzeltilir
type: feedback
---

Bir düzeltme turundan sonraki bağımsız inceleme (`%code-review`, `%sap-code-review`) yalnız o turda değişen satırlara ve
onların doğrudan çağıranlarına bakar; dosyanın ya da paketin tamamı yeniden taranmaz. Yeni bir build'in ilk incelemesi tam
kapsamlı kalır.

Hüküm kuralı:
- Yalnız yüksek önemdeki bulgu (derlenmeyen kod, sessiz yanlış veri/fiyat, kesin yasak ya da güvenlik ihlali) BLOCKER'dır ve
  yeni bir düzeltme turu açar.
- Orta/düşük bulgu "aynı turda düzelt" listesine girer ve yeniden inceleme açılmadan geçer — iki koşulla: ① düzeltme yalnız
  bulgunun gösterdiği yeri ve değişen değerin/adın diğer geçtiği yerleri değiştirir, o yerler düzeltmeyi yapan tarafından
  taranmıştır (özet satırı, indeks satırı, PR gövdesi, kardeş kayıt dahil) ② yeni mantık dalı, yeni dosya ya da bulgu dışı
  davranış değişikliği getirmez. Biri tutmuyorsa o yüzey bir sonraki dar incelemeye girer.
- Tam regresyon tur sonunda bir kez koşulur.

**Neden:** Ekip dersinde build → inceleme → düzeltme → yeniden inceleme döngüsü saatlerce uzadı; kullanıcı "kaç defa
çalışacak, ne zaman bitecek" dedi. İncelemeler gerçek yüksek bulgular yakaladı (derlenmeyen çağrı, para birimi ondalığı
yüzünden 100 kat yanlış fiyat); maliyetli olan inceleme değil, kapsamı ve orta/düşük bulgularda yeni tur açmasıydı. Kullanıcı
dar kapsam kuralını onayladı. Koşul ① eski bir vakadan gelir: "gösterilen yer düzeltildi, kopyası kaçtı".
**Nasıl uygulanır:** Yeniden inceleme brifine iki satır yaz: kapsam ("yalnız bu turun farkı + çağıranları") ve hüküm kuralı
("yalnız yüksek bulgu BLOCKER; orta/düşük düzeltme listesine, WARNING"). Bağımsız inceleme kuralının kendisi geçerliliğini
korur ([[kendi-isini-yeniden-siniflandirip-kural-disina-cikma]]); yalnız yeniden incelemenin kapsamı daralır.
Önceki kayıt: bulundu [[kendi-isini-yeniden-siniflandirip-kural-disina-cikma]] (incelemeyi atlama) — bu kayıt yeniden
incelemenin kapsamını ekler; aranan: `memory/`, `skills/code-review` (yeniden inceleme, re-gate, tur)
Son-doğrulama: 2026-11-17 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: tüm projeler — build → bağımsız inceleme → düzeltme döngüsü
