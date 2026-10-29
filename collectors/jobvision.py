"""Jobvision: robots.txt forbids every URL with '?', so we only use the published job sitemap + detail pages."""
from .base import Fetcher, sitemap_urls
from .detail import collect_details, last_number

NAME, MARKET = "jobvision", "iran"
SITEMAPS = ["https://jobvision.ir/sitemap/jobposts.xml", "https://jobvision.ir/sitemap.xml"]


def collect(fetcher: Fetcher, limit: int):
    urls: list[str] = []
    for sm in SITEMAPS:
        urls = sitemap_urls(fetcher, sm, r"jobvision\.ir/jobs/\d+", limit * 2)
        if urls:
            break
    yield from collect_details(fetcher, urls, source=NAME, id_from_url=last_number, limit=limit)
