---
name: ui5-lokal-popup-hesap-kilidi
description: UI5 lokal çalıştırmada logon popup'ı iki ayrı sebep - lrep/varyant 401 (teknik) ya da ısrarlı $metadata 401 (hesap kilidi); ikincisinde deneme yapılmaz
type: feedback
---

Lokal `fiori run` açılınca tarayıcı SAP kullanıcı/parola popup'ı atıp doğru parolayla da geçmiyorsa önce sunucu loguna
bakılır. İki sebep birbirine karıştırılmaz:
(a) Logda `lrep`/flex ya da varyant servisi 401 varsa sebep tekniktir. `index.html` bootstrap'a
`data-sap-ui-flexibility-services="[]"` eklenir, varyant localStorage'a alınır, `start-noflp` kullanılır.
(b) Bu kapalıyken popup ısrarla geliyor ve logda yalnız uygulamanın `$metadata` 401'i varsa büyük olasılıkla **SAP
kullanıcısı kilitlidir**.

**Neden:** Bir ekip (b) durumunda popup'ı defalarca denedi. Denemeler başarısız logon sayacını doldurup kilidi uzattı;
yaklaşık 1 saat kaybedildi. Başka bir kanalın (ADT) 200 dönmesi yanılttı; o kanal önbellekli oturum kullanıyordu.
Kilit SU01'de açılınca popup kalktı.
**Nasıl uygulanır:** (b) belirtisinde başka deneme yapılmaz. Kullanıcıya kilidi SU01'de kontrol ettirmesi ya da Basis'e
açtırması söylenir; parola süresi dolduysa sıfırlanır. Doğru kimlikle sonsuz 401 ama ikisi de değilse `ui5*.yaml` host'u
kanonik mi diye bakılır (alias host). Ayrıntı: `%sap-ui5-fiori` → `references/deploy-and-local-run.md` §1.1.
Önceki kayıt: yok
Son-doğrulama: 2026-09-14 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
