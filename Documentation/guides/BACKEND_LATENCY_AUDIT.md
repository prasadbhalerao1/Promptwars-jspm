# Backend Latency Audit — `services/agents` and downstream

> **Update 2026-08-02 (sweep 2):** A second sweep covered everything the first pass didn't
> touch — all `services/api/modules/*/router.py` files, the full `services/agents/assessment/`,
> `hackathon/`, and `supervisor/` subtrees, plus a repo-wide search for subprocess/git-clone
> calls. New findings are in **"Sweep 2"** below, ranked into the same Tier system. Nothing
> in the original Tier 1/Tier 2 lists changes.

> **Update 2026-08-02 (deployment/environment sweep):** A third investigation looked past
> code-level bugs at *why the entire app feels uniformly slow, not just AI-heavy pages*.
> Verdict: the dominant cause was **not code** — it was that the app ran as a single-worker
> dev server on localhost while its database and vector store were hosted remotely, so
> every query on every page paid a public-internet round trip. See **"Tier 0"** below.
>
> **RESOLVED 2026-08-16.** Postgres, Qdrant and Redis now all run as local Docker
> containers on loopback (`infra/docker-compose.yml`), which removes the network from the
> query path entirely. Tier 0 is kept below as the record of the diagnosis.

Date: 2026-08-02

## Summary

The "whole app feels slow" complaint traces to **synchronous, un-threaded blocking calls sitting directly inside async FastAPI/LangGraph request handlers**. A blocking call inside an `async def` stalls the *entire event loop* for that worker process — meaning every other concurrent user's request (dashboard, login, unrelated pages) queues behind it, not just the one action that's actually slow. This is a better explanation for global sluggishness than DB indexing or Next.js rendering, both of which were checked separately and found largely fine.

Three problem classes below: **Tier 0** (deployment/environment — the actual root cause of *uniform* slowness), **Tier 1** (event-loop-blocking code bugs — degrades the whole app under concurrency), and **Tier 2** (serial-but-non-blocking — slow for that one request only).

---

## Tier 0 — Deployment and environment (root cause of "everything is slow")

> **Fixed 2026-08-16 — the data tier is now entirely local.** Recorded as diagnosed.

**This app has never actually been deployed.** It runs as a local dev server on whatever
machine is running `uvicorn`, and at the time of this audit it talked to two *remotely
hosted* data services over the public internet, for every single request, on every page,
for every user:

- **Postgres** — hosted in a different AWS region than the machine running the app.
- **Vector store (Qdrant)** — hosted in a *third* region, different again from both.
- **Backend process** — started per `README.md` as `uvicorn services.api.main:app --reload --port 8000`: single-process, single-worker, dev auto-reload mode. No `gunicorn`, no `--workers`, no process manager.
- **No deployment config exists for this app.** The only `render.yaml` in the repo lives under `TEMP/` and belongs to a completely unrelated project (`backend-axle`, different stack, different env vars) — it is not wired to this codebase at all.

Why this explains *uniform* slowness (not just AI pages): `GET /me` fires on every
authenticated route-group navigation (`CurrentUserProvider`), dashboard endpoints fire on
every dashboard visit, login/signup happen constantly — every one of these paid a full
cross-region public-internet round trip before any application logic even ran.
Everything else in the request path was checked and is clean:

- DB pooling is correctly configured (`services/api/core/db.py`: `create_async_engine` with `asyncpg`, `pool_size=20`, `max_overflow=20`, `pool_pre_ping=True`, sessions properly scoped/closed via `async with` in `get_db()`). No leak, no `NullPool` misconfig, no per-request engine creation.
- `/me` (`services/api/core/rbac.py:35-52`) is a single indexed PK lookup with a cheap JWT decode and `@lru_cache`d settings — not slow itself, just multiplies fixed cross-region latency by call frequency.
- `/me/dashboard` (`candidates/router.py:783-806`) is 3 sequential simple indexed queries plus in-memory summation — not N+1.
- Frontend already dedupes the `/me` fetch across all 5 role layouts, batches dashboard calls into one request, and lazy-loads heavy libraries (`recharts`, `framer-motion`, `monaco-editor`, `pyodide`) off the shared bundle via `next/dynamic`.
- The embedding model is `@lru_cache`d and pre-warmed at startup (`main.py:110-129`), not reloaded per request.
- Redis is intentionally unused at this scale (rate limiting is in-memory by design, per its own docstring) — not a caching gap, since nothing expensive is actually recomputed per-request in the hot paths checked.

