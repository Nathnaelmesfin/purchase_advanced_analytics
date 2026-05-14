/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Purchase Analytics Frontend Service
 * Handles RPC calls to the backend purchase.analytics.service model.
 */
export class PurchaseAnalyticsService {
    constructor(env) {
        this.env = env;
        this.orm = env.services.orm;
        this._bootstrapData = null;
        this._settingsCache = null;
    }

    // ─── PRIVATE ──────────────────────────────────────────────────

    async _call(method, args = [], kwargs = {}) {
        return this.orm.call("purchase.analytics.service", method, args, kwargs);
    }

    // ─── PUBLIC ───────────────────────────────────────────────────

    async getBootstrapData() {
        if (!this._bootstrapData) {
            this._bootstrapData = await this._call("get_dashboard_bootstrap_data");
        }
        return this._bootstrapData;
    }

    async getDashboardData(filters = {}) {
        return this._call("get_dashboard_data", [], { filters });
    }

    async getPurchaseRequestAnalysis(filters = {}) {
        return this._call("get_purchase_request_analysis", [], { filters });
    }

    async getRfqAnalysis(filters = {}) {
        return this._call("get_rfq_analysis", [], { filters });
    }

    async getPurchaseOrderAnalysis(filters = {}) {
        return this._call("get_purchase_order_analysis", [], { filters });
    }

    async getVendorAnalysis(filters = {}) {
        return this._call("get_vendor_analysis", [], { filters });
    }

    async getProductPurchaseAnalysis(filters = {}) {
        return this._call("get_product_purchase_analysis", [], { filters });
    }

    async getReceiptMatching(filters = {}) {
        return this._call("get_receipt_matching", [], { filters });
    }

    async getBillMatching(filters = {}) {
        return this._call("get_bill_matching", [], { filters });
    }

    async getApprovalAnalysis(filters = {}) {
        return this._call("get_approval_analysis", [], { filters });
    }

    async getLateUnfinishedPurchases(filters = {}) {
        return this._call("get_late_unfinished_purchases", [], { filters });
    }

    async getPriceTrendAnalysis(filters = {}) {
        return this._call("get_price_trend_analysis", [], { filters });
    }

    async getVendorScorecards(filters = {}) {
        return this._call("get_vendor_scorecards", [], { filters });
    }

    async getPurchaseTargets(filters = {}) {
        return this._call("get_purchase_targets", [], { filters });
    }

    async getPurchaseAlerts(filters = {}) {
        return this._call("get_purchase_alerts", [], { filters });
    }

    async getGroupedReportData(filters = {}) {
        return this._call("get_grouped_report_data", [], { filters });
    }

    /**
     * Route calls to the correct method based on dashboard mode.
     */
    async getDataForMode(mode, filters = {}) {
        const modeMethodMap = {
            live_dashboard: () => this.getDashboardData(filters),
            purchase_request_analysis: () => this.getPurchaseRequestAnalysis(filters),
            rfq_analysis: () => this.getRfqAnalysis(filters),
            purchase_order_analysis: () => this.getPurchaseOrderAnalysis(filters),
            vendor_analysis: () => this.getVendorAnalysis(filters),
            product_purchase_analysis: () => this.getProductPurchaseAnalysis(filters),
            receipt_matching: () => this.getReceiptMatching(filters),
            bill_matching: () => this.getBillMatching(filters),
            approval_analysis: () => this.getApprovalAnalysis(filters),
            late_unfinished_purchases: () => this.getLateUnfinishedPurchases(filters),
            price_trend_analysis: () => this.getPriceTrendAnalysis(filters),
            vendor_scorecards: () => this.getVendorScorecards(filters),
            purchase_targets: () => this.getPurchaseTargets(filters),
            purchase_alerts: () => this.getPurchaseAlerts(filters),
        };
        const fn = modeMethodMap[mode];
        if (!fn) {
            return this.getDashboardData(filters);
        }
        return fn();
    }

    invalidateBootstrap() {
        this._bootstrapData = null;
    }
}

registry.category("services").add("purchase_analytics_service", {
    dependencies: ["orm"],
    start(env) {
        return new PurchaseAnalyticsService(env);
    },
});
