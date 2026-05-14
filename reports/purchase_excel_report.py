import io
import logging
from datetime import datetime, date
import pytz

_logger = logging.getLogger(__name__)


class PurchaseExcelReport:
    """Excel report generator for Purchase Advanced Analytics."""

    def __init__(self, env, filters, wizard=None):
        self.env = env
        self.filters = filters
        self.wizard = wizard
        self.service = env['purchase.analytics.service']
        self.company = env.company
        self.currency = env.company.currency_id
        self.report_type = filters.get('report_type', 'purchase_management_summary')
        self.timezone = filters.get('timezone', 'Africa/Addis_Ababa')

    def generate(self):
        """Generate and return the Excel workbook bytes."""
        output = io.BytesIO()
        try:
            import xlsxwriter
        except ImportError:
            raise ImportError("xlsxwriter is required for Excel export. Install it with: pip install xlsxwriter")

        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'remove_timezone': True})
        self._setup_formats(workbook)
        self._build_workbook(workbook)
        workbook.close()
        return output.getvalue()

    def _setup_formats(self, workbook):
        """Define all cell formats."""
        self.fmt = {}
        # Title
        self.fmt['title'] = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#1a6496', 'align': 'left'})
        # Header
        self.fmt['header'] = workbook.add_format({'bold': True, 'bg_color': '#1a6496', 'font_color': 'white', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        # Sub-header
        self.fmt['subheader'] = workbook.add_format({'bold': True, 'bg_color': '#2980b9', 'font_color': 'white', 'border': 1})
        # Meta label
        self.fmt['meta_label'] = workbook.add_format({'bold': True, 'font_color': '#555555', 'font_size': 9})
        # Meta value
        self.fmt['meta_value'] = workbook.add_format({'font_color': '#333333', 'font_size': 9})
        # Regular text
        self.fmt['text'] = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        self.fmt['text_wrap'] = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'vcenter'})
        # Numbers
        self.fmt['number'] = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})
        self.fmt['integer'] = workbook.add_format({'border': 1, 'num_format': '#,##0', 'align': 'right'})
        self.fmt['quantity'] = workbook.add_format({'border': 1, 'num_format': '#,##0.000', 'align': 'right'})
        self.fmt['currency'] = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right', 'font_color': '#1a6496'})
        self.fmt['percent'] = workbook.add_format({'border': 1, 'num_format': '0.00%', 'align': 'right'})
        self.fmt['date'] = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd', 'align': 'center'})
        # Alternating rows
        self.fmt['even'] = workbook.add_format({'border': 1, 'bg_color': '#f5f5f5', 'valign': 'vcenter'})
        self.fmt['even_num'] = workbook.add_format({'border': 1, 'bg_color': '#f5f5f5', 'num_format': '#,##0.00', 'align': 'right'})
        self.fmt['even_currency'] = workbook.add_format({'border': 1, 'bg_color': '#f5f5f5', 'num_format': '#,##0.00', 'align': 'right', 'font_color': '#1a6496'})
        self.fmt['even_qty'] = workbook.add_format({'border': 1, 'bg_color': '#f5f5f5', 'num_format': '#,##0.000', 'align': 'right'})
        self.fmt['even_pct'] = workbook.add_format({'border': 1, 'bg_color': '#f5f5f5', 'num_format': '0.00%', 'align': 'right'})
        self.fmt['even_date'] = workbook.add_format({'border': 1, 'bg_color': '#f5f5f5', 'num_format': 'yyyy-mm-dd', 'align': 'center'})
        # Totals row
        self.fmt['total'] = workbook.add_format({'bold': True, 'bg_color': '#1a6496', 'font_color': 'white', 'border': 1, 'num_format': '#,##0.00', 'align': 'right'})
        self.fmt['total_label'] = workbook.add_format({'bold': True, 'bg_color': '#1a6496', 'font_color': 'white', 'border': 1})
        self.fmt['total_int'] = workbook.add_format({'bold': True, 'bg_color': '#1a6496', 'font_color': 'white', 'border': 1, 'num_format': '#,##0', 'align': 'right'})
        # Alert/warning
        self.fmt['alert'] = workbook.add_format({'border': 1, 'bg_color': '#fff3cd', 'font_color': '#856404'})
        self.fmt['alert_num'] = workbook.add_format({'border': 1, 'bg_color': '#fff3cd', 'font_color': '#856404', 'num_format': '#,##0.00', 'align': 'right'})
        self.fmt['danger'] = workbook.add_format({'border': 1, 'bg_color': '#f8d7da', 'font_color': '#721c24'})
        self.fmt['danger_num'] = workbook.add_format({'border': 1, 'bg_color': '#f8d7da', 'font_color': '#721c24', 'num_format': '#,##0.00', 'align': 'right'})

    def _build_workbook(self, workbook):
        """Dispatch to report-type-specific builder."""
        builders = {
            'purchase_management_summary': self._build_management_summary,
            'purchase_request_analysis_report': self._build_purchase_request_analysis,
            'rfq_analysis_report': self._build_rfq_analysis,
            'purchase_order_analysis_report': self._build_po_analysis,
            'vendor_performance_report': self._build_vendor_performance,
            'product_purchase_report': self._build_product_purchase,
            'category_purchase_report': self._build_category_purchase,
            'buyer_performance_report': self._build_buyer_performance,
            'receipt_matching_report': self._build_receipt_matching,
            'bill_matching_report': self._build_bill_matching,
            'approval_analysis_report': self._build_approval_analysis,
            'late_purchase_report': self._build_late_purchase,
            'unfinished_purchase_report': self._build_unfinished_purchase,
            'price_trend_report': self._build_price_trend,
            'vendor_price_comparison_report': self._build_vendor_price_comparison,
            'requested_product_report': self._build_requested_product,
            'unreceived_product_report': self._build_unreceived_product,
            'unbilled_purchase_report': self._build_unbilled_purchase,
            'cancelled_purchase_report': self._build_cancelled_purchase,
            'purchase_target_report': self._build_purchase_target,
            'purchase_alert_report': self._build_purchase_alert,
        }
        builder = builders.get(self.report_type, self._build_management_summary)
        builder(workbook)

    # ─── METADATA HELPERS ───────────────────────────────────────

    def _write_metadata(self, ws, row=0, title='Purchase Analytics Report'):
        """Write company, title, filter info at the top of a sheet. Returns next row."""
        ws.merge_range(row, 0, row, 7, self.company.name, self.fmt['title'])
        row += 1
        ws.merge_range(row, 0, row, 7, title, self.fmt.get('subheader', self.fmt['header']))
        row += 1
        # Date range
        ws.write(row, 0, 'Date Range:', self.fmt['meta_label'])
        ws.write(row, 1, f"{self.filters.get('date_start', '')} to {self.filters.get('date_end', '')}", self.fmt['meta_value'])
        ws.write(row, 3, 'Report Basis:', self.fmt['meta_label'])
        ws.write(row, 4, self.service._basis_label(self.filters), self.fmt['meta_value'])
        row += 1
        # Generated info
        tz = pytz.timezone(self.timezone) if self.timezone else pytz.UTC
        now_local = datetime.now(tz)
        ws.write(row, 0, 'Generated By:', self.fmt['meta_label'])
        ws.write(row, 1, self.env.user.name, self.fmt['meta_value'])
        ws.write(row, 3, 'Generated At:', self.fmt['meta_label'])
        ws.write(row, 4, now_local.strftime('%Y-%m-%d %H:%M:%S %Z'), self.fmt['meta_value'])
        row += 2
        return row

    def _write_table(self, ws, row, headers, rows, col_formats=None):
        """Write a table with headers and data rows. Returns next row."""
        # Header row
        for col, header in enumerate(headers):
            ws.write(row, col, header, self.fmt['header'])
        row += 1
        # Data rows
        for i, data_row in enumerate(rows):
            is_even = (i % 2 == 0)
            for col, value in enumerate(data_row):
                fmt = self._get_cell_format(col, headers, value, is_even, col_formats)
                if isinstance(value, (datetime, date)):
                    ws.write(row, col, str(value), self.fmt['even_date' if is_even else 'date'])
                else:
                    ws.write(row, col, value if value is not None else '', fmt)
            row += 1
        return row

    def _get_cell_format(self, col, headers, value, is_even, col_formats=None):
        """Return the appropriate format for a cell based on header name and value type."""
        if col_formats and col < len(col_formats):
            return col_formats[col]
        header = (headers[col] if col < len(headers) else '').lower() if headers else ''
        # Currency detection
        currency_keywords = ['amount', 'total', 'untaxed', 'tax', 'billed', 'unbilled',
                             'price', 'subtotal', 'residual', 'budget', 'target', 'value', 'cost']
        if any(k in header for k in currency_keywords) and isinstance(value, (int, float)):
            return self.fmt['even_currency' if is_even else 'currency']
        # Percentage
        pct_keywords = ['%', 'percent', 'rate', 'score', 'achievement', 'on_time', 'pct']
        if any(k in header for k in pct_keywords) and isinstance(value, (int, float)):
            return self.fmt['even_pct' if is_even else 'percent']
        # Quantity
        qty_keywords = ['qty', 'quantity', 'ordered', 'received', 'pending', 'count', 'billed_qty']
        if any(k in header for k in qty_keywords) and isinstance(value, (int, float)):
            return self.fmt['even_qty' if is_even else 'quantity']
        # Integer
        if isinstance(value, int):
            return self.fmt['even' if is_even else 'integer']
        # Float
        if isinstance(value, float):
            return self.fmt['even_num' if is_even else 'number']
        return self.fmt['even' if is_even else 'text']

    def _auto_column_widths(self, ws, headers, rows, min_width=8, max_width=40):
        """Set column widths based on content."""
        widths = [len(str(h)) + 2 for h in headers]
        for row in rows:
            for col, val in enumerate(row):
                if col < len(widths):
                    widths[col] = max(widths[col], min(len(str(val or '')), max_width))
        for col, width in enumerate(widths):
            ws.set_column(col, col, max(min_width, width))

    def _write_totals_row(self, ws, row, num_cols, data_rows, total_label='TOTAL', numeric_cols=None):
        """Write a totals row summing numeric columns."""
        ws.write(row, 0, total_label, self.fmt['total_label'])
        for col in range(1, num_cols):
            if numeric_cols is None or col in numeric_cols:
                total = sum(r[col] for r in data_rows if col < len(r) and isinstance(r[col], (int, float)))
                ws.write(row, col, total, self.fmt['total'])
            else:
                ws.write(row, col, '', self.fmt['total_label'])
        return row + 1

    def _add_sheet(self, workbook, name):
        """Add a worksheet, truncating name to 31 chars (Excel limit)."""
        return workbook.add_worksheet(name[:31])

    # ─── MANAGEMENT SUMMARY ──────────────────────────────────────

    def _build_management_summary(self, workbook):
        data = self.service.get_dashboard_data(self.filters)
        kpis = data.get('kpis', {})

        # Summary Sheet
        ws = self._add_sheet(workbook, 'Summary')
        ws.set_zoom(90)
        row = self._write_metadata(ws, 0, 'Purchase Management Summary')

        ws.write(row, 0, 'KPI', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        kpi_items = [
            ('Total RFQs', kpis.get('total_rfqs', 0)),
            ('RFQs Sent', kpis.get('rfqs_sent', 0)),
            ('Waiting Approval', kpis.get('waiting_approval', 0)),
            ('Approved POs', kpis.get('approved_pos', 0)),
            ('Cancelled', kpis.get('cancelled', 0)),
            ('Total Purchase Amount', kpis.get('total_purchase_amount', 0)),
            ('Total Untaxed Amount', kpis.get('total_untaxed', 0)),
            ('Total Tax Amount', kpis.get('total_tax', 0)),
            ('Average PO Value', kpis.get('avg_po_value', 0)),
            ('Total Ordered Qty', kpis.get('total_ordered_qty', 0)),
            ('Total Received Qty', kpis.get('total_received_qty', 0)),
            ('Pending Receipt Qty', kpis.get('pending_receipt_qty', 0)),
            ('Billed Amount', kpis.get('billed_amount', 0)),
            ('Unbilled Amount', kpis.get('unbilled_amount', 0)),
            ('Late PO Count', kpis.get('late_po_count', 0)),
            ('Top Vendor', kpis.get('top_vendor', '')),
            ('Top Product', kpis.get('top_product', '')),
            ('Top Category', kpis.get('top_category', '')),
            ('Top Buyer', kpis.get('top_buyer', '')),
        ]
        for label, value in kpi_items:
            ws.write(row, 0, label, self.fmt['text'])
            if isinstance(value, float):
                ws.write(row, 1, value, self.fmt['currency'])
            elif isinstance(value, int):
                ws.write(row, 1, value, self.fmt['integer'])
            else:
                ws.write(row, 1, str(value or ''), self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 30)
        ws.set_column(1, 1, 20)

        # Vendor Summary Sheet
        vendor_ws = self._add_sheet(workbook, 'Vendor Summary')
        self._write_vendor_summary_sheet(vendor_ws, data.get('vendor_summary', []))

        # Product Summary Sheet
        prod_ws = self._add_sheet(workbook, 'Product Summary')
        self._write_product_summary_sheet(prod_ws, data.get('product_summary', []))

        # Category Summary Sheet
        cat_ws = self._add_sheet(workbook, 'Category Summary')
        self._write_category_summary_sheet(cat_ws, data.get('category_summary', []))

        # Buyer Summary Sheet
        buyer_ws = self._add_sheet(workbook, 'Buyer Summary')
        self._write_buyer_summary_sheet(buyer_ws, data.get('buyer_summary', []))

        # Waiting Approval Sheet
        wa_ws = self._add_sheet(workbook, 'Waiting Approval')
        self._write_waiting_approval_sheet(wa_ws, data.get('waiting_approval', []))

        # Late POs Sheet
        late_ws = self._add_sheet(workbook, 'Late Purchases')
        self._write_late_pos_sheet(late_ws, data.get('late_pos', []))

        # Price Alerts Sheet
        alert_ws = self._add_sheet(workbook, 'Price Alerts')
        self._write_price_alerts_sheet(alert_ws, data.get('price_change_alerts', []))

        # Raw Orders if requested
        if self.filters.get('include_raw_orders'):
            raw_ws = self._add_sheet(workbook, 'Raw Purchase Orders')
            raw_data = self.service._get_raw_purchase_orders(self.filters) if hasattr(self.service, '_get_raw_purchase_orders') else []
            self._write_raw_orders_sheet(raw_ws, raw_data)

    def _write_vendor_summary_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Vendor Summary')
        headers = ['Vendor', 'RFQ Count', 'PO Count', 'Total Amount', 'Untaxed Amount', 'Avg PO Value', 'Last Purchase Date']
        data_rows = [[r.get('vendor_name',''), r.get('rfq_count',0), r.get('po_count',0),
                      r.get('total_amount',0), r.get('untaxed_amount',0), r.get('avg_po_value',0),
                      r.get('last_purchase_date','')] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)
        ws.autofilter(row, 0, row + len(data_rows), len(headers) - 1)

    def _write_product_summary_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Product Summary')
        headers = ['Product', 'Category', 'Ordered Qty', 'Received Qty', 'Pending Qty',
                   'Billed Qty', 'Total Amount', 'Avg Price', 'Min Price', 'Max Price', 'PO Count', 'Last Purchase Date']
        data_rows = [[r.get('product_name',''), r.get('category_name',''), r.get('ordered_qty',0),
                      r.get('received_qty',0), r.get('pending_qty',0), r.get('billed_qty',0),
                      r.get('total_amount',0), r.get('avg_price',0), r.get('min_price',0),
                      r.get('max_price',0), r.get('po_count',0), r.get('last_purchase_date','')] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)
        ws.autofilter(row, 0, row + len(data_rows), len(headers) - 1)

    def _write_category_summary_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Category Summary')
        headers = ['Category', 'Total Amount', 'Ordered Qty', 'PO Count']
        data_rows = [[r.get('category_name',''), r.get('total_amount',0),
                      r.get('ordered_qty',0), r.get('po_count',0)] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)

    def _write_buyer_summary_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Buyer Summary')
        headers = ['Buyer', 'PO Count', 'Waiting Approval', 'Total Amount']
        data_rows = [[r.get('buyer_name',''), r.get('po_count',0),
                      r.get('waiting_count',0), r.get('total_amount',0)] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)

    def _write_waiting_approval_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Waiting Approval')
        headers = ['PO Reference', 'Vendor', 'Buyer', 'Order Date', 'Amount', 'Days Waiting']
        data_rows = [[r.get('po_ref',''), r.get('vendor_name',''), r.get('buyer_name',''),
                      r.get('order_date',''), r.get('amount_total',0), r.get('days_waiting',0)] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)

    def _write_late_pos_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Late Purchases')
        headers = ['PO Reference', 'Vendor', 'Buyer', 'Expected Date', 'Ordered Qty', 'Received Qty', 'Pending Qty', 'Late Days', 'Amount']
        data_rows = [[r.get('po_ref',''), r.get('vendor_name',''), r.get('buyer_name',''),
                      r.get('expected_date',''), r.get('ordered_qty',0), r.get('received_qty',0),
                      r.get('pending_qty',0), r.get('late_days',0), r.get('amount_total',0)] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)

    def _write_price_alerts_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Price Increase Alerts')
        headers = ['Product', 'Vendor', 'Previous Price', 'Latest Price', 'Price Change', 'Change %', 'Last Purchase Date']
        data_rows = [[r.get('product_name',''), r.get('vendor_name',''), r.get('prev_price',0),
                      r.get('latest_price',0), r.get('price_change',0), r.get('pct_change',0),
                      r.get('last_purchase_date','')] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)

    def _write_raw_orders_sheet(self, ws, rows):
        row = self._write_metadata(ws, 0, 'Raw Purchase Orders')
        if not rows:
            ws.write(row, 0, 'No data available', self.fmt['text'])
            return
        headers = list(rows[0].keys()) if rows else []
        data_rows = [[r.get(h) for h in headers] for r in rows]
        self._write_table(ws, row, headers, data_rows)
        self._auto_column_widths(ws, headers, data_rows)

    # ─── SPECIFIC REPORT BUILDERS ────────────────────────────────

    def _build_purchase_request_analysis(self, workbook):
        data = self.service.get_purchase_request_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Summary')
        row = self._write_metadata(ws, 0, 'Purchase Request Analysis')
        if data.get('fallback_message'):
            ws.merge_range(row, 0, row, 5, data['fallback_message'], self.fmt['alert'])
            row += 2
        kpis = data.get('kpis', {})
        kpi_items = [(k.replace('_', ' ').title(), v) for k, v in kpis.items()]
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for label, value in kpi_items:
            ws.write(row, 0, label, self.fmt['text'])
            if isinstance(value, (int, float)):
                ws.write(row, 1, value, self.fmt['number'])
            else:
                ws.write(row, 1, str(value or ''), self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        # Status breakdown
        status_ws = self._add_sheet(workbook, 'Status Breakdown')
        status_row = self._write_metadata(status_ws, 0, 'Request Status Breakdown')
        breakdown = data.get('status_breakdown', [])
        if breakdown:
            headers = ['Status', 'Count', 'Amount']
            d_rows = [[r.get('status',''), r.get('count',0), r.get('amount',0)] for r in breakdown]
            self._write_table(status_ws, status_row, headers, d_rows)
            self._auto_column_widths(status_ws, headers, d_rows)

    def _build_rfq_analysis(self, workbook):
        data = self.service.get_rfq_analysis(self.filters)
        ws = self._add_sheet(workbook, 'RFQ Summary')
        row = self._write_metadata(ws, 0, 'RFQ Analysis Report')
        kpis = data.get('kpis', {})
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for k, v in kpis.items():
            ws.write(row, 0, k.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, v if v is not None else 0, self.fmt['number'] if isinstance(v, (int, float)) else self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        # RFQ list
        rfq_ws = self._add_sheet(workbook, 'RFQ List')
        rfq_row = self._write_metadata(rfq_ws, 0, 'RFQ Details')
        rfq_rows = data.get('raw_rfqs', [])
        if rfq_rows:
            headers = list(rfq_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in rfq_rows]
            self._write_table(rfq_ws, rfq_row, headers, d_rows)
            self._auto_column_widths(rfq_ws, headers, d_rows)
            rfq_ws.autofilter(rfq_row, 0, rfq_row + len(d_rows), len(headers) - 1)

    def _build_po_analysis(self, workbook):
        data = self.service.get_purchase_order_analysis(self.filters)
        ws = self._add_sheet(workbook, 'PO Summary')
        row = self._write_metadata(ws, 0, 'Purchase Order Analysis')
        kpis = data.get('kpis', {})
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for k, v in kpis.items():
            ws.write(row, 0, k.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, v if v is not None else 0, self.fmt['number'] if isinstance(v, (int, float)) else self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        vendor_ws = self._add_sheet(workbook, 'Vendor Breakdown')
        vrow = self._write_metadata(vendor_ws, 0, 'PO by Vendor')
        vrows = data.get('vendor_breakdown', [])
        if vrows:
            headers = list(vrows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in vrows]
            self._write_table(vendor_ws, vrow, headers, d_rows)
            self._auto_column_widths(vendor_ws, headers, d_rows)

    def _build_vendor_performance(self, workbook):
        data = self.service.get_vendor_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Vendor Scorecards')
        row = self._write_metadata(ws, 0, 'Vendor Performance Report')
        scorecards = data.get('scorecards', [])
        if scorecards:
            headers = ['Vendor', 'Total POs', 'Purchase Amount', 'On-Time Delivery %',
                       'Avg Lead Time', 'Late Count', 'Price Stability Score',
                       'Completion Score', 'Overall Score']
            d_rows = [[r.get('vendor_name',''), r.get('po_count',0), r.get('total_amount',0),
                       r.get('on_time_pct',0), r.get('avg_lead_time',0), r.get('late_count',0),
                       r.get('price_stability_score',0), r.get('completion_score',0),
                       r.get('overall_score',0)] for r in scorecards]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
            ws.autofilter(row, 0, row + len(d_rows), len(headers) - 1)
        vendor_ws = self._add_sheet(workbook, 'Vendor Purchase Summary')
        vrow = self._write_metadata(vendor_ws, 0, 'Vendor Purchase Summary')
        summary = data.get('vendor_summary', [])
        if summary:
            headers = list(summary[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in summary]
            self._write_table(vendor_ws, vrow, headers, d_rows)
            self._auto_column_widths(vendor_ws, headers, d_rows)

    def _build_product_purchase(self, workbook):
        data = self.service.get_product_purchase_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Product Summary')
        row = self._write_metadata(ws, 0, 'Product Purchase Report')
        rows = data.get('product_rows', [])
        if rows:
            headers = ['Product', 'Category', 'Ordered Qty', 'Received Qty', 'Pending Qty',
                       'Billed Qty', 'Purchase Amount', 'Avg Price', 'Last Price',
                       'Min Price', 'Max Price', 'Price Change %', 'PO Count', 'Last Purchase Date']
            d_rows = [[r.get('product_name',''), r.get('category_name',''), r.get('ordered_qty',0),
                       r.get('received_qty',0), r.get('pending_qty',0), r.get('billed_qty',0),
                       r.get('total_amount',0), r.get('avg_price',0), r.get('last_price',0),
                       r.get('min_price',0), r.get('max_price',0), r.get('price_change_pct',0),
                       r.get('po_count',0), r.get('last_purchase_date','')] for r in rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
            ws.autofilter(row, 0, row + len(d_rows), len(headers) - 1)

    def _build_category_purchase(self, workbook):
        data = self.service.get_product_purchase_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Category Summary')
        row = self._write_metadata(ws, 0, 'Category Purchase Report')
        rows = data.get('category_summary', [])
        if rows:
            headers = ['Category', 'Total Amount', 'Ordered Qty', 'PO Count']
            d_rows = [[r.get('category_name',''), r.get('total_amount',0),
                       r.get('ordered_qty',0), r.get('po_count',0)] for r in rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)

    def _build_buyer_performance(self, workbook):
        data = self.service.get_purchase_order_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Buyer Summary')
        row = self._write_metadata(ws, 0, 'Buyer Performance Report')
        rows = data.get('buyer_summary', [])
        if rows:
            headers = list(rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)

    def _build_receipt_matching(self, workbook):
        data = self.service.get_receipt_matching(self.filters)
        ws = self._add_sheet(workbook, 'Receipt Matching')
        row = self._write_metadata(ws, 0, 'Receipt Matching Report')
        kpis = data.get('kpis', {})
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for k, v in kpis.items():
            ws.write(row, 0, k.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, v if v is not None else 0, self.fmt['number'] if isinstance(v, (int, float)) else self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        detail_ws = self._add_sheet(workbook, 'Receipt Details')
        drow = self._write_metadata(detail_ws, 0, 'Receipt Matching Details')
        receipt_rows = data.get('receipt_rows', [])
        if receipt_rows:
            headers = list(receipt_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in receipt_rows]
            self._write_table(detail_ws, drow, headers, d_rows)
            self._auto_column_widths(detail_ws, headers, d_rows)
            detail_ws.autofilter(drow, 0, drow + len(d_rows), len(headers) - 1)
        unreceived_ws = self._add_sheet(workbook, 'Unreceived Products')
        urow = self._write_metadata(unreceived_ws, 0, 'Unreceived Products')
        unreceived = data.get('unreceived_products', [])
        if unreceived:
            headers = list(unreceived[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in unreceived]
            self._write_table(unreceived_ws, urow, headers, d_rows)
            self._auto_column_widths(unreceived_ws, headers, d_rows)

    def _build_bill_matching(self, workbook):
        data = self.service.get_bill_matching(self.filters)
        ws = self._add_sheet(workbook, 'Bill Matching')
        row = self._write_metadata(ws, 0, 'Bill Matching Report')
        kpis = data.get('kpis', {})
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for k, v in kpis.items():
            ws.write(row, 0, k.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, v if v is not None else 0, self.fmt['number'] if isinstance(v, (int, float)) else self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        detail_ws = self._add_sheet(workbook, 'Bill Details')
        drow = self._write_metadata(detail_ws, 0, 'Bill Matching Details')
        bill_rows = data.get('bill_rows', [])
        if bill_rows:
            headers = list(bill_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in bill_rows]
            self._write_table(detail_ws, drow, headers, d_rows)
            self._auto_column_widths(detail_ws, headers, d_rows)

    def _build_approval_analysis(self, workbook):
        data = self.service.get_approval_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Approval Summary')
        row = self._write_metadata(ws, 0, 'Approval Analysis Report')
        kpis = data.get('kpis', {})
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for k, v in kpis.items():
            ws.write(row, 0, k.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, v if v is not None else 0, self.fmt['number'] if isinstance(v, (int, float)) else self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        wa_ws = self._add_sheet(workbook, 'Waiting Approval')
        warow = self._write_metadata(wa_ws, 0, 'Waiting Approval Details')
        wa_rows = data.get('waiting_rows', [])
        if wa_rows:
            headers = list(wa_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in wa_rows]
            self._write_table(wa_ws, warow, headers, d_rows)
            self._auto_column_widths(wa_ws, headers, d_rows)

    def _build_late_purchase(self, workbook):
        data = self.service.get_late_unfinished_purchases(self.filters)
        ws = self._add_sheet(workbook, 'Late Purchases')
        row = self._write_metadata(ws, 0, 'Late Purchase Report')
        late_rows = data.get('late_pos', [])
        if late_rows:
            headers = ['PO Ref', 'Vendor', 'Buyer', 'Expected Date', 'Ordered Qty', 'Received Qty', 'Pending Qty', 'Late Days', 'Amount']
            d_rows = [[r.get('po_ref',''), r.get('vendor_name',''), r.get('buyer_name',''),
                       r.get('expected_date',''), r.get('ordered_qty',0), r.get('received_qty',0),
                       r.get('pending_qty',0), r.get('late_days',0), r.get('amount_total',0)] for r in late_rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
            ws.autofilter(row, 0, row + len(d_rows), len(headers) - 1)

    def _build_unfinished_purchase(self, workbook):
        data = self.service.get_late_unfinished_purchases(self.filters)
        ws = self._add_sheet(workbook, 'Unfinished Purchases')
        row = self._write_metadata(ws, 0, 'Unfinished Purchase Report')
        unfinished = data.get('unfinished_pos', [])
        if unfinished:
            headers = ['PO Ref', 'Vendor', 'Buyer', 'State', 'Pending Qty', 'Unbilled Amount', 'Amount', 'Age Days']
            d_rows = [[r.get('po_ref',''), r.get('vendor_name',''), r.get('buyer_name',''),
                       r.get('state',''), r.get('pending_qty',0), r.get('unbilled_amount',0),
                       r.get('amount_total',0), r.get('age_days',0)] for r in unfinished]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)

    def _build_price_trend(self, workbook):
        data = self.service.get_price_trend_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Price Trend')
        row = self._write_metadata(ws, 0, 'Price Trend Report')
        trend_rows = data.get('price_trend_rows', [])
        if trend_rows:
            headers = list(trend_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in trend_rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
            ws.autofilter(row, 0, row + len(d_rows), len(headers) - 1)
        alerts_ws = self._add_sheet(workbook, 'Price Increase Alerts')
        arow = self._write_metadata(alerts_ws, 0, 'Price Increase Alerts')
        alert_rows = data.get('price_increase_alerts', [])
        if alert_rows:
            headers = ['Product', 'Vendor', 'Previous Price', 'Latest Price', 'Change Amount', 'Change %', 'Last Date']
            d_rows = [[r.get('product_name',''), r.get('vendor_name',''), r.get('prev_price',0),
                       r.get('latest_price',0), r.get('price_change',0), r.get('pct_change',0),
                       r.get('last_purchase_date','')] for r in alert_rows]
            self._write_table(alerts_ws, arow, headers, d_rows)
            self._auto_column_widths(alerts_ws, headers, d_rows)

    def _build_vendor_price_comparison(self, workbook):
        data = self.service.get_price_trend_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Vendor Price Comparison')
        row = self._write_metadata(ws, 0, 'Vendor Price Comparison Report')
        comparison = data.get('vendor_price_comparison', [])
        if comparison:
            headers = list(comparison[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in comparison]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
        else:
            ws.write(row, 0, 'No vendor price comparison data available.', self.fmt['text'])

    def _build_requested_product(self, workbook):
        data = self.service.get_purchase_request_analysis(self.filters)
        ws = self._add_sheet(workbook, 'Requested Products')
        row = self._write_metadata(ws, 0, 'Requested Product Report')
        if data.get('fallback_message'):
            ws.merge_range(row, 0, row, 5, data['fallback_message'], self.fmt['alert'])
            row += 2
        prod_rows = data.get('product_breakdown', [])
        if prod_rows:
            headers = list(prod_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in prod_rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
        else:
            ws.write(row, 0, 'No requested product data available.', self.fmt['text'])

    def _build_unreceived_product(self, workbook):
        data = self.service.get_receipt_matching(self.filters)
        ws = self._add_sheet(workbook, 'Unreceived Products')
        row = self._write_metadata(ws, 0, 'Unreceived Product Report')
        rows = data.get('unreceived_products', [])
        if rows:
            headers = list(rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
            ws.autofilter(row, 0, row + len(d_rows), len(headers) - 1)
        else:
            ws.write(row, 0, 'No unreceived products found.', self.fmt['text'])

    def _build_unbilled_purchase(self, workbook):
        data = self.service.get_bill_matching(self.filters)
        ws = self._add_sheet(workbook, 'Unbilled Purchases')
        row = self._write_metadata(ws, 0, 'Unbilled Purchase Report')
        rows = data.get('unbilled_rows', [])
        if rows:
            headers = list(rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
        else:
            ws.write(row, 0, 'No unbilled purchases found.', self.fmt['text'])

    def _build_cancelled_purchase(self, workbook):
        cancelled_filters = dict(self.filters)
        cancelled_filters['purchase_state'] = 'cancel'
        data = self.service.get_purchase_order_analysis(cancelled_filters)
        ws = self._add_sheet(workbook, 'Cancelled Purchases')
        row = self._write_metadata(ws, 0, 'Cancelled Purchase Report')
        kpis = data.get('kpis', {})
        ws.write(row, 0, 'Metric', self.fmt['header'])
        ws.write(row, 1, 'Value', self.fmt['header'])
        row += 1
        for k, v in kpis.items():
            ws.write(row, 0, k.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, v if v is not None else 0, self.fmt['number'] if isinstance(v, (int, float)) else self.fmt['text'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 20)
        raw_ws = self._add_sheet(workbook, 'Cancelled PO Details')
        rrow = self._write_metadata(raw_ws, 0, 'Cancelled PO Details')
        raw_rows = data.get('raw_pos', [])
        if raw_rows:
            headers = list(raw_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in raw_rows]
            self._write_table(raw_ws, rrow, headers, d_rows)
            self._auto_column_widths(raw_ws, headers, d_rows)

    def _build_purchase_target(self, workbook):
        data = self.service.get_purchase_targets(self.filters)
        ws = self._add_sheet(workbook, 'Target Achievement')
        row = self._write_metadata(ws, 0, 'Purchase Target Report')
        target_rows = data.get('target_rows', [])
        if target_rows:
            headers = ['Target Name', 'Vendor', 'Product', 'Category', 'Buyer',
                       'Date Start', 'Date End', 'Target Amount', 'Actual Amount',
                       'Achievement %', 'Remaining', 'Max Amount', 'Budget Used %',
                       'Target Qty', 'Actual Qty', 'Qty Achievement %']
            d_rows = [[
                r.get('name',''), r.get('vendor_name',''), r.get('product_name',''),
                r.get('category_name',''), r.get('buyer_name',''),
                r.get('date_start',''), r.get('date_end',''),
                r.get('target_amount',0), r.get('actual_amount',0),
                r.get('achievement_pct',0) / 100.0, r.get('remaining',0),
                r.get('maximum_amount',0), r.get('budget_used_pct',0) / 100.0,
                r.get('target_quantity',0), r.get('actual_qty',0),
                r.get('qty_achievement_pct',0) / 100.0
            ] for r in target_rows]
            self._write_table(ws, row, headers, d_rows)
            self._auto_column_widths(ws, headers, d_rows)
        else:
            ws.write(row, 0, 'No purchase targets configured.', self.fmt['text'])

    def _build_purchase_alert(self, workbook):
        data = self.service.get_purchase_alerts(self.filters)
        ws = self._add_sheet(workbook, 'Alert Summary')
        row = self._write_metadata(ws, 0, 'Purchase Alert Report')
        summary = data.get('alert_summary', {})
        ws.write(row, 0, 'Alert Type', self.fmt['header'])
        ws.write(row, 1, 'Count', self.fmt['header'])
        row += 1
        for alert_type, count in summary.items():
            ws.write(row, 0, alert_type.replace('_', ' ').title(), self.fmt['text'])
            ws.write(row, 1, count, self.fmt['integer'])
            row += 1
        ws.set_column(0, 0, 35)
        ws.set_column(1, 1, 15)
        detail_ws = self._add_sheet(workbook, 'Alert Details')
        drow = self._write_metadata(detail_ws, 0, 'Alert Details')
        alert_rows = data.get('alert_rows', [])
        if alert_rows:
            headers = list(alert_rows[0].keys())
            d_rows = [[r.get(h) for h in headers] for r in alert_rows]
            self._write_table(detail_ws, drow, headers, d_rows)
            self._auto_column_widths(detail_ws, headers, d_rows)
