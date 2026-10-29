"""Karboom: /jobs listing pages (?page=N is allowed; only ?q= is disallowed) link to /jobs/<code>/<slug>."""
import re

from .base import Fetcher, harvest_links
from .detail import collect_details

NAME, MARKET = "karboom", "iran"
BASE = "https://karboom.io"
DETAIL = r"karboom\.io/jobs/[a-z]{6}/[^/]+$"


def _code(url: str) -> str:
    m = re.search(r"/jobs/([a-z]{6})/", url)
    return m.group(1) if m else url


def _detail_urls(fetcher: Fetcher, limit: int):
    seen: set[str] = set()
    for page in range(1, 30):
        html = fetcher.get(f"{BASE}/jobs" + (f"?page={page}" if page > 1 else ""))
        if not html:
            return
        fresh = [u for u in harvest_links(html, DETAIL, BASE) if u not in seen]
        if not fresh:
            return  # ran past the last page
        for url in fresh:
            seen.add(url)
            yield url
        if len(seen) >= limit * 2:
            return


def collect(fetcher: Fetcher, limit: int):
    yield from collect_details(fetcher, _detail_urls(fetcher, limit), source=NAME, id_from_url=_code, limit=limit)
