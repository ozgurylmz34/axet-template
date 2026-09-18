// ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle değiştir (naming.md §3).
// Ekran üreteci kiti — IT_BUTTONS satır tipi (tablo tipi ZBC000_TT_SCREEN_BUTTON'ın satırı).
// Alanlar kaynak ekibin canlı yapısıyla birebir; alan tipleri standart data element (yasak A: yalnız kullanılır).
// ⚠ Bu // satırları bilgi amaçlıdır: adt_push_source'a göndermeden önce SİL
//   (DDIC yapı DDL'inde yorum satırının kabulü bu kitte DOĞRULANMADI). Etiket metnini kullanıcı onaylar.
@EndUserText.label : 'Ekran üreteci: app-toolbar buton tanımı'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
define structure zbc000_s_screen_button {

  fcode     : gui_func;
  text      : gui_text;
  icon      : icon_d;
  quickinfo : gui_info;
  fkey      : cua_pfno;

}
