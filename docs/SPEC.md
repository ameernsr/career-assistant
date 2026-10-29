# SPEC — AI Career Path Assistant (RC-MLB-HACK-2026-01)

The single source of truth for **what we build and when it counts as done**. Code freeze 16:15, submission 17:00.
Data shapes live in [`core/schemas.py`](../core/schemas.py); this file references them, never redefines them.

Owners: **P1** = taxonomy & graph · **P2** = data & ranking · **P3** = LLM & app. (Names: see team-plan.html.)

## 1. Architecture rules

- **Deterministic core, generative edge.** Taxonomy, roadmap, scoring, years-of-experience, dedup are plain Python with tests. The LLM only converses, extracts JSON, and writes explanations.
- **Taxonomy is the spine.** Every skill anywhere (chat, resume, job ad) is mapped to a taxonomy concept id before use. Unknown ids are dropped, never shown (A-04).
- **LLM output is untrusted.** Parse → validate with the Pydantic model → filter ids against the taxonomy → use. On failure: retry once, then a rule-based fallback.
- **Cached data only at demo time.** The app reads `data/*.json`; it never crawls live.

## 2. Module contracts

| Module | Owner | Public function | Returns |
|---|---|---|---|
| `core/llm.py` | P3 | `chat_json(messages, model_cls) -> model_cls`, `embed(texts) -> np.ndarray`, `usage()` | validated model / vectors / per-session tokens + cost |
| `core/taxonomy.py` | P1 | `load_taxonomy() -> Taxonomy`; `Taxonomy.resolve(text) -> id \| None`; `Taxonomy.check_dag()` | raises with the cycle path if not a DAG |
| `core/roadmap.py` | P1 | `compute_roadmap(tax, role_id, target_level, known, not_known) -> Roadmap` | `Roadmap` |
| `core/summary.py` | P1 | `summarize(roadmap, tax) -> str` | Persian text built only from `roadmap.stages` (A-09) |
| `core/conversation.py` | P3 | `next_turn(state, user_msg) -> (reply, state)` | `state.profile: UserProfile`, `state.done: bool` |
| `core/resume_parser.py` | P3 | `parse_resume(data: bytes, filename: str) -> ResumeProfile` | raises `ResumeError` with a Persian message |
| `core/matching.py` | P2 | `rank(resume, jobs, method="hybrid"\|"baseline", filters=None, k=10) -> list[MatchResult]` | sorted, score in [0,1] |
| `collectors/run_collect.py` | P2 | CLI | `data/jobs.json` |

### Data files

```jsonc
// data/taxonomy.json (P1)
{
  "roles": [{"id": "data_analyst", "name_fa": "تحلیلگر داده", "name_en": "Data Analyst", "domain": "data",
             "levels": {"junior": ["excel", "sql_basics"], "mid": ["..."], "senior": ["..."]}}],
  "concepts": [{"id": "sql_basics", "name_fa": "مبانی SQL", "name_en": "SQL basics",
                "aliases": ["sql", "اس‌کیو‌ال", "mysql"], "prerequisites": ["relational_db"]}]
}
// data/resources.json (P1) — only entries that passed scripts/verify_links.py
{"sql_basics": [{"title": "SQL Tutorial", "url": "https://...", "lang": "en", "verified_at": "2026-10-29"}]}
```

## 3. Algorithms

**Roadmap (A-05):**
```
target  = ⋃ role.levels[l] for l ≤ target_level
closure = target ∪ ancestors(target)
known   = (claims with proficiency ∈ {used, proficient}) ∪ ancestors(those)   # implicit prerequisites
known  -= not_known                                                            # explicit "I don't know" wins
stages  = nx.topological_generations(G.subgraph(closure − known))
```

**Ranking (B-04, B-07):** baseline = Jaccard on taxonomy ids. hybrid = `0.45·cos(emb) + 0.35·coverage + 0.10·φ_exp + 0.10·location_fit`, then optional LLM rerank of the top 20. Weights are chosen once, not tuned on the eval set. If the LLM rerank fails or exceeds its timeout, return the hybrid order (NF-06).
- `φ_exp` (optional, P2 decides): `1` if `y_user ≥ y_min(job)`, else `exp(−λ·(y_min − y_user)²)` with λ = 0.5; `y_min` is extracted per job in the same LLM pass that maps job skills to taxonomy ids. Without `y_min`, fall back to seniority-label match.

