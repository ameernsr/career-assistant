import copy

import pytest

# A tiny, hand-checked taxonomy. Prerequisite edges:
#   computer_basics → excel, relational_db, python_basics
#   relational_db → sql_basics → bi_tools, data_modeling
#   excel → bi_tools ; statistics → data_modeling ; python_basics → pandas
MINI = {
    "roles": [
        {
            "id": "data_analyst",
            "name_fa": "تحلیلگر داده",
            "name_en": "Data Analyst",
            "domain": "data",
            "levels": {
                "junior": ["excel", "sql_basics", "statistics"],
                "mid": ["bi_tools", "pandas"],
                "senior": ["data_modeling"],
            },
        }
    ],
    "concepts": [
        {"id": "computer_basics", "name_fa": "مهارت‌های پایه‌ی کامپیوتر", "name_en": "Computer basics", "aliases": [], "prerequisites": []},
        {"id": "excel", "name_fa": "اکسل", "name_en": "Excel", "aliases": ["microsoft excel", "اکسل پیشرفته"], "prerequisites": ["computer_basics"]},
        {"id": "relational_db", "name_fa": "پایگاه داده‌ی رابطه‌ای", "name_en": "Relational databases", "aliases": ["rdbms"], "prerequisites": ["computer_basics"]},
        {"id": "sql_basics", "name_fa": "مبانی SQL", "name_en": "SQL basics", "aliases": ["sql", "اس‌کیو‌ال"], "prerequisites": ["relational_db"]},
        {"id": "statistics", "name_fa": "آمار", "name_en": "Statistics", "aliases": ["آمار توصیفی"], "prerequisites": []},
        {"id": "python_basics", "name_fa": "مبانی پایتون", "name_en": "Python basics", "aliases": ["python", "پایتون"], "prerequisites": ["computer_basics"]},
        {"id": "pandas", "name_fa": "پانداس", "name_en": "Pandas", "aliases": [], "prerequisites": ["python_basics"]},
        {"id": "bi_tools", "name_fa": "ابزارهای BI", "name_en": "BI tools", "aliases": ["power bi", "tableau"], "prerequisites": ["excel", "sql_basics"]},
        {"id": "data_modeling", "name_fa": "مدل‌سازی داده", "name_en": "Data modeling", "aliases": [], "prerequisites": ["sql_basics", "statistics"]},
    ],
}


@pytest.fixture
def mini_dict():
    return copy.deepcopy(MINI)
