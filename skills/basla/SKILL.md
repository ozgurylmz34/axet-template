---
name: basla
description: >
  aXet oturumunu açar: oturum özetini (session_brief.py) taze çalıştırır, kimlik satırını ve özetten en fazla
  5 satırı yazar, açık iş varsa hangisiyle devam edileceğini sorar. Her yeni aXet oturumunun ilk mesajı olarak
  kullanıcı %basla yazar. Oturumun ilk mesajı "başla", "oturumu aç", "açılış özeti" ya da "neredeyiz" ise de
  çalıştır; oturum ortasındaki "tamam, başla" gibi onaylar bu skill'i ÇAĞIRMAZ.
---

# basla — oturum açılışı

> Oturum açılışı otomatik tetiklenmez (aXet'te hook yok; model ilk mesajın türüne göre açılışı atlayabiliyor —
> ölçüldü). Açılışın tek güvenilir yolu kullanıcının her yeni oturumu `%basla` ile açmasıdır.

## How to use this skill
1. **Özeti çalıştır:** proje `AGENTS.md` "Oturum" bölümündeki `session_brief.py` komutu. Bölüm yoksa
   `<AXET_HOME>/scripts/session_brief.py`; `<AXET_HOME>` = bu skill klasörünün iki üstü
   (`<AXET_HOME>/skills/basla/SKILL.md`) — yolu buradan türet, varsayma.
   Bulunulan dizin proje kökü değilse komuta `--project-dir "<proje kökü>"` ekle. Komut özeti
   `.axet-code/acilis-brief.md`'ye de yazar.
   Çalışmazsa hatayı aynen göster; özeti tahminle üretme. O durumda bağlamdaki "AÇILIŞ BRIEF'İ" bloğunu üretim
   saatiyle aktar; tarihi bugün değilse `— BAYAT` yaz.
2. **Yanıtı yaz — bu adım koşulsuzdur, atlanmaz.** Bu yanıt çekirdek §0/§8 açılışının KENDİSİDİR: kimlik satırını ve
   özeti bir kez yaz, bağlamdaki eski brief'ten ayrıca aktarma. Yanıtının ilk satırı çekirdek §0'daki kimlik satırıdır
   (değerleri yalnız bağlamında gördüğün kimliklerden doldur, göremediğine `YOK` yaz). Ardından
   `Açılış brief'i: <üretim saati>` ve özetten en fazla 5 satır: dal/değişiklik uyarısı, template güncelliği,
   FAIL/WARN, SAP profili, aktif paketin son kaydı, aktif işler ve devir notu.
3. **Sor:** açık iş ya da devir notu varsa hangisiyle devam edileceğini sor; yoksa "Ne üzerinde çalışalım?" de.
   Kullanıcı cevap vermeden işe başlama.

## Kurallar
- `%basla`'dan sonra aynı oturumda gelen mesajlarda kimlik satırını ve özeti tekrar yazma.
- Özet FAIL gösteriyorsa (ör. doctor) onu ilk satırlarda söyle; iş seçiminden önce çözülmesini öner.
- Özet "template eski" diyorsa `%guncelle`, "proje şablonu eski" diyorsa `%guncelle-proje` öner; kendiliğinden çalıştırma.
