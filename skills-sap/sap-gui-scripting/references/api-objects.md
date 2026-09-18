# SAP GUI Scripting API — doğrulanmış adlar

> **Kaynak:** SAP GUI for Windows kurulumundaki tip kütüphaneleri çevrimdışı okundu (2026-09-13, `pythoncom.LoadTypeLib`;
> SAP GUI oturumu açılmadı, SAP'ye bağlanılmadı):
> - `sapfewse.ocx` → kütüphane `SAPFEWSELib`, 161 tip, dosya sürümü 8000.1.5.257
> - `SAPROTWR.DLL` → kütüphane `SapROTWr`, arayüz `ISapROTWrapper`
>
> "Okunur/yazılır" sütunu tip kütüphanesindeki özellik bayrağıdır (salt-okur bayrağı yoksa okunur/yazılır). Adın tip
> kütüphanesinde olması çalışma zamanı davranışını kanıtlamaz: "Canlı" sütunu ayrıca belirtilir.
> Yeniden doğrulama (SAP GUI kurulu makinede):
> ```
> python -c "import pythoncom; tl=pythoncom.LoadTypeLib(r'<SAP GUI klasörü>\sapfewse.ocx'); print(tl.GetDocumentation(-1)[0], tl.GetTypeInfoCount())"
> ```

## 1. Oturuma bağlanma
| Nesne | Üye | Tür | Okunur/yazılır | Şablonda | Canlı |
|---|---|---|---|---|---|
| (VBScript) | `GetObject("SAPGUI")` | çalışan SAP Logon'un ROT girdisi | — | evet | DOĞRULANMADI |
| `ISapROTWrapper` (ProgID `SapROTWr.SapROTWrapper`) | `GetROTEntry(strDisplayName)` | metot | — | hayır (PowerShell yolu) | DOĞRULANMADI |
| `GuiApplication` | `GetScriptingEngine` | metot | — | evet | DOĞRULANMADI |
| `GuiApplication` | `ActiveSession` | özellik | salt-okur | evet | DOĞRULANMADI |
| `GuiApplication` | `Children`, `Connections` | özellik | salt-okur | evet (`Children`) | DOĞRULANMADI |
| `GuiApplication` | `OpenConnection`, `OpenConnectionByConnectionString` | metot | — | **YASAK** (yeni giriş) | — |
| `GuiApplication` | `RegisterROT`, `RevokeROT` | metot | — | hayır | — |
| `GuiConnection` | `Children`, `Sessions` | özellik | salt-okur | evet (`Children`) | DOĞRULANMADI |
| `GuiConnection` | `CloseConnection`, `CloseSession` | metot | — | hayır (etkileşim) | — |

Kayıt bulguları (registry okuması): `SAPGUI` kayıtlı bir ProgID değil (64 ve 32-bit sınıf kayıtlarında yok) →
`GetObject("SAPGUI")` çalışan SAP Logon'un kaydettiği ROT girdisine dayanır (çıkarım; `RegisterROT` üyesi bununla
tutarlı). `SapROTWr.SapROTWrapper` yalnız 32-bit in-process sunucu olarak kayıtlı (`WOW6432Node` altında
`saprotwr.dll`) → PowerShell yolu için 32-bit PowerShell gerekir (çıkarım). Şablonlar bu yüzden
`C:\Windows\SysWOW64\cscript.exe` ile çalıştırılır; 64-bit `cscript` ile `GetObject("SAPGUI")` davranışı DOĞRULANMADI.

