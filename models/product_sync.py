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
    
    @api.model
    def create(self, vals):
        """ایجاد محصول جدید با همگام‌سازی خودکار"""
        product = super().create(vals)
        
        # اگر همگام‌سازی فعال است و محصول قابل فروش است
        if product.woo_sync_enabled and product.sale_ok:
            try:
                product.sync_to_woocommerce()
            except Exception as e:
                _logger.error(f'Auto-sync failed for new product {product.name}: {str(e)}')
        
        return product
    
    def write(self, vals):
        """بروزرسانی محصول با همگام‌سازی خودکار"""
        # فیلدهایی که باید همگام‌سازی را trigger کنند
        sync_fields = [
            'name', 'list_price', 'standard_price', 'description', 
            'description_sale', 'default_code', 'weight', 'active',
            'qty_available', 'image_1920', 'categ_id'
        ]
        
        result = super().write(vals)
        
        # بررسی نیاز به همگام‌سازی
        if any(field in vals for field in sync_fields):
            for product in self:
                if product.woo_sync_enabled and product.sale_ok and product.woo_id:
                    try:
                        product.sync_to_woocommerce()
                    except Exception as e:
                        _logger.error(f'Auto-sync failed for {product.name}: {str(e)}')
        
        return result
    
    def sync_to_woocommerce(self):
        """همگام‌سازی محصول با WooCommerce - با مدیریت بهتر خطاها"""
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
                # ابتدا بررسی کنیم محصول در WooCommerce وجود دارد
                check_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
                check_response = requests.get(
                    check_url,
                    auth=(config.consumer_key, config.consumer_secret),
                    timeout=10
                )
                
                if check_response.status_code == 404:
                    # محصول در WooCommerce حذف شده، ID را پاک می‌کنیم
                    self.woo_id = False
                    _logger.warning(f'Product {self.name} was deleted from WooCommerce, creating new one')
                    
                    # ایجاد محصول جدید
                    create_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products"
                    response = requests.post(
                        create_url,
                        auth=(config.consumer_key, config.consumer_secret),
                        json=product_data,
                        timeout=30
                    )
                else:
                    # بروزرسانی محصول موجود
                    response = requests.put(
                        check_url,
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
                
                # همگام‌سازی موارد اضافی
                if config.sync_product_images and self.image_1920:
                    self._sync_product_images(result.get('id'), config)
                
                if config.sync_product_categories and self.categ_id:
                    self._sync_product_categories(result.get('id'), config)
                
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
                error_data = response.json() if response.content else {}
                raise UserError(
                    f'خطا در همگام‌سازی: {response.status_code}\n'
                    f'{error_data.get("message", response.text)}'
                )
                
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
            'sale_price': '',  # فعلاً خالی
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
        
        # ابعاد محصول اگر موجود باشد
        if hasattr(self, 'product_length') and self.product_length:
            data['dimensions'] = {
                'length': str(self.product_length),
                'width': str(self.product_width or ''),
                'height': str(self.product_height or ''),
            }
        
        # GTIN/EAN/ISBN از بارکد
        if self.barcode:
            data['sku'] = self.barcode  # استفاده از بارکد به عنوان SKU
        
        return data
    
    def _sync_product_images(self, woo_product_id, config):
        """همگام‌سازی تصاویر محصول"""
        if not self.image_1920:
            return
        
        try:
            # آپلود تصویر به WordPress Media Library
            media_url = f"{config.store_url.rstrip('/')}/wp-json/wp/v2/media"
            
            # آماده‌سازی فایل
            image_data = base64.b64decode(self.image_1920)
            files = {
                'file': (f'{self.name}.jpg', image_data, 'image/jpeg')
            }
            
            # آپلود تصویر
            media_response = requests.post(
                media_url,
                auth=(config.consumer_key, config.consumer_secret),
                files=files,
                timeout=60
            )
            
            if media_response.status_code == 201:
                media_data = media_response.json()
                image_id = media_data.get('id')
                
                # اتصال تصویر به محصول
                product_data = {
                    'images': [{
                        'id': image_id
                    }]
                }
                
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{woo_product_id}"
                response = requests.put(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=product_data,
                    timeout=30
                )
                
                if response.status_code not in [200, 201]:
                    _logger.error(f"Error attaching image: {response.text}")
            else:
                _logger.error(f"Error uploading image: {media_response.text}")
                
        except Exception as e:
            _logger.error(f"Error syncing product image: {str(e)}")
    
    def _sync_product_categories(self, woo_product_id, config):
        """همگام‌سازی دسته‌بندی محصول"""
        if not self.categ_id:
            return
        
        try:
            # ابتدا بررسی/ایجاد دسته‌بندی در WooCommerce
            category_name = self.categ_id.name
            
            # جستجوی دسته‌بندی
            search_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/categories"
            search_params = {'search': category_name}
            
            search_response = requests.get(
                search_url,
                auth=(config.consumer_key, config.consumer_secret),
                params=search_params,
                timeout=10
            )
            
            if search_response.status_code == 200:
                categories = search_response.json()
                
                if categories:
                    # استفاده از دسته‌بندی موجود
                    category_id = categories[0]['id']
                else:
                    # ایجاد دسته‌بندی جدید
                    category_data = {
                        'name': category_name,
                        'slug': category_name.lower().replace(' ', '-')
                    }
                    
                    create_response = requests.post(
                        search_url,
                        auth=(config.consumer_key, config.consumer_secret),
                        json=category_data,
                        timeout=30
                    )
                    
                    if create_response.status_code == 201:
                        category_id = create_response.json()['id']
                    else:
                        _logger.error(f"Error creating category: {create_response.text}")
                        return
                
                # اتصال دسته‌بندی به محصول
                product_data = {
                    'categories': [{'id': category_id}]
                }
                
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{woo_product_id}"
                response = requests.put(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=product_data,
                    timeout=30
                )
                
                if response.status_code not in [200, 201]:
                    _logger.error(f"Error updating product categories: {response.text}")
                    
        except Exception as e:
            _logger.error(f"Error syncing product categories: {str(e)}")


class WooConfig(models.Model):
    _inherit = 'woo.config'
    
    # تنظیمات mapping
    sync_product_images = fields.Boolean('همگام‌سازی تصاویر', default=True)
    sync_product_categories = fields.Boolean('همگام‌سازی دسته‌بندی‌ها', default=True)
    sync_product_tags = fields.Boolean('همگام‌سازی برچسب‌ها', default=True)
    sync_inventory_real_time = fields.Boolean('همگام‌سازی لحظه‌ای موجودی', default=True)
    auto_sync_on_change = fields.Boolean('همگام‌سازی خودکار هنگام تغییرات', default=True)
    
    def sync_all_products(self):
        """همگام‌سازی همه محصولات فعال"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise UserError('ابتدا اتصال را تست کنید!')
        
        # محصولات قابل فروش
        products = self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('type', 'in', ['product', 'consu'])
        ], limit=10)  # افزایش به 10 محصول
        
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
