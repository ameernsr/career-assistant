"""IranTalent: search pages and '?' URLs are disallowed; city listing pages (/jobs/jobs-in-*) come from the
job-filter sitemap and link to /job/<slug>/<id> detail pages, which carry JSON-LD."""
from .base import Fetcher, harvest_links, sitemap_urls
from .detail import collect_details, last_number
from .targets import is_relevant

NAME, MARKET = "irantalent", "iran"
BASE = "https://www.irantalent.com"
FALLBACK_LISTINGS = [f"{BASE}/jobs/{s}" for s in (
    "backend-developer", "frontend-developer", "python-developer", "android-developer",
    "digital-marketing-specialist", "seo-specialist", "senior-accountant", "financial-manager", "scrum-master",
)]


def _detail_urls(fetcher: Fetcher, limit: int):
    # Role pages (/jobs/backend-developer, /jobs/seo-specialist…) from the job-filter sitemap.
    listings = [
        u for u in sitemap_urls(fetcher, f"{BASE}/fa/job-filter/sitemap.xml", r"/jobs/[^/]+$", 2000)
        if "jobs-in-" not in u and "jobs-for-" not in u and is_relevant(u)
    ] or FALLBACK_LISTINGS
    seen: set[str] = set()
    for listing in listings:
        html = fetcher.get(listing)
        if not html:
            continue
        for url in harvest_links(html, r"irantalent\.com/job/[^/]+/\d+$", BASE):
            if url not in seen:
                seen.add(url)
                yield url
        if len(seen) >= limit * 3:
            return


def collect(fetcher: Fetcher, limit: int):
    yield from collect_details(fetcher, _detail_urls(fetcher, limit), source=NAME, id_from_url=last_number, limit=limit)
