"""IranTalent: search pages and '?' URLs are disallowed; city listing pages (/jobs/jobs-in-*) come from the
job-filter sitemap and link to /job/<slug>/<id> detail pages, which carry JSON-LD."""
from .base import Fetcher, harvest_links, sitemap_urls
from .detail import collect_details, last_number

NAME, MARKET = "irantalent", "iran"
BASE = "https://www.irantalent.com"
FALLBACK_LISTINGS = [f"{BASE}/jobs/jobs-in-tehran", f"{BASE}/jobs/jobs-in-isfahan", f"{BASE}/jobs/jobs-in-alborz"]


def _detail_urls(fetcher: Fetcher, limit: int):
    listings = sitemap_urls(fetcher, f"{BASE}/fa/job-filter/sitemap.xml", r"/jobs/jobs-in-", 8) or FALLBACK_LISTINGS
    # Tehran first: most postings.
    listings.sort(key=lambda u: "tehran" not in u)
    seen: set[str] = set()
    for listing in listings:
        html = fetcher.get(listing)
        if not html:
            continue
        for url in harvest_links(html, r"irantalent\.com/job/[^/]+/\d+$", BASE):
            if url not in seen:
                seen.add(url)
                yield url
        if len(seen) >= limit * 2:
            return


def collect(fetcher: Fetcher, limit: int):
    yield from collect_details(fetcher, _detail_urls(fetcher, limit), source=NAME, id_from_url=last_number, limit=limit)
