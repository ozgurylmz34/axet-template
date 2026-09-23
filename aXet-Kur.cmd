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
echo  Kurulum TAMAMLANMADI - cikis kodu %RC%.
echo  Yukaridaki mesajlari okuyun. Gerekirse ekran goruntusunu destek ekibine gonderin.
goto son

:deneme
echo  DENEME MODU: hicbir sey kurulmadi. Gercek kurulum icin dosyaya secenek vermeden cift tiklayin.
goto son

:tamam
echo  Kurulum TAMAM.
echo  Simdi aXet'i acin ve bir sey yazin: ilk cevabin ilk satiri [AXET-CORE- ile baslamali.
goto son

:yeniden
echo  Bu pencereyi kapatin ve bu dosyaya TEKRAR cift tiklayin.
echo  (Yeni kurulan bir program bu pencerede henuz gorunmuyor.)
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
