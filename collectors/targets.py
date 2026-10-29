"""Which postings are worth collecting: only those near our 12 taxonomy roles.

Used twice: to pick category/listing pages before crawling, and to drop off-topic ads by title,
so we spend requests (and the eval set) on relevant jobs."""
from __future__ import annotations

import re
from urllib.parse import unquote

from .normalize import fa_normalize

ROLE_KEYWORDS: dict[str, list[str]] = {
    "backend_developer": ["backend", "back-end", "بک‌اند", "بک اند", "بکند", "django", "laravel", "php", "java", "golang", "node.js", "nodejs", ".net", "python developer", "برنامه‌نویس", "برنامه نویس", "software engineer", "مهندس نرم‌افزار", "توسعه‌دهنده", "developer"],
    "frontend_developer": ["frontend", "front-end", "فرانت", "react", "angular", "vue", "next.js", "طراح سایت", "وب‌سایت"],
    "devops_engineer": ["devops", "دواپس", "sre", "kubernetes", "docker", "linux admin", "cloud engineer"],
    "mobile_developer": ["android", "اندروید", "ios", "flutter", "فلاتر", "react native", "موبایل"],
    "data_analyst": ["data analyst", "تحلیلگر داده", "تحلیل‌گر داده", "تحلیل داده", "power bi", "هوش تجاری", "business intelligence", "bi analyst", "گزارش‌ساز"],
    "data_scientist": ["data scientist", "دانشمند داده", "machine learning", "یادگیری ماشین", "data science"],
    "ml_engineer": ["ml engineer", "هوش مصنوعی", "deep learning", "nlp", "computer vision", "پردازش تصویر", "پردازش زبان"],
    "data_engineer": ["data engineer", "مهندس داده", "etl", "big data", "داده‌کاوی", "dba", "پایگاه داده"],
    "product_manager": ["product manager", "مدیر محصول", "product owner", "مالک محصول", "scrum", "اسکرام", "product designer"],
    "digital_marketer": ["digital marketing", "دیجیتال مارکتینگ", "بازاریابی دیجیتال", "seo", "سئو", "content", "محتوا", "social media", "شبکه‌های اجتماعی", "اینستاگرام", "performance marketing", "مارکتینگ", "marketing", "بازاریابی", "copywriter", "کپی‌رایتر", "برند"],
    "recruiter_hr": ["recruiter", "recruitment", "منابع انسانی", "human resources", "جذب و استخدام", "talent acquisition", "کارگزینی", "آموزش و توسعه"],
    "financial_analyst": ["financial analyst", "تحلیلگر مالی", "حسابدار", "accountant", "accounting", "حسابداری", "finance", "audit", "حسابرس", "auditor", "بودجه"],
}
# Short words that need whole-word matching ("ai" in "maintenance", «مالی» in «شمالی»).
WHOLE_WORDS = ["ai", "bi", "hr", "ui", "qa", "مالی"]

_PATTERNS = [re.escape(fa_normalize(k).lower().replace("-", " ")) for kws in ROLE_KEYWORDS.values() for k in kws]
_RX = re.compile("|".join(_PATTERNS + [rf"(?<!\w){re.escape(w)}(?!\w)" for w in WHOLE_WORDS]))

# Category listing pages that map to our roles (path-based, allowed by each robots.txt).
KARBOOM_CATEGORIES = [
    "programming-and-software", "it-network-hardware", "digital-marketing-produce-content",
    "financial-analyst", "accounting-auditing", "hr-training", "product-manager",
    "product-management-project-management", "business-planning",
]


def is_relevant(*texts: str | None) -> bool:
    """True if a title / URL slug / requirement list mentions one of our roles."""
    blob = fa_normalize(unquote(" ".join(t for t in texts if t))).lower().replace("-", " ")
    return bool(_RX.search(blob))
