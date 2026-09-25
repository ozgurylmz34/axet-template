# EKİP HAFIZASI — indeks
MEMORY-ID: AXET-TEAM-MEMORY

> Her satır bir kayda işaret eder: `- [Başlık](dosya.md) — tek satır özet`. İçerik indekse yazılmaz.
> Kayıt biçimi ve ne zaman yazılacağı: `%remember`. Bu indeks her oturum yüklenir; kısa tutulur.
> Burada yalnız her projede geçerli çalışma dersleri durur. Projeye özel bilgi proje reposunun `.axet-code/memory/` klasörüne yazılır.
> Buraya yapılan değişiklik tüm ekibe git ile gider: commit/PR ile girer.

## Çalışma dersleri (feedback)

- [Kararları önce topla](feedback_kararlari-once-topla.md) — uzun işe/devre başlamadan kullanıcı kararlarının hepsi tek seferde; teknik kararı kendin ver
- [Spec mutabakatı build'den önce](feedback_spec-mutabakat-once-build.md) — yeni program: ekran + fonksiyonel spec iste → sentezle → madde madde onay → sonra kod
- [Deploy kullanıcı testinden sonra](feedback_deploy-kullanici-testi-sonrasi.md) — yerelde sun, kullanıcı OK demeden SAP/ortak sisteme deploy yok
- [Yeni teknolojide önce araştır](feedback_yeni-teknoloji-once-arastir.md) — deneme-yanılma yerine kanıtlı yöntem; ilk SAP yazımından önce kural seti; çıktıyı say
- [Çapraz kesen işte önce envanter](feedback_envanter-once-capraz-is.md) — çok katman/uygulama değişikliğini tek tek yamalama; yüzeyin tamamını tara
- [Bayat sayı ve satır referansı](feedback_bayat-sayi-referans.md) — kalıcı metinde içerik çapası; başarıyı önce/sonra iki sayıyla kanıtla
- [Kopya silmeden önce referans ölç](feedback_kopya-silmeden-referans-olc.md) — aynı hash ≠ aynı kullanım; tüketicileri bağlamadan silme
- [git diff ve satır sonu tuzakları](feedback_git-diff-ve-satir-sonu.md) — `A...B` ≠ `A..B`; CRLF diff'i şişirir → `--ignore-cr-at-eol`
- [PowerShell BOM ve tırnak](feedback_powershell-bom-ve-tirnak.md) — PS 5.1 utf8 BOM ekler; gömülü çift tırnak git'i bozar; aXet write BOM'suz
- [Geçici dosyalar .tmp/'ye](feedback_scratch-dosyalari-tmp.md) — ekran görüntüsü/deneme çıktısı repo köküne değil gitignore'lu `.tmp/`'ye
- [Skill frontmatter YAML tuzağı](feedback_skill-frontmatter-yaml.md) — tırnaksız `: ` → aXet skill'i sessizce düşürür; `>` blok + doctor.py
- [Bağımsız tam doküman](feedback_bagimsiz-tam-dokuman.md) — uygulama/tip dokümanı başka dokümana göre fark raporu değil, kendi başına tam
- [İnceleme bulgusu kontrol listesine](feedback_inceleme-bulgusu-kontrol-listesine.md) — tekrar edebilir tuzak: yöntem referansı + inceleme kontrol listesi maddesi (öner, onayla gir)
- [Kontrol yazarken kör nokta](feedback_kontrol-yazarken-kor-nokta.md) — koştu ≠ baktı; metin/hedef, ikinci yüzey, fail-open testi; dar + uyarı modunda devreye al
- [Devredilen işi etkiyle doğrula](feedback_devredilen-isi-etkiyle-dogrula.md) — önerdiğin adla 0 eşleşme ≠ yapılmadı; önce git status, sonra etki
- [Kural yazımı: konum ve koşul](feedback_kural-yazim-konum-ve-kosul.md) — kural eylemin geçtiği yerde; yanlış kural eksikten kötü; çürütme koşullu; yanlışı kaynağında düzelt
- [Kullanıcı meta-uyarısında dur](feedback_kullanici-meta-uyari-dur.md) — "yine yapıyorsun / okudun mu / bi dur" → dur, %recall, yapısal önlem, onay
- [UI5 plumbing reuse + runtime done](feedback_ui5-plumbing-reuse-runtime-done.md) — save/nav/setData mekaniği kanonik desenden; done = statik + runtime
- [UI5 i18n iki dosya](feedback_ui5-i18n-iki-dosya.md) — TR uygulamada metin/anahtar i18n + i18n_tr ikisinde, sonra Ctrl+F5
- [UI5 runtime sayıyla doğrula](feedback_ui5-runtime-sayiyla-dogrula.md) — click() değil firePress/model API; dolgu farkını runtime'da yan yana oku
- [UI5 lokal popup ↔ hesap kilidi](feedback_ui5-lokal-popup-hesap-kilidi.md) — lrep/varyant 401 teknik; ısrarlı $metadata 401 = kilit, deneme yapma
- [UI5 elle kurulan istek sap-client taşımaz](feedback_ui5-elle-kurulan-istek-sap-client.md) — ikinci model/ham istek ana modelin `aUrlParams`'ını devralır; iki client + ayırıcı veriyle ölç
- [UI5 sayfadan ayrılırken senkron XHR gitmez](feedback_ui5-sayfadan-ayrilirken-senkron-xhr.md) — kilit bırakma `fetch`+`keepalive`+CSRF; bırakınca bayrağı sıfırla (navigasyonda ölçüldü)
- [Kanıtın kapsamı ve zamanı korunur](feedback_kanit-kapsam-ve-zaman-korunur.md) — aktarırken niteleyici/birim düşmez; önce/sonra kıyasında zaman damgası; ölçüm artefaktın kendi join/filtresiyle; üreticinin girdisi
- [Sıfır sonuçtan önce kontrol grubu](feedback_sifir-sonuc-kanitla-once-kontrol-grubu.md) — "0 eşleşme" ≠ "yok": TR karakter varyantı, ASCII kaynak, CRLF'li liste, hiç koşmamış komut; bilinen-pozitifle sına
- [Yeşil sinyalin kapsamını sor](feedback_yesil-sinyal-kapsamini-sor.md) — exit 0/OK/0 bulgu ≠ kanıt, kanıt çıktıdır; ters yönü koş; öneri ve onay da iddiadır
- [Kullanıcının bildiğini ölçme, sor](feedback_kullanicinin-bildigini-olcme-sor.md) — deneme sonucu/iş gerçeği → sor; teknik değer → ölç; beyanı kaynağıyla yaz
- [Performans önerisi de iddiadır](feedback_performans-onerisi-de-iddiadir.md) — önce maliyet dağılımını ölç, sonra kaldıraç öner; çürürse geri çek
- [Uyarlama verisi açık kalem değil](feedback_uyarlama-verisi-acik-kalem-degil.md) — tablo DEĞERİ iş listesine/hafızaya yazılmaz; o anda söyle, kayda geçirme
- [Ölçüm önkoşullu risk notu](feedback_olcum-onkosullu-risk-notu.md) — "ölçülmeli" şerhi yazınca aynı turda iş listesine kalem; düzeltmeden önce şerhi ara
- [Karar sormadan önce erişilebilirlik](feedback_karar-sormadan-once-erisilebilirlik-olc.md) — ulaşılamaz daldaki bulgu karar sorusu değil; ulaşılamazlığı guard adıyla yaz
- [Kendi işini yeniden sınıflandırma](feedback_kendi-isini-yeniden-siniflandirip-kural-disina-cikma.md) — "küçük / build değil / araç" etiketiyle incelemeyi atlama; etiketi olgu koyar; baskıda tur sayısını kes, incelemeyi değil
- [Muafiyet gerekçesinden geniş olmasın](feedback_muafiyet-gerekcesinden-genis-olmasin.md) — gerekçe alt küme için, muafiyet dosyanın tamamı için → kör nokta; satır/token bazlı daralt, pozitif kontrol koy
- [Sızıntı taramasının uzayı git farkıdır](feedback_sizinti-taramasi-arama-uzayi-git-deltasidir.md) — uzay = `origin/main...HEAD` + `git status`, dosya sayısını yaz; kirli çıktının üreticisini de düzelt
- [Yerel takım CI'nin ikizi değil](feedback_yerel-suit-ci-ikizi-degil.md) — aynı commit Windows'ta yeşil, Linux CI'da kırmızı olabilir; kanıt CI; takımı ritüelle değil diff'e göre koş
- [Paylaşılan modülün desenini yeniden türetme](feedback_paylasilan-modulun-desenini-yeniden-turetme.md) — tek seferlik script'te paylaşılan modülü kullan/yorumunu oku; aynı girdide kör iki katman redundans değil
- [Kabuk heredoc Türkçe/kaçış bozulması](feedback_bash-heredoc-turkce-kacis.md) — heredoc/`python -c` Türkçe ve `\` kaçışını bozabilir; `write` ile yaz, dosyayı yeniden okuyarak doğrula (aXet bash'inde ölçülmedi)
- [Asılı CI koşusu: PR kapat/aç](feedback_github-actions-asili-kosu-pr-kapat-ac.md) — queued + 0 job saatlerce → `run_attempt`/`updated_at` ölç, PR'ı kapatıp hemen aç

## Referanslar (reference)

(henüz kayıt yok)
