# دستیار مسیر شغلی با هوش مصنوعی

پروژه‌ی هکاتون بوت‌کمپ ماشین‌لرنینگ رهنما کالج (RFP: RC-MLB-HACK-2026-01).

- **ماژول A: دستیار مسیر شغلی.** با یک گفتگوی فارسی در حداکثر ۶ سؤال، نقش و سطح هدف و پیشینه‌ی کاربر را می‌فهمد و نقشه‌ی راه یادگیری را **از روی یک تاکسونومی صریح مهارت‌ها (DAG)** حساب می‌کند. نقشه به‌صورت گراف مرحله‌به‌مرحله و همراه با منابع آموزشی بررسی‌شده نمایش داده می‌شود.
- **ماژول B: تطبیق رزومه با شغل.** رزومه‌ی PDF یا DOCX (فارسی یا انگلیسی) را به یک پروفایل ساختاریافته تبدیل می‌کند و ۲۵۸ آگهی واقعی از ۵ سایت ایرانی را رتبه‌بندی می‌کند. برای هر شغل مهارت‌های منطبق، مهارت‌های جاافتاده، لینک آگهی اصلی و یک نقشه‌ی راه اختصاصی نشان می‌دهد.

گزارش فنی: [`REPORT.md`](REPORT.md) · مشخصات و معیارهای پذیرش: [`docs/SPEC.md`](docs/SPEC.md) · برنامه‌ی تیم: [`team-plan.html`](team-plan.html)

## اجرا با یک دستور
```bash
cp .env.example .env        # OPENAI_BASE_URL و OPENAI_API_KEY گیت‌وی را وارد کنید
./run.sh                    # بار اول virtualenv را می‌سازد و وابستگی‌ها را نصب می‌کند، سپس اپ را روی http://localhost:8501 اجرا می‌کند
```
- پیش‌نیاز: Python 3.11 یا بالاتر.
- اپ به‌طور پیش‌فرض فقط روی localhost در دسترس است تا کسی در شبکه نتواند اعتبار API تیم را مصرف کند. برای اشتراک عمدی در شبکه: `HOST=0.0.0.0 ./run.sh`.