**Evaluation (RFP 10.2):** 3 synthetic resumes × 25 postings: junior data analyst, mid backend developer, and one business profile (marketing or accounting), because most cached postings are non-technical. Binary labels in `data/eval/labels.csv` (`resume_id,job_id,relevant`). Report P@5, nDCG@10, MRR and Recall@10 for baseline, hybrid, hybrid+rerank. **Only numbers produced by `scripts/eval_ranking.py` go into the report or slides.**

## 4. Requirements and acceptance criteria

Status: ☐ todo · ◐ in progress · ☑ done (update in your PR).

| ID | Pri | Owner | Done when | Status |
|---|---|---|---|---|
| A-01 | Must | P3 | Persian chat reaches `done` in ≤ 6 assistant questions for all 3 Appendix B personas; the counter is enforced in code | ◐ `core/conversation.py` done; real run: persona 1 → 4 q, persona 2 → 3 q; UI pending |
| A-02 | Must | P1 | `taxonomy.json` has ≥ 10 roles in ≥ 3 domains, each with junior/mid/senior concept lists | ☑ draft: 12 roles, 109 concepts — P1 to review |
| A-03 | Must | P1 | `check_dag()` passes on our file and raises with the cycle path on a test file containing a cycle | ☑ guard test passes on real file |
| A-04 | Must | P3 | A test feeds LLM JSON containing a fake role and fake concept; both are dropped | ☑ `test_unknown_role_and_concepts_are_dropped` |
| A-05 | Must | P1 | Test: every concept appears after all its prerequisites; known concepts are absent | ☑ `core/roadmap.py` |
| A-06 | Must | P3 | Graph renders on one laptop screen for a 25-node roadmap, known vs to-learn colored | ☐ |
| A-07 | Must | P1 | Every displayed URL comes from `resources.json` and `verify_links.py` reports 0 failures | ☑ 129/129 links verified, 109/109 concepts covered |
| A-08 | Should | P3 | «من اکسل بلد نیستم» adds excel back into the graph without restarting the chat | ◐ logic done + real run («داکر بلد نیستم»); UI pending |
| A-09 | Should | P1 | Summary text names exactly the concepts in `roadmap.stages` (test) | ☐ |
| A-10 | Could | P3 | Voice input transcribed into the chat; summary playable as audio | ☑ `st.audio_input` → `gpt-transcribe`; summary → `gpt-4o-mini-tts` (real round trip verified) |
| A-11 | Could | P1 | Download buttons for SVG/PNG of the graph | ☐ |
| B-01 | Must | P3 | Persian PDF, English PDF, and DOCX samples parse; corrupt/encrypted file shows a Persian error | ☐ |
| B-02 | Must | P3 | `ResumeProfile` filled for all eval resumes; years computed in code (Jalali supported) | ☐ |
| B-03 | Must | P2 | `jobs_meta.json` shows ≥ 50 jobs from ≥ 2 sources ✅ (155 from 4 at 11:50) | ☑ |
| B-04 | Must | P2 | Top 10 with scores in < 60 s for the full cached set | ◐ `rank()` 0.54 s on 258 jobs; UI pending |
| B-05 | Must | P2 | Each result lists matched and missing taxonomy concepts | ◐ in `MatchResult`; UI pending |
| B-06 | Must | P2 | Each result links to `job.url` | ☐ |
| B-07 | Should | P2 | Eval table shows hybrid vs baseline P@5 and nDCG@10 | ☑ hybrid > baseline on all 4 metrics (P@5 0.533 vs 0.467, nDCG@10 0.594 vs 0.524) |
| B-08 | Should | P2 | Filters for city, seniority, remote change the result list | ◐ `rank(filters=…)` tested; UI pending |
| B-09 | Should | P2 | `dedup()` used in `run_collect` ✅; duplicates count shown in meta | ☑ |
| B-10 | Could | P3 | "برای این شغل چه یاد بگیرم؟" button draws a roadmap of that job's missing concepts | ☐ |
| B-11 | Could | P2 | `--incremental` crawl + refresh button with last-updated time | ◐ |
| NF-01 | Must | P3 | Whole UI RTL Persian (Vazirmatn) | ☐ |
| NF-02 | Should | P2 | Chat reply < 10 s, ranking < 60 s | ☐ |
| NF-03 | Must | P3 | Consent notice before upload; resume text never logged or saved | ☐ |
| NF-04 | Must | all | `git log -p \| grep -iE "sk-\|api[_-]?key="` finds nothing but `.env.example` placeholders | ☐ |
| NF-05 | Should | P3 | Sidebar shows tokens + estimated cost of the session | ◐ `LLM.usage` + budget cap done; sidebar pending |
| NF-06 | Must | P3 | Killing the network or returning bad JSON shows a Persian message, no traceback | ◐ `LLM` raises Persian `LLMError` (tested); UI must catch it |
| NF-07 | Should | P2 | `./run.sh` on a fresh clone starts the app | ☐ |
| NF-08 | Must | P2 | robots-aware collector ✅; ToS notes for each source in README | ◐ |

