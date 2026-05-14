# Copyright 2024 - Purchase Advanced Analytics
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError


class PurchaseAnalyticsVendorRule(models.Model):
    _name = "purchase.analytics.vendor.rule"
    _description = "Vendor Scorecard Weighting Rule"
    _order = "company_id, name"

    name = fields.Char(
        string="Rule Name",
        required=True,
    )
    on_time_delivery_weight = fields.Float(
        string="On-Time Delivery Weight (%)",
        default=30.0,
    )
    price_stability_weight = fields.Float(
        string="Price Stability Weight (%)",
        default=20.0,
    )
    completion_rate_weight = fields.Float(
        string="Completion Rate Weight (%)",
        default=20.0,
    )
    response_speed_weight = fields.Float(
        string="Response Speed Weight (%)",
        default=15.0,
    )
    quality_score_weight = fields.Float(
        string="Quality Score Weight (%)",
        default=15.0,
    )
    active = fields.Boolean(
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            "name_company_uniq",
            "UNIQUE(name, company_id)",
            "A rule with this name already exists for the selected company.",
        ),
    ]

    # ------------------------------------------------------------------
    # Computed / Properties
    # ------------------------------------------------------------------

    @property
    def total_weight(self):
        """Return the sum of all scorecard weights."""
        return (
            self.on_time_delivery_weight
            + self.price_stability_weight
            + self.completion_rate_weight
            + self.response_speed_weight
            + self.quality_score_weight
        )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains(
        "on_time_delivery_weight",
        "price_stability_weight",
        "completion_rate_weight",
        "response_speed_weight",
        "quality_score_weight",
    )
    def _check_weights_non_negative(self):
        for record in self:
            if record.on_time_delivery_weight < 0:
                raise ValidationError(
                    "On-Time Delivery Weight must be greater than or equal to 0."
                )
            if record.price_stability_weight < 0:
                raise ValidationError(
                    "Price Stability Weight must be greater than or equal to 0."
                )
            if record.completion_rate_weight < 0:
                raise ValidationError(
                    "Completion Rate Weight must be greater than or equal to 0."
                )
            if record.response_speed_weight < 0:
                raise ValidationError(
                    "Response Speed Weight must be greater than or equal to 0."
                )
            if record.quality_score_weight < 0:
                raise ValidationError(
                    "Quality Score Weight must be greater than or equal to 0."
                )

    @api.constrains(
        "on_time_delivery_weight",
        "price_stability_weight",
        "completion_rate_weight",
        "response_speed_weight",
        "quality_score_weight",
    )
    def _check_total_weight_positive(self):
        for record in self:
            total = (
                record.on_time_delivery_weight
                + record.price_stability_weight
                + record.completion_rate_weight
                + record.response_speed_weight
                + record.quality_score_weight
            )
            if total <= 0:
                raise ValidationError(
                    "The total of all scorecard weights must be greater than 0."
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
                "or delete vendor scorecard rules."
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

    # ------------------------------------------------------------------
    # Business Methods
    # ------------------------------------------------------------------

    def get_default_rule(self, company_id=None):
        """Return the active rule for the given company.

        Falls back to a global rule (company_id is False/None) if no
        company-specific rule is found.  Returns None when no rule exists.

        :param company_id: int or res.company record, or None for the
                           current company.
        :return: PurchaseAnalyticsVendorRule recordset (single record) or None
        """
        if company_id is None:
            company_id = self.env.company.id
        elif hasattr(company_id, "id"):
            company_id = company_id.id

        # 1. Look for a rule specific to the requested company.
        rule = self.search(
            [("company_id", "=", company_id), ("active", "=", True)],
            limit=1,
            order="id asc",
        )
        if rule:
            return rule

        # 2. Fall back to a global (company-agnostic) rule.
        rule = self.search(
            [("company_id", "=", False), ("active", "=", True)],
            limit=1,
            order="id asc",
        )
        if rule:
            return rule

        return None
