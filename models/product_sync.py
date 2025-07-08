# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
import base64
from datetime import datetime

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
    
    # فیلدهای تکمیلی
    woo_short_description = fields.Text(
        string='توضیحات کوتاه WooCommerce',
        help='اگر خالی باشد از description_sale استفاده می‌شود'
    )
    woo_brand_id = fields.Many2one(
        'product.brand',
        string='برند'
    )
    
    @api.model
    def create(self, vals):
        """ایجاد محصول جدید با همگام‌سازی خودکار"""
        product = super().create(vals)
        
        # همگام‌سازی خودکار
        if product.woo_sync_enabled and product.sale_ok:
            try:
                product.with_delay().sync_to_woocommerce()
            except:
                product.sync_to_woocommerce()
        
        return product
    
    def write(self, vals):
        """بروزرسانی محصول با همگام‌سازی خودکار"""
        # فیلدهایی که باید همگام‌سازی را trigger کنند
        sync_fields = [
            'name', 'list_price', 'standard_price', 'description', 
            'description_sale', 'default_code', 'weight', 'active',
            'image_1920', 'categ_id', 'barcode', 'product_tag_ids',
            'volume', 'product_length', 'product_width', 'product_height'
        ]
        
        result = super().write(vals)
        
        # بررسی نیاز به همگام‌سازی
        if any(field in vals for field in sync_fields):
            for product in self:
                if product.woo_sync_enabled and product.sale_ok and product.woo_id:
                    try:
                        product.with_delay().sync_to_woocommerce()
                    except:
                        product.sync_to_woocommerce()
        
        return result
    
    def sync_to_woocommerce(self):
        """همگام‌سازی کامل محصول با WooCommerce"""
        self.ensure_one()
        
        # دریافت تنظیمات فعال
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        try:
            # 1. همگام‌سازی تصاویر (اول باید انجام شود)
            image_ids = []
            if config.sync_product_images and self.image_1920:
                image_ids = self._sync_product_images(config)
            
            # 2. همگام‌سازی دسته‌بندی‌ها
            category_ids = []
            if config.sync_product_categories and self.categ_id:
                category_ids = self._sync_product_categories(config)
            
            # 3. همگام‌سازی برچسب‌ها
            tag_ids = []
            if config.sync_product_tags and self.product_tag_ids:
                tag_ids = self._sync_product_tags(config)
            
            # 4. آماده‌سازی داده محصول کامل
            product_data = self._prepare_complete_product_data(
                image_ids, category_ids, tag_ids
            )
            
            # 5. ارسال به WooCommerce
            if self.woo_id:
                # بررسی وجود محصول
                check_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
                check_response = requests.get(
                    check_url,
                    auth=(config.consumer_key, config.consumer_secret),
                    timeout=10
                )
                
                if check_response.status_code == 404:
                    # محصول حذف شده، ایجاد مجدد
                    self.woo_id = False
                    url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products"
                    response = requests.post(
                        url,
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
                
                # 6. همگام‌سازی موجودی real-time
                if config.sync_inventory_real_time:
                    self._sync_stock_quantity(result.get('id'), config)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'همگام‌سازی موفق',
                        'message': f'محصول {self.name} با تمام جزئیات همگام‌سازی شد',
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
    
    def _prepare_complete_product_data(self, image_ids=None, category_ids=None, tag_ids=None):
        """آماده‌سازی کامل داده محصول از تمام فیلدهای Odoo"""
        self.ensure_one()
        
        # داده‌های پایه
        data = {
            'name': self.name,
            'type': 'simple',
            'regular_price': str(self.list_price),
            'description': self.description or '',
            'short_description': self.woo_short_description or self.description_sale or '',
            'sku': self.barcode or self.default_code or f'ODOO-{self.id}',
            'status': self.woo_status,
            'featured': False,
            'catalog_visibility': 'visible',
            'weight': str(self.weight) if self.weight else '',
            'manage_stock': True,
            'stock_quantity': int(self.qty_available),
            'stock_status': 'instock' if self.qty_available > 0 else 'outofstock',
            'backorders': 'no',
            'sold_individually': False,
            'reviews_allowed': True,
        }
        
        # قیمت فروش ویژه
        if hasattr(self, 'lst_price') and self.lst_price < self.list_price:
            data['sale_price'] = str(self.lst_price)
        
        # ابعاد محصول
        dimensions = {}
        if hasattr(self, 'product_length') and self.product_length:
            dimensions['length'] = str(self.product_length)
        if hasattr(self, 'product_width') and self.product_width:
            dimensions['width'] = str(self.product_width)
        if hasattr(self, 'product_height') and self.product_height:
            dimensions['height'] = str(self.product_height)
        if dimensions:
            data['dimensions'] = dimensions
        
        # تصاویر
        if image_ids:
            data['images'] = [{'id': img_id} for img_id in image_ids]
        
        # دسته‌بندی‌ها
        if category_ids:
            data['categories'] = [{'id': cat_id} for cat_id in category_ids]
        
        # برچسب‌ها
        if tag_ids:
            data['tags'] = [{'id': tag_id} for tag_id in tag_ids]
        
        # ویژگی‌های محصول (attributes)
        attributes = []
        
        # برند به عنوان attribute
        if self.woo_brand_id:
            attributes.append({
                'name': 'برند',
                'options': [self.woo_brand_id.name],
                'visible': True,
                'variation': False,
            })
        
        # بارکد/GTIN
        if self.barcode:
            attributes.append({
                'name': 'GTIN/EAN',
                'options': [self.barcode],
                'visible': True,
                'variation': False,
            })
        
        # کشور مبدا
        if hasattr(self, 'country_of_origin_id') and self.country_of_origin_id:
            attributes.append({
                'name': 'کشور مبدا',
                'options': [self.country_of_origin_id.name],
                'visible': True,
                'variation': False,
            })
        
        if attributes:
            data['attributes'] = attributes
        
        # محصولات مرتبط
        if hasattr(self, 'accessory_product_ids') and self.accessory_product_ids:
            related_skus = [p.default_code for p in self.accessory_product_ids if p.default_code]
            if related_skus:
                # بعداً پیاده‌سازی می‌شود
                pass
        
        # یادداشت خرید به عنوان meta data
        meta_data = []
        if self.description_purchase:
            meta_data.append({
                'key': '_purchase_note',
                'value': self.description_purchase
            })
        
        if hasattr(self, 'hs_code') and self.hs_code:
            meta_data.append({
                'key': '_hs_code',
                'value': self.hs_code
            })
        
        if meta_data:
            data['meta_data'] = meta_data
        
        return data
    
    def _sync_product_images(self, config):
        """همگام‌سازی کامل تصاویر محصول"""
        image_ids = []
        
        try:
            # تصویر اصلی
            if self.image_1920:
                main_image_id = self._upload_image_to_wordpress(
                    self.image_1920, 
                    f"{self.name} - تصویر اصلی",
                    config
                )
                if main_image_id:
                    image_ids.append(main_image_id)
            
            # تصاویر اضافی
            if hasattr(self, 'product_template_image_ids'):
                for idx, img in enumerate(self.product_template_image_ids):
                    if img.image_1920:
                        extra_image_id = self._upload_image_to_wordpress(
                            img.image_1920,
                            f"{self.name} - تصویر {idx + 2}",
                            config
                        )
                        if extra_image_id:
                            image_ids.append(extra_image_id)
            
            return image_ids
            
        except Exception as e:
            _logger.error(f"Error syncing images: {str(e)}")
            return []
    
    def _upload_image_to_wordpress(self, image_data, title, config):
        """آپلود تصویر به WordPress Media Library"""
        try:
            media_url = f"{config.store_url.rstrip('/')}/wp-json/wp/v2/media"
            
            # تبدیل base64 به binary
            image_binary = base64.b64decode(image_data)
            
            # تعیین نوع فایل
            if image_binary.startswith(b'\xff\xd8'):
                mime_type = 'image/jpeg'
                extension = 'jpg'
            elif image_binary.startswith(b'\x89PNG'):
                mime_type = 'image/png'
                extension = 'png'
            else:
                mime_type = 'image/jpeg'
                extension = 'jpg'
            
            files = {
                'file': (f'{title}.{extension}', image_binary, mime_type)
            }
            
            headers = {
                'Content-Disposition': f'attachment; filename="{title}.{extension}"'
            }
            
            response = requests.post(
                media_url,
                auth=(config.consumer_key, config.consumer_secret),
                files=files,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 201:
                return response.json().get('id')
            else:
                _logger.error(f"Image upload failed: {response.text}")
                return None
                
        except Exception as e:
            _logger.error(f"Error uploading image: {str(e)}")
            return None
    
    def _sync_product_categories(self, config):
        """همگام‌سازی دسته‌بندی‌های محصول"""
        category_ids = []
        
        try:
            # دسته‌بندی اصلی
            if self.categ_id:
                cat_id = self._get_or_create_woo_category(
                    self.categ_id.name,
                    self.categ_id.parent_id.name if self.categ_id.parent_id else None,
                    config
                )
                if cat_id:
                    category_ids.append(cat_id)
            
            # دسته‌بندی‌های عمومی وب‌سایت
            if hasattr(self, 'public_categ_ids') and self.public_categ_ids:
                for categ in self.public_categ_ids:
                    cat_id = self._get_or_create_woo_category(
                        categ.name,
                        categ.parent_id.name if categ.parent_id else None,
                        config
                    )
                    if cat_id:
                        category_ids.append(cat_id)
            
            return category_ids
            
        except Exception as e:
            _logger.error(f"Error syncing categories: {str(e)}")
            return []
    
    def _get_or_create_woo_category(self, name, parent_name, config):
        """دریافت یا ایجاد دسته‌بندی در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/categories"
            
            # جستجوی دسته‌بندی
            search_params = {'search': name}
            response = requests.get(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                params=search_params,
                timeout=10
            )
            
            if response.status_code == 200:
                categories = response.json()
                
                # بررسی وجود دسته‌بندی
                for cat in categories:
                    if cat['name'] == name:
                        return cat['id']
                
                # ایجاد دسته‌بندی جدید
                parent_id = 0
                if parent_name:
                    parent_id = self._get_or_create_woo_category(parent_name, None, config)
                
                category_data = {
                    'name': name,
                    'slug': name.lower().replace(' ', '-').replace('/', '-'),
                    'parent': parent_id
                }
                
                create_response = requests.post(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=category_data,
                    timeout=30
                )
                
                if create_response.status_code == 201:
                    return create_response.json()['id']
            
            return None
            
        except Exception as e:
            _logger.error(f"Error creating category {name}: {str(e)}")
            return None
    
    def _sync_product_tags(self, config):
        """همگام‌سازی برچسب‌های محصول"""
        tag_ids = []
        
        try:
            for tag in self.product_tag_ids:
                tag_id = self._get_or_create_woo_tag(tag.name, config)
                if tag_id:
                    tag_ids.append(tag_id)
            
            return tag_ids
            
        except Exception as e:
            _logger.error(f"Error syncing tags: {str(e)}")
            return []
    
    def _get_or_create_woo_tag(self, name, config):
        """دریافت یا ایجاد برچسب در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/tags"
            
            # جستجوی برچسب
            search_params = {'search': name}
            response = requests.get(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                params=search_params,
                timeout=10
            )
            
            if response.status_code == 200:
                tags = response.json()
                
                # بررسی وجود برچسب
                for tag in tags:
                    if tag['name'] == name:
                        return tag['id']
                
                # ایجاد برچسب جدید
                tag_data = {
                    'name': name,
                    'slug': name.lower().replace(' ', '-')
                }
                
                create_response = requests.post(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json=tag_data,
                    timeout=30
                )
                
                if create_response.status_code == 201:
                    return create_response.json()['id']
            
            return None
            
        except Exception as e:
            _logger.error(f"Error creating tag {name}: {str(e)}")
            return None
    
    def _sync_stock_quantity(self, woo_product_id, config):
        """همگام‌سازی موجودی انبار"""
        try:
            # محاسبه موجودی واقعی
            stock_quantity = int(self.qty_available)
            
            # بروزرسانی موجودی در WooCommerce
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{woo_product_id}"
            stock_data = {
                'stock_quantity': stock_quantity,
                'stock_status': 'instock' if stock_quantity > 0 else 'outofstock'
            }
            
            response = requests.put(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                json=stock_data,
                timeout=10
            )
            
            if response.status_code not in [200, 201]:
                _logger.error(f"Stock update failed: {response.text}")
                
        except Exception as e:
            _logger.error(f"Error updating stock: {str(e)}")


class ProductBrand(models.Model):
    _name = 'product.brand'
    _description = 'برند محصول'
    
    name = fields.Char('نام برند', required=True)
    description = fields.Text('توضیحات')
    image = fields.Binary('لوگو')
    product_ids = fields.One2many('product.template', 'woo_brand_id', 'محصولات')


class ProductTag(models.Model):
    _inherit = 'product.tag'
    
    woo_tag_id = fields.Integer('شناسه برچسب WooCommerce', readonly=True)


class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    woo_category_id = fields.Integer('شناسه دسته‌بندی WooCommerce', readonly=True)


class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    @api.model
    def create(self, vals):
        """همگام‌سازی خودکار موجودی هنگام تغییر"""
        quant = super().create(vals)
        self._sync_product_stock(quant)
        return quant
    
    def write(self, vals):
        """همگام‌سازی خودکار موجودی هنگام تغییر"""
        result = super().write(vals)
        for quant in self:
            self._sync_product_stock(quant)
        return result
    
    def _sync_product_stock(self, quant):
        """همگام‌سازی موجودی محصول با WooCommerce"""
        if quant.location_id.usage == 'internal' and quant.product_id.product_tmpl_id.woo_sync_enabled:
            config = self.env['woo.config'].search([
                ('active', '=', True),
                ('sync_inventory_real_time', '=', True)
            ], limit=1)
            
            if config:
                try:
                    quant.product_id.product_tmpl_id._sync_stock_quantity(
                        quant.product_id.product_tmpl_id.woo_id,
                        config
                    )
                except Exception as e:
                    _logger.error(f"Auto stock sync failed: {str(e)}")


class WooConfig(models.Model):
    _inherit = 'woo.config'
    
    def sync_all_products(self):
        """همگام‌سازی کامل همه محصولات فعال"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise UserError('ابتدا اتصال را تست کنید!')
        
        # محصولات قابل فروش
        products = self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('type', 'in', ['product', 'consu'])
        ], limit=10)
        
        if not products:
            raise UserError('محصولی برای همگام‌سازی یافت نشد!')
        
        # فعال کردن sync برای این محصولات
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
                _logger.info(f'Successfully synced: {product.name}')
            except Exception as e:
                error_count += 1
                error_msg = f'❌ {product.name}: {str(e)}'
                errors.append(error_msg)
                _logger.error(error_msg)
        
        message = f'📊 نتیجه همگام‌سازی کامل:\n\n'
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
                'title': 'همگام‌سازی کامل',
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
