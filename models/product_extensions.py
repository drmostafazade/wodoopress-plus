# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplateWoo(models.Model):
    _inherit = 'product.template'
    
    # فیلدهای اضافی برای WooCommerce
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
    
    woo_sync_images = fields.Boolean(
        string='همگام‌سازی تصاویر',
        default=True
    )
    
    woo_sync_price = fields.Boolean(
        string='همگام‌سازی قیمت',
        default=True
    )
    
    woo_sync_lock = fields.Boolean(
        string='قفل همگام‌سازی',
        default=False,
        help='جلوگیری از همگام‌سازی خودکار'
    )
