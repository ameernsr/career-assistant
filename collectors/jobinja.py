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
    """Sitemap if published (it was 404 on 2026-10-29), else paginate /jobs?page=N (allowed by robots.txt).
    The title is in the URL slug, so off-topic ads are dropped before their page is fetched."""
    urls: list[str] = []
    for sm in fetcher.robots(BASE).sitemaps:
        urls += [u for u in sitemap_urls(fetcher, sm, DETAIL, 20000) if is_relevant(u)]
    if urls:
        return urls[: limit * 2]
    seen: set[str] = set()
    for page in range(1, 40):
        html = fetcher.get(f"{BASE}/jobs" + (f"?page={page}" if page > 1 else ""))
        links = harvest_links(html or "", DETAIL, BASE)
        if not links:
            break
        for url in links:
            if url not in seen and is_relevant(url):
                seen.add(url)
                urls.append(url)
        if len(urls) >= limit * 2:
            break
    return urls


def collect(fetcher: Fetcher, limit: int):
    yield from collect_details(fetcher, _detail_urls(fetcher, limit), source=NAME, id_from_url=_code, limit=limit)