**A local offline profile already exists but isn't being used**: at the time of the audit
`infra/docker-compose.yml` defined `postgres` and `qdrant` under an opt-in
`profiles: ["offline"]` while `.env` pointed at remotely hosted equivalents, so dev work
paid full round-trip latency on every query even though nothing about the data needed to
be shared or persistent.

> *Since fixed:* the opt-in profile is gone. `postgres`, `qdrant` and `redis` are all
> plain services that come up together with `docker compose up -d`, and `.env` points at
> loopback.

### Three compounding issues, not one

1. **Cross-region network latency** (environmental) — ~50-150ms+ of unavoidable round trip per query, before any app logic runs. Dominant factor; explains uniform slowness even with zero concurrent load.
2. **Single-worker `--reload` dev server** (structural, but a config fix) — zero concurrency headroom, so every Tier 1 blocking-call bug below stalls *every other user*, always.
3. **The Tier 1/Tier 2 code bugs documented below** — real, but currently being measured against a baseline that's already slow for unrelated reasons. Fixing them without fixing #1/#2 will not make the app feel fast.

### Verdict: fix deployment, don't rewrite the architecture

There's no evidence of a system-design failure — pooling, caching, lazy-loading, and the
LangGraph fan-out patterns are all sound where checked. What's broken is deployment posture:
a dev box hitting cross-continent managed services in single-worker `--reload` mode. That's
an ops/config fix, not a system redesign.

---

## Tier 1 — Event-loop-blocking bugs

These stall every concurrent request on the worker, not just the slow one.

### 1. `services/agents/ppt_analyzer/nodes/slide_image_ocr.py:17-21` — worst offender

Loops over every slide **sequentially** (no `asyncio.gather`, no `to_thread`). Per slide:
- `ocr_image()` (`ppt_analyzer/tools/ocr.py:33-41`) — synchronous `pytesseract.image_to_string`, blocking.
- `vision_diagram_summary()` (`ocr.py:44-88`) — builds a **fresh `anthropic.Anthropic()` client per call** (line 48, bypasses the shared gateway in `services/api/core/llm.py` entirely) and makes a **synchronous blocking network call** to Claude vision.

For a 15-slide deck: up to 15 sequential blocking Claude calls (~1-3s each = 15-45s) plus 15+ sequential Tesseract calls, all on the event loop. Feeds into `technical_feasibility` on the PPT analysis critical path.

**Fix:** wrap both calls in `asyncio.to_thread`; parallelize across slides with bounded `asyncio.gather`. Route `vision_diagram_summary` through `generate_completion`/`generate_structured` in `services/api/core/llm.py` instead of a hand-rolled client.

### 2. `services/agents/fraud/tools/visual_forensics.py:55-112` (`_vision_pass`)

Same pattern: fresh `anthropic.Anthropic()` client (line 62) + synchronous `client.messages.create()`, called directly from `fraud/nodes/visual_forensics.py:7` with no threading. Blocks the loop on every certificate check that reaches the "no verification URL" branch of `cert_graph.py`.

**Fix:** thread it or route through the shared gateway.

### 3. `services/agents/candidate_intelligence/nodes/certificate_ocr.py:16` → `certificate.py:29-30`

`pytesseract.image_to_data()` called synchronously, un-threaded, inside `async def run()`. Runs on every signup/profile-update with a certificate upload.

**Fix:** `await asyncio.to_thread(extract_certificate, ...)`.

### 4. `services/agents/candidate_intelligence/nodes/resume_parser.py:21` → `resume.py:57-67`

`pdfplumber.open()` / `docx.Document()` (synchronous parsing) called directly inside `async def run()`, un-threaded. Runs on every resume upload.

**Fix:** `await asyncio.to_thread(extract_resume_text, ...)`.

### 5. `services/agents/candidate_intelligence/tools/skill_gap.py` (`analyze_skill_gaps`)

