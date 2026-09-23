@echo off
rem aXet template kurulumu: kur.ps1'i bu klasorden calistirir (parametreler aynen gecer: -Hedef -Kaynak -Kaldir
rem -Sifirla -DenemeModu -Winget). -Sifirla: klonu template ile birebir ayni hale getirir, once yedek/<tarih-saat> dali acar.
rem -Winget: eksik Git/Python'u winget ile kurmayi SORAR (yalniz kisisel makine); verilmezse winget hic kullanilmaz.
rem -ExecutionPolicy Bypass: internetten indirilmis (Zone.Identifier) betik RemoteSigned politikasinda aksi halde engellenir.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kur.ps1" %*
exit /b %ERRORLEVEL%
