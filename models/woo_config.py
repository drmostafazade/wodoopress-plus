# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class WooConfig(models.Model):
    _name = 'woo.config'
    _description = 'تنظیمات WooCommerce'
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(
        string='نام تنظیمات',
        required=True,
        default='تنظیمات اصلی'
    )
    
    store_url = fields.Char(
        string='آدرس فروشگاه',
        required=True,
        help='مثال: https://bsepar.com'
    )
    
    consumer_key = fields.Char(
        string='Consumer Key',
        required=True,
        help='از WooCommerce > Settings > Advanced > REST API'
    )
    
    consumer_secret = fields.Char(
        string='Consumer Secret',
        required=True,
        help='از WooCommerce > Settings > Advanced > REST API'
    )
    
    active = fields.Boolean(
        string='فعال',
        default=True
    )
    
    connection_status = fields.Selection([
        ('not_tested', 'تست نشده'),
        ('connected', 'متصل'),
        ('error', 'خطا در اتصال')
    ], string='وضعیت اتصال', default='not_tested', readonly=True)
    
    last_connection_test = fields.Datetime(
        string='آخرین تست اتصال',
        readonly=True
    )
    
    # فیلدهای تنظیمات همگام‌سازی
    sync_product_images = fields.Boolean('همگام‌سازی تصاویر', default=True)
    sync_product_categories = fields.Boolean('همگام‌سازی دسته‌بندی‌ها', default=True)
    sync_product_tags = fields.Boolean('همگام‌سازی برچسب‌ها', default=True)
    sync_inventory_real_time = fields.Boolean('همگام‌سازی Real-time موجودی', default=True)

    @api.constrains('store_url')
    def _check_store_url(self):
        for record in self:
            if record.store_url and not record.store_url.startswith(('http://', 'https://')):
                raise ValidationError('آدرس فروشگاه باید با http:// یا https:// شروع شود')

    def test_connection(self):
        """تست اتصال به WooCommerce"""
        self.ensure_one()
        
        try:
            # تست ساده با دریافت اطلاعات سیستم
            url = f"{self.store_url.rstrip('/')}/wp-json/wc/v3/system_status"
            
            response = requests.get(
                url,
                auth=(self.consumer_key, self.consumer_secret),
                timeout=10
            )
            
            if response.status_code == 200:
                self.write({
                    'connection_status': 'connected',
                    'last_connection_test': fields.Datetime.now()
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'اتصال موفق',
                        'message': 'اتصال به WooCommerce با موفقیت برقرار شد!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                self.connection_status = 'error'
                raise ValidationError(f'خطا در اتصال: کد {response.status_code}')
                
        except requests.exceptions.RequestException as e:
            self.connection_status = 'error'
            raise ValidationError(f'خطا در اتصال: {str(e)}')
        except Exception as e:
            self.connection_status = 'error'
            raise ValidationError(f'خطای غیرمنتظره: {str(e)}')

    def sync_all_products(self):
        """همگام‌سازی کامل همه محصولات فعال"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise ValidationError('ابتدا اتصال را تست کنید!')
        
        # یافتن محصولات قابل فروش
        products = self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('type', 'in', ['product', 'consu'])
        ], limit=10)  # برای تست با 10 محصول شروع می‌کنیم
        
        if not products:
            raise ValidationError('محصولی برای همگام‌سازی یافت نشد!')
        
        # فعال کردن همگام‌سازی
        products.write({'woo_sync_enabled': True})
        
        success_count = 0
        error_count = 0
        errors = []
        synced_details = []
        
        for product in products:
            try:
                product.sync_to_woocommerce()
                success_count += 1
                synced_details.append(f"✅ {product.name}")
                _logger.info(f'محصول {product.name} با موفقیت همگام‌سازی شد')
            except Exception as e:
                error_count += 1
                error_msg = f"❌ {product.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(f'خطا در همگام‌سازی {product.name}: {str(e)}')
        
        # ساخت پیام نتیجه
        message = f'📊 نتیجه همگام‌سازی:\n\n'
        message += f'✅ موفق: {success_count} محصول\n'
        message += f'❌ خطا: {error_count} محصول\n\n'
        
        if synced_details:
            message += '📋 محصولات همگام شده:\n' + '\n'.join(synced_details[:5])
            if len(synced_details) > 5:
                message += f'\n... و {len(synced_details) - 5} محصول دیگر'
        
        if errors:
            message += '\n\n⚠️ خطاها:\n' + '\n'.join(errors[:3])
            if len(errors) > 3:
                message += f'\n... و {len(errors) - 3} خطای دیگر'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'همگام‌سازی کامل انجام شد',
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
    
    def reset_all_woo_ids(self):
        """ریست کردن همه شناسه‌های WooCommerce"""
        self.ensure_one()
        
        # یافتن محصولات دارای شناسه WooCommerce
        products = self.env['product.template'].search([
            '|',
            ('woo_id', '!=', False),
            ('woo_sync_enabled', '=', True)
        ])
        
        count = len(products)
        
        # ریست کردن فیلدها
        products.write({
            'woo_id': False,
            'woo_sync_enabled': False,
            'woo_last_sync': False,
            'woo_status': 'publish'
        })
        
        _logger.info(f'{count} محصول ریست شدند')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ ریست انجام شد',
                'message': f'{count} محصول با موفقیت ریست شدند',
                'type': 'success',
            }
        }
