"""Collect job postings from all sources into data/jobs.json.

    python -m collectors.run_collect                       # all main sources, 60 each
    python -m collectors.run_collect --sources karboom quera --max-per-source 40
    python -m collectors.run_collect --incremental         # B-11: keep old ads, add new ones
    python -m collectors.run_collect --every 360           # background refresh every 6 h (minutes, min 60)

Per-source files go to data/jobs/<source>.jsonl; the merged, de-duplicated set to data/jobs.json.
Both are committed to git so the whole team (and the demo) uses the same cached data.
"""
from __future__ import annotations

import argparse
import importlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from core.schemas import JobPosting

from .base import ROOT, Blocked, Fetcher
from .dedup import dedup

MAIN = ["jobinja", "jobvision", "karboom", "irantalent"]
BACKUP = ["quera"]  # remotive.py kept for reference: its robots.txt disallows /api/*, so the crawler refuses it
JOBS_DIR = ROOT / "data" / "jobs"
MERGED = ROOT / "data" / "jobs.json"
META = ROOT / "data" / "jobs_meta.json"


def load_jsonl(path: Path) -> list[JobPosting]:
    if not path.exists():
        return []
    return [JobPosting.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_source(name: str, limit: int, incremental: bool, use_cache: bool) -> tuple[int, str]:
    module = importlib.import_module(f"collectors.{name}")
    fetcher = Fetcher(name, use_cache=use_cache)
    out = JOBS_DIR / f"{name}.jsonl"
    existing = {j.id: j for j in load_jsonl(out)} if incremental else {}
    new = 0
    status = "ok"
    try:
        for job in module.collect(fetcher, limit):
            if job.id not in existing:
                new += 1
            existing[job.id] = job
            print(f"  [{name}] {len(existing):>3}  {job.title[:60]}", flush=True)
    except Blocked as exc:
        status = f"blocked: {exc}"
    except Exception as exc:  # one broken source must not stop the others
        status = f"error: {exc.__class__.__name__}: {exc}"
    if existing:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(j.model_dump_json() for j in existing.values()) + "\n", encoding="utf-8")
    s = fetcher.stats
    print(f"  [{name}] done: {new} new, {len(existing)} total | fetched={s['fetched']} cached={s['cached']} "
          f"robots_denied={s['robots_denied']} errors={s['errors']} | {status}\n", flush=True)
    return new, status


def merge() -> dict:
    jobs: list[JobPosting] = []
    for f in sorted(JOBS_DIR.glob("*.jsonl")):
        jobs += load_jsonl(f)
    unique, dropped = dedup(jobs)
    MERGED.write_text(json.dumps([j.model_dump() for j in unique], ensure_ascii=False, indent=1), encoding="utf-8")
    per_source: dict[str, int] = {}
    for j in unique:
        per_source[j.source] = per_source.get(j.source, 0) + 1
    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(unique),
        "duplicates_removed": dropped,
        "per_source": per_source,
    }
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", nargs="+", default=MAIN, help=f"main: {MAIN}  backup: {BACKUP}  or 'all'")
    ap.add_argument("--max-per-source", type=int, default=60)
    ap.add_argument("--incremental", action="store_true", help="keep previously collected ads (B-11)")
    ap.add_argument("--no-cache", action="store_true", help="re-download pages even if cached in data/raw/")
    ap.add_argument("--merge-only", action="store_true", help="just rebuild data/jobs.json from data/jobs/*.jsonl")
    ap.add_argument("--every", type=int, metavar="MINUTES",
                    help="keep running and refresh incrementally every N minutes (min 60: be polite to the sites)")
    args = ap.parse_args()
    sources = MAIN + BACKUP if args.sources == ["all"] else args.sources
    if args.every:
        interval = max(60, args.every) * 60
        while True:
            for name in sources:
                print(f"== {name}", flush=True)
                run_source(name, args.max_per_source, True, use_cache=False)
            meta = merge()
            print(f"[{meta['last_updated']}] {meta['total']} jobs; next refresh in {interval // 60} min", flush=True)
            time.sleep(interval)

    if not args.merge_only:
        for name in sources:
            print(f"== {name}", flush=True)
            run_source(name, args.max_per_source, args.incremental, not args.no_cache)
    meta = merge()
    print(f"Merged {meta['total']} unique jobs ({meta['duplicates_removed']} duplicates removed): {meta['per_source']}")
    print(f"→ {MERGED.relative_to(ROOT)}")
    if meta["total"] < 50 or len(meta["per_source"]) < 2:
        print("⚠ RFP needs ≥50 jobs from ≥2 sources. Add backups: --sources quera --incremental")


if __name__ == "__main__":
    main()
