# معماری تأییدشده سامانه نبض راز کیهان

## مسیر اجرایی

NASA/MAST → دریافت محصولات FITS → محاسبات قطعی روی داده علمی → انتخاب محور محدود با AI در صورت موفقیت provider → تولید متن دوزبانه → صف D1 و receipt → انتشار Telegram → ساخت داده سایت → Next.js static export → Vercel و مرورگر.

## اجزا

| بخش | مسیر | نقش | وضعیت |
|---|---|---|---|
| دریافت و آماده‌سازی | `pipeline/` و workflowهای `.github/workflows/` | دریافت MAST، ساخت محصول، ثبت metadata و checkpoint | فعال در GitHub Actions؛ اجرای زنده دوباره انجام نشد |
| محاسبات علمی | `pipeline/evidence_analysis.py`, `annotator.py` | اندازه‌گیری FITS، آمار robust و امتیاز ساختار | قطعی و قابل‌آزمون؛ مستقل از AI |
| انتخاب محور | `pipeline/bilingual_analysis.py` | انتخاب از schema بسته؛ fallback به مسیر قطعی | AI-assisted، با اعتبارسنجی شناسه‌های مجاز |
| تولید متن | `pipeline/ai_message.py`, `evidence_analysis.py` | متن دوزبانه و برچسب‌گذاری نوع محتوا | AI فقط در مسیرهای مشخص؛ fail-safe در خطا |
| انتشار | `pipeline/analysis_worker.py`, `cloudflare/analysis-worker.mjs` | ارسال جفتی، receipt و جلوگیری از تکرار | فعال در سورس؛ نوشتن زنده انجام نشد |
| ذخیره‌سازی | `cloudflare/analysis.sql`, `cloud_queue.py` | صف‌ها، slotها و receiptهای تحلیل | binding زنده قابل‌بررسی نبود |
| وب‌سایت | `site/src/` | نمایش تحلیل/خبر، SEO، منظومه سه‌بعدی و Admin | build محلی موفق؛ Production فعلی قدیمی‌تر از patch محلی است |

## کنترل خطا و تکرار

Pipeline پیش از ارسال checkpoint می‌نویسد، پاسخ Telegram را با receipt کنترل می‌کند، برای slot و زبان و بخش وضعیت ثبت می‌کند و در خطای مبهم از ارسال دوباره بی‌قاعده جلوگیری می‌کند. captionهای بزرگ‌تر از حد Telegram نگه داشته می‌شوند. در provider AI، نبود کلید/مدل یا پاسخ نامعتبر باید به fallback قطعی منجر شود.

## تفکیک AI و علم

دریافت FITS، محاسبات آماری، threshold و metadata علمی قطعی‌اند. AI فقط می‌تواند در انتخاب محور از گزینه‌های مجاز و در تولید روایت برچسب‌خورده کمک کند؛ نباید کشف جدید، طبقه‌بندی قطعی یا عدد اندازه‌گیری‌شده را جعل کند. کانال خبر رسمی از تحلیل AI جدا نگه داشته شده است.

## وضعیت ماژول‌ها

سورس شامل pipeline فعال، Worker مستقل و سایت Next.js است. بعضی workflowهای نگهداری Telegram و اسکریپت‌های تاریخی در مخزن باقی مانده‌اند و باید پیش از حذف، با owner و لاگ workflow تطبیق داده شوند. حذف یا تغییر Cron در این مأموریت انجام نشد.
