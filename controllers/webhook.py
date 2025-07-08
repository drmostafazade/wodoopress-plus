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
            
            # بررسی که آیا محصول توسط Odoo مدیریت می‌شود
            meta_data = data.get('meta_data', [])
            for meta in meta_data:
                if meta.get('key') == '_managed_by_odoo' and meta.get('value') == 'true':
                    _logger.info(f"محصول {data.get('name')} توسط Odoo مدیریت می‌شود - تغییرات نادیده گرفته شد")
                    return {'status': 'ignored', 'message': 'Product managed by Odoo'}
            
            # اگر محصول توسط Odoo مدیریت نمی‌شود، می‌توان تغییرات را اعمال کرد
            # TODO: پیاده‌سازی sync از WooCommerce به Odoo
            
            return {'status': 'success'}
            
        except Exception as e:
            _logger.error(f"خطا در webhook: {str(e)}")
            return {'status': 'error', 'message': str(e)}
