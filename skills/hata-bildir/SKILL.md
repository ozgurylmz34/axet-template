---
name: hata-bildir
description: Use when the user wants to report an aXet bug, a wrong or missing rule or skill behavior, or send an improvement suggestion to the aXet maintainers, or says "hata bildir", "sorun bildir", "aXet'e bildir", "issue aç", "öneri gönder", "bunu aXet ekibine ilet". Prepares a leak-free, evidence-based report file in the project; the user sends it (GitHub Issue form if they have an account, otherwise to the person or team who installed aXet). Never opens an Issue itself.
---

# aXet'e hata / öneri bildir

## When to use this skill
- Kullanıcı aXet'in (çekirdek kurallar, skill'ler, kurulum/güncelleme araçları, `doctor.py`) yanlış davrandığını, bir şeyin eksik olduğunu ya da bir iyileştirme önerisini aXet bakımcılarına iletmek istiyor.
- Kullanıcı "issue aç" dese bile bu akış izlenir: **Issue'yu sen açmazsın**; bildirimi hazırlarsın, kullanıcı gönderir.
- Kullanıcı aXet'i başkalarına kuran kişiyse ve ekibinden gelen bir bildirim dosyasını Issue'ya taşıyacaksa: 10. adım (aracı).

**Bu akış DEĞİL:**
- SAP sistemindeki sorun (dump, yetki, transport, sistem ayarı) → SAP ekibinin/Basis'in işidir; aXet'e bildirilmez. Sorun aXet'in bir SAP aracının yanlış davranmasıysa bildirilir.
- `doctor.py` FAIL veriyorsa önce kurulum sorunudur: `<AXET_HOME>/docs/onboarding.md` "Sorun giderme" bölümünü uygula. FAIL kapanmıyorsa ya da çözüm yanlış görünüyorsa o zaman bildir.
- Projeye özel bir kural/karar → `%remember`.

`<AXET_HOME>` = bu skill klasörünün iki üstü (`<AXET_HOME>/skills/hata-bildir/SKILL.md`); yolu buradan türet, varsayma, kullanıcıya özel yol yazma.

**Bildirim neden bu kadar ayrıntılı:** bakımcı gelen metni kanıt değil **ihbar** sayar ve her iddiayı güncel aXet'te kendisi yeniden ölçer (bkz. "Gönderdikten sonra"). Yeniden üretilemeyen bildirim çoğu zaman "üretilemedi" ile kapanır. Ayrıntı, bildirimin sonuç vermesini sağlar.

## How to use this skill
1. **Konuyu netleştir.** Kullanıcıya sor (bildiklerini tekrar sorma): ne yapıyordun · hangi adımları izledin · ne bekliyordun, ne oldu · hata mı öneri mi. Tek cümlelik özet çıkar: *hangi mekanizma, hangi koşulda, ne yanlış yapıyor*. "Çalışmıyor" tek başına bildirim değildir. Tek bildirim tek konu: iki ayrı sorun iki ayrı dosyadır. Bir konuda birden çok iddia varsa numarala (İ1, İ2 …); bakımcı her birini ayrı ölçer.
2. **Kurulum mu, aXet mi?** `python "<AXET_HOME>/scripts/doctor.py"`: son satırdaki `SONUÇ: N FAIL · M WARN` sayılarını ve `[PASS]` satır sayısını al. Konuyla ilgili FAIL varsa önce onboarding "Sorun giderme"yi uygula; FAIL kapanınca sorun da kapanıyorsa bu bir bildirim değil, kurulum adımıdır.
3. **Güncel aXet'te hâlâ var mı?** Klonun geride olabilir; bakımcı bildirimini güncel sürüme karşı okur. Salt-okur ölç (çalışma ağacını değiştirmez; ağ gerekir, hesap gerekmez):
   ```bash
   git -C "<AXET_HOME>" fetch -q origin
   git -C "<AXET_HOME>" rev-list --count HEAD..origin/main
   git -C "<AXET_HOME>" grep -n -i "<konu kelimesi>" origin/main -- guncelle/yayinlar.json
   ```
   - İkinci komut 0'dan büyükse klon geride demektir. Üçüncü komut bir yayın kaleminde konuyu buluyorsa kalemi kullanıcıya göster: sorun o yayında düzeltilmiş olabilir → önce `%guncelle`, sonra yeniden dene; hâlâ varsa bildir.
   - Bildirim **"X aXet'te yok"** diyorsa bu en pahalı iddiadır: `git -C "<AXET_HOME>" grep -n -i "<desen>" origin/main -- .` ile tüm ağaçta ara (yalnız `skills/` değil; `core/`, `skills-sap/`, `docs/`, `scripts/` de) ve aramanın kendisini (desen, sonuç sayısı) kapsam beyanına yaz.
   - Komut ağ ya da izin nedeniyle çalışmazsa alanlara "ölçülemedi: <neden>" yaz ve devam et; bildirimi bu yüzden durdurma.
