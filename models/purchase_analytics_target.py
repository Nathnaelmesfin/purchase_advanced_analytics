# Copyright 2024 - Purchase Advanced Analytics
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError


class PurchaseAnalyticsTarget(models.Model):
    _name = "purchase.analytics.target"
    _description = "Purchase Analytics Target"
    _order = "date_start desc, name"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string="Name",
        required=True,
    )
    date_start = fields.Date(
        string="Start Date",
        required=True,
    )
    date_end = fields.Date(
        string="End Date",
        required=True,
    )
    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        domain=[("supplier_rank", ">", 0)],
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
    )
    product_category_id = fields.Many2one(
        comodel_name="product.category",
        string="Product Category",
    )
    buyer_id = fields.Many2one(
        comodel_name="res.users",
        string="Buyer",
    )
    department = fields.Char(
        string="Department",
    )
    branch_label = fields.Char(
        string="Branch",
    )
    target_amount = fields.Float(
        string="Target Amount",
        digits=(16, 2),
    )
    maximum_amount = fields.Float(
        string="Maximum Amount / Budget Limit",
        digits=(16, 2),
    )
    target_quantity = fields.Float(
        string="Target Quantity",
        digits=(16, 3),
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(
        default=True,
    )
    notes = fields.Text(
        string="Notes",
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end:
                if record.date_end < record.date_start:
                    raise ValidationError(
                        "End Date must be greater than or equal to Start Date."
                    )

    @api.constrains("target_amount", "maximum_amount", "target_quantity")
    def _check_amounts_non_negative(self):
        for record in self:
            if record.target_amount < 0:
                raise ValidationError(
                    "Target Amount must be greater than or equal to 0."
                )
            if record.maximum_amount < 0:
                raise ValidationError(
                    "Maximum Amount / Budget Limit must be greater than or equal to 0."
                )
            if record.target_quantity < 0:
                raise ValidationError(
                    "Target Quantity must be greater than or equal to 0."
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
                "or delete purchase analytics targets."
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
