{
    'name': 'Purchase Advanced Analytics Dashboard',
    'version': '17.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Complete procurement lifecycle analytics: RFQ, PO, receipt, billing, vendor performance, price trends and operational control.',
    'description': """
Purchase Advanced Analytics Dashboard
======================================
A production-ready procurement analytics system for Odoo 17 that tracks the full
purchase lifecycle from Purchase Request → RFQ → PO → Approval → Receipt → Bill → Payment.

Features:
- Live operational dashboard with KPIs, charts, and tables
- Purchase Request Analysis (native model or inferred)
- RFQ Analysis
- Purchase Order Analysis
- Vendor Analysis and Scorecards
- Product Purchase Analysis
- Receipt Matching
- Bill Matching
- Approval Analysis
- Late and Unfinished Purchases
- Price Trend Analysis
- Purchase Targets
- Alert Rules
- PDF and Excel exports
- Multi-company support
- Runtime-safe optional module detection
    """,
    'author': 'Purchase Analytics',
    'depends': [
        'purchase',
        'stock',
        'account',
        'product',
        'web',
        'uom',
        'base',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/dashboard_actions.xml',
        'views/purchase_analytics_vendor_rule_views.xml',
        'views/purchase_analytics_target_views.xml',
        'views/purchase_analytics_status_map_views.xml',
        'views/purchase_analytics_alert_rule_views.xml',
        'views/purchase_analytics_report_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/purchase_analytics_menu.xml',
        'reports/purchase_analytics_report_action.xml',
        'reports/purchase_analytics_pdf_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'purchase_advanced_analytics/static/src/scss/purchase_analytics_dashboard.scss',
            'purchase_advanced_analytics/static/src/js/purchase_analytics_service.js',
            'purchase_advanced_analytics/static/src/js/purchase_analytics_dashboard.js',
            'purchase_advanced_analytics/static/src/xml/purchase_analytics_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
