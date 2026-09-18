// ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle değiştir (naming.md §3).
// Ekran üreteci kiti — IT_FIELDS satır tipi (tablo tipi ZBC000_TT_SCREEN_FIELD'ın satırı).
// Alan ADLARI RPY_DYFATC ile birebir aynıdır: FM MOVE-CORRESPONDING ile aktarır → ad değiştirme.
// Alanlar kaynak ekibin canlı yapısıyla birebir; alan tipleri standart data element (yasak A: yalnız kullanılır).
// ⚠ Bu // satırları bilgi amaçlıdır: adt_push_source'a göndermeden önce SİL
//   (DDIC yapı DDL'inde yorum satırının kabulü bu kitte DOĞRULANMADI). Etiket metnini kullanıcı onaylar.
@EndUserText.label : 'Ekran üreteci: dynpro alan tanımı'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
define structure zbc000_s_screen_field {

  cont_type  : scrctype;
  cont_name  : scrcname;
  name       : scrfname;
  type       : scrntype;
  format     : scrftype;
  length     : scrndeflg;
  vislength  : scrnvislg;
  line       : scrnline;
  column     : scrncoln;
  text       : scrfstxg;
  from_dict  : scrfdict;
  input_fld  : scrffein;
  output_fld : scrffout;
  requ_entry : scrffobl;
  poss_entry : scrfcmbprm;
  matchcode  : scrfmtch;
  conv_exit  : scrfucnv;
  ref_field  : scrfwaer;
  group1     : scrfgrp1;

}
