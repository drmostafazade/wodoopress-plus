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
    
    # فیلدهای WooCommerce پایه
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
    
    # فیلدهای جدید
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
    
    woo_featured = fields.Boolean('محصول ویژه', default=False)
    woo_catalog_visibility = fields.Selection([
        ('visible', 'نمایش در فروشگاه و جستجو'),
        ('catalog', 'فقط در فروشگاه'),
        ('search', 'فقط در جستجو'),
        ('hidden', 'مخفی')
    ], string='نمایش در کاتالوگ', default='visible')
    
    def create(self, vals):
        """ایجاد محصول جدید با همگام‌سازی خودکار"""
        product = super().create(vals)
        
        if product.woo_sync_enabled and product.sale_ok:
            try:
                product.sync_to_woocommerce()
            except Exception as e:
                _logger.error(f"خطا در همگام‌سازی خودکار: {str(e)}")
        
        return product
    
    def write(self, vals):
        """بروزرسانی محصول با همگام‌سازی خودکار"""
        sync_fields = {
            'name', 'list_price', 'description', 'description_sale', 
            'description_purchase', 'default_code', 'barcode', 'weight', 
            'active', 'image_1920', 'categ_id', 'product_tag_ids',
            'qty_available', 'woo_brand_id', 'reordering_min_qty'
        }
        
        result = super().write(vals)
        
        if any(field in vals for field in sync_fields):
            for product in self:
                if product.woo_sync_enabled and product.sale_ok and product.woo_id:
                    try:
                        product.sync_to_woocommerce()
                    except Exception as e:
                        _logger.error(f"خطا در همگام‌سازی خودکار: {str(e)}")
        
        return result
    
    def sync_to_woocommerce(self):
        """همگام‌سازی کامل محصول با WooCommerce"""
        self.ensure_one()
        
        # دریافت تنظیمات
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        try:
            # آماده‌سازی داده‌ها
            product_data = self._prepare_product_data(config)
            
            # ارسال به WooCommerce
            if self.woo_id:
                result = self._update_woo_product(config, product_data)
            else:
                result = self._create_woo_product(config, product_data)
            
            # ذخیره نتیجه
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
            
        except Exception as e:
            _logger.error(f"خطا در همگام‌سازی: {str(e)}")
            raise UserError(f'خطا در همگام‌سازی: {str(e)}')
    
    def _prepare_product_data(self, config):
        """آماده‌سازی داده‌های محصول برای ارسال"""
        self.ensure_one()
        
        # داده‌های پایه
        data = {
            'name': self.name,
            'type': 'simple' if self.type == 'product' else 'virtual',
            'status': self.woo_status if self.active else 'draft',
            'featured': self.woo_featured,
            'catalog_visibility': self.woo_catalog_visibility,
            'description': self.description or '',
            'short_description': self.woo_short_description or self.description_sale or '',
            'sku': self.default_code or self.barcode or f'ODOO-{self.id}',
        }
        
        # قیمت‌ها
        data['regular_price'] = str(self.list_price)
        if hasattr(self, 'lst_price') and self.lst_price and self.lst_price < self.list_price:
            data['sale_price'] = str(self.lst_price)
        
        # موجودی
        data.update({
            'manage_stock': self.woo_manage_stock,
            'stock_quantity': int(self.qty_available),
            'stock_status': 'instock' if self.qty_available > 0 else 'outofstock',
            'backorders': self.woo_backorders,
            'low_stock_amount': int(self.reordering_min_qty) if self.reordering_min_qty else None,
        })
        
        # ابعاد و وزن
        if self.weight:
            data['weight'] = str(self.weight)
        
        # تصاویر
        if self.image_1920 and hasattr(config, 'sync_product_images') and config.sync_product_images:
            images = self._prepare_images(config)
            if images:
                data['images'] = images
        
        # دسته‌بندی‌ها
        if hasattr(config, 'sync_product_categories') and config.sync_product_categories:
            categories = self._prepare_categories(config)
            if categories:
                data['categories'] = categories
        
        # برچسب‌ها
        if hasattr(config, 'sync_product_tags') and config.sync_product_tags and self.product_tag_ids:
            tags = self._prepare_tags(config)
            if tags:
                data['tags'] = tags
        
        # ویژگی‌ها (برند و غیره)
        attributes = self._prepare_attributes()
        if attributes:
            data['attributes'] = attributes
        
        # محصولات مرتبط
        related = self._prepare_related_products()
        if related.get('cross_sell_ids'):
            data['cross_sell_ids'] = related['cross_sell_ids']
        if related.get('upsell_ids'):
            data['upsell_ids'] = related['upsell_ids']
        
        # Meta data
        meta_data = self._prepare_meta_data()
        if meta_data:
            data['meta_data'] = meta_data
        
        # تنظیمات اضافی
        data.update({
            'reviews_allowed': True,
            'sold_individually': False,
            'shipping_required': self.type == 'product',
            'shipping_taxable': True,
        })
        
        return data
    
    def _prepare_images(self, config):
        """آماده‌سازی تصاویر محصول"""
        images = []
        
        try:
            # تصویر اصلی
            if self.image_1920:
                image_id = self._upload_image_to_wordpress(
                    self.image_1920,
                    f"{self.name} - اصلی",
                    config
                )
                if image_id:
                    images.append({
                        'id': image_id,
                        'position': 0
                    })
            
            # گالری تصاویر (اگر مدل وجود داشته باشد)
            if hasattr(self, 'product_template_image_ids'):
                for idx, img in enumerate(self.product_template_image_ids, 1):
                    if img.image_1920:
                        gallery_id = self._upload_image_to_wordpress(
                            img.image_1920,
                            f"{self.name} - {idx}",
                            config
                        )
                        if gallery_id:
                            images.append({
                                'id': gallery_id,
                                'position': idx
                            })
            
            return images
            
        except Exception as e:
            _logger.error(f"خطا در آماده‌سازی تصاویر: {str(e)}")
            return []
    
    def _upload_image_to_wordpress(self, image_data, title, config):
        """آپلود تصویر به WordPress"""
        try:
            media_url = f"{config.store_url.rstrip('/')}/wp-json/wp/v2/media"
            image_binary = base64.b64decode(image_data)
            
            # تعیین نوع فایل
            mime_type = 'image/jpeg'
            extension = 'jpg'
            if image_binary.startswith(b'\x89PNG'):
                mime_type = 'image/png'
                extension = 'png'
            
            files = {
                'file': (f'{title}.{extension}', image_binary, mime_type)
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
    
    def _prepare_categories(self, config):
        """آماده‌سازی دسته‌بندی‌ها"""
        categories = []
        
        try:
            if self.categ_id:
                cat_id = self._get_or_create_woo_category(
                    self.categ_id.name,
                    config
                )
                if cat_id:
                    categories.append({'id': cat_id})
            
            # دسته‌بندی‌های عمومی (اگر وجود داشته باشد)
            if hasattr(self, 'public_categ_ids'):
                for categ in self.public_categ_ids:
                    cat_id = self._get_or_create_woo_category(
                        categ.name,
                        config
                    )
                    if cat_id:
                        categories.append({'id': cat_id})
            
            return categories
            
        except Exception as e:
            _logger.error(f"خطا در دسته‌بندی‌ها: {str(e)}")
            return []
    
    def _get_or_create_woo_category(self, name, config):
        """دریافت یا ایجاد دسته‌بندی در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/categories"
            
            # جستجو
            response = requests.get(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                params={'search': name},
                timeout=10
            )
            
            if response.status_code == 200:
                categories = response.json()
                for cat in categories:
                    if cat['name'] == name:
                        return cat['id']
                
                # ایجاد جدید
                create_response = requests.post(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json={'name': name},
                    timeout=30
                )
                
                if create_response.status_code == 201:
                    return create_response.json()['id']
            
        except Exception as e:
            _logger.error(f"خطا در دسته‌بندی {name}: {str(e)}")
        
        return None
    
    def _prepare_tags(self, config):
        """آماده‌سازی برچسب‌ها"""
        tags = []
        
        try:
            for tag in self.product_tag_ids:
                tag_id = self._get_or_create_woo_tag(tag.name, config)
                if tag_id:
                    tags.append({'id': tag_id})
            
            return tags
            
        except Exception as e:
            _logger.error(f"خطا در برچسب‌ها: {str(e)}")
            return []
    
    def _get_or_create_woo_tag(self, name, config):
        """دریافت یا ایجاد برچسب در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/tags"
            
            # جستجو
            response = requests.get(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                params={'search': name},
                timeout=10
            )
            
            if response.status_code == 200:
                tags = response.json()
                for tag in tags:
                    if tag['name'] == name:
                        return tag['id']
                
                # ایجاد جدید
                create_response = requests.post(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    json={'name': name},
                    timeout=30
                )
                
                if create_response.status_code == 201:
                    return create_response.json()['id']
            
        except Exception as e:
            _logger.error(f"خطا در برچسب {name}: {str(e)}")
        
        return None
    
    def _prepare_attributes(self):
        """آماده‌سازی ویژگی‌های محصول"""
        attributes = []
        
        # برند
        if self.woo_brand_id and self.woo_brand_id.name:
            attributes.append({
                'id': 0,
                'name': 'برند',
                'position': 0,
                'visible': True,
                'variation': False,
                'options': [self.woo_brand_id.name]
            })
        
        # بارکد
        if self.barcode:
            attributes.append({
                'id': 0,
                'name': 'بارکد',
                'position': 1,
                'visible': True,
                'variation': False,
                'options': [self.barcode]
            })
        
        # کشور مبدا (اگر وجود داشته باشد)
        if hasattr(self, 'country_of_origin_id') and self.country_of_origin_id:
            attributes.append({
                'id': 0,
                'name': 'کشور مبدا',
                'position': 2,
                'visible': True,
                'variation': False,
                'options': [self.country_of_origin_id.name]
            })
        
        return attributes
    
    def _prepare_related_products(self):
        """آماده‌سازی محصولات مرتبط"""
        related = {}
        
        # محصولات مکمل
        if hasattr(self, 'accessory_product_ids') and self.accessory_product_ids:
            cross_sell_ids = []
            for product in self.accessory_product_ids:
                if product.woo_id:
                    cross_sell_ids.append(product.woo_id)
            if cross_sell_ids:
                related['cross_sell_ids'] = cross_sell_ids
        
        # محصولات جایگزین
        if hasattr(self, 'alternative_product_ids') and self.alternative_product_ids:
            upsell_ids = []
            for product in self.alternative_product_ids:
                if product.woo_id:
                    upsell_ids.append(product.woo_id)
            if upsell_ids:
                related['upsell_ids'] = upsell_ids
        
        return related
    
    def _prepare_meta_data(self):
        """آماده‌سازی Meta Data"""
        meta_data = []
        
        # یادداشت خرید
        if self.description_purchase:
            meta_data.append({
                'key': '_purchase_note',
                'value': self.description_purchase
            })
        
        # کد تعرفه (اگر وجود داشته باشد)
        if hasattr(self, 'hs_code') and self.hs_code:
            meta_data.append({
                'key': '_hs_code',
                'value': self.hs_code
            })
        
        # شناسه Odoo
        meta_data.append({
            'key': '_odoo_id',
            'value': str(self.id)
        })
        
        # نشانگر مدیریت توسط Odoo
        meta_data.append({
            'key': '_managed_by_odoo',
            'value': 'true'
        })
        
        # تاریخ همگام‌سازی
        meta_data.append({
            'key': '_last_sync_from_odoo',
            'value': fields.Datetime.now().isoformat()
        })
        
        # قیمت خرید (اگر نیاز باشد)
        if self.standard_price:
            meta_data.append({
                'key': '_purchase_price',
                'value': str(self.standard_price)
            })
        
        return meta_data
    
    def _update_woo_product(self, config, product_data):
        """بروزرسانی محصول در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
            
            # بررسی وجود محصول
            check_response = requests.get(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                timeout=10
            )
            
            if check_response.status_code == 404:
                # محصول حذف شده، ایجاد مجدد
                self.woo_id = False
                return self._create_woo_product(config, product_data)
            
            # بروزرسانی
            response = requests.put(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                json=product_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return response.json()
            else:
                raise UserError(f'خطا در بروزرسانی: {response.status_code}\n{response.text}')
                
        except Exception as e:
            raise UserError(f'خطا در بروزرسانی: {str(e)}')
    
    def _create_woo_product(self, config, product_data):
        """ایجاد محصول جدید در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products"
            
            response = requests.post(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                json=product_data,
                timeout=30
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                raise UserError(f'خطا در ایجاد: {response.status_code}\n{response.text}')
                
        except Exception as e:
            raise UserError(f'خطا در ایجاد: {str(e)}')


class ProductBrand(models.Model):
    _inherit = 'product.brand'
    
    woo_brand_id = fields.Integer('شناسه برند در WooCommerce', readonly=True)


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
        """همگام‌سازی خودکار موجودی"""
        quant = super().create(vals)
        self._sync_product_stock(quant)
        return quant
    
    def write(self, vals):
        """همگام‌سازی خودکار موجودی"""
        result = super().write(vals)
        for quant in self:
            self._sync_product_stock(quant)
        return result
    
    def _sync_product_stock(self, quant):
        """همگام‌سازی موجودی با WooCommerce"""
        if (quant.location_id.usage == 'internal' and 
            quant.product_id.product_tmpl_id.woo_sync_enabled and
            quant.product_id.product_tmpl_id.woo_id):
            
            config = self.env['woo.config'].search([
                ('active', '=', True),
                ('sync_inventory_real_time', '=', True)
            ], limit=1)
            
            if config:
                try:
                    url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{quant.product_id.product_tmpl_id.woo_id}"
                    
                    stock_data = {
                        'stock_quantity': int(quant.product_id.product_tmpl_id.qty_available),
                        'stock_status': 'instock' if quant.product_id.product_tmpl_id.qty_available > 0 else 'outofstock'
                    }
                    
                    response = requests.put(
                        url,
                        auth=(config.consumer_key, config.consumer_secret),
                        json=stock_data,
                        timeout=10
                    )
                    
                    if response.status_code in [200, 201]:
                        _logger.info(f"موجودی {quant.product_id.name} همگام‌سازی شد")
                    
                except Exception as e:
                    _logger.error(f"خطا در همگام‌سازی موجودی: {str(e)}")


class WooConfig(models.Model):
    _inherit = 'woo.config'
    
    def sync_all_products(self):
        """همگام‌سازی همه محصولات فعال"""
        self.ensure_one()
        
        if self.connection_status != 'connected':
            raise ValidationError('ابتدا اتصال را تست کنید!')
        
        products = self.env['product.template'].search([
            ('sale_ok', '=', True),
            ('type', 'in', ['product', 'consu'])
        ], limit=10)
        
        if not products:
            raise ValidationError('محصولی برای همگام‌سازی یافت نشد!')
        
        products.write({'woo_sync_enabled': True})
        
        success_count = 0
        error_count = 0
        errors = []
        
        for product in products:
            try:
                product.sync_to_woocommerce()
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f'{product.name}: {str(e)}')
        
        message = f'نتیجه همگام‌سازی:\n'
        message += f'✅ موفق: {success_count} محصول\n'
        message += f'❌ خطا: {error_count} محصول'
        
        if errors:
            message += '\n\nخطاها:\n' + '\n'.join(errors[:5])
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'همگام‌سازی انجام شد',
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
