# Teslim, çalıştırma ve sonuç okuma

## 0. Neden geliştirici çalıştırır
- Kullanıcı kararı: model GUI script'ini yazar, geliştirici kontrol edip kendisi çalıştırır.
- aXet'te hook yoktur ve `axet-code run` / `-y` modunda izin sorulmaz (ölçüldü): modelin başlattığı bir GUI script'ini
  mekanik olarak durduracak katman yok. Tek güvenli sınır, çalıştırma kararının insanda kalmasıdır.
- Ek bağlam (DOĞRULANMADI): şirket içi bir eklenti belgesi, SAP API politikasının (2026) ajanın sürdüğü SAP GUI
  scripting'e yalnız her çalıştırma geliştiricice ayrı ayrı onaylandığında izin verdiğini aktarıyor. Birincil politika
  metni okunmadı.

## 1. Teslim notu şablonu
```text
## SAP GUI script teslimi
Script: <proje>/.tmp/gui/<ad>.vbs
Amaç: <tek cümle>
Mod: okuma | akis
Önce sen yap: SAP GUI'de sisteme kendin giriş yap → <işlem kodu> → <seçim değerleri> → sonuç ekranında bırak.
Script ne yapacak:
  1. Açık SAP GUI oturumuna bağlanır (yeni giriş yapmaz, şifre sormaz ve yazmaz).
  2. Hangi ekranda olduğunu çıktıya yazar (işlem kodu, program, ekran no).
  3. <okunan elemanlar / ALV / tablo>
  4. Çıktıyı <çıktı yolu> dosyasına yazar; son satır "# BITTI".
Ekranda değişiklik: yok | kaydırma (ALV/tablo) | akis: <basılan düğmeler, doldurulan alanlar, başlatılan işlemler — tek tek>
Geri alınamaz adım: YOK | <adım + neden>   (VAR ise ayrıca açık onay iste)
Çalıştır (kendi terminalinde):
  C:\Windows\SysWOW64\cscript.exe //Nologo //T:300 "<script>" "<çıktı yolu>" [<ek argümanlar>]
Beklenen çıktı: <dosya> · ilk satır "# BASLANGIC", son satır "# BITTI" · biçim: <…> · yaklaşık satır: <…>
Denetleyici: check_gui_script.py → çıkış <0/1>, BLOCKER=<n> WARN=<n> INFO=<n>
Denetleyicinin bakmadıkları: <çıktıdaki BAKILMAYANLAR listesi>
DOĞRULANMADI: <şablonun canlı doğrulanmamış varsayımları; references/api-objects.md §7>
Çalıştırdıktan sonra "çalıştı" ya da konsoldaki hata satırını yaz; çıktı dosyasını ben okurum.
```

## 2. Çalıştırma komutu
- `cscript` seçenekleri (`cscript //?` çıktısından): `//Nologo` başlık basmaz, `//T:nn` script'i nn saniye sonra keser
  (askıda kalmayı önler), `//B` hataları gizler → **kullanma**.
- `C:\Windows\SysWOW64\cscript.exe`: SAP GUI'nin scripting bileşenleri bu makinede 32-bit kayıtlı
  (`references/api-objects.md` §1). 64-bit `cscript` ile çalışıp çalışmadığı DOĞRULANMADI.
- Argümanlar: 1. argüman her zaman çıktı dosyası. Çıktı dosyası varsa script durur (üzerine yazmaz).

## 3. Kayıttan akışa dönüşüm (`MOD: akis`)
1. Kayıt dosyasını `view` ile oku. İçinde kullanıcı adı, şifre, sistem ya da client değeri varsa kullanıcıya söyle,
   değeri sohbete alıntılama.
2. Yasak kontrolü: kaydet/sil/release/kilit adımı ya da standart veri değişikliği varsa script YAZILMAZ; DUR, yasak
   ve alternatif yol (BAPI → RFC FM → BDC → manuel) ile kullanıcıya dön.
3. Bağlantı açma ve giriş ekranı satırlarını sil; yerine şablonlardaki `Init` + `AttachSession` + `WriteHeader`
   bloklarını koy.
4. Her `StartTransaction` / `SendCommand` / `SendVKey` / `Press` satırından sonra: `If Err.Number <> 0 Then Fail
   "<adım açıklaması>"` ve durum çubuğu metnini çıktıya yazan satır. Durum çubuğu `MessageType` değerlerinin (hata harfi)
   anlamı DOĞRULANMADI: ilk çalıştırmada bu satırları geliştiriciyle birlikte oku, değer kümesini ölçmeden "hata
   harfinde dur" kuralı yazma.
5. Sabit girilmiş iş değerlerini (belge no, tarih, malzeme) script argümanına çevir.
6. Başlığa `MOD: akis` ve `GERI-ALINAMAZ: <adımlar ya da yok>` yaz.
7. `check_gui_script.py --mode akis` çalıştır. Her `ETKILESIM` uyarısı teslim notunun "Ekranda değişiklik" satırına
   tek tek girer.

## 4. Sonuç okuma kontrol listesi
- [ ] Dosya var mı? Yoksa konsol çıktısını iste (script dosyayı yazamamış olabilir).
- [ ] İlk satır `# BASLANGIC`, son satır `# BITTI` mi? `# HATA` satırı var mı?
- [ ] `# ISLEM`, `# PROGRAM`, `# EKRAN` beklenen ekran mı? Değilse sonuç yanlış ekrandandır; kullanma.
- [ ] `# SATIR_TOPLAM` ile `# SATIR_YAZILAN` aynı mı? `# UYARI` satırlarını raporla (kırpma, kaydırma yok).
- [ ] Veriyi yalnız sorunun gerektirdiği kadar aktar; kişisel veri rapora ve hafızaya yazılmaz.
- [ ] Sonuçtan çıkan iddiayı kanıtın sınırına indir: "ekranda şu görünüyor" ≠ "tabloda şu var".
