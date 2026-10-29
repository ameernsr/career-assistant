from datetime import datetime, timezone

import numpy as np
import pytest

from core.matching import job_skill_ids, rank
from core.schemas import JobPosting, ResumeProfile
from core.taxonomy import Taxonomy


@pytest.fixture
def tax(mini_dict):
    return Taxonomy.from_dict(mini_dict)


def job(jid, title, reqs=(), desc="", city="تهران", remote=None, seniority=None):
    return JobPosting(id=jid, source="t", source_id=jid, url=f"https://x/{jid}", title=title, location=city,
                      remote=remote, seniority=seniority, requirements=list(reqs), description=desc,
                      collected_at=datetime.now(timezone.utc).isoformat())


def test_find_in_text_matches_aliases_as_whole_words(tax):
    found = tax.find_in_text("تسلط به اکسل پیشرفته و SQL، آشنایی با Power BI؛ کار با Python مزیت است")
    assert found == {"excel", "sql_basics", "bi_tools", "python_basics"}
    assert tax.find_in_text("Statistical sqlite pythonic") == set()  # no partial-word hits


def test_job_skills_combine_requirements_and_text(tax):
    j = job("1", "Data Analyst", reqs=["Power BI"], desc="نیاز به تسلط بر آمار و اکسل")
    assert job_skill_ids(j, tax) == {"bi_tools", "statistics", "excel"}


def test_baseline_ranks_by_skill_overlap(tax):
    resume = ResumeProfile(skill_ids=["excel", "sql_basics", "statistics"])
    jobs = [job("a", "Python dev", reqs=["Python", "Pandas"]),
            job("b", "Data analyst", reqs=["Excel", "SQL", "آمار"]),
            job("c", "Reporting", reqs=["Excel", "Power BI"])]
    out = rank(resume, jobs, tax, method="baseline")
    assert [r.job_id for r in out] == ["b", "c", "a"]
    assert all(0 <= r.score <= 1 for r in out)


def test_matched_and_missing_use_implied_prerequisites(tax):
    # Knowing SQL implies relational_db; knowing pandas implies python_basics.
    resume = ResumeProfile(skill_ids=["sql_basics", "pandas"])
    jobs = [job("a", "Analyst", reqs=["Python", "Power BI", "پایگاه داده‌ی رابطه‌ای"])]
    r = rank(resume, jobs, tax, method="baseline")[0]
    assert set(r.matched_skills) == {"python_basics", "relational_db"}
    assert r.missing_skills == ["bi_tools"]


def test_hybrid_uses_embeddings_to_break_skill_ties(tax):
    resume = ResumeProfile(skill_ids=["excel"])
    jobs = [job("far", "Excel clerk", reqs=["Excel"]), job("near", "Excel analyst", reqs=["Excel"])]
    vectors = {"far": np.array([1.0, 0.0]), "near": np.array([0.0, 1.0])}
    out = rank(resume, jobs, tax, method="hybrid", job_vectors=vectors, resume_vector=np.array([0.1, 1.0]))
    assert [r.job_id for r in out] == ["near", "far"]


def test_job_without_skills_still_scored_without_crash(tax):
    resume = ResumeProfile(skill_ids=["excel"])
    jobs = [job("x", "کارشناس", desc="شرح شغل نامشخص"), job("y", "Excel", reqs=["Excel"])]
    out = rank(resume, jobs, tax, method="hybrid")
    assert {r.job_id for r in out} == {"x", "y"} and out[0].job_id == "y"


def test_filters_and_k(tax):
    resume = ResumeProfile(skill_ids=["excel"], location="تهران")
    jobs = [job(str(i), "Excel", reqs=["Excel"], city="شیراز" if i % 2 else "تهران", remote=(i == 3)) for i in range(6)]
    out = rank(resume, jobs, tax, method="baseline", filters={"city": "تهران", "remote_ok": True}, k=10)
    assert {r.job_id for r in out} == {"0", "2", "4", "3"}  # Tehran jobs + the remote one
    assert len(rank(resume, jobs, tax, method="baseline", k=2)) == 2


def test_jobs_without_content_signal_cannot_score_high(tax):
    # No skills extracted and no embeddings: city/seniority fit alone must not look like a strong match.
    resume = ResumeProfile(skill_ids=["excel"], location="تهران")
    r = rank(resume, [job("x", "کارشناس", desc="شرح نامشخص")], tax, method="hybrid")[0]
    assert r.score < 0.3


def test_one_skill_job_does_not_beat_a_broad_full_match(tax):
    resume = ResumeProfile(skill_ids=["excel", "sql_basics", "statistics"])
    jobs = [job("narrow", "Clerk", reqs=["Excel"]), job("broad", "Analyst", reqs=["Excel", "SQL", "آمار"])]
    assert rank(resume, jobs, tax, method="hybrid")[0].job_id == "broad"
