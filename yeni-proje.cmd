@echo off
rem yeni-proje.cmd - sorarak aXet SAP projesi kurar. Tek kod yolu: scripts\yeni_proje.py (%%yeni-proje skill'i de bunu cagirir).
rem Kullanim: yeni-proje.cmd            (sorular terminalde tek tek sorulur)
rem           yeni-proje.cmd --help     (bayrakli kullanim)
setlocal
rem Z98: `python` calismiyorsa (PATH'te yok ya da Windows magaza kisayolu) `py -3` denenir. PY = secilen
rem yorumlayicinin TAM yolu (sys.executable): sonraki cagrilar dogrudan python.exe'ye gider (.cmd kisayolu `call`suz
rem cagrilinca geri donmez). Z80 nit: eski Python 'bulunamadi' degil 'surum yetersiz' der ve erken durur (esik tek
rem satirda, :python_sec icinde: install.PY_ASGARI, parite testi).
set "PY="
set "PY_ESKI="
call :python_sec python
if not defined PY call :python_sec py -3
if defined PY goto python_hazir
if defined PY_ESKI goto python_eski
goto python_yok
:python_hazir
"%PY%" "%~dp0scripts\yeni_proje.py" %*
exit /b %errorlevel%

:python_eski
echo HATA: python bulundu ama surumu yetersiz - Python 3.12+ gerekli. Kurulu surum:
call %PY_ESKI% --version
echo Guncelleme: sirketinin yazilim merkezinden (Software Center / Company Portal) kur ya da BT'den iste;
echo resmi indirme: https://www.python.org/downloads/windows/  - sonra YENI bir terminal ac ve tekrar calistir.
exit /b 9009

:python_yok
echo HATA: python bulunamadi ya da calismiyor - PATH'te Python 3.12+ gerekli.
echo Kurulum: sirketinin yazilim merkezinden (Software Center / Company Portal) kur ya da BT'den iste;
echo resmi indirme: https://www.python.org/downloads/windows/  - sonra YENI bir terminal ac ve tekrar calistir.
echo Not: Windows'un "python" magaza kisayolu gercek Python degildir.
exit /b 9009

:python_sec
rem %* = aday komut (python ya da py -3). Calismazsa hicbir sey ayarlanmaz; calisir ama surumu yetersizse PY_ESKI,
rem yeterliyse PY = yorumlayicinin tam yolu.
set "ADAY="
for /f "usebackq delims=" %%P in (`%* -c "import sys;print(sys.executable if sys.version_info>=(3,12) else 'ESKI')" 2^>nul`) do set "ADAY=%%P"
if not defined ADAY exit /b 0
if "%ADAY%"=="ESKI" goto python_sec_eski
if exist "%ADAY%" set "PY=%ADAY%"
exit /b 0
:python_sec_eski
if not defined PY_ESKI set "PY_ESKI=%*"
exit /b 0
