/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const TABS = [
    { mode: "live_dashboard", label: "Live Dashboard" },
    { mode: "purchase_request_analysis", label: "Purchase Requests" },
    { mode: "rfq_analysis", label: "RFQ Analysis" },
    { mode: "purchase_order_analysis", label: "Purchase Orders" },
    { mode: "vendor_analysis", label: "Vendor Analysis" },
    { mode: "product_purchase_analysis", label: "Product Analysis" },
    { mode: "receipt_matching", label: "Receipt Matching" },
    { mode: "bill_matching", label: "Bill Matching" },
    { mode: "approval_analysis", label: "Approval Analysis" },
    { mode: "late_unfinished_purchases", label: "Late & Unfinished" },
    { mode: "price_trend_analysis", label: "Price Trends" },
    { mode: "vendor_scorecards", label: "Vendor Scorecards" },
    { mode: "purchase_targets", label: "Targets" },
    { mode: "purchase_alerts", label: "Alerts" },
];

class PurchaseAnalyticsDashboard extends Component {
    static template = "purchase_analytics_dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Determine initial mode from action context
        const ctx = this.props.action?.context || {};
        const initialMode = ctx.mode || "live_dashboard";

        this.state = useState({
            loading: true,
            loading_mode: false,
            error: null,
            mode: initialMode,
            data: null,
            refreshing: false,
            bootstrapData: null,
        });

        this.filters = useState({
            date_range: "this_month",
            date_start: "",
            date_end: "",
            report_basis: "purchase_amount",
            group_by: "month",
            only_late: false,
            only_waiting_approval: false,
            only_unreceived: false,
            only_unbilled: false,
            only_unfinished: false,
        });

        this.tabs = TABS;
        this._refreshTimer = null;
        this._abortController = null;

        onWillStart(async () => {
            await this.initialize();
        });

        onMounted(() => {
            this.scheduleAutoRefresh();
        });

