# conn — SAP sistemleri (DEV / QA)

Her SAP sistemi bu klasörde bir dosyadır: `DEV.env`, `QA.env`. Aktif bağlantı proje kökündeki `.conn_adt`'dir.

1. Proje klasöründeki `KURULUMU-TAMAMLA.cmd`'ye çift tıkla. `DEV.env` ve `QA.env` şablonlarını yazar (var olanı
   ezmez) ve Notepad'de açar.
2. `<...>` yazan her değeri doldur (köşeli parantezleri de sil), kaydet. `ADT_SAP_TIER`, `ADT_SAP_LANGUAGE` ve
   `ADT_SAP_SYSTEM_NAME` satırları hazır gelir; değiştirme. QA sistemi yoksa `QA.env`'e dokunma, boş şablon atlanır.
3. `KURULUMU-TAMAMLA.cmd`'ye tekrar çift tıkla. Dosyaları denetler: hatalı alan varsa alan adıyla söyler (değeri
   basmaz) ve dosyayı yeniden açar. `DEV.env` geçerliyse aktif sistemi DEV yapar.
4. Sistem değiştirmek için aXet'te `%sistem` yaz ya da "QA'ya geç" / "DEV'e dön" de. Seçilen dosya `.conn_adt`
   olur; eskisi `conn/.conn_adt.bak` olarak saklanır.

Bilmen gerekenler:
- Parola dosyada **düz metin** durur. `conn/` içindeki dosyalar git'e girmez (`.gitignore`: `conn/*`); yalnız bu
  README izlenir.
- `<...>` değeri kalmış dosyaya geçilmez.
- QA ve PRD salt-okunurdur; SAP'ye yazma yalnız DEV'de.
- Dosyaların içeriğini sohbete yapıştırma, aXet'e okutma.
- Başka bir sistem (ör. PRD) için aynı biçimde `<AD>.env` ekleyebilirsin. Parolayı dosyaya yazmak istemezsen
  PowerShell'de: `python "$HOME\axet\skills-sap\sap-adt-foundation\scripts\setup_credentials.py" --slot <AD>`
  (bilgileri sorar, parola ekrana yansımaz). aXet'i varsayılan klasör (`%USERPROFILE%\axet`) dışına kurduysan
  `$HOME\axet` yerine o klasörü yaz.
