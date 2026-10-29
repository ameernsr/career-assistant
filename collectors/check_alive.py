"""Remove closed job ads: re-visit each cached ad and mark it closed when the page is gone (404/410) or no longer
carries schema.org JobPosting data (boards drop it when an ad expires). Network errors never close an ad.

    python -m collectors.check_alive              # all ads (≈ 2.5 s each, polite)
    python -m collectors.check_alive --limit 20   # quick sample
Closed ids go to data/jobs_closed.json; run_collect's merge() leaves them out of data/jobs.json.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import requests

from .base import ROOT, Fetcher, extract_jsonld

JOBS = ROOT / "data" / "jobs.json"
CLOSED = ROOT / "data" / "jobs_closed.json"


def load_closed() -> dict[str, dict]:
    return json.loads(CLOSED.read_text(encoding="utf-8")) if CLOSED.exists() else {}


def check(limit: int | None = None) -> dict:
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))[:limit]
    closed = load_closed()
    fetchers: dict[str, Fetcher] = {}
    counts = {"open": 0, "closed": 0, "skipped": 0}
    for j in jobs:
        f = fetchers.setdefault(j["source"], Fetcher(f"alive-{j['source']}", use_cache=False, verbose=False))
        if not f.allowed(j["url"]):
            counts["skipped"] += 1
            continue
        time.sleep(f.delay)
        try:
            r = f.session.get(j["url"], timeout=25)
        except requests.RequestException:
            counts["skipped"] += 1  # unreachable from this network ≠ closed
            continue
        reason = None
        if r.status_code in (404, 410):
            reason = f"HTTP {r.status_code}"
        elif r.status_code == 200 and extract_jsonld(r.text) is None and "__NEXT_DATA__" not in r.text:
            reason = "no JobPosting data on the page any more"
        elif r.status_code != 200:
            counts["skipped"] += 1
            continue
        if reason:
            closed[j["id"]] = {"url": j["url"], "reason": reason, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            counts["closed"] += 1
            print(f"  closed: {j['title'][:50]} ({reason})", flush=True)
        else:
            closed.pop(j["id"], None)
            counts["open"] += 1
    CLOSED.write_text(json.dumps(closed, ensure_ascii=False, indent=1), encoding="utf-8")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    counts = check(args.limit)
    from .run_collect import merge

    meta = merge()
    print(f"{counts} → {meta['total']} open jobs in data/jobs.json")


if __name__ == "__main__":
    main()
