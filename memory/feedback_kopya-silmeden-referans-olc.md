---
name: kopya-silmeden-referans-olc
description: Aynı içerikli (aynı hash) dosyaları silmeden ya da tek kaynağa indirmeden önce her kopyayı kimin kullandığını ölç
type: feedback
---

Aynı hash içerik eşitliğini söyler, kullanım eşitliğini söylemez. Birden çok yerde duran aynı dosya "kopya" diye
toptan silinmez.

**Neden:** Bir temizlikte aynı hash'li dosya ailesi silinseydi, kendi kopyasını yükleyen çalışan bir uygulamanın
yolu kırılacaktı. İçerik aynıydı, tüketici farklıydı. Silinen dosya kolay geri gelir; kırılan uygulama ise fark
edilene kadar bozuk kalır.
**Nasıl uygulanır:** Silmeden önce her kopya için kim yüklüyor/import ediyor ölç (`grep` ile import, require,
manifest, yol dizgesi; `lsp_references`, `code_graph`; SAP objesinde where-used). Referansı olan kopya silinmez.
Tek kaynağa indirme, tüm tüketiciler yeni kaynağa bağlandıktan sonra yapılır. Tersi de geçerli: "kullanan bulunamadı"
sonucu aramanın kapsamıyla birlikte yazılır, tek başına "yetim" kanıtı değildir.
Önceki kayıt: yok
Son-doğrulama: 2026-09-13 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
