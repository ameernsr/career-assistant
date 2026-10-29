"""RFP 10.2: measure ranking quality of baseline vs hybrid on labelled synthetic resumes.

Step 1 — build the labelling sheet (pooling: top results of every method + a few random jobs):
    .venv/bin/python scripts/eval_ranking.py pool
    → data/eval/labels_todo.csv   (open in Excel/Sheets, fill `relevant` with 1 or 0; a second person fills `relevant_2`)
    → save it as data/eval/labels.csv

Step 2 — score:
    .venv/bin/python scripts/eval_ranking.py score
    → prints P@5, nDCG@10, MRR, Recall@10 per method and writes data/eval/results.json (shown in the app's eval tab)

Parsed resume profiles are cached in data/eval/profiles.json so scoring is deterministic and costs nothing.
Jobs that nobody labelled count as not relevant (standard pooling assumption; noted in the report).
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.config import load_settings  # noqa: E402
from core.llm import LLM  # noqa: E402
from core.matching import rank  # noqa: E402
from core.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k  # noqa: E402
from core.resume_parser import parse_resume_text  # noqa: E402
from core.schemas import JobPosting, ResumeProfile  # noqa: E402
from core.taxonomy import load_taxonomy  # noqa: E402

EVAL = ROOT / "data" / "eval"
PROFILES = EVAL / "profiles.json"
TODO, LABELS, RESULTS = EVAL / "labels_todo.csv", EVAL / "labels.csv", EVAL / "results.json"
METHODS = ["baseline", "hybrid"]
POOL_PER_METHOD, RANDOM_EXTRA, SEED = 12, 6, 13


def load_jobs():
    jobs = [JobPosting(**j) for j in json.loads((ROOT / "data" / "jobs.json").read_text(encoding="utf-8"))]
    d = np.load(ROOT / "data" / "job_embeddings.npz")
    return jobs, dict(zip(d["ids"].tolist(), d["vectors"]))


def load_profiles(tax) -> dict[str, tuple[ResumeProfile, np.ndarray]]:
    """Parse each synthetic resume once (LLM + embedding) and cache the result."""
    cache = json.loads(PROFILES.read_text(encoding="utf-8")) if PROFILES.exists() else {}
    llm = None
    for f in sorted((EVAL / "resumes").glob("*.txt")):
        if f.stem in cache:
            continue
        llm = llm or LLM(load_settings())
        text = f.read_text(encoding="utf-8")
        profile = parse_resume_text(text, llm, tax)
        cache[f.stem] = {"profile": profile.model_dump(), "vector": llm.embed([text])[0].tolist()}
        print(f"parsed {f.name}: {len(profile.skill_ids)} skills, {profile.years_experience} years")
    PROFILES.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return {rid: (ResumeProfile(**v["profile"]), np.array(v["vector"], dtype=np.float32)) for rid, v in cache.items()}


def ranked_ids(method, profile, vec, jobs, vectors, tax, k):
    return [r.job_id for r in rank(profile, jobs, tax, method=method, k=k, job_vectors=vectors, resume_vector=vec)]


def cmd_pool() -> None:
    tax = load_taxonomy()
    jobs, vectors = load_jobs()
    by_id = {j.id: j for j in jobs}
    old = {}
    if LABELS.exists():
        with LABELS.open(encoding="utf-8-sig") as fh:
            old = {(r["resume_id"], r["job_id"]): r for r in csv.DictReader(fh)}
    rows = []
    rng = random.Random(SEED)
    for rid, (profile, vec) in load_profiles(tax).items():
        pool: list[str] = []
        for m in METHODS:
            for jid in ranked_ids(m, profile, vec, jobs, vectors, tax, POOL_PER_METHOD):
                if jid not in pool:
                    pool.append(jid)
        rest = [j.id for j in jobs if j.id not in pool]
        pool += rng.sample(rest, RANDOM_EXTRA)
        rng.shuffle(pool)  # labellers must not see which method ranked what
        for jid in pool:
            j = by_id[jid]
            prev = old.get((rid, jid), {})
            rows.append({"resume_id": rid, "job_id": jid, "title": j.title, "company": j.company or "",
                         "city": j.location or "", "url": j.url,
                         "relevant": prev.get("relevant", ""), "relevant_2": prev.get("relevant_2", "")})
    with TODO.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM so Excel shows Persian correctly
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows → {TODO.relative_to(ROOT)}  (fill `relevant` with 1/0, save as {LABELS.name})")


def cmd_score() -> None:
    if not LABELS.exists():
        sys.exit(f"{LABELS.relative_to(ROOT)} not found: run `pool`, label the sheet, save it as labels.csv")
    tax = load_taxonomy()
    jobs, vectors = load_jobs()
    with LABELS.open(encoding="utf-8-sig") as fh:
        labels = list(csv.DictReader(fh))
    relevant: dict[str, set[str]] = {}
    pairs = agree = 0
    for r in labels:
        if r["relevant"].strip() == "1":
            relevant.setdefault(r["resume_id"], set()).add(r["job_id"])
        if r.get("relevant_2", "").strip() in ("0", "1") and r["relevant"].strip() in ("0", "1"):
            pairs += 1
            agree += r["relevant"].strip() == r["relevant_2"].strip()
    profiles = load_profiles(tax)
    table, per_resume = [], {}
    for m in METHODS:
        scores = {"P@5": [], "nDCG@10": [], "MRR": [], "Recall@10": []}
        for rid, (profile, vec) in profiles.items():
            rel = relevant.get(rid, set())
            ids = ranked_ids(m, profile, vec, jobs, vectors, tax, len(jobs))
            row = {"P@5": precision_at_k(ids, rel, 5), "nDCG@10": ndcg_at_k(ids, rel, 10),
                   "MRR": mrr(ids, rel), "Recall@10": recall_at_k(ids, rel, 10)}
            per_resume.setdefault(rid, {})[m] = {k: round(v, 3) for k, v in row.items()}
            for k, v in row.items():
                scores[k].append(v)
        table.append({"method": m, **{k: round(float(np.mean(v)), 3) for k, v in scores.items()}})
    notes = (f"{len(profiles)} synthetic resumes, {len(labels)} labelled pairs, "
             f"{sum(map(len, relevant.values()))} relevant. Unlabelled jobs count as not relevant (pooling).")
    if pairs:
        notes += f" Inter-annotator agreement: {agree}/{pairs} ({agree / pairs:.0%})."
    RESULTS.write_text(json.dumps({"table": table, "per_resume": per_resume, "notes": notes}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print(f"{'method':10} {'P@5':>6} {'nDCG@10':>8} {'MRR':>6} {'R@10':>6}")
    for t in table:
        print(f"{t['method']:10} {t['P@5']:6.3f} {t['nDCG@10']:8.3f} {t['MRR']:6.3f} {t['Recall@10']:6.3f}")
    print(notes, f"→ {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    {"pool": cmd_pool, "score": cmd_score}.get(sys.argv[1] if len(sys.argv) > 1 else "score", cmd_score)()
