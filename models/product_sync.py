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
    
    # فیلدهای جدید برای کنترل بهتر
    woo_featured = fields.Boolean('محصول ویژه', default=False)
    woo_catalog_visibility = fields.Selection([
        ('visible', 'نمایش در فروشگاه و جستجو'),
        ('catalog', 'فقط در فروشگاه'),
        ('search', 'فقط در جستجو'),
        ('hidden', 'مخفی')
    ], string='نمایش در کاتالوگ', default='visible')
    
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
        sync_fields = {
            'name', 'list_price', 'standard_price', 'description', 
            'description_sale', 'description_purchase', 'default_code', 
            'barcode', 'weight', 'volume', 'active', 'image_1920', 
            'categ_id', 'public_categ_ids', 'product_tag_ids',
            'product_length', 'product_width', 'product_height',
            'qty_available', 'accessory_product_ids', 'alternative_product_ids',
            'woo_brand_id', 'hs_code', 'country_of_origin_id'
        }
        
        result = super().write(vals)
        
        # بررسی نیاز به همگام‌سازی
        if any(field in vals for field in sync_fields):
            for product in self:
                if product.woo_sync_enabled and product.sale_ok:
                    try:
                        product.with_delay().sync_to_woocommerce()
                    except:
                        product.sync_to_woocommerce()
        
        return result
    
    def sync_to_woocommerce(self):
        """همگام‌سازی کامل و جامع محصول با WooCommerce"""
        self.ensure_one()
        
        # دریافت تنظیمات فعال
        config = self.env['woo.config'].search([
            ('active', '=', True),
            ('connection_status', '=', 'connected')
        ], limit=1)
        
        if not config:
            raise UserError('تنظیمات فعال WooCommerce یافت نشد!')
        
        try:
            # آماده‌سازی داده‌ها برای ارسال
            product_data = self._prepare_woocommerce_data(config)
            
            # ارسال به WooCommerce
            if self.woo_id:
                # بروزرسانی محصول موجود
                result = self._update_woocommerce_product(config, product_data)
            else:
                # ایجاد محصول جدید
                result = self._create_woocommerce_product(config, product_data)
            
            # ذخیره اطلاعات همگام‌سازی
            self.write({
                'woo_id': result.get('id'),
                'woo_last_sync': fields.Datetime.now()
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'همگام‌سازی موفق',
                    'message': f'محصول {self.name} با تمام جزئیات همگام‌سازی شد',
                    'type': 'success',
                }
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(f'خطا در ارتباط: {str(e)}')
    
    def _prepare_woocommerce_data(self, config):
        """آماده‌سازی کامل داده‌های محصول برای WooCommerce"""
        self.ensure_one()
        
        # 1. داده‌های پایه
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
        
        # 2. قیمت‌ها
        data.update({
            'regular_price': str(self.list_price),
            'sale_price': str(self.lst_price) if hasattr(self, 'lst_price') and self.lst_price < self.list_price else '',
        })
        
        # 3. موجودی انبار
        data.update({
            'manage_stock': True,
            'stock_quantity': int(self.qty_available),
            'stock_status': 'instock' if self.qty_available > 0 else 'outofstock',
            'backorders': getattr(self, 'woo_backorders', 'no'),
            'low_stock_amount': int(getattr(self, 'reordering_min_qty', 5)),
        })
        
        # 4. ابعاد و وزن
        data['weight'] = str(self.weight) if self.weight else ''
        
        dimensions = {}
        if hasattr(self, 'product_length') and self.product_length:
            dimensions['length'] = str(self.product_length)
        if hasattr(self, 'product_width') and self.product_width:
            dimensions['width'] = str(self.product_width)
        if hasattr(self, 'product_height') and self.product_height:
            dimensions['height'] = str(self.product_height)
        
        if dimensions:
            data['dimensions'] = dimensions
        
        # 5. تصاویر (اصلی + گالری)
        images = self._prepare_product_images(config)
        if images:
            data['images'] = images
        
        # 6. دسته‌بندی‌ها
        categories = self._prepare_product_categories(config)
        if categories:
            data['categories'] = categories
        
        # 7. برچسب‌ها
        tags = self._prepare_product_tags(config)
        if tags:
            data['tags'] = tags
        
        # 8. ویژگی‌ها (Attributes)
        attributes = self._prepare_product_attributes()
        if attributes:
            data['attributes'] = attributes
        
        # 9. محصولات مرتبط
        if self.accessory_product_ids:
            cross_sell_ids = [p.woo_id for p in self.accessory_product_ids if p.woo_id]
            if cross_sell_ids:
                data['cross_sell_ids'] = cross_sell_ids
        
        if self.alternative_product_ids:
            upsell_ids = [p.woo_id for p in self.alternative_product_ids if p.woo_id]
            if upsell_ids:
                data['upsell_ids'] = upsell_ids
        
        # 10. Meta Data (اطلاعات اضافی)
        meta_data = self._prepare_meta_data()
        if meta_data:
            data['meta_data'] = meta_data
        
        # 11. سایر تنظیمات
        data.update({
            'reviews_allowed': True,
            'sold_individually': False,
            'shipping_required': self.type == 'product',
            'shipping_taxable': True,
        })
        
        return data
    
    def _prepare_product_images(self, config):
        """آماده‌سازی و آپلود تصاویر محصول"""
        images = []
        
        try:
            # تصویر اصلی
            if self.image_1920:
                main_image_id = self._upload_image_to_wordpress(
                    self.image_1920,
                    f"{self.name} - Main",
                    config
                )
                if main_image_id:
                    images.append({
                        'id': main_image_id,
                        'position': 0,
                        'name': self.name,
                        'alt': self.name
                    })
            
            # گالری تصاویر
            if hasattr(self, 'product_template_image_ids'):
                for idx, img in enumerate(self.product_template_image_ids, 1):
                    if img.image_1920:
                        gallery_image_id = self._upload_image_to_wordpress(
                            img.image_1920,
                            f"{self.name} - Gallery {idx}",
                            config
                        )
                        if gallery_image_id:
                            images.append({
                                'id': gallery_image_id,
                                'position': idx,
                                'name': img.name or f"{self.name} {idx}",
                                'alt': img.name or self.name
                            })
            
            _logger.info(f"تعداد {len(images)} تصویر برای {self.name} آماده شد")
            return images
            
        except Exception as e:
            _logger.error(f"خطا در آماده‌سازی تصاویر: {str(e)}")
            return []
    
    def _upload_image_to_wordpress(self, image_data, title, config):
        """آپلود تصویر به WordPress Media Library"""
        try:
            media_url = f"{config.store_url.rstrip('/')}/wp-json/wp/v2/media"
            
            # تبدیل base64 به binary
            image_binary = base64.b64decode(image_data)
            
            # تعیین نوع فایل
            mime_type = 'image/jpeg'
            extension = 'jpg'
            
            if image_binary.startswith(b'\x89PNG'):
                mime_type = 'image/png'
                extension = 'png'
            elif image_binary.startswith(b'GIF'):
                mime_type = 'image/gif'
                extension = 'gif'
            
            # آماده‌سازی فایل
            filename = f"{title.replace(' ', '-').lower()}.{extension}"
            files = {
                'file': (filename, image_binary, mime_type)
            }
            
            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
            
            # ارسال درخواست
            response = requests.post(
                media_url,
                auth=(config.consumer_key, config.consumer_secret),
                files=files,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 201:
                result = response.json()
                _logger.info(f"تصویر {title} با موفقیت آپلود شد: ID={result['id']}")
                return result['id']
            else:
                _logger.error(f"خطا در آپلود تصویر: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            _logger.error(f"خطا در آپلود تصویر {title}: {str(e)}")
            return None
    
    def _prepare_product_categories(self, config):
        """آماده‌سازی دسته‌بندی‌های محصول"""
        categories = []
        
        try:
            # دسته‌بندی داخلی
            if self.categ_id:
                cat_id = self._get_or_create_woo_category(
                    self.categ_id.complete_name,
                    config
                )
                if cat_id:
                    categories.append({'id': cat_id})
            
            # دسته‌بندی‌های عمومی (وب‌سایت)
            if hasattr(self, 'public_categ_ids') and self.public_categ_ids:
                for categ in self.public_categ_ids:
                    cat_id = self._get_or_create_woo_category(
                        categ.complete_name,
                        config
                    )
                    if cat_id:
                        categories.append({'id': cat_id})
            
            return categories
            
        except Exception as e:
            _logger.error(f"خطا در آماده‌سازی دسته‌بندی‌ها: {str(e)}")
            return []
    
    def _get_or_create_woo_category(self, category_path, config):
        """دریافت یا ایجاد دسته‌بندی در WooCommerce"""
        try:
            # تجزیه مسیر دسته‌بندی
            parts = category_path.split(' / ')
            parent_id = 0
            
            for part in parts:
                # جستجو یا ایجاد هر سطح
                url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/categories"
                
                # جستجو
                params = {'search': part, 'parent': parent_id}
                response = requests.get(
                    url,
                    auth=(config.consumer_key, config.consumer_secret),
                    params=params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    categories = response.json()
                    
                    # پیدا کردن دسته‌بندی
                    found = False
                    for cat in categories:
                        if cat['name'] == part and cat['parent'] == parent_id:
                            parent_id = cat['id']
                            found = True
                            break
                    
                    # اگر پیدا نشد، ایجاد کن
                    if not found:
                        cat_data = {
                            'name': part,
                            'parent': parent_id,
                            'display': 'default',
                            'menu_order': 0
                        }
                        
                        create_response = requests.post(
                            url,
                            auth=(config.consumer_key, config.consumer_secret),
                            json=cat_data,
                            timeout=30
                        )
                        
                        if create_response.status_code == 201:
                            parent_id = create_response.json()['id']
                            _logger.info(f"دسته‌بندی {part} ایجاد شد")
            
            return parent_id
            
        except Exception as e:
            _logger.error(f"خطا در مدیریت دسته‌بندی {category_path}: {str(e)}")
            return None
    
    def _prepare_product_tags(self, config):
        """آماده‌سازی برچسب‌های محصول"""
        tags = []
        
        try:
            for tag in self.product_tag_ids:
                tag_id = self._get_or_create_woo_tag(tag.name, config)
                if tag_id:
                    tags.append({'id': tag_id})
            
            return tags
            
        except Exception as e:
            _logger.error(f"خطا در آماده‌سازی برچسب‌ها: {str(e)}")
            return []
    
    def _get_or_create_woo_tag(self, tag_name, config):
        """دریافت یا ایجاد برچسب در WooCommerce"""
        try:
            url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/tags"
            
            # جستجو
            params = {'search': tag_name}
            response = requests.get(
                url,
                auth=(config.consumer_key, config.consumer_secret),
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                tags = response.json()
                
                # بررسی وجود
                for tag in tags:
                    if tag['name'] == tag_name:
                        return tag['id']
                
                # ایجاد برچسب جدید
                tag_data = {
                    'name': tag_name,
                    'description': ''
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
            _logger.error(f"خطا در مدیریت برچسب {tag_name}: {str(e)}")
            return None
    
    def _prepare_product_attributes(self):
        """آماده‌سازی ویژگی‌های محصول"""
        attributes = []
        position = 0
        
        # برند
        if self.woo_brand_id and self.woo_brand_id.name:
            attributes.append({
                'id': 0,
                'name': 'برند',
                'position': position,
                'visible': True,
                'variation': False,
                'options': [self.woo_brand_id.name]
            })
            position += 1
        
        # بارکد
        if self.barcode:
            attributes.append({
                'id': 0,
                'name': 'بارکد',
                'position': position,
                'visible': True,
                'variation': False,
                'options': [self.barcode]
            })
            position += 1
        
        # کشور مبدا
        if hasattr(self, 'country_of_origin_id') and self.country_of_origin_id:
            attributes.append({
                'id': 0,
                'name': 'کشور مبدا',
                'position': position,
                'visible': True,
                'variation': False,
                'options': [self.country_of_origin_id.name]
            })
            position += 1
        
        # ویژگی‌های محصول از attribute_line_ids
        if hasattr(self, 'attribute_line_ids'):
            for line in self.attribute_line_ids:
                options = [v.name for v in line.value_ids]
                if options:
                    attributes.append({
                        'id': 0,
                        'name': line.attribute_id.name,
                        'position': position,
                        'visible': True,
                        'variation': False,
                        'options': options
                    })
                    position += 1
        
        return attributes
    
    def _prepare_meta_data(self):
        """آماده‌سازی Meta Data برای ذخیره اطلاعات اضافی"""
        meta_data = []
        
        # یادداشت خرید
        if self.description_purchase:
            meta_data.append({
                'key': '_purchase_note',
                'value': self.description_purchase
            })
        
        # کد تعرفه گمرکی
        if hasattr(self, 'hs_code') and self.hs_code:
            meta_data.append({
                'key': '_hs_code',
                'value': self.hs_code
            })
        
        # مرجع داخلی Odoo
        meta_data.append({
            'key': '_odoo_id',
            'value': str(self.id)
        })
        
        # نشانگر مدیریت توسط Odoo
        meta_data.append({
            'key': '_managed_by_odoo',
            'value': 'true'
        })
        
        # تاریخ آخرین همگام‌سازی
        meta_data.append({
            'key': '_last_sync_from_odoo',
            'value': fields.Datetime.now().isoformat()
        })
        
        # قیمت خرید (برای گزارش‌های داخلی)
        if self.standard_price:
            meta_data.append({
                'key': '_purchase_price',
                'value': str(self.standard_price)
            })
        
        # حجم محصول
        if self.volume:
            meta_data.append({
                'key': '_volume',
                'value': str(self.volume)
            })
        
        # موجودی مجازی
        if hasattr(self, 'virtual_available'):
            meta_data.append({
                'key': '_virtual_stock',
                'value': str(self.virtual_available)
            })
        
        # کلاس مالیاتی
        if self.taxes_id:
            tax_names = ', '.join(self.taxes_id.mapped('name'))
            meta_data.append({
                'key': '_tax_class',
                'value': tax_names
            })
        
        return meta_data
    
    def _update_woocommerce_product(self, config, product_data):
        """بروزرسانی محصول موجود در WooCommerce"""
        try:
            # بررسی وجود محصول
            check_url = f"{config.store_url.rstrip('/')}/wp-json/wc/v3/products/{self.woo_id}"
            check_response = requests.get(
                check_url,
                auth=(config.consumer_key, config.consumer_secret),
                timeout=10
            )
            
            if check_response.status_code == 404:
                # محصول حذف شده، ایجاد مجدد
                _logger.warning(f"محصول {self.name} در WooCommerce یافت نشد، ایجاد مجدد...")
                self.woo_id = False
                return self._create_woocommerce_product(config, product_data)
            
            # بروزرسانی محصول
            response = requests.put(
                check_url,
                auth=(config.consumer_key, config.consumer_secret),
                json=product_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                _logger.info(f"محصول {self.name} با موفقیت بروزرسانی شد")
                return result
            else:
                raise UserError(
                    f'خطا در بروزرسانی محصول: {response.status_code}\n'
                    f'{response.text}'
                )
                
        except Exception as e:
            raise UserError(f'خطا در بروزرسانی محصول: {str(e)}')
    
    def _create_woocommerce_product(self, config, product_data):
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
                result = response.json()
                _logger.info(f"محصول {self.name} با موفقیت ایجاد شد")
                return result
            else:
                raise UserError(
                    f'خطا در ایجاد محصول: {response.status_code}\n'
                    f'{response.text}'
                )
                
        except Exception as e:
            raise UserError(f'خطا در ایجاد محصول: {str(e)}')


class ProductBrand(models.Model):
    _inherit = 'product.brand'
    
    woo_brand_id = fields.Integer('شناسه برند در WooCommerce', readonly=True)


class ProductTag(models.Model):
    _inherit = 'product.tag'
    
    woo_tag_id = fields.Integer('شناسه برچسب WooCommerce', readonly=True)


class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    woo_category_id = fields.Integer('شناسه دسته‌بندی WooCommerce', readonly=True)


class ProductImage(models.Model):
    _inherit = 'product.image'
    
    woo_image_id = fields.Integer('شناسه تصویر WooCommerce', readonly=True)
    woo_image_url = fields.Char('آدرس تصویر در WooCommerce')


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
            
            if config and quant.product_id.product_tmpl_id.woo_id:
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
                        _logger.info(f"موجودی {quant.product_id.name} بروزرسانی شد")
                    
                except Exception as e:
                    _logger.error(f"خطا در همگام‌سازی موجودی: {str(e)}")
