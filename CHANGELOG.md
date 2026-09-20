# Değişiklik günlüğü

<!-- ÜRETİLEN DOSYA — elle düzenlemeyin. Kaynak: `guncelle/yayinlar.json` · üretici: `yayin_hazirla.py` (yayın anında). -->

Her başlık bir yayın etiketidir (`git tag`). Kalem numaraları yayın commit'inin `Guncelleme-Kalemi:` trailer'larıyla ve `%guncelle` planıyla AYNIDIR: bir kalemi seçmek, aşağıda o kalemin altında listelenen DOSYALARI almak demektir. Yayın başına tek commit atıldığı için (Q2) kalem seçimi yalnız bu eşlemeyle, dosya düzeyinde yapılabilir; aynı dosyaya dokunan kalemler birlikte alınır.

★ = kritik kalem (`%guncelle` planında varsayılan olarak SEÇİLİ gelir).

## v0.3.0 — 2026-09-20

### ★ 0.3.0-01 · %guncelle kapanış commit'i: aracın kendi dosyaları dışında bir şey varsa ATILMAZ (düzeltme)

- **neden:** Kapanış commit'i index'in TAMAMINI alıyordu; güncelleme sırasında index'te duran alakasız değişikliklerin 'guncelle: ... kalemler ...' commit'ine sessizce girmesi mümkündü. Artık index kapsamı ölçülür; aracın plan yolları dışında dosya varsa commit atılmaz. Kapsam ÖLÇÜLEMEZSE de durur (ölçülemedi != temiz).
- **dosyalar:** `scripts/guncelle.py`, `tests/test_guncelle.py`
- **test:** `python tests/run_tests.py -k guncelle`
- **gerektirir:** —

### ★ 0.3.0-02 · Bütünlük mührü: önceki turdan kalan butunluk.json artık bu turun ölçümü sanılmıyor (düzeltme)

- **neden:** butunluk.json ve durum.json plan mührü taşımıyordu; bir önceki güncelleme turundan kalan bayat bütünlük sonucu GÜNCEL ölçüm gibi okunabiliyordu (sahte güvence). Artık her ikisi plan mührüyle damgalanır ve mühür tutmazsa kapanış 'BU TUR İÇİN ÖLÇÜLMEDİ' der.
- **dosyalar:** `scripts/guncelle.py`, `tests/test_guncelle.py`
- **test:** `python tests/run_tests.py -k guncelle`
- **gerektirir:** —

### 0.3.0-03 · Satır sonu normalizasyonu tek kaynaktan: CRLF ve tek başına CR (düzeltme)

- **neden:** Normalizasyon iki yerde ayrı yazılıydı ve tek başına CR (eski Mac satır sonu) işlenmiyordu; sessizce ayrışabilirdi. Artık new_project.satir_sonu_normalize tek kaynaktır, guncelle_proje ona delege eder. Bugün izlenen 791 dosyanın 0'ında tek-başına CR var - yeni gate AÇILMADI.
- **dosyalar:** `scripts/new_project.py`, `scripts/guncelle_proje.py`, `tests/test_guncelle_proje.py`
- **test:** `python tests/run_tests.py -k guncelle_proje`
- **gerektirir:** —

### ★ 0.3.0-04 · Oturum özeti izin kuralı joker içermeyen TAM komutla üretiliyor (güvenlik)

- **neden:** Kurulumun ürettiği bash allow kuralı joker içerseydi, aynı önekle başlayan başka komutlar da izinli olurdu (zincir yükseltme). Kural artık klonun mutlak yolundan türetilen tek ve TAM komuttur; joker yasağı testle zorlanır. Kurulumdan sonra aXet'i kapatıp açmak gerekir.
- **dosyalar:** `scripts/install.py`, `tests/test_install.py`
- **test:** `python tests/run_tests.py -k install`
- **gerektirir:** —

### ★ 0.3.0-05 · Reviewer SKIP'i artık NEDENİNİ söylüyor (boş parantez yerine rc + stderr) (düzeltme)