Called synchronously from `nodes/skill_gap_analysis.py:15` (no `await`/`to_thread`). Does up to 4 synchronous `model.encode()` calls (CPU-bound) plus multiple Qdrant round trips inline. First node in `career_guidance_graph.py`, which is already invoked synchronously inside the `GET /candidates/me/career-guidance` cache-miss path — compounds that bug by stalling unrelated requests network-wide, not just being slow for the caller.

**Fix:** `await asyncio.to_thread(analyze_skill_gaps, ...)` at minimum; longer-term this GET route shouldn't synchronously invoke a graph at all (background + poll, matching the pattern already used for ingestion/matching status).

### 6. `services/agents/ppt_analyzer/nodes/slide_embedding.py:17`

`model.encode()` called synchronously inside `async def run()`, un-threaded. Less severe (embeddings are fast) but still blocks the loop for large decks.

### 7. `services/agents/fraud/nodes/structural_similarity.py:10` → `tools/structural_similarity.py`

`compute_structural_similarity()` runs a CPU-bound O(corpus-size) pairwise comparison loop (`copydetect.compare_files` per corpus entry) synchronously inside `async def run()`. Real multi-second CPU stall on the event loop for large assessment cohorts.

### 8. `services/api/modules/candidates/router.py:918,923` (downstream of candidate_intelligence document generation)

`render_resume_pdf()` (WeasyPrint, CPU-heavy native rendering) and `upload_file()` (`cloudinary.uploader.upload`, blocking network call) both called synchronously, un-threaded, in the same async route handler — right after an LLM call for content generation. This one route blocks the loop through PDF render + Cloudinary upload on top of LLM latency.

---

## Sweep 2 — new findings (routers, assessment/hackathon/supervisor subtrees, subprocess/git audit)

Ranked by frequency × call cost, same as Tier 1 above — these are genuinely new Tier 1
event-loop-blocking bugs, not previously documented.

### S1. `services/api/core/security.py:10,15` (`bcrypt.hashpw` / `bcrypt.checkpw`) — likely the single highest-impact finding in this sweep

Called synchronously, un-threaded, from:
- `services/api/modules/users/router.py:40` — `hash_password()` inside `async def signup()` — **`POST /auth/signup`**
- `services/api/modules/users/router.py:80` — `verify_password()` inside `async def login()` — **`POST /auth/login`**

