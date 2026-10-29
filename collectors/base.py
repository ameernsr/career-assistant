"""Polite HTTP fetching shared by every collector: robots.txt, rate limit, retries, raw cache."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .robots import RobotsRules

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"  # gitignored: re-parse without re-fetching

USER_AGENT = (
    "RahnamaHackathonBot/1.0 (+https://github.com/yasaman1994/rahnama-career-assistant; "
    "educational project, Rahnama College ML Bootcamp)"
)
DEFAULT_DELAY = 2.5  # seconds between requests to the same host


class Blocked(Exception):
    """The site refused us (403/429 repeatedly). Stop this source instead of hammering it."""


class Fetcher:
    def __init__(self, source: str, delay: float = DEFAULT_DELAY, use_cache: bool = True, verbose: bool = True):
        self.source = source
        self.delay = delay
        self.use_cache = use_cache
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fa,en;q=0.8"})
        self._robots: dict[str, RobotsRules] = {}
        self._last_hit: dict[str, float] = {}
        self._refusals = 0
        self.stats = {"fetched": 0, "cached": 0, "robots_denied": 0, "errors": 0}

    # ---------- robots ----------
    def robots(self, url: str) -> RobotsRules:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            try:
                try:
                    r = self.session.get(host + "/robots.txt", timeout=15)
                except requests.RequestException:
                    time.sleep(3)
                    r = self.session.get(host + "/robots.txt", timeout=25)
                if r.status_code == 200 and "html" not in r.headers.get("content-type", ""):
                    rules = RobotsRules(_decode(r.content))
                elif 400 <= r.status_code < 500 and r.status_code not in (401, 403, 429):
                    rules = RobotsRules(None)  # no robots.txt: everything allowed (RFC 9309)
                else:
                    rules = RobotsRules(None, available=False)  # blocked / server error: stay out
            except requests.RequestException:
                rules = RobotsRules(None, available=False)
            self._robots[host] = rules
            cd = rules.crawl_delay(USER_AGENT)
            if cd:
                self.delay = max(self.delay, cd)
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        return self.robots(url).can_fetch(USER_AGENT, url)

    # ---------- fetching ----------
    def get(self, url: str, *, binary: bool = False) -> str | bytes | None:
        """Return page text (or bytes), or None if disallowed / failed. Raises Blocked on repeated refusals."""
        cache_file = RAW_DIR / self.source / (hashlib.sha1(url.encode()).hexdigest() + ".bin")
        if self.use_cache and cache_file.exists():
            self.stats["cached"] += 1
            data = cache_file.read_bytes()
            return data if binary else _decode(data)

        if not self.allowed(url):
            self.stats["robots_denied"] += 1
            self._log(f"robots.txt disallows {url}")
            return None

        host = urlsplit(url).netloc
        for attempt in range(3):
            wait = self.delay - (time.time() - self._last_hit.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self._last_hit[host] = time.time()
            try:
                r = self.session.get(url, timeout=25)
            except requests.RequestException as exc:
                self._log(f"network error ({exc.__class__.__name__}) {url}")
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (403, 429):
                self._refusals += 1
                self._log(f"HTTP {r.status_code} {url}")
                if self._refusals >= 3:
                    raise Blocked(f"{self.source}: refused {self._refusals} times (HTTP {r.status_code})")
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                self._log(f"HTTP {r.status_code} {url}")
                break
            self._refusals = 0
            self.stats["fetched"] += 1
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(r.content)
            return r.content if binary else _decode(r.content)
        self.stats["errors"] += 1
        return None

    def get_json(self, url: str):
        text = self.get(url)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            self._log(f"invalid JSON from {url}")
            return None

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [{self.source}] {msg}", flush=True)


# ---------- helpers used by several sources ----------
def _decode(data: bytes) -> str:
    if data[:2] == b"\x1f\x8b":  # gzipped sitemap
        data = gzip.decompress(data)
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):  # Jobvision serves UTF-16 sitemaps
        return data.decode("utf-16")
    return data.decode("utf-8", errors="replace")


def sitemap_urls(fetcher: Fetcher, sitemap_url: str, url_pattern: str, limit: int, _depth: int = 0) -> list[str]:
    """Walk a sitemap (or sitemap index) and return page URLs matching url_pattern (regex)."""
    xml = fetcher.get(sitemap_url)
    if not xml or _depth > 3:
        return []
    locs = [l.strip() for l in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)]
    if "<sitemapindex" in xml:
        found: list[str] = []
        for child in locs:
            found += sitemap_urls(fetcher, child, url_pattern, limit - len(found), _depth + 1)
            if len(found) >= limit:
                break
        return found[:limit]
    rx = re.compile(url_pattern)
    return [u for u in locs if rx.search(u)][:limit]


def extract_jsonld(html: str, wanted_type: str = "JobPosting") -> dict | None:
    """Find the first JSON-LD object of the given @type. Tolerates raw newlines inside strings (Karboom)."""
    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", html, re.S | re.I):
        try:
            data = json.loads(block.strip(), strict=False)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if isinstance(item, dict):
                t = item.get("@type")
                if t == wanted_type or (isinstance(t, list) and wanted_type in t):
                    return item
    return None


def extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def harvest_links(html: str, pattern: str, base: str = "") -> list[str]:
    """Collect unique links matching a regex (absolute or site-relative), keeping page order."""
    seen, out = set(), []
    for href in re.findall(r'href="([^"#]+)"', html):
        url = href if href.startswith("http") else base.rstrip("/") + "/" + href.lstrip("/")
        url = url.split("?")[0]
        if re.search(pattern, url) and url not in seen:
            seen.add(url)
            out.append(url)
    return out
