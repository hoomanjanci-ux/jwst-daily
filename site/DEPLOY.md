# دیپلوی nabzekeyhan.ir روی ورسل — دفترچهٔ اجرا

> این سند برای لحظه‌ای است که مالک Access Token ورسل را می‌دهد.
> همه‌چیز از قبل آماده است؛ اجرای واقعی ≤ ۱۵ دقیقه.

## وضعیت آماده‌سازی (تاریخ: ۲۰۲۶-۱۰-۲۳)

- کد سایت: `site/` در مخزن `jwst-daily` (شاخهٔ main) — Next.js 16 + **خروجی ایستا** (`output: "export"`).
- ۳۵ صفحهٔ ایستا: خانه + ۲۷ صفحهٔ خبر + صفحهٔ تحلیل‌ها (فعلاً placeholder) + ادمین + robots + sitemap.
- محتوا هر بیلد از `analyses/` و `pipeline/state.json` (آرشیو فارسی خبرها) + ۳ فید رسمی ناسا/اسا ساخته می‌شود.
- هیچ قابلیت سروری/ورسل-خاصی استفاده نشده → مهاجرت به هر هاست دیگر = کپی `out/` + تغییر DNS.

## سناریوی A — دیپلوی با Access Token (CLI) — سریع‌ترین

```bash
npm i -g vercel@latest
cd site/
vercel --token <TOKEN> --yes --prod          # اولین دیپلوی: پروژه ساخته می‌شود
```

- ورسل خودکار تشخیص می‌دهد Next.js است؛ خروجی نهایی: `https://<project>.vercel.app`
- نام پروژه: `nabzekeyhan` (با `vercel --prod --name` یا از داشبورد تغییر دهد).
- Git Integration: بعد از اولین دیپلوی، از داشبورد پروژه → Settings → Git → Connect →
  مخزن `hoomanjanci-ux/jwst-daily`، Root Directory = `site` → هر push = دیپلوی خودکار.

## سناریوی B — اتصال گیت‌هاب (بدون توکن در دست دستیار)

مالک در داشبورد ورسل: Add New Project → Import `jwst-daily` →
Root Directory: `site` → Framework: Next.js (خودکار) → Deploy.

## اتصال دامنه (بعد از خرید nabzekeyhan.ir)

1. ورسل → Project → Domains → Add `nabzekeyhan.ir` (+ `www`).
2. DNS:
   - اگر دامنه در ابر Cloudflare باشد (پیشنهاد): رکورد A/AAAA یا CNAME به
     `cname.vercel-dns.com`، پروکسی Cloudflare **فعال** (قفل نارنجی).
   - اگر بدون CF: رکوردهای پیشنهادی خود ورسل (A → 76.76.21.21).
3. SSL خودکار (ورسل + CF هر دو Let's Encrypt می‌دهند).

## نکات پلن Hobby

- لیمیت ~۱۰۰GB/ماه انتقال (سایت ایستای سبک = سال‌ها کافی) — ۱۰۰GB یعنی صدها هزار بازدید.
- Cron در Hobby روزانه است (لازم نیست؛ تازگی سایت با هر push/بیلد تضمین می‌شود).
- بیلدها با هر push مخزن اجرا می‌شوند (ران‌های پایپ‌لاین چند بار در روز push می‌کنند → سایت خودبه‌خود تازه می‌شود).

## چک‌لیست پس از دیپلوی

- [ ] صفحهٔ خانه لود شد (هیرو ۳D + فید + فوتر).
- [ ] `https://<domain>/robots.txt` شامل `Disallow: /admin`.
- [ ] `https://<domain>/sitemap.xml` معتبر.
- [ ] `/admin` با ROOT_1024/ROOT_1024 وارد می‌شود (noindex).
- [ ] در Google Search Console: دامنه را با سابمیت sitemap ثبت کن (مالک، ۵ دقیقه).
