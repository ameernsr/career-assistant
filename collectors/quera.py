"""Quera Magnet (backup, tech-focused): listing pages embed jobs in __NEXT_DATA__; detail pages add JSON-LD."""
from .base import Fetcher, extract_jsonld, extract_next_data
from .normalize import fa_normalize, job_from_jsonld, make_job, normalize_city, to_iso_date

NAME, MARKET = "quera", "iran"
BASE = "https://quera.org/magnet/jobs"
LEVELS = {"intern": "intern", "junior": "junior", "mid-level": "mid", "midlevel": "mid", "mid": "mid", "senior": "senior", "lead": "lead"}


def collect(fetcher: Fetcher, limit: int, with_details: bool = True):
    got = 0
    for page in range(1, 20):
        data = extract_next_data(fetcher.get(BASE + (f"?page={page}" if page > 1 else "")) or "")
        edges = (((data or {}).get("props") or {}).get("pageProps") or {}).get("jobs", {}).get("edges", [])
        if not edges:
            return
        for edge in edges:
            node = edge.get("node") or {}
            if not node.get("pk") or not node.get("open", True):
                continue
            url = f"{BASE}/{node['pk']}"
            techs = [t["technology"]["name"] for t in node.get("jobtechnology_set") or [] if t.get("technology")]
            job = None
            if with_details:
                ld = extract_jsonld(fetcher.get(url) or "")
                if ld:
                    job = job_from_jsonld(ld, source=NAME, source_id=node["pk"], url=url)
            if job is None:
                job = make_job(source=NAME, source_id=node["pk"], url=url, title=node.get("title", ""))
            if job is None:
                continue
            # The listing JSON is cleaner than JSON-LD for these fields.
            job.requirements = list(dict.fromkeys(techs + job.requirements))[:40]
            job.seniority = LEVELS.get(str(node.get("level", "")).lower(), job.seniority)
            job.remote = bool(node.get("offers_remote")) or job.remote
            job.company = fa_normalize((node.get("company") or {}).get("name", "")) or job.company
            job.location = normalize_city((node.get("city") or {}).get("name")) or job.location
            job.employment_type = node.get("collaboration_type") or job.employment_type
            job.date_posted = to_iso_date(node.get("publish_time")) or job.date_posted
            got += 1
            yield job
            if got >= limit:
                return
