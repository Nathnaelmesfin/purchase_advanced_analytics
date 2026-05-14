# Copyright 2024 - Purchase Advanced Analytics
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api
from odoo.exceptions import AccessError


class PurchaseAnalyticsReportWizard(models.TransientModel):
    _name = "purchase.analytics.report.wizard"
    _description = "Purchase Analytics Report Wizard"

    # ------------------------------------------------------------------
    # Date Range Fields
    # ------------------------------------------------------------------

    date_start = fields.Date(
        string="Date From",
    )
    date_end = fields.Date(
        string="Date To",
    )
    order_date_from = fields.Date(
        string="Order Date From",
    )
    order_date_to = fields.Date(
        string="Order Date To",
    )
    expected_date_from = fields.Date(
        string="Expected Date From",
    )
    expected_date_to = fields.Date(
        string="Expected Date To",
    )
    confirmation_date_from = fields.Date(
        string="Confirmation Date From",
    )
    confirmation_date_to = fields.Date(
        string="Confirmation Date To",
    )

    # ------------------------------------------------------------------
    # Grouping / Participant Fields
    # ------------------------------------------------------------------

    vendor_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Vendors",
        domain=[("supplier_rank", ">", 0)],
    )
    buyer_ids = fields.Many2many(
        comodel_name="res.users",
        string="Buyers",
    )
    requested_by_ids = fields.Many2many(
        comodel_name="res.users",
        relation="pal_wizard_requested_by_rel",
        string="Requested By",
    )
    approved_by_ids = fields.Many2many(
        comodel_name="res.users",
        relation="pal_wizard_approved_by_rel",
        string="Approved By",
    )
    department = fields.Char(
        string="Department",
    )
    branch_label = fields.Char(
        string="Branch",
    )
    warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        string="Warehouses",
    )
    product_category_ids = fields.Many2many(
        comodel_name="product.category",
        string="Product Categories",
    )
    product_ids = fields.Many2many(
        comodel_name="product.product",
        string="Products",
    )

    # ------------------------------------------------------------------
    # Status Filter Fields
    # ------------------------------------------------------------------

    purchase_state = fields.Selection(
        selection=[
            ("", "All"),
            ("draft", "Draft RFQ"),
            ("sent", "RFQ Sent"),
            ("to approve", "Waiting Approval"),
            ("purchase", "Purchase Order"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Purchase State",
        default="",
    )
    receipt_status = fields.Selection(
        selection=[
            ("", "All"),
            ("not_received", "Not Received"),
            ("partially_received", "Partially Received"),
            ("fully_received", "Fully Received"),
        ],
        string="Receipt Status",
        default="",
    )
    bill_status = fields.Selection(
        selection=[
            ("", "All"),
            ("not_billed", "Not Billed"),
            ("partially_billed", "Partially Billed"),
            ("fully_billed", "Fully Billed"),
        ],
        string="Bill Status",
        default="",
    )
    payment_status = fields.Selection(
        selection=[
            ("", "All"),
            ("not_paid", "Not Paid"),
            ("partial", "Partial"),
            ("paid", "Paid"),
            ("overdue", "Overdue"),
        ],
        string="Payment Status",
        default="",
    )

    # ------------------------------------------------------------------
    # Report Configuration Fields
    # ------------------------------------------------------------------

    report_type = fields.Selection(
        selection=[
            ("purchase_management_summary", "Purchase Management Summary"),
            ("purchase_request_analysis_report", "Purchase Request Analysis Report"),
            ("rfq_analysis_report", "RFQ Analysis Report"),
            ("purchase_order_analysis_report", "Purchase Order Analysis Report"),
            ("vendor_performance_report", "Vendor Performance Report"),
            ("product_purchase_report", "Product Purchase Report"),
            ("category_purchase_report", "Category Purchase Report"),
            ("buyer_performance_report", "Buyer Performance Report"),
            ("receipt_matching_report", "Receipt Matching Report"),
            ("bill_matching_report", "Bill Matching Report"),
            ("approval_analysis_report", "Approval Analysis Report"),
            ("late_purchase_report", "Late Purchase Report"),
            ("unfinished_purchase_report", "Unfinished Purchase Report"),
            ("price_trend_report", "Price Trend Report"),
            ("vendor_price_comparison_report", "Vendor Price Comparison Report"),
            ("requested_product_report", "Requested Product Report"),
            ("unreceived_product_report", "Unreceived Product Report"),
            ("unbilled_purchase_report", "Unbilled Purchase Report"),
            ("cancelled_purchase_report", "Cancelled Purchase Report"),
            ("purchase_target_report", "Purchase Target Report"),
            ("purchase_alert_report", "Purchase Alert Report"),
        ],
        string="Report Type",
        required=True,
        default="purchase_management_summary",
    )
    group_by = fields.Selection(
        selection=[
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("year", "Year"),
            ("vendor", "Vendor"),
            ("buyer", "Buyer"),
            ("requested_by", "Requested By"),
            ("approved_by", "Approved By"),
            ("product", "Product"),
            ("product_category", "Product Category"),
            ("warehouse", "Warehouse"),
            ("department", "Department"),
            ("branch", "Branch"),
            ("purchase_status", "Purchase Status"),
            ("business_status", "Business Status"),
            ("receipt_status", "Receipt Status"),
            ("bill_status", "Bill Status"),
            ("payment_status", "Payment Status"),
        ],
        string="Group By",
        default="month",
    )
    report_basis = fields.Selection(
        selection=[
            ("purchase_amount", "Purchase Amount"),
            ("untaxed_amount", "Untaxed Amount"),
            ("tax_amount", "Tax Amount"),
            ("ordered_quantity", "Ordered Quantity"),
            ("received_quantity", "Received Quantity"),
            ("pending_quantity", "Pending Quantity"),
            ("po_count", "PO Count"),
            ("rfq_count", "RFQ Count"),
            ("billed_amount", "Billed Amount"),
            ("unbilled_amount", "Unbilled Amount"),
        ],
        string="Report Basis",
        default="purchase_amount",
    )

    # ------------------------------------------------------------------
    # Include Detail Flags
    # ------------------------------------------------------------------

    include_raw_orders = fields.Boolean(
        string="Include Raw Orders",
        default=False,
    )
    include_raw_lines = fields.Boolean(
        string="Include Raw PO Lines",
        default=False,
    )
    include_receipts = fields.Boolean(
        string="Include Receipt Details",
        default=False,
    )
    include_bills = fields.Boolean(
        string="Include Bill Details",
        default=False,
    )

    # ------------------------------------------------------------------
    # Export Format
    # ------------------------------------------------------------------

    export_format = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("excel", "Excel"),
        ],
        string="Export Format",
        required=True,
        default="excel",
    )

    # ------------------------------------------------------------------
    # Filter Flag Fields
    # ------------------------------------------------------------------

    only_waiting_approval = fields.Boolean(
        string="Only Waiting Approval",
        default=False,
    )
    only_late = fields.Boolean(
        string="Only Late Purchases",
        default=False,
    )
    only_unreceived = fields.Boolean(
        string="Only Unreceived Products",
        default=False,
    )
    only_unbilled = fields.Boolean(
        string="Only Unbilled Purchases",
        default=False,
    )
    only_unfinished = fields.Boolean(
        string="Only Unfinished",
        default=False,
    )
    only_price_increased = fields.Boolean(
        string="Only Price Increased",
        default=False,
    )
    only_cancelled = fields.Boolean(
        string="Only Cancelled",
        default=False,
    )

    # ------------------------------------------------------------------
    # Main Action
    # ------------------------------------------------------------------

    def action_generate_report(self):
        """Generate a PDF or Excel report based on wizard configuration."""
        self.ensure_one()
        if not self.env.user.has_group(
            "purchase_advanced_analytics.group_purchase_analytics_user"
        ):
            raise AccessError(
                "You do not have the required access rights to generate "
                "purchase analytics reports."
            )

        if self.export_format == "pdf":
            return self.env.ref(
                "purchase_advanced_analytics.action_purchase_analytics_report_pdf"
            ).report_action(self)

        # export_format == 'excel'
        return {
            "type": "ir.actions.act_url",
            "url": f"/purchase_advanced_analytics/xlsx/{self.id}",
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Filter Builder
    # ------------------------------------------------------------------

    def _build_filters(self):
        """Return a dict of active filters from the wizard fields.

        Used by the report service and Excel export controller to build
        domain / query parameters.
        """
        self.ensure_one()
        filters = {}

        # Date ranges
        if self.date_start:
            filters["date_start"] = self.date_start
        if self.date_end:
            filters["date_end"] = self.date_end
        if self.order_date_from:
            filters["order_date_from"] = self.order_date_from
        if self.order_date_to:
            filters["order_date_to"] = self.order_date_to
        if self.expected_date_from:
            filters["expected_date_from"] = self.expected_date_from
        if self.expected_date_to:
            filters["expected_date_to"] = self.expected_date_to
        if self.confirmation_date_from:
            filters["confirmation_date_from"] = self.confirmation_date_from
        if self.confirmation_date_to:
            filters["confirmation_date_to"] = self.confirmation_date_to

        # Many2many participant filters
        if self.vendor_ids:
            filters["vendor_ids"] = self.vendor_ids.ids
        if self.buyer_ids:
            filters["buyer_ids"] = self.buyer_ids.ids
        if self.requested_by_ids:
            filters["requested_by_ids"] = self.requested_by_ids.ids
        if self.approved_by_ids:
            filters["approved_by_ids"] = self.approved_by_ids.ids

        # Char filters
        if self.department:
            filters["department"] = self.department
        if self.branch_label:
            filters["branch_label"] = self.branch_label

        # Many2many dimension filters
        if self.warehouse_ids:
            filters["warehouse_ids"] = self.warehouse_ids.ids
        if self.product_category_ids:
            filters["product_category_ids"] = self.product_category_ids.ids
        if self.product_ids:
            filters["product_ids"] = self.product_ids.ids

        # Status filters (only include when a specific value is chosen)
        if self.purchase_state:
            filters["purchase_state"] = self.purchase_state
        if self.receipt_status:
            filters["receipt_status"] = self.receipt_status
        if self.bill_status:
            filters["bill_status"] = self.bill_status
        if self.payment_status:
            filters["payment_status"] = self.payment_status

        # Report configuration
        filters["report_type"] = self.report_type
        filters["group_by"] = self.group_by
        filters["report_basis"] = self.report_basis

        # Include detail flags
        filters["include_raw_orders"] = self.include_raw_orders
        filters["include_raw_lines"] = self.include_raw_lines
        filters["include_receipts"] = self.include_receipts
        filters["include_bills"] = self.include_bills

        # Boolean shortcut filters
        filters["only_waiting_approval"] = self.only_waiting_approval
        filters["only_late"] = self.only_late
        filters["only_unreceived"] = self.only_unreceived
        filters["only_unbilled"] = self.only_unbilled
        filters["only_unfinished"] = self.only_unfinished
        filters["only_price_increased"] = self.only_price_increased
        filters["only_cancelled"] = self.only_cancelled

        return filters

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def action_generate_pdf(self):
        """Convenience method: force PDF export and generate the report."""
        self.ensure_one()
        self.export_format = "pdf"
        return self.action_generate_report()

    def action_generate_excel(self):
        """Convenience method: force Excel export and generate the report."""
        self.ensure_one()
        self.export_format = "excel"
        return self.action_generate_report()