- **neden:** Reviewer rc'si 0/1 dışındaysa ve JSON ayrıştırılamıyorsa verdict SKIP'e düşüyor, passed True dönüyor ve pre-flight KOŞMADAN SAP yazımı sürüyordu; kullanıcıya giden not ise 'PRE-FLIGHT KOŞMADI ()' diye BOŞ çıkıyordu. Artık rc ve stderr kuyruğu yazılır. VERDICT SEMANTİĞİ DEĞİŞMEDİ - fail-closed'a çevirmek ayrı bir karardır, önce rc uzayı bu teşhisle ölçülecek.
- **dosyalar:** `skills-sap/sap-adt-foundation/scripts/sapadt/_reviewer.py`, `skills-sap/sap-adt-foundation/tests/test_reviewer_skip_teshisi.py`
- **test:** `python skills-sap/sap-adt-foundation/tests/run_tests.py -k reviewer`
- **gerektirir:** —

### 0.3.0-06 · 'validator bulunamadı' teşhisine Windows MAX_PATH ipucu (düzeltme)

- **neden:** Windows'ta LongPathsEnabled=0 iken 259 karakteri aşan yola Python dosya yazamaz ama git YAZAR; uzun yollu bir klonda validator diskte durur, git status temizdir, buna karşılık Path.exists() False döner. Eski mesaj yalnız 'bulunamadı' dediği için kullanıcı gate'i silinmiş sanıp kurulumu onarmaya çalışıyordu. Hüküm değişmedi (eksik BLOCKER gate hala BLOCKER + rc 1), yalnız teşhis eklendi.
- **dosyalar:** `skills-sap/sap-adt-foundation/scripts/sapadt/lib/validators/run_review.py`, `skills-sap/sap-adt-foundation/tests/test_uzun_yol_teshisi.py`
- **test:** `python skills-sap/sap-adt-foundation/tests/run_tests.py -k uzun_yol`
- **gerektirir:** —

## v0.2.0 — 2026-09-18

### 0.2.0-01 · Kurulum betiği: adsız argüman reddi, -Kaldir kendi klonu, bayat kayıt mesajı (düzeltme)

- **neden:** K-A: adı verilmemiş argüman sessizce -Hedef oluyordu, artık DURDU. K-B: klondaki kur.cmd -Kaldir hedef verilmezse kendi klonunu kaldırır. K-C: yalnız bayat kayıt varken 'Config zaten bu klonu gösteriyor' denmez.
- **dosyalar:** `kur.ps1`, `tests/test_kur.py`
- **test:** `python tests/run_tests.py -k kur`
- **gerektirir:** —

### 0.2.0-02 · Yeni proje ve %guncelle-proje: aXet'in kendi .gitignore'u 'proje vardı' sayılmaz, ikili dosya bayt bayt (düzeltme)

- **neden:** K-E: yalnız aXet'in yazdığı .gitignore varken şablon sürüm kaydı yazılmıyordu. Z9: ikili şablon dosyası metin olarak okunup bozuluyordu. Geçerli UTF-8 olarak çözülebilen ikili dosya (NUL içerir) da artık metin sayılmaz; ölçüt %guncelle-proje ile aynı (uzantı + NUL). %guncelle-proje ikili dosyayı güncellerken satır sonlarını çeviriyordu (PNG başlığındaki \r\n bile siliniyordu) ve doğrulama bunu yakalamıyordu; artık bayt bayt yazılır.
- **dosyalar:** `scripts/new_project.py`, `scripts/guncelle_proje.py`, `tests/test_guncelle_proje.py`
- **test:** `python tests/run_tests.py -k guncelle_proje`, `python tests/run_tests.py -k new_project`
- **gerektirir:** —

### 0.2.0-03 · %guncelle: 'yerel' kararlı izlenmeyen dosya commit'e girmez, git add hatasında index geri alınır, okunamayan yerel dosya ezilmez (düzeltme)

- **neden:** M-6: --karar yerel = dosyaya dokunma; izlenmeyen kullanıcı dosyası aXet commit'iyle depoya giriyordu. M-1: git tarafı patlarsa rapor 'onaylı kapandı' demez. git add hatasında yarım stage kullanıcının sonraki commit'ine sızmaz. Dosya hash'lenemezse (git hash-object hatası) 'dosya yok' sayılıp yedeksiz ezilmez; plan ÖLÇÜLEMEDİ deyip durur. Aynı koruma yeniden adlandırılan V7'de (kullanıcının dosyası yeni yolda), 'ertelendi' kararında ve karar verilmemiş dosyada da geçerli: motorun yazmadığı izlenmeyen yol kapanış commit'ine girmez.
- **dosyalar:** `scripts/guncelle.py`, `tests/test_guncelle.py`
- **test:** `python tests/run_tests.py -k guncelle`
- **gerektirir:** —

