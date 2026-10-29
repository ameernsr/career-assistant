# دستیار مسیر شغلی با هوش مصنوعی (Rahnama Hackathon)

پروژه‌ی هکاتون بوت‌کمپ ماشین‌لرنینگ رهنما کالج (RFP: RC-MLB-HACK-2026-01).

- **ماژول A:** دستیار گفتگومحور فارسی که نقشه‌ی راه یادگیری را از روی تاکسونومی مهارت‌ها (DAG) محاسبه می‌کند و به‌صورت گراف نشان می‌دهد.
- **ماژول B:** تطبیق رزومه با آگهی‌های شغلی واقعی. ۱۰ شغل برتر با مهارت‌های منطبق و جاافتاده نمایش داده می‌شود.

برنامه‌ی تیم: [`team-plan.html`](team-plan.html)

## اجرا
```bash
cp .env.example .env   # کلید و base URL گیت‌وی را وارد کنید
./run.sh
```
*(تکمیل می‌شود: مدل‌ها، منابع داده، ToS منابع، ارزیابی.)*

## جمع‌آوری آگهی‌ها (ماژول B)
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m collectors.probe                 # بررسی سلامت هر سایت (چند صفحه)
.venv/bin/python -m collectors.run_collect           # منابع اصلی، ۶۰ آگهی از هر کدام
.venv/bin/python -m collectors.run_collect --sources jobinja --incremental   # اضافه کردن یک منبع
```
- خروجی: `data/jobs/<source>.jsonl` و فایل ادغام‌شده‌ی `data/jobs.json`. قالب داده در [`data/README.md`](data/README.md) توضیح داده شده.
- **جابینجا IPهای خارج از ایران را بلاک می‌کند.** برای کرال آن VPN را خاموش کنید.
- قبل از هر درخواست robots.txt چک می‌شود (با پشتیبانی کامل از wildcard). بین درخواست‌ها ۲.۵ ثانیه فاصله است، User-Agent تیم را معرفی می‌کند و اطلاعات تماس از متن آگهی‌ها حذف می‌شود.
- Remotive و RemoteOK در robots.txt خود API را برای ربات‌ها ممنوع کرده‌اند، برای همین از آن‌ها استفاده نمی‌کنیم.

| منبع | روش | robots.txt |
|---|---|---|
| Jobinja | sitemap یا صفحه‌ی `/jobs`، سپس JSON-LD صفحه‌ی آگهی | در زمان اجرا چک می‌شود |
| Jobvision | `sitemap/jobposts.xml`، سپس JSON-LD | `*?*` ممنوع است؛ هیچ URL دارای query درخواست نمی‌شود |
| Karboom | `/jobs?page=N`، سپس JSON-LD | فقط `?q=`، `/cv` و `/profile` ممنوع‌اند |
| IranTalent | صفحه‌های شهر از job-filter sitemap، سپس JSON-LD | `*?*` و `/jobs-search/` ممنوع‌اند |
| Quera Magnet (پشتیبان) | `__NEXT_DATA__` صفحه‌ی لیست و JSON-LD صفحه‌ی آگهی | مسیر jobs مجاز است |

## افشا
در توسعه‌ی این پروژه از دستیار کدنویسی Claude Code استفاده شده است.
