' AXET-GUI-SCRIPT v1
' AMAC: Acik SAP GUI ekranindaki elemanlari (id, tip, metin) ve durum cubugunu dosyaya yazar.
' MOD: okuma
' GERI-ALINAMAZ: yok
' CIKTI: arguman 1 - UTF-8 metin; satir basina id<TAB>tip<TAB>metin; bilgi satirlari "#" ile baslar
' KULLANIM: C:\Windows\SysWOW64\cscript.exe //Nologo //T:300 read-screen.vbs "<cikti_dosyasi>" [en_fazla_eleman]
' ONKOSUL: SAP GUI'de sisteme gelistirici kendisi giris yapmis ve okunacak ekran acik; scripting acik.
' GUVENLIK: yeni baglanti acmaz, giris yapmaz, alana yazmaz, dugmeye basmaz, sifre alani metnini yazmaz,
'           kullanici/client/sistem bilgisi yazmaz. Cikti dosyasi varsa uzerine yazmaz.
Option Explicit

Dim gStream, gOutPath, gMax, gCount, gStop, gSes

' ---------- ortak blok (tum sablonlarda ayni) ----------
Sub Init(minArgs, usage)
  Dim fso
  If WScript.Arguments.Count < minArgs Then
    WScript.Echo "KULLANIM: " & usage
    WScript.Quit 2
  End If
  gOutPath = WScript.Arguments(0)
  Set fso = CreateObject("Scripting.FileSystemObject")
  If fso.FileExists(gOutPath) Then
    WScript.Echo "HATA: cikti dosyasi zaten var, uzerine yazilmaz: " & gOutPath
    WScript.Quit 1
  End If
  Set gStream = CreateObject("ADODB.Stream")
  gStream.Type = 2
  gStream.Charset = "utf-8"
  gStream.Open
End Sub

Sub OutLine(s)
  gStream.WriteText s & vbCrLf
End Sub

Sub Finish(code)
  On Error Resume Next
  gStream.SaveToFile gOutPath, 1
  If Err.Number <> 0 Then WScript.Echo "HATA: cikti dosyasi yazilamadi: " & gOutPath & " (" & Err.Description & ")"
  WScript.Quit code
End Sub

Sub Fail(msg)
  Dim d
  d = ""
  If Err.Number <> 0 Then d = " [Err " & Err.Number & ": " & Err.Description & "]"
  OutLine "# HATA" & vbTab & msg & d
  WScript.Echo "HATA: " & msg & d
  Finish 1
End Sub

Function T1(v)
  Dim s
  If IsNull(v) Or IsEmpty(v) Then
    s = ""
  Else
    s = CStr(v)
  End If
  s = Replace(s, vbCr, " ")
  s = Replace(s, vbLf, " ")
  T1 = Replace(s, vbTab, " ")
End Function

Function AttachSession()
  Dim rot, app, ses
  On Error Resume Next
  Set rot = GetObject("SAPGUI")
  If Err.Number <> 0 Then Fail "SAP GUI nesnesi alinamadi: SAP Logon acik ve sisteme giris yapilmis mi?"
  Set app = rot.GetScriptingEngine
  If Err.Number <> 0 Then Fail "Scripting motoru alinamadi: scripting kapali olabilir (sunucu parametresi sapgui/user_scripting, Basis) ya da yetki yok"
  If app.Children.Count < 1 Then Fail "Acik baglanti yok: SAP GUI'de sisteme once kendiniz giris yapin"
  Set ses = Nothing
  Set ses = app.ActiveSession
  If Err.Number <> 0 Or (ses Is Nothing) Then
    Err.Clear
    Set ses = Nothing
    If app.Children.Count = 1 Then
      If app.Children.ElementAt(0).Children.Count = 1 Then Set ses = app.Children.ElementAt(0).Children.ElementAt(0)
    End If
  End If
  If Err.Number <> 0 Then Fail "Oturum alinamadi"
  If ses Is Nothing Then Fail "Hangi oturumun okunacagi belirsiz: okunacak SAP GUI penceresine tiklayip yeniden calistirin"
  If ses.Busy Then Fail "Oturum mesgul: ekran yanit verdikten sonra yeniden calistirin"
  Set AttachSession = ses
End Function

Sub WriteHeader(ses, kind)
  On Error Resume Next
  OutLine "# BASLANGIC" & vbTab & kind & vbTab & Now
  OutLine "# ISLEM" & vbTab & T1(ses.Info.Transaction)
  OutLine "# PROGRAM" & vbTab & T1(ses.Info.Program)
  OutLine "# EKRAN" & vbTab & T1(ses.Info.ScreenNumber)
  OutLine "# PENCERE" & vbTab & T1(ses.ActiveWindow.Text)
  OutLine "# SUNUCU_SCRIPTING_SALT_OKUR" & vbTab & T1(ses.Info.ScriptingModeReadOnly)
  If Err.Number <> 0 Then Fail "Oturum bilgisi okunamadi"
End Sub

Sub WriteStatusbar(obj, depth)
  Dim i, n, child, mt
  On Error Resume Next
  If depth > 3 Then Exit Sub
  mt = Empty
  mt = obj.MessageType
  If Err.Number = 0 And Not IsEmpty(mt) Then
    OutLine "# DURUM_CUBUGU" & vbTab & T1(mt) & vbTab & T1(obj.Text)
    Err.Clear
    Exit Sub
  End If
  Err.Clear
  n = 0
  n = obj.Children.Count
  Err.Clear
  For i = 0 To n - 1
    Set child = obj.Children.ElementAt(i)
    If Err.Number = 0 Then WriteStatusbar child, depth + 1
    Err.Clear
  Next
End Sub
' ---------- ortak blok sonu ----------

Sub DumpTree(obj, depth)
  Dim i, n, child, t, id, txt
  On Error Resume Next
  If depth > 30 Or gStop Then Exit Sub
  n = 0
  n = obj.Children.Count
  Err.Clear
  For i = 0 To n - 1
    If gStop Then Exit Sub
    Set child = Nothing
    Set child = obj.Children.ElementAt(i)
    If Err.Number <> 0 Or (child Is Nothing) Then
      OutLine "# UYARI" & vbTab & "eleman okunamadi: " & T1(obj.Id) & " sira " & i
      Err.Clear
    Else
      t = T1(child.Type)
      id = T1(child.Id)
      txt = ""
      txt = T1(child.Text)
      Err.Clear
      If InStr(1, t, "Password", 1) > 0 Or InStr(1, id, "/pwd", 1) > 0 Then txt = "<gizlendi>"
      OutLine id & vbTab & t & vbTab & txt
      gCount = gCount + 1
      If gCount >= gMax Then
        OutLine "# UYARI" & vbTab & "eleman siniri doldu: " & gMax
        gStop = True
        Exit Sub
      End If
      DumpTree child, depth + 1
    End If
  Next
End Sub

Init 1, "cscript //Nologo read-screen.vbs ""<cikti_dosyasi>"" [en_fazla_eleman]"
gMax = 2000
If WScript.Arguments.Count >= 2 Then
  If Not IsNumeric(WScript.Arguments(1)) Then Fail "en_fazla_eleman sayi olmali"
  gMax = CLng(WScript.Arguments(1))
End If
gCount = 0
gStop = False
Set gSes = AttachSession()
WriteHeader gSes, "read-screen"
WriteStatusbar gSes.ActiveWindow, 0
DumpTree gSes.ActiveWindow, 0
OutLine "# ELEMAN_SAYISI" & vbTab & gCount
OutLine "# BITTI"
Finish 0
