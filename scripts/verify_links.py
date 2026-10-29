"""A-07: keep only learning links that really exist.

    .venv/bin/python scripts/verify_links.py          # data/resource_candidates.json → data/resources.json

A link passes when it answers 2xx after redirects, was not redirected to a site's home page, and the page is not
a "404 / not found" page. Failures are listed so someone can replace them. The app shows only data/resources.json.
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "data" / "resource_candidates.json"
OUT = ROOT / "data" / "resources.json"
UA = "RahnamaHackathonBot/1.0 (+https://github.com/yasaman1994/rahnama-career-assistant; link check)"
NOT_FOUND = re.compile(r"<title>[^<]*(404|not found|page not found|یافت نشد|پیدا نشد)[^<]*</title>", re.I)


def check(url: str) -> tuple[bool, str]:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en,fa"}, timeout=20, allow_redirects=True)
    except requests.RequestException as exc:
        return False, exc.__class__.__name__
    if not 200 <= r.status_code < 300:
        return False, f"HTTP {r.status_code}"
    asked, landed = urlsplit(url), urlsplit(r.url)
    if asked.path.strip("/") and not landed.path.strip("/"):
        return False, f"redirected to home page {r.url}"
    if NOT_FOUND.search(r.text[:5000]):
        return False, "soft 404 page"
    return True, "ok"


def main() -> None:
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    pairs = [(cid, item) for cid, items in candidates.items() for item in items]
    with ThreadPoolExecutor(max_workers=8) as pool:  # different hosts; one request per link
        results = list(pool.map(lambda p: check(p[1]["url"]), pairs))
    verified: dict[str, list[dict]] = {}
    failed = []
    today = date.today().isoformat()
    for (cid, item), (ok, why) in zip(pairs, results):
        if ok:
            verified.setdefault(cid, []).append({**item, "verified_at": today})
        else:
            failed.append((cid, item["url"], why))
    OUT.write_text(json.dumps(verified, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"verified {sum(map(len, verified.values()))}/{len(pairs)} links; "
          f"{len(verified)}/{len(candidates)} concepts have at least one resource → {OUT.relative_to(ROOT)}")
    for cid, url, why in failed:
        print(f"  ✗ {cid:24} {why:32} {url}")
    sys.exit(0)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"done in {time.time() - t0:.0f}s")
