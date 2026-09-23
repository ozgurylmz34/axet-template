@echo off
rem proje-tamamla.cmd - aXet proje kurulumunun KULLANICI adimlari, tek pencerede sirayla:
rem   1) SAP baglanti sablonlari conn\DEV.env + conn\QA.env (kullanici Notepad'de doldurur; pencere parola SORMAZ)
rem   2) davranis yuzeyi onayi (behavior_manifest.py generate - onayi kullanici verir)
rem   3) doctor.py   4) aXet'i projede ac (axet-code -c)
rem Kullanim: proje-tamamla.cmd [PROJE_KLASORU]   (verilmezse bulunulan dizin)
rem Projedeki KURULUMU-TAMAMLA.cmd kisayolu (yeni_proje.py yazar) bunu cagirir. Tekrar calistirmak guvenlidir:
rem var olan dosyayi ezmez, yapilmis adimi atlar.
rem aXet oturumu bu dosyayi CALISTIRMAZ ve pencere ACMAZ: baglanti bilgisi ve onay kullanicinindir.
rem Etiketli goto kullanilir: parantezli blok icinde ')' iceren yol (orn. "Program Files (x86)") blogu bozar.
rem AXET_KURULUM_EDITOR_ACMA tanimliysa Notepad acilmaz (yalniz otomatik testler icin).
setlocal
set "AXET_HOME=%~dp0"
set "FOUND=%AXET_HOME%skills-sap\sap-adt-foundation\scripts"
set "HEDEF=%~1"
if "%HEDEF%"=="" set "HEDEF=%CD%"
for %%I in ("%HEDEF%") do set "PROJE=%%~fI"
if "%PROJE:~-1%"=="\" set "PROJE=%PROJE:~0,-1%"
set "CONN=%PROJE%\conn"

echo ============================================================
echo  aXet kurulum tamamlama - "%PROJE%"
echo ============================================================
echo.

python --version >nul 2>nul
if errorlevel 1 goto python_yok
if not exist "%AXET_HOME%scripts\doctor.py" goto klon_yok
if not exist "%AXET_HOME%scripts\conn_sablon.py" goto klon_yok
if not exist "%PROJE%\" goto klasor_yok
if not exist "%PROJE%\sap-project.json" goto proje_yok
cd /d "%PROJE%"

rem ---------- 1) SAP baglanti sablonlari ----------
echo [1/4] SAP baglanti bilgileri (conn\DEV.env, conn\QA.env)
python "%AXET_HOME%scripts\conn_sablon.py" hazirla --project-dir "%PROJE%"
if errorlevel 1 goto sablon_hata
rem dogrula: 0 hatali yok + en az biri dolu-gecerli / 1 hatali dosya var / 2 dolu-gecerli dosya yok
python "%AXET_HOME%scripts\conn_sablon.py" dogrula --project-dir "%PROJE%"
set "CRC=%errorlevel%"
if "%CRC%"=="0" goto conn_gecerli
if "%CRC%"=="2" goto conn_bos
goto doldur

:conn_bos
if not exist "%PROJE%\.conn_adt" goto doldur
echo   Not: aktif baglanti (.conn_adt) zaten var, conn\ sablonlari bos. Baska sistem (QA) icin doldurabilirsin.
goto ozet

:conn_gecerli
if exist "%PROJE%\.conn_adt" goto ozet
echo   Aktif sistem DEV olarak ayarlaniyor...
python "%FOUND%\switch_tier.py" DEV --project-dir "%PROJE%" >nul
if errorlevel 1 goto dev_yok

:ozet
rem Sistem ozeti: yalniz ad + tier + durum (deger basilmaz)
python "%AXET_HOME%scripts\conn_sablon.py" ozet --project-dir "%PROJE%"
echo   Sistem degistirmek icin aXet'te: %%sistem  (ya da "QA'ya gec" de)

:adim2
echo.
rem ---------- 2) Davranis yuzeyi onayi ----------
echo [2/4] Proje ayarlarinin onayi (davranis yuzeyi)
python "%AXET_HOME%scripts\behavior_manifest.py" check --project-dir "%PROJE%"
if not errorlevel 1 goto onay_var
echo.
if errorlevel 2 goto onay_liste
echo   Onaylanacaklar: yukarida "!" ile isaretli degisiklikler.
goto onay_sor
:onay_liste
echo   Onaylanacak dosyalar:
set "AXET_SCRIPTS=%AXET_HOME%scripts"
set "AXET_PROJE=%PROJE%"
python -c "import os,sys;sys.path.insert(0,os.environ['AXET_SCRIPTS']);import behavior_manifest as b;from pathlib import Path;[print('     '+k) for k in b.topla(Path(os.environ['AXET_PROJE']))]"
:onay_sor
rem Onay YALNIZ gercek konsoldan: `echo E | ...` ile boruyla verilen cevap kabul edilmez (choice boruyu okur - olculdu).
set "AXET_SCRIPTS=%AXET_HOME%scripts"
python -c "import os,sys;sys.path.insert(0,os.environ['AXET_SCRIPTS']);import yeni_proje as y;sys.exit(0 if y.etkilesimli_mi() else 1)"
if errorlevel 1 goto onay_konsol_yok
choice /c EH /n /m "  Bu proje ayarlarini onayliyor musun? [E/H]: "
if errorlevel 2 goto onay_yok
python "%AXET_HOME%scripts\behavior_manifest.py" generate --project-dir "%PROJE%"
if errorlevel 1 goto onay_hata
goto adim3
:onay_var
echo   Ayarlar zaten onayli.

