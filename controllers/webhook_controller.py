# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging
import hmac
import hashlib

_logger = logging.getLogger(__name__)


class WooCommerceWebhook(http.Controller):
    
    @http.route('/woocommerce/webhook/product', type='json', auth='none', methods=['POST'], csrf=False)
    def product_webhook(self, **kwargs):
        """دریافت تغییرات محصول از WooCommerce"""
        try:
            # بررسی امضای webhook
            if not self._verify_webhook_signature():
                return {'status': 'error', 'message': 'Invalid signature'}
            
            # دریافت داده‌های محصول
            data = request.jsonrequest
            
            # بررسی اینکه محصول توسط Odoo مدیریت می‌شود
            meta_data = data.get('meta_data', [])
            managed_by_odoo = False
            
            for meta in meta_data:
                if meta.get('key') == '_managed_by_odoo' and meta.get('value') == 'true':
                    managed_by_odoo = True
                    break
            
            # اگر محصول توسط Odoo مدیریت می‌شود، تغییرات WooCommerce را نادیده بگیر
            if managed_by_odoo:
                _logger.info(f"تغییرات محصول {data.get('name')} نادیده گرفته شد - مدیریت توسط Odoo")
                return {'status': 'ignored', 'message': 'Product managed by Odoo'}
            
            # در غیر این صورت، تغییرات را در Odoo اعمال کن
            self._sync_from_woocommerce(data)
            
            return {'status': 'success'}
            
        except Exception as e:
            _logger.error(f"خطا در webhook: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _verify_webhook_signature(self):
        """بررسی امضای webhook"""
        # دریافت تنظیمات فعال
        config = request.env['woo.config'].sudo().search([
            ('active', '=', True)
        ], limit=1)
        
        if not config or not config.webhook_secret:
            return False
        
        # دریافت امضا از header
        signature = request.httprequest.headers.get('X-WC-Webhook-Signature')
        if not signature:
            return False
        
        # محاسبه امضای مورد انتظار
        body = request.httprequest.get_data()
        expected_signature = hmac.new(
            config.webhook_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # مقایسه امضاها
        return hmac.compare_digest(signature, expected_signature)
    
    def _sync_from_woocommerce(self, data):
        """همگام‌سازی محصول از WooCommerce به Odoo"""
        try:
            # جستجوی محصول بر اساس SKU
            sku = data.get('sku')
            if not sku:
                return
            
            product = request.env['product.template'].sudo().search([
                '|',
                ('default_code', '=', sku),
                ('barcode', '=', sku)
            ], limit=1)
            
            if not product:
                # ایجاد محصول جدید
                self._create_product_from_woo(data)
            else:
                # بروزرسانی محصول موجود
                self._update_product_from_woo(product, data)
                
        except Exception as e:
            _logger.error(f"خطا در همگام‌سازی از WooCommerce: {str(e)}")
    
    def _create_product_from_woo(self, data):
        """ایجاد محصول جدید از داده‌های WooCommerce"""
        vals = {
            'name': data.get('name'),
            'default_code': data.get('sku'),
            'list_price': float(data.get('regular_price', 0)),
            'description': data.get('description', ''),
            'description_sale': data.get('short_description', ''),
            'woo_id': data.get('id'),
            'woo_sync_enabled': False,  # غیرفعال تا از loop جلوگیری شود
            'sale_ok': True,
            'purchase_ok': True,
            'type': 'product',
        }
        
        # قیمت فروش ویژه
        if data.get('sale_price'):
            vals['lst_price'] = float(data['sale_price'])
        
        # وزن
        if data.get('weight'):
            vals['weight'] = float(data['weight'])
        
        product = request.env['product.template'].sudo().create(vals)
        _logger.info(f"محصول جدید از WooCommerce ایجاد شد: {product.name}")
    
    def _update_product_from_woo(self, product, data):
        """بروزرسانی محصول موجود از داده‌های WooCommerce"""
        vals = {}
        
        # فقط فیلدهایی که در Odoo خالی هستند را بروزرسانی کن
        if not product.name:
            vals['name'] = data.get('name')
        
        if not product.description:
            vals['description'] = data.get('description', '')
        
        if not product.description_sale:
            vals['description_sale'] = data.get('short_description', '')
        
        # همیشه قیمت و موجودی را بروزرسانی کن
        vals['list_price'] = float(data.get('regular_price', 0))
        
        if data.get('sale_price'):
            vals['lst_price'] = float(data['sale_price'])
        
        # ذخیره WooCommerce ID
        vals['woo_id'] = data.get('id')
        
        if vals:
            product.sudo().write(vals)
            _logger.info(f"محصول {product.name} از WooCommerce بروزرسانی شد")


class WooCommerceWebhookConfig(http.Controller):
    
    @http.route('/woocommerce/webhook/test', type='http', auth='none', methods=['GET'])
    def test_webhook(self):
        """تست webhook endpoint"""
        return "WooCommerce Webhook is active!"
