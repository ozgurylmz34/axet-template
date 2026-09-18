' AXET-GUI-SCRIPT v1
' AMAC: Acik ekrandaki ALV grid'in (GuiGridView) kolon ve satirlarini CSV dosyasina yazar.
' MOD: okuma
' GERI-ALINAMAZ: yok
' CIKTI: arguman 1 - UTF-8 CSV, ";" ayrac; 1. veri satiri teknik kolon adlari, 2. satir kolon basliklari;
'        bilgi satirlari "#" ile baslar
' KULLANIM: C:\Windows\SysWOW64\cscript.exe //Nologo //T:600 dump-alv-grid.vbs "<cikti.csv>" [grid_id|-] [en_fazla_satir]
'           grid_id verilmezse ("-") aktif pencerede ilk ALV grid aranir.
' ONKOSUL: SAP GUI'de sisteme gelistirici kendisi giris yapmis, ALV sonuc ekrani acik; scripting acik.
' EKRANDA DEGISIKLIK: yalniz kaydirma (FirstVisibleRow) - satirlarin kaydirinca yuklendigi varsayimi DOGRULANMADI.
' GUVENLIK: yeni baglanti acmaz, giris yapmaz, hucre degistirmez, dugmeye basmaz. Cikti dosyasi varsa uzerine yazmaz.
Option Explicit

Dim gStream, gOutPath, gSes, gGrid, gGridId, gMaxRows

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

Function IsGrid(o)
  Dim rc, cc, co
  On Error Resume Next
  rc = -1
  cc = -1
  rc = o.RowCount
  cc = o.ColumnCount
  Set co = o.ColumnOrder
  IsGrid = (Err.Number = 0 And rc >= 0 And cc > 0)
  Err.Clear
End Function

Function FindGrid(obj, depth)
  Dim i, n, child, found
  On Error Resume Next
  Set FindGrid = Nothing
  If depth > 30 Then Exit Function
  If IsGrid(obj) Then
    Set FindGrid = obj
    Exit Function
  End If
  n = 0
  n = obj.Children.Count
  Err.Clear
  For i = 0 To n - 1
    Set child = Nothing
    Set child = obj.Children.ElementAt(i)
    If Err.Number = 0 And Not (child Is Nothing) Then
      Set found = FindGrid(child, depth + 1)
      If Not (found Is Nothing) Then
        Set FindGrid = found
        Exit Function
      End If
    End If
    Err.Clear
  Next
End Function

Function GetGrid(ses, gid)
  Dim g
  On Error Resume Next
  Set g = Nothing
  If gid <> "-" Then
    Set g = ses.FindById(gid)
    If Err.Number <> 0 Then Fail "Verilen ID ile eleman bulunamadi: " & gid
  Else
    Set g = FindGrid(ses.ActiveWindow, 0)
  End If
  If g Is Nothing Then Fail "Ekranda ALV grid bulunamadi: grid ID'sini ikinci arguman olarak verin"
  If Not IsGrid(g) Then Fail "Eleman ALV grid gibi gorunmuyor (RowCount/ColumnCount/ColumnOrder okunamadi)"
  Set GetGrid = g
End Function

Function ColName(cols, i)
  Dim s
  On Error Resume Next
  s = cols.Item(i)
  If Err.Number <> 0 Then
    Err.Clear
    s = cols.ElementAt(i)
  End If
  If Err.Number <> 0 Then Fail "Kolon adi okunamadi: sira " & i
  ColName = s
End Function

Sub DumpGrid(g, maxRows)
  Dim cols, nCols, c, r, total, lastRow, vis, line, names, v, scrollWarned
  On Error Resume Next
  Set cols = g.ColumnOrder
  nCols = cols.Count
  If Err.Number <> 0 Then Fail "Kolon listesi okunamadi"
  If nCols < 1 Then Fail "Grid'de kolon yok"
  ReDim names(nCols - 1)
  For c = 0 To nCols - 1
    names(c) = ColName(cols, c)
  Next
  total = g.RowCount
  vis = g.VisibleRowCount
  If Err.Number <> 0 Then Fail "Satir sayisi okunamadi"
  If vis < 1 Then vis = 1
  OutLine "# GRID_ID" & vbTab & T1(g.Id)
  OutLine "# SATIR_TOPLAM" & vbTab & total
  line = ""
  For c = 0 To nCols - 1
    If c > 0 Then line = line & ";"
    line = line & Q(names(c))
  Next
  OutLine line
  line = ""
  For c = 0 To nCols - 1
    If c > 0 Then line = line & ";"
    v = ""
    v = g.GetDisplayedColumnTitle(names(c))
    If Err.Number <> 0 Then
      v = ""
      Err.Clear
    End If
    line = line & Q(v)
  Next
  OutLine line
  lastRow = total - 1
  If lastRow > maxRows - 1 Then lastRow = maxRows - 1
  scrollWarned = False
  For r = 0 To lastRow
    If (r Mod vis) = 0 Then
      g.FirstVisibleRow = r
      If Err.Number <> 0 And Not scrollWarned Then
        OutLine "# UYARI" & vbTab & "kaydirma yapilamadi; gorunmeyen satirlar bos gelebilir"
        scrollWarned = True
      End If
      Err.Clear
    End If
    line = ""
    For c = 0 To nCols - 1
      If c > 0 Then line = line & ";"
      v = g.GetCellValue(r, names(c))
      If Err.Number <> 0 Then Fail "Hucre okunamadi: satir " & r & ", kolon " & names(c)
      line = line & Q(v)
    Next
    OutLine line
  Next
  OutLine "# SATIR_YAZILAN" & vbTab & (lastRow + 1)
  If total > maxRows Then OutLine "# UYARI" & vbTab & "satir siniri nedeniyle kirpildi: " & maxRows & " / " & total
End Sub

Init 1, "cscript //Nologo dump-alv-grid.vbs ""<cikti.csv>"" [grid_id|-] [en_fazla_satir]"
gGridId = "-"
If WScript.Arguments.Count >= 2 Then gGridId = WScript.Arguments(1)
gMaxRows = 5000
If WScript.Arguments.Count >= 3 Then
  If Not IsNumeric(WScript.Arguments(2)) Then Fail "en_fazla_satir sayi olmali"
  gMaxRows = CLng(WScript.Arguments(2))
End If
Set gSes = AttachSession()
WriteHeader gSes, "dump-alv-grid"
Set gGrid = GetGrid(gSes, gGridId)
DumpGrid gGrid, gMaxRows
OutLine "# BITTI"
Finish 0
