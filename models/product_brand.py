# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'برند محصول'
    _order = 'name'
    
    name = fields.Char('نام برند', required=True)
    description = fields.Text('توضیحات')
    image = fields.Binary('لوگو')
    product_ids = fields.One2many('product.template', 'woo_brand_id', string='محصولات')
    active = fields.Boolean('فعال', default=True)
    product_count = fields.Integer('تعداد محصولات', compute='_compute_product_count')
    
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'نام برند باید یکتا باشد!'),
    ]
    
    @api.depends('product_ids')
    def _compute_product_count(self):
        for brand in self:
            brand.product_count = len(brand.product_ids)
