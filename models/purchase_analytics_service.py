import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import pytz

from odoo import models, fields, api
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PurchaseAnalyticsService(models.AbstractModel):
    _name = 'purchase.analytics.service'
    _description = 'Purchase Advanced Analytics Service'

    # ─── ACCESS CONTROL ───────────────────────────────────────────

    def _check_analytics_access(self):
        if not self.env.user.has_group('purchase_advanced_analytics.group_purchase_analytics_user'):
            raise AccessError("You do not have access to Purchase Analytics.")

    def _check_manager_access(self):
        if not self.env.user.has_group('purchase_advanced_analytics.group_purchase_analytics_manager'):
            raise AccessError("This action requires Purchase Analytics Manager access.")

    # ─── OPTIONAL MODEL / FIELD DETECTION ─────────────────────────

    @api.model
    def _model_exists(self, model_name):
        try:
            return model_name in self.env
        except Exception:
            return False

    @api.model
    def _model_has_field(self, model_name, field_name):
        try:
            if not self._model_exists(model_name):
                return False
            return field_name in self.env[model_name]._fields
        except Exception:
            return False

    @api.model
    def _table_has_column(self, table_name, column_name):
        try:
            self.env.cr.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
                (table_name, column_name)
            )
            return bool(self.env.cr.fetchone())
        except Exception:
            return False

    @api.model
    def _safe_read_field(self, record, field_name, default=None):
        try:
            if field_name in record._fields:
                return record[field_name]
        except Exception:
            pass
        return default

    @api.model
    def _safe_first_existing_field(self, model_name, field_names):
        for fn in field_names:
            if self._model_has_field(model_name, fn):
                return fn
        return None

    @api.model
    def _get_optional_approval_fields(self):
        result = {}
        for candidate in ['approval_state', 'x_approval_status', 'request_state', 'x_request_status']:
            if self._model_has_field('purchase.order', candidate):
                result['approval_state_field'] = candidate
                break
        result['approved_by'] = 'approved_by' if self._model_has_field('purchase.order', 'approved_by') else None
        result['requested_by'] = 'requested_by' if self._model_has_field('purchase.order', 'requested_by') else None
        return result

    @api.model
    def _get_optional_department_field(self):
        for fn in ['department_id', 'x_department_id']:
            if self._model_has_field('purchase.order', fn):
                return fn
        return None

    @api.model
    def _get_optional_branch_field(self):
        for fn in ['branch_id', 'x_branch_id']:
            if self._model_has_field('purchase.order', fn):
                return fn
        return None

    @api.model
    def _has_purchase_request_model(self):
        return self._model_exists('purchase.request')

    # ─── SETTINGS ─────────────────────────────────────────────────

    @api.model
    def _get_settings(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        return {
            'default_dashboard_date_range': get('purchase_advanced_analytics.default_dashboard_date_range', 'this_month'),
            'auto_refresh_interval': int(get('purchase_advanced_analytics.auto_refresh_interval', '300')),
            'default_report_timezone': get('purchase_advanced_analytics.default_report_timezone', 'Africa/Addis_Ababa'),
            'late_receipt_grace_days': int(get('purchase_advanced_analytics.late_receipt_grace_days', '0')),
            'waiting_approval_late_days': int(get('purchase_advanced_analytics.waiting_approval_late_days', '3')),
            'pending_rfq_late_days': int(get('purchase_advanced_analytics.pending_rfq_late_days', '7')),
            'price_increase_threshold_percentage': float(get('purchase_advanced_analytics.price_increase_threshold_percentage', '5.0')),
            'unfinished_purchase_days_threshold': int(get('purchase_advanced_analytics.unfinished_purchase_days_threshold', '30')),
            'enable_purchase_request_analytics': get('purchase_advanced_analytics.enable_purchase_request_analytics', 'True') == 'True',
            'enable_rfq_analytics': get('purchase_advanced_analytics.enable_rfq_analytics', 'True') == 'True',
            'enable_purchase_order_analytics': get('purchase_advanced_analytics.enable_purchase_order_analytics', 'True') == 'True',
            'enable_vendor_analytics': get('purchase_advanced_analytics.enable_vendor_analytics', 'True') == 'True',
            'enable_receipt_matching': get('purchase_advanced_analytics.enable_receipt_matching', 'True') == 'True',
            'enable_bill_matching': get('purchase_advanced_analytics.enable_bill_matching', 'True') == 'True',
            'enable_approval_analytics': get('purchase_advanced_analytics.enable_approval_analytics', 'True') == 'True',
            'enable_price_trend_analytics': get('purchase_advanced_analytics.enable_price_trend_analytics', 'True') == 'True',
            'enable_target_analytics': get('purchase_advanced_analytics.enable_target_analytics', 'True') == 'True',
            'enable_alert_analytics': get('purchase_advanced_analytics.enable_alert_analytics', 'True') == 'True',
            'enable_buyer_analytics': get('purchase_advanced_analytics.enable_buyer_analytics', 'True') == 'True',
        }

    # ─── FILTER NORMALIZATION ──────────────────────────────────────

    @api.model
    def _normalize_filters(self, filters):
        if not filters:
            filters = {}
        settings = self._get_settings()
        date_range = filters.get('date_range', settings.get('default_dashboard_date_range', 'this_month'))
        today = date.today()

        if date_range == 'today':
            date_start, date_end = today, today
        elif date_range == 'this_week':
            date_start = today - timedelta(days=today.weekday())
            date_end = date_start + timedelta(days=6)
        elif date_range == 'this_month':
            date_start = today.replace(day=1)
            date_end = (today.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        elif date_range == 'this_quarter':
            q = (today.month - 1) // 3
            date_start = today.replace(month=q * 3 + 1, day=1)
            date_end = (date_start + relativedelta(months=3)) - timedelta(days=1)
        elif date_range == 'this_year':
            date_start = today.replace(month=1, day=1)
            date_end = today.replace(month=12, day=31)
        elif date_range == 'last_7_days':
            date_start, date_end = today - timedelta(days=6), today
        elif date_range == 'last_30_days':
            date_start, date_end = today - timedelta(days=29), today
        elif date_range == 'last_90_days':
            date_start, date_end = today - timedelta(days=89), today
        else:
            def _parse_date(v):
                if isinstance(v, date):
                    return v
                if isinstance(v, str):
                    try:
                        return datetime.strptime(v[:10], '%Y-%m-%d').date()
                    except Exception:
                        pass
                return None
            date_start = _parse_date(filters.get('date_start')) or today.replace(day=1)
            date_end = _parse_date(filters.get('date_end')) or today

        result = dict(filters)
        result.update({
            'date_start': date_start,
            'date_end': date_end,
            'date_range': date_range,
            'settings': settings,
            'today': today,
            'timezone': filters.get('timezone', settings.get('default_report_timezone', 'Africa/Addis_Ababa')),
            'company_ids': self._get_allowed_company_ids(),
            'report_basis': filters.get('report_basis', 'purchase_amount'),
            'group_by': filters.get('group_by', 'month'),
        })
        return result

    @api.model
    def _get_allowed_company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    # ─── DOMAIN BUILDERS ──────────────────────────────────────────

    @api.model
    def _get_purchase_domain(self, filters):
        company_ids = filters.get('company_ids', [self.env.company.id])
        date_start = filters.get('date_start')
        date_end = filters.get('date_end')
        domain = [('company_id', 'in', company_ids)]
        if date_start:
            domain += [('date_order', '>=', datetime.combine(date_start, datetime.min.time()))]
        if date_end:
            domain += [('date_order', '<=', datetime.combine(date_end, datetime.max.time()))]
        if filters.get('vendor_ids'):
            domain += [('partner_id', 'in', filters['vendor_ids'])]
        if filters.get('buyer_ids'):
            domain += [('user_id', 'in', filters['buyer_ids'])]
        if filters.get('warehouse_ids'):
            domain += [('picking_type_id.warehouse_id', 'in', filters['warehouse_ids'])]
        if filters.get('purchase_state'):
            domain += [('state', '=', filters['purchase_state'])]
        if filters.get('only_waiting_approval'):
            domain += [('state', '=', 'to approve')]
        if filters.get('only_cancelled'):
            domain += [('state', '=', 'cancel')]
        return domain

    @api.model
    def _get_purchase_line_domain(self, filters):
        company_ids = filters.get('company_ids', [self.env.company.id])
        date_start = filters.get('date_start')
        date_end = filters.get('date_end')
        domain = [('order_id.company_id', 'in', company_ids)]
        if date_start:
            domain += [('order_id.date_order', '>=', datetime.combine(date_start, datetime.min.time()))]
        if date_end:
            domain += [('order_id.date_order', '<=', datetime.combine(date_end, datetime.max.time()))]
        if filters.get('vendor_ids'):
            domain += [('order_id.partner_id', 'in', filters['vendor_ids'])]
        if filters.get('buyer_ids'):
            domain += [('order_id.user_id', 'in', filters['buyer_ids'])]
        if filters.get('product_ids'):
            domain += [('product_id', 'in', filters['product_ids'])]
        if filters.get('product_category_ids'):
            domain += [('product_id.categ_id', 'child_of', filters['product_category_ids'])]
        return domain

    # ─── REPORT BASIS HELPERS ─────────────────────────────────────

    @api.model
    def _basis_label(self, filters):
        return {
            'purchase_amount': 'Purchase Amount',
            'untaxed_amount': 'Untaxed Amount',
            'tax_amount': 'Tax Amount',
            'ordered_quantity': 'Ordered Quantity',
            'received_quantity': 'Received Quantity',
            'pending_quantity': 'Pending Quantity',
            'po_count': 'PO Count',
            'rfq_count': 'RFQ Count',
            'billed_amount': 'Billed Amount',
            'unbilled_amount': 'Unbilled Amount',
        }.get(filters.get('report_basis', 'purchase_amount'), 'Purchase Amount')

    @api.model
    def _basis_key(self, filters):
        return filters.get('report_basis', 'purchase_amount')

    @api.model
    def _basis_value(self, row, filters):
        return row.get(self._basis_key(filters), 0.0)

    # ─── BUSINESS STATUS HELPERS ──────────────────────────────────

    @api.model
    def _get_receipt_status_from_lines(self, lines):
        storable = [l for l in lines if l.product_id.type in ('product', 'consu')]
        if not storable:
            return 'no_receipt_required'
        total_ordered = sum(l.product_qty for l in storable)
        total_received = sum(getattr(l, 'qty_received', 0) for l in storable)
        if total_ordered <= 0:
            return 'no_receipt_required'
        if total_received <= 0:
            return 'not_received'
        if total_received >= total_ordered:
            return 'fully_received'
        return 'partially_received'

    @api.model
    def _get_bill_status_from_lines(self, lines):
        if not lines:
            return 'no_bill_required'
        total_ordered = sum(l.product_qty for l in lines)
        total_billed = sum(getattr(l, 'qty_invoiced', 0) for l in lines)
        if total_ordered <= 0:
            return 'no_bill_required'
        if total_billed <= 0:
            return 'not_billed'
        if total_billed >= total_ordered:
            return 'fully_billed'
        return 'partially_billed'

    @api.model
    def _get_business_status(self, po):
        if po.state == 'cancel':
            return 'cancelled'
        receipt_stat = self._get_receipt_status_from_lines(po.order_line)
        bill_stat = self._get_bill_status_from_lines(po.order_line)
        if po.state == 'draft':
            return 'draft_rfq'
        if po.state == 'sent':
            return 'rfq_sent'
        if po.state == 'to approve':
            return 'waiting_approval'
        # purchase or done
        if bill_stat == 'fully_billed':
            return 'fully_billed'
        if bill_stat == 'partially_billed':
            return 'partially_billed'
        if receipt_stat == 'fully_received':
            return 'fully_received'
        if receipt_stat == 'partially_received':
            return 'partially_received'
        today = date.today()
        date_planned = None
        if self._model_has_field('purchase.order', 'date_planned') and po.date_planned:
            date_planned = po.date_planned.date() if hasattr(po.date_planned, 'date') else po.date_planned
        if not date_planned:
            for line in po.order_line:
                if line.date_planned:
                    dp = line.date_planned.date() if hasattr(line.date_planned, 'date') else line.date_planned
                    date_planned = dp
                    break
        if date_planned and date_planned < today and receipt_stat in ('not_received', 'partially_received'):
            return 'late'
        return 'approved_po'

    def _get_payment_status_from_po(self, po):
        try:
            bills = po.invoice_ids.filtered(lambda m: m.move_type == 'in_invoice' and m.state != 'cancel')
            if not bills:
                return 'unknown'
            states = {getattr(b, 'payment_state', 'unknown') for b in bills}
            if states == {'paid'}:
                return 'paid'
            if 'in_payment' in states:
                return 'in_payment'
            if 'partial' in states:
                return 'partial'
            return 'not_paid'
        except Exception:
            return 'unknown'

    # ─── SQL HELPERS ──────────────────────────────────────────────

    def _ids_param(self, ids):
        return tuple(ids) if len(ids) > 1 else (ids[0],)

    def _base_po_params(self, filters):
        company_ids = filters.get('company_ids', [self.env.company.id])
        date_start = filters.get('date_start')
        date_end = filters.get('date_end')
        params = {
            'company_ids': self._ids_param(company_ids),
            'date_start': datetime.combine(date_start, datetime.min.time()),
            'date_end': datetime.combine(date_end, datetime.max.time()),
        }
        extra = ''
        if filters.get('vendor_ids'):
            params['vendor_ids'] = self._ids_param(filters['vendor_ids'])
            extra += ' AND po.partner_id IN %(vendor_ids)s'
        if filters.get('buyer_ids'):
            params['buyer_ids'] = self._ids_param(filters['buyer_ids'])
            extra += ' AND po.user_id IN %(buyer_ids)s'
        if filters.get('purchase_state'):
            params['purchase_state'] = filters['purchase_state']
            extra += ' AND po.state = %(purchase_state)s'
        return params, extra

    # ─── BOOTSTRAP DATA ───────────────────────────────────────────

    @api.model
    def get_dashboard_bootstrap_data(self):
        self._check_analytics_access()
        settings = self._get_settings()
        currency = self.env.company.currency_id
        company_ids = self._get_allowed_company_ids()
        vendors = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=200, order='name')
        buyers = self.env['res.users'].search([('share', '=', False), ('active', '=', True)], limit=100, order='name')
        warehouses = self.env['stock.warehouse'].search([('company_id', 'in', company_ids)])
        categories = self.env['product.category'].search([], limit=200, order='complete_name')
        return {
            'settings': settings,
            'currency_symbol': currency.symbol or '',
            'currency_position': currency.position or 'before',
            'has_purchase_request_model': self._has_purchase_request_model(),
            'optional_fields': self._get_optional_approval_fields(),
            'vendors': [{'id': v.id, 'name': v.name} for v in vendors],
            'buyers': [{'id': u.id, 'name': u.name} for u in buyers],
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'categories': [{'id': c.id, 'name': c.complete_name} for c in categories],
            'company_name': self.env.company.name,
            'user_name': self.env.user.name,
            'is_manager': self.env.user.has_group('purchase_advanced_analytics.group_purchase_analytics_manager'),
        }

    # ─── MAIN DASHBOARD ───────────────────────────────────────────

    @api.model
    def get_dashboard_data(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        settings = filters.get('settings', {})
        return {
            'filters': {'date_start': str(filters['date_start']), 'date_end': str(filters['date_end']), 'date_range': filters.get('date_range')},
            'basis_label': self._basis_label(filters),
            'kpis': self._get_kpis(filters),
            'purchase_amount_trend': self._get_purchase_amount_trend(filters),
            'status_breakdown': self._get_status_breakdown(filters),
            'vendor_summary': self._get_vendor_summary(filters),
            'product_summary': self._get_product_summary(filters),
            'category_summary': self._get_category_summary(filters),
            'buyer_summary': self._get_buyer_summary(filters) if settings.get('enable_buyer_analytics', True) else [],
            'receipt_status_summary': self._get_receipt_status_summary(filters) if settings.get('enable_receipt_matching', True) else {},
            'bill_status_summary': self._get_bill_status_summary(filters) if settings.get('enable_bill_matching', True) else {},
            'late_pos': self._get_late_pos(filters),
            'unfinished_pos': self._get_unfinished_pos(filters),
            'waiting_approval': self._get_waiting_approval(filters) if settings.get('enable_approval_analytics', True) else [],
            'price_change_alerts': self._get_price_change_alerts(filters) if settings.get('enable_price_trend_analytics', True) else [],
        }

    # ─── KPIs ─────────────────────────────────────────────────────

    @api.model
    def _get_kpis(self, filters):
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())

        self.env.cr.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE po.state IN ('draft','sent')) AS total_rfqs,
                COUNT(*) FILTER (WHERE po.state = 'sent') AS rfqs_sent,
                COUNT(*) FILTER (WHERE po.state = 'to approve') AS waiting_approval,
                COUNT(*) FILTER (WHERE po.state IN ('purchase','done')) AS approved_pos,
                COUNT(*) FILTER (WHERE po.state = 'cancel') AS cancelled,
                COALESCE(SUM(po.amount_total) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS total_purchase_amount,
                COALESCE(SUM(po.amount_untaxed) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS total_untaxed,
                COALESCE(SUM(po.amount_tax) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS total_tax,
                COALESCE(AVG(po.amount_total) FILTER (WHERE po.state IN ('purchase','done')), 0) AS avg_po_value
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              {extra}
        """, params)
        row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT
                COALESCE(SUM(pol.product_qty), 0) AS total_ordered_qty,
                COALESCE(SUM(pol.qty_received), 0) AS total_received_qty,
                COALESCE(SUM(pol.qty_invoiced), 0) AS total_billed_qty
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('cancel') {extra}
        """, params)
        lrow = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT COUNT(DISTINCT po.id) AS late_count
            FROM purchase_order po
            JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done')
              AND pol.qty_received < pol.product_qty
              AND pol.date_planned IS NOT NULL AND pol.date_planned::date < %(today)s
              {extra}
        """, {**params, 'today': today})
        late_row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT po.partner_id, rp.name AS vendor_name,
                   SUM(po.amount_total) AS total_amount
            FROM purchase_order po JOIN res_partner rp ON rp.id = po.partner_id
            WHERE po.company_id IN %(company_ids)s AND po.date_order >= %(date_start)s
              AND po.date_order <= %(date_end)s AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY po.partner_id, rp.name ORDER BY total_amount DESC LIMIT 1
        """, params)
        top_vendor = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT pol.product_id, pt.name AS product_name, SUM(pol.price_subtotal) AS total
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE po.company_id IN %(company_ids)s AND po.date_order >= %(date_start)s
              AND po.date_order <= %(date_end)s AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY pol.product_id, pt.name ORDER BY total DESC LIMIT 1
        """, params)
        top_product = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT pc.name AS category_name, SUM(pol.price_subtotal) AS total
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            WHERE po.company_id IN %(company_ids)s AND po.date_order >= %(date_start)s
              AND po.date_order <= %(date_end)s AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY pc.name ORDER BY total DESC LIMIT 1
        """, params)
        top_cat = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT rp.name AS buyer_name, SUM(po.amount_total) AS total
            FROM purchase_order po JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner rp ON rp.id = ru.partner_id
            WHERE po.company_id IN %(company_ids)s AND po.date_order >= %(date_start)s
              AND po.date_order <= %(date_end)s AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY rp.name ORDER BY total DESC LIMIT 1
        """, params)
        top_buyer = self.env.cr.dictfetchone() or {}

        self.env.cr.execute("""
            SELECT COALESCE(SUM(am.amount_total_signed), 0) AS billed,
                   COALESCE(SUM(am.amount_residual_signed), 0) AS residual
            FROM account_move am
            WHERE am.company_id IN %(company_ids)s AND am.move_type = 'in_invoice'
              AND am.state = 'posted'
              AND am.invoice_date >= %(date_start)s::date AND am.invoice_date <= %(date_end)s::date
        """, params)
        bill_row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute("""
            SELECT MIN(po.date_order) AS oldest FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s AND po.state = 'to approve'
        """, params)
        oldest_approval = (self.env.cr.dictfetchone() or {}).get('oldest')

        self.env.cr.execute("""
            SELECT MIN(po.date_order) AS oldest FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s AND po.state IN ('draft','sent')
        """, params)
        oldest_rfq = (self.env.cr.dictfetchone() or {}).get('oldest')

        def days_since(dt):
            if not dt:
                return None
            d = dt.date() if hasattr(dt, 'date') else dt
            return (today - d).days

        total_purchase = float(row.get('total_purchase_amount') or 0)
        billed_amount = abs(float(bill_row.get('billed') or 0))
        return {
            'total_rfqs': int(row.get('total_rfqs') or 0),
            'rfqs_sent': int(row.get('rfqs_sent') or 0),
            'waiting_approval': int(row.get('waiting_approval') or 0),
            'approved_pos': int(row.get('approved_pos') or 0),
            'cancelled': int(row.get('cancelled') or 0),
            'total_purchase_amount': total_purchase,
            'total_untaxed': float(row.get('total_untaxed') or 0),
            'total_tax': float(row.get('total_tax') or 0),
            'avg_po_value': float(row.get('avg_po_value') or 0),
            'total_ordered_qty': float(lrow.get('total_ordered_qty') or 0),
            'total_received_qty': float(lrow.get('total_received_qty') or 0),
            'pending_receipt_qty': max(0, float(lrow.get('total_ordered_qty') or 0) - float(lrow.get('total_received_qty') or 0)),
            'billed_amount': billed_amount,
            'unbilled_amount': max(0, total_purchase - billed_amount),
            'late_po_count': int(late_row.get('late_count') or 0),
            'top_vendor': top_vendor.get('vendor_name', ''),
            'top_vendor_amount': float(top_vendor.get('total_amount') or 0),
            'top_product': top_product.get('product_name', ''),
            'top_category': top_cat.get('category_name', ''),
            'top_buyer': top_buyer.get('buyer_name', ''),
            'oldest_pending_rfq_days': days_since(oldest_rfq),
            'oldest_waiting_approval_days': days_since(oldest_approval),
        }

    # ─── TREND ────────────────────────────────────────────────────

    @api.model
    def _get_purchase_amount_trend(self, filters):
        params, extra = self._base_po_params(filters)
        trunc = {'day': 'day', 'week': 'week', 'month': 'month', 'year': 'year'}.get(filters.get('group_by', 'month'), 'month')
        self.env.cr.execute(f"""
            SELECT DATE_TRUNC('{trunc}', po.date_order)::date AS period,
                   COALESCE(SUM(po.amount_total), 0) AS purchase_amount,
                   COALESCE(SUM(po.amount_untaxed), 0) AS untaxed_amount,
                   COUNT(*) AS po_count
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY period ORDER BY period
        """, params)
        return [{'period': str(r['period']), 'purchase_amount': float(r['purchase_amount'] or 0),
                 'untaxed_amount': float(r['untaxed_amount'] or 0), 'po_count': int(r['po_count'] or 0)}
                for r in self.env.cr.dictfetchall()]

    # ─── STATUS BREAKDOWN ─────────────────────────────────────────

    @api.model
    def _get_status_breakdown(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.state, COUNT(*) AS count, COALESCE(SUM(po.amount_total), 0) AS total_amount
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY po.state
        """, params)
        labels = {'draft': 'Draft RFQ', 'sent': 'RFQ Sent', 'to approve': 'Waiting Approval',
                  'purchase': 'Purchase Order', 'done': 'Done', 'cancel': 'Cancelled'}
        return [{'state': r['state'], 'label': labels.get(r['state'], r['state']),
                 'count': int(r['count'] or 0), 'total_amount': float(r['total_amount'] or 0)}
                for r in self.env.cr.dictfetchall()]

    # ─── VENDOR SUMMARY ───────────────────────────────────────────

    @api.model
    def _get_vendor_summary(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.partner_id AS vendor_id, rp.name AS vendor_name,
                   COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('draft','sent')) AS rfq_count,
                   COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('purchase','done')) AS po_count,
                   COALESCE(SUM(po.amount_total) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS total_amount,
                   COALESCE(SUM(po.amount_untaxed) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS untaxed_amount,
                   COALESCE(AVG(po.amount_total) FILTER (WHERE po.state IN ('purchase','done')), 0) AS avg_po_value,
                   MAX(po.date_order) AS last_purchase_date
            FROM purchase_order po JOIN res_partner rp ON rp.id = po.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY po.partner_id, rp.name ORDER BY total_amount DESC LIMIT 20
        """, params)
        return [{'vendor_id': r['vendor_id'], 'vendor_name': r['vendor_name'],
                 'rfq_count': int(r['rfq_count'] or 0), 'po_count': int(r['po_count'] or 0),
                 'total_amount': float(r['total_amount'] or 0), 'untaxed_amount': float(r['untaxed_amount'] or 0),
                 'avg_po_value': float(r['avg_po_value'] or 0),
                 'last_purchase_date': str(r['last_purchase_date']) if r['last_purchase_date'] else ''}
                for r in self.env.cr.dictfetchall()]

    # ─── PRODUCT / CATEGORY / BUYER SUMMARIES ─────────────────────

    @api.model
    def _get_product_summary(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT pol.product_id, pt.name AS product_name, pc.name AS category_name,
                   COALESCE(SUM(pol.product_qty), 0) AS ordered_qty,
                   COALESCE(SUM(pol.qty_received), 0) AS received_qty,
                   COALESCE(SUM(pol.qty_invoiced), 0) AS billed_qty,
                   COALESCE(SUM(pol.price_subtotal), 0) AS total_amount,
                   COALESCE(AVG(pol.price_unit), 0) AS avg_price,
                   MIN(pol.price_unit) AS min_price, MAX(pol.price_unit) AS max_price,
                   COUNT(DISTINCT pol.order_id) AS po_count,
                   MAX(po.date_order) AS last_purchase_date
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY pol.product_id, pt.name, pc.name ORDER BY total_amount DESC LIMIT 30
        """, params)
        result = []
        for r in self.env.cr.dictfetchall():
            ordered = float(r['ordered_qty'] or 0)
            received = float(r['received_qty'] or 0)
            result.append({
                'product_id': r['product_id'], 'product_name': r['product_name'],
                'category_name': r['category_name'], 'ordered_qty': ordered,
                'received_qty': received, 'pending_qty': max(0, ordered - received),
                'billed_qty': float(r['billed_qty'] or 0), 'total_amount': float(r['total_amount'] or 0),
                'avg_price': float(r['avg_price'] or 0), 'min_price': float(r['min_price'] or 0),
                'max_price': float(r['max_price'] or 0), 'last_price': float(r['max_price'] or 0),
                'po_count': int(r['po_count'] or 0),
                'last_purchase_date': str(r['last_purchase_date']) if r['last_purchase_date'] else '',
            })
        return result

    @api.model
    def _get_category_summary(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT pc.id AS category_id, pc.name AS category_name,
                   COALESCE(SUM(pol.price_subtotal), 0) AS total_amount,
                   COALESCE(SUM(pol.product_qty), 0) AS ordered_qty,
                   COUNT(DISTINCT pol.order_id) AS po_count
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY pc.id, pc.name ORDER BY total_amount DESC LIMIT 20
        """, params)
        return [{'category_id': r['category_id'], 'category_name': r['category_name'],
                 'total_amount': float(r['total_amount'] or 0), 'ordered_qty': float(r['ordered_qty'] or 0),
                 'po_count': int(r['po_count'] or 0)} for r in self.env.cr.dictfetchall()]

    @api.model
    def _get_buyer_summary(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.user_id AS buyer_id, rp.name AS buyer_name,
                   COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('purchase','done')) AS po_count,
                   COUNT(DISTINCT po.id) FILTER (WHERE po.state = 'to approve') AS waiting_count,
                   COALESCE(SUM(po.amount_total) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS total_amount
            FROM purchase_order po JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner rp ON rp.id = ru.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY po.user_id, rp.name ORDER BY total_amount DESC LIMIT 20
        """, params)
        return [{'buyer_id': r['buyer_id'], 'buyer_name': r['buyer_name'],
                 'po_count': int(r['po_count'] or 0), 'waiting_count': int(r['waiting_count'] or 0),
                 'total_amount': float(r['total_amount'] or 0)} for r in self.env.cr.dictfetchall()]

    @api.model
    def _get_receipt_status_summary(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT COALESCE(SUM(pol.product_qty), 0) AS total_ordered,
                   COALESCE(SUM(pol.qty_received), 0) AS total_received,
                   COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_received = 0 AND pol.product_qty > 0) AS not_received_pos,
                   COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_received > 0 AND pol.qty_received < pol.product_qty) AS partial_pos,
                   COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_received >= pol.product_qty AND pol.product_qty > 0) AS fully_received_pos
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done') {extra}
        """, params)
        r = self.env.cr.dictfetchone() or {}
        total_ordered = float(r.get('total_ordered') or 0)
        total_received = float(r.get('total_received') or 0)
        return {
            'total_ordered': total_ordered, 'total_received': total_received,
            'pending_qty': max(0, total_ordered - total_received),
            'not_received_pos': int(r.get('not_received_pos') or 0),
            'partial_pos': int(r.get('partial_pos') or 0),
            'fully_received_pos': int(r.get('fully_received_pos') or 0),
        }

    @api.model
    def _get_bill_status_summary(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT COALESCE(SUM(pol.qty_invoiced), 0) AS total_billed_qty,
                   COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_invoiced = 0) AS not_billed_pos,
                   COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_invoiced > 0 AND pol.qty_invoiced < pol.product_qty) AS partial_pos,
                   COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_invoiced >= pol.product_qty AND pol.product_qty > 0) AS fully_billed_pos
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done') {extra}
        """, params)
        r = self.env.cr.dictfetchone() or {}
        return {
            'total_billed_qty': float(r.get('total_billed_qty') or 0),
            'not_billed_pos': int(r.get('not_billed_pos') or 0),
            'partial_pos': int(r.get('partial_pos') or 0),
            'fully_billed_pos': int(r.get('fully_billed_pos') or 0),
        }

    # ─── LATE / UNFINISHED / WAITING ──────────────────────────────

    @api.model
    def _get_late_pos(self, filters):
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())
        self.env.cr.execute(f"""
            SELECT po.id, po.name AS po_ref, po.state,
                   rp.name AS vendor_name, ru_p.name AS buyer_name,
                   COALESCE(SUM(pol.product_qty), 0) AS ordered_qty,
                   COALESCE(SUM(pol.qty_received), 0) AS received_qty,
                   COALESCE(SUM(pol.product_qty) - SUM(pol.qty_received), 0) AS pending_qty,
                   MIN(pol.date_planned)::date AS expected_date,
                   (%(today)s - MIN(pol.date_planned)::date) AS late_days,
                   po.amount_total
            FROM purchase_order po
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done')
              AND pol.qty_received < pol.product_qty
              AND pol.date_planned IS NOT NULL AND pol.date_planned::date < %(today)s {extra}
            GROUP BY po.id, po.name, po.state, rp.name, ru_p.name, po.amount_total
            ORDER BY late_days DESC LIMIT 50
        """, {**params, 'today': today})
        return [{'id': r['id'], 'po_ref': r['po_ref'], 'state': r['state'],
                 'vendor_name': r['vendor_name'], 'buyer_name': r['buyer_name'],
                 'ordered_qty': float(r['ordered_qty'] or 0), 'received_qty': float(r['received_qty'] or 0),
                 'pending_qty': float(r['pending_qty'] or 0),
                 'expected_date': str(r['expected_date']) if r['expected_date'] else '',
                 'late_days': int(r['late_days'] or 0), 'amount_total': float(r['amount_total'] or 0)}
                for r in self.env.cr.dictfetchall()]

    @api.model
    def _get_unfinished_pos(self, filters):
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())
        self.env.cr.execute(f"""
            SELECT po.id, po.name AS po_ref, po.state,
                   rp.name AS vendor_name, ru_p.name AS buyer_name, po.date_order,
                   COALESCE(SUM(pol.product_qty) - SUM(pol.qty_received), 0) AS pending_qty,
                   COALESCE(SUM((pol.product_qty - pol.qty_invoiced) * pol.price_unit), 0) AS unbilled_amount,
                   po.amount_total
            FROM purchase_order po
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('cancel')
              AND (po.state IN ('draft','sent','to approve')
                   OR pol.qty_received < pol.product_qty
                   OR pol.qty_invoiced < pol.product_qty) {extra}
            GROUP BY po.id, po.name, po.state, rp.name, ru_p.name, po.date_order, po.amount_total
            ORDER BY po.date_order LIMIT 50
        """, params)
        result = []
        for r in self.env.cr.dictfetchall():
            order_dt = r['date_order']
            order_d = order_dt.date() if hasattr(order_dt, 'date') else order_dt
            result.append({
                'id': r['id'], 'po_ref': r['po_ref'], 'state': r['state'],
                'vendor_name': r['vendor_name'], 'buyer_name': r['buyer_name'],
                'pending_qty': float(r['pending_qty'] or 0),
                'unbilled_amount': float(r['unbilled_amount'] or 0),
                'amount_total': float(r['amount_total'] or 0),
                'age_days': (today - order_d).days if order_d else 0,
            })
        return result

    @api.model
    def _get_waiting_approval(self, filters):
        params, _ = self._base_po_params(filters)
        self.env.cr.execute("""
            SELECT po.id, po.name AS po_ref, po.state,
                   rp.name AS vendor_name, ru_p.name AS buyer_name, po.date_order,
                   po.amount_total,
                   CURRENT_DATE - po.date_order::date AS days_waiting
            FROM purchase_order po
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            WHERE po.company_id IN %(company_ids)s AND po.state = 'to approve'
            ORDER BY days_waiting DESC LIMIT 50
        """, params)
        return [{'id': r['id'], 'po_ref': r['po_ref'], 'state': r['state'],
                 'vendor_name': r['vendor_name'], 'buyer_name': r['buyer_name'],
                 'order_date': str(r['date_order'].date()) if r['date_order'] else '',
                 'amount_total': float(r['amount_total'] or 0),
                 'days_waiting': int(r['days_waiting'] or 0)}
                for r in self.env.cr.dictfetchall()]

    # ─── PRICE CHANGE ALERTS ──────────────────────────────────────

    @api.model
    def _get_price_change_alerts(self, filters):
        params, _ = self._base_po_params(filters)
        settings = filters.get('settings', {})
        threshold = settings.get('price_increase_threshold_percentage', 5.0) / 100.0
        params['threshold'] = threshold
        self.env.cr.execute("""
            WITH ranked AS (
                SELECT pol.product_id, pt.name AS product_name,
                       po.partner_id AS vendor_id, rp.name AS vendor_name,
                       pol.price_unit, po.date_order,
                       ROW_NUMBER() OVER (PARTITION BY pol.product_id, po.partner_id ORDER BY po.date_order DESC) AS rn
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                JOIN product_product pp ON pp.id = pol.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                JOIN res_partner rp ON rp.id = po.partner_id
                WHERE po.company_id IN %(company_ids)s AND po.state IN ('purchase','done')
            )
            SELECT l.product_id, l.product_name, l.vendor_id, l.vendor_name,
                   p.price_unit AS prev_price, l.price_unit AS latest_price,
                   l.price_unit - p.price_unit AS price_change,
                   CASE WHEN p.price_unit > 0 THEN (l.price_unit - p.price_unit)/p.price_unit ELSE 0 END AS pct_change,
                   l.date_order AS last_purchase_date
            FROM ranked l JOIN ranked p ON p.product_id = l.product_id AND p.vendor_id = l.vendor_id AND p.rn = 2
            WHERE l.rn = 1 AND l.price_unit > p.price_unit AND p.price_unit > 0
              AND (l.price_unit - p.price_unit)/p.price_unit >= %(threshold)s
            ORDER BY pct_change DESC LIMIT 30
        """, params)
        return [{'product_id': r['product_id'], 'product_name': r['product_name'],
                 'vendor_id': r['vendor_id'], 'vendor_name': r['vendor_name'],
                 'prev_price': float(r['prev_price'] or 0), 'latest_price': float(r['latest_price'] or 0),
                 'price_change': float(r['price_change'] or 0), 'pct_change': float(r['pct_change'] or 0),
                 'last_purchase_date': str(r['last_purchase_date'].date()) if r['last_purchase_date'] else ''}
                for r in self.env.cr.dictfetchall()]

    # ─── PURCHASE REQUEST ANALYSIS ────────────────────────────────

    @api.model
    def get_purchase_request_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_purchase_request_analytics', True):
            return {'disabled': True, 'message': 'Purchase Request Analytics is disabled in settings.'}

        if self._has_purchase_request_model():
            return self._get_native_purchase_request_analysis(filters)
        return self._get_inferred_purchase_request_analysis(filters)

    def _get_native_purchase_request_analysis(self, filters):
        company_ids = filters.get('company_ids', [self.env.company.id])
        date_start = filters.get('date_start')
        date_end = filters.get('date_end')
        domain = [('company_id', 'in', company_ids)]
        if date_start:
            domain += [('date_start', '>=', str(date_start))]
        if date_end:
            domain += [('date_start', '<=', str(date_end))]
        try:
            requests = self.env['purchase.request'].search(domain, limit=500)
            total = len(requests)
            state_counts = {}
            for req in requests:
                s = getattr(req, 'state', 'unknown')
                state_counts[s] = state_counts.get(s, 0) + 1
            kpis = {
                'total_requests': total,
                'draft': state_counts.get('draft', 0),
                'pending': state_counts.get('to_approve', state_counts.get('pending', 0)),
                'approved': state_counts.get('approved', 0),
                'rejected': state_counts.get('rejected', state_counts.get('cancel', 0)),
            }
            status_breakdown = [{'status': k, 'count': v, 'amount': 0} for k, v in state_counts.items()]
            return {'kpis': kpis, 'status_breakdown': status_breakdown, 'product_breakdown': [],
                    'fallback_message': None, 'has_native_model': True}
        except Exception as e:
            _logger.warning("Error reading purchase.request model: %s", e)
            return self._get_inferred_purchase_request_analysis(filters)

    @api.model
    def _get_inferred_purchase_request_analysis(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.state, COUNT(*) AS count, COALESCE(SUM(po.amount_total), 0) AS amount
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY po.state
        """, params)
        rows = self.env.cr.dictfetchall()
        total = sum(r['count'] for r in rows)
        labels = {'draft': 'Draft RFQ', 'sent': 'RFQ Sent', 'to approve': 'Waiting Approval',
                  'purchase': 'Purchase Order', 'done': 'Done', 'cancel': 'Cancelled'}
        status_breakdown = [{'status': labels.get(r['state'], r['state']), 'count': int(r['count'] or 0),
                              'amount': float(r['amount'] or 0)} for r in rows]
        kpis = {'total_requests': total, 'note': 'Inferred from purchase orders and RFQs'}
        return {
            'kpis': kpis, 'status_breakdown': status_breakdown, 'product_breakdown': [],
            'fallback_message': 'Purchase Request model not installed. Showing inferred request analysis from RFQs and Purchase Orders.',
            'has_native_model': False,
        }

    # ─── RFQ ANALYSIS ─────────────────────────────────────────────

    @api.model
    def get_rfq_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_rfq_analytics', True):
            return {'disabled': True}
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())

        self.env.cr.execute(f"""
            SELECT
                COUNT(*) AS total_rfqs,
                COUNT(*) FILTER (WHERE po.state = 'draft') AS draft_rfqs,
                COUNT(*) FILTER (WHERE po.state = 'sent') AS sent_rfqs,
                COUNT(*) FILTER (WHERE po.state = 'cancel') AS cancelled_rfqs,
                COALESCE(SUM(po.amount_total) FILTER (WHERE po.state IN ('draft','sent')), 0) AS estimated_amount,
                MIN(po.date_order) FILTER (WHERE po.state IN ('draft','sent')) AS oldest_rfq_date
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('draft','sent','cancel') {extra}
        """, params)
        row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT po.id, po.name AS po_ref, po.state, rp.name AS vendor_name,
                   ru_p.name AS buyer_name, po.date_order::date AS order_date,
                   po.date_planned::date AS expected_date,
                   COUNT(pol.id) AS product_count, COALESCE(SUM(pol.product_qty), 0) AS total_qty,
                   COALESCE(SUM(pol.price_subtotal), 0) AS estimated_amount,
                   (%(today)s - po.date_order::date) AS days_since_created,
                   po.origin
            FROM purchase_order po
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            LEFT JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('draft','sent') {extra}
            GROUP BY po.id, po.name, po.state, rp.name, ru_p.name, po.date_order,
                     po.date_planned, po.origin
            ORDER BY po.date_order DESC LIMIT 100
        """, {**params, 'today': today})
        raw_rfqs = []
        for r in self.env.cr.dictfetchall():
            raw_rfqs.append({
                'id': r['id'], 'po_ref': r['po_ref'], 'state': r['state'],
                'vendor_name': r['vendor_name'], 'buyer_name': r['buyer_name'],
                'order_date': str(r['order_date']) if r['order_date'] else '',
                'expected_date': str(r['expected_date']) if r['expected_date'] else '',
                'product_count': int(r['product_count'] or 0),
                'total_qty': float(r['total_qty'] or 0),
                'estimated_amount': float(r['estimated_amount'] or 0),
                'days_since_created': int(r['days_since_created'] or 0),
                'origin': r['origin'] or '',
            })

        oldest = row.get('oldest_rfq_date')
        kpis = {
            'total_rfqs': int(row.get('total_rfqs') or 0),
            'draft_rfqs': int(row.get('draft_rfqs') or 0),
            'sent_rfqs': int(row.get('sent_rfqs') or 0),
            'cancelled_rfqs': int(row.get('cancelled_rfqs') or 0),
            'estimated_amount': float(row.get('estimated_amount') or 0),
            'oldest_rfq_days': (today - (oldest.date() if hasattr(oldest, 'date') else oldest)).days if oldest else None,
        }
        return {'kpis': kpis, 'raw_rfqs': raw_rfqs}

    # ─── PURCHASE ORDER ANALYSIS ──────────────────────────────────

    @api.model
    def get_purchase_order_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_purchase_order_analytics', True):
            return {'disabled': True}
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())

        self.env.cr.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE po.state = 'to approve') AS waiting_approval,
                COUNT(*) FILTER (WHERE po.state IN ('purchase','done')) AS approved_pos,
                COUNT(*) FILTER (WHERE po.state = 'done') AS done_pos,
                COUNT(*) FILTER (WHERE po.state = 'cancel') AS cancelled,
                COUNT(*) FILTER (WHERE po.state NOT IN ('cancel')) AS total_pos,
                COALESCE(SUM(po.amount_total) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS total_amount,
                COALESCE(AVG(po.amount_total) FILTER (WHERE po.state IN ('purchase','done')), 0) AS avg_amount
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
        """, params)
        row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT COALESCE(SUM(pol.product_qty), 0) AS ordered_qty,
                   COALESCE(SUM(pol.qty_received), 0) AS received_qty
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('cancel') {extra}
        """, params)
        lrow = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT COUNT(DISTINCT po.id) AS late_count
            FROM purchase_order po JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done')
              AND pol.qty_received < pol.product_qty
              AND pol.date_planned IS NOT NULL AND pol.date_planned::date < %(today)s {extra}
        """, {**params, 'today': today})
        late_row = self.env.cr.dictfetchone() or {}

        vendor_breakdown = self._get_vendor_summary(filters)
        buyer_summary = self._get_buyer_summary(filters)

        self.env.cr.execute(f"""
            SELECT po.id, po.name AS po_ref, po.state, rp.name AS vendor_name,
                   ru_p.name AS buyer_name, po.date_order::date AS order_date,
                   po.date_planned::date AS expected_date,
                   COUNT(pol.id) AS product_count,
                   COALESCE(SUM(pol.product_qty), 0) AS ordered_qty,
                   COALESCE(SUM(pol.qty_received), 0) AS received_qty,
                   po.amount_untaxed, po.amount_tax, po.amount_total, po.origin
            FROM purchase_order po
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            LEFT JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state NOT IN ('draft','cancel') {extra}
            GROUP BY po.id, po.name, po.state, rp.name, ru_p.name, po.date_order,
                     po.date_planned, po.amount_untaxed, po.amount_tax, po.amount_total, po.origin
            ORDER BY po.date_order DESC LIMIT 200
        """, params)
        raw_pos = []
        for r in self.env.cr.dictfetchall():
            raw_pos.append({
                'id': r['id'], 'po_ref': r['po_ref'], 'state': r['state'],
                'vendor_name': r['vendor_name'], 'buyer_name': r['buyer_name'],
                'order_date': str(r['order_date']) if r['order_date'] else '',
                'expected_date': str(r['expected_date']) if r['expected_date'] else '',
                'product_count': int(r['product_count'] or 0),
                'ordered_qty': float(r['ordered_qty'] or 0),
                'received_qty': float(r['received_qty'] or 0),
                'amount_untaxed': float(r['amount_untaxed'] or 0),
                'amount_tax': float(r['amount_tax'] or 0),
                'amount_total': float(r['amount_total'] or 0),
                'origin': r['origin'] or '',
            })

        total_ord = float(lrow.get('ordered_qty') or 0)
        total_rec = float(lrow.get('received_qty') or 0)
        kpis = {
            'waiting_approval': int(row.get('waiting_approval') or 0),
            'approved_pos': int(row.get('approved_pos') or 0),
            'done_pos': int(row.get('done_pos') or 0),
            'cancelled': int(row.get('cancelled') or 0),
            'total_pos': int(row.get('total_pos') or 0),
            'total_amount': float(row.get('total_amount') or 0),
            'avg_amount': float(row.get('avg_amount') or 0),
            'total_ordered_qty': total_ord,
            'total_received_qty': total_rec,
            'pending_qty': max(0, total_ord - total_rec),
            'late_count': int(late_row.get('late_count') or 0),
        }
        return {'kpis': kpis, 'vendor_breakdown': vendor_breakdown,
                'buyer_summary': buyer_summary, 'raw_pos': raw_pos}

    # ─── VENDOR ANALYSIS ──────────────────────────────────────────

    @api.model
    def get_vendor_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_vendor_analytics', True):
            return {'disabled': True}
        vendor_summary = self._get_vendor_summary(filters)
        scorecards = self._get_vendor_scorecard_rows(filters)
        return {'vendor_summary': vendor_summary, 'scorecards': scorecards,
                'kpis': {'total_vendors': len(vendor_summary)}}

    @api.model
    def _get_vendor_scorecard_rows(self, filters):
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())
        self.env.cr.execute(f"""
            SELECT
                po.partner_id AS vendor_id, rp.name AS vendor_name,
                COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('purchase','done')) AS po_count,
                COALESCE(SUM(po.amount_total) FILTER (WHERE po.state IN ('purchase','done')), 0) AS total_amount,
                COUNT(DISTINCT po.id) FILTER (
                    WHERE po.state IN ('purchase','done')
                    AND EXISTS (
                        SELECT 1 FROM purchase_order_line pol2
                        WHERE pol2.order_id = po.id AND pol2.qty_received < pol2.product_qty
                        AND pol2.date_planned IS NOT NULL AND pol2.date_planned::date < %(today)s
                    )
                ) AS late_count,
                COUNT(DISTINCT po.id) FILTER (WHERE po.state = 'cancel') AS cancelled_count,
                COALESCE(AVG(
                    CASE WHEN po.state IN ('purchase','done') AND po.date_planned IS NOT NULL AND po.date_order IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (po.date_planned - po.date_order))/86400.0 END
                ), 0) AS avg_lead_time
            FROM purchase_order po JOIN res_partner rp ON rp.id = po.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY po.partner_id, rp.name
            HAVING COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('purchase','done')) > 0
            ORDER BY total_amount DESC LIMIT 50
        """, {**params, 'today': today})
        rows = self.env.cr.dictfetchall()
        result = []
        for r in rows:
            po_count = int(r['po_count'] or 0)
            late_count = int(r['late_count'] or 0)
            on_time_pct = ((po_count - late_count) / po_count * 100) if po_count > 0 else 100.0
            price_stability_score = max(0, 100 - (r.get('price_instability', 0) or 0))
            completion_score = on_time_pct
            overall_score = round((on_time_pct * 0.4) + (price_stability_score * 0.3) + (completion_score * 0.3), 1)
            result.append({
                'vendor_id': r['vendor_id'], 'vendor_name': r['vendor_name'],
                'po_count': po_count, 'total_amount': float(r['total_amount'] or 0),
                'on_time_pct': round(on_time_pct, 1), 'late_count': late_count,
                'avg_lead_time': round(float(r['avg_lead_time'] or 0), 1),
                'cancelled_count': int(r['cancelled_count'] or 0),
                'price_stability_score': round(price_stability_score, 1),
                'completion_score': round(completion_score, 1),
                'overall_score': overall_score,
            })
        return result

    # ─── PRODUCT PURCHASE ANALYSIS ────────────────────────────────

    @api.model
    def get_product_purchase_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        product_rows = self._get_product_summary(filters)
        category_summary = self._get_category_summary(filters)
        # compute price change pct for each product row
        for row in product_rows:
            row['price_change_pct'] = 0.0
        kpis = {
            'total_products': len(product_rows),
            'total_categories': len(category_summary),
            'top_product': product_rows[0]['product_name'] if product_rows else '',
            'top_category': category_summary[0]['category_name'] if category_summary else '',
        }
        return {'kpis': kpis, 'product_rows': product_rows, 'category_summary': category_summary}

    # ─── RECEIPT MATCHING ─────────────────────────────────────────

    @api.model
    def get_receipt_matching(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_receipt_matching', True):
            return {'disabled': True}
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())

        self.env.cr.execute(f"""
            SELECT
                COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_received < pol.product_qty AND po.state IN ('purchase','done')) AS waiting_receipt,
                COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_received > 0 AND pol.qty_received < pol.product_qty AND po.state IN ('purchase','done')) AS partial_receipt,
                COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_received >= pol.product_qty AND pol.product_qty > 0 AND po.state IN ('purchase','done')) AS fully_received,
                COALESCE(SUM(pol.product_qty - pol.qty_received) FILTER (WHERE po.state IN ('purchase','done')), 0) AS pending_qty,
                COALESCE(SUM(pol.qty_received), 0) AS received_qty
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
        """, params)
        kpi_row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT po.id AS po_id, po.name AS po_ref, rp.name AS vendor_name,
                   sp.name AS receipt_ref, sp.state AS receipt_state,
                   sp.scheduled_date::date AS expected_date, sp.date_done::date AS receipt_date,
                   sw.name AS warehouse_name,
                   COALESCE(SUM(sm.product_uom_qty), 0) AS ordered_qty,
                   COALESCE(SUM(sm.quantity_done), 0) AS received_qty,
                   COALESCE(SUM(sm.product_uom_qty) - SUM(sm.quantity_done), 0) AS pending_qty,
                   CASE WHEN sp.scheduled_date IS NOT NULL AND sp.date_done IS NULL
                        THEN %(today)s - sp.scheduled_date::date
                        ELSE 0 END AS late_days,
                   po.state AS po_state
            FROM purchase_order po
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN stock_picking sp ON sp.purchase_id = po.id
            JOIN stock_move sm ON sm.picking_id = sp.id
            LEFT JOIN stock_warehouse sw ON sw.lot_stock_id = sp.location_dest_id OR sw.id IN (
                SELECT wh.id FROM stock_warehouse wh WHERE wh.company_id = po.company_id LIMIT 1
            )
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND sp.state NOT IN ('cancel') {extra}
            GROUP BY po.id, po.name, rp.name, sp.name, sp.state, sp.scheduled_date,
                     sp.date_done, sw.name, po.state
            ORDER BY late_days DESC LIMIT 100
        """, {**params, 'today': today})
        receipt_rows = []
        for r in self.env.cr.dictfetchall():
            receipt_rows.append({
                'po_id': r['po_id'], 'po_ref': r['po_ref'], 'vendor_name': r['vendor_name'],
                'receipt_ref': r['receipt_ref'] or '', 'receipt_state': r['receipt_state'] or '',
                'expected_date': str(r['expected_date']) if r['expected_date'] else '',
                'receipt_date': str(r['receipt_date']) if r['receipt_date'] else '',
                'warehouse_name': r['warehouse_name'] or '',
                'ordered_qty': float(r['ordered_qty'] or 0), 'received_qty': float(r['received_qty'] or 0),
                'pending_qty': float(r['pending_qty'] or 0), 'late_days': int(r['late_days'] or 0),
                'po_state': r['po_state'],
            })

        unreceived_products = self._get_unreceived_products(filters)
        kpis = {
            'waiting_receipt': int(kpi_row.get('waiting_receipt') or 0),
            'partial_receipt': int(kpi_row.get('partial_receipt') or 0),
            'fully_received': int(kpi_row.get('fully_received') or 0),
            'pending_qty': float(kpi_row.get('pending_qty') or 0),
            'received_qty': float(kpi_row.get('received_qty') or 0),
        }
        return {'kpis': kpis, 'receipt_rows': receipt_rows, 'unreceived_products': unreceived_products}

    @api.model
    def _get_unreceived_products(self, filters):
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())
        self.env.cr.execute(f"""
            SELECT pol.product_id, pt.name AS product_name, pc.name AS category_name,
                   rp.name AS vendor_name, po.name AS po_ref,
                   pol.product_qty AS ordered_qty, pol.qty_received AS received_qty,
                   pol.product_qty - pol.qty_received AS pending_qty,
                   pol.date_planned::date AS expected_date,
                   CASE WHEN pol.date_planned IS NOT NULL
                        THEN %(today)s - pol.date_planned::date ELSE 0 END AS late_days
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            JOIN res_partner rp ON rp.id = po.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done')
              AND pol.qty_received < pol.product_qty
              AND pt.type IN ('product','consu') {extra}
            ORDER BY late_days DESC LIMIT 100
        """, {**params, 'today': today})
        return [{'product_id': r['product_id'], 'product_name': r['product_name'],
                 'category_name': r['category_name'], 'vendor_name': r['vendor_name'],
                 'po_ref': r['po_ref'], 'ordered_qty': float(r['ordered_qty'] or 0),
                 'received_qty': float(r['received_qty'] or 0), 'pending_qty': float(r['pending_qty'] or 0),
                 'expected_date': str(r['expected_date']) if r['expected_date'] else '',
                 'late_days': int(r['late_days'] or 0)} for r in self.env.cr.dictfetchall()]

    # ─── BILL MATCHING ────────────────────────────────────────────

    @api.model
    def get_bill_matching(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_bill_matching', True):
            return {'disabled': True}
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())

        self.env.cr.execute(f"""
            SELECT
                COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_invoiced = 0 AND po.state IN ('purchase','done')) AS not_billed,
                COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_invoiced > 0 AND pol.qty_invoiced < pol.product_qty) AS partial_billed,
                COUNT(DISTINCT po.id) FILTER (WHERE pol.qty_invoiced >= pol.product_qty AND pol.product_qty > 0) AS fully_billed
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
        """, params)
        kpi_row = self.env.cr.dictfetchone() or {}

        self.env.cr.execute(f"""
            SELECT am.id AS bill_id, am.name AS bill_ref, rp.name AS vendor_name,
                   am.invoice_date, am.invoice_date_due,
                   am.state AS bill_state, am.payment_state,
                   am.amount_total, am.amount_residual,
                   po.name AS po_ref, po.amount_total AS po_total
            FROM account_move am
            JOIN res_partner rp ON rp.id = am.partner_id
            LEFT JOIN purchase_order_invoice_rel poir ON poir.invoice_id = am.id
            LEFT JOIN purchase_order po ON po.id = poir.purchase_id
            WHERE am.company_id IN %(company_ids)s
              AND am.move_type = 'in_invoice'
              AND am.state != 'cancel'
              AND am.invoice_date >= %(date_start)s::date
              AND am.invoice_date <= %(date_end)s::date
            ORDER BY am.invoice_date DESC LIMIT 100
        """, params)
        bill_rows = []
        for r in self.env.cr.dictfetchall():
            due_date = r['invoice_date_due']
            is_overdue = due_date and r['payment_state'] not in ('paid',) and due_date < today
            bill_rows.append({
                'bill_id': r['bill_id'], 'bill_ref': r['bill_ref'] or '',
                'vendor_name': r['vendor_name'], 'po_ref': r['po_ref'] or '',
                'invoice_date': str(r['invoice_date']) if r['invoice_date'] else '',
                'due_date': str(due_date) if due_date else '',
                'bill_state': r['bill_state'], 'payment_state': r['payment_state'] or '',
                'amount_total': abs(float(r['amount_total'] or 0)),
                'amount_residual': abs(float(r['amount_residual'] or 0)),
                'po_total': float(r['po_total'] or 0),
                'is_overdue': bool(is_overdue),
            })

        unbilled_rows = self._get_unbilled_pos(filters)
        am_params = dict(params)
        self.env.cr.execute("""
            SELECT am.state, am.payment_state, COUNT(*) AS count, COALESCE(SUM(am.amount_total), 0) AS total
            FROM account_move am
            WHERE am.company_id IN %(company_ids)s AND am.move_type = 'in_invoice'
              AND am.state != 'cancel'
              AND am.invoice_date >= %(date_start)s::date AND am.invoice_date <= %(date_end)s::date
            GROUP BY am.state, am.payment_state
        """, am_params)
        bill_status_summary = self.env.cr.dictfetchall()

        kpis = {
            'not_billed': int(kpi_row.get('not_billed') or 0),
            'partial_billed': int(kpi_row.get('partial_billed') or 0),
            'fully_billed': int(kpi_row.get('fully_billed') or 0),
            'overdue_bills': sum(1 for b in bill_rows if b['is_overdue']),
        }
        return {'kpis': kpis, 'bill_rows': bill_rows,
                'unbilled_rows': unbilled_rows, 'bill_status_summary': bill_status_summary}

    @api.model
    def _get_unbilled_pos(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.name AS po_ref, rp.name AS vendor_name,
                   COALESCE(SUM(pol.price_subtotal), 0) AS po_subtotal,
                   COALESCE(SUM(pol.qty_invoiced * pol.price_unit), 0) AS billed_amount,
                   COALESCE(SUM((pol.product_qty - pol.qty_invoiced) * pol.price_unit), 0) AS unbilled_amount
            FROM purchase_order po JOIN res_partner rp ON rp.id = po.partner_id
            JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done')
              AND pol.qty_invoiced < pol.product_qty {extra}
            GROUP BY po.name, rp.name
            HAVING COALESCE(SUM((pol.product_qty - pol.qty_invoiced) * pol.price_unit), 0) > 0
            ORDER BY unbilled_amount DESC LIMIT 100
        """, params)
        return [{'po_ref': r['po_ref'], 'vendor_name': r['vendor_name'],
                 'po_subtotal': float(r['po_subtotal'] or 0),
                 'billed_amount': float(r['billed_amount'] or 0),
                 'unbilled_amount': float(r['unbilled_amount'] or 0)}
                for r in self.env.cr.dictfetchall()]

    # ─── APPROVAL ANALYSIS ────────────────────────────────────────

    @api.model
    def get_approval_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_approval_analytics', True):
            return {'disabled': True}
        params, extra = self._base_po_params(filters)
        today = filters.get('today', date.today())

        self.env.cr.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE po.state = 'to approve') AS waiting_approval,
                COUNT(*) FILTER (WHERE po.state IN ('purchase','done')) AS approved,
                COUNT(*) FILTER (WHERE po.state = 'cancel') AS rejected,
                COALESCE(AVG(
                    CASE WHEN po.state IN ('purchase','done') AND po.date_approve IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (po.date_approve - po.date_order))/86400.0 END
                ), 0) AS avg_approval_days
            FROM purchase_order po
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
        """, params)
        row = self.env.cr.dictfetchone() or {}

        waiting_rows = self._get_waiting_approval(filters)

        self.env.cr.execute(f"""
            SELECT ru_p.name AS buyer_name,
                   COALESCE(AVG(
                       CASE WHEN po.state IN ('purchase','done') AND po.date_approve IS NOT NULL
                       THEN EXTRACT(EPOCH FROM (po.date_approve - po.date_order))/86400.0 END
                   ), 0) AS avg_approval_days,
                   COUNT(*) FILTER (WHERE po.state = 'to approve') AS waiting_count
            FROM purchase_order po
            JOIN res_users ru ON ru.id = po.user_id
            JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY ru_p.name ORDER BY avg_approval_days DESC LIMIT 20
        """, params)
        delay_by_buyer = [{'buyer_name': r['buyer_name'],
                           'avg_approval_days': round(float(r['avg_approval_days'] or 0), 1),
                           'waiting_count': int(r['waiting_count'] or 0)}
                          for r in self.env.cr.dictfetchall()]

        kpis = {
            'waiting_approval': int(row.get('waiting_approval') or 0),
            'approved': int(row.get('approved') or 0),
            'rejected': int(row.get('rejected') or 0),
            'avg_approval_days': round(float(row.get('avg_approval_days') or 0), 1),
        }
        return {'kpis': kpis, 'waiting_rows': waiting_rows, 'delay_by_buyer': delay_by_buyer}

    # ─── LATE & UNFINISHED ────────────────────────────────────────

    @api.model
    def get_late_unfinished_purchases(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        late_pos = self._get_late_pos(filters)
        unfinished_pos = self._get_unfinished_pos(filters)
        waiting = self._get_waiting_approval(filters)
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT
                COUNT(DISTINCT po.id) FILTER (WHERE po.state NOT IN ('cancel')
                    AND (po.state IN ('draft','sent','to approve') OR pol.qty_received < pol.product_qty OR pol.qty_invoiced < pol.product_qty)) AS total_unfinished
            FROM purchase_order po JOIN purchase_order_line pol ON pol.order_id = po.id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
        """, params)
        kpi_row = self.env.cr.dictfetchone() or {}
        kpis = {
            'total_unfinished': int(kpi_row.get('total_unfinished') or 0),
            'late_count': len(late_pos),
            'waiting_approval': len(waiting),
        }
        return {'kpis': kpis, 'late_pos': late_pos, 'unfinished_pos': unfinished_pos, 'waiting': waiting}

    # ─── PRICE TREND ANALYSIS ─────────────────────────────────────

    @api.model
    def get_price_trend_analysis(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_price_trend_analytics', True):
            return {'disabled': True}
        params, extra = self._base_po_params(filters)

        self.env.cr.execute(f"""
            SELECT pol.product_id, pt.name AS product_name, pc.name AS category_name,
                   rp.name AS vendor_name, po.partner_id AS vendor_id,
                   po.date_order::date AS purchase_date, pol.price_unit,
                   LAG(pol.price_unit) OVER (PARTITION BY pol.product_id, po.partner_id ORDER BY po.date_order) AS prev_price
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            JOIN res_partner rp ON rp.id = po.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done') {extra}
            ORDER BY pol.product_id, po.date_order DESC
        """, params)
        price_trend_rows = []
        for r in self.env.cr.dictfetchall():
            price_unit = float(r['price_unit'] or 0)
            prev_price = float(r['prev_price'] or 0) if r['prev_price'] else None
            price_change = (price_unit - prev_price) if prev_price is not None else 0
            pct_change = ((price_change / prev_price) * 100) if prev_price else 0
            price_trend_rows.append({
                'product_id': r['product_id'], 'product_name': r['product_name'],
                'category_name': r['category_name'], 'vendor_name': r['vendor_name'],
                'vendor_id': r['vendor_id'],
                'purchase_date': str(r['purchase_date']) if r['purchase_date'] else '',
                'price_unit': price_unit, 'prev_price': prev_price or 0,
                'price_change': price_change, 'pct_change': round(pct_change, 2),
            })

        self.env.cr.execute(f"""
            SELECT pol.product_id, pt.name AS product_name, po.partner_id AS vendor_id, rp.name AS vendor_name,
                   MIN(pol.price_unit) AS min_price, MAX(pol.price_unit) AS max_price, AVG(pol.price_unit) AS avg_price,
                   (MAX(pol.price_unit) - MIN(pol.price_unit)) AS price_range
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN res_partner rp ON rp.id = po.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
              AND po.state IN ('purchase','done') {extra}
            GROUP BY pol.product_id, pt.name, po.partner_id, rp.name
            ORDER BY price_range DESC LIMIT 50
        """, params)
        vendor_price_comparison = [{'product_id': r['product_id'], 'product_name': r['product_name'],
                                     'vendor_id': r['vendor_id'], 'vendor_name': r['vendor_name'],
                                     'min_price': float(r['min_price'] or 0), 'max_price': float(r['max_price'] or 0),
                                     'avg_price': float(r['avg_price'] or 0), 'price_range': float(r['price_range'] or 0)}
                                    for r in self.env.cr.dictfetchall()]

        price_increase_alerts = self._get_price_change_alerts(filters)
        return {
            'price_trend_rows': price_trend_rows,
            'vendor_price_comparison': vendor_price_comparison,
            'price_increase_alerts': price_increase_alerts,
        }

    # ─── VENDOR SCORECARDS ────────────────────────────────────────

    @api.model
    def get_vendor_scorecards(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        scorecards = self._get_vendor_scorecard_rows(filters)
        return {'scorecards': scorecards}

    # ─── PURCHASE TARGETS ─────────────────────────────────────────

    @api.model
    def get_purchase_targets(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_target_analytics', True):
            return {'disabled': True}
        company_ids = filters.get('company_ids', [self.env.company.id])
        date_start = filters.get('date_start')
        date_end = filters.get('date_end')
        domain = ['|', ('company_id', '=', False), ('company_id', 'in', company_ids), ('active', '=', True)]
        targets = self.env['purchase.analytics.target'].search(domain)
        target_rows = []
        for t in targets:
            # Build purchase domain for this target
            po_domain = [('company_id', 'in', company_ids), ('state', 'not in', ['cancel', 'draft'])]
            if t.date_start:
                po_domain += [('date_order', '>=', datetime.combine(t.date_start, datetime.min.time()))]
            if t.date_end:
                po_domain += [('date_order', '<=', datetime.combine(t.date_end, datetime.max.time()))]
            if t.vendor_id:
                po_domain += [('partner_id', '=', t.vendor_id.id)]
            if t.buyer_id:
                po_domain += [('user_id', '=', t.buyer_id.id)]
            pos = self.env['purchase.order'].search(po_domain)
            line_domain = [('order_id', 'in', pos.ids)]
            if t.product_id:
                line_domain += [('product_id', '=', t.product_id.id)]
            if t.product_category_id:
                line_domain += [('product_id.categ_id', 'child_of', t.product_category_id.id)]
            lines = self.env['purchase.order.line'].search(line_domain)
            actual_amount = sum(l.price_subtotal for l in lines)
            actual_qty = sum(l.product_qty for l in lines)
            achievement_pct = (actual_amount / t.target_amount * 100) if t.target_amount > 0 else 0
            budget_used_pct = (actual_amount / t.maximum_amount * 100) if t.maximum_amount > 0 else 0
            qty_achievement_pct = (actual_qty / t.target_quantity * 100) if t.target_quantity > 0 else 0
            target_rows.append({
                'id': t.id, 'name': t.name,
                'vendor_name': t.vendor_id.name if t.vendor_id else '',
                'product_name': t.product_id.display_name if t.product_id else '',
                'category_name': t.product_category_id.complete_name if t.product_category_id else '',
                'buyer_name': t.buyer_id.name if t.buyer_id else '',
                'department': t.department or '', 'branch_label': t.branch_label or '',
                'date_start': str(t.date_start) if t.date_start else '',
                'date_end': str(t.date_end) if t.date_end else '',
                'target_amount': t.target_amount, 'actual_amount': actual_amount,
                'achievement_pct': round(achievement_pct, 1),
                'remaining': max(0, t.target_amount - actual_amount),
                'maximum_amount': t.maximum_amount, 'budget_used_pct': round(budget_used_pct, 1),
                'target_quantity': t.target_quantity, 'actual_qty': actual_qty,
                'qty_achievement_pct': round(qty_achievement_pct, 1),
            })
        return {
            'target_rows': target_rows,
            'total_targets': len(target_rows),
        }

    # ─── PURCHASE ALERTS ──────────────────────────────────────────

    @api.model
    def get_purchase_alerts(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        if not filters.get('settings', {}).get('enable_alert_analytics', True):
            return {'disabled': True}
        company_ids = filters.get('company_ids', [self.env.company.id])
        alert_rules = self.env['purchase.analytics.alert.rule'].search(
            ['|', ('company_id', '=', False), ('company_id', 'in', company_ids), ('active', '=', True)]
        )
        settings = filters.get('settings', {})
        alert_rows = []
        alert_summary = {}

        for rule in alert_rules:
            atype = rule.alert_type
            rows = []
            if atype == 'late_receipt':
                days = rule.threshold_days or settings.get('late_receipt_grace_days', 0)
                rows = [{'type': atype, 'description': f'PO {r["po_ref"]} is {r["late_days"]} days late',
                         'vendor': r['vendor_name'], 'buyer': r['buyer_name'],
                         'late_days': r['late_days'], 'amount': r['amount_total']}
                        for r in self._get_late_pos(filters) if r['late_days'] >= days]
            elif atype == 'waiting_approval_too_long':
                days = rule.threshold_days or settings.get('waiting_approval_late_days', 3)
                rows = [{'type': atype, 'description': f'PO {r["po_ref"]} waiting {r["days_waiting"]} days for approval',
                         'vendor': r['vendor_name'], 'buyer': r['buyer_name'],
                         'days_waiting': r['days_waiting'], 'amount': r['amount_total']}
                        for r in self._get_waiting_approval(filters) if r['days_waiting'] >= days]
            elif atype == 'price_increase':
                threshold_pct = rule.threshold_percentage or settings.get('price_increase_threshold_percentage', 5.0)
                rows = [{'type': atype, 'description': f'{r["product_name"]} price increased {r["pct_change"]*100:.1f}% from {r["vendor_name"]}',
                         'vendor': r['vendor_name'], 'product': r['product_name'],
                         'pct_change': r['pct_change'], 'latest_price': r['latest_price']}
                        for r in self._get_price_change_alerts(filters) if r['pct_change'] * 100 >= threshold_pct]
            elif atype == 'unbilled_po':
                rows = [{'type': atype, 'description': f'PO {r["po_ref"]} has unbilled amount {r["unbilled_amount"]:.2f}',
                         'vendor': r['vendor_name'], 'amount': r['unbilled_amount']}
                        for r in self._get_unbilled_pos(filters)]
            elif atype == 'high_value_po':
                threshold_amt = rule.threshold_amount or 0
                params, extra = self._base_po_params(filters)
                self.env.cr.execute(f"""
                    SELECT po.name AS po_ref, rp.name AS vendor_name, po.amount_total
                    FROM purchase_order po JOIN res_partner rp ON rp.id = po.partner_id
                    WHERE po.company_id IN %(company_ids)s
                      AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s
                      AND po.state NOT IN ('cancel') AND po.amount_total >= %(threshold)s {extra}
                    ORDER BY po.amount_total DESC LIMIT 20
                """, {**params, 'threshold': threshold_amt})
                rows = [{'type': atype, 'description': f'High value PO {r["po_ref"]}: {r["amount_total"]:.2f}',
                         'vendor': r['vendor_name'], 'amount': float(r['amount_total'] or 0)}
                        for r in self.env.cr.dictfetchall()]
            if rows:
                alert_rows.extend(rows)
                alert_summary[atype] = alert_summary.get(atype, 0) + len(rows)

        return {
            'alert_rows': alert_rows[:200],
            'alert_summary': alert_summary,
            'total_alerts': len(alert_rows),
        }

    # ─── REPORT DATA ──────────────────────────────────────────────

    @api.model
    def get_report_data(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        report_type = filters.get('report_type', 'purchase_management_summary')
        dispatch = {
            'purchase_management_summary': self.get_dashboard_data,
            'purchase_request_analysis_report': self.get_purchase_request_analysis,
            'rfq_analysis_report': self.get_rfq_analysis,
            'purchase_order_analysis_report': self.get_purchase_order_analysis,
            'vendor_performance_report': self.get_vendor_analysis,
            'product_purchase_report': self.get_product_purchase_analysis,
            'category_purchase_report': self.get_product_purchase_analysis,
            'buyer_performance_report': self.get_purchase_order_analysis,
            'receipt_matching_report': self.get_receipt_matching,
            'bill_matching_report': self.get_bill_matching,
            'approval_analysis_report': self.get_approval_analysis,
            'late_purchase_report': self.get_late_unfinished_purchases,
            'unfinished_purchase_report': self.get_late_unfinished_purchases,
            'price_trend_report': self.get_price_trend_analysis,
            'vendor_price_comparison_report': self.get_price_trend_analysis,
            'requested_product_report': self.get_purchase_request_analysis,
            'unreceived_product_report': self.get_receipt_matching,
            'unbilled_purchase_report': self.get_bill_matching,
            'cancelled_purchase_report': self.get_purchase_order_analysis,
            'purchase_target_report': self.get_purchase_targets,
            'purchase_alert_report': self.get_purchase_alerts,
        }
        fn = dispatch.get(report_type, self.get_dashboard_data)
        return fn(filters)

    @api.model
    def get_grouped_report_data(self, filters=None):
        self._check_analytics_access()
        filters = self._normalize_filters(filters or {})
        group_by = filters.get('group_by', 'month')
        params, extra = self._base_po_params(filters)

        group_expr_map = {
            'day': "DATE_TRUNC('day', po.date_order)::date",
            'week': "DATE_TRUNC('week', po.date_order)::date",
            'month': "DATE_TRUNC('month', po.date_order)::date",
            'year': "DATE_TRUNC('year', po.date_order)::date",
            'vendor': 'rp.name',
            'buyer': 'ru_p.name',
            'product': 'pt.name',
            'purchase_status': 'po.state',
        }
        group_expr = group_expr_map.get(group_by, "DATE_TRUNC('month', po.date_order)::date")
        group_label = 'period' if group_by in ('day', 'week', 'month', 'year') else 'group_label'

        needs_partner = group_by in ('vendor',)
        needs_buyer = group_by in ('buyer',)
        needs_product = group_by in ('product', 'product_category')
        join_clauses = ''
        if needs_partner or True:
            join_clauses += ' JOIN res_partner rp ON rp.id = po.partner_id'
        if needs_buyer or True:
            join_clauses += ' JOIN res_users ru ON ru.id = po.user_id JOIN res_partner ru_p ON ru_p.id = ru.partner_id'

        self.env.cr.execute(f"""
            SELECT
                {group_expr} AS group_label,
                COALESCE(SUM(po.amount_total) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS purchase_amount,
                COALESCE(SUM(po.amount_untaxed) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS untaxed_amount,
                COALESCE(SUM(po.amount_tax) FILTER (WHERE po.state NOT IN ('draft','cancel')), 0) AS tax_amount,
                COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('purchase','done')) AS po_count,
                COUNT(DISTINCT po.id) FILTER (WHERE po.state IN ('draft','sent')) AS rfq_count,
                COUNT(DISTINCT po.id) FILTER (WHERE po.state = 'cancel') AS cancelled_count
            FROM purchase_order po {join_clauses}
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            GROUP BY group_label ORDER BY group_label
        """, params)
        rows = self.env.cr.dictfetchall()
        return [{'group_label': str(r['group_label'] or ''),
                 'purchase_amount': float(r['purchase_amount'] or 0),
                 'untaxed_amount': float(r['untaxed_amount'] or 0),
                 'tax_amount': float(r['tax_amount'] or 0),
                 'po_count': int(r['po_count'] or 0),
                 'rfq_count': int(r['rfq_count'] or 0),
                 'cancelled_count': int(r['cancelled_count'] or 0)}
                for r in rows]

    # ─── RAW DATA HELPERS ─────────────────────────────────────────

    @api.model
    def _get_raw_purchase_orders(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.id, po.name AS po_ref, po.state, po.date_order::date AS order_date,
                   po.date_planned::date AS expected_date, rp.name AS vendor_name,
                   ru_p.name AS buyer_name, po.amount_untaxed, po.amount_tax, po.amount_total, po.origin
            FROM purchase_order po JOIN res_partner rp ON rp.id = po.partner_id
            JOIN res_users ru ON ru.id = po.user_id JOIN res_partner ru_p ON ru_p.id = ru.partner_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            ORDER BY po.date_order DESC LIMIT 1000
        """, params)
        return [{
            'po_ref': r['po_ref'], 'state': r['state'],
            'order_date': str(r['order_date']) if r['order_date'] else '',
            'expected_date': str(r['expected_date']) if r['expected_date'] else '',
            'vendor_name': r['vendor_name'], 'buyer_name': r['buyer_name'],
            'amount_untaxed': float(r['amount_untaxed'] or 0),
            'amount_tax': float(r['amount_tax'] or 0),
            'amount_total': float(r['amount_total'] or 0),
            'origin': r['origin'] or '',
        } for r in self.env.cr.dictfetchall()]

    @api.model
    def _get_raw_purchase_lines(self, filters):
        params, extra = self._base_po_params(filters)
        self.env.cr.execute(f"""
            SELECT po.name AS po_ref, po.state, rp.name AS vendor_name,
                   pt.name AS product_name, pc.name AS category_name,
                   pol.product_qty AS ordered_qty, pol.qty_received AS received_qty,
                   pol.qty_invoiced AS billed_qty, pol.price_unit,
                   pol.price_subtotal, pol.date_planned::date AS expected_date
            FROM purchase_order_line pol JOIN purchase_order po ON po.id = pol.order_id
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            JOIN product_category pc ON pc.id = pt.categ_id
            WHERE po.company_id IN %(company_ids)s
              AND po.date_order >= %(date_start)s AND po.date_order <= %(date_end)s {extra}
            ORDER BY po.date_order DESC LIMIT 2000
        """, params)
        return [{'po_ref': r['po_ref'], 'state': r['state'], 'vendor_name': r['vendor_name'],
                 'product_name': r['product_name'], 'category_name': r['category_name'],
                 'ordered_qty': float(r['ordered_qty'] or 0), 'received_qty': float(r['received_qty'] or 0),
                 'billed_qty': float(r['billed_qty'] or 0), 'price_unit': float(r['price_unit'] or 0),
                 'price_subtotal': float(r['price_subtotal'] or 0),
                 'expected_date': str(r['expected_date']) if r['expected_date'] else ''}
                for r in self.env.cr.dictfetchall()]

    # ─── FILTER OPTIONS ───────────────────────────────────────────

    @api.model
    def _get_filter_options(self):
        company_ids = self._get_allowed_company_ids()
        vendors = self.env['res.partner'].search([('supplier_rank', '>', 0)], limit=200, order='name')
        buyers = self.env['res.users'].search([('share', '=', False), ('active', '=', True)], limit=100, order='name')
        warehouses = self.env['stock.warehouse'].search([('company_id', 'in', company_ids)])
        categories = self.env['product.category'].search([], limit=200, order='complete_name')
        return {
            'vendors': [{'id': v.id, 'name': v.name} for v in vendors],
            'buyers': [{'id': u.id, 'name': u.name} for u in buyers],
            'warehouses': [{'id': w.id, 'name': w.name} for w in warehouses],
            'categories': [{'id': c.id, 'name': c.complete_name} for c in categories],
        }
