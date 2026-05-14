# Copyright 2024 - Purchase Advanced Analytics
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError


class PurchaseAnalyticsAlertRule(models.Model):
    _name = "purchase.analytics.alert.rule"
    _description = "Purchase Operational Alert Rule"
    _order = "company_id, name"

    name = fields.Char(
        string="Name",
        required=True,
    )
    alert_type = fields.Selection(
        selection=[
            ("late_receipt", "Late Receipt"),
            ("waiting_approval_too_long", "Waiting Approval Too Long"),
            ("price_increase", "Price Increase"),
            ("unbilled_po", "Unbilled PO"),
            ("unreceived_po", "Unreceived PO"),
            ("vendor_delay", "Vendor Delay"),
            ("high_value_po", "High Value PO"),
            ("cancelled_po_spike", "Cancelled PO Spike"),
            ("pending_rfq_too_long", "Pending RFQ Too Long"),
            ("partial_receipt_too_long", "Partial Receipt Too Long"),
            ("bill_overdue", "Bill Overdue"),
        ],
        string="Alert Type",
        required=True,
    )
    threshold_days = fields.Integer(
        string="Threshold Days",
        default=7,
    )
    threshold_amount = fields.Float(
        string="Threshold Amount",
        digits=(16, 2),
    )
    threshold_percentage = fields.Float(
        string="Threshold Percentage (%)",
        digits=(5, 2),
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product Filter",
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Category Filter",
    )
    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor Filter",
        domain=[("supplier_rank", ">", 0)],
    )
    buyer_id = fields.Many2one(
        comodel_name="res.users",
        string="Buyer Filter",
    )
    active = fields.Boolean(
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    description = fields.Text(
        string="Description",
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("threshold_days")
    def _check_threshold_days(self):
        for record in self:
            if record.threshold_days < 0:
                raise ValidationError(
                    "Threshold Days must be greater than or equal to 0."
                )

    @api.constrains("threshold_amount")
    def _check_threshold_amount(self):
        for record in self:
            if record.threshold_amount < 0:
                raise ValidationError(
                    "Threshold Amount must be greater than or equal to 0."
                )

    @api.constrains("threshold_percentage")
    def _check_threshold_percentage(self):
        for record in self:
            if record.threshold_percentage < 0:
                raise ValidationError(
                    "Threshold Percentage must be greater than or equal to 0."
                )

    # ------------------------------------------------------------------
    # Access Control
    # ------------------------------------------------------------------

    def _check_manager_access(self):
        """Raise AccessError if the current user is not a purchase analytics manager."""
        if not self.env.user.has_group(
            "purchase_advanced_analytics.group_purchase_analytics_manager"
        ):
            raise AccessError(
                "Only Purchase Analytics Managers can create, modify, "
                "or delete purchase alert rules."
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager_access()
        return super().create(vals_list)

    def write(self, vals):
        self._check_manager_access()
        return super().write(vals)

    def unlink(self):
        self._check_manager_access()
        return super().unlink()