        onWillUnmount(() => {
            this.clearAutoRefresh();
        });
    }

    // ─── INITIALIZATION ───────────────────────────────────────────

    async initialize() {
        try {
            this.state.loading = true;
            this.state.error = null;

            // Load bootstrap data (filter options, settings)
            const bootstrap = await this.orm.call(
                "purchase.analytics.service",
                "get_dashboard_bootstrap_data",
                [],
                {}
            );
            this.state.bootstrapData = bootstrap;

            // Apply default date range from settings
            if (bootstrap.settings && bootstrap.settings.default_dashboard_date_range) {
                this.filters.date_range = bootstrap.settings.default_dashboard_date_range;
            }

            // Load initial mode data
            await this.loadData();
        } catch (e) {
            this.state.error = e.message || String(e);
            this.state.loading = false;
        }
    }

    // ─── DATA LOADING ─────────────────────────────────────────────

    async loadData() {
        try {
            this.state.loading = true;
            this.state.error = null;

            const filters = this.buildFilters();
            const data = await this.orm.call(
                "purchase.analytics.service",
                this.getMethodForMode(this.state.mode),
                [],
                { filters }
            );
            this.state.data = data;
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    getMethodForMode(mode) {
        const map = {
            live_dashboard: "get_dashboard_data",
            purchase_request_analysis: "get_purchase_request_analysis",
            rfq_analysis: "get_rfq_analysis",
            purchase_order_analysis: "get_purchase_order_analysis",
            vendor_analysis: "get_vendor_analysis",
            product_purchase_analysis: "get_product_purchase_analysis",
            receipt_matching: "get_receipt_matching",
            bill_matching: "get_bill_matching",
            approval_analysis: "get_approval_analysis",
            late_unfinished_purchases: "get_late_unfinished_purchases",
            price_trend_analysis: "get_price_trend_analysis",
            vendor_scorecards: "get_vendor_scorecards",
            purchase_targets: "get_purchase_targets",
            purchase_alerts: "get_purchase_alerts",
        };
        return map[mode] || "get_dashboard_data";
    }

    buildFilters() {
        const f = { ...this.filters };
        // Convert boolean strings if needed
        f.only_late = Boolean(f.only_late);
        f.only_waiting_approval = Boolean(f.only_waiting_approval);
        f.only_unreceived = Boolean(f.only_unreceived);
        f.only_unbilled = Boolean(f.only_unbilled);
        f.only_unfinished = Boolean(f.only_unfinished);
        f.report_type = this.getModeReportType(this.state.mode);
        return f;
    }

    getModeReportType(mode) {
        const map = {
            live_dashboard: "purchase_management_summary",
            purchase_request_analysis: "purchase_request_analysis_report",
            rfq_analysis: "rfq_analysis_report",
            purchase_order_analysis: "purchase_order_analysis_report",
            vendor_analysis: "vendor_performance_report",
            product_purchase_analysis: "product_purchase_report",
            receipt_matching: "receipt_matching_report",
            bill_matching: "bill_matching_report",
            approval_analysis: "approval_analysis_report",
            late_unfinished_purchases: "late_purchase_report",
            price_trend_analysis: "price_trend_report",
            vendor_scorecards: "vendor_performance_report",
            purchase_targets: "purchase_target_report",
            purchase_alerts: "purchase_alert_report",
        };
        return map[mode] || "purchase_management_summary";
    }

    // ─── USER ACTIONS ─────────────────────────────────────────────

    async switchMode(mode) {
        if (this.state.mode === mode && !this.state.loading) return;
        this.state.mode = mode;
        this.state.data = null;
        await this.loadData();
    }

    async applyFilters() {
        await this.loadData();
    }

    onFilterChange() {
        // Debounce auto-apply for select changes
    }

    resetFilters() {
        this.filters.date_range = "this_month";
        this.filters.date_start = "";
        this.filters.date_end = "";
        this.filters.report_basis = "purchase_amount";
        this.filters.group_by = "month";
        this.filters.only_late = false;
        this.filters.only_waiting_approval = false;
        this.filters.only_unreceived = false;
        this.filters.only_unbilled = false;
        this.filters.only_unfinished = false;
    }

    async refreshData() {
        if (this.state.refreshing) return;
        this.state.refreshing = true;
        try {
            await this.loadData();
        } finally {
            this.state.refreshing = false;
        }
    }

    async openReportWizard() {
        const filters = this.buildFilters();
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "purchase.analytics.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_report_type: filters.report_type,
                default_date_start: filters.date_start || false,
                default_date_end: filters.date_end || false,
                default_report_basis: filters.report_basis,
                default_group_by: filters.group_by,
            },
        });
    }

    async openTargetForm() {
        await this.action.doAction("purchase_advanced_analytics.action_purchase_analytics_target");
    }

    // ─── AUTO REFRESH ─────────────────────────────────────────────

    scheduleAutoRefresh() {
        const settings = this.state.bootstrapData?.settings || {};
        const interval = Math.max(30, settings.auto_refresh_interval || 300) * 1000;
        this._refreshTimer = setInterval(() => {
            if (!document.hidden) {
                this.loadData();
            }
        }, interval);
    }

    clearAutoRefresh() {
        if (this._refreshTimer) {
            clearInterval(this._refreshTimer);
            this._refreshTimer = null;
        }
    }

    // ─── FORMATTING HELPERS ───────────────────────────────────────

    getPageTitle() {
        const tab = TABS.find((t) => t.mode === this.state.mode);
        return tab ? tab.label : "Purchase Analytics";
    }

    formatCurrency(value) {
        if (value === null || value === undefined || value === "") return "-";
        const num = parseFloat(value) || 0;
        const bootstrap = this.state.bootstrapData;
        const symbol = bootstrap?.currency_symbol || "";
        const position = bootstrap?.currency_position || "before";
        const formatted = num.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return position === "before" ? `${symbol}${formatted}` : `${formatted}${symbol}`;
    }

    formatQty(value) {
        if (value === null || value === undefined) return "0";
        const num = parseFloat(value) || 0;
        return num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 3 });
    }

    formatNumber(value) {
        if (value === null || value === undefined) return "0";
        return parseFloat(value).toLocaleString();
    }

    formatPercent(value) {
        if (value === null || value === undefined) return "0%";
        return `${parseFloat(value).toFixed(1)}%`;
    }
}

// Register as client action
registry.category("actions").add("purchase_analytics_dashboard", PurchaseAnalyticsDashboard);
