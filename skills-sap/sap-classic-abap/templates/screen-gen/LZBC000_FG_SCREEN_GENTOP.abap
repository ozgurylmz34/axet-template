*&---------------------------------------------------------------------*
*& ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
*& değiştir (naming.md §3).
*& Ekran üreteci kiti — fonksiyon grubu ZBC000_FG_SCREEN_GEN'in TOP include'u.
*& Fonksiyon grubu yaratılınca SAP bu include'u kendisi üretir; kaynak ekipte
*& FUNCTION-POOL satırı dışında içerik yoktu → genelde dokunmak gerekmez,
*& üretilenle karşılaştır (DEPLOY.md Adım 4).
*&---------------------------------------------------------------------*
FUNCTION-POOL zbc000_fg_screen_gen.         "MESSAGE-ID ..

* INCLUDE LZBC000_FG_SCREEN_GEND...          " Local class definition