## 5. Checkpoints

- **13:00** each module runs alone with sample data.
- **14:45** every Must and Should works end to end in the app. After this, only Coulds and fixes.
- **16:15** code freeze → rehearse demo, secret scan, submit by 17:00.

## 6. Decisions log

| Time | Decision | Why |
|---|---|---|
| 11:00 | Knowing a concept implies its prerequisites; explicit «بلد نیستم» wins | Team vote; shorter, more realistic roadmaps |
| 11:50 | Remotive/RemoteOK dropped | Their robots.txt disallows `/api/*` for bots (NF-08) |
| 12:40 | From Erfan's architecture doc: adopt metric definitions (P@5, R@10, MRR, nDCG@10), φ_exp (optional), LLM-timeout fallback; use its formulas in REPORT.md | Cheap, improves the 20-pt ML criterion |
| 12:40 | Not adopted: BM25, semantic chat cache, graded 0–3 labels, required/preferred split (unless free in the extraction prompt) | Time, privacy risk (shared cache across users), RFP asks for binary relevance |
| 12:40 | The doc's results table holds placeholder numbers; it stays empty until eval runs | Reporting unmeasured results would mislead the jury |
| 13:30 | Chat model `gpt-5.4-mini` (fallback `gpt-4.1-mini`), embeddings `text-embedding-3-small`, STT `gpt-4o-mini-transcribe`, TTS `gpt-4o-mini-tts` | `scripts/check_models.py`: 5.4-mini 1.1 s avg, 3/3 valid+correct, fewest tokens; 4.1-mini 1.4 s 3/3; 4o-mini 1.9 s 3/3; 4.1-nano deprecated; gpt-5-mini rejects temperature=0. Embeddings: fa↔en same meaning cos 0.57 vs unrelated 0.19–0.26 |
| 13:30 | LLM JSON schemas use enums/Literal for ids, never free strings | Smoke test: with a loose schema the model stuffed advice into the `role` field |
| 14:10 | Measured cost per chat session ≈ $0.01 (gpt-5.4-mini, 4–5 calls, ~2k-token catalog in the system prompt); 1.2–1.8 s per turn | Real runs of personas 1 and 2 |
| 15:30 | Merged from Amir's FastAPI prototype: direct skill editing (A-08 without LLM), voice (A-10), rule-based fallback extraction. Not merged: FastAPI/Cytoscape frontend, its taxonomy (no aliases), hard-coded cost | Strengths that fit our stack before the freeze; its substring keyword fallback had an `html`→`ml` false positive, ours matches whole words |
| 15:30 | STT model `gpt-transcribe` | `gpt-4o-mini-transcribe`, `gpt-4o-transcribe`, `whisper-1` return 404 on the gateway; `gpt-transcribe` transcribed a TTS round trip exactly |
| 15:40 | Explicit «بلد نیستم» also removes skills that were only inferred from the user's level and depend on it | "Senior but no SQL" left advanced SQL/BI/data modeling as known — contradictory |
| 15:40 | Business roles enriched (bookkeeping, reconciliation, cost accounting, graphic design, job descriptions, user stories); junior roadmaps 8–9 skills like technical roles | Junior financial/marketing roadmaps had only 5 skills |
| 15:40 | Closed ads: 60-day filter on by default + `collectors/check_alive.py` (404/410 or JobPosting data gone) in the periodic refresh | 89/258 ads older than 30 days |
| 16:00 | Primary labels: Erfan (human). Second column: Claude (AI), reported as such; used only for agreement (92%) and a robustness check | A second human annotator was not available; an AI label must not be presented as human judgement |
| 16:00 | Prices: embeddings and TTS from OpenAI list, STT from OpenRouter list (per second); TTS cost counts input text only | Metis page lists chat models only; the speech endpoint returns no usage |
| 12:40 | `fa_normalize` applies NFKC | Persian PDFs extract as presentation forms (ﻣﺴﺎﺑﻘﻪ); verified on a real LuaTeX PDF |
