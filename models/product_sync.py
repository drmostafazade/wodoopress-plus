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
    
    # فیلدهای WooCommerce
    woo_id = fields.Integer(
        string='شناسه WooCommerce',
        readonly=True,
        copy=False
    )
    woo_sync_enabled = fields.Boolean(
        string='همگام‌سازی با WooCommerce',
        default=False,
        help='فعال کردن همگام‌سازی خودکار با WooCommerce'
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
    
    # فیلدهای اضافی فقط برای WooCommerce
    woo_short_description = fields.Text(
        string='توضیحات کوتاه WooCommerce',
        help='اگر خالی باشد از description_sale استفاده می‌شود'
    )
    
    def sync_to_woocommerce(self):
        """همگام‌سازی محصول با WooCommerce - خواندن داده از Odoo"""
        self.ensure_one()
        
        # دریافت تنظیمات فعال
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        # آماده‌سازی داده محصول از فیلدهای موجود Odoo
        product_data = self._prepare_product_data()
        
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
                
                # همگام‌سازی تصاویر اگر وجود دارد
                if self.image_1920:
                    self._sync_product_images(result.get('id'), config)
                
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
    
    def _prepare_product_data(self):
        """آماده‌سازی داده محصول از فیلدهای Odoo"""
        self.ensure_one()
        
        # داده‌های پایه از Odoo
        data = {
            'name': self.name,
            'type': 'simple',
            'regular_price': str(self.list_price),
            'sale_price': str(self.standard_price) if self.standard_price else '',
            'description': self.description or '',
            'short_description': self.woo_short_description or self.description_sale or '',
            'sku': self.default_code or f'ODOO-{self.id}',
            'status': self.woo_status,
            'featured': False,
            'catalog_visibility': 'visible',
            'weight': str(self.weight) if self.weight else '',
            'manage_stock': True,
            'stock_quantity': int(self.qty_available),
            'stock_status': 'instock' if self.qty_available > 0 else 'outofstock',
            'backorders': 'no',
        }
        
        # دسته‌بندی‌ها
        if self.categ_id:
            # بعداً پیاده‌سازی می‌شود
            pass
        
        # ابعاد محصول
        if hasattr(self, 'product_length'):
            data['dimensions'] = {
                'length': str(self.product_length or ''),
                'width': str(self.product_width or ''),
                'height': str(self.product_height or ''),
            }
        
        # GTIN/EAN/ISBN
        if self.barcode:
            data['attributes'] = [{
                'name': 'GTIN/EAN',
                'options': [self.barcode],
                'visible': True,
                'variation': False,
            }]
        
        return data
    
    def _sync_product_images(self, woo_product_id, config):
        """همگام‌سازی تصاویر محصول"""
        if not self.image_1920:
            return
        
        try:
            # تبدیل تصویر به base64
            image_data = {
                'images': [{
                    'src': f"data:image/png;base64,{self.image_1920.decode('utf-8')}",
                    'name': f"{self.name} - تصویر اصلی",
                    'alt': self.name,
                }]
            }
            
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{woo_product_id}"
            response = requests.put(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                json=image_data,
                timeout=60
            )
            
            if response.status_code not in [200, 201]:
                _logger.error(f"Error syncing image: {response.text}")
                
        except Exception as e:
            _logger.error(f"Error syncing product image: {str(e)}")


class WooConfig(models.Model):
    _inherit = 'woo.config'
    
    # تنظیمات mapping
    sync_product_images = fields.Boolean('همگام‌سازی تصاویر', default=True)
    sync_product_categories = fields.Boolean('همگام‌سازی دسته‌بندی‌ها', default=True)
    sync_product_tags = fields.Boolean('همگام‌سازی برچسب‌ها', default=True)
    sync_inventory_real_time = fields.Boolean('همگام‌سازی لحظه‌ای موجودی', default=True)
    
    def sync_all_products(self):
        """همگام‌سازی همه محصولات فعال"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise UserError('ابتدا اتصال را تست کنید!')
        
        # محصولات قابل فروش
        products = self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('type', 'in', ['product', 'consu'])  # فقط محصولات فیزیکی و مصرفی
        ], limit=5)  # محدود به 5 محصول برای تست
        
        if not products:
            raise UserError('محصولی برای همگام‌سازی یافت نشد!')
        
        # فعال کردن sync برای این محصولات
        products.write({'woo_sync_enabled': True})
        
        success_count = 0
        error_count = 0
        errors = []
        
        for product in products:
            try:
                product.with_context(no_variant_sync=True).sync_to_woocommerce()
                success_count += 1
                _logger.info(f'Successfully synced: {product.name}')
            except Exception as e:
                error_count += 1
                error_msg = f'{product.name}: {str(e)}'
                errors.append(error_msg)
                _logger.error(error_msg)
        
        message = f'موفق: {success_count} محصول\nخطا: {error_count} محصول'
        if errors:
            message += '\n\nجزئیات خطاها:\n' + '\n'.join(errors[:3])
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'نتیجه همگام‌سازی',
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
