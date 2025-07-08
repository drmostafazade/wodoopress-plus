# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class WooWebhook(http.Controller):
    
    @http.route('/woocommerce/webhook/product', type='json', auth='public', methods=['POST'], csrf=False)
    def product_webhook(self, **kwargs):
        """دریافت تغییرات محصول از WooCommerce"""
        try:
            data = request.jsonrequest
            
            # بررسی meta data
            meta_data = data.get('meta_data', [])
            for meta in meta_data:
                if meta.get('key') == '_managed_by_odoo' and meta.get('value') == 'true':
                    _logger.info(f"محصول {data.get('name')} توسط Odoo مدیریت می‌شود - نادیده گرفته شد")
                    return {'status': 'ignored', 'message': 'Product managed by Odoo'}
            
            # اگر محصول توسط Odoo مدیریت نمی‌شود، می‌توان sync کرد
            # TODO: پیاده‌سازی sync از WooCommerce به Odoo در آینده
            
            return {'status': 'success'}
            
        except Exception as e:
            _logger.error(f"خطا در webhook: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/woocommerce/webhook/test', type='http', auth='none', methods=['GET'])
    def test_webhook(self):
        """تست webhook endpoint"""
        return "WooCommerce Webhook is active!"
