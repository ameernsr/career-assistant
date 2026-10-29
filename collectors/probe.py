"""Quick health check of every source before a real crawl:  python -m collectors.probe

For each site prints: robots.txt reachable?, sitemaps, whether a sample job page is allowed and
has schema.org JobPosting data. Fetches only a handful of pages (and caches them)."""
from __future__ import annotations

import importlib
import itertools

from .base import Blocked, Fetcher, extract_jsonld
from .run_collect import BACKUP, MAIN

HOMES = {
    "jobinja": "https://jobinja.ir/", "jobvision": "https://jobvision.ir/", "karboom": "https://karboom.io/",
    "irantalent": "https://www.irantalent.com/", "quera": "https://quera.org/", "remotive": "https://remotive.com/",
}


def probe(name: str) -> None:
    f = Fetcher(name, verbose=False)
    rules = f.robots(HOMES[name])
    print(f"\n== {name}")
    print(f"  robots.txt: {'reachable' if rules.available else 'UNREACHABLE (blocked? VPN?) → crawler will skip this site'}")
    if rules.sitemaps:
        print(f"  sitemaps:   {', '.join(rules.sitemaps[:3])}")
    if not rules.available:
        return
    try:
        jobs = list(itertools.islice(importlib.import_module(f"collectors.{name}").collect(f, 2), 2))
    except Blocked as exc:
        print(f"  BLOCKED: {exc}")
        return
    except Exception as exc:
        print(f"  ERROR: {exc.__class__.__name__}: {exc}")
        return
    s = f.stats
    print(f"  requests:   fetched={s['fetched']} cached={s['cached']} robots_denied={s['robots_denied']} errors={s['errors']}")
    if not jobs:
        print("  ✗ no jobs parsed. Paste this output to the team/Claude to fix the parser.")
    for j in jobs:
        print(f"  ✓ {j.title[:50]} | {j.company} | {j.location} | {j.date_posted} | reqs={len(j.requirements)} desc={len(j.description)}ch")
        print(f"    {j.url}")


def main() -> None:
    import sys

    for name in sys.argv[1:] or MAIN + BACKUP:
        probe(name)
    print("\nNext: python -m collectors.run_collect   (add --sources quera --incremental if a main source failed)")


if __name__ == "__main__":
    main()
