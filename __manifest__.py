# -*- coding: utf-8 -*-
{
    'name': 'WodooPress Plus',
    'version': '18.0.1.0.0',
    'category': 'Website/eCommerce',
    'summary': 'یکپارچه‌سازی حرفه‌ای WordPress WooCommerce با Odoo 18',
    'description': """
WodooPress Plus - Professional WooCommerce Integration
=====================================================

ماژول حرفه‌ای یکپارچه‌سازی WordPress WooCommerce با Odoo 18 Enterprise

ویژگی‌های کلیدی:
-----------------
* همگام‌سازی Real-time محصولات، سفارشات و موجودی
* پشتیبانی از محصولات متغیر (Variable Products)
* مدیریت چند انبار
* پشتیبانی چندارزی
* رابط کاربری کاملاً فارسی

سازنده: Dr. Mostafazade
وبسایت: https://bsepar.com
    """,
    'author': 'Dr. Mostafazade',
    'website': 'https://bsepar.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'stock',
        'product',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/woo_config_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
}
