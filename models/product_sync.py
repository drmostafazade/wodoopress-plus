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
    
    def sync_to_woocommerce(self):
        """همگام‌سازی محصول با WooCommerce - نسخه Debug"""
        self.ensure_one()
        
        _logger.info(f"=== Starting sync for product: {self.name} (ID: {self.id}, WOO_ID: {self.woo_id}) ===")
        
        # دریافت تنظیمات فعال
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        _logger.info(f"Using config: {config.name} - URL: {config.store_url}")
        
        # آماده‌سازی داده محصول
        product_data = self._prepare_product_data()
        _logger.info(f"Product data prepared: {json.dumps(product_data, indent=2)}")
        
        try:
            if self.woo_id:
                _logger.info(f"Product has WOO_ID: {self.woo_id}, checking if exists in WooCommerce...")
                
                # بررسی وجود محصول
                check_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
                _logger.info(f"Checking URL: {check_url}")
                
                check_response = requests.get(
                    check_url,
                    auth=(config.consumer_key, config.consumer_secret),
                    timeout=10
                )
                
                _logger.info(f"Check response status: {check_response.status_code}")
                
                if check_response.status_code == 404:
                    _logger.warning(f"Product not found in WooCommerce, resetting woo_id")
                    self.woo_id = False
                    
                    # ایجاد محصول جدید
                    create_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products"
                    _logger.info(f"Creating new product at: {create_url}")
                    
                    response = requests.post(
                        create_url,
                        auth=(config.consumer_key, config.consumer_secret),
                        json=product_data,
                        timeout=30
                    )
                elif check_response.status_code == 200:
                    # محصول موجود است، بروزرسانی
                    _logger.info(f"Product exists, updating...")
                    response = requests.put(
                        check_url,
                        auth=(config.consumer_key, config.consumer_secret),
                        json=product_data,
                        timeout=30
                    )
                else:
                    # خطای دیگر
                    error_msg = check_response.json() if check_response.content else check_response.text
                    _logger.error(f"Unexpected response: {error_msg}")
                    raise UserError(f"خطای غیرمنتظره: {check_response.status_code}\n{error_msg}")
            else:
                # ایجاد محصول جدید
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products"
                _logger.info(f"Creating new product at: {url}")
                
                response = requests.post(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=product_data,
                    timeout=30
                )
            
            _logger.info(f"Final response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                new_woo_id = result.get('id')
                _logger.info(f"Success! New WOO_ID: {new_woo_id}")
                
                self.write({
                    'woo_id': new_woo_id,
                    'woo_last_sync': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'همگام‌سازی موفق',
                        'message': f'محصول {self.name} با موفقیت همگام‌سازی شد (WOO ID: {new_woo_id})',
                        'type': 'success',
                    }
                }
            else:
                error_data = response.json() if response.content else {}
                _logger.error(f"Sync failed: {response.status_code} - {error_data}")
                raise UserError(
                    f'خطا در همگام‌سازی: {response.status_code}\n'
                    f'{error_data.get("message", response.text)}'
                )
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"Request exception: {str(e)}")
            raise UserError(f'خطا در ارتباط: {str(e)}')
    
    def _prepare_product_data(self):
        """آماده‌سازی داده محصول از فیلدهای Odoo"""
        self.ensure_one()
        
        # داده‌های پایه از Odoo
        data = {
            'name': self.name,
            'type': 'simple',
            'regular_price': str(self.list_price),
            'description': self.description or '',
            'short_description': self.description_sale or '',
            'sku': self.default_code or f'ODOO-{self.id}',
            'status': self.woo_status,
            'manage_stock': True,
            'stock_quantity': int(self.qty_available),
            'stock_status': 'instock' if self.qty_available > 0 else 'outofstock',
        }
        
        # اگر بارکد داریم، از آن به عنوان SKU استفاده کنیم
        if self.barcode:
            data['sku'] = self.barcode
        
        return data
    
    def reset_woo_id(self):
        """ریست کردن WooCommerce ID"""
        self.ensure_one()
        self.woo_id = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'WooCommerce ID برای {self.name} ریست شد',
                'type': 'success',
            }
        }


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
            ('type', 'in', ['product', 'consu'])
        ], limit=5)
        
        if not products:
            raise UserError('محصولی برای همگام‌سازی یافت نشد!')
        
        # فعال کردن sync برای این محصولات
        products.write({'woo_sync_enabled': True})
        
        success_count = 0
        error_count = 0
        errors = []
        
        for product in products:
            try:
                _logger.info(f"\n{'='*50}")
                _logger.info(f"Syncing product: {product.name}")
                _logger.info(f"{'='*50}")
                
                product.sync_to_woocommerce()
                success_count += 1
            except Exception as e:
                error_count += 1
                error_msg = f'{product.name}: {str(e)}'
                errors.append(error_msg)
                _logger.error(error_msg)
        
        message = f'✅ موفق: {success_count} محصول\n❌ خطا: {error_count} محصول'
        if errors:
            message += '\n\n📋 جزئیات خطاها:\n' + '\n'.join(errors[:5])
        
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
    
    def reset_all_woo_ids(self):
        """ریست کردن همه WooCommerce ID ها"""
        products = self.env['product.template'].search([('woo_id', '!=', False)])
        products.write({'woo_id': False})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'{len(products)} محصول ریست شد',
                'type': 'success',
            }
        }
