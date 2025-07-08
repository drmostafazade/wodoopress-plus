# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplateExtended(models.Model):
    _inherit = 'product.template'
    
    # فیلدهای اضافی برای همگام‌سازی بهتر
    reordering_min_qty = fields.Float(
        string='آستانه کم‌بودن موجودی',
        default=5.0,
        help='هشدار زمانی که موجودی به این مقدار برسد'
    )
    
    woo_manage_stock = fields.Boolean(
        string='مدیریت موجودی در WooCommerce',
        default=True
    )
    
    woo_backorders = fields.Selection([
        ('no', 'اجازه نده'),
        ('notify', 'اجازه بده و اطلاع بده'),
        ('yes', 'اجازه بده')
    ], string='سفارش‌های Backorder', default='no')
