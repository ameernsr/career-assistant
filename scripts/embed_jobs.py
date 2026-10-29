"""Embed every cached job once → data/job_embeddings.npz (ids + vectors). Re-run after a crawl;
only jobs without a vector are sent, so incremental refreshes stay cheap (B-11).

    .venv/bin/python scripts/embed_jobs.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import load_settings  # noqa: E402
from core.llm import LLM  # noqa: E402
from core.matching import job_text  # noqa: E402
from core.schemas import JobPosting  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "job_embeddings.npz"


def load_vectors() -> dict[str, np.ndarray]:
    if not OUT.exists():
        return {}
    d = np.load(OUT)
    return dict(zip(d["ids"].tolist(), d["vectors"]))


def main() -> None:
    jobs = [JobPosting(**j) for j in json.loads((ROOT / "data" / "jobs.json").read_text(encoding="utf-8"))]
    vectors = load_vectors()
    todo = [j for j in jobs if j.id not in vectors]
    llm = LLM(load_settings())
    for i in range(0, len(todo), 64):
        batch = todo[i : i + 64]
        for j, v in zip(batch, llm.embed([job_text(j) for j in batch])):
            vectors[j.id] = v
        print(f"embedded {min(i + 64, len(todo))}/{len(todo)}")
    keep = {j.id for j in jobs}
    ids = [i for i in vectors if i in keep]
    np.savez_compressed(OUT, ids=np.array(ids), vectors=np.stack([vectors[i] for i in ids]))
    print(f"{len(ids)} job vectors → {OUT.relative_to(ROOT)} | usage {llm.usage}")


if __name__ == "__main__":
    main()
