# Debug Log - 2025-01-08

## مشکل: Internal Server Error

### اقدامات انجام شده:
1. حذف product_extensions.py
2. حذف controllers
3. تصحیح models/__init__.py
4. ساده‌سازی __manifest__.py
5. پاکسازی cache

### وضعیت فایل‌ها:
- models/woo_config.py ✅
- models/product_sync.py ✅
- models/product_brand.py ✅
- views/*.xml ✅
- security/ir.model.access.csv ✅

### مرحله بعد:
اگر همچنان خطا دارد، لاگ کامل را بررسی کنید
