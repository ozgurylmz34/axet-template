*&---------------------------------------------------------------------*
*& ZBC000 nötr ortak paket gövdesidir; kendi ortak paketinin gövdesiyle
*& değiştir (naming.md §3).
*& Ekran üreteci kiti — fonksiyon grubu ZBC000_FG_SCREEN_GEN'in ANA programı
*& (SAPLZBC000_FG_SCREEN_GEN). SAP bunu grup yaratılırken KENDİSİ üretir:
*& bu dosya yalnız karşılaştırma içindir, push edilmez (DEPLOY.md Adım 4).
*& Grup adı uzunsa SAP include adlarını kısaltabilir → gerçek adları üretilen
*& programdan OKU, türetme (references/fugr-fm.md §4.1).
*&---------------------------------------------------------------------*
*******************************************************************
*   System-defined Include-files.                                 *
*******************************************************************
  INCLUDE LZBC000_FG_SCREEN_GENTOP.          " Global Declarations
  INCLUDE LZBC000_FG_SCREEN_GENUXX.          " Function Modules

*******************************************************************
*   User-defined Include-files (if necessary).                    *
*******************************************************************
* INCLUDE LZBC000_FG_SCREEN_GENF...          " Subroutines
* INCLUDE LZBC000_FG_SCREEN_GENO...          " PBO-Modules
* INCLUDE LZBC000_FG_SCREEN_GENI...          " PAI-Modules
* INCLUDE LZBC000_FG_SCREEN_GENE...          " Events
* INCLUDE LZBC000_FG_SCREEN_GENP...          " Local class implement.
* INCLUDE LZBC000_FG_SCREEN_GENT99.          " ABAP Unit tests