### 0.2.0-04 · Oturum özeti: yayını zaten içeren klonda sahte 'kalem bekliyor' satırı (düzeltme)

- **neden:** K-F: taze klon v0.1.0'ı içerdiği hâlde oturum özeti kalıcı olarak '1 güncelleme kalemi bekliyor' diyordu. Ata testi artık motorla tek kaynaktan (guncelle.yayin_durumu).
- **dosyalar:** `scripts/session_brief.py`, `scripts/guncelle.py`, `tests/test_yayin_surumleri.py`
- **test:** `python tests/run_tests.py -k yayin_surumleri`, `python tests/run_tests.py -k guncelle`
- **gerektirir:** `0.2.0-03`

### 0.2.0-05 · SAP: $TMP paketinde kabuk/domain/veri elemanı yaratma transport istemez (kural)

- **neden:** K-M: yerel ($TMP) objede SAP transport numarasını yok sayıyor; araç ortak ekip transportunu istemeye itiyordu. Yalnız tam '$TMP' eşleşmesi; adt_struct_create ve düzenleme araçları transport istemeye devam eder.
- **dosyalar:** `skills-sap/sap-adt-foundation/scripts/sapadt/gate.py`, `skills-sap/sap-adt-foundation/scripts/sapadt/guardrails.py`, `skills-sap/sap-adt-foundation/scripts/sapadt/tools/atom.py`, `skills-sap/sap-adt-foundation/scripts/sapadt/tools/composite.py`, `skills-sap/sap-adt-foundation/scripts/sapadt/tools/shells.py`, `skills-sap/sap-adt-foundation/tests/test_inprocess_guards.py`, `skills-sap/sap-adt-foundation/tests/test_cli_gate.py`
- **test:** `python skills-sap/sap-adt-foundation/tests/run_tests.py`
- **gerektirir:** —

### 0.2.0-06 · Kapılar: FAIL anında 'kuralı değiştirme' hatırlatması + pre-commit .rules.md değişikliği uyarısı (kural)

- **neden:** K-O: pre-commit adlandırma FAIL'i alan model .rules.md regex'ini genişletip geçti. Üç FAIL çıkışı hatırlatma basar; pre-commit staged .rules.md Naming/istisna değişikliğini eski→yeni WARN olarak gösterir (engellemez). Stage'lenmemiş .rules.md değişikliği (adlandırma denetimi kuralı diskten okur) ve yeniden adlandırılan .rules.md de uyarı alır.
- **dosyalar:** `scripts/check_package_naming.py`, `scripts/project_precommit.py`, `skills-sap/sap-adt-foundation/scripts/sap_adt_cli.py`, `skills-sap/sap-adt-foundation/tests/test_cli_gate.py`, `skills-sap/sap-classic-abap/scripts/scaffold_classic_program.py`, `tests/test_precommit.py`, `tests/test_kural_hatirlatma.py`
- **test:** `python tests/run_tests.py -k precommit`, `python tests/run_tests.py -k kural_hatirlatma`
- **gerektirir:** —

### 0.2.0-07 · Çekirdek ve skill talimatları (CORE 0.4.0, SAP 0.3.0) (kural)

- **neden:** Davranış testi bulguları: açılış adımı her mesajda, SKIP'i PASS sayma, istenenden fazlasını yapma, kabuk ortamı, yasak A örneği (CDS extend dahil), SALV API doğrulaması, kuralı değiştirerek geçme, gün sonu/verify-done beyanları, bash 'Allow for Session' uyarısı. SAP kesin yasak bölümü değiştiği için SAP projelerinde %guncelle-proje damgayı yeniler.
- **dosyalar:** `core/00-temel.md`, `core/sap/00-sap.md`, `skills-sap/sap-classic-abap/references/alv-report.md`, `skills/gun-sonu/SKILL.md`, `skills/verify-done/SKILL.md`, `README.md`
- **test:** `python tests/run_tests.py -k sap_stamp`, `python tests/run_tests.py -k doctor`
- **gerektirir:** —