## 2. Oturum ve pencere
| Nesne | Üye | Tür | Okunur/yazılır | Şablonda | Canlı |
|---|---|---|---|---|---|
| `GuiSession` | `ActiveWindow`, `Info`, `Children` | özellik | salt-okur | evet | DOĞRULANMADI |
| `GuiSession` | `Busy` | özellik | okunur/yazılır (şablon yalnız okur) | evet | DOĞRULANMADI |
| `GuiSession` | `FindById(Id, Raise)` | metot | — | evet (`Raise` verilmez) | DOĞRULANMADI |
| `GuiSession` | `StartTransaction(Transaction)`, `SendCommand(Command)`, `SendCommandAsync`, `SendMenu` | metot | — | hayır (etkileşim; yalnız `akis`) | — |
| `GuiSession` | `CreateSession` | metot | — | hayır (yeni pencere) | — |
| `GuiSession` | `Record`, `RecordFile` | özellik | — | hayır (kayıt ayarı) | — |
| `GuiSessionInfo` | `Transaction`, `Program`, `ScreenNumber` | özellik | salt-okur | evet | DOĞRULANMADI |
| `GuiSessionInfo` | `ScriptingModeReadOnly`, `ScriptingModeRecordingDisabled` | özellik | salt-okur | evet (ilki) | DOĞRULANMADI |
| `GuiSessionInfo` | `User`, `Client`, `SystemName`, `SystemNumber`, `SystemSessionId`, `ApplicationServer`, `MessageServer`, `Group` | özellik | salt-okur | **yazılmaz** (kimlik/sistem bilgisi) | — |
| `GuiFrameWindow` / `GuiModalWindow` | `Text` | özellik | okunur/yazılır (şablon yalnız okur) | evet | DOĞRULANMADI |
| `GuiFrameWindow` / `GuiModalWindow` | `FindById(Id, Raise)`, `Children` | metot / özellik | salt-okur | hayır | — |
| `GuiFrameWindow` / `GuiModalWindow` | `SendVKey(VKey)` | metot | — | hayır (etkileşim; tuş numaralarının anlamı DOĞRULANMADI) | — |
| `GuiModalWindow` | `PopupDialogText`, `IsPopupDialog` | özellik | — | hayır | — |

## 3. Ekran elemanları
| Nesne | Üye | Tür | Okunur/yazılır | Şablonda | Canlı |
|---|---|---|---|---|---|
| `GuiComponent` (tümü) | `Id`, `Type`, `Name`, `ContainerType`, `Parent` | özellik | salt-okur | evet (`Id`, `Type`) | DOĞRULANMADI |
| `GuiVComponent` | `Text` | özellik | okunur/yazılır (şablon yalnız okur) | evet | DOĞRULANMADI |
| `GuiVComponent` | `Changeable`, `Tooltip` | özellik | salt-okur | hayır | — |
| `GuiComponentCollection` | `Count` | özellik | salt-okur | evet | DOĞRULANMADI |
| `GuiComponentCollection` | `Item(Index)` (varsayılan üye, DISPID 0), `ElementAt(Index)` | metot | — | evet (`ElementAt`) | DOĞRULANMADI |
| `GuiCollection` | `Count`, `Item(Index)`, `ElementAt(Index)` | özellik / metot | salt-okur | evet (ALV kolon listesi) | DOĞRULANMADI |
| `GuiStatusbar` | `Text` | özellik | okunur/yazılır (şablon yalnız okur) | evet | DOĞRULANMADI |
| `GuiStatusbar` | `MessageType`, `MessageId`, `MessageNumber` | özellik | salt-okur | evet (`MessageType`) | değer kümesi DOĞRULANMADI |
| `GuiShell` | `SubType` | özellik | salt-okur | hayır | — |
| `GuiButton` | `Press` | metot | — | hayır (etkileşim) | — |
| `GuiRadioButton` | `Select`, `Selected` | metot / özellik (okunur/yazılır) | — | hayır (etkileşim) | — |
| `GuiCheckBox` | `Selected` | özellik | okunur/yazılır | hayır (etkileşim) | — |
| `GuiComboBox` | `Key`, `Value` | özellik | okunur/yazılır | hayır (etkileşim) | — |
| `GuiTab`, `GuiMenu` | `Select` | metot | — | hayır (etkileşim) | — |
| `GuiPasswordField` | (metin okuma) | — | — | **yazılmaz**: şablon metni gizler | — |

`Type` özelliği metin döndürür. Tip kütüphanesindeki `GuiComponentType` sayımının adları (`GuiTextField`,
`GuiCTextField`, `GuiPasswordField`, `GuiLabel`, `GuiShell`, `GuiTableControl`, `GuiStatusbar` …) okundu; çalışma
zamanında `Type` metninin bu adlarla aynı olduğu DOĞRULANMADI. Şablonlar bu yüzden grid ve tabloyu `Type` metniyle
değil, özellik okuma denemesiyle tanır; şifre alanı için hem `Type` hem ID içinde `pwd` aranır.

