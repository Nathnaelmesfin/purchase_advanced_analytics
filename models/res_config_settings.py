from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Dashboard & General Settings
    default_dashboard_date_range = fields.Selection(
        selection=[
            ('today', 'Today'),
            ('this_week', 'This Week'),
            ('this_month', 'This Month'),
            ('this_quarter', 'This Quarter'),
            ('this_year', 'This Year'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('last_90_days', 'Last 90 Days'),
            ('custom', 'Custom'),
        ],
        string="Default Dashboard Date Range",
        default='this_month',
        config_parameter='purchase_advanced_analytics.default_dashboard_date_range',
    )

    auto_refresh_interval = fields.Integer(
        string="Auto Refresh Interval (seconds)",
        default=300,
        config_parameter='purchase_advanced_analytics.auto_refresh_interval',
    )

    default_report_timezone = fields.Char(
        string="Default Report Timezone",
        default='Africa/Addis_Ababa',
        config_parameter='purchase_advanced_analytics.default_report_timezone',
    )

    # Alert & Threshold Settings
    late_receipt_grace_days = fields.Integer(
        string="Late Receipt Grace Days",
        default=0,
        config_parameter='purchase_advanced_analytics.late_receipt_grace_days',
    )

    waiting_approval_late_days = fields.Integer(
        string="Waiting Approval Late After (days)",
        default=3,
        config_parameter='purchase_advanced_analytics.waiting_approval_late_days',
    )

    pending_rfq_late_days = fields.Integer(
        string="Pending RFQ Late After (days)",
        default=7,
        config_parameter='purchase_advanced_analytics.pending_rfq_late_days',
    )

    price_increase_threshold_percentage = fields.Float(
        string="Price Increase Alert Threshold (%)",
        default=5.0,
        config_parameter='purchase_advanced_analytics.price_increase_threshold_percentage',
        digits=(5, 2),
    )

    unfinished_purchase_days_threshold = fields.Integer(
        string="Unfinished Purchase Alert After (days)",
        default=30,
        config_parameter='purchase_advanced_analytics.unfinished_purchase_days_threshold',
    )

    # Analytics Module Toggles
    enable_purchase_request_analytics = fields.Boolean(
        string="Enable Purchase Request Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_purchase_request_analytics',
    )

    enable_rfq_analytics = fields.Boolean(
        string="Enable RFQ Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_rfq_analytics',
    )

    enable_purchase_order_analytics = fields.Boolean(
        string="Enable Purchase Order Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_purchase_order_analytics',
    )

    enable_vendor_analytics = fields.Boolean(
        string="Enable Vendor Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_vendor_analytics',
    )

    enable_receipt_matching = fields.Boolean(
        string="Enable Receipt Matching",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_receipt_matching',
    )

    enable_bill_matching = fields.Boolean(
        string="Enable Bill Matching",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_bill_matching',
    )

    enable_approval_analytics = fields.Boolean(
        string="Enable Approval Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_approval_analytics',
    )

    enable_price_trend_analytics = fields.Boolean(
        string="Enable Price Trend Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_price_trend_analytics',
    )

    enable_target_analytics = fields.Boolean(
        string="Enable Target Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_target_analytics',
    )

    enable_alert_analytics = fields.Boolean(
        string="Enable Alert Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_alert_analytics',
    )

    enable_buyer_analytics = fields.Boolean(
        string="Enable Buyer Analytics",
        default=True,
        config_parameter='purchase_advanced_analytics.enable_buyer_analytics',
    )

    # Many2many default filter fields (stored as comma-separated IDs in ir.config_parameter)
    default_vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='res_config_settings_default_vendor_rel',
        column1='config_id',
        column2='partner_id',
        string="Default Vendors",
    )

    default_buyer_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_config_settings_default_buyer_rel',
        column1='config_id',
        column2='user_id',
        string="Default Buyers",
    )

    default_warehouse_ids = fields.Many2many(
        comodel_name='stock.warehouse',
        relation='res_config_settings_default_warehouse_rel',
        column1='config_id',
        column2='warehouse_id',
        string="Default Warehouses",
    )

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('auto_refresh_interval')
    def _check_auto_refresh_interval(self):
        for record in self:
            if record.auto_refresh_interval < 30:
                raise ValidationError(
                    "Auto Refresh Interval must be at least 30 seconds."
                )

    # -------------------------------------------------------------------------
    # Config parameter helpers
    # -------------------------------------------------------------------------

    def _get_many2many_from_param(self, param_key, model_name):
        """Read comma-separated IDs from ir.config_parameter and return recordset."""
        IrConfigParameter = self.env['ir.config_parameter'].sudo()
        value = IrConfigParameter.get_param(param_key, default='')
        if not value:
            return self.env[model_name]
        try:
            ids = [int(id_str.strip()) for id_str in value.split(',') if id_str.strip()]
        except (ValueError, TypeError):
            return self.env[model_name]
        return self.env[model_name].browse(ids).exists()

    def _set_many2many_to_param(self, param_key, records):
        """Write comma-separated IDs to ir.config_parameter."""
        IrConfigParameter = self.env['ir.config_parameter'].sudo()
        value = ','.join(str(rec.id) for rec in records) if records else ''
        IrConfigParameter.set_param(param_key, value)

    # -------------------------------------------------------------------------
    # get_values / set_values
    # -------------------------------------------------------------------------

    @api.model
    def get_values(self):
        res = super().get_values()

        # Many2many fields — loaded from ir.config_parameter
        res['default_vendor_ids'] = self._get_many2many_from_param(
            'purchase_advanced_analytics.default_vendor_ids',
            'res.partner',
        ).ids

        res['default_buyer_ids'] = self._get_many2many_from_param(
            'purchase_advanced_analytics.default_buyer_ids',
            'res.users',
        ).ids

        res['default_warehouse_ids'] = self._get_many2many_from_param(
            'purchase_advanced_analytics.default_warehouse_ids',
            'stock.warehouse',
        ).ids

        return res

    def set_values(self):
        super().set_values()

        # Many2many fields — persisted to ir.config_parameter
        self._set_many2many_to_param(
            'purchase_advanced_analytics.default_vendor_ids',
            self.default_vendor_ids,
        )

        self._set_many2many_to_param(
            'purchase_advanced_analytics.default_buyer_ids',
            self.default_buyer_ids,
        )

        self._set_many2many_to_param(
            'purchase_advanced_analytics.default_warehouse_ids',
            self.default_warehouse_ids,
        )
