#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
تحلیل کامل فیلدهای محصول در Odoo 18
و نحوه mapping آنها به WooCommerce
"""

ODOO_TO_WOOCOMMERCE_MAPPING = {
    # اطلاعات پایه
    'name': 'name',  # نام محصول
    'default_code': 'sku',  # کد محصول/SKU
    'barcode': 'sku',  # بارکد (اگر default_code نباشد)
    'active': 'status',  # فعال/غیرفعال → publish/draft
    
    # قیمت‌ها
    'list_price': 'regular_price',  # قیمت فروش
    'standard_price': None,  # قیمت خرید (در WooCommerce نیست)
    'lst_price': 'sale_price',  # قیمت تخفیف‌خورده
    
    # توضیحات
    'description': 'description',  # توضیحات کامل
    'description_sale': 'short_description',  # توضیحات کوتاه
    'description_purchase': '_purchase_note',  # یادداشت خرید (meta_data)
    
    # موجودی و انبار
    'qty_available': 'stock_quantity',  # موجودی فعلی
    'virtual_available': None,  # موجودی پیش‌بینی شده
    'incoming_qty': None,  # در راه
    'outgoing_qty': None,  # رزرو شده
    
    # ابعاد و وزن
    'weight': 'weight',  # وزن
    'volume': None,  # حجم (محاسبه از ابعاد)
    'product_length': 'dimensions.length',  # طول
    'product_width': 'dimensions.width',  # عرض
    'product_height': 'dimensions.height',  # ارتفاع
    
    # تصاویر
    'image_1920': 'images[0]',  # تصویر اصلی
    'product_template_image_ids': 'images[1:]',  # گالری تصاویر
    
    # دسته‌بندی‌ها
    'categ_id': 'categories',  # دسته‌بندی داخلی
    'public_categ_ids': 'categories',  # دسته‌بندی‌های عمومی
    
    # برچسب‌ها و ویژگی‌ها
    'product_tag_ids': 'tags',  # برچسب‌ها
    'attribute_line_ids': 'attributes',  # ویژگی‌های محصول
    
    # محصولات مرتبط
    'accessory_product_ids': 'cross_sell_ids',  # محصولات مکمل
    'alternative_product_ids': 'upsell_ids',  # محصولات جایگزین
    
    # نوع محصول
    'type': 'type',  # product/service → simple/virtual
    'sale_ok': 'purchasable',  # قابل فروش
    'purchase_ok': None,  # قابل خرید (Odoo only)
    
    # مالیات
    'taxes_id': '_tax_class',  # کلاس مالیاتی (meta_data)
    
    # سایر
    'hs_code': '_hs_code',  # کد تعرفه گمرکی (meta_data)
    'country_of_origin_id': '_country_of_origin',  # کشور مبدا (meta_data)
    'product_brand_id': 'attributes[brand]',  # برند
}

# فیلدهای اضافی WooCommerce که باید مدیریت شوند
WOOCOMMERCE_SPECIFIC_FIELDS = {
    'featured': False,  # محصول ویژه
    'catalog_visibility': 'visible',  # نمایش در کاتالوگ
    'reviews_allowed': True,  # اجازه نظرات
    'sold_individually': False,  # فروش تکی
    'shipping_required': True,  # نیاز به ارسال
    'shipping_taxable': True,  # مالیات حمل
    'manage_stock': True,  # مدیریت موجودی
    'stock_status': 'instock',  # وضعیت موجودی
    'backorders': 'no',  # سفارش‌های backorder
    'low_stock_amount': 5,  # آستانه کم‌بودن موجودی
}

print("=== فیلدهای محصول Odoo 18 و نحوه انتقال به WooCommerce ===\n")

# نمایش mapping
for odoo_field, woo_field in ODOO_TO_WOOCOMMERCE_MAPPING.items():
    if woo_field:
        print(f"✅ {odoo_field:30} → {woo_field}")
    else:
        print(f"⚠️  {odoo_field:30} → [فقط در Odoo]")

print("\n=== فیلدهای اختصاصی WooCommerce ===")
for field, default in WOOCOMMERCE_SPECIFIC_FIELDS.items():
    print(f"📌 {field:30} = {default}")
