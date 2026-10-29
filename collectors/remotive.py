"""Remotive public API (backup, international remote jobs).
Terms: link back to the Remotive URL and credit Remotive as the source; call it rarely (we cache)."""
from .base import Fetcher
from .normalize import guess_seniority, html_to_text, make_job, split_requirements, to_iso_date

NAME, MARKET = "remotive", "remote"
CATEGORIES = ["software-dev", "data", "devops", "product", "marketing", "finance-legal", "hr"]


def collect(fetcher: Fetcher, limit: int):
    per_cat = max(5, limit // len(CATEGORIES) + 1)
    got, seen = 0, set()
    for cat in CATEGORIES:
        data = fetcher.get_json(f"https://remotive.com/api/remote-jobs?category={cat}&limit={per_cat}") or {}
        for j in data.get("jobs", []):
            if j.get("id") in seen:
                continue
            seen.add(j.get("id"))
            job = make_job(
                source=NAME, source_id=j["id"], url=j.get("url", ""), title=j.get("title", ""), market=MARKET,
                company=j.get("company_name"), location=j.get("candidate_required_location") or "Remote",
                remote=True, employment_type=j.get("job_type"), seniority=guess_seniority(j.get("title")),
                description=html_to_text(j.get("description")), requirements=split_requirements(j.get("tags")),
                date_posted=to_iso_date(j.get("publication_date")), salary=j.get("salary") or None, language="en",
            )
            if job:
                got += 1
                yield job
            if got >= limit:
                return
