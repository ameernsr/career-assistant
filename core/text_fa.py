"""Persian text normalization shared by the app modules."""
import re
import unicodedata

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_KEY_STRIP = re.compile(r"[\s‌\-_.]+")


def fa_normalize(text: str) -> str:
    """PDF glyph forms → letters (NFKC), Arabic ي/ك/ة → Persian ی/ک/ه, unify digits, squeeze spaces. Keeps ZWNJ."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)  # Persian PDFs often extract as presentation forms (ﻣﺴﺎﺑﻘﻪ)
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").translate(_DIGITS)
    return re.sub(r"\s+", " ", text).strip()


def skill_key(text: str) -> str:
    """Lookup key: 'Microsoft  Excel', 'microsoft-excel' and 'MicrosoftExcel' collide on purpose."""
    return _KEY_STRIP.sub("", fa_normalize(text).lower())
