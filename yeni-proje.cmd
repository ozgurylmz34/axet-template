@echo off
rem yeni-proje.cmd - sorarak aXet SAP projesi kurar. Tek kod yolu: scripts\yeni_proje.py (%%yeni-proje skill'i de bunu cagirir).
rem Kullanim: yeni-proje.cmd            (sorular terminalde tek tek sorulur)
rem           yeni-proje.cmd --help     (bayrakli kullanim)
setlocal
python --version >nul 2>nul
if errorlevel 1 goto python_yok
python "%~dp0scripts\yeni_proje.py" %*
exit /b %errorlevel%

:python_yok
echo HATA: python bulunamadi ya da calismiyor - PATH'te Python 3.12+ gerekli.
echo Kurulum: sirketinin yazilim merkezinden (Software Center / Company Portal) kur ya da BT'den iste;
echo resmi indirme: https://www.python.org/downloads/windows/  - sonra YENI bir terminal ac ve tekrar calistir.
echo Not: Windows'un "python" magaza kisayolu gercek Python degildir.
exit /b 9009
