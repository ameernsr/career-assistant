"""Karboom: role-related category pages (/jobs/<category>, ?page=N allowed; only ?q= is disallowed)
link to /jobs/<code>/<slug> detail pages with JSON-LD."""
import re

from .base import Fetcher, harvest_links
from .detail import collect_details
from .targets import KARBOOM_CATEGORIES

NAME, MARKET = "karboom", "iran"
BASE = "https://karboom.io"
DETAIL = r"karboom\.io/jobs/[a-z]{6}/[^/]+$"
PAGES_PER_CATEGORY = 3


def _code(url: str) -> str:
    m = re.search(r"/jobs/([a-z]{6})/", url)
    return m.group(1) if m else url


def _detail_urls(fetcher: Fetcher, limit: int):
    seen: set[str] = set()
    for page in range(1, PAGES_PER_CATEGORY + 1):  # breadth first: page 1 of every category, then page 2…
        for cat in KARBOOM_CATEGORIES:
            html = fetcher.get(f"{BASE}/jobs/{cat}" + (f"?page={page}" if page > 1 else ""))
            for url in harvest_links(html or "", DETAIL, BASE):
                if url not in seen:
                    seen.add(url)
                    yield url
            if len(seen) >= limit * 2:
                return


def collect(fetcher: Fetcher, limit: int):
    yield from collect_details(fetcher, _detail_urls(fetcher, limit), source=NAME, id_from_url=_code, limit=limit)
