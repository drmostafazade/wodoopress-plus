# WodooPress Plus - Development Tasks

## 🎯 Project Overview
یکپارچه‌سازی حرفه‌ای WordPress WooCommerce با Odoo 18 Enterprise

## 📊 Development Phases

### Phase 1: Base Structure ✅
- [x] ایجاد ساختار پایه ماژول
- [x] فایل `__manifest__.py`
- [x] مدل `woo.config` برای تنظیمات
- [x] رابط کاربری تنظیمات
- [x] تست اتصال به WooCommerce
- [x] منوی اصلی و زیرمنوها
- [x] دسترسی‌ها (security)
- [x] نصب موفق در Odoo 18

### Phase 2: Product Sync Basic 🔄 (در حال انجام)
- [x] مدل `product_sync.py`
- [x] افزودن فیلدهای WooCommerce به محصولات
- [x] متد `sync_to_woocommerce`
- [x] دکمه همگام‌سازی در محصولات
- [x] دکمه همگام‌سازی گروهی در تنظیمات
- [ ] تست موفق همگام‌سازی با WooCommerce واقعی
- [ ] مدیریت خطاها و لاگ
- [ ] webhook دریافت محصولات از WooCommerce

### Phase 3: Variable Products 📦 (آینده)
- [ ] پشتیبانی از محصولات متغیر
- [ ] همگام‌سازی attributes
- [ ] همگام‌سازی variations
- [ ] مدیریت ترکیب‌های محصول
- [ ] قیمت‌گذاری برای هر variant
- [ ] موجودی برای هر variant

### Phase 4: Orders & Inventory 🛒 (آینده)
- [ ] دریافت سفارشات از WooCommerce
- [ ] ایجاد خودکار Sale Order در Odoo
- [ ] mapping وضعیت سفارشات
- [ ] همگام‌سازی real-time موجودی
- [ ] مدیریت چند انبار
- [ ] بروزرسانی وضعیت سفارش به WooCommerce

### Phase 5: Multi-currency & Customers 💱 (آینده)
- [ ] پشتیبانی چندارزی
- [ ] نرخ تبدیل ارز
- [ ] همگام‌سازی مشتریان
- [ ] ایجاد خودکار res.partner
- [ ] گروه‌بندی مشتریان
- [ ] تاریخچه خرید مشتریان

### Phase 6: Dashboard & Reporting 📈 (آینده)
- [ ] داشبورد مدیریتی
- [ ] آمار همگام‌سازی
- [ ] گزارش خطاها
- [ ] نمودارهای تحلیلی
- [ ] گزارش‌های قابل export
- [ ] هشدارها و نوتیفیکیشن‌ها

## 🔧 Technical Tasks

### Infrastructure
- [x] Git repository setup
- [x] Screen session management
- [x] Auto-sync script
- [ ] CI/CD pipeline
- [ ] Automated testing

### Documentation
- [x] README.md
- [x] PROGRESS.md
- [x] In-code documentation (Persian/English)
- [ ] User manual
- [ ] API documentation
- [ ] Video tutorials

### Security & Performance
- [ ] Webhook signature validation
- [ ] Rate limiting
- [ ] Caching mechanism
- [ ] Batch processing
- [ ] Error recovery

## 🐛 Known Issues
- [x] XML syntax error in views (Fixed)
- [x] Tree view to List view migration for Odoo 18 (Fixed)
- [ ] Product sync with real WooCommerce endpoint
- [ ] Duplicate column error on upgrade

## 📝 Notes
- تمام داده‌ها از فیلدهای موجود Odoo خوانده می‌شوند
- WooCommerce فقط receiver است، Odoo منبع اصلی داده
- استفاده از SKU های Odoo برای شناسایی محصولات

---
آخرین بروزرسانی: 2025-01-07 22:15

## 🐛 Fixed Issues
- [x] مدیریت محصولات حذف شده از WooCommerce
- [x] همگام‌سازی خودکار هنگام create/update در Odoo

## 🔄 Current Issues
- [ ] همگام‌سازی تصاویر به WordPress Media Library
- [ ] همگام‌سازی دسته‌بندی‌ها
- [ ] همگام‌سازی برچسب‌ها و برندها

---
آخرین بروزرسانی: 2025-01-07 22:25

### Phase 2 Updates - Complete Sync ✅
- [x] همگام‌سازی کامل تصاویر (اصلی و گالری)
- [x] آپلود به WordPress Media Library
- [x] همگام‌سازی دسته‌بندی‌ها با ایجاد خودکار
- [x] همگام‌سازی برچسب‌ها
- [x] مدل برند محصولات
- [x] همگام‌سازی ابعاد و وزن
- [x] همگام‌سازی بارکد/GTIN
- [x] همگام‌سازی real-time موجودی
- [x] ذخیره metadata اضافی

---
آخرین بروزرسانی: $(date '+%Y-%m-%d %H:%M')

## 🔧 آخرین وضعیت - 2025-01-08

### مشکلات برطرف شده:
- [x] خطای Internal Server Error
- [x] خطای XML syntax در views
- [x] اضافه کردن متدهای sync_all_products و reset_all_woo_ids
- [x] ایجاد مدل product.brand در فایل جداگانه
- [x] اضافه کردن فیلدهای تنظیمات همگام‌سازی

### آماده برای:
- [ ] تست نهایی همگام‌سازی با WooCommerce واقعی
- [ ] شروع Phase 3: Variable Products

---
آخرین بروزرسانی: 2025-01-08

## 🆕 بروزرسانی 2025-01-08 - تکمیل همگام‌سازی

### اضافه شده:
- [x] همگام‌سازی کامل تصاویر (اصلی + گالری)
- [x] همگام‌سازی برند به عنوان attribute
- [x] همگام‌سازی موجودی و آستانه کم‌بودن
- [x] همگام‌سازی محصولات پیوند شده (cross-sell, upsell)
- [x] پیاده‌سازی Webhook برای دریافت تغییرات
- [x] جلوگیری از تغییر محصولات مدیریت شده توسط Odoo

### نحوه عملکرد:
1. محصولات از Odoo به WooCommerce ارسال می‌شوند با تگ "_managed_by_odoo"
2. اگر کسی در WooCommerce محصول را تغییر دهد:
   - اگر تگ "_managed_by_odoo" داشته باشد، تغییرات نادیده گرفته می‌شود
   - در غیر این صورت، تغییرات به Odoo منتقل می‌شود

## 🔧 Debug Notes - 2025-01-08
- Internal Server Error برطرف شد
- ساختار ساده‌تر برای پایداری
- Controllers در فاز بعدی اضافه می‌شود
- فعلاً تمرکز روی همگام‌سازی یک‌طرفه (Odoo → WooCommerce)

### Next Steps:
1. تست کامل همگام‌سازی محصولات
2. اضافه کردن webhook در مرحله جداگانه
3. شروع Variable Products
