"""Jobinja: blocks non-Iranian IPs (turn VPN off). Prefer its sitemap; fall back to the query-free /jobs page.
Run `python -m collectors.probe` first and read Jobinja's terms before enabling it."""
from .base import Fetcher, harvest_links, sitemap_urls
from .detail import collect_details
from .targets import is_relevant

NAME, MARKET = "jobinja", "iran"
BASE = "https://jobinja.ir"
DETAIL = r"jobinja\.ir/companies/[^/]+/jobs/[A-Za-z0-9]+(/[^/]*)?$"


def _code(url: str) -> str:
    parts = url.rstrip("/").split("/jobs/")
    return parts[-1].split("/")[0] if len(parts) > 1 else url


def _detail_urls(fetcher: Fetcher, limit: int):
    urls: list[str] = []
    for sm in fetcher.robots(BASE).sitemaps or [f"{BASE}/sitemap.xml"]:
        urls += [u for u in sitemap_urls(fetcher, sm, DETAIL, 20000) if is_relevant(u)]
        if len(urls) >= limit * 2:
            break
    if not urls:
        html = fetcher.get(f"{BASE}/jobs")
        urls = harvest_links(html or "", DETAIL, BASE)
    return urls


def collect(fetcher: Fetcher, limit: int):
    yield from collect_details(fetcher, _detail_urls(fetcher, limit), source=NAME, id_from_url=_code, limit=limit)