4. **Aynı konu zaten bildirilmiş mi?** `git -C "<AXET_HOME>" remote get-url origin` adresi `github.com` ise kullanıcıya arama adresini ver: `https://github.com/<sahip>/<depo>/issues?q=<konu kelimesi>` (`<sahip>/<depo>` bu adresten, `.git` uzantısı atılarak). Herkese açık depoda Issue'ları **okumak hesap gerektirmez**. Kullanıcı aynı konuyu bulursa yeni bildirim açılmaz: dosya hazırlanır ve **mevcut Issue'ya ek kanıt** olarak gönderilir (8. adım; dosyaya Issue adresi yazılır).
5. **Kanıtı topla (tahmin yazma).** Proje kökünde koş, çıktıları sen oku:
   - **aXet sürümü** — dört sinyal birlikte yazılır, çünkü `%guncelle` seçmelidir ve tek sinyal yanıltabilir:
     - `rg -m1 "^> Sürüm:" "<AXET_HOME>/README.md"` — README'deki sürüm satırı (README kalemi güncellemede seçilmediyse eski kalabilir)
     - `git -C "<AXET_HOME>" log -1 --grep="^guncelle: v" --format="%h %cs %s"` — son `%guncelle` kapanışının uyguladığı yayın (boşsa klon hiç `%guncelle` görmemiştir)
     - `git -C "<AXET_HOME>" describe --tags --abbrev=0 --match "v*"` — klonun tamamen içerdiği son yayın etiketi (hata verirse "ölçülemedi" yaz)
     - `git -C "<AXET_HOME>" log -1 --format="%h %cs"` — klonun şu anki commit'i
   - **Güncellik** — 3. adımın sonucu: geride commit sayısı, yayın kataloğu araması, `%guncelle` sonrası yeniden denendi mi.
   - **Yeniden üretim** — başkasının kopyalayıp çalıştırabileceği **en kısa** adım dizisi (aXet'te yazılan `%…` komutu, çalıştırılan komut, açılan dosya). 3-5 adımı geçiyorsa daralt.
   - **Kanıt** — hatayı üreten komutun ya da aracın **çıktısının kendisi** (anlatım değil) + ilgili `dosya:satır` (aXet dosyası ise `<AXET_HOME>/…` ile). Kırptıysan nerede kırptığını yaz. Beklentiyi neye dayandırdığını da yaz: skill adı, kural, README ya da belge cümlesi.
   - **Kontrol grubu** — aynı mekanizmanın **çalıştığı bilinen** bir vaka (başka proje, başka obje, bir önceki sürüm). Yoksa "bulunamadı, çünkü …" yaz. Aynı girdiyle yapılan başarısız denemeleri çoğaltmak kanıt değildir.
   - **Kapsam beyanı** — neye BAKMADIN: hangi proje/obje tipi/profil denenmedi, hangi adım ölçülemedi. "Ölçülemedi" ≠ "sorun yok".
6. **SIZINTI TEMİZLİĞİ — zorunlu, atlanmaz.** Bildirim public bir yere gidebilir ve public'e giden metin geri alınamaz. Metni yazmadan önce şunları yer tutucuyla değiştir:

   | Ne | Yer tutucu |
   |---|---|
   | Müşteri / şirket / proje adı | `<MUSTERI>` · `<PROJE>` |
   | SAP sistem kimliği (SID), host, URL, IP, port, istemci no | `<SYS>` · `<HOST>` · `<CLIENT>` |
   | SAP kullanıcı adı, Windows kullanıcı adı (yollarda `C:\Users\<ad>` dahil), kişi adları | `<SAP_USER>` · `<KULLANICI>` · `<KISI>` |
   | E-posta adresi | `<EPOSTA>` |
   | Gerçek belge numarası (sipariş, teslimat, fatura, malzeme, transport no) | `<BELGE_NO>` · `<TR>` |
   | Müşteriye ait Z/Y paket ve obje adları | `ZSD001` gibi jenerik ad |
   | Müşteri kaynak kodu | çıkar; gerekiyorsa sorunu gösteren en kısa **jenerik** örnek |
   | Proje klasörü mutlak yolu | `<PROJE-KOKU>`; aXet klonu için `<AXET_HOME>` |

   Şifre, token, `.conn*` / `*.env` içeriği ve ekran görüntüsü bildirime **hiç** girmez (yer tutucuyla bile).
7. **Onay al ve dosyayı yaz.** Son metnin tamamını kullanıcıya göster ve sor: "Bu metinde müşteri, sistem ya da kişi kimliği kalmadı mı, bu hâliyle kaydedeyim mi?" Açık "evet" olmadan dosya yazma; cevapsız onay = HAYIR: taslağı yalnız sohbette bırak ve durumu söyle. Onay gelirse `.axet-code/bildirimler/<YYYY-AA-GG>-<kisa-konu>.md` yaz (bugünün gerçek tarihi; `kisa-konu` küçük harf, tireli, kimlik taşımaz). Aynı konuda bugünkü dosya varsa onu güncelle. Sonra:
   - **Mekanik son tarama:** `rg -n "@|(?i:users)[\\/]|(?i:https?)://|\b[0-9]{6,}\b|\b[ZY][A-Z0-9_/]{3,}|\b[zy][a-z0-9]*_[a-z0-9_]+" ".axet-code/bildirimler/<dosya>.md"` (obje adı dalları büyük/küçük harfe duyarlıdır; küçük harfli obje adı ancak alt çizgi içeriyorsa yakalanır, böylece "yazdım" gibi Türkçe kelimeler eşleşmez). Her eşleşmeyi tek tek değerlendir (jenerik `ZSD001` ve 4. adımdaki github Issue adresi meşrudur); kimlik taşıyanı temizle, değişen metni yeniden göster. ⚠ Tarama yalnız bu desenlere bakar: müşteri adı, kişi adı ve kod içeriğini **yakalamaz** — 6. adımın yerine geçmez.
   - **Git dışında mı?** `git check-ignore -v ".axet-code/bildirimler/<dosya>.md"`. Proje şablonunun `.axet-code/.gitignore`'ı bu klasörü dışarıda bırakır; komut bir kural basmazsa (dosya izlenebilir durumda) kullanıcıya söyle — `.gitignore`'u sen değiştirme.
8. **Gönderme yolunu seç — önce sor: "GitHub hesabın var mı?"** Cevap yoksa ya da belirsizse hesapsız yolu öner; kullanıcıdan hesap açmasını isteme.
   - **Hesabı varsa (ve origin `github.com` ise):** form `https://github.com/<sahip>/<depo>/issues/new/choose` → **"aXet hata / öneri bildirimi"**. Dosyadaki bölümleri aynı adlı alanlara yapıştır, beyan kutularını işaretle. Mevcut bir Issue varsa (4. adım) yeni form açılmaz: dosya o Issue'ya yorum olarak yapıştırılır.
   - **Hesabı yoksa:** dosyayı aXet'i ona kuran kişiye ya da ekibinin aXet sorumlusuna şirket içi kanalıyla (e-posta, sohbet, iş takip aracı) iletir. Kimi bilmiyorsa ekip liderine sorar. Bildirim hesapsız da eksiksizdir; Issue'yu aracı açar (10. adım).
   - **Hesapsız Issue denenirse ne olur (kullanıcıya böyle anlat):** GitHub Issue formu giriş ister; oturum açılmamışsa form yerine **GitHub giriş sayfası** gelir ve hiçbir şey gönderilmez. Bu bir hata değildir: dosya projede durur, hesapsız yolla gönderilir. Aynı şekilde origin `github.com` değilse (şirket içi ayna) form yoktur → hesapsız yol.
   - **"Gönderildi" ne zaman denir:** hesap yolunda yalnız Issue ya da yorum **adresi** görüldüğünde; hesapsız yolda aracı Issue adresini geri bildirdiğinde. Öncesinde durum "iletildi, Issue bekleniyor"dur.
9. **Takip bölümünü doldur ve kullanıcıya söyle.** Dosyanın sonundaki `## Takip` bölümüne gönderim tarihini, yolu (Issue adresi ya da "aracıya iletildi: <tarih>") ve durumu yaz; Issue adresi sonradan gelirse kullanıcı onu buraya ekletir. Kullanıcıya: dosyanın yolu, seçilen gönderim yolu, dosyanın gönderilene kadar yalnız bu makinede durduğu, ve aşağıdaki "Gönderdikten sonra" özetini söyle.
10. **Aracı olarak gönderiyorsan (hesabı olmayan bir ekip üyesinin dosyası).** Dosyayı olduğu gibi kopyalama:
    1. 6-7. adımın temizliğini ve mekanik taramayı **yeniden** koş — dosya senin kurumunun dışına, public bir depoya gidecek; ilk temizliğe güvenme.
    2. Bildirene ait kimlik (ad, e-posta, ekip) Issue'ya yazılmaz; gerekirse "ekip içinden bildirildi" yeter.
    3. 3-4. adımları kendi klonunda tekrarla (geride mi, aynı Issue var mı); mümkünse yeniden üretimi kendin koş ve sonucunu "Kontrol grubu"na ekle.
    4. Formu doldur (ya da mevcut Issue'ya yorum yaz), Issue adresini bildirene ilet; o da kendi dosyasının Takip bölümüne yazar.

### Bildirim dosyası biçimi

Başlıklar Issue formunun alanlarıyla aynıdır; alanı boş bırakma — bilmediğini "ölçülemedi: <neden>" diye yaz.

```markdown
# aXet bildirimi — <tek cümle özet>

## Tür
<Hata | Öneri | Belge eksik ya da yanlış>

## Özet
<hangi mekanizma (skill, kural, komut), hangi koşulda, ne yanlış yapıyor; birden çok iddia varsa İ1, İ2 …>

## aXet sürümü
- README sürüm satırı: <…>
- Son %guncelle: <kısa hash, tarih, "guncelle: vX kalemler …" ya da "yok">
- İçerilen son yayın etiketi: <vX | ölçülemedi: <neden>>
- Klon commit: <kısa hash, tarih>
- doctor: <N> PASS · <N> WARN · <N> FAIL  (+ ilgili satırlar, temizlenmiş)
- aXet uygulama sürümü: <biliyorsan>
- İşletim sistemi: <ör. Windows 11>

## Güncellik
- Güncel sürümden geride: <N commit | ölçülemedi: <neden>>
- Yayın kataloğunda konu: <bulunmadı | bulundu: <kalem> → %guncelle sonrası yeniden denendi: <sonuç>>
- Aynı konuda Issue: <aranmadı | bulunmadı (arama: <kelime>) | var: <adres> → bu bildirim ek kanıttır>

## Ne yapıyordun
<amaç, tek paragraf>

## Yeniden üretim
1. <kopyalanıp çalıştırılabilir en kısa adım dizisi>

## Beklenen / Olan
- Beklenen: <neye dayanarak — skill adı, kural, belge cümlesi, dosya:satır>
- Olan: <…>

## Kanıt
<komutun/aracın çıktısı — kırpıldıysa nerede; ilgili dosya:satır>

## Kontrol grubu
<çalıştığı bilinen vaka | "bulunamadı, çünkü …">

## Kapsam beyanı
<neye bakılmadı, ne ölçülemedi; "yok" iddiasında aramanın kendisi>

## Öneri (isteğe bağlı)
<düzeltme fikri; denenip çalışmayan yollar ve nedeni>

## Takip
- Gönderim: <tarih> · <Issue adresi | yorum adresi | aracıya iletildi>
- Durum: <iletildi, Issue bekleniyor | açık | …>
```

## Gönderdikten sonra (kullanıcının beklentisi)
- Bakımcı önce kimlik taraması yapar: kimlik taşıyan Issue **düzenlenmez, kapatılır** ve temiz hâli yeniden istenir (public metin geri alınamaz).
- Sonra her iddiayı güncel aXet'te **kendisi yeniden ölçer**; bildirimdeki çıktı kanıt sayılmaz. Doğrulanan iddia için etki analizi yapılır, değişiklik aXet sahibinin onayıyla yapılır. Bu yüzden cevap gecikebilir ve önerilen çözüm aynen uygulanmayabilir.
- Issue yedi bölümlü bir **kapanış yorumuyla** kapanır: sonuç · yapılan · yapılmayan ve nedeni · senin yapacağın adımlar · dikkat · doğrulama · yeniden açma koşulu. Kapanışı görünce: ① "senin yapacağın adımlar"ı sırayla uygula — `%guncelle` proje dosyalarını ve yerel ayarlarını DEĞİŞTİRMEZ, orada yazan yerel adımları sen yaparsın ② "yapılmayan" ve "dikkat" bölümünde çıkarılan şeyi yerelde yeniden ekleme ③ "doğrulama" bölümündeki komutla kendi makinende ölç — "yayında" ≠ "bende düzeldi" ④ sonucu bildirim dosyanın `## Takip` bölümüne yaz; tutmuyorsa "yeniden açma koşulu"na göre aynı Issue'ya yorum yaz (hesabın yoksa aracı kişiye ilet).
- Üretilemeyen bildirim de aynı yorumla kapanır; 1. bölümde "üretilemedi + hangi ortamda denendi" yazar. Bu bir ret değil kapsam beyanıdır, daha dar bir yeniden üretimle yeniden açılabilir. Aynı bulguyu yeni Issue olarak açma: ek kanıt mevcut Issue'ya yorum olarak gider.
- Beklerken aXet klonunu (`<AXET_HOME>`) elle düzeltme: `%guncelle` o dosyayı yerel değişiklik olarak ayırır ya da çakışır ve sonraki güncellemeleri zorlaştırır. İşin durmasın diye gereken geçici yol projeye `%remember` ile not edilir.

## Rules
- **Sessiz gönderim yok.** Issue açmazsın (`gh issue create`, `gh issue comment` ya da tarayıcı otomasyonu yok), e-posta/mesaj göndermezsin, dosyayı bir yere yüklemezsin. Son metni kullanıcı görür, onaylar ve kendisi gönderir.
- Hesap şartı dayatılmaz: kullanıcıdan GitHub hesabı açmasını isteme; hesapsız yol eksiksiz bir yoldur.
- Sızıntı temizliği ve kullanıcı onayı her bildirimde tekrarlanır; "önceki bildirim temizdi" gerekçe değildir.
- Ölçmediğin şeyi yazma: sürüm, doctor ya da güncellik komutu çalışmadıysa alana "ölçülemedi: <neden>" yaz, değer uydurma.
- Kimlik bilgisi (şifre, token) sohbete de yazılmaz; kullanıcı yapıştırırsa bildirime alma ve uyar.
