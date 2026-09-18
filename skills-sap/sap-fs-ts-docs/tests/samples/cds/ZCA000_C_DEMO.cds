@EndUserText.label: 'Demo onay projeksiyonu'
@AccessControl.authorizationCheck: #NOT_REQUIRED
@ObjectModel.usageType: { serviceQuality: #X, sizeCategory: #S, dataClass: #MIXED }
define root view entity ZCA000_C_DEMO
  provider contract transactional_query
  as projection on ZCA000_I_DEMO
{
      @UI.lineItem: [{ position: 10, label: 'Talep No' }]
      @UI.selectionField: [{ position: 10 }]
      @Consumption.filter: { mandatory: true }
  key RequestId,
      @UI.selectionField: [{ position: 20 }]
      @Consumption.valueHelpDefinition: [{ entity: { name: 'ZCA000_I_STATUS_VH', element: 'Status' } }]
      Status,
      // etiket interface CDS'ten gelir
      Amount,
      Currency as CurrencyCode,
      RefNo,
      Note,
      /* association */
      _Items : redirected to composition child ZCA000_C_DEMO_ITEM
}
