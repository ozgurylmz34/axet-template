---
name: yeni-proje
description: >
  Use when the user wants to start, open or create a new aXet SAP project folder: asks the setup questions one by
  one in chat, confirms a summary, runs scripts/yeni_proje.py first with --dry-run and then for real (git init,
  project skeleton, sap-project.json and AGENTS.md filled, doctor, KURULUMU-TAMAMLA.cmd shortcut), and tells the user
  to double-click that shortcut for the remaining steps. Triggers: "yeni proje", "proje aç", "proje oluştur", "yeni projeye başlıyorum", "projeyi kur".
  Not for creating a package inside an existing project (new_package.py), first-day machine setup (%onboard) or
  template maintenance.
---

# yeni-proje — sorarak SAP projesi kurma

Tek kod yolu: bu skill ve terminal yedeği `yeni-proje.cmd` aynı script'i çağırır:
`<AXET_HOME>/scripts/yeni_proje.py`. `<AXET_HOME>` = bu skill klasörünün iki üstü
(`<AXET_HOME>/skills/yeni-proje/SKILL.md`); yolu buradan türet, varsayma, kullanıcıya özel yol yazma.

## When to use this skill
- Kullanıcı yeni bir proje klasörü açmak, oluşturmak ya da kurmak istiyor.
- **Kullanma:** var olan projeye paket eklemek (`new_package.py`) · makine kurulumu, ilk gün (`%onboard`) ·
  template bakımı.

## How to use this skill
1. **Soruları sohbette TEK TEK sor** (her soruda öneri/seçenek ver, bir cevap gelmeden sonrakine geçme):

   | # | Alan | Bayrak | Seçenek / öneri |
   |---|---|---|---|
   | 1 | Proje klasörü (tam yol; yoksa oluşturulur) | konumsal | template reposunun, başka bir git reposunun ya da `.git`'in içi olamaz; ad nokta/boşlukla bitmez, `CON`/`NUL` gibi ayrılmış ad olmaz |
   | 2 | Proje adı | `--name` | klasör adı; harf, rakam, `.` `_` `-`, boşluksuz |
   | 3 | SAP profili | `--sap-profile` | `ecc` · `s4_private` · `s4_public` · `btp_abap` |
   | 4 | SAP sürümü | `--release` | ör. `2023`; bilmiyorsa ekip sorumlusuna sorsun, uydurma |
   | 5 | master_language | `--master-language` | 2 harf (ör. `TR`); Z obje metin dili, emin değilse ekip sorumlusu |
   | 6 | cleancore_policy | `--cleancore-policy` | YALNIZ `s4_private`'ta sor ve ver: `strict` · `balanced` (profil varsayılanı) · `classic`. Diğer profillerde politika ekseni yok: verilirse script uyarır ve boş yazar |
   | 7 | source_root | `--source-root` | `SOURCE_CODES` |
   | 8 | Amaç (tek satır) | `--purpose` | zorunlu |
   | 9 | Teknoloji | `--tech` | profilden önerilir (ör. `SAP S/4HANA ABAP`) |
   | 10 | Depo | `--repo` | remote adresi ya da `yerel`; http(s) adresinde kullanıcı/parola/token, scp biçiminde (`kul:parola@host:yol`) parola olamaz; ayrıştırılamayan adres ve belirsiz scp adresi (`@` öncesinde `/` ya da birden çok `@`) de reddedilir (script reddeder). Sınır biçimleri reddedilmez, uyarıyla kabul edilir: http(s) adresinin yolunda/sorgusunda `@` varsa (ör. `https://host/~kul@ekip/r.git`, `https://TO/KEN@host`) script `! UYARI: depo: …` basar — bu uyarıyı kullanıcıya ilet. `--repo` verilmezse origin önerilir; origin güvenle temizlenemezse `yerel` yazılır ve uyarı basılır |
   | 11 | Test / çalıştırma / doğrulama komutu | `--test-cmd` `--run-cmd` `--lint-cmd` | boş geçilebilir |
   | 12 | Proje kuralları | `--rule` (her kural için ayrı) | boş geçilebilir; nötr varsayılan yazılır |

   Metinlerde `<` `>` ve ters tırnak kullanma; script bunları yer tutucu sayıp reddeder.
