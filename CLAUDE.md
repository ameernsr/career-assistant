# CLAUDE.md

Hackathon project (one day, 3 junior devs): Persian career-path assistant + resume-to-job matching. Streamlit app, OpenAI-compatible gateway.

**Read [`docs/SPEC.md`](docs/SPEC.md) before starting any task**: module contracts, algorithms, and the acceptance criterion for every requirement ID (A-01…B-11, NF-01…NF-08). Work is done when its criterion in SPEC is met and its status cell is updated.

## Contracts
- `core/schemas.py` is the shared contract between the three developers. Read it, import from it; propose changes to the team instead of editing it on a feature branch.
- Every skill mention (chat, resume, job ad) resolves to a taxonomy concept id via `Taxonomy.resolve`; anything that does not resolve is dropped.
- LLM output is untrusted input: validate with the Pydantic model and filter ids before use. Scores, dates, years of experience, and roadmaps are computed in Python.
- URLs shown to users come only from `data/resources.json` (verified) or `job.url`.

## Guardrails (disqualification if broken)
- Secrets live only in `.env` (gitignored). Code reads them through `core/config.py`.
- Collectors go through `collectors/base.Fetcher`, which enforces robots.txt, rate limit, and the team User-Agent. Store only fields in `JobPosting`; contact details are stripped.
- Resume content stays in memory for the session: no logging, no files.

## Working style
- Follow the karpathy guidelines: smallest change that meets the criterion, surgical edits, state assumptions.
- Deterministic modules (`taxonomy`, `roadmap`, `matching`, `summary`, `collectors`) are built test-first; run `.venv/bin/python -m pytest -q` before every commit.
- User-facing text is Persian, RTL; code, identifiers, and commit messages are English.
- One branch per owner (`feat/<area>`), small PRs into `main`, pull `main` often. Each file has one owner (see SPEC §2).
- Stuck for more than 20 minutes → say so and ask; time is the scarcest resource.
