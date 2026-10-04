# Kontrol listesi — Yol D (XDP + `RENDER_PDF`)

> Bu yolda uygulanan satırların **tek yeri** burasıdır. SFP yolunun (form objesi var) satırları — iş bölümü, driver,
> interface sözleşmesi, `FP_*` deseni, adlandırma — Yol D'de **uygulanmaz** (interface/driver programı yoktur; çağıran Z
> sınıf/FM projenin genel adlandırmasına uyar) ve `%sap-classic-abap` → `references/forms-f1-help.md`'dedir.
> Önem: BLOCKER = geçmeden ilerleme yok · WARNING = düzelt ya da gerekçesini kullanıcıya yaz.

| ID | Kontrol | Önem | Nasıl ölçülür | Kaynak |
|---|---|---|---|---|
| AF-005 | Çağıran kod Z namespace'te; **standart output objesine dokunulmaz**; NAST/NACE/ADS yapılandırması operatör/Basis işidir | BLOCKER | kod incelemesi; yasak A | kesin yasaklar |
| AF-XDP-01 | Yol D kullanıcının **açık seçimi** (Designer bakımı olmayacağı söylendi); yasal çıktı (e-İrsaliye/e-Fatura) DEĞİL | BLOCKER | kullanıcının cümlesi kayıtta (paket `SESSION_NOTES.md` ya da TS) | `recete.md` §1 |
| AF-XDP-02 | `.xdp` + örnek veri `.xml` repoda kaynak; ABAP'taki kopya **üretici script**le üretilir ve güncel (elle kopya YOK) | WARNING | `scripts/xdp_abap_uret.py … --check` çıkış 0 | `recete.md` §5.5 |
| AF-XDP-03 | **Çok kolonlu tablo satırlarında** (`lr-tb`) kolon toplamı kapsayıcıdan **1 mm küçük**; kasıtlı sarılan kart ızgaraları hariç | WARNING | `scripts/xdp_denetle.py` XDP-03 UYARI 0 (BİLGİ satırları okunur) + PDF'e bakış | `recete.md` §5.1 |
| AF-XDP-04 | Büyük harfli sabit etiketlerde yabancı sözcük `İ` taraması (`BOOKİNG` ✗) | WARNING | `scripts/xdp_denetle.py` XDP-04 listesi tek tek okundu | `recete.md` §5.2 |
| AF-XDP-05 | `typeface="Arial"` + `embed_fonts = abap_true`; locale = projenin yerel ayarı (TR projede `tr_TR`) | BLOCKER | `scripts/xdp_denetle.py --locale tr_TR` XDP-05 UYARI 0 + ABAP'ta `embed_fonts` (denetçi görmez) | `recete.md` §2, §5.4 |
| AF-XDP-06 | Deneme koşusunda `ev_pages` beklenenle aynı **ve** PDF açılıp gözle okundu (bayt/sayfa yerleşim kusurunu söylemez) | BLOCKER | `scripts/pdf_coz.py` SAYFA satırı + PDF'i aç | `recete.md` §5.6 |
| AF-XDP-07 | Mail gönderen deneme koşusu **tek istek** (zaman aşımı/500'de tekrar YOK, önce SOST/SOOD); deneme sınıfı iş bitince silinir | WARNING | koşu kaydı; `adt_inactive_objects` / `adt_get` ile sınıfın silindiği | `mail-eki.md` §5 |

Ek (reçete tuzakları, kontrol listesi satırı olmayan):
- [ ] `activity="layout:ready"` yok — `activity="ready" ref="$layout"` (`xdp_denetle.py` R-3.7 HATA 0).
- [ ] Uzun metin alanları `multiLine="1"` + `minH`, sabit `h` yok (`xdp_denetle.py` R-3.3).
- [ ] Bağlama simülasyonu hata 0, bağlanmayan veri yaprakları bilinçli (`xdp_abap_uret.py` BAĞLAMA satırı).
- [ ] Veri XML'ine giden numaralar `ALPHA = OUT` sonrası `condense( )` / `shift_right( )` (`recete.md` §5.8).
- [ ] Mail varsa: gönderen politikası soruldu, deneme yalnız kullanıcının kendi adresine, RAP'tan ise ayrı LUW (`mail-eki.md`).
