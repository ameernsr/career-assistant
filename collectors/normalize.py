"""Turn messy source fields into the shared JobPosting shape."""
from __future__ import annotations

import hashlib
import html as htmllib
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from core.schemas import JobPosting

_FA_CHARS = re.compile(r"[؀-ۿ]")
_LATIN_CHARS = re.compile(r"[A-Za-z]")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+98|0098|0)?9\d{9}|(?:\+98|0)?21[\s-]?\d{8}|\b\d{3,4}[\s-]\d{3,4}[\s-]\d{4}\b")

CITY_ALIASES = {
    "tehran": "تهران", "تهران": "تهران", "isfahan": "اصفهان", "esfahan": "اصفهان", "اصفهان": "اصفهان",
    "shiraz": "شیراز", "شیراز": "شیراز", "mashhad": "مشهد", "مشهد": "مشهد", "tabriz": "تبریز", "تبریز": "تبریز",
    "karaj": "کرج", "کرج": "کرج", "alborz": "البرز", "البرز": "البرز", "qom": "قم", "قم": "قم",
    "ahvaz": "اهواز", "اهواز": "اهواز", "rasht": "رشت", "رشت": "رشت", "remote": "دورکاری",
}

SENIORITY_HINTS = [
    ("intern", ("intern", "internship", "کارآموز", "کاراموز")),
    ("lead", ("lead", "head of", "principal", "manager", "مدیر", "سرپرست", "لید")),
    ("senior", ("senior", "sr.", "ارشد", "سنیور", "سینیور")),
    ("junior", ("junior", "jr.", "entry", "جونیور", "جونیور", "تازه‌کار", "مبتدی")),
    ("mid", ("mid", "middle", "intermediate", "میدلول", "میانی")),
]


def fa_normalize(text: str) -> str:
    """Arabic ي/ك → Persian ی/ک, unify digits, squeeze spaces. Keeps ZWNJ."""
    if not text:
        return ""
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").translate(_DIGITS)
    return re.sub(r"[ \t ]+", " ", text).strip()


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    # Some sources double-escape their HTML (&lt;p&gt;), so unescape until stable.
    for _ in range(3):
        unescaped = htmllib.unescape(raw)
        if unescaped == raw:
            break
        raw = unescaped
    text = BeautifulSoup(raw, "lxml").get_text("\n")
    text = re.sub(r"\n\s*\n+", "\n", text)
    return fa_normalize(text)


def strip_contacts(text: str) -> str:
    """Remove recruiter emails / phone numbers: third-party personal data we must not store (RFP 10.3)."""
    return _PHONE.sub("[تماس حذف شد]", _EMAIL.sub("[ایمیل حذف شد]", text))


def detect_language(text: str) -> str:
    fa, en = len(_FA_CHARS.findall(text)), len(_LATIN_CHARS.findall(text))
    if fa + en == 0:
        return "fa"
    ratio = fa / (fa + en)
    return "fa" if ratio > 0.7 else "en" if ratio < 0.3 else "mixed"


def guess_seniority(*texts: str | None) -> str | None:
    blob = " ".join(t for t in texts if t).lower()
    for level, hints in SENIORITY_HINTS:
        if any(h in blob for h in hints):
            return level
    return None


def normalize_city(raw: str | None) -> str | None:
    if not raw:
        return None
    city = fa_normalize(str(raw)).split("،")[0].split(",")[0].strip()
    return CITY_ALIASES.get(city.lower(), city) or None


def to_iso_date(raw) -> str | None:
    """Accept '2026-10-27', '2026-10-27 15:56:40', ISO datetimes, epoch seconds, or Jalali '1405/08/05'."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc).date().isoformat()
    s = fa_normalize(str(raw))
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    if y < 1700:  # Jalali calendar
        try:
            import jdatetime

            return jdatetime.date(y, mo, d).togregorian().isoformat()
        except Exception:
            return None
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return None


def split_requirements(*chunks) -> list[str]:
    """Flatten skill/qualification fields (str or list) into short, unique phrases."""
    out: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        items = chunk if isinstance(chunk, list) else [chunk]
        for item in items:
            if isinstance(item, dict):
                item = item.get("name") or item.get("description") or ""
            text = html_to_text(str(item))
            for part in re.split(r"[\n،,;•·|]+|\s-\s", text):
                part = part.strip(" .-–:*")
                if 1 < len(part) <= 120 and part not in out:
                    out.append(part)
    return out[:40]


def make_job(*, source: str, source_id: str, url: str, title: str, market: str = "iran", **fields) -> JobPosting | None:
    title = fa_normalize(title or "")
    if not title or not url:
        return None
    description = strip_contacts(fields.pop("description", "") or "")[:5000]
    lang_sample = title + " " + description[:1000]
    return JobPosting(
        id=hashlib.sha1(f"{source}:{source_id}".encode()).hexdigest()[:16],
        source=source,
        source_id=str(source_id),
        url=url,
        title=title,
        description=description,
        language=fields.pop("language", None) or detect_language(lang_sample),
        market=market,
        collected_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **fields,
    )


def job_from_jsonld(ld: dict, *, source: str, source_id: str, url: str, market: str = "iran") -> JobPosting | None:
    """Most Iranian boards publish schema.org JobPosting for Google Jobs; read it uniformly."""
    org = ld.get("hiringOrganization") or {}
    loc = ld.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address", {}) if isinstance(loc, dict) else {}
    if isinstance(addr, str):
        addr = {"addressLocality": addr}
    locality, region = addr.get("addressLocality"), addr.get("addressRegion")
    # Jobvision puts the neighbourhood in addressLocality ("فرمانیه"); prefer the region when it is a known city.
    city = region if region and fa_normalize(str(region)).lower() in CITY_ALIASES else (locality or region)
    description = html_to_text(
        "\n".join(str(ld.get(k) or "") for k in ("description", "responsibilities", "qualifications"))
    )
    remote = None
    if str(ld.get("jobLocationType", "")).upper() == "TELECOMMUTE" or "دورکاری" in description[:500]:
        remote = True
    emp = ld.get("employmentType")
    if isinstance(emp, list):
        emp = ", ".join(map(str, emp))
    if emp and "{" in str(emp):  # Karboom puts a JSON blob here
        m = re.search(r"cooperation_type\W+(\w+)", html_to_text(str(emp)))
        emp = m.group(1) if m else None
    exp = ld.get("experienceRequirements")
    exp_text = exp.get("description", "") if isinstance(exp, dict) else str(exp or "")
    salary = ld.get("baseSalary")
    if isinstance(salary, dict):
        val = salary.get("value", {})
        salary = str(val.get("value") or f"{val.get('minValue', '')}-{val.get('maxValue', '')}") if isinstance(val, dict) else str(val)
    return make_job(
        source=source,
        source_id=source_id,
        url=url,
        market=market,
        title=html_to_text(ld.get("title", "")),
        company=fa_normalize(org.get("name", "")) if isinstance(org, dict) else None,
        location=normalize_city(city),
        country=(addr.get("addressCountry") if isinstance(addr.get("addressCountry"), str) else None) or ("IR" if market == "iran" else None),
        remote=remote,
        employment_type=fa_normalize(str(emp)) if emp else None,
        seniority=guess_seniority(ld.get("title"), exp_text),
        description=description,
        requirements=split_requirements(ld.get("skills"), ld.get("qualifications"), ld.get("educationRequirements")),
        date_posted=to_iso_date(ld.get("datePosted")),
        salary=str(salary) if salary not in (None, "", {}) else None,
    )
