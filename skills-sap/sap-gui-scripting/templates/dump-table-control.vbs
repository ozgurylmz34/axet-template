' AXET-GUI-SCRIPT v1
' AMAC: Acik klasik Dynpro ekranindaki table control'un (GuiTableControl) satirlarini CSV dosyasina yazar.
' MOD: okuma
' GERI-ALINAMAZ: yok
' CIKTI: arguman 1 - UTF-8 CSV, ";" ayrac; 1. veri satiri kolon basliklari; bilgi satirlari "#" ile baslar
' KULLANIM: C:\Windows\SysWOW64\cscript.exe //Nologo //T:600 dump-table-control.vbs "<cikti.csv>" [tablo_id|-] [kaydir 0|1] [en_fazla_satir]
'           tablo_id verilmezse ("-") aktif pencerede ilk table control aranir.
'           kaydir=0 (varsayilan): yalniz gorunen satirlar yazilir, ekranda hicbir sey degismez.
'           kaydir=1: dikey kaydirma yapilir (sunucu turu; ekranin PAI mantigi calisabilir) - DOGRULANMADI:
'           GetCell satir indeksinin gorunen alana gore oldugu varsayimi canli olculmedi.
' ONKOSUL: SAP GUI'de sisteme gelistirici kendisi giris yapmis, tablo ekrani acik; scripting acik.
' GUVENLIK: yeni baglanti acmaz, giris yapmaz, hucreye yazmaz, dugmeye basmaz. Cikti dosyasi varsa uzerine yazmaz.
Option Explicit

Dim gStream, gOutPath, gSes, gTable, gTableId, gScroll, gMaxRows

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

Function Q(v)
  Q = """" & Replace(T1(v), """", """""") & """"
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
' ---------- ortak blok sonu ----------

Function IsTable(o)
  Dim rc, vr, n
  On Error Resume Next
  rc = -1
  vr = -1
  n = -1
  rc = o.RowCount
  vr = o.VisibleRowCount
  n = o.Columns.Count
  IsTable = (Err.Number = 0 And rc >= 0 And vr >= 0 And n > 0)
  Err.Clear
End Function

Function FindTable(obj, depth)
  Dim i, n, child, found
  On Error Resume Next
  Set FindTable = Nothing
  If depth > 30 Then Exit Function
  If IsTable(obj) Then
    Set FindTable = obj
    Exit Function
  End If
  n = 0
  n = obj.Children.Count
  Err.Clear
  For i = 0 To n - 1
    Set child = Nothing
    Set child = obj.Children.ElementAt(i)
    If Err.Number = 0 And Not (child Is Nothing) Then
      Set found = FindTable(child, depth + 1)
      If Not (found Is Nothing) Then
        Set FindTable = found
        Exit Function
      End If
    End If
    Err.Clear
  Next
End Function

Function GetTable(ses, tid)
  Dim t
  On Error Resume Next
  Set t = Nothing
  If tid <> "-" Then
    Set t = ses.FindById(tid)
    If Err.Number <> 0 Then Fail "Verilen ID ile eleman bulunamadi: " & tid
  Else
    Set t = FindTable(ses.ActiveWindow, 0)
  End If
  If t Is Nothing Then Fail "Ekranda table control bulunamadi: tablo ID'sini ikinci arguman olarak verin"
  If Not IsTable(t) Then Fail "Eleman table control gibi gorunmuyor (RowCount/VisibleRowCount/Columns okunamadi)"
  Set GetTable = t
End Function

Sub DumpTable(t, scroll, maxRows)
  Dim tid, nCols, c, i, line, v, cell, total, vis, pos, written, title
  On Error Resume Next
  tid = t.Id
  nCols = t.Columns.Count
  total = t.RowCount
  vis = t.VisibleRowCount
  If Err.Number <> 0 Then Fail "Tablo boyutlari okunamadi"
  If vis < 1 Then Fail "Tabloda gorunen satir yok"
  OutLine "# TABLO_ID" & vbTab & T1(tid)
  OutLine "# SATIR_TOPLAM" & vbTab & total
  OutLine "# GORUNEN_SATIR" & vbTab & vis
  line = ""
  For c = 0 To nCols - 1
    title = ""
    title = t.Columns.ElementAt(c).Title
    If Err.Number <> 0 Then
      title = ""
      Err.Clear
    End If
    If c > 0 Then line = line & ";"
    line = line & Q(title)
  Next
  OutLine line
  written = 0
  pos = 0
  Do
    For i = 0 To vis - 1
      If written >= maxRows Or (pos + i) >= total Then Exit For
      line = ""
      For c = 0 To nCols - 1
        Set cell = t.GetCell(i, c)
        If Err.Number <> 0 Then Fail "Hucre okunamadi: gorunen satir " & i & ", kolon " & c
        v = ""
        v = cell.Text
        If Err.Number <> 0 Then
          v = ""
          Err.Clear
        End If
        If c > 0 Then line = line & ";"
        line = line & Q(v)
      Next
      OutLine line
      written = written + 1
    Next
    If scroll = 0 Then Exit Do
    If written >= maxRows Or (pos + vis) >= total Then Exit Do
    pos = pos + vis
    t.VerticalScrollbar.Position = pos
    If Err.Number <> 0 Then Fail "Kaydirma basarisiz: konum " & pos
    Set t = gSes.FindById(tid)
    If Err.Number <> 0 Then Fail "Kaydirmadan sonra tablo yeniden bulunamadi: " & tid
  Loop
  OutLine "# SATIR_YAZILAN" & vbTab & written
  If scroll = 0 And vis < total Then OutLine "# UYARI" & vbTab & "yalniz gorunen satirlar yazildi; tumu icin kaydir=1 (DOGRULANMADI)"
  If written >= maxRows And total > maxRows Then OutLine "# UYARI" & vbTab & "satir siniri nedeniyle kirpildi: " & maxRows & " / " & total
End Sub

Init 1, "cscript //Nologo dump-table-control.vbs ""<cikti.csv>"" [tablo_id|-] [kaydir 0|1] [en_fazla_satir]"
gTableId = "-"
If WScript.Arguments.Count >= 2 Then gTableId = WScript.Arguments(1)
gScroll = 0
If WScript.Arguments.Count >= 3 Then
  If WScript.Arguments(2) <> "0" And WScript.Arguments(2) <> "1" Then Fail "kaydir 0 ya da 1 olmali"
  gScroll = CLng(WScript.Arguments(2))
End If
gMaxRows = 2000
If WScript.Arguments.Count >= 4 Then
  If Not IsNumeric(WScript.Arguments(3)) Then Fail "en_fazla_satir sayi olmali"
  gMaxRows = CLng(WScript.Arguments(3))
End If
Set gSes = AttachSession()
WriteHeader gSes, "dump-table-control"
Set gTable = GetTable(gSes, gTableId)
DumpTable gTable, gScroll, gMaxRows
OutLine "# BITTI"
Finish 0