Bcrypt is deliberately CPU-slow (~100-300ms depending on cost factor, by design — that's the whole point of bcrypt). Login/signup are the highest-frequency, most latency-sensitive endpoints in the entire app. Every single login stalls the event loop for every other concurrent user for the full hash-verify duration. Unlike the Tier 1 items above (each gated behind a specific upload/action), this fires on literally every authentication.

**Fix:** `await asyncio.to_thread(hash_password, payload.password)` / `await asyncio.to_thread(verify_password, payload.password, user.password_hash)`.

### S2. `services/agents/assessment/nodes/static_analysis.py:12` → `tools/static_analysis.py`

`async def run()` calls `run_static_analysis(source)` directly and synchronously — no `asyncio.to_thread`. That function does real CPU/disk work on the event loop with no timeouts:
- `ast.parse()` + radon's `cc_visit`/`raw.analyze` (AST walking)
- `lizard.analyze_file()` — writes source to a `tempfile.NamedTemporaryFile` (blocking disk I/O), then parses it
- bandit's `BanditManager.discover_files()` + `.run_tests()` — another temp-file write plus a full bandit AST/rule scan

Triggered on **every `POST /assessments/{id}/submit`** for `coding`/`project_analysis` submissions — `verification_graph.py` runs `static_analysis` unconditionally at START before fanning out to `grading`/`llm_code_review`. Every candidate code submission stalls the event loop for the full radon+lizard+bandit pass.

**Fix:** `await asyncio.to_thread(run_static_analysis, source)`.

### S3. `services/api/modules/assessments/router.py:78-88` (`_fetch_repo_sample_source`), called at line 151

Plain synchronous PyGithub — `Github(retry=None)`, `client.get_repo(repo_full_name)`, `repo.get_contents("")` — called directly (no `await`, no `to_thread`) inside `async def submit_assessment()`, immediately before the verification graph runs. Triggered on **every `project_analysis`-type submission** — one blocking GitHub network round trip on the event loop per submission. The correct pattern already exists two calls away: `candidates/router.py:596-598`'s GitHub OAuth callback wraps the equivalent PyGithub call in `asyncio.to_thread`; this call site just didn't follow it. Also matches the exact pattern already fixed in `commit_attribution.py` (`assessment/tools/github_contribution.py`'s `attribute_commits` is correctly threaded via `nodes/commit_attribution.py:14-16`) — this router call site is the one place in the assessment path that didn't get the same treatment.

**Fix:** `await asyncio.to_thread(_fetch_repo_sample_source, repo_full_name)`.

### S4. `services/agents/ppt_analyzer/nodes/format_normalization.py:36` → `tools/extraction.py:65` (`convert_ppt_to_pptx` → `subprocess.run`)

`async def run()` calls `convert_ppt_to_pptx()` directly, which shells out to LibreOffice headless (`subprocess.run([...], timeout=60, ...)`) synchronously, un-threaded. Only triggered for legacy `.ppt` uploads (not `.pptx`/`.pdf`), so lower frequency than the above, but worst-case duration: a real subprocess spawn that can block the event loop for up to the full 60s timeout. Same graph/route as the already-documented `slide_image_ocr.py` finding (Tier 1 #1) — **`POST` pitch-deck upload**, `services/api/modules/presentations/router.py`.

**Fix:** `await asyncio.to_thread(convert_ppt_to_pptx, file_bytes, settings.libreoffice_binary)`.

### S5. `services/agents/ppt_analyzer/nodes/content_extraction.py:29,38,40` → `tools/extraction.py` (`extract_slides_from_pptx` / `extract_slides_from_pdf`)

`async def run()` calls these directly, un-threaded. `extract_slides_from_pptx` (python-pptx) and `extract_slides_from_pdf` (PyMuPDF rasterization) are synchronous CPU-bound parsing — same class of bug as the already-documented `resume_parser.py` (Tier 1 #4), just for the pitch-deck graph instead of candidate_intelligence. Runs on **every pitch-deck upload**, immediately before `slide_image_ocr`/`slide_embedding` (both already documented).

**Fix:** `await asyncio.to_thread(extract_slides_from_pptx, normalized)` (and the `_pdf` variant).

### S6. `services/api/modules/presentations/router.py:143` (`upload_file` → `cloudinary.uploader.upload`)

Called synchronously, un-threaded, inside `async def _analyze_presentation()`, scheduled via `background_tasks.add_task` from `POST /presentations/upload`. A distinct call site from the already-documented `candidates/router.py:923` (same underlying `services/api/core/storage.py:34` function, different caller) — FastAPI `BackgroundTasks` still run on the same event loop/worker, so this blocks concurrent requests during Cloudinary upload of every pitch deck.

**Fix:** `await asyncio.to_thread(upload_file, ...)`.

### S7. `services/api/modules/fraud/router.py:365,377` (`compute_photo_hash` — PIL decode + `imagehash.phash`)

Called synchronously, un-threaded, in a loop (lines 370-381) inside `async def check_profile_duplicate()` — `POST /verification/profiles/{candidate_id}/duplicate-check`. One synchronous PIL image open/crop/hash per candidate in the comparison corpus — N calls back-to-back for N corpus entries. Lower severity: reviewer-only/infrequent endpoint, individually fast, but compounds with corpus size.

**Fix:** `await asyncio.to_thread(compute_photo_hash, ...)` per candidate, or gather in a bounded threadpool batch.

### Verified clean in this sweep (ruled out)

- `services/api/modules/admin/router.py`, `hackathons/router.py`, `recruitment/router.py`, `candidates/router.py` (aside from already-documented 918/923), `public/router.py`, `supervisor/router.py` — fully async, DB-only or correctly-`await`ed graph/`httpx.AsyncClient` calls.
- `services/agents/assessment/tools/github_contribution.py`'s `attribute_commits` — synchronous PyGithub, but correctly wrapped in `asyncio.to_thread` at `nodes/commit_attribution.py:14-16`.
- All `services/agents/assessment/` LLM call sites route through `services/api/core/llm.py`'s `generate_structured` gateway — no hand-rolled clients.
- `services/agents/hackathon/` (all files beyond `repo_deck_linking.py`) — pure in-memory dict/list work or correctly-`await`ed LLM gateway calls, no I/O.
- `services/agents/supervisor/` (entire subtree) — thin async dispatch layer over already-audited, clean subsystems (`recruitment/matching_graph.py`, `classifier_llm.py` via the shared gateway).
- Repo-wide search for `subprocess.*`/`os.system`/GitPython `clone_from`: only one subprocess call exists in all of `services/` (`ppt_analyzer/tools/extraction.py:65`, S4 above); no GitPython repo-cloning anywhere — all GitHub interaction goes through PyGithub's REST API, not local clones.
- Repo-wide search for hand-rolled `anthropic.Anthropic()`/`openai.OpenAI()`: only the two already-documented sites (`ocr.py`, `visual_forensics.py`) plus the legitimate ones inside `services/api/core/llm.py` itself.
- Repo-wide search for `time.sleep(`: zero matches in `services/`.

---

## Tier 2 — Serial work that should be parallel

Slow for that one request; doesn't block other users.

### 9. `services/agents/candidate_intelligence/nodes/talent_scoring.py:39-72` — biggest serial-latency bug

Three expensive operations run fully sequentially via `await`:
- `code_quality_score` (threaded, samples up to 3 repos)
- `project_quality()` (`judgment_scores.py:115-140`) — **redundantly re-samples complexity a second time** via its own `sample_complexity()` call (line 121), despite the docstring (`judgment_scores.py:105-108`) claiming this sampling pass is shared/deduped — it isn't. Separate GitHub network round trips, plus 1 sequential LLM call (`_llm_quality_judgment`).
- `innovation()` (`judgment_scores.py:157-214`) — embedding + Qdrant + a second sequential `_llm_quality_judgment` call.

Every full talent-score computation (signup, GitHub refresh) does 2 sequential LLM round-trips plus a duplicated GitHub-sampling pass. Plausibly adds 5-10+ seconds per run.

**Fix:** `asyncio.gather(project_quality(...), innovation(...))` — they write disjoint dict keys, no data dependency. Pass `code_quality_score`'s already-computed `(avg_complexity, sampled_files)` into `project_quality` instead of re-sampling.

### 10. `services/agents/fraud/plagiarism_graph.py`

Sequential `structural_similarity → public_repo_crosscheck → plagiarism_verdict`. The docstring admits `public_repo_crosscheck` doesn't depend on `structural_similarity`'s output — it's sequential purely to avoid a state-reducer for the `context` dict. Unlike `duplicate_graph.py` (where this tradeoff is justified — no network calls), `public_repo_crosscheck` does a real GitHub network round trip via `to_thread`, so serializing after a CPU-bound pass adds real wall-clock for no correctness reason.

**Fix:** fan both out from START (same pattern already used in `candidate_intelligence/graph.py` and `ppt_analyzer/graph.py`), merge into `plagiarism_verdict`.

### 11. `services/agents/ppt_analyzer/tools/plagiarism.py:54-62`

Per-slide sequential `client.search()` calls to Qdrant instead of `search_batch` — the exact batching fix already applied elsewhere in this codebase (`recruitment/tools/embeddings.py:batch_candidate_project_relevance`). Individually fast, but N serial round trips add up for large decks.

> **Fixed.** `plagiarism.py` now issues one `query_batch_points()` call for the whole deck. Note the method name: `search_batch` was removed in qdrant-client 1.18, and calling it raised `AttributeError` inside a blanket `except Exception: return []` — so plagiarism checking reported "no matches" for **every** deck rather than surfacing the breakage. Both halves are fixed: the call, and the swallow that hid it (see doc 07).

---

## Verified NOT bugs (ruled out)

- `candidate_intelligence/graph.py`, `ppt_analyzer/graph.py`, `assessment/verification_graph.py`, `recruitment/matching_graph.py` all correctly fan out independent nodes.
- ~~`services/api/core/llm.py` has **no retry/backoff decorator** — single-attempt, fails fast (`LLMUnavailable`). No retry-amplification risk in the shared gateway.~~
  **Superseded 2026-08-19.** This was accurate when audited and is no longer true. The gateway now retries via `_call_with_retry()`: exponential backoff with jitter, bounded by `LLM_MAX_RETRIES` (default 2), and *only* for error classes that can actually succeed on a second attempt. `LLMQuotaExhausted` and `LLMNotConfigured` are explicitly never retried, so the retry-amplification concern noted here does not apply to the two failure modes where amplification would be pure waste. Calls are also bounded by `LLM_TIMEOUT_SECONDS` (default 60), which the single-attempt version lacked entirely — an unbounded call could hold a request open indefinitely. See doc 11 for the full taxonomy.
- `recruitment/copilot_graph.py`, `assessment/interview_graph.py`, `hackathon/graph.py`, `fraud/duplicate_graph.py`, `fraud/cert_graph.py` are inherently sequential (genuine data dependencies or well-justified low-cost tradeoffs) — not bugs.
- `get_llm_client()`'s per-call SDK client rebuild (known, lower-severity finding) does **not** cover the two hand-rolled `anthropic.Anthropic()` sites above (`ocr.py`, `visual_forensics.py`) — those bypass the gateway entirely and need their own fix.
- DB indexes on hot paths (candidates, jobs, match_scores) were checked separately and found adequate — this is not primarily a database bottleneck.

---

## Fix order — full plan (Tier 0 → Tier 2)

Ordered by leverage: each phase is close to worthless without the one before it. Threading
blocking calls (Phase 2) matters far less if the app is still single-worker on a dev box
1,500 miles from its database (Phase 0) — you'd be optimizing a request that still pays
150ms of unavoidable network latency either way.

### Phase 0 — Deployment/environment (do this first; nothing else matters until this is done)

**What:** stop paying a cross-region network round trip on every query.

**Done 2026-08-16.** Postgres, Qdrant and Redis are now first-class services in
`infra/docker-compose.yml`, all reached over loopback:

1. `docker compose -f infra/docker-compose.yml up -d` brings up all three.
2. `.env` points `DATABASE_URL` at `localhost:5432` and `QDRANT_URL` at `localhost:6333`,
   with `DATABASE_SSL_REQUIRED=false`.
3. `alembic upgrade head`, then the seed scripts in `scripts/`.

This removed the network from the query path entirely, which was the single largest
latency win available.

**If this app is ever actually deployed**, the remaining Tier 0 items still apply: run it
with a real process manager rather than a single dev worker (`--workers N` behind
`gunicorn -k uvicorn.workers.UvicornWorker`), deploy the Next.js frontend pointed at the
real API URL rather than `localhost:8000`, and co-locate the app with its database in one
region. Worker-count and CDN tuning only become meaningful after that exists.

### Phase 1 — Highest-frequency single-line fixes (ship immediately, trivial risk)

1. **Thread `bcrypt.hashpw`/`bcrypt.checkpw`** in `services/api/core/security.py`, called from `users/router.py:40,80`. Highest-frequency endpoint in the app (every login/signup). `await asyncio.to_thread(hash_password, ...)` / `await asyncio.to_thread(verify_password, ...)`.

### Phase 2 — Thread every remaining blocking call inside async handlers

All of these are mechanical `asyncio.to_thread(...)` wraps around an existing synchronous function call — no logic changes, low risk, can be done as one batch PR:

2. `ppt_analyzer/nodes/slide_image_ocr.py` (biggest single chain — up to 15-45s per PPT upload) — thread both `ocr_image()` and `vision_diagram_summary()`; also parallelize across slides with bounded `asyncio.gather` instead of a serial loop.
3. `fraud/tools/visual_forensics.py`'s `_vision_pass`
4. `candidate_intelligence/nodes/certificate_ocr.py`
5. `candidate_intelligence/nodes/resume_parser.py`
6. `candidate_intelligence/tools/skill_gap.py`
7. `assessment/nodes/static_analysis.py` (S2)
8. `ppt_analyzer/nodes/content_extraction.py` (S5)
9. `ppt_analyzer/nodes/format_normalization.py`'s `subprocess.run` LibreOffice call (S4) — worst case 60s block
10. `candidates/router.py:918,923` — `render_resume_pdf` (WeasyPrint) and `upload_file` (Cloudinary)
11. `presentations/router.py:143` — second `upload_file` site (S6)
12. `assessments/router.py:78-88,151` — `_fetch_repo_sample_source` (S3, sync PyGithub)
13. `fraud/router.py:365,377` — `compute_photo_hash` (S7, lower priority — reviewer-only path)
14. `ppt_analyzer/nodes/slide_embedding.py`
15. `fraud/nodes/structural_similarity.py`

### Phase 3 — Route hand-rolled LLM clients through the shared gateway

16. Replace the two hand-rolled `anthropic.Anthropic()` client constructions (`ppt_analyzer/tools/ocr.py:48`, `fraud/tools/visual_forensics.py:62`) with calls through `services/api/core/llm.py`'s `generate_completion`/`generate_structured` — gets threading, tracing, and client reuse for free instead of duplicating it ad hoc.

### Phase 4 — Serial-latency fixes (slower for that one request, not blocking others — lower urgency than Phase 0-3)

17. Parallelize `talent_scoring.py`'s `project_quality`/`innovation` calls via `asyncio.gather`; dedupe the redundant double GitHub complexity-sampling between them.
18. Fan out `plagiarism_graph.py`'s `structural_similarity`/`public_repo_crosscheck` from START instead of running them sequentially.
19. Batch `ppt_analyzer/tools/plagiarism.py`'s per-slide Qdrant `search()` calls into `search_batch`.

### Phase 5 — UX: make waiting feel fast (independent of backend fixes above)

20. Build a shared ambient-loading component (rotating status phrases + subtle animation, Claude-style) for every AI-backed wait — PPT analysis, talent scoring, career guidance, copilot, matching. Use it even when no real progress data exists yet; swap in real progress once a phase completes if available. This directly addresses "no loaders, no animations, feels dead" independent of whether the underlying call is actually fast yet.
21. Swap the ~8 pages using a bare `Loading…` string for the `CardListSkeleton`/`KanbanSkeleton` components that already exist and are used correctly elsewhere (matches, pipeline pages) — cheap, mechanical, consistent polish.
22. Fix `jobs/[id]/matches` page to poll `matching-status` instead of showing a permanent false "no candidates yet" message.

---

## Related: frontend "feels slow" findings (separate investigation)

Not blocking backend fixes above, but contributes to perceived slowness:

- `RoleIndicator.tsx` reads `useAuth().user`, a field that doesn't exist on `AuthContextValue` — fails `tsc --noEmit`, renders nothing at runtime. Rendered in the global header on every page. **Fix:** use `useCurrentUser()` / `me?.profile?.role` instead; also needs `CurrentUserProvider` moved up to wrap the header, not just `{children}`.
- `apps/web/src/app/(organizer)/hackathons/[id]/manage/page.tsx` fires every fetch twice (both the `load` callback and the mount effect independently call `fetchHackathon` + `fetchHackathonTeams`).
- `apps/web/src/app/(recruiter)/jobs/[id]/matches/page.tsx` never polls matching status — shows a permanent false "no candidates yet" message even when matching is still processing or failed.
- ~8 pages use a bare `Loading…` string instead of the existing `CardListSkeleton`/`KanbanSkeleton` components already used elsewhere (matches, pipeline pages) — cheap, mechanical fix for visual consistency.
- Loading-state infrastructure (skeletons, disabled buttons, `useAsyncResource`) already exists and is used correctly on most pages — this is not a systemic absence, just inconsistent application.

## Related: API access-control and correctness findings (separate investigation)

- `DELETE /admin/trusted-issuers/{issuer_id}` (`services/api/modules/fraud/router.py:717`) returns an undefined variable `flag` after the delete/commit already succeeded — always throws `NameError`/500 despite the mutation succeeding.
- `get_assessment`/`get_submission` (`services/api/modules/assessments/router.py`) have no ownership check — any candidate can read another candidate's hidden test cases by guessing/enumerating assessment UUIDs; any recruiter can read any candidate's submission.
- Pitch-deck status/report/plagiarism-matches endpoints (`services/api/modules/presentations/router.py:319-403`) have no ownership check — any authenticated user can view any other candidate's presentation report by UUID.
- The old workers package was a non-functional stub (since removed) — all real background work runs via FastAPI's in-process `BackgroundTasks`, so a crash/redeploy mid-task leaves `matching_status`/`ingestion_status`/presentation `status` stuck at `"processing"` forever with no recovery.
