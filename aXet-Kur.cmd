@echo off
rem aXet kurulumu: bu dosyaya cift tikla.
rem Kurulum aracini (kur.ps1) aXet'in yayin deposundan indirir ve calistirir.
rem Ek secenekler aynen gecer, ornek: aXet-Kur.cmd -DenemeModu
setlocal
set "KUR=%TEMP%\axet-kur.ps1"
set "URL=https://raw.githubusercontent.com/ozgurylmz34/axet-template/main/kur.ps1"

echo.
echo  aXet kurulumu basliyor...
echo  Kurulum araci indiriliyor.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing '%URL%' -OutFile '%KUR%'"
if errorlevel 1 goto indirilemedi

powershell -NoProfile -ExecutionPolicy Bypass -File "%KUR%" %*
set "RC=%errorlevel%"
echo.
echo %* | findstr /i "DenemeModu" >nul && goto deneme
if "%RC%"=="0" goto tamam
if "%RC%"=="3" goto yeniden
if "%RC%"=="2" goto onkosul
echo  Kurulum TAMAMLANMADI - cikis kodu %RC%.
echo  Yukaridaki mesajlari okuyun. Gerekirse ekran goruntusunu destek ekibine gonderin.
goto son

:deneme
echo  DENEME MODU: hicbir sey kurulmadi. Gercek kurulum icin dosyaya secenek vermeden cift tiklayin.
goto son

:tamam
echo  Kurulum TAMAM - aXet'i acin.
echo  Ilk cevabin ilk satiri [AXET-CORE- ile baslamali. Guncelleme icin aXet'te %%guncelle yazin.
goto son

:yeniden
echo  Bu pencereyi kapatin ve bu dosyaya TEKRAR cift tiklayin.
echo  (Yeni kurulan bir program bu pencerede henuz gorunmuyor.)
goto son

rem Cikis 2 dort durumda gelir: eksik program (portal listesi), Git kurulu ama calismiyor, -Winget yolu,
rem -Kaldir sirasinda Python yok. Ne yapilacagini kur.ps1 hemen yukarida kendisi yazar; burasi tarafsiz kalir.
:onkosul
echo  Kurulum DURDU: on kosul sorunu var. Ne yapmaniz gerektigi hemen yukaridaki mesajda yazar.
echo  Program eksik dediyse onu kurun (sirket bilgisayarinda: Software Center / Company Portal),
echo  sonra bu pencereyi kapatin ve bu dosyaya TEKRAR cift tiklayin.
echo  Baska bir sorun yazdiysa oradaki adimi izleyin; anlasilmazsa ekran goruntusunu destek ekibine gonderin.
goto son

:indirilemedi
set "RC=1"
echo  HATA: kurulum araci indirilemedi.
echo  Internet baglantisini ya da sirket proxy/VPN ayarini kontrol edin, sonra tekrar deneyin.
echo  Adres: %URL%

:son
echo.
pause
exit /b %RC%