### 0.2.0-08 · doctor: template bulgu satırı docstring'i gerçek davranışı söyler (düzeltme)

- **neden:** Z10: docstring satırda kaç yolun listelendiğini yanlış anlatıyordu.
- **dosyalar:** `scripts/doctor.py`
- **test:** `python tests/run_tests.py -k doctor`
- **gerektirir:** —

### 0.2.0-09 · Yayın aracı testleri: noreply kimlik ve kopyalama hatası (düzeltme)

- **neden:** Bakımcı yayın aracının yeni denetimlerinin (noreply olmayan commit kimliğiyle yayın DURUR, uzun yolda anlamlı hata) testleri.
- **dosyalar:** `tests/test_yayin_hazirla.py`, `tests/test_yayin_surumleri.py`
- **test:** `python tests/run_tests.py -k yayin`
- **gerektirir:** —

### 0.2.0-10 · Rapor doğruluğu: git hatası 'temiz / PASS / değişiklik yok' diye okunmaz (düzeltme)

- **neden:** Başarısız git çağrıları sessizce olumlu sonuca dönüşüyordu: doctor bozuk git'e '[PASS] git: ?' diyordu, oturum özeti bozuk index'te 'çalışma ağacı temiz' diyordu ve ilk değişen dosyanın adını 1 karakter eksik gösteriyordu, %guncelle hazırlığında geri dönüş etiketi kullanıcının değişikliğini içermeyebiliyordu, merge-file hatası '255 çakışma' sayılıyordu, %guncelle-proje paket şablonu ve ekip reposu denetimlerinde hata 'değişiklik yok / ekip yok' diye okunuyordu. Artık ÇALIŞMIYOR / ÖLÇÜLEMEDİ yazılır ya da akış durur. Git deposu olmayan projede ekip reposu satırı 'ÖLÇÜLEMEDİ' gürültüsü basmaz; bütünlük raporunun asgari güvence satırı hash hatasında ÖLÇÜLEMEDİ yazar.
- **dosyalar:** `scripts/install.py`, `scripts/session_brief.py`, `scripts/guncelle.py`, `scripts/guncelle_proje.py`, `tests/test_install.py`, `tests/test_session_brief.py`, `tests/test_guncelle.py`, `tests/test_guncelle_proje.py`
- **test:** `python tests/run_tests.py -k install`, `python tests/run_tests.py -k session_brief`, `python tests/run_tests.py -k guncelle`
- **gerektirir:** `0.2.0-03`

### 0.2.0-11 · Test takımı: mutasyon denetiminde sağ kalan kurallar teste bağlandı (düzeltme)

- **neden:** Bağımsız mutasyon denetimi 11 kuralın bozulsa bile testleri yeşil bıraktığını ölçtü (doctor SAP profil FAIL'i, bozuk manifest, V6d, %guncelle-proje kapanış/damga/savunma dalları). Ürün davranışı değişmedi; yalnız regresyon koruması eklendi. Vakum tarayıcısının kalibrasyon testleri: büyük harfli vurgu sözcükleri vaat sayılmaz, üründe geçen kısa etiket vaat sayılır.
- **dosyalar:** `tests/test_doctor.py`, `tests/test_behavior_manifest.py`, `tests/test_guncelle.py`, `tests/test_guncelle_proje.py`, `tests/test_vakum_tara.py`
- **test:** `python tests/run_tests.py -k doctor`, `python tests/run_tests.py -k behavior_manifest`, `python tests/run_tests.py -k guncelle`, `python tests/run_tests.py -k vakum_tara`
- **gerektirir:** —

## v0.1.0 — 2026-09-18

### 0.1.0-01 · İlk public yayın (yetenek)

- **neden:** aXet template'in ilk public sürümü. Bu etiket sonraki yayınların güncelleme tabanıdır; taze klon bu yayını zaten içerir, %guncelle planına girmez.
- **dosyalar:** `README.md`
- **test:** —
- **gerektirir:** —
