---
name: ui5-sayfadan-ayrilirken-senkron-xhr
description: Sayfadan ayrılırken (beforeunload/pagehide/unload) senkron XHR Chromium'da sunucuya gitmez, try/catch yutar (navigasyonda ölçüldü) - belge kilidi bırakma fetch+keepalive+CSRF ile; bırakmadan sonra kilit bayrağını sıfırla
type: feedback
---

Sayfadan ayrılırken (`beforeunload`/`pagehide`/`unload`) açılan `XMLHttpRequest(..., false)` Chromium'da sunucuya
**ulaşmaz**; `try/catch` içindeyse hiçbir iz bırakmaz. Doğrusu `fetch(url, {method:"POST", keepalive:true,
credentials:"same-origin", headers:{"x-csrf-token": oModel.getSecurityToken()}}).catch(...)`. `sendBeacon` özel başlık
(CSRF) taşıyamaz.

**Neden:** Bir ekibin ölçümü (Chromium 153, lokal sunucu, üç olay × navigasyonla sayfadan ayrılış): senkron XHR 0/3
(aynı istek normal anda 1/1), `keepalive` fetch 3/3 CSRF başlığıyla; gerçek uygulama fonksiyonlarıyla eski 0/5 · yeni
5/5. Belge kilidi reçetesi "senkron XHR" öneriyordu ⇒ kilit yalnız zaman aşımıyla düşüyordu. **Sınır:** sekme KAPATMA
ayırt edilemedi (`page.close({runBeforeUnload:true})`'da `sendBeacon` dahil hiçbiri ulaşmadı — ölçüm sınırı, iddia
değil); Firefox / Safari / FLP ölçülmedi.
**Nasıl uygulanır:** unload isteğinde `fetch` + `keepalive`; URL `sServiceUrl + "/"` (sondaki `/` `sServiceUrl`'de yok —
unutulursa 307 → 403 "No service found") + ana modelin client parametreleri (bkz. ilgili kayıt). Bırakma artık gerçekten
gittiği için: ekrandan çıkılan her yolda (geri/kayıt/silme) kilit bırakıldıktan sonra kilit bayrağını sıfırla, unload
dinleyicisi bayrağa baksın — yoksa listedeyken sayfadan ayrılınca (yenileme / başka adrese gitme) aynı belgeye tekrar
bırakma gider ve kullanıcının başka sekmedeki kilidi düşer. Reçete `%sap-ui5-fiori` → `freestyle-odata-v2.md` §7.5,
kontrol FE-49 / UI-SAVE-06; backend sözleşmesi `%sap-rap` → `draft-and-locks.md` §6.
İlgili: [UI5 elle kurulan istek sap-client](feedback_ui5-elle-kurulan-istek-sap-client.md).
Önceki kayıt: yok
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi) · Kapsam: freestyle UI5, sayfadan ayrılırken istek gönderen her ekran