### تنظیمات (`.env`)
| کلید | مقدار فعلی | توضیح |
|---|---|---|
| `OPENAI_BASE_URL`, `OPENAI_API_KEY` | — | گیت‌وی سازگار با OpenAI (Metis). **فقط در `.env` که در git نیست** (NF-04) |
| `CHAT_MODEL` | `gpt-5.4-mini` | گفتگو و استخراج پروفایل |
| `EMBED_MODEL` | `text-embedding-3-small` | embedding آگهی و رزومه |
| `STT_MODEL`, `TTS_MODEL` | `gpt-transcribe`, `gpt-4o-mini-tts` | ورودی صوتی فارسی و خواندن خلاصه (A-10). مدل‌های transcribe دیگر روی گیت‌وی ۴۰۴ می‌دهند |
| `MODEL_PRICES` | از [قیمت‌های متیس](https://docs.metisai.ir/pricing) | دلار به‌ازای یک میلیون توکن، برای داشبورد هزینه (NF-05) |
| `SESSION_BUDGET_USD` | `0.50` | سقف هزینه‌ی هر جلسه. بعد از آن درخواستی به مدل ارسال نمی‌شود |

## تست‌ها
```bash
.venv/bin/python -m pytest -q          # ۹۶ تست
```
بخش‌های قطعی با TDD نوشته شده‌اند: تاکسونومی، نقشه‌ی راه، رتبه‌بندی، معیارهای ارزیابی، پارسر رزومه، robots.txt و نرمال‌سازی متن. در تست‌های مربوط به LLM فقط خود گیت‌وی شبیه‌سازی شده و بقیه‌ی منطق واقعاً اجرا می‌شود.

## داده‌ها و اسکریپت‌ها
| کار | دستور |
|---|---|
| بررسی سلامت سایت‌های آگهی | `.venv/bin/python -m collectors.probe` |
| کرال آگهی‌ها (۵ منبع) | `.venv/bin/python -m collectors.run_collect --sources jobinja jobvision karboom irantalent quera --max-per-source 50` |
| کرال افزایشی (B-11) | همان دستور با `--incremental`. برای اجرای خودکار هر ۶ ساعت: `--every 360`. معادل cron: `0 */6 * * * cd /app && .venv/bin/python -m collectors.run_collect --incremental` |
| پر کردن جای خالی یک نقش | `... --focus data_analyst data_engineer --incremental` |
| embedding آگهی‌ها (فقط آگهی‌های جدید) | `.venv/bin/python scripts/embed_jobs.py` |
| بررسی لینک منابع آموزشی (A-07) | `.venv/bin/python scripts/verify_links.py` |
| انتخاب مدل با بنچمارک | `.venv/bin/python scripts/check_models.py MODEL_A MODEL_B` |
| ارزیابی رتبه‌بندی (۱۰.۲) | `scripts/eval_ranking.py pool`، برچسب‌زنی، سپس `scripts/eval_ranking.py score` (راهنما در [`data/eval/README.md`](data/eval/README.md)) |

قالب داده‌ها در [`data/README.md`](data/README.md) آمده است. اپ هیچ‌وقت در لحظه کرال نمی‌کند و همیشه `data/jobs.json` کش‌شده را می‌خواند.

## منابع آگهی و جمع‌آوری مسئولانه (NF-08)
| منبع | روش | robots.txt |
|---|---|---|
| Jobinja | صفحه‌های `/jobs?page=N`، فیلتر عنوان از روی slug آدرس، سپس JSON-LD صفحه‌ی آگهی | همه‌چیز مجاز (`Disallow:` خالی) |
| Jobvision | `sitemap/jobposts.xml`، فیلتر از روی slug، سپس JSON-LD | `*?*` ممنوع است؛ هیچ URL دارای query درخواست نمی‌شود |
| Karboom | صفحه‌های دسته‌بندی مرتبط (`/jobs/<category>`)، سپس JSON-LD | فقط `?q=`، `/cv` و `/profile` ممنوع‌اند |
| IranTalent | صفحه‌های نقش از job-filter sitemap، سپس JSON-LD | `*?*` و `/jobs-search/` ممنوع‌اند |
| Quera Magnet | `__NEXT_DATA__` صفحه‌ی لیست و JSON-LD صفحه‌ی آگهی | مسیر jobs مجاز است |

- **قبل از هر درخواست robots.txt بررسی می‌شود.** پیاده‌سازی خودمان از `*` و `$` پشتیبانی می‌کند، چون `urllib.robotparser` این wildcardها را نادیده می‌گیرد.
- بین درخواست‌ها به هر سایت ۲.۵ ثانیه فاصله است. User-Agent تیم را معرفی می‌کند (`RahnamaHackathonBot/1.0 (+repo)`). بعد از ۳ بار پاسخ 403 یا 429 کرال آن منبع متوقف می‌شود.
- فقط فیلدهای لازم برای تطبیق ذخیره می‌شوند. **ایمیل و شماره‌ی تماس رابط استخدام قبل از ذخیره حذف می‌شود.**
- Remotive و RemoteOK کنار گذاشته شدند، چون robots.txt آن‌ها API را برای ربات‌ها ممنوع کرده است.
- ⚠️ **وضعیت بررسی قوانین استفاده (ToS):** تیم پیش از ارسال باید قوانین استفاده‌ی هر پنج سایت را بخواند و نتیجه را اینجا ثبت کند.

## حریم خصوصی و امنیت
- **رزومه:** فقط در حافظه‌ی همان جلسه پردازش می‌شود. روی دیسک نوشته یا لاگ نمی‌شود و فقط برای استخراج اطلاعات به گیت‌وی هوش مصنوعی فرستاده می‌شود. پیش از آپلود از کاربر رضایت گرفته می‌شود. دکمه‌ی «پاک کردن داده‌های من» هم وجود دارد (NF-03).
- **کلید API:** فقط از `.env` خوانده می‌شود (`core/config.py`)، هرگز به کلاینت فرستاده نمی‌شود و در `.gitignore` است (NF-04).
- **رزومه‌های ارزیابی** همه مصنوعی‌اند.

## ساختار کد
```
app.py                    رابط Streamlit (فارسی، راست‌به‌چپ)
core/
  config.py llm.py        تنظیمات و تنها درگاه به گیت‌وی: JSON معتبر، retry، شمارش توکن و هزینه، سقف بودجه
  taxonomy.py roadmap.py  تاکسونومی (DAG) و محاسبه‌ی قطعی نقشه‌ی راه
  conversation.py         گفتگوی ماژول A (حداکثر ۶ سؤال، اعتبارسنجی با تاکسونومی، اصلاح توسط کاربر)
  resume_parser.py        PDF/DOCX → متن → ResumeProfile (سال‌های تجربه در کد حساب می‌شود)
  matching.py metrics.py  رتبه‌بندی baseline و hybrid، و معیارهای P@5، nDCG@10، MRR و R@10
  summary.py graph_view.py  خلاصه‌ی متنی هم‌خوان با گراف، DOT و خروجی HTML
  text_fa.py schemas.py   نرمال‌سازی فارسی و قراردادهای داده (Pydantic)
collectors/               کرالرهای سازگار با robots.txt، نرمال‌سازی، حذف تکراری، هدف‌گیری نقش‌ها
data/                     taxonomy.json، resources.json، jobs.json، job_embeddings.npz، eval/
scripts/ tests/
```

## کتابخانه‌ها و قدردانی
Streamlit (Apache-2.0)، OpenAI Python SDK (Apache-2.0)، Pydantic (MIT)، NetworkX (BSD-3)، **PyMuPDF (AGPL-3.0)**، python-docx (MIT)، Requests (Apache-2.0)، Beautiful Soup (MIT)، lxml (BSD)، jdatetime (Python-2.0)، NumPy (BSD-3)، scikit-learn (BSD-3)، python-dotenv (BSD-3)، pytest (MIT)، lameenc / LAME (LGPL؛ تبدیل WAV میکروفون به MP3)، Viz.js (MIT؛ فقط در فایل HTML خروجی)، فونت Vazirmatn (OFL-1.1).

منابع مرجع برای ساخت تاکسونومی: roadmap.sh و آگهی‌های شغلی جمع‌آوری‌شده. منابع آموزشی متعلق به ناشران خودشان هستند و فقط به آن‌ها لینک داده شده است.

## مشارکت اعضای تیم
- ویرایش مستقیم مهارت‌ها با تیک زدن، ورودی و خروجی صوتی، و استخراج قاعده‌محور هنگام قطع LLM بر اساس نمونه‌ی اولیه‌ی ماژول A امیر نصیری پیاده شده‌اند.
- سند معماری و فرمول‌های معیارهای ارزیابی بر اساس سند عرفان تمیمی نوشته شده‌اند.

## افشای استفاده از دستیار هوش مصنوعی
در طراحی، کدنویسی، تست و مستندسازی این پروژه از دستیار کدنویسی **Claude Code** (Anthropic) استفاده شده است. تصمیم‌های اصلی را تیم گرفته و ثبت کرده است: بخش «Decisions log» در `docs/SPEC.md`.
