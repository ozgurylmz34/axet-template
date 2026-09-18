sap.ui.define([
	"sap/ui/core/mvc/Controller",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator",
	"sap/m/MessageToast"
], function (Controller, Filter, FilterOperator, MessageToast) {
	"use strict";

	return Controller.extend("zxx001.order.controller.OrderList", {
		// Not: caseSensitive: false YASAK; oModel.createEntry("_Item") da yanlış — bu yorumlar bulgu üretmemeli.
		_txt: function (sKey, aArgs) {
			return this.getOwnerComponent().getModel("i18n").getResourceBundle().getText(sKey, aArgs);
		},

		onSearch: function (sQuery) {
			var oBinding = this.byId("orderTable").getBinding("rows");
			oBinding.filter([new Filter("Customer", FilterOperator.Contains, sQuery)]);
		},

		onLoadCountries: function () {
			this.getView().getModel("vh").read("/CountryVHSet", {
				success: function () {}
			});
		},

		onRelease: function (sId) {
			var oModel = this.getView().getModel();
			oModel.callFunction("/ReleaseOrder", {
				method: "POST",
				urlParameters: { OrderId: sId },
				success: function () {
					MessageToast.show(this._txt("msg.saved", [sId]));
				}.bind(this)
			});
		},

		onLoadItems: function (sId) {
			var oModel = this.getView().getModel();
			oModel.read("/OrderSet('" + sId + "')/to_Item", {});
			oModel.read("/OrderSet", { urlParameters: { "$select": "OrderId,Customer" } });
		},

		onNumericLiveChange: function (oEvent) {
			var oInput = oEvent.getSource();
			oInput.setValue(String(oEvent.getParameter("value") || "").replace(/[^0-9.,]/g, ""));
		},

		getSaveText: function () {
			return this._txt("btn.save");
		}
	});
});
