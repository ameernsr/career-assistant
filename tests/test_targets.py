import pytest

from collectors.targets import is_relevant


@pytest.mark.parametrize("title", [
    "استخدام برنامه‌نویس بک‌اند (Python/Django)",
    "Senior Java Developer",
    "کارشناس دیجیتال مارکتینگ",
    "استخدام حسابدار ارشد",
    "Data Analyst - Power BI",
    "https://jobvision.ir/jobs/73596/%D8%A7%D8%B3%D8%AA%D8%AE%D8%AF%D8%A7%D9%85-%DA%A9%D8%A7%D8%B1%D9%85%D9%86%D8%AF-%D8%AD%D8%B3%D8%A7%D8%A8%D8%AF%D8%A7%D8%B1%DB%8C",  # slug: کارمند حسابداری
    "Front-End Developer (React)",
    "کارشناس منابع انسانی",
    "AI Engineer",
])
def test_role_related_titles_are_kept(title):
    assert is_relevant(title)


@pytest.mark.parametrize("title", [
    "منشی اداری - خانم",
    "استخدام کارشناس مامایی",
    "Medical Representative",
    "سرپرست تولید - تهران شمالی",
    "Maintenance Technician",
])
def test_off_topic_titles_are_dropped(title):
    assert not is_relevant(title)
