# data/

| مسیر | محتوا | در git؟ |
|---|---|---|
| `jobs/<source>.jsonl` | آگهی‌های نرمال‌شده‌ی هر منبع، هر خط یک `JobPosting` | ✅ بله |
| `jobs.json` | ادغام همه‌ی منابع بعد از حذف تکراری‌ها. **ورودی اصلی matching و دمو** | ✅ بله |
| `jobs_meta.json` | زمان آخرین به‌روزرسانی، تعداد کل، تعداد آگهی هر منبع | ✅ بله |
| `raw/<source>/*.bin` | کش خام HTML و XML صفحه‌ها، برای پارس دوباره بدون دانلود مجدد | ❌ نه (gitignore) |
| `taxonomy.json`, `resources.json` | تاکسونومی و منابع یادگیری (مسئولیت نفر ۱) | ✅ بله |
| `eval/` | رزومه‌های مصنوعی و `labels.csv` برای ارزیابی | ✅ بله |

## قالب مشترک آگهی (`JobPosting`)

تعریف دقیق در [`core/schemas.py`](../core/schemas.py) است. **قبل از هر تغییری در آن، به بقیه‌ی تیم خبر بدهید.**

```json
{
  "id": "a1b2c3d4e5f60718",
  "source": "karboom",
  "source_id": "wjamzl",
  "url": "https://karboom.io/jobs/wjamzl/help-desk",
  "title": "استخدام Help Desk",
  "company": "هلدینگ بان",
  "location": "تهران",
  "country": "IR",
  "remote": null,
  "employment_type": "FULL_TIME",
  "seniority": null,
  "description": "شرح وظایف: ...",
  "requirements": ["شبکه", "نصب نرم‌افزار"],
  "skills": [],
  "date_posted": "2026-10-27",
  "salary": null,
  "language": "fa",
  "market": "iran",
  "collected_at": "2026-10-29T08:30:00+00:00"
}
```

- `requirements`: عبارت‌های خامی که در خود آگهی آمده‌اند.
- `skills`: بعداً با ID مفاهیم تاکسونومی پر می‌شود (کار نفر ۲).
- اطلاعات تماس (ایمیل و تلفن) قبل از ذخیره از `description` حذف می‌شود.
