"""B-09: drop the same ad collected twice (same source or across sources)."""
from __future__ import annotations

import re

from core.schemas import JobPosting

from .normalize import fa_normalize

_NOISE = re.compile(r"(استخدام|دعوت به همکاری|نیازمند|\(.*?\)|[^\w\s])")


def _key(job: JobPosting) -> str:
    title = _NOISE.sub(" ", fa_normalize(job.title).lower())
    company = _NOISE.sub(" ", fa_normalize(job.company or "").lower())
    return " ".join(title.split()) + "|" + " ".join(company.split()) + "|" + (job.location or "")


def dedup(jobs: list[JobPosting]) -> tuple[list[JobPosting], int]:
    """Keep one copy per (title, company, city); when two collide keep the longer description."""
    seen_ids: set[str] = set()
    best: dict[str, JobPosting] = {}
    for job in jobs:
        if job.id in seen_ids:
            continue
        seen_ids.add(job.id)
        k = _key(job)
        if k not in best or len(job.description) > len(best[k].description):
            best[k] = job
    unique = list(best.values())
    return unique, len(jobs) - len(unique)
