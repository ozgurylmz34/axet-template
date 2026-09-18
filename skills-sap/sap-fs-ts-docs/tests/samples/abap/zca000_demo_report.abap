REPORT zca000_demo_report.
*----------------------------------------------------------------------*
* Demo rapor — test örneği. FROM yorum_tablosu satırı yok sayılmalı.
*----------------------------------------------------------------------*
TABLES: vbak.

PARAMETERS p_bukrs TYPE bukrs.
SELECT-OPTIONS s_erdat FOR vbak-erdat.

START-OF-SELECTION.
  PERFORM get_data.
  CALL SCREEN 100.

FORM get_data.
  SELECT vbeln, erdat FROM vbak INTO TABLE @DATA(lt_head) WHERE erdat IN @s_erdat.
  SELECT * FROM zca000_t_demo INTO TABLE @DATA(lt_demo).
  CALL FUNCTION 'BAPI_SALESORDER_GETLIST'
    EXPORTING
      customer_number = '0000000001'.
  CALL FUNCTION 'Z_CA000_DEMO_FM'.
ENDFORM.
