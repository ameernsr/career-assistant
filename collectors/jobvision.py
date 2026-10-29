"""Jobvision: robots.txt forbids every URL with '?', so we only use the published job sitemap + detail pages.
Job titles are in the URL slug, so off-topic ads are filtered before any detail page is fetched."""
from .base import Fetcher, sitemap_urls
from .detail import collect_details, last_number
from .targets import is_relevant

NAME, MARKET = "jobvision", "iran"
SITEMAPS = ["https://jobvision.ir/sitemap/jobposts.xml", "https://jobvision.ir/sitemap.xml"]


def collect(fetcher: Fetcher, limit: int):
    urls: list[str] = []
    for sm in SITEMAPS:
        urls = sitemap_urls(fetcher, sm, r"jobvision\.ir/jobs/\d+", 20000)
        if urls:
            break
    urls = [u for u in urls if is_relevant(u)]
    urls.sort(key=lambda u: -int(last_number(u)) if last_number(u).isdigit() else 0)  # newest ids first
    fetcher._log(f"{len(urls)} role-related ads in sitemap")
    yield from collect_details(fetcher, urls, source=NAME, id_from_url=last_number, limit=limit)