:adim3
echo.
rem ---------- 3) Kontrol ----------
echo [3/4] Proje kontrolu (doctor)
python "%AXET_HOME%scripts\doctor.py"
if errorlevel 1 goto doctor_fail

rem ---------- 4) aXet'i ac ----------
echo.
echo [4/4] Kurulum tamam.
where axet-code >nul 2>nul
if errorlevel 1 goto axet_yok
choice /c EH /n /m "  aXet'i bu projede simdi acayim mi? [E/H]: "
if errorlevel 2 goto bitti
axet-code -c "%PROJE%"
exit /b 0

:bitti
echo   Tamam. aXet'i sonra acmak icin: axet-code -c "%PROJE%"
set "RC=0"
goto son

:doldur
echo.
echo   YAPMAN GEREKEN: Notepad'de acilan dosyalarda ^<...^> yazan yerleri doldur (koseli parantezleri de sil), kaydet.
echo   - DEV.env zorunlu. QA sistemi yoksa QA.env'e dokunma (bos sablon atlanir).
echo   - Dosyalar git'e girmez; parola yalniz bu dosyalarda durur. Icerigini sohbete yapistirma.
echo   Bitince bu dosyaya tekrar cift tikla.
if defined AXET_KURULUM_EDITOR_ACMA goto doldur_son
if exist "%CONN%\DEV.env" start "" notepad "%CONN%\DEV.env"
if exist "%CONN%\QA.env" start "" notepad "%CONN%\QA.env"
:doldur_son
set "RC=3"
goto son

:dev_yok
echo   HATA: DEV sistemine gecilemedi - conn\DEV.env dolu ve gecerli olmali (yazma yalniz DEV'de).
goto doldur

:sablon_hata
echo   HATA: conn\ sablonlari yazilamadi - yukaridaki mesaja bak.
set "RC=3"
goto son

:python_yok
echo HATA: python bulunamadi ya da calismiyor - PATH'te Python 3.12+ gerekli.
echo Kurulum: sirketinin yazilim merkezinden (Software Center / Company Portal) kur ya da BT'den iste;
echo resmi indirme: https://www.python.org/downloads/windows/  - sonra bu dosyaya tekrar cift tikla.
set "RC=9009"
goto son

:klon_yok
echo HATA: aXet klonu eksik gorunuyor: "%AXET_HOME%scripts" altinda doctor.py / conn_sablon.py yok.
echo aXet'i %%guncelle ile guncelle ya da kur.cmd ile yeniden kur.
set "RC=1"
goto son

:klasor_yok
echo HATA: proje klasoru bulunamadi: "%PROJE%"
set "RC=1"
goto son

:proje_yok
echo Bu klasorde henuz aXet projesi yok (sap-project.json bulunamadi): "%PROJE%"
echo Once aXet'i burada acip %%yeni-proje ile kurulumu yap, sonra bu dosyaya tekrar cift tikla.
set "RC=2"
goto son

:onay_yok
echo   Onay verilmedi. Hazir olunca bu dosyaya tekrar cift tikla (onceki adimlar korunur).
set "RC=4"
goto son

:onay_konsol_yok
echo   Onay yalniz bu dosyaya CIFT TIKLAYINCA acilan pencerede verilir (girdi yonlendirilmis - onay sorulmadi).
set "RC=4"
goto son

:onay_hata
echo   Onay kaydedilemedi - yukaridaki mesaja bak.
set "RC=4"
goto son

:doctor_fail
echo.
echo   Kontrolde FAIL var - yukaridaki FAIL satirlarina bak. Ekran goruntusunu paylasabilirsin.
echo   Duzelttikten sonra bu dosyaya tekrar cift tikla.
set "RC=5"
goto son

:axet_yok
echo   axet-code komutu bulunamadi (PATH). Kurulum icin kur.cmd; sonra: axet-code -c "%PROJE%"
set "RC=6"
goto son

:son
echo.
pause
exit /b %RC%