2. **Özetle ve onay al:** tüm değerleri tek tabloda göster, "doğru mu?" diye sor.
3. **Önce plan:** bayraklı çağrı, `--no-input --dry-run` ile. Değer içeren her argümanı çift tırnakla:
   ```
   python "<AXET_HOME>/scripts/yeni_proje.py" "<klasör>" --no-input --dry-run --name <ad> --sap-profile <profil> --release "<sürüm>" --master-language <dil> --cleancore-policy <politika> --purpose "<amaç>" --rule "<kural>"
   ```
   Çıktıyı kullanıcıya göster (klasör/git durumu, doldurulacak alanlar, `[KORUNDU]` ve `!` satırları).
   Dry-run çıkış 1 (`PLAN SORUNLU`) verdiyse gerçek çağrıya geçme; `!` satırlarını kullanıcıyla çöz.
4. **Onayla gerçek çağrı:** aynı komut `--dry-run` olmadan.
5. **Sonucu raporla:** `DOĞRULAMA` satırları, `UYARILAR` ve `doctor` `SONUÇ:` satırı. Çıkış kodu:
   - 0 kuruldu.
   - 1 bir adım, doğrulama ya da doctor başarısız ya da **ÇELİŞKİ**: var olan `sap-project.json`'daki
     `sap_profile`/`master_language` istenenden farklı. Hangisinin doğru olduğunu kullanıcıya sor; dosyayı sen
     değiştirme. Düzeltilince aynı komut yeniden çalıştırılabilir (var olanı ezmez).
     Kullanıcı `sap-project.json`'u düzeltirse `AGENTS.md`'deki `- SAP` satırını da **elle** aynı profile ve
     master_language'e getirmesini söyle: araç doldurulmuş satırı yeniden yazmaz; satır json'la çelişiyorsa ya da
     okunamıyorsa (`ÖLÇÜLEMEDİ`) çıkış yine 1 olur.
   - 2 girdi hatası (hiçbir şey yazılmadı; eksik ya da hatalı alanı sor).
   `[KORUNDU]` + `UYARILAR` satırı (ör. `release` farkı) çıkışı bozmaz; farkı kullanıcıya söyle.
6. **Son adımı tek cümleyle söyle** (script'in sonda bastığı `SON ADIM (SENDE)` satırı): "Proje klasöründeki
   `KURULUMU-TAMAMLA.cmd`'ye çift tıkla." Kısayol, klondaki `proje-tamamla.cmd`'yi çağırır ve sırayla:
   ① `conn\DEV.env` / `conn\QA.env` bağlantı şablonlarını yazar ve hangi dosyaya (tam yol; DEV zorunlu, QA isteğe
   bağlı) hangi alanları yazacağını söyler — editör açmaz, soru sormaz (kullanıcı doldurur, kaydeder, tekrar
   çift tıklar; dosyalar denetlenir, hatalı alan adıyla gösterilir, değer basılmaz; geçerli DEV aktif sistem olur)
   ② davranış yüzeyi onayını sorar ③ `doctor.py` ④ aXet'i projede açmayı sorar (ilk satırda `proje: <ad>` görünmeli).
   Kısayol yazılamadıysa (`[YAZILAMADI]`) script'in bastığı elle yolu ver. Sistem değiştirmek için sonra `%sistem`.

## Rules
- **Kimlik bilgisi:** kullanıcı adı, parola, host, sistem bilgisi isteme ve yazma; `.conn_adt` ve `conn/` okuma,
  listeleme. Bağlantı bilgisini kullanıcı `KURULUMU-TAMAMLA.cmd`'nin hazırladığı `conn\*.env` şablonlarına kendisi yazar.
- `setup_credentials.py`, `behavior_manifest.py generate` ve `KURULUMU-TAMAMLA.cmd` / `proje-tamamla.cmd`'yi
  **çalıştırma**, `start` ile pencere de **açma**: bağlantı bilgisi ve davranış yüzeyi onayı kullanıcının kendi
  işlemidir; pencereyi modelin başlatması onayı modelden başlatmak olur (izin kurallarının amacının etrafından
  dolanır). `generate`'i ayrıca aXet izin kuralları engeller.
- Script'i bayraksız (etkileşimli) çağırma: aXet kabuğunda terminal yok. Her zaman `--no-input`.
- SAP'de paket ya da transport yaratmayı önerme: paketi kullanıcı SE21 ile yaratır, sonra `new_package.py`.
- aXet'in kendi "Initialize Project" komutunu bu projede önerme: `AGENTS.md`'yi yeniden yazıp kesin yasak damgasını
  ve doldurulan alanları bozabilir (DOĞRULANMADI — ölçülmedi; bozulursa `doctor.py` damgayı FAIL gösterir).
- Hata çıkarsa değeri tahmin edip yeniden deneme: hatayı göster, doğru değeri kullanıcıya sor.
