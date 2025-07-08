# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplateExtensions(models.Model):
    _inherit = 'product.template'
    
    # ابعاد محصول (اگر در Odoo 18 موجود نباشد)
    product_length = fields.Float('طول محصول', help='طول بر حسب متر')
    product_width = fields.Float('عرض محصول', help='عرض بر حسب متر')
    product_height = fields.Float('ارتفاع محصول', help='ارتفاع بر حسب متر')
    
    # فیلدهای sync اضافی
    woo_sync_images = fields.Boolean('همگام‌سازی تصاویر', default=True)
    woo_sync_price = fields.Boolean('همگام‌سازی قیمت', default=True)
    woo_sync_lock = fields.Boolean('قفل همگام‌سازی', default=False)
