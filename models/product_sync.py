# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import base64

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    # فیلدهای WooCommerce پایه
    woo_id = fields.Integer('شناسه WooCommerce', readonly=True, copy=False)
    woo_sync_enabled = fields.Boolean('همگام‌سازی با WooCommerce', default=False)
    woo_last_sync = fields.Datetime('آخرین همگام‌سازی', readonly=True)
    woo_status = fields.Selection([
        ('publish', 'منتشر شده'),
        ('draft', 'پیش‌نویس'),
        ('pending', 'در انتظار'),
        ('private', 'خصوصی'),
    ], string='وضعیت در WooCommerce', default='publish')
    
    # فیلدهای اضافی
    woo_short_description = fields.Text('توضیحات کوتاه WooCommerce')
    woo_brand_id = fields.Many2one('product.brand', string='برند')
    reordering_min_qty = fields.Float('آستانه کم‌بودن موجودی', default=5.0)
    
    def sync_to_woocommerce(self):
        """همگام‌سازی محصول با WooCommerce"""
        self.ensure_one()
        
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        try:
            # داده‌های پایه محصول
            product_data = {
                'name': self.name,
                'type': 'simple',
                'status': self.woo_status if self.active else 'draft',
                'description': self.description or '',
                'short_description': self.woo_short_description or self.description_sale or '',
                'sku': self.default_code or self.barcode or f'ODOO-{self.id}',
                'regular_price': str(self.list_price),
                'manage_stock': True,
                'stock_quantity': int(self.qty_available),
                'stock_status': 'instock' if self.qty_available > 0 else 'outofstock',
                'weight': str(self.weight) if self.weight else '',
            }
            
            # آستانه موجودی
            if self.reordering_min_qty:
                product_data['low_stock_amount'] = int(self.reordering_min_qty)
            
            # برند
            if self.woo_brand_id:
                product_data['attributes'] = [{
                    'id': 0,
                    'name': 'برند',
                    'visible': True,
                    'variation': False,
                    'options': [self.woo_brand_id.name]
                }]
            
            # تصویر اصلی
            if self.image_1920 and config.sync_product_images:
                try:
                    image_id = self._upload_image_simple(self.image_1920, config)
                    if image_id:
                        product_data['images'] = [{'id': image_id}]
                except:
                    _logger.warning('خطا در آپلود تصویر')
            
            # meta data
            product_data['meta_data'] = [
                {'key': '_managed_by_odoo', 'value': 'true'},
                {'key': '_odoo_id', 'value': str(self.id)}
            ]
            
            # یادداشت خرید
            if self.description_purchase:
                product_data['meta_data'].append({
                    'key': '_purchase_note',
                    'value': self.description_purchase
                })
            
            # ارسال به WooCommerce
            if self.woo_id:
                # بروزرسانی
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
                response = requests.put(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=product_data,
                    timeout=30
                )
            else:
                # ایجاد جدید
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
                        'message': f'محصول {self.name} همگام‌سازی شد',
                        'type': 'success',
                    }
                }
            else:
                raise UserError(f'خطا: {response.status_code}\n{response.text}')
                
        except Exception as e:
            raise UserError(f'خطا در همگام‌سازی: {str(e)}')
    
    def _upload_image_simple(self, image_data, config):
        """آپلود ساده تصویر"""
        try:
            media_url = f"{config.store_url.rstrip('/')}/wp-json/wp/v2/media"
            image_binary = base64.b64decode(image_data)
            
            files = {
                'file': (f'{self.name}.jpg', image_binary, 'image/jpeg')
            }
            
            response = requests.post(
                media_url,
                auth=(config.consumer_key, config.consumer_secret),
                files=files,
                timeout=60
            )
            
            if response.status_code == 201:
                return response.json().get('id')
                
        except Exception as e:
            _logger.error(f"خطا در آپلود تصویر: {str(e)}")
            return None
