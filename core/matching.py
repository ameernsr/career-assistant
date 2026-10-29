"""Module B ranking (B-04, B-05, B-07): baseline keyword overlap and a hybrid score, both explainable."""
from __future__ import annotations

import networkx as nx
import numpy as np

from core.schemas import JobPosting, MatchResult, ResumeProfile
from core.taxonomy import Taxonomy

WEIGHTS = {"semantic": 0.45, "coverage": 0.35, "seniority": 0.10, "location": 0.10}
LEVEL_ORDER = ["intern", "junior", "mid", "senior", "lead"]


def job_skill_ids(job: JobPosting, tax: Taxonomy) -> set[str]:
    """Taxonomy concepts a job asks for: exact requirement phrases plus whole-word mentions in its text."""
    ids = {cid for r in job.requirements if (cid := tax.resolve(r))}
    for r in job.requirements:
        ids |= tax.find_in_text(r)
    return ids | tax.find_in_text(f"{job.title}\n{job.description}")


def job_text(job: JobPosting) -> str:
    """What gets embedded for a job (keep in sync with scripts/embed_jobs.py)."""
    return f"{job.title}\n{', '.join(job.requirements)}\n{job.description[:800]}"


def _with_prerequisites(ids: set[str], tax: Taxonomy) -> set[str]:
    have = {i for i in ids if i in tax.concepts}
    for cid in list(have):
        have |= nx.ancestors(tax.graph, cid)
    return have


def _user_level(years: float | None) -> str | None:
    if years is None:
        return None
    return "intern" if years < 0.5 else "junior" if years < 2 else "mid" if years < 5 else "senior"


def _seniority_fit(user: str | None, job: str | None) -> float:
    if not user or not job:
        return 0.7  # unknown: mildly neutral
    gap = abs(LEVEL_ORDER.index(user) - LEVEL_ORDER.index(job))
    return 1.0 if gap == 0 else 0.5 if gap == 1 else 0.0


def _location_fit(resume: ResumeProfile, job: JobPosting) -> float:
    if job.remote or not resume.location or not job.location:
        return 1.0
    return 1.0 if resume.location in job.location or job.location in resume.location else 0.3


def _passes(job: JobPosting, filters: dict | None) -> bool:
    if not filters:
        return True
    remote_ok = filters.get("remote_ok", True)
    if filters.get("remote_only") and not job.remote:
        return False
    city = filters.get("city")
    if city and not (job.location and city in job.location) and not (remote_ok and job.remote):
        return False
    levels = filters.get("seniority")
    if levels and job.seniority and job.seniority not in levels:
        return False
    max_age = filters.get("max_age_days")
    if max_age and job.date_posted:  # old ads are likely closed
        from datetime import date

        try:
            if (date.today() - date.fromisoformat(job.date_posted)).days > max_age:
                return False
        except ValueError:
            pass
    return True


def rank(
    resume: ResumeProfile,
    jobs: list[JobPosting],
    tax: Taxonomy,
    *,
    method: str = "hybrid",
    filters: dict | None = None,
    k: int = 10,
    job_vectors: dict[str, np.ndarray] | None = None,
    resume_vector: np.ndarray | None = None,
) -> list[MatchResult]:
    have = _with_prerequisites(set(resume.skill_ids), tax)
    raw_have = {i for i in resume.skill_ids if i in tax.concepts}
    candidates = [j for j in jobs if _passes(j, filters)]

    semantic: dict[str, float] = {}
    if method == "hybrid" and job_vectors is not None and resume_vector is not None:
        rv = resume_vector / (np.linalg.norm(resume_vector) or 1.0)
        cos = {j.id: float(job_vectors[j.id] @ rv / (np.linalg.norm(job_vectors[j.id]) or 1.0))
               for j in candidates if j.id in job_vectors}
        if cos:  # min-max per query: raw cosine ranges are model-specific
            lo, hi = min(cos.values()), max(cos.values())
            semantic = {jid: (c - lo) / (hi - lo) if hi > lo else 1.0 for jid, c in cos.items()}

    level = _user_level(resume.years_experience)
    results: list[MatchResult] = []
    for j in candidates:
        need = job_skill_ids(j, tax)
        matched, missing = sorted(need & have), sorted(need - have)
        if method == "baseline":
            union = need | raw_have
            score = len(need & raw_have) / len(union) if union else 0.0
        else:
            parts = {
                "semantic": semantic.get(j.id),
                # +1 in the denominator: a job listing one skill is weaker evidence than one listing five (B8: none → skip)
                "coverage": len(matched) / (len(need) + 1) if need else None,
                "seniority": _seniority_fit(level, j.seniority),
                "location": _location_fit(resume, j),
            }
            used = {n: v for n, v in parts.items() if v is not None}
            content = [n for n in ("semantic", "coverage") if n in used]
            if content:
                score = sum(WEIGHTS[n] * v for n, v in used.items()) / sum(WEIGHTS[n] for n in used)
            else:  # nothing about the job's content is known: context fit alone caps at 0.2
                score = WEIGHTS["seniority"] * used["seniority"] + WEIGHTS["location"] * used["location"]
        results.append(MatchResult(job_id=j.id, score=round(min(max(score, 0.0), 1.0), 4),
                                   matched_skills=matched, missing_skills=missing))
    results.sort(key=lambda r: (-r.score, -len(r.matched_skills), r.job_id))
    return results[:k]
