from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError


class PurchaseAnalyticsStatusMap(models.Model):
    _name = 'purchase.analytics.status.map'
    _description = 'Purchase Analytics Status Map'
    _order = 'technical_state, applies_to'

    name = fields.Char(required=True)
    technical_state = fields.Char(required=True, string="Technical State")
    business_status = fields.Selection(
        selection=[
            ('draft_rfq', 'Draft RFQ'),
            ('rfq_sent', 'RFQ Sent'),
            ('waiting_approval', 'Waiting Approval'),
            ('approved_po', 'Approved Purchase Order'),
            ('partially_received', 'Partially Received'),
            ('fully_received', 'Fully Received'),
            ('partially_billed', 'Partially Billed'),
            ('fully_billed', 'Fully Billed'),
            ('late', 'Late'),
            ('unfinished', 'Unfinished'),
            ('cancelled', 'Cancelled'),
            ('other', 'Other'),
        ],
        required=True,
        string="Business Status",
    )
    applies_to = fields.Selection(
        selection=[
            ('rfq', 'RFQ'),
            ('purchase_order', 'Purchase Order'),
            ('receipt', 'Receipt'),
            ('bill', 'Bill'),
            ('all', 'All'),
        ],
        required=True,
        default='all',
        string="Applies To",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        default=lambda self: self.env.company,
    )
    description = fields.Text(string="Description")

    def _check_manager_access(self):
        if not self.env.user.has_group(
            'purchase_advanced_analytics.group_purchase_analytics_manager'
        ):
            raise AccessError(
                self.env._("You must be a Purchase Analytics Manager to perform this action.")
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

    @api.model
    def get_default_mappings(self):
        """Return a list of dicts with default technical state -> business status mappings."""
        return [
            {
                'name': 'Draft',
                'technical_state': 'draft',
                'business_status': 'draft_rfq',
                'applies_to': 'rfq',
                'description': 'RFQ in draft state.',
            },
            {
                'name': 'Sent',
                'technical_state': 'sent',
                'business_status': 'rfq_sent',
                'applies_to': 'rfq',
                'description': 'RFQ has been sent to the vendor.',
            },
            {
                'name': 'To Approve',
                'technical_state': 'to approve',
                'business_status': 'waiting_approval',
                'applies_to': 'purchase_order',
                'description': 'Purchase order is waiting for manager approval.',
            },
            {
                'name': 'Purchase',
                'technical_state': 'purchase',
                'business_status': 'approved_po',
                'applies_to': 'purchase_order',
                'description': 'Purchase order has been confirmed and approved.',
            },
            {
                'name': 'Done',
                'technical_state': 'done',
                'business_status': 'fully_received',
                'applies_to': 'purchase_order',
                'description': 'Purchase order is fully received and locked.',
            },
            {
                'name': 'Cancelled',
                'technical_state': 'cancel',
                'business_status': 'cancelled',
                'applies_to': 'all',
                'description': 'Order or document has been cancelled.',
            },
        ]
