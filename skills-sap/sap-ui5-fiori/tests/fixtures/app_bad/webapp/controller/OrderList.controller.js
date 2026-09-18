sap.ui.define([
	"sap/ui/core/mvc/Controller",
	"sap/ui/model/Filter",
	"sap/ui/model/FilterOperator"
], function (Controller, Filter, FilterOperator) {
	"use strict";

	return Controller.extend("zxx001.orderbad.controller.OrderList", {
		onSearch: function (sQuery) {
			var oBinding = this.byId("orderTable").getBinding("items");
			oBinding.filter([new Filter({ path: "Customer", operator: FilterOperator.Contains, value1: sQuery, caseSensitive: false })]);
			oBinding.filter([new Filter("CustomerName", FilterOperator.Contains, sQuery)]);
		},

		onAddItem: function () {
			var oModel = this.getView().getModel();
			oModel.createEntry("_Item", { properties: {} });
		},

		onLoad: function () {
			var oModel = this.getView().getModel();
			oModel.read("/OrdersSet", {});
			oModel.callFunction("/ReleaseOrders", {
				method: "POST",
				urlParameters: { OrderID: "1" }
			});
		},

		getSaveText: function () {
			return this._txt("btn.save");
		}
	});
});
