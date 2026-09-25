---
name: yerel-suit-ci-ikizi-degil
description: Yerel test takımı CI'nin ikizi değildir — aynı commit Windows'ta yeşil, Linux CI'da kırmızı olabilir; kapanış kanıtı CI koşumudur; takımı ritüelle değil, değişiklik takımın ölçtüğü kodu etkiliyorsa koş (CI'lı repolar ve aXet bakımı)
type: feedback
---

Yerel takım ile CI aynı kodu koşsa da aynı ortamı koşmaz. "Yerelde yeşil ⇒ CI'da yeşil" bir çıkarım değil bir varsayımdır.
Kabuk, yol, dosya sistemi ya da satır sonu davranışına dokunan bir değişiklikte kapanış kanıtı yerel yeşil değil CI
koşumudur; PR'ı açıp CI'yi hakem yapmak ucuz ve dürüst bir ölçümdür.

**Neden:** Ekip dersinde aynı commit Windows'ta 10'dan fazla ardışık koşumda 145/145 geçti ve mutasyon testi yakalandı;
`ubuntu-latest` CI'da tek koşumda 144/145 verdi ve aynı mutasyon kaçtı. Kusur üretim kodunda değil test korpusundaydı: yol
çıkarımını sınayan bir vaka Linux'ta mutasyonu ayırt edemiyordu — kanıtın kapsamı tek işletim sistemiydi. Ters yönde bir
vakada da yalnız bir ajan tanımı satırı ve bir docstring değişmişken "gün sonu" alışkanlığıyla tam takım başlatıldı; 7 dakika
koştu, kullanıcı durdurdu ("gerekmiyorsa neden çalıştırıyorsun").
**Nasıl uygulanır:**
- Kabuk/yol/dosya sistemi davranışını sınayan testin en az bir bağlamı başka bir işletim sistemi olmalı; "başka dizin" yetmez.
- Düzeltmeyi "yerelde yeşil" diye kapatma; merge'i CI'ye bağla (aXet reposunda `.github/workflows/testler.yml`).
- Takımı koşma kararı `git diff --stat`'tan: dokunulan dosya takımın ölçtüğü çalıştırılabilir kod mu (script, test, hook,
  doğrulayıcı)? Yalnız markdown/yorum/docstring/hafıza değiştiyse takım yeni bilgi üretmez; emin değilsen hedefli
  `python tests/run_tests.py -k <desen>` koş.
- Yeşil takım yalnız baktığı yüzey kadar şey söyler: [[yesil-sinyal-kapsamini-sor]].
Önceki kayıt: bulundu [[yesil-sinyal-kapsamini-sor]] (geçen test takımı kapsamı kadar söyler) — bu kayıt ortam farkını ve
takımın ne zaman koşulacağını ekler; aranan: `memory/`, `core/`, `maintenance/UPDATE-PROCEDURE.md` — CI, yerel, takım
Son-doğrulama: 2026-09-25 (ekip dersinden uyarlandı; aXet'te ayrıca ölçülmedi)
Applies-to: CI'lı proje repoları ve aXet template bakımı — test koşumu ve kapanış kanıtı