## 4. ALV grid (`GuiGridView`)
| Üye | Tür | Okunur/yazılır | Şablonda | Canlı |
|---|---|---|---|---|
| `RowCount`, `ColumnCount`, `VisibleRowCount` | özellik | salt-okur | evet | DOĞRULANMADI |
| `ColumnOrder` | özellik (kolon adları koleksiyonu) | okunur/yazılır (şablon yalnız okur) | evet | koleksiyon erişim biçimi DOĞRULANMADI |
| `FirstVisibleRow` | özellik | okunur/yazılır | evet: kaydırma için yazılır | satırların kaydırınca yüklendiği DOĞRULANMADI |
| `GetCellValue(Row, Column)` | metot | — | evet (`Column` = teknik kolon adı) | DOĞRULANMADI |
| `GetDisplayedColumnTitle(Column)`, `GetColumnTitles(Column)` | metot | — | evet (ilki) | DOĞRULANMADI |
| `ModifyCell`, `ModifyCheckBox`, `InsertRows`, `DeleteRows`, `DuplicateRows`, `MoveRows` | metot | — | **hayır** (veri değiştirir) | — |
| `PressToolbarButton`, `PressButton`, `PressEnter`, `Click`, `DoubleClick`, `SelectAll`, `SetCurrentCell`, `SelectContextMenuItem` | metot | — | hayır (etkileşim) | — |

## 5. Table control (`GuiTableControl`) ve kaydırma çubuğu
| Nesne | Üye | Tür | Okunur/yazılır | Şablonda | Canlı |
|---|---|---|---|---|---|
| `GuiTableControl` | `RowCount`, `VisibleRowCount`, `Columns`, `Rows`, `VerticalScrollbar` | özellik | salt-okur | evet | DOĞRULANMADI |
| `GuiTableControl` | `GetCell(Row, Column)` | metot | — | evet | `Row`'un görünen alana göre mi mutlak mı olduğu DOĞRULANMADI |
| `GuiTableColumn` | `Title` | özellik | salt-okur | evet | DOĞRULANMADI |
| `GuiScrollbar` | `Position` | özellik | okunur/yazılır | yalnız `kaydir=1` ile yazılır | DOĞRULANMADI |
| `GuiScrollbar` | `Minimum`, `Maximum`, `PageSize` | özellik | salt-okur | hayır | — |

Kaydırma ekranda sunucu turu yaratır; ekranın PAI mantığı çalışabilir (çıkarım). Kaydırmadan sonra tablo nesnesinin
yeniden bulunması gerekip gerekmediği DOĞRULANMADI; şablon ID ile yeniden bulur.

## 6. Hata tipleri (`GuiErrorType`)
Tip kütüphanesinde okunan, hata mesajında işe yarayanlar: `Gui_Err_Scripting_Disabled_Srv` (sunucuda scripting kapalı),
`Gui_Err_FindById`, `Gui_Err_Disconnected`, `Gui_Err_AccessDenied`, `Gui_Err_Permission_Denied`. VBScript'te
`Err.Number` ile bu adların sayısal karşılığının eşleşmesi DOĞRULANMADI; şablonlar `Err.Description`'ı olduğu gibi yazar.

## 7. Canlı doğrulanmamış genel varsayımlar
- Element ID yol biçimi (`wnd[0]/usr/...` gibi): yerel kaynaklarda örnek bulunamadı (aranan: `wnd[0]`; kapsam: bu
  template'in kaynağı olan metodoloji deposu ve şirket dokümanları). Şablonlar ID'yi uydurmaz; ID gerekiyorsa
  geliştiricinin kayıt dosyasından alınır.
- `ActiveSession`'ın, script konsoldan çalışırken en son odaklanan SAP GUI penceresini döndürmesi.
- `ColumnOrder` koleksiyonunun `Item(i)` ya da `ElementAt(i)` ile okunması (şablon ikisini de dener).
