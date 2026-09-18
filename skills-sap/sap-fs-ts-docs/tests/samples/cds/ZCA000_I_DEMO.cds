@EndUserText.label: 'Demo onay'
define root view entity ZCA000_I_DEMO
  as select from zca000_t_demo
  composition [0..*] of ZCA000_I_DEMO_ITEM as _Items
{
      @EndUserText.label: 'Talep No'
  key request_id as RequestId,
      @EndUserText.label: 'Durum'
      status     as Status,
      @EndUserText.label: 'Tutar'
      amount     as Amount,
      @EndUserText.label: 'Para Birimi'
      currency   as CurrencyCode,
      ref_no     as RefNo,
      note       as Note,
      _Items
}
