"""Shared loop: visit job detail pages and read their schema.org JobPosting."""
from __future__ import annotations

import re
from typing import Callable, Iterable, Iterator

from core.schemas import JobPosting

from .base import Fetcher, extract_jsonld
from .normalize import job_from_jsonld
from .targets import is_relevant


def collect_details(
    fetcher: Fetcher,
    urls: Iterable[str],
    *,
    source: str,
    id_from_url: Callable[[str], str],
    limit: int,
    market: str = "iran",
) -> Iterator[JobPosting]:
    got = 0
    for url in urls:
        if got >= limit:
            return
        html = fetcher.get(url)
        if not html:
            continue
        ld = extract_jsonld(html)
        if not ld:
            fetcher._log(f"no JobPosting JSON-LD on {url}")
            continue
        job = job_from_jsonld(ld, source=source, source_id=id_from_url(url), url=url, market=market)
        if job and not is_relevant(job.title, " ".join(job.requirements)):
            fetcher._log(f"off-topic, skipped: {job.title[:50]}")
            continue
        if job:
            got += 1
            yield job


def last_number(url: str) -> str:
    nums = re.findall(r"/(\d+)(?:/|$)", url)
    return nums[-1] if nums else url
