# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    # فیلدهای WooCommerce
    woo_id = fields.Integer(
        string='شناسه WooCommerce',
        readonly=True,
        copy=False
    )
    woo_sync_enabled = fields.Boolean(
        string='همگام‌سازی با WooCommerce',
        default=False
    )
    woo_last_sync = fields.Datetime(
        string='آخرین همگام‌سازی',
        readonly=True
    )
    woo_status = fields.Selection([
        ('publish', 'منتشر شده'),
        ('draft', 'پیش‌نویس'),
        ('pending', 'در انتظار'),
        ('private', 'خصوصی'),
    ], string='وضعیت در WooCommerce', default='publish')
    
    def sync_to_woocommerce(self):
        """همگام‌سازی محصول با WooCommerce"""
        self.ensure_one()
        
        # دریافت تنظیمات فعال
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        # آماده‌سازی داده محصول
        product_data = {
            'name': self.name,
            'type': 'simple',
            'regular_price': str(self.list_price),
            'description': self.description or '',
            'short_description': self.description_sale or '',
            'sku': self.default_code or f'ODOO-{self.id}',
            'status': self.woo_status,
            'manage_stock': True,
            'stock_quantity': int(self.qty_available),
        }
        
        try:
            if self.woo_id:
                # بروزرسانی محصول موجود
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
                response = requests.put(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=product_data,
                    timeout=30
                )
            else:
                # ایجاد محصول جدید
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products"
                response = requests.post(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=product_data,
                    timeout=30
                )
            
            if response.status_code in [200, 201]:
                result = response.json()
                self.write({
                    'woo_id': result.get('id'),
                    'woo_last_sync': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'همگام‌سازی موفق',
                        'message': f'محصول {self.name} با موفقیت همگام‌سازی شد',
                        'type': 'success',
                    }
                }
            else:
                raise UserError(f'خطا در همگام‌سازی: {response.status_code}\n{response.text}')
                
        except requests.exceptions.RequestException as e:
            raise UserError(f'خطا در ارتباط: {str(e)}')


class WooConfig(models.Model):
    _inherit = 'woo.config'
    
    def sync_all_products(self):
        """همگام‌سازی همه محصولات فعال"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise UserError('ابتدا اتصال را تست کنید!')
        
        # یافتن محصولات برای همگام‌سازی
        products = self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('woo_sync_enabled', '=', True)
        ])
        
        if not products:
            raise UserError('محصولی برای همگام‌سازی یافت نشد!')
        
        success_count = 0
        error_count = 0
        
        for product in products:
            try:
                product.sync_to_woocommerce()
                success_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f'Error syncing product {product.name}: {str(e)}')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'نتیجه همگام‌سازی',
                'message': f'موفق: {success_count} | خطا: {error_count}',
                'type': 'success' if error_count == 0 else 'warning',
            }
        }
