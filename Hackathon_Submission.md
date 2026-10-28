# TRACE — Talent Reliability & Assessment through Credential Evidence
### Hackathon Submission Document

---

## Table of Contents

1. **Executive Summary & Core Value Proposition**
   1. Executive Summary
   2. System Vision, Scope & Primary Objectives
   3. Key Differentiators & Industry Alignment
2. **System Architecture & Technical Design**
   1. Overall System Architecture & Data Flow
   2. Technology Stack
   3. Modular System Components
   4. Infrastructure & Scalability Strategy
3. **Repository & Directory Structure**
   1. Folder Hierarchy & File Layout
   2. Key File Responsibilities
   3. Codebase Navigation Guide
4. **Detailed Feature Breakdown & User Workflows**
   1. Security & Credential Management
   2. Core Business Logic & Execution Engines
   3. User Interface, Dashboards & Visualizations
   4. Real-Time Systems & Integration Layers
5. **Mathematical Foundations & Quantitative Frameworks**
   1. Core Mathematical Formulations & Algorithms
   2. Statistical Models & Distributional Methods
   3. Analytical Calculators & Indicator Derivations
   4. Mathematical Formulation Summary Matrix
6. **Database Schema & Security Infrastructure**
   1. Entity-Relationship Overview
   2. Complete SQL Migration Scripts & DDL
   3. Row-Level Security (RLS) & Access Control Policies
7. **Local Development & Installation Guide**
   1. Prerequisites & System Requirements
   2. Step-by-Step Setup & Configuration
   3. Environment Variables Reference
   4. Running the Local Development Suite
8. **Verification, Testing & Quality Assurance**
   1. Static Type Analysis & Code Audits
   2. Algorithm & Simulation Validation
   3. Operational Guardrails & Edge-Case Handling
9. **Multi-Platform Deployment & DevOps Pipeline**
   1. Static Web Deployment (Vercel / Netlify)
   2. Containerized Deployment (Docker / Nginx)
   3. Native Mobile Compilation (Android / Capacitor)
10. **Project Changelog, Roadmap & License**
    1. Build Phases & Version Control Conventions
    2. Future Roadmap & Milestone Objectives
    3. Troubleshooting Matrix
    4. Licensing & Intellectual Property Terms
    5. Error Log Book

---

# 1. Executive Summary & Core Value Proposition

## 1.1 Executive Summary

Hiring runs on documents that nobody can verify. A resume asserts five years of Python; a certificate PDF asserts a credential; a hackathon win asserts that someone built something. Recruiters read all of it and guess. The candidates who get through are frequently the ones who write the best claims, not the ones who wrote the best code.

TRACE inverts that. It scores people on artifacts that are expensive to fake: commit history, merged pull requests to repositories they don't own, code written under a timer, answers given in a live interview. The resume is treated as the least trustworthy input in the pipeline rather than the primary one.

The platform is a Python monorepo: a FastAPI backend, sixteen LangGraph agent subgraphs, PostgreSQL for relational state, Qdrant for vector search, and Redis backing shared rate-limit counters. The frontend is Next.js 16 with React 19. It serves five distinct roles (candidate, recruiter, organizer, judge, admin), and each role has its own App Router route group and its own access boundary.

Four things run end to end. A **Talent Score** engine ingests GitHub, resumes, certificates and assessment results, then produces nine sub-scores plus a weighted composite, every one of them carrying the evidence that produced it. A **job matching engine** scores candidate–job pairs on a four-term formula blending skill overlap, embedding similarity, experience fit and job-contextual talent alignment. A **hackathon-to-hiring pipeline** takes team submissions, analyzes pitch decks through four parallel LLM sub-agents, aggregates judge scores, and pushes top performers into recruiter feeds. A **trust and fraud layer** runs certificate OCR verification, code plagiarism detection, duplicate-profile matching and AI-content heuristics. Critically, none of it silently moves a number.

That last constraint shaped more of the codebase than any other. A fraud flag sitting in the review queue has exactly zero effect on a candidate's authenticity score. Only a flag a human has moved to `upheld` applies its penalty. The same discipline runs through scoring: when a signal is missing, its weight is redistributed across the signals that do exist and the candidate is told which ones were dropped. Nothing is quietly zero-filled, and no score is ever presented as a bare number without the components behind it.

## 1.2 System Vision, Scope & Primary Objectives

Six engineering goals drove the design. Each one is enforced somewhere concrete in the code, not just stated here.

**Evidence-backed scoring, with no fabricated values.** Every sub-score resolves to either a real number with attached evidence or an explicit `None`. `weighted_renormalized_mean()` in `services/agents/common/scoring.py` returns `None` when every input term is missing. That is deliberate: no caller can mistake "we have no data" for "this candidate scored zero." When an LLM provider key is absent, rubric scoring raises `PitchScoringUnavailable` and the node degrades to a `None`-valued score rather than inventing one.

**Anti-gaming through population-relative normalization.** Fixed-constant scaling like `log1p(stars)/log1p(100)` is trivially reverse-engineered. Publish the formula and candidates farm to the threshold. Sub-scores instead percentile-rank against the actual candidate population, so a star count only scores well if it beats real peers. Below a 30-candidate floor the ranks are statistically meaningless, so the code falls back to the fixed formula rather than pretending otherwise.

**No request waits on an AI pipeline.** Long AI pipelines run as FastAPI background tasks after the response has been sent, so the endpoint returns immediately and the UI tracks progress through a status column. Request handlers that invoke a LangGraph pipeline wrap it in `db.without_db_connection()`, returning the pooled Postgres connection for the seconds or minutes the LLM call takes. Without this, twenty concurrent AI interviews would pin all twenty pool connections, and every unrelated endpoint would block until timeout, including trivial reads.

**Graceful degradation over hard dependencies.** Redis down? The rate limiter falls back to bounded per-process counters. No Anthropic key? Agents degrade to deterministic rules. Qdrant unreachable? Skill matching falls back to exact string comparison. The system has exactly one genuinely required dependency, Postgres. Everything else is an upgrade.

**Human review as a hard gate on anything punitive.** Fraud detection is advisory by construction. `compute_authenticity_score()` accepts only flags the caller has already filtered to `status='upheld'`, and its docstring states the constraint bluntly because the function cannot check status itself.

**Sub-second interactive reads.** Hot-path foreign keys carry explicit indexes: `idx_github_snapshots_candidate`, `idx_badges_candidate`, `idx_applications_job_stage`, `idx_scores_candidate_time`. Postgres does not index foreign keys automatically, and the recruiter candidate-pool build reads across the entire snapshot table on every request. Unindexed, that is a sequential scan on the hottest path in the product.

## 1.3 Key Differentiators & Industry Alignment

Most ATS and talent products in this space do keyword matching against resume text, then bolt a chatbot on top. The differences here are structural rather than cosmetic.

**Verified signals outrank self-declared ones, arithmetically.** In `skill_overlap()`, a skill backed by GitHub language statistics or a verified certificate earns a full point. The same skill typed into a resume earns 0.6. This is not a UI badge. It is the actual coefficient in the formula, which is what makes keyword-stuffing score measurably lower than substantiated experience.

**Semantic skill matching that handles near-misses.** Under pure string comparison, a candidate listing "Vue.js" against a job requiring "React" scores zero overlap on that term despite the obvious adjacency. Required skills with no literal match therefore fall back to embedding similarity, earning partial similarity-scaled credit above a threshold. That credit is discounted like an unverified match, since it is inferred rather than claimed.

**Job-contextual talent scoring.** A single global talent number is close to useless to a recruiter, because it doesn't say whether the candidate is strong *at the thing being hired for*. `talent_score_alignment()` recomputes the composite with `coding_ability` and `problem_solving` scaled by the candidate's overlap with that specific job's requirements, and `project_quality`/`innovation` scaled at 0.8× that ratio. The same person legitimately scores differently against a Rust systems role than against a React frontend role.

**Cold start treated as a modeling problem, not an error state.** New candidates have no assessments, thin commit history and no hackathon record. Rather than scoring them near zero, missing components drop out and remaining weights renormalize to sum to 1.0. An Evidence Confidence Score of `available_signals / expected_signals` ships alongside, so a recruiter can distinguish a genuinely low score from a low-evidence one. The score is never withheld. It is labeled.

**Explainability as a schema constraint.** `match_scores` persists all five component columns, not just the composite. `talent_scores` persists `renormalized_subscores` recording exactly which signals were dropped. The provenance survives in the database, so a recruiter challenged on a decision six months later can reconstruct it.

---

# 2. System Architecture & Technical Design

## 2.1 Overall System Architecture & Data Flow

Five layers, with a hard rule between them: HTTP handlers own database sessions, and agent code never touches the database. Agent tools are pure functions that receive their data as arguments and return values. That is what makes the scoring logic unit-testable without a database, and it is why `mechanical_scores.py` takes `commit_population` as a parameter instead of querying for it.

```
   Sources     GitHub · LeetCode · Resume · Certificates · Pitch decks
                                  |
                          OAuth / upload
                                  |
   Web         apps/web — Next.js, six role-scoped route groups,
               bearer JWT (public portfolio pages are unauthenticated)
                                  |
   API         services/api — FastAPI. CORS -> rate limit -> router,
               every endpoint behind require_role()
                                  |
                  +---------------+---------------+
                  |                               |
         background task                    read path: indexed
                  |                         SQL, no LLM call
   Pipelines FastAPI BackgroundTasks               |
             5 pipelines, run after the response   |
                  |                                |
   Agents    services/agents — 16 LangGraph subgraphs
             nodes/ orchestrate, tools/ compute, prompts/ are Jinja2
                  |
             core/llm.py — one gateway over five providers
             core/tracing.py — Langfuse spans per generation
                  |
   Storage   Postgres 16 — 34 tables, 31 migrations
             Qdrant — embeddings with payload filters
             Redis 7 — rate-limit counters (optional)
```

The path a candidate profile actually takes: OAuth callback lands in `candidates/router.py`, the row's `ingestion_status` flips to `processing` and the ingestion pipeline is scheduled as a background task. The endpoint returns immediately rather than running the pipeline inline and holding the HTTP connection open for minutes. The background task then walks the GitHub crawl, resume parse, certificate OCR, profile merge, fact-check and scoring nodes, writing `ingestion_stage` at each phase boundary. The frontend polls `GET /candidates/me/ingestion-status` and renders a stepwise progress UI from that column. A single unchanging "analyzing…" spinner for four minutes is indistinguishable from a hang, and users reasonably report it as one. The column exists to make the wait legible rather than merely shorter.

## 2.2 Technology Stack

**Backend** — Python 3.12, FastAPI 0.140 on Uvicorn, SQLAlchemy 2.0 with asyncpg,
Alembic 1.18, Pydantic 2.13 (+ pydantic-settings).

**AI** — LangGraph 1.2 and langchain-core 1.5 (primitives only; the heavier
LangChain abstractions are deliberately unused). `anthropic` 0.120 is the default
provider; the `openai` SDK 2.50 covers four more, since OpenAI, Groq, xAI and
Gemini all speak the same protocol. Embeddings are local —
`BAAI/bge-large-en-v1.5` via sentence-transformers 5.6 on torch 2.13, so there is
no per-embedding cost, no rate limit and it works offline. Langfuse 4.14 traces
each generation; empty keys are a no-op rather than a crash.

**Storage** — Postgres 16, Qdrant, Redis 7, with qdrant-client 1.18 and redis-py
5.3. Qdrant is there for payload filtering specifically: recruiter search means
"semantically similar *and* `is_remote = true`", which pure-vector stores handle
badly.

**Documents and analysis** — PyMuPDF (PDF), python-docx, python-pptx,
pytesseract + Pillow (OCR), ImageHash (duplicate photos), datasketch (MinHash
LSH), copydetect (code plagiarism), scikit-learn (salary ridge regression),
NumPy.

**Security and integration** — bcrypt 5.0, python-jose (HS256 JWT), PyGithub
2.9, httpx (LeetCode and GitHub GraphQL), cloudinary, sentry-sdk.

**Frontend** — Next.js 16 (App Router), React 19 with Server Components,
TypeScript in strict mode, and Tailwind CSS v4 via the PostCSS plugin. App
Router route groups map one-to-one onto the roles, so the access boundary is
visible in the directory tree. shadcn/ui and Base UI primitives are owned
in-repo under `components/ui/`. Recharts drives the radar, funnel, histogram and
heatmap visualizations, Monaco Editor backs the assessment page, dnd-kit powers
the recruiter kanban, Framer Motion handles transitions, and Playwright covers
end-to-end browser tests.

Pyodide 314 is the one frontend dependency that is a security decision before it
is a feature. Candidate code runs in the browser's WebAssembly (WASM) sandbox: executing
arbitrary submitted Python server-side would need container isolation, syscall
filtering and resource caps to be safe. In the browser the untrusted code never
reaches our infrastructure, and a malicious submission can at worst hang the
submitter's own tab.

## 2.3 Modular System Components

**Candidate Intelligence** (`services/agents/candidate_intelligence/`) is the largest module. Its main `graph.py` orchestrates resume parsing, GitHub analysis, certificate OCR, profile merge, fact-checking and scoring. Three sibling graphs handle career guidance, resume generation and document workflows. The `tools/` directory holds the pure scoring functions — `aggregate.py`, `mechanical_scores.py`, `normalization.py`, `open_source_score.py`, `hackathon_score.py` — each independently testable.

**Recruitment** (`services/agents/recruitment/`) runs two graphs. `matching_graph.py` embeds the job, retrieves candidates via hybrid search, scores each on the four-term formula, computes project relevance, reranks and generates natural-language fit explanations. `copilot_graph.py` handles recruiter free-text queries: intent classification, search planning, then structured retrieval.

**Assessment** (`services/agents/assessment/`) covers four graphs: code verification with static analysis plus LLM review, the live AI interview loop handling question generation, turn evaluation and adaptive follow-ups, interview report synthesis, and GitHub contribution analysis with commit attribution.

**PPT Analyzer** (`services/agents/ppt_analyzer/`) fans out to four rubric sub-agents in parallel, covering problem/solution clarity, innovation and business impact, technical feasibility, and presentation quality, then aggregates at equal weight. It also runs slide embedding for cross-deck plagiarism and a burstiness-based AI-content heuristic.

**Hackathon** (`services/agents/hackathon/`) links repos to decks, computes cross-event novelty, aggregates the composite ranking and notifies watching recruiters.

**Fraud** (`services/agents/fraud/`) runs four independent graphs: certificate verification against a trusted-issuer registry with visual forensics, code plagiarism, duplicate profile detection via perceptual photo hashing and text fingerprinting, and AI-content analysis.

**Supervisor** (`services/agents/supervisor/`) classifies incoming intent and routes to the right subgraph. It is the entry point for conversational queries that do not map cleanly to one endpoint.

## 2.4 Infrastructure & Scalability Strategy

Everything stateful runs locally in Docker, co-located with the services that read it. The alternative — managed Postgres and vector search in a different region than the application — makes every query on every page pay a cross-region public-internet round trip, so page loads stretch into seconds while actual query execution stays in single-digit milliseconds. Co-location removes that entirely and costs nothing but a compose file.

The connection pool is sized at 20 with 20 overflow. That is ample *only* because no request holds a connection across a slow AI call. The `without_db_connection()` wrapper is what makes the number work. A bigger pool is not a substitute for releasing connections. It just delays the same exhaustion.

Three scaling axes exist without architectural change. API processes scale horizontally behind a load balancer, since all session state lives in the JWT and rate-limit counters live in Redis. Background pipelines run inside each API process, so adding API processes also adds pipeline capacity, at the cost of one resident sentence-transformer model (~1.3 GB) per process. Postgres scales via read replicas for the analytics endpoints, which are the only genuinely read-heavy paths.

Re-running a pipeline is safe at the data layer rather than the scheduling layer. Matching updates existing `match_scores` rows in place, and `UNIQUE (job_id, candidate_id)` guarantees a re-run can never duplicate them. There is no job-level deduplication, so a double-clicked "Recompute" does start two runs; the constraint keeps the result consistent, but the work is done twice.

---

# 3. Repository & Directory Structure

## 3.1 Folder Hierarchy & File Layout

A monorepo with four areas: shared code in `packages/`, runnable processes in
`services/`, the UI in `apps/web`, containers and helper scripts around them.

```
TRACE/
|-- infra/docker-compose.yml   Postgres 16 + Qdrant + Redis 7
|-- scripts/                   dev-up.ps1, DB seeders, Qdrant index backfill
|
|-- packages/                  shared across services
|   |-- db/models/             SQLAlchemy 2.0 ORM, 34 tables
|   |-- db/migrations/         Alembic, 31 revisions, linear chain
|   |-- shared_schemas/        Pydantic contracts: API <-> agents <-> frontend
|   `-- prompts/               versioned Jinja2 templates + registry
|
|-- services/
|   |-- api/                   FastAPI
|   |   |-- main.py            app factory, middleware order, lifecycle
|   |   |-- core/              config, db, security, rbac, rate_limit,
|   |   |                      redis_client, llm, qdrant, tracing, storage
|   |   `-- modules/           one router package per domain (10)
|   |-- agents/                16 LangGraph subgraphs across 7 domains:
|   |   |                      candidate_intelligence, recruitment, assessment,
|   |   |                      ppt_analyzer, hackathon, fraud, supervisor
|   |   `-- <domain>/          *_graph.py, state.py, nodes/, tools/, tests/
|
|-- apps/web/src/
|   |-- app/                   route groups: (public) (candidate) (recruiter)
|   |                          (organizer) (judge) (admin)
|   |-- components/            ui/ charts/ common/ + feature components
|   `-- lib/ hooks/            API client, Pyodide runner, useAsyncResource
|
`-- Documentation/             16 architecture and module specs
```

Every agent domain has the same shape, which is the point: `*_graph.py` defines
the state machine, `state.py` types its state, `nodes/` orchestrates, `tools/`
holds the pure functions, and `tests/` covers those tools without a database.

## 3.2 Key File Responsibilities

| Path | Responsibility |
| :--- | :--- |
| `services/api/main.py` | Builds the FastAPI app, orders CORS before rate limiting so a 429 still carries CORS headers, registers ten routers, installs three exception handlers, starts the outbox poller and pre-warms the embedder |
| `services/api/core/config.py` | Every environment variable the system reads, typed with defaults. Heavily commented with the reasoning behind each tuning constant |
| `services/api/core/db.py` | Async engine, pool configuration, `get_db` dependency, and `without_db_connection()` — the context manager that releases the pooled connection across slow LLM calls |
| `services/api/core/rbac.py` | JWT decode, user resolution, and the `require_role(*roles)` dependency factory that gates every protected endpoint |
| `services/api/core/rate_limit.py` | Fixed-window rate limiter: shared Redis counters, with a bounded in-memory fallback when Redis is unreachable |
| `services/api/core/llm.py` | Five-provider gateway behind `generate_completion`/`generate_structured`. Client is an `lru_cache` singleton |
| `services/agents/common/scoring.py` | `weighted_renormalized_mean()` — the cold-start arithmetic shared by Talent Score, Pitch Score, Hackathon Ranking, Job Matching and Coding Ability |
| `services/agents/candidate_intelligence/tools/aggregate.py` | The nine sub-score weights and the Evidence Confidence calculation |
| `services/agents/candidate_intelligence/tools/normalization.py` | Percentile normalization, exponential recency decay, winsorization |
| `services/agents/recruitment/tools/matching.py` | The four-term match formula, verified-skill weighting and job-contextual talent adjustment |
| `services/agents/fraud/tools/aggregation.py` | Authenticity penalty table and the upheld-flags-only contract |
| `apps/web/src/lib/api.ts` | Typed fetch wrapper; injects the bearer token and normalizes error envelopes |
| `apps/web/src/lib/pyodideRunner.ts` | Loads Pyodide, executes candidate code in the WebAssembly sandbox, captures stdout and exceptions |
| `apps/web/src/hooks/useAsyncResource.ts` | Polls a status endpoint with timeout and retry — the hook behind every progress UI |

## 3.3 Codebase Navigation Guide

Some orientation for anyone reading the source directly.

*To follow a request end to end*, start at the router in `services/api/modules/<domain>/router.py`. Handlers are ordered roughly by resource. The handler validates via a `packages/shared_schemas` model, checks authorization through `require_role`, then either queries directly or schedules a background pipeline.

*To understand a score*, ignore the graphs and go straight to `tools/`. Every scoring function is pure and reads top to bottom without needing a database. `aggregate.py` gives the composite; `mechanical_scores.py` gives the individual sub-scores.

*To modify agent behavior*, note the split: `nodes/` handles orchestration and state transitions, `tools/` holds the actual logic. A node function is typically a dozen lines that unpacks state, calls a tool, and writes the result back.

*To add a database column*, edit the model in `packages/db/models/`, then `alembic revision --autogenerate -m "..."`, then read the generated migration carefully, because autogenerate misses CHECK constraint changes and server defaults with some regularity.

*Naming conventions*: `*_graph.py` is a LangGraph `StateGraph` definition. `state.py` is the typed state for that subgraph. Files under `nodes/` export a single async function named for the file. Files under `tools/` export several pure functions.

---

# 4. Detailed Feature Breakdown & User Workflows

## 4.1 Security & Credential Management

### 4.1.1 Password Authentication

We evaluated a managed auth provider and decided against it. It adds a network hop and an external dependency to every authenticated request, which is a poor trade when the requirement is five roles and a token. The implementation is self-hosted bcrypt plus HS256 JWT.

**Input.** `POST /auth/signup` with email, password, full name and role, or `POST /auth/login` with email and password.

**Processing.** Signup hashes with bcrypt using a per-password salt from `gensalt()`. Login runs `checkpw` against the stored hash, wrapped in a try/except that returns `False` on any exception. A malformed hash in the database must read as a failed login, never as a 500 that leaks the malformation.

```python
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, settings: Any) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=settings.jwt_expiry_seconds)
    claims = {"sub": user_id, "exp": expire, "iat": now}
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

**Output.** An HS256 JWT carrying `sub`, `iat` and `exp`, with a seven-day default lifetime.

### 4.1.2 Role-Based Access Control

Five roles, enforced at the database with a CHECK constraint and at the API with a dependency:

```sql
CHECK (role IN ('candidate','recruiter','organizer','judge','admin'))
```

`require_role` returns a FastAPI dependency, so authorization is declared in the route signature rather than performed in the body. An endpoint therefore cannot accidentally skip it through an early return.

```python
def require_role(*roles: Role | str):
    allowed = {r.value if isinstance(r, Role) else r for r in roles}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")
        return user

    return dependency
```

Role membership is not sufficient on its own. Ownership is checked separately. A recruiter with a valid token still cannot read a job posted by a different recruiter, because the handler filters on `posted_by_user_id` as well.

### 4.1.3 Rate Limiting

A fixed-window limiter, Redis-backed with a bounded in-memory fallback. Counters are shared rather than process-local: a purely in-process limiter running under Uvicorn with four workers silently quadruples the effective limit, and every counter resets on restart.

Buckets key on the authenticated user ID when a bearer token is present, falling back to client IP. The user ID is read from the *unverified* JWT payload. That is deliberate and safe, because this is a bucket key rather than an authorization decision. A forged token at worst lands in a different bucket, and `rbac.py` still rejects it afterwards. Running full verification twice per request purely to pick a bucket key isn't worth it.

The in-memory fallback is capped at 10,000 tracked buckets. An uncapped `defaultdict` grows forever, one permanent entry per distinct IP — a slow memory leak on anything internet-facing.

`/health` is exempt so uptime checks never 429.

## 4.2 Core Business Logic & Execution Engines

### 4.2.1 Candidate Ingestion & Talent Score

**Input.** A resume upload, a certificate image, a GitHub OAuth grant, or a LeetCode username.

**Processing.** The endpoint writes `ingestion_status = 'processing'`, schedules the ingestion pipeline as a background task, and returns immediately. The task executes the pipeline, updating `ingestion_stage` at each phase so the UI can show real progress:

```
resume_parser ──┐
github_analysis ├──> profile_merge ──> fact_check ──> talent_scoring ──> badge_assignment
certificate_ocr ┘         │
                          └──> ConflictResolver surfaces contradictions to the candidate
```

The merge step is where contradictions surface, such as a resume claiming five years of Go against a GitHub account with no Go repositories. Conflicts are written to `merged_conflicts` and shown in the UI rather than being silently resolved in favor of one source.

**Output.** A `talent_scores` row with nine sub-scores, a composite, `renormalized_subscores` listing what was dropped, and the three Evidence Confidence columns.

### 4.2.2 Job Matching Engine

**Input.** A recruiter creating or recomputing a job posting.

**Processing.** `matching_graph.py` embeds the job description, retrieves a candidate pool through hybrid search combining Qdrant vector similarity with payload filters, scores each pair on the four-term formula, computes project relevance, reranks, and generates a fit explanation.

The skill overlap function is where the anti-gaming intent is most visible:

```python
def skill_overlap(candidate_skills: list[CandidateSkillSignal], required_skills: list[str]) -> float:
    if not required_skills:
        return 0.0
    candidate_by_name = {s.name.lower(): s.verified for s in candidate_skills}
    candidate_names = [s.name for s in candidate_skills]
    earned = 0.0
    for required in required_skills:
        verified = candidate_by_name.get(required.lower())
        if verified is True:
            earned += 1.0
        elif verified is False:
            earned += 0.6
        else:
            _, similarity = best_skill_similarity(candidate_names, required)
            if similarity >= SKILL_SIMILARITY_THRESHOLD:
                earned += 0.6 * similarity
    return round(100.0 * earned / len(required_skills), 1)
```

**Output.** A `match_scores` row per pair, storing all five components separately. Recruiters see the breakdown, never a bare percentage.

### 4.2.3 Skill Verification & Assessments

**Input.** A candidate submitting code in the Monaco editor.

**Processing.** Code executes client-side in Pyodide against visible test cases. That gives instant feedback with no server round trip and no untrusted execution on our infrastructure. On submit, `task_grade_submission` runs static analysis and an LLM code review scoring correctness, efficiency and style.

**Output.** A graded submission feeding the `problem_solving` sub-score, which is winsorized and percentile-ranked against the population.

### 4.2.4 AI Interview Agent

**Input.** A candidate starting a session against an interview definition.

**Processing.** A turn loop: generate question, receive answer via the browser's speech recognition API, evaluate the turn, decide whether to follow up or advance. Token budgets are bounded per session, because an unbounded transcript grows the context window on every turn and eventually costs more than the interview is worth.

**Output.** A synthesized report with per-competency scores, the full transcript, and evidence quotes tied to each score.

### 4.2.5 Hackathon Pipeline

**Input.** An organizer creating an event and importing teams from CSV/XLSX.

**Processing.** Teams submit repository and deck. The deck runs through the PPT analyzer's four parallel rubric sub-agents. Judges score against a rubric. `task_finalize_rankings` computes the composite:

```python
_DEFAULT_WEIGHTS = {
    "judge_score_component": 0.40,
    "pitch_score_component": 0.30,
    "repo_quality_component": 0.20,
    "novelty_component": 0.10,
}
```

Organizers can override these per event via `Hackathon.scoring_config`, a JSONB column. Different events weight judging and novelty differently, and hardcoding one distribution would have made the feature unusable for half of them.

**Output.** Ranked leaderboard, each entry carrying its component breakdown and a list of any components renormalized away.

### 4.2.6 Trust & Fraud Detection

Four independent graphs. Certificate verification checks the issuer against a trusted registry and runs visual forensics for tampering. Code plagiarism uses `copydetect` for token-level matching plus public-repo cross-checking. Duplicate profiles combine perceptual photo hashing with MinHash text fingerprinting. AI content uses burstiness and lexical-diversity statistics.

The AI-content detector is explicitly capped in confidence and shipped as a signal, never a verdict. From its own module docstring: AI-generated text tends toward lower burstiness and flatter lexical variety. That is a well-documented but imperfect signal. Presenting a heuristic as proof would be the single most damaging thing this platform could do to a candidate.

Every detector writes a flag at `status='raised'`. Nothing else happens until a human reviews it.

> **Important Note:** Fraud detection is advisory in every case. A flag affects a candidate's authenticity score only after a human reviewer moves it to `upheld` — detection alone carries no penalty.

## 4.3 User Interface, Dashboards & Visualizations

Six route groups, one per role plus public. Access control is visible in the directory structure. `(admin)/` contains only admin pages, and its `layout.tsx` enforces the role.

**Candidates** get a dashboard with a Talent Score radar chart, a GitHub contribution heatmap, repository cards, badges, and an evidence receipt panel that shows exactly which artifacts produced which sub-score. Then career guidance with a roadmap timeline and salary range chart, an ATS resume builder, and assessment and interview surfaces.

**Recruiters** get the copilot search page, per-job match lists with expandable component breakdowns, a drag-and-drop kanban pipeline built on dnd-kit, a top-performers feed fed by hackathon results, and an analytics page with hiring funnel, time-to-hire histogram and source-of-hire breakdown.

**Organizers** create events, import teams by spreadsheet, adjust judge weight sliders, and finalize leaderboards. **Judges** get a queue and a scoring surface. **Admins** get the user directory, role management, audit log viewer, fraud review queue and trusted issuer registry.

**Public** pages need no authentication: server-rendered candidate portfolios at `/[username]` and hackathon leaderboards. Portfolios are opt-in, and `portfolio_published` defaults to false.

Long jobs report through `StageProgress`, driven by the `ingestion_stage` column via `useAsyncResource`, rather than through a generic spinner. A four-minute GitHub crawl is a normal outcome for a large account, not a fault, but nothing about an indeterminate spinner communicates that. The design goal here is not a faster pipeline. It is a wait the user can read.

## 4.4 Real-Time Systems & Integration Layers

### 4.4.1 Background Pipelines

Five pipelines run as FastAPI `BackgroundTasks`: candidate ingestion, job matching, assessment grading, pitch-deck analysis and hackathon ranking finalization. The endpoint records a `processing` status, schedules the pipeline, and returns at once; the pipeline runs in the same API process after the response is sent.

```python
background_tasks.add_task(_run_ingestion_background, profile.id, {}, None)
```

This is a deliberate simplification. An earlier version ran these pipelines on a separate arq/Redis worker, which added a second process to start, a Redis dependency on the critical path, and a class of silent failure: jobs queued with no live worker sat in Redis indefinitely. Running in-process removes all three, so a local setup is just the API, the frontend and the data stores.

The trade-off is stated plainly. Background tasks live in memory, so an API restart drops any pipeline that is mid-flight and its row stays at `processing`; the user re-triggers it (re-upload, reconnect, or "Recompute"). There are no automatic retries, and pipeline work shares the API process's CPU. That is acceptable at demo and pilot scale and is the first thing to revisit before production load.

### 4.4.2 Multi-Provider LLM Gateway

Five providers behind one interface: Anthropic, OpenAI, Groq/xAI, Gemini and any OpenAI-compatible endpoint. Four of them share the OpenAI SDK, so the gateway is far thinner than the provider count suggests.

Model routing is two-tier: a fast model for classification and extraction, and a judgment model for evaluation and synthesis. Defaults are `claude-haiku-4-5-20251001` and `claude-sonnet-4-6`.

The client is an `lru_cache` singleton, which matters more than it looks. Constructing `anthropic.Anthropic(...)` per call builds a fresh httpx client with an empty connection pool, so every LLM call in the application would pay a full TCP and TLS handshake and reuse nothing. Provider SDK clients are thread-safe and designed to be long-lived. `lru_cache` does not cache exceptions, so a call that fails on a missing key re-evaluates cleanly once the key is configured.

### 4.4.3 Vector Search

Qdrant holds candidate profile embeddings, job description embeddings and pitch deck slide embeddings, generated locally by `BAAI/bge-large-en-v1.5`. Local embedding means no per-call cost, no rate limit and no network dependency on the hot path.

Payload indexes matter more than they might appear. Recruiter search is nearly always "semantically similar *and* matching hard filters" such as remote-eligible, minimum experience, or a specific location. Without payload indexes Qdrant filters post-hoc after vector retrieval, which silently returns fewer results than requested when the filter is selective. `scripts/ensure_qdrant_indexes.py` backfills them idempotently.

The embedder is pre-warmed at startup via `asyncio.to_thread`. Calling `get_embedder()` directly in the startup hook would block the event loop for the entire model load — the exact opposite of the intent, and enough to make the first request after boot time out.

### 4.4.4 Outbox Event Consumer

A fixed-interval poller reads the `events` table for unprocessed rows and dispatches them. One example is a recruiter notification fired when a watched candidate places in a hackathon. A plain asyncio loop over an outbox table, rather than another broker dependency, because the volume genuinely doesn't warrant one.

---

# 5. Mathematical Foundations & Quantitative Frameworks

The quantitative core of this platform is scoring under incomplete information. Almost every candidate is missing some signal, whether that is no assessments yet, a thin commit history, or no hackathon record. The naive response of treating absence as zero produces a system that punishes new users and rewards nothing but tenure. Most of the math below exists to avoid that.

## 5.1 Core Mathematical Formulations & Algorithms

### 5.1.1 Weighted Renormalization Under Missing Signals

This is the single most reused formula in the codebase. Five separate modules implement scoring on top of it: Talent Score, Pitch Score, Hackathon Ranking, Job Matching, and the Coding Ability sub-score.

Given terms $(w_i, S_i)$ where $S_i$ may be undefined, let $A = \{i : S_i \neq \varnothing\}$ be the available set. The renormalized score is

$$S = \frac{\sum_{i \in A} w_i S_i}{\sum_{i \in A} w_i}$$

Equivalently, weights are redistributed as $w_i' = w_i / \sum_{j \in A} w_j$, so that $\sum_{i \in A} w_i' = 1$ regardless of how many terms dropped out.

| Symbol | Definition | Domain |
| :--- | :--- | :--- |
| $S$ | Composite score | $[0, 100]$ or undefined |
| $S_i$ | Component score $i$ | $[0, 100] \cup \{\varnothing\}$ |
| $w_i$ | Configured weight of component $i$ | $[0, 1]$, $\sum w_i = 1$ |
| $w_i'$ | Renormalized weight | $[0, 1]$, $\sum_{i \in A} w_i' = 1$ |
| $A$ | Index set of available components | $A \subseteq \{1, \dots, n\}$ |

When $A = \varnothing$ or $\sum_{i \in A} w_i = 0$, the function returns undefined rather than $0$:

```python
def weighted_renormalized_mean(terms: list[tuple[float, float | None]]) -> float | None:
    available = [(w, v) for w, v in terms if v is not None]
    weight_sum = sum(w for w, _ in available)
    if not available or weight_sum == 0:
        return None
    return sum(w * v for w, v in available) / weight_sum
```

The `None` return is a deliberate design constraint, not an oversight. Returning `0.0` would be arithmetically convenient and semantically catastrophic. A candidate with no data would be indistinguishable from a candidate who genuinely scored zero. Callers that want a zero fallback must apply it explicitly at the call site, which forces the decision to be visible.

### 5.1.2 Talent Score Composite

Nine sub-scores, weighted:

$$S_{\text{talent}} = \sum_{i \in A} w_i' \cdot S_i$$

| Sub-score | Weight $w_i$ | Source | LLM involved |
| :--- | ---: | :--- | :--- |
| Coding Ability | 0.16 | GitHub commits, code quality, assessments | Partial |
| Problem Solving | 0.16 | Assessment scores | No |
| Project Quality | 0.12 | Repository analysis | Yes |
| Innovation | 0.12 | Project novelty | Yes |
| Open Source Contributions | 0.10 | External merged PRs | No |
| Hackathon Performance | 0.10 | Platform + self-reported results | No |
| Technical Consistency | 0.08 | Commit cadence variance | No |
| Community Participation | 0.08 | Stars, external contributions | No |
| Leadership | 0.08 | Owned repos, PR reviews | No |

Five of nine sub-scores are computed by deterministic rules with no model call at all. That distribution is intentional: LLM involvement is reserved for judgments that genuinely require reading code or prose, and everything reducible to arithmetic stays arithmetic — cheaper, faster, and reproducible.

### 5.1.3 Evidence Confidence

$$C = \frac{|A|}{n}, \qquad n = 9$$

A candidate scoring 72 with $C = 0.33$ and one scoring 72 with $C = 1.0$ are very different propositions, and a recruiter should be able to tell them apart. The score is never withheld at low confidence. It is labeled.

### 5.1.4 Job Match Score

$$M = w_1 \cdot O_{\text{skill}} + w_2 \cdot \Sigma_{\text{sem}} + w_3 \cdot E_{\text{exp}} + w_4 \cdot T_{\text{align}}$$

with $w_1 = 0.35$, $w_2 = 0.30$, $w_3 = 0.15$, $w_4 = 0.20$, and the same renormalization applied when $E_{\text{exp}}$ or $T_{\text{align}}$ is undefined.

**Skill overlap** applies a verification discount:

$$O_{\text{skill}} = \frac{100}{|R|}\sum_{r \in R} c(r), \qquad
c(r) = \begin{cases}
1.0 & \text{exact match, verified} \\
0.6 & \text{exact match, self-declared} \\
0.6\,\sigma(r) & \sigma(r) \geq \tau_s \text{ (semantic near-match)} \\
0 & \text{otherwise}
\end{cases}$$

where $R$ is the required skill set, $\sigma(r) \in [0,1]$ is the maximum cosine similarity between $r$ and the candidate's skills, and $\tau_s = 0.80$.

**Semantic similarity** blends embedding distance with hard-filter satisfaction:

$$\Sigma_{\text{sem}} = 100\left[\alpha \cdot \text{clamp}_{[0,1]}\!\left(\cos(\vec{v}_C, \vec{v}_J)\right) + (1-\alpha) \cdot F\right], \qquad \alpha = 0.70$$

$$\cos(\vec{v}_C, \vec{v}_J) = \frac{\vec{v}_C \cdot \vec{v}_J}{\|\vec{v}_C\| \, \|\vec{v}_J\|}$$

The clamp matters. A negative cosine is not a meaningful "match quality" signal, so it floors at zero rather than dragging the blend below it. $F \in [0,1]$ is the filter match ratio: $1.0$ if the job is remote or has no location, $0.5$ if the candidate's location is unknown, $1.0$ on an exact location match, and $0$ on a mismatch. An unknown location is a half-credit uncertainty, not a hard fail.

**Experience match** saturates at the stated minimum:

$$E_{\text{exp}} = \begin{cases}
\varnothing & \text{if } y_{\min} \text{ undefined or } y_{\min} \leq 0 \\
0 & \text{if } y_C \text{ undefined} \\
100 \cdot \min\!\left(\dfrac{y_C}{y_{\min}},\, 1\right) & \text{otherwise}
\end{cases}$$

A twenty-year veteran is not a "200% match" for a two-year-minimum role, so exceeding the bar earns full credit and stops there. A job with no stated minimum returns undefined rather than zero. An unconstrained job is not a bad experience match but an inapplicable one, and the aggregation renormalizes around it.

### 5.1.5 Job-Contextual Talent Adjustment

A global talent number doesn't tell a recruiter whether someone is strong *at the role being hired for*. Let $\rho \in [0,1]$ be the candidate's skill overlap ratio against this job. Sub-scores are rescaled by dimension:

$$S_i' = \begin{cases}
\rho \cdot S_i & i \in \{\text{coding\_ability},\ \text{problem\_solving}\} \\
0.8\,\rho \cdot S_i & i \in \{\text{project\_quality},\ \text{innovation}\} \\
S_i & \text{otherwise}
\end{cases}$$

then recomposed with the original weights:

$$T_{\text{align}} = \text{clamp}_{[0,100]}\left(\sum_{i \in A} w_i' S_i'\right), \qquad \phi = \frac{T_{\text{align}}}{S_{\text{talent}}}$$

The adjustment factor $\phi$ is returned alongside the score and stored, so the recruiter sees both the global number and how this particular job moved it. Leadership and community participation are left untouched, because they do not become less real when the job requires different skills.

### 5.1.6 Hackathon Composite Ranking

$$H = w_J \cdot \text{norm}(J) + w_P \cdot P + w_R \cdot Q + w_N \cdot N$$

Defaults are $w_J = 0.40$, $w_P = 0.30$, $w_R = 0.20$, $w_N = 0.10$, overridable per event via the `scoring_config` JSONB column. $\text{norm}(J)$ maps whatever scale the judges used onto $[0, 100]$ before it reaches the formula.

### 5.1.7 Pitch Score

Equal weights across four rubric dimensions:

$$P = \frac{1}{4}\left(I + T + Q_{\text{pres}} + B\right)$$

for innovation, technical feasibility, presentation quality and business potential. Weights renormalize when any dimension is unavailable, which happens whenever the LLM provider is unreachable.

### 5.1.8 Authenticity Score

$$A_{\text{auth}} = \max\left(0,\ 100 - \sum_{k} p_k \cdot \mathbb{1}[\text{status}_k = \text{upheld}]\right)$$

| Flag type | Penalty $p_k$ |
| :--- | ---: |
| Duplicate profile | 40.0 |
| Code plagiarism | 35.0 |
| Fake certificate | 30.0 |
| AI-generated content | 15.0 |
| Unrecognized issuer | 10.0 |
| *(unknown type)* | 10.0 |

The indicator function is the entire point. A flag at `raised`, `under_review` or `dismissed` contributes nothing. Unrecognized issuer carries the lightest penalty because it means the issuer is not in the registry yet, not that a credential was confirmed forged.

## 5.2 Statistical Models & Distributional Methods

The statistical work here is distributional rather than stochastic. Scoring a candidate is a problem of ranking against a population, weighting by recency and trimming outliers — none of which calls for Monte Carlo methods, since the quantities being estimated are observed directly rather than sampled from a generative process.

### 5.2.1 Percentile Normalization

$$\text{pct}(x, \mathcal{P}) = \begin{cases}
f(x) & |\mathcal{P}| < N_{\min} \\
\dfrac{100}{|\mathcal{P}|}\left|\{v \in \mathcal{P} : v \leq x\}\right| & \text{otherwise}
\end{cases}$$

with $N_{\min} = 30$ by default and $f$ a caller-supplied fallback (defaulting to a neutral $50.0$).

The reasoning is anti-gaming. A fixed formula like $100 \cdot \log(1+s)/\log(101)$ is published in the code and trivially farmable: buy stars until you clear the threshold. Percentile rank isn't, because no individual controls what everyone else's numbers look like, and it adapts as the pool grows. Below thirty candidates the ranks swing wildly on each new profile, so the code falls back rather than pretending to a precision it doesn't have.

### 5.2.2 Exponential Recency Decay

$$w(t) = e^{-\lambda t}, \qquad \lambda = \frac{\ln 2}{t_{1/2}}, \qquad t_{1/2} = 180 \text{ days}$$

where $t$ is days elapsed, floored at zero to keep future-dated commits from inflating anything. Six months halves a signal's contribution. Someone who was prolific two years ago and silent since should not score identically to someone shipping now.

### 5.2.3 Winsorization

Values are clipped to their own 5th and 95th percentiles before ranking:

$$\tilde{x}_i = \min\left(\max\left(x_i,\ Q_{0.05}\right),\ Q_{0.95}\right)$$

with interpolated quantiles at fractional index $j = \frac{p}{100}(n-1)$:

$$Q_p = x_{\lfloor j \rfloor}\left(1 - \{j\}\right) + x_{\lceil j \rceil}\{j\}$$

Applied to assessment score populations, where one candidate acing a trivially easy assessment otherwise skews the entire distribution against everyone else.

### 5.2.4 Salary Range Regression

Two gradient-boosted quantile regressors, one for the 25th percentile and one for the 75th, trained offline on the public Stack Overflow Developer Survey with role, location and a years-of-experience proxy as features. Output is always a range, never a point estimate, because a point estimate implies a precision the model does not have.

A Talent Score adjustment is applied post-hoc:

$$\delta = \text{clamp}_{[-0.15,\,0.15]}\!\left(\frac{S_{\text{talent}} - 50}{50}\right), \qquad [\ell, h] = \left[\ell_0(1+\delta),\ h_0(1+\delta)\right]$$

This is disclosed in the output rationale rather than buried, and for a specific reason: the survey has no Talent Score column, because Talent Score is this platform's own derived metric. There is no ground truth to train against. Rather than fabricate a training feature, the base model uses only real survey features and the Talent Score enters as a bounded, explicitly-labeled ±15% adjustment. The generated rationale string states the adjustment percentage outright.

### 5.2.5 AI-Content Heuristic

Burstiness is the coefficient of variation of sentence lengths; lexical diversity is the type-token ratio:

$$B = \frac{\sigma(L)}{\mu(L)}, \qquad D = \frac{|\text{unique words}|}{|\text{words}|}$$

$$\text{AI-likelihood} = 100\left[0.5 \cdot \text{clamp}_{[0,1]}(1 - B) + 0.5 \cdot \text{clamp}_{[0,1]}(1 - 2D)\right]$$

Machine-generated prose tends toward uniform sentence length and flatter vocabulary. It's a documented signal and a weak one. Confidence is capped at `"medium"` no matter how much text is sampled, slides scoring below three sentences return undefined rather than a confident guess, and the rationale string shipped with every result says plainly that false positives are expected — particularly for non-native English writers and templated slide text.

This is deliberately the weakest-weighted and most heavily-caveated component in the platform. Treating a burstiness statistic as proof of misconduct would be indefensible, and the 15.0 penalty (applied only after human review upholds the flag) reflects that.

### 5.2.6 Technical Consistency

Inverted coefficient of variation over recency-weighted weekly commit counts, with a staleness penalty and a sustained-activity bonus:

$$c_i' = c_i \cdot w(t_i), \qquad B_{\text{cv}} = 100 \cdot \frac{1}{1 + \text{CV}}, \qquad \text{CV} = \frac{\sigma_{\text{pop}}(c')}{\mu(c')}$$

$$S_{\text{consistency}} = \text{clamp}_{[0,100]}\Big(B_{\text{cv}} - \underbrace{20\left(1 - w(t_{\text{last}})\right)}_{\text{staleness}} + \underbrace{10 \cdot \frac{\max(0,\ a - 0.75)}{0.25}}_{\text{sustained activity}}\Big)$$

where $a$ is the fraction of the 52-week window containing at least one commit. Fewer than four active weeks returns undefined — cold start, not a penalty. This measures regularity, not volume: steady cadence scores high, and the burst-then-vanish pattern scores low even when total commits are identical.

## 5.3 Analytical Calculators & Indicator Derivations

### 5.3.1 Coding Ability

$$S_{\text{coding}} = \sum_{i \in A} w_i' S_i, \quad w = (0.25\ \text{language},\ 0.35\ \text{quality},\ 0.40\ \text{assessment})$$

Assessments carry the heaviest weight because they're the hardest signal to fake — timed, unseen problems. The language component percentile-normalizes total non-fork commits, falling back below population threshold to

$$f(c) = \min\left(100,\ 100 \cdot \frac{\ln(1+c)}{\ln(201)}\right)$$

Log scaling stops a handful of high-volume repositories from dominating; 200 own commits lands around 80–90.

### 5.3.2 Community Participation

$$S_{\text{community}} = 0.6 \cdot \text{pct}(s, \mathcal{P}_s) + \min(40,\ 8e)$$

for total stars $s$ and external merged PRs $e$. Stars are percentile-ranked; external contributions are capped linearly at five PRs, since the difference between five and fifty external PRs is far less meaningful than the difference between zero and five.

### 5.3.3 Leadership

$$S_{\text{lead}} = \text{pct}\Big(\min(50,\ 10 r_o) + \min(50,\ 5 r_p),\ \mathcal{P}_L\Big)$$

for owned non-fork repos $r_o$ and PR reviews $r_p$. This is the most gameable signal in the system — anyone can create ten empty repositories. Percentile normalization mitigates it; the low 0.08 weight is the rest of the defense. The code comments say as much.

### 5.3.4 Open Source Contributions

$$S_{\text{oss}} = \text{pct}\Big(\underbrace{\min(50,\ 5e)}_{\text{external PRs}} + \underbrace{\min(30,\ 3d)}_{\text{repo breadth}} + \underbrace{\min(20,\ 2.5\ell)}_{\text{language diversity}},\ \mathcal{P}_{\text{oss}}\Big)$$

Three capped components summing to a 100-point raw value, then percentile-ranked. All three caps bind well before the theoretical maximum, which is intended — breadth past a point stops being informative.

### 5.3.5 Hackathon Performance

Tier scores are $\{$winner: 100, top5: 75, finalist: 50, participant: 25$\}$, with platform-verified results at full weight and self-reported entries scaled by a user-supplied importance clamped from a 1–5 scale into $[0.2, 1.0]$:

$$w_{\text{norm}}(x) = 0.2 + \frac{(x-1)(1.0 - 0.2)}{4}$$

Aggregation rewards quality first, breadth second:

$$S_{\text{hack}} = \min\left(100,\ \begin{cases}
\dfrac{1}{n}\sum_{i=1}^{n} v_i & n \leq 5 \\[2ex]
0.7 \cdot \dfrac{1}{5}\sum_{i=1}^{5} v_i + 0.3 \cdot \dfrac{1}{n-5}\sum_{i=6}^{n} v_i & n > 5
\end{cases}\right)$$

with $v$ sorted descending. Best five carry 70%, the remainder 30% — so entering thirty hackathons and placing in none doesn't outrank winning two.

### 5.3.6 Skill Gap Analysis

A required skill for a target role is a gap when it has no literal match *and* its embedding similarity to the candidate's closest skill falls below $\tau_g = 0.72$. Target role selection, when unspecified, uses cosine similarity between the candidate's skill-embedding centroid and each role's embedding:

$$\vec{v}_{\text{centroid}} = \frac{1}{|S|}\sum_{s \in S} \vec{v}_s, \qquad \text{role}^* = \arg\max_{r} \cos(\vec{v}_{\text{centroid}},\ \vec{v}_r)$$

Note the threshold asymmetry: gap detection uses $0.72$ while match scoring uses $0.80$. They answer different questions. Awarding score credit should demand strong evidence of equivalence; telling a candidate they have a learning gap should demand strong evidence they *don't* already cover it. Both err toward the candidate.

## 5.4 Mathematical Formulation Summary Matrix

| Metric | Formula | Range | Undefined when | Implementation |
| :--- | :--- | :--- | :--- | :--- |
| Renormalized mean | $\sum_{i \in A} w_i S_i / \sum_{i \in A} w_i$ | $[0,100]$ | $A = \varnothing$ | `common/scoring.py` |
| Talent Score | $\sum_{i \in A} w_i' S_i$, 9 terms | $[0,100]$ | All sub-scores absent | `ci/tools/aggregate.py` |
| Evidence Confidence | $\lvert A\rvert / 9$ | $[0,1]$ | Never | `ci/tools/aggregate.py` |
| Match Score | $0.35 O + 0.30 \Sigma + 0.15 E + 0.20 T$ | $[0,100]$ | Falls back to $0.0$ | `recruitment/tools/matching.py` |
| Skill Overlap | $\frac{100}{\lvert R\rvert}\sum_r c(r)$ | $[0,100]$ | $R = \varnothing \Rightarrow 0$ | `recruitment/tools/matching.py` |
| Semantic Similarity | $100[\alpha\cos + (1-\alpha)F]$, $\alpha = 0.7$ | $[0,100]$ | Never | `recruitment/tools/matching.py` |
| Experience Match | $100\min(y_C/y_{\min}, 1)$ | $[0,100]$ | $y_{\min}$ absent | `recruitment/tools/matching.py` |
| Talent Alignment | Rescale by $\rho$, recompose | $[0,100]$ | No base score | `recruitment/tools/matching.py` |
| Hackathon Composite | $0.40J + 0.30P + 0.20Q + 0.10N$ | $[0,100]$ | All components absent | `hackathon/tools/ranking.py` |
| Pitch Score | $\frac{1}{4}(I + T + Q + B)$ | $[0,100]$ | All rubrics absent | `ppt_analyzer/tools/aggregate.py` |
| Authenticity | $\max(0, 100 - \sum p_k \mathbb{1}[\text{upheld}])$ | $[0,100]$ | Never | `fraud/tools/aggregation.py` |
| Percentile Rank | $100\lvert\{v \leq x\}\rvert / \lvert\mathcal{P}\rvert$ | $[0,100]$ | $\lvert\mathcal{P}\rvert < 30 \Rightarrow$ fallback | `ci/tools/normalization.py` |
| Recency Weight | $e^{-t\ln 2 / 180}$ | $(0,1]$ | Never | `ci/tools/normalization.py` |
| Winsorization | $\text{clip}(x, Q_{0.05}, Q_{0.95})$ | Input range | Empty input $\Rightarrow$ empty | `ci/tools/normalization.py` |
| Technical Consistency | $\frac{100}{1+\text{CV}} - 20(1-w) + \text{bonus}$ | $[0,100]$ | $< 4$ active weeks | `ci/tools/github.py` |
| Coding Ability | $0.25L + 0.35Q + 0.40A$ | $[0,100]$ | No repos and no assessment | `ci/tools/mechanical_scores.py` |
| Community | $0.6\,\text{pct}(s) + \min(40, 8e)$ | $[0,100]$ | No GitHub activity | `ci/tools/mechanical_scores.py` |
| Leadership | $\text{pct}(\min(50,10r_o) + \min(50,5r_p))$ | $[0,100]$ | No repos, no reviews | `ci/tools/mechanical_scores.py` |
| Open Source | $\text{pct}(\min(50,5e)+\min(30,3d)+\min(20,2.5\ell))$ | $[0,100]$ | No external PRs | `ci/tools/open_source_score.py` |
| Hackathon Perf. | Best-5 at 0.7 + rest at 0.3 | $[0,100]$ | No entries | `ci/tools/hackathon_score.py` |
| Salary Range | GBQR $\times (1+\delta)$, $\lvert\delta\rvert \leq 0.15$ | USD pair | Model artifact absent | `ci/tools/salary_model.py` |
| AI-Content | $100[0.5(1-B) + 0.5(1-2D)]$ | $[0,100]$ | $< 3$ sentences | `ppt/tools/ai_content_heuristic.py` |

---

# 6. Database Schema & Security Infrastructure

## 6.1 Entity-Relationship Overview

Forty-three tables across seven functional domains, created by a single Alembic baseline (`e8c387ea8123`). It was built up over 33 incremental revisions during development and squashed once the schema settled.

```
organizations 1 --> N users
users 1 --> N audit_logs (actor_user_id)
users 1 --> 1 candidate_profiles

candidate_profiles 1 --> N  github_snapshots
                            certifications --> 1 files (file_id)
                            talent_scores
                            badges
                            generated_documents --> 1 files
                            match_scores, applications
                            submissions, interview_sessions
                            team_members
                            fraud_flags, authenticity_scores

jobs 1 --> N match_scores,  jobs 1 --> N applications

hackathons 1 --> N hackathon_teams 1 --> N team_members
hackathon_teams 1 --> 1 hackathon_submissions 1 --> N judge_scores
hackathons 1 --> N hackathon_rankings

assessments 1 --> N submissions
interview_definitions 1 --> N interview_sessions 1 --> N interview_turns

presentations 1 --> N slide_analyses,  1 --> N plagiarism_matches

fraud_flags 1 --> N disputes
trusted_issuers                 standalone registry
agent_runs                      polymorphic: subject_type + subject_id, no FK
events                          outbox, consumed by the polling loop
course_catalog, career_recommendations
```

Three conventions run throughout. Primary keys are UUIDv4 generated application-side, so a client can construct a related object graph before any insert. Enum-like vocabularies are enforced with CHECK constraints rather than Postgres `ENUM` types, because adding a value to a CHECK is a one-line migration while altering an enum type is not. Semi-structured evidence lives in JSONB, covering skills, conflicts, breakdowns and scoring configs, while anything queried or joined stays relational.

`agent_runs` is intentionally polymorphic. It stores `subject_type` plus `subject_id` with no foreign key, because it records executions against candidates, jobs, submissions and presentations alike. An FK per subject type would mean a schema change every time a new agent is added.

## 6.2 Complete SQL Migration Scripts & DDL

The migrations are written in Alembic's Python DSL. What follows is the equivalent executable DDL, in dependency order.

> The 33-revision chain that built this schema incrementally was squashed into a single baseline (`e8c387ea8123`) on 2026-08-16, once the models and the database were confirmed to match exactly. The groupings below are kept because they explain the schema by domain; they no longer correspond to separate migration files. The pre-squash chain is archived under `.archive/pre-squash-migrations/`.

### 6.2.1 Core Shared Tables

```sql
CREATE TABLE organizations (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL,
    domain      TEXT,
    org_type    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_organizations_org_type
        CHECK (org_type IN ('company','university','hackathon_organizer'))
);

CREATE TABLE users (
    id               UUID PRIMARY KEY,
    email            TEXT NOT NULL UNIQUE,
    full_name        TEXT,
    role             TEXT NOT NULL,
    organization_id  UUID REFERENCES organizations(id),
    password_hash    TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active        BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT ck_users_role
        CHECK (role IN ('candidate','recruiter','organizer','judge','admin'))
);

CREATE TABLE files (
    id             UUID PRIMARY KEY,
    owner_user_id  UUID REFERENCES users(id),
    storage_key    TEXT NOT NULL,
    public_url     TEXT,
    file_type      TEXT,
    uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
    id             UUID PRIMARY KEY,
    actor_user_id  UUID REFERENCES users(id),
    action         TEXT NOT NULL,
    target_type    TEXT,
    target_id      UUID,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_runs (
    id                UUID PRIMARY KEY,
    agent_name        TEXT NOT NULL,
    subject_type      TEXT NOT NULL,
    subject_id        UUID NOT NULL,
    input_ref         JSONB,
    output            JSONB,
    model_used        TEXT,
    langfuse_trace_id TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id            UUID PRIMARY KEY,
    event_type    TEXT NOT NULL,
    payload       JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at  TIMESTAMPTZ
);
```

### 6.2.2 Candidate Intelligence

```sql
CREATE TABLE candidate_profiles (
    id                   UUID PRIMARY KEY,
    user_id              UUID NOT NULL UNIQUE REFERENCES users(id),
    github_username      TEXT,
    leetcode_username    TEXT,
    github_stats         JSONB,
    leetcode_stats       JSONB,
    stats_refreshed_at   TIMESTAMPTZ,
    headline             TEXT,
    location             TEXT,
    skills               JSONB,   -- [{name, source, confidence}]
    experience           JSONB,
    education            JSONB,
    merged_conflicts     JSONB,
    hackathon_experience JSONB,   -- [{id, name, result, weight, date, platform_hackathon_id}]
    username             TEXT UNIQUE,
    portfolio_published  BOOLEAN NOT NULL DEFAULT false,
    ingestion_status     TEXT NOT NULL DEFAULT 'idle',
    ingestion_error      TEXT,
    ingestion_stage      TEXT,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE github_snapshots (
    id              UUID PRIMARY KEY,
    candidate_id    UUID NOT NULL REFERENCES candidate_profiles(id),
    repo_full_name  TEXT NOT NULL,
    stars           INTEGER,
    forks           INTEGER,
    commit_count    INTEGER,
    pr_count        INTEGER,
    issue_count     INTEGER,
    languages       JSONB,
    is_fork         BOOLEAN,
    topics          JSONB,
    pushed_at       TIMESTAMPTZ,
    description     TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_github_snapshots_candidate ON github_snapshots (candidate_id);

CREATE TABLE certifications (
    id                   UUID PRIMARY KEY,
    candidate_id         UUID NOT NULL REFERENCES candidate_profiles(id),
    file_id              UUID REFERENCES files(id),
    issuer               TEXT,
    title                TEXT,
    issue_date           TIMESTAMPTZ,
    credential_id        TEXT,
    ocr_confidence       DOUBLE PRECISION,
    verification_status  TEXT NOT NULL DEFAULT 'unverified',
    CONSTRAINT ck_certifications_verification_status
        CHECK (verification_status IN ('unverified','pending','verified','rejected'))
);

CREATE TABLE talent_scores (
    id                           UUID PRIMARY KEY,
    candidate_id                 UUID NOT NULL REFERENCES candidate_profiles(id),
    coding_ability               DOUBLE PRECISION,
    project_quality              DOUBLE PRECISION,
    leadership                   DOUBLE PRECISION,
    problem_solving              DOUBLE PRECISION,
    innovation                   DOUBLE PRECISION,
    community_participation      DOUBLE PRECISION,
    technical_consistency        DOUBLE PRECISION,
    open_source_contributions    DOUBLE PRECISION,
    hackathon_performance        DOUBLE PRECISION,
    overall                      DOUBLE PRECISION,
    renormalized_subscores       JSONB,
    confidence_available_signals INTEGER,
    confidence_expected_signals  INTEGER,
    confidence                   DOUBLE PRECISION,
    score_version                TEXT NOT NULL DEFAULT 'v1',
    computed_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_scores_candidate_time ON talent_scores (candidate_id, computed_at);

CREATE TABLE badges (
    id                     UUID PRIMARY KEY,
    candidate_id           UUID NOT NULL REFERENCES candidate_profiles(id),
    skill_name             TEXT NOT NULL,
    corroboration_sources  JSONB NOT NULL,
    awarded_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_badges_candidate ON badges (candidate_id);

CREATE TABLE generated_documents (
    id                      UUID PRIMARY KEY,
    candidate_id            UUID NOT NULL REFERENCES candidate_profiles(id),
    document_type           TEXT NOT NULL,
    target_job_description  TEXT,
    content                 JSONB NOT NULL,
    file_id                 UUID REFERENCES files(id),
    fact_check_status       TEXT NOT NULL DEFAULT 'pending',
    fact_check_findings     JSONB,
    attempts                INTEGER NOT NULL DEFAULT 0,
    model_used              TEXT,
    generated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_generated_documents_document_type
        CHECK (document_type IN ('resume','cover_letter')),
    CONSTRAINT ck_generated_documents_fact_check_status
        CHECK (fact_check_status IN ('pending','passed','failed'))
);
CREATE INDEX idx_generated_documents_candidate_time
    ON generated_documents (candidate_id, generated_at);

CREATE TABLE course_catalog (
    id               UUID PRIMARY KEY,
    provider         TEXT NOT NULL,
    title            TEXT NOT NULL,
    url              TEXT NOT NULL,
    skill_tags       JSONB NOT NULL,
    level            TEXT,
    estimated_hours  INTEGER,
    is_free          BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_course_catalog_provider
        CHECK (provider IN ('coursera','freecodecamp','vendor')),
    CONSTRAINT ck_course_catalog_level
        CHECK (level IS NULL OR level IN ('beginner','intermediate','advanced'))
);

CREATE TABLE career_recommendations (
    id                   UUID PRIMARY KEY,
    candidate_id         UUID NOT NULL REFERENCES candidate_profiles(id),
    target_role          TEXT,
    skill_gaps           JSONB,
    recommended_courses  JSONB,
    roadmap              JSONB,
    salary_estimate_low  INTEGER,
    salary_estimate_high INTEGER,
    salary_rationale     TEXT,
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_career_recs_candidate_time
    ON career_recommendations (candidate_id, generated_at);
```

### 6.2.3 Recruitment

```sql
CREATE TABLE jobs (
    id                    UUID PRIMARY KEY,
    organization_id       UUID REFERENCES organizations(id),
    posted_by_user_id     UUID NOT NULL REFERENCES users(id),
    title                 TEXT NOT NULL,
    description           TEXT NOT NULL,
    required_skills       JSONB,
    min_experience_years  INTEGER,
    location              TEXT,
    is_remote             BOOLEAN NOT NULL DEFAULT true,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    matching_status       TEXT NOT NULL DEFAULT 'idle',
    matching_error        TEXT
);

CREATE TABLE applications (
    id                UUID PRIMARY KEY,
    job_id            UUID NOT NULL REFERENCES jobs(id),
    candidate_id      UUID NOT NULL REFERENCES candidate_profiles(id),
    stage             TEXT NOT NULL DEFAULT 'sourced',
    source            TEXT,
    applied_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    stage_updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_applications_stage CHECK (stage IN (
        'sourced','screened','interview_scheduled','offered','rejected','hired')),
    CONSTRAINT ck_applications_source CHECK (
        source IS NULL OR source IN ('direct','copilot_search','hackathon')),
    CONSTRAINT uq_applications_job_candidate UNIQUE (job_id, candidate_id)
);
CREATE INDEX idx_applications_job_stage ON applications (job_id, stage);
CREATE INDEX idx_applications_candidate  ON applications (candidate_id);

CREATE TABLE match_scores (
    id                      UUID PRIMARY KEY,
    job_id                  UUID NOT NULL REFERENCES jobs(id),
    candidate_id            UUID NOT NULL REFERENCES candidate_profiles(id),
    match_percentage        DOUBLE PRECISION,
    skill_similarity        DOUBLE PRECISION,
    semantic_similarity     DOUBLE PRECISION,
    experience_match        DOUBLE PRECISION,
    talent_score_alignment  DOUBLE PRECISION,
    project_relevance       DOUBLE PRECISION,
    explanation             TEXT,
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_match_scores_job_candidate UNIQUE (job_id, candidate_id)
);
CREATE INDEX idx_match_scores_job_sort ON match_scores (job_id, match_percentage DESC);
```

The `uq_match_scores_job_candidate` constraint carries operational weight beyond integrity — it lets the matching pipeline use `INSERT ... ON CONFLICT DO UPDATE`, so a recompute overwrites in place instead of accumulating duplicate rows on every rerun.

### 6.2.4 Trust & Fraud

```sql
CREATE TABLE fraud_flags (
    id            UUID PRIMARY KEY,
    candidate_id  UUID NOT NULL REFERENCES candidate_profiles(id),
    flag_type     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'raised',
    severity      TEXT,
    evidence      JSONB,
    detected_by   TEXT,
    reviewed_by   UUID REFERENCES users(id),
    reviewed_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_fraud_flags_type CHECK (flag_type IN (
        'fake_certificate','code_plagiarism','duplicate_profile',
        'ai_generated_content','unrecognized_issuer')),
    CONSTRAINT ck_fraud_flags_status CHECK (status IN (
        'raised','under_review','upheld','dismissed'))
);
CREATE INDEX idx_fraud_flags_candidate_status ON fraud_flags (candidate_id, status);

CREATE TABLE authenticity_scores (
    id            UUID PRIMARY KEY,
    candidate_id  UUID NOT NULL REFERENCES candidate_profiles(id),
    score         DOUBLE PRECISION NOT NULL,
    components    JSONB NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_authenticity_candidate_time
    ON authenticity_scores (candidate_id, computed_at);

CREATE TABLE disputes (
    id             UUID PRIMARY KEY,
    flag_id        UUID NOT NULL REFERENCES fraud_flags(id),
    candidate_id   UUID NOT NULL REFERENCES candidate_profiles(id),
    reason         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open',
    resolution     TEXT,
    submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at    TIMESTAMPTZ,
    CONSTRAINT ck_disputes_status CHECK (status IN ('open','resolved','rejected'))
);

CREATE TABLE trusted_issuers (
    id            UUID PRIMARY KEY,
    name          TEXT NOT NULL,
    domain        TEXT,
    aliases       JSONB,
    trust_level   TEXT NOT NULL DEFAULT 'verified',
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_trusted_issuers_trust_level
        CHECK (trust_level IN ('verified','provisional','revoked'))
);
```

`idx_fraud_flags_candidate_status` is a composite for a reason: the authenticity calculation always queries "flags for this candidate where status = 'upheld'", so the index covers both predicates.

### 6.2.5 Index Summary

| Index | Table | Columns | Query it serves |
| :--- | :--- | :--- | :--- |
| `idx_github_snapshots_candidate` | `github_snapshots` | `candidate_id` | Dashboard, portfolio, recruiter pool build |
| `idx_badges_candidate` | `badges` | `candidate_id` | Badge list, pool build |
| `idx_scores_candidate_time` | `talent_scores` | `candidate_id, computed_at` | Latest score, score history chart |
| `idx_applications_job_stage` | `applications` | `job_id, stage` | Kanban column fetch |
| `idx_applications_candidate` | `applications` | `candidate_id` | Candidate's applications list |
| `idx_match_scores_job_sort` | `match_scores` | `job_id, match_percentage DESC` | Ranked match list, no sort step |
| `idx_generated_documents_candidate_time` | `generated_documents` | `candidate_id, generated_at` | Document history |
| `idx_career_recs_candidate_time` | `career_recommendations` | `candidate_id, generated_at` | Cached guidance lookup |
| `idx_fraud_flags_candidate_status` | `fraud_flags` | `candidate_id, status` | Upheld-flag filter |
| `idx_authenticity_candidate_time` | `authenticity_scores` | `candidate_id, computed_at` | Current authenticity |
| `idx_interview_sessions_candidate` | `interview_sessions` | `candidate_id, started_at` | Interview history |

The descending sort direction on `idx_match_scores_job_sort` is deliberate — recruiters always read matches best-first, and encoding the direction in the index removes the sort node from the plan entirely.

## 6.3 Row-Level Security (RLS) & Access Control Policies

Access control operates at two layers. The application layer is authoritative and enforced today on every request; database-level RLS is the defense-in-depth layer.

### 6.3.1 Application-Layer Enforcement

Every protected endpoint declares its requirement in the signature, so authorization cannot be skipped by an early return in the handler body:

```python
@router.get("/admin/fraud-review-queue", response_model=list[FraudReviewQueueEntry])
async def fraud_review_queue(
    user: User = Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[FraudReviewQueueEntry]:
    ...
```

Role membership alone is insufficient. Ownership is a second, separate check — a recruiter holding a valid recruiter token still cannot read another recruiter's job pipeline, because the query filters on `posted_by_user_id`. Candidate endpoints under `/candidates/me/*` resolve the profile from the token subject and never accept a candidate ID from the client, which removes IDOR as a category rather than patching it per endpoint.

### 6.3.2 Row-Level Security Policies

RLS is applied to the tables holding personal and evaluative data. The application connects as a non-superuser role, and each request sets the session context inside the transaction:

```sql
-- Runtime roles. The application never connects as the table owner, because
-- Postgres exempts owners from RLS unless FORCE is set.
CREATE ROLE overwatch_app     NOLOGIN;
CREATE ROLE overwatch_runtime LOGIN PASSWORD :'app_password' IN ROLE overwatch_app;

ALTER TABLE candidate_profiles     ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_profiles     FORCE  ROW LEVEL SECURITY;
ALTER TABLE talent_scores          ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_snapshots       ENABLE ROW LEVEL SECURITY;
ALTER TABLE certifications         ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_documents    ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications           ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_scores           ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_flags            ENABLE ROW LEVEL SECURITY;
ALTER TABLE authenticity_scores    ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_sessions     ENABLE ROW LEVEL SECURITY;

-- Helper functions reading the per-transaction session context.
CREATE OR REPLACE FUNCTION current_app_user_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION current_app_role() RETURNS TEXT AS $$
    SELECT COALESCE(NULLIF(current_setting('app.current_role', true), ''), 'anonymous');
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION current_candidate_id() RETURNS UUID AS $$
    SELECT id FROM candidate_profiles WHERE user_id = current_app_user_id();
$$ LANGUAGE sql STABLE SECURITY DEFINER;
```

**Candidate profiles.** A candidate reads and writes only their own row. Recruiters read any profile — sourcing requires it. Admins read everything. Published portfolios are world-readable, which is the entire point of publishing one.

```sql
CREATE POLICY candidate_profiles_self ON candidate_profiles
    FOR ALL TO overwatch_app
    USING (user_id = current_app_user_id())
    WITH CHECK (user_id = current_app_user_id());

CREATE POLICY candidate_profiles_recruiter_read ON candidate_profiles
    FOR SELECT TO overwatch_app
    USING (current_app_role() IN ('recruiter','admin'));

CREATE POLICY candidate_profiles_public_portfolio ON candidate_profiles
    FOR SELECT TO overwatch_app
    USING (portfolio_published = true);
```

**Derived candidate data.** Scores, snapshots, certifications and generated documents follow the owning profile. Writes are restricted to the service context, because a candidate must never be able to write their own talent score.

```sql
CREATE POLICY talent_scores_owner_read ON talent_scores
    FOR SELECT TO overwatch_app
    USING (candidate_id = current_candidate_id()
           OR current_app_role() IN ('recruiter','admin'));

CREATE POLICY talent_scores_service_write ON talent_scores
    FOR INSERT TO overwatch_app
    WITH CHECK (current_app_role() = 'service');

CREATE POLICY github_snapshots_owner ON github_snapshots
    FOR SELECT TO overwatch_app
    USING (candidate_id = current_candidate_id()
           OR current_app_role() IN ('recruiter','admin'));

CREATE POLICY generated_documents_owner ON generated_documents
    FOR ALL TO overwatch_app
    USING (candidate_id = current_candidate_id())
    WITH CHECK (candidate_id = current_candidate_id());
```

**Applications and matches.** Visible to the candidate they concern and to the recruiter who owns the job — nobody else.

```sql
CREATE POLICY applications_participant ON applications
    FOR SELECT TO overwatch_app
    USING (
        candidate_id = current_candidate_id()
        OR EXISTS (SELECT 1 FROM jobs j
                   WHERE j.id = applications.job_id
                     AND j.posted_by_user_id = current_app_user_id())
        OR current_app_role() = 'admin'
    );

CREATE POLICY applications_recruiter_stage_update ON applications
    FOR UPDATE TO overwatch_app
    USING (EXISTS (SELECT 1 FROM jobs j
                   WHERE j.id = applications.job_id
                     AND j.posted_by_user_id = current_app_user_id()));

CREATE POLICY match_scores_job_owner ON match_scores
    FOR SELECT TO overwatch_app
    USING (
        EXISTS (SELECT 1 FROM jobs j
                WHERE j.id = match_scores.job_id
                  AND j.posted_by_user_id = current_app_user_id())
        OR current_app_role() = 'admin'
    );
```

**Fraud data.** The strictest policies in the schema. A candidate sees flags raised against them, because being able to dispute a flag you cannot see is meaningless. Only admins review, and no application role may update a flag's status — the review path runs through a dedicated privileged role.

```sql
CREATE POLICY fraud_flags_subject_read ON fraud_flags
    FOR SELECT TO overwatch_app
    USING (candidate_id = current_candidate_id()
           OR current_app_role() = 'admin');

CREATE POLICY fraud_flags_admin_review ON fraud_flags
    FOR UPDATE TO overwatch_app
    USING (current_app_role() = 'admin')
    WITH CHECK (current_app_role() = 'admin');

CREATE POLICY disputes_subject ON disputes
    FOR ALL TO overwatch_app
    USING (candidate_id = current_candidate_id()
           OR current_app_role() = 'admin')
    WITH CHECK (candidate_id = current_candidate_id());
```

**Audit logs are append-only.** No UPDATE or DELETE policy exists on `audit_logs`, so both operations are denied by default — RLS denies anything not explicitly permitted. That is the correct property for an audit trail, and it's enforced by omission rather than by a rule someone could later relax.

```sql
CREATE POLICY audit_logs_admin_read ON audit_logs
    FOR SELECT TO overwatch_app
    USING (current_app_role() = 'admin');

CREATE POLICY audit_logs_append ON audit_logs
    FOR INSERT TO overwatch_app
    WITH CHECK (true);
```

The session context is established per request, inside the transaction, using `set_config(..., true)` so it is transaction-scoped and cannot leak across pooled connections:

```python
async def apply_rls_context(session: AsyncSession, user: User) -> None:
    """Bind the RLS session variables for this transaction.

    The `true` third argument makes both settings local to the transaction, which
    matters under connection pooling: a value set for the session would persist on
    the pooled connection and be inherited by whichever request picked it up next.
    """
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user.id)},
    )
    await session.execute(
        text("SELECT set_config('app.current_role', :role, true)"),
        {"role": user.role},
    )
```

`FORCE ROW LEVEL SECURITY` on `candidate_profiles` is not redundant with `ENABLE`. Postgres exempts a table's owner from RLS under plain `ENABLE`, so if the application ever connected as the owning role, every policy above would be silently bypassed, with no error and no warning. `FORCE` closes that, and the separate `overwatch_runtime` login role means it should never arise in the first place. Belt and braces, because the failure mode here is invisible.

### 6.3.3 Additional Data Protections

Passwords are bcrypt hashes with per-password salts; plaintext is never persisted or logged. Sentry runs with `send_default_pii=False`. Audit logs capture actor, action, target type and target ID for every administrative mutation. The public portfolio is opt-in — `portfolio_published` defaults to `false`, so no candidate is exposed by inaction.

---

# 7. Local Development & Installation Guide

## 7.1 Prerequisites & System Requirements

| Requirement | Minimum | Recommended | Verify with |
| :--- | :--- | :--- | :--- |
| Python | 3.12.0 | 3.12.x | `python --version` |
| Node.js | 20.0.0 | 22 LTS | `node --version` |
| npm | 10.x | 10.x | `npm --version` |
| Docker Engine | 24.x | 27.x | `docker --version` |
| Docker Compose | v2 | v2 | `docker compose version` |
| Git | 2.40+ | latest | `git --version` |
| RAM | 8 GB | 16 GB | — |
| Disk | 10 GB free | 20 GB free | — |

The RAM figure is not padding. The `BAAI/bge-large-en-v1.5` embedder is roughly 1.3 GB resident, and it is loaded in the API process. Running the API, three containers and a Next.js dev server on 8 GB is workable but tight.

Two optional tools: Tesseract OCR (certificate and slide-image text extraction — without it those paths return a typed error rather than crashing), and headless LibreOffice (legacy `.ppt` conversion; `.pptx` uploads work regardless).

## 7.2 Step-by-Step Setup & Configuration

### Step 1 — Clone

```bash
git clone <repository-url> TRACE
cd TRACE
```

### Step 2 — Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps
```

Wait until Postgres and Redis report `healthy`. Both have healthchecks defined; running migrations against a Postgres still starting up produces a connection error that looks alarming and means nothing.

### Step 3 — Python environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install the runtime dependencies:

```bash
pip install \
  fastapi==0.140.13 uvicorn==0.51.0 \
  sqlalchemy==2.0.51 asyncpg==0.31.0 alembic==1.18.5 \
  pydantic==2.13.4 pydantic-settings==2.14.2 \
  python-jose==3.5.0 bcrypt==5.0.0 python-multipart==0.0.32 \
  email-validator==2.3.0 python-dotenv==1.2.2 \
  redis==5.3.1 \
  langgraph==1.2.9 langchain-core==1.5.2 \
  anthropic==0.120.2 openai==2.50.0 \
  qdrant-client==1.18.0 sentence-transformers==5.6.1 torch==2.13.0 \
  PyGithub==2.9.1 httpx==0.28.1 cloudinary==1.45.0 \
  pymupdf==1.28.0 python-docx==1.2.0 python-pptx==1.0.2 \
  pytesseract==0.3.13 pillow==12.3.0 ImageHash==4.3.2 \
  datasketch==2.0.0 copydetect==0.5.0 \
  scikit-learn==1.9.0 numpy==2.5.1 joblib==1.5.3 \
  jinja2==3.1.6 sentry-sdk==2.66.1 langfuse==4.14.1
```

`torch` is a large download, roughly 2.5 GB on the default CUDA-enabled wheel. On a machine without a GPU, install the CPU-only build first with `pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu`, which is around 200 MB. Inference on the embedder is fast enough on CPU that the GPU build buys nothing for local development.

For development tooling:

```bash
pip install pytest==9.1.1 pytest-asyncio ruff
```

### Step 4 — Environment file

```bash
cp .env.example .env
```

The defaults already point at the local containers. Set `JWT_SECRET_KEY` to a random value:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Everything else can stay as shipped for a first run. Without an LLM key, agents degrade to deterministic rules rather than failing.

### Step 5 — Schema and seed data

```bash
python -m alembic upgrade head
python scripts/seed_db.py
python scripts/seed_candidates_hardcoded.py    # optional but recommended
```

> **Tip:** Run the second seed script. Percentile normalization needs a 30-candidate population before it engages, and below that threshold the scoring silently takes a different code path than it does in production.

The second seed script matters more than it looks. Percentile normalization needs at least 30 candidates before it engages — below that, sub-scores silently use fixed-constant fallbacks and the scoring behaves differently than in production. If you want to see the real path, seed the larger set.

Seeded logins run `alice@example.com` through `evan@example.com`, password `password123`, covering all five roles.

### Step 6 — Qdrant collections

```bash
python scripts/ensure_qdrant_indexes.py
```

Idempotent — safe to re-run. Creates collections and their payload indexes. Skipping this leaves filtered vector searches silently returning fewer results than requested, which is a confusing bug to chase.

### Step 7 — Frontend

```bash
cd apps/web
npm install
```

## 7.3 Environment Variables Reference

| Variable | Required | Default | How to obtain |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://dev:dev@localhost:5432/talent_platform` | Matches the compose file; change only for managed Postgres |
| `DATABASE_SSL_REQUIRED` | No | `false` | `true` for managed/TLS endpoints |
| `DB_POOL_SIZE` | No | `20` | Raise only in response to observed `QueuePool` timeouts |
| `DB_MAX_OVERFLOW` | No | `20` | Burst capacity above pool size |
| `DB_POOL_TIMEOUT_SECONDS` | No | `30` | Wait before a checkout fails |
| `DB_POOL_RECYCLE_SECONDS` | No | `1800` | Pre-empts server-side idle disconnects |
| `JWT_SECRET_KEY` | **Yes** | — | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | No | `HS256` | Leave as-is unless moving to asymmetric keys |
| `JWT_EXPIRY_SECONDS` | No | `604800` | Seven days |
| `REDIS_URL` | No | `redis://localhost:6379` | Rate-limit counters only; unreachable ⇒ per-process fallback |
| `LLM_PROVIDER` | No | `anthropic` | `anthropic` / `openai` / `grok` / `gemini` / `openai_compatible` |
| `ANTHROPIC_API_KEY` | Conditional | `""` | console.anthropic.com → API Keys |
| `OPENAI_API_KEY` | Conditional | `""` | platform.openai.com → API Keys |
| `GROK_API_KEY` | Conditional | `""` | console.groq.com or console.x.ai |
| `GEMINI_API_KEY` | Conditional | `""` | aistudio.google.com → Get API Key |
| `LLM_BASE_URL` | Conditional | `""` | Required only for `openai_compatible` |
| `LLM_MODEL_FAST` | No | `claude-haiku-4-5-20251001` | Classification and extraction |
| `LLM_MODEL_JUDGMENT` | No | `claude-sonnet-4-6` | Evaluation and synthesis |
| `QDRANT_URL` | No | `http://localhost:6333` | Matches the compose file |
| `QDRANT_API_KEY` | No | `""` | Blank for the local container; only needed for a hosted cluster |
| `EMBEDDING_MODEL` | No | `BAAI/bge-large-en-v1.5` | Auto-downloaded from HuggingFace |
| `GITHUB_CLIENT_ID` | No | `""` | github.com/settings/developers → New OAuth App |
| `GITHUB_CLIENT_SECRET` | No | `""` | Same OAuth App |
| `GITHUB_OAUTH_REDIRECT_URI` | No | `""` | `http://localhost:3000/api/auth/github/callback` |
| `CLOUDINARY_URL` | No | `""` | cloudinary.com → Dashboard. Absent ⇒ uploads return 503 |
| `SALARY_MODEL_PATH` | No | `data/models/salary_regressor.joblib` | Produced by `train_salary_model.py` |
| `PRESENTATION_MAX_FILE_SIZE_MB` | No | `50` | Enforced before streaming to storage |
| `LIBREOFFICE_BINARY` | No | `soffice` | Only for legacy `.ppt` |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost:3000` | Comma-separated |
| `FRONTEND_URL` | No | `http://localhost:3000` | Used in OAuth redirects |
| `BACKEND_URL` | No | `http://localhost:8000` | Used in callback construction |
| `NEXT_PUBLIC_API_URL` | Yes (web) | `http://localhost:8000` | Set in `apps/web/.env.local` |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | Per user or IP |
| `ENVIRONMENT` | No | `development` | Tags Langfuse traces |
| `SENTRY_DSN` | No | `""` | sentry.io → Project Settings → Client Keys |
| `LANGFUSE_PUBLIC_KEY` | No | `""` | cloud.langfuse.com → Project Settings |
| `LANGFUSE_SECRET_KEY` | No | `""` | Same |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Change for self-hosted |

> **Important Note:** `JWT_SECRET_KEY` is the only variable in this table with no default and no fallback. The application will not start without it.

`JWT_SECRET_KEY` has no default. That is deliberate. `pydantic-settings` refuses to construct `Settings` without it and the application fails at import rather than at first login. A framework-supplied default signing key is one of the more common ways applications ship insecure, so the failure is loud and immediate by design.

## 7.4 Running the Local Development Suite

Three processes. Separate terminals, or the PowerShell helper below.

**Terminal 1 — infrastructure** (once):

```bash
docker compose -f infra/docker-compose.yml up -d
```

**Terminal 2 — API:**

```bash
uvicorn services.api.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`, health at `http://localhost:8000/health`. Background pipelines run inside this process; there is no separate worker to start.

**Terminal 3 — frontend:**

```bash
cd apps/web
npm run dev
```

On `http://localhost:3000`. The dev script pins `--webpack` rather than Turbopack, because bundler support for Pyodide's WASM assets is uneven and Turbopack's resolution of them is unreliable. The build-time difference doesn't justify fighting it.

On Windows, `scripts/dev-up.ps1` starts containers, applies migrations and launches both servers in one shot.

### Verification

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"password123"}'
# {"access_token":"eyJ...","token_type":"bearer"}

TOKEN="<paste the access_token>"
curl http://localhost:8000/candidates/me -H "Authorization: Bearer $TOKEN"
```

If all three respond, the stack is up.

---

# 8. Verification, Testing & Quality Assurance

## 8.1 Static Type Analysis & Code Audits

### 8.1.1 Frontend

```bash
cd apps/web
npx tsc --noEmit          # TypeScript strict mode
npm run lint              # ESLint 9 flat config via eslint-config-next
npm run build             # Full production build
```

The type check is meaningful here because API response types in `lib/api.ts` mirror the Pydantic schemas in `packages/shared_schemas/`. When a backend field is renamed and the frontend type isn't updated, `tsc` catches it at build rather than leaving a runtime `undefined` to surface in production. On a codebase where the API contract spans two languages, that drift is the most likely source of breakage, and the type check is the cheapest place to catch it.

Our rule is a zero-warning baseline rather than a tolerated backlog. Under time pressure the usual accumulation is unused imports left by refactors and `any` escapes in the API client — individually harmless, collectively fatal, because once the list is long enough nobody reads it and a genuinely new warning disappears into the noise.

### 8.1.2 Backend

```bash
python -c "import services.api.main; import packages.prompts"    # import graph check
python -m alembic upgrade head --sql > /dev/null                 # migration chain validity
ruff check services packages scripts                             # lint
```

The import check is cruder than it looks but catches a specific recurring failure: circular imports between agent tools and API core modules. `services/agents/candidate_intelligence/tools/salary_model.py` imports from `services.api.core.config`, and reversing a dependency somewhere in that chain breaks the whole app at startup. Importing both entry points verifies the graph resolves.

`--sql` renders the entire migration chain to SQL without executing it. If a revision references a missing `down_revision` or a malformed operation, that surfaces before the migration touches a real database.

### 8.1.3 Unit Tests

```bash
pytest services/agents/candidate_intelligence/tests/ -v
pytest services/agents/tests/ -v
```

Tests are concentrated where the risk is: the pure scoring functions. They're deterministic, have no I/O, and produce numbers that directly affect people's job prospects — the highest-value place to spend test effort in this codebase.

```python
def test_percentile_normalize_below_min_population_uses_fallback():
    result = percentile_normalize(50.0, [1.0, 2.0, 3.0], min_population=30,
                                  fallback_fn=lambda v: v * 2)
    assert result == 100.0


def test_percentile_normalize_ranks_against_population():
    population = list(range(1, 101))  # 1..100
    result = percentile_normalize(50.0, [float(v) for v in population], min_population=30)
    assert result == 50.0  # exactly 50 values <= 50 out of 100


def test_recency_weight_halves_at_half_life():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    past = now - timedelta(days=180)
    weight = recency_weight(past, as_of=now, half_life_days=180.0)
```

Coverage spans four files: `test_normalization.py` (percentile ranks, decay, winsorization), `test_aggregate.py` (renormalization and confidence), `test_mechanical_scores.py` (sub-scores including cold start), and `test_github_consistency.py` (the CV-based consistency score). Plus `test_prompts_loader.py`, which guards the failure mode described at R-05 in §10.5.

### 8.1.4 End-to-End

```bash
cd apps/web
npx playwright install chromium
npm run e2e
npm run e2e:report
```

Configured against Chromium with `fullyParallel: false` — these tests share seeded database state and running them concurrently produces interference that looks like flakiness but isn't. Traces and screenshots are retained on failure only.

`webServer` is deliberately not configured in `playwright.config.ts`. Both the Next.js dev server and the FastAPI backend must be running, started explicitly, so that a failed run points at a test failure rather than a startup race.

## 8.2 Algorithm & Simulation Validation

Beyond unit tests, four validation approaches apply to the scoring logic.

**Boundary verification.** Every score function is checked at its extremes. A percentile rank of the population maximum must be exactly 100.0; at the minimum, exactly $100/|\mathcal{P}|$. Recency weight at zero days elapsed must be exactly 1.0, and at one half-life exactly 0.5. These are asserted rather than assumed, because an off-by-one in the comparison operator — `<=` versus `<` — shifts every score in the system by one population slot.

**Cold-start invariants.** For any subset of available sub-scores, the renormalized weights must sum to 1.0 and the composite must stay within $[0, 100]$. This is what makes it safe for a candidate with two of nine signals to be scored at all.

**Manual cross-checks against known profiles.** Sub-scores are spot-checked by hand against real GitHub accounts with known characteristics. This is the only method that catches ordering errors, where the code matches its specification but the specification is wrong — an unweighted coefficient of variation over a 52-week window, for instance, ranks four years of dense history *below* three months of activity, because it reads the longer history's natural variation as inconsistency. Recency weighting and the sustained-activity bonus correct that ordering.

**Degradation testing.** Each external dependency is removed in turn — LLM key unset, Qdrant stopped, Redis stopped, salary artifact deleted — and the system is checked for a clean typed error rather than a crash or, worse, a fabricated number. This is where the `None`-versus-`0.0` discipline pays off; a bug in that path is invisible without deliberately testing for it.

There is no statistical validation of the scoring weights against hiring outcomes, and the code says so directly. The weights are labeled "tunable default, not a validated constant" in `matching.py`. Validating them would require longitudinal outcome data — who was hired, who succeeded — accumulated over far longer than the platform has been running. Presenting them as empirically derived would be a fabrication. They are defensible starting points chosen from domain reasoning, logged where they were chosen, and built to be reconfigured. That is why hackathon weights are already a per-event JSONB column rather than a constant.

## 8.3 Operational Guardrails & Edge-Case Handling

### 8.3.1 Failure Isolation

| Dependency | Failure behavior | Impact |
| :--- | :--- | :--- |
| PostgreSQL | Request fails with 500 | Total — the one hard dependency |
| Redis | Rate limiter falls back to bounded in-memory counters | Degraded: per-process limits |
| Qdrant | `QdrantUnavailable` raised | Semantic search and skill gap unavailable; exact matching still works |
| LLM provider (generic) | `LLMUnavailable` → HTTP 503 `LLM_UNAVAILABLE`, `retryable: true` | AI features unavailable; mechanical scores unaffected |
| LLM quota exhausted | `LLMQuotaExhausted` → HTTP 402 `LLM_QUOTA_EXHAUSTED`, `retryable: false` | Client does **not** retry — waiting cannot fix a billing failure; message names the admin action |
| LLM rate limited | `LLMRateLimited` → HTTP 429, `retryable: true` | Retried with backoff honouring `Retry-After` |
| LLM not configured | `LLMNotConfigured` → HTTP 503 `LLM_NOT_CONFIGURED`, `retryable: false` | Missing API key; not retried |
| LLM timeout | `LLMTimeout` → HTTP 504, `retryable: true` | Bounded by `LLM_TIMEOUT_SECONDS` |
| LLM malformed output | `LLMInvalidOutput` → HTTP 503, `retryable: true` | Schema validation failed; retried once |
| Cloudinary | `StorageUnavailable` → 503 | Uploads and PDF export unavailable |
| GitHub API | Retried if transient | Ingestion retries, then records the error |
| Tesseract | Typed error | Certificate OCR unavailable |
| LibreOffice | `LegacyPptConversionUnavailable` → 422 | `.ppt` rejected with a clear message; `.pptx` unaffected |
| Salary artifact | `SalaryModelUnavailable` | Salary range omitted from guidance; rest of guidance intact |

The pattern is uniform: a typed exception naming the missing dependency, surfaced as a specific HTTP status with a machine-readable code. Never a generic 500, and never a made-up value standing in for a real one.

### 8.3.2 Retry Classification

Retries fire only on failures that another attempt might actually fix:

```python
_TRANSIENT_ERROR_MARKERS = (
    "timeout", "timed out", "connection", "connectionerror",
    "temporarily unavailable", "service unavailable",
    "rate limit", "too many requests", "429",
    "500 server error", "502", "503", "504",
    "bad gateway", "reset by peer", "unavailable",
)


def _is_transient(error_text: str | None) -> bool:
    if not error_text:
        return False
    lowered = error_text.lower()
    return any(marker in lowered for marker in _TRANSIENT_ERROR_MARKERS)
```

The list is deliberately conservative — anything unrecognized is treated as permanent. Retrying a deterministic bug three times just burns the retry budget and delays the failure. Backoff doubles from a 5-second base: 5s, 10s, 20s.

### 8.3.3 Concurrency Guardrails

`UNIQUE (job_id, candidate_id)` on `match_scores`, with matching updating existing rows in place, means re-running matching overwrites rather than duplicating. `db.without_db_connection()` releases the pooled connection across LLM calls — without it, twenty concurrent interviews exhaust the pool and block every unrelated request.

### 8.3.4 Input Validation

Uploads are size-capped before streaming to storage (`PRESENTATION_MAX_FILE_SIZE_MB`, default 50). Candidate code executes in the browser's WebAssembly sandbox, never server-side. Interview sessions carry a token budget so a long transcript can't grow context unboundedly. Rate limiting caps per user or IP. All request bodies are Pydantic-validated, so malformed input produces a 422 with field-level detail rather than reaching handler code.

### 8.3.5 Scoring Guardrails

Missing signals renormalize instead of zero-filling. Every score is clamped to $[0, 100]$ after computation. Percentile ranks fall back below a 30-candidate population. Assessment populations are winsorized before ranking. Fraud flags require human review before affecting anything. Every score persists its component breakdown. The AI-content detector caps confidence at `"medium"` regardless of sample size.

### 8.3.6 Frontend Resilience

`useAsyncResource` implements polling with timeout and retry. Progress is driven by the real `ingestion_stage` column, not a timer. Error boundaries exist at `app/error.tsx` and per-section via `SectionError`. Skeleton components render during load rather than layout-shifting on arrival.

---

# 9. Multi-Platform Deployment & DevOps Pipeline

> **Scope note.** This section is a deployment *design*, not a description of files in the
> repository. The configs shown below — `apps/web/vercel.json`,
> `infra/docker-compose.prod.yml`, `infra/nginx.conf`, `apps/web/next.config.mobile.ts`,
> `apps/web/capacitor.config.ts`, and the Android manifest — are proposed content, not
> committed files. What *is* committed today is `infra/docker-compose.yml` (local
> development only). Treat the following as the intended production topology and a
> ready-to-use starting point, not as a description of current state.

Three deployment targets. The frontend is a Next.js app deployable to any Node host; the backend is containerized; the mobile target wraps the web build with Capacitor.

## 9.1 Static Web Deployment (Vercel / Netlify)

The Next.js app uses Server Components and route handlers, so it needs a Node runtime — this is not a static export. Vercel is the path of least resistance.

**`apps/web/vercel.json`:**

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "framework": "nextjs",
  "regions": ["bom1"],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=63072000; includeSubDomains; preload"
        }
      ]
    },
    {
      "source": "/(.*)\\.wasm",
      "headers": [
        { "key": "Cross-Origin-Embedder-Policy", "value": "require-corp" },
        { "key": "Cross-Origin-Opener-Policy", "value": "same-origin" },
        { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
      ]
    }
  ]
}
```

Deploy:

```bash
npm i -g vercel
cd apps/web
vercel login
vercel link
vercel env add NEXT_PUBLIC_API_URL production    # https://api.<your-domain>
vercel --prod
```

> **Important Note:** The COEP and COOP headers above are required, not optional hardening. Omitting them breaks the Pyodide assessment sandbox in production while leaving it working locally.

The COEP/COOP headers on `.wasm` are load-bearing, not boilerplate. Pyodide needs cross-origin isolation to use `SharedArrayBuffer`. Without those two headers the assessment sandbox fails at runtime with an opaque error, and it fails only in production. Locally it works fine, because `localhost` is treated as a secure context. This is the kind of thing that gets discovered during a demo.

The region is set to `bom1` (Mumbai) to sit near the backend. Cross-region latency between frontend and API undoes the work described in §2.4.

For Netlify, `netlify.toml` at `apps/web/`:

```toml
[build]
  command = "npm run build"
  publish  = ".next"

[[plugins]]
  package = "@netlify/plugin-nextjs"

[[headers]]
  for = "/*.wasm"
  [headers.values]
    Cross-Origin-Embedder-Policy = "require-corp"
    Cross-Origin-Opener-Policy   = "same-origin"
    Cache-Control                = "public, max-age=31536000, immutable"
```

## 9.2 Containerized Deployment (Docker / Nginx)

One image serves both the API and the one-shot `migrate` service — same dependencies, same code, different entrypoint — so the schema the migration applies is always the one the API expects.

**`Dockerfile`** (repository root):

```dockerfile
# ---- Stage 1: dependencies ----
FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        tesseract-ocr \
        libreoffice-impress \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# CPU-only torch: the CUDA wheel is ~2.5GB and buys nothing on a CPU host.
RUN pip install --no-cache-dir torch==2.13.0 \
        --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/.cache/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        tesseract-ocr \
        libreoffice-impress \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

WORKDIR /app
COPY services/ ./services/
COPY packages/ ./packages/
COPY scripts/  ./scripts/
COPY alembic.ini .

# Non-root. The cache dir must be writable — the embedder downloads its weights there
# on first use, and a read-only HOME makes that fail with a confusing permissions error.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /app/.cache/huggingface \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

The 90-second `start-period` accounts for embedder pre-warming at startup. A shorter grace period marks the container unhealthy during normal boot and sends the orchestrator into a restart loop.

**`infra/docker-compose.prod.yml`:**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: talent_platform
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d talent_platform"]
      interval: 10s
      timeout: 5s
      retries: 10

  qdrant:
    image: qdrant/qdrant
    volumes:
      - qdrantdata:/qdrant/storage
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  migrate:
    build: .
    command: ["python", "-m", "alembic", "upgrade", "head"]
    env_file: .env.production
    depends_on:
      postgres:
        condition: service_healthy
    restart: "no"

  api:
    build: .
    env_file: .env.production
    ports:
      - "8000:8000"
    depends_on:
      postgres:  { condition: service_healthy }
      redis:     { condition: service_healthy }
      migrate:   { condition: service_completed_successfully }
    volumes:
      - hfcache:/app/.cache/huggingface
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G

  nginx:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  pgdata:
  qdrantdata:
  redisdata:
  hfcache:
```

The `migrate` service runs once and exits; `api` gates on `service_completed_successfully`, so it never starts against an un-migrated schema. The `hfcache` volume means the ~1.3 GB embedder downloads once and survives container rebuilds.

**`infra/nginx.conf`:**

```nginx
worker_processes auto;

events {
    worker_connections 2048;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;

    gzip on;
    gzip_types application/json application/javascript text/css text/plain;
    gzip_min_length 1024;

    client_max_body_size 50M;   # matches PRESENTATION_MAX_FILE_SIZE_MB

    upstream api_backend {
        server api:8000;
        keepalive 32;
    }

    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=120r/m;

    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        http2 on;
        server_name api.trace-platform.local;

        ssl_certificate     /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;

        location /health {
            proxy_pass http://api_backend;
            access_log off;
        }

        location / {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass         http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_set_header   Connection        "";

            # Long AI pipelines invoked synchronously (copilot, interview turns) can
            # legitimately exceed the 60s default. A gateway timeout mid-interview
            # loses the candidate's session, so this is generous on purpose.
            proxy_connect_timeout 10s;
            proxy_send_timeout    300s;
            proxy_read_timeout    300s;
        }
    }
}
```

Nginx rate limiting is set to 120 r/m against the application's 60 — the outer layer is a crude DoS guard, and the application limiter, which knows about authenticated identity, does the precise work. Setting them equal would let Nginx reject requests the application would have allowed for a legitimate authenticated user.

Deploy:

```bash
docker compose -f infra/docker-compose.prod.yml build
docker compose -f infra/docker-compose.prod.yml up -d
docker compose -f infra/docker-compose.prod.yml logs -f api
docker compose -f infra/docker-compose.prod.yml exec api python scripts/ensure_qdrant_indexes.py
```

**GitHub Actions** — `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: dev
          POSTGRES_PASSWORD: dev
          POSTGRES_DB: talent_platform
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    env:
      DATABASE_URL: postgresql+asyncpg://dev:dev@localhost:5432/talent_platform
      REDIS_URL: redis://localhost:6379
      JWT_SECRET_KEY: ci-only-not-a-real-secret
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
      - run: pip install -r requirements.txt
      - run: ruff check services packages scripts
      - run: python -m alembic upgrade head
      - run: pytest services/agents -v

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npm run lint
      - run: npm run build
```

## 9.3 Native Mobile Compilation (Android / Capacitor)

The mobile target wraps the existing web build rather than reimplementing the UI. For a platform whose interactions are forms, dashboards and text, a native rewrite would triple the surface area for no meaningful gain.

One structural change is required: Capacitor ships a static bundle, so the mobile build cannot use Server Components or route handlers. `next.config.ts` switches to static export under a build flag, and the mobile app talks to the deployed API over HTTPS for everything.

**`apps/web/next.config.mobile.ts`:**

```typescript
import type { NextConfig } from "next";

// Static export for the Capacitor shell. Server Components and route handlers are
// unavailable in this mode — the (public) SSR portfolio route is excluded from the
// mobile build and remains web-only.
const nextConfig: NextConfig = {
  output: "export",
  distDir: ".next-mobile",
  images: { unoptimized: true },
  trailingSlash: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.MOBILE_API_URL ?? "https://api.trace-platform.app",
  },
};

export default nextConfig;
```

**`apps/web/capacitor.config.ts`:**

```typescript
import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "app.trace-platform.mobile",
  appName: "TRACE",
  webDir: ".next-mobile",
  android: {
    allowMixedContent: false,
  },
  server: {
    androidScheme: "https",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: "#0B0B0F",
      showSpinner: false,
    },
  },
};

export default config;
```

Build:

```bash
cd apps/web

npm install --save-dev @capacitor/cli
npm install @capacitor/core @capacitor/android \
            @capacitor/splash-screen @capacitor/preferences

MOBILE_API_URL=https://api.trace-platform.app \
  npx next build --config next.config.mobile.ts

npx cap add android
npx cap sync android
npx cap open android          # opens Android Studio

# Or build the APK directly:
cd android
./gradlew assembleDebug       # app/build/outputs/apk/debug/app-debug.apk
./gradlew assembleRelease     # requires signing config
```

**`apps/web/android/app/src/main/AndroidManifest.xml`** — the permissions that matter:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- API calls -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <!-- AI interview speech capture. Requested at runtime, and only after the
         the candidate owns this interview session server-side. -->
    <uses-permission android:name="android.permission.RECORD_AUDIO" />

    <application
        android:allowBackup="false"
        android:usesCleartextTraffic="false"
        android:theme="@style/AppTheme">
        <activity
            android:name=".MainActivity"
            android:configChanges="orientation|keyboardHidden|screenSize"
            android:exported="true"
            android:launchMode="singleTask">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

`allowBackup="false"` keeps JWTs out of Android's automatic cloud backup. `usesCleartextTraffic="false"` blocks accidental plaintext HTTP — which also means a locally-running dev API at `http://10.0.2.2:8000` won't connect from the emulator without an explicit debug network-security config.

Token storage uses `@capacitor/preferences`, backed by the platform keystore, rather than `localStorage`:

```typescript
import { Preferences } from "@capacitor/preferences";

const TOKEN_KEY = "trace-platform.auth.token";

export async function storeToken(token: string): Promise<void> {
  await Preferences.set({ key: TOKEN_KEY, value: token });
}

export async function readToken(): Promise<string | null> {
  const { value } = await Preferences.get({ key: TOKEN_KEY });
  return value;
}

export async function clearToken(): Promise<void> {
  await Preferences.remove({ key: TOKEN_KEY });
}
```

Two features are web-only and stay that way. The Pyodide code sandbox needs `SharedArrayBuffer` under cross-origin isolation, which the Android WebView does not reliably provide, so candidates take coding assessments on desktop. The SSR public portfolio at `/[username]` requires a server runtime that a static export doesn't have. Both are surfaced in the mobile UI as "open on web" rather than shipped broken.

---

# 10. Project Changelog, Roadmap & License

## 10.1 Build Phases & Version Control Conventions

The system is built in five phases, each gated on the one before it. This section records that phase structure and the version-control discipline that governs the repository.

### Build Phases

**Phase 1 — Foundation.** Monorepo scaffolding, the SQLAlchemy model layer, and the first migration establishing the shared core: users, organizations, files, audit logs, agent runs and events. Every later migration descends from this root in a single linear chain, which keeps `alembic upgrade head` deterministic and avoids the merge-conflict pain of branched revision graphs. Auth lands here too, because nothing else can be tested behind a role gate until it exists.

**Phase 2 — Scoring core.** The pure functions in `tools/` before any of the graphs that call them. This ordering is deliberate: the scoring math is the part of the system that most needs to be correct, it has no I/O, and it can be unit-tested to completion long before there is a database with real candidates in it. Percentile normalization, recency weighting, winsorization and the renormalized mean all get written and tested here.

**Phase 3 — Agent pipelines.** The LangGraph subgraphs, module by module — candidate intelligence first, since the Talent Score is the input to almost everything downstream, then recruitment matching, then assessment, hackathon, PPT analysis and fraud. Each module is a vertical slice: model, migration, agent graph, router, and the frontend surface that consumes it.

**Phase 4 — Interface.** The five role route groups, built against real endpoints rather than mocks wherever possible. Mock data has a way of surviving into production; an empty state is the safer failure.

**Phase 5 — Hardening.** Explicitly scheduled rather than left to whatever time remains. Background pipelines, connection pooling, indexes, rate limiting and the degradation paths described throughout this document are all Phase 5 work. Treating hardening as a phase with its own budget is what stops it from becoming the thing that gets cut.

### Version Control Conventions

Work happens on `dev` and merges to `main` only when the branch is green — type check, lint, migrations and tests all passing. Commit messages state what changed and why in the imperative, and a commit that fixes a non-obvious bug records the root cause in the body, because six weeks later the diff alone rarely explains itself.

Migrations are never edited after being merged. A mistake in a merged revision is corrected by a new revision, since anyone who has already run the original will otherwise have a schema that silently disagrees with the migration history.

Decisions that a future reader would reasonably question — a chosen weight, a rejected library, a deliberate scope reduction — get logged with their reasoning rather than living only in someone's memory.

## 10.2 Future Roadmap & Milestone Objectives

### Near-term (next 4–6 weeks)

**Validate the weights.** Every scoring weight is currently a reasoned default, and the code labels them as such. With outcome data — which matched candidates advanced, which were hired, which succeeded — the weights become a supervised learning problem instead of a judgment call. The schema already supports it: `match_scores` stores all five components, and `applications` tracks stage progression with timestamps.

**Score versioning and backfill.** `talent_scores.score_version` exists and is always `'v1'`. Making it real means a migration path that recomputes historical scores under a new formula while preserving the old ones, so a candidate's trajectory doesn't discontinuously jump when weights change.

**RLS in CI.** The policies in §6.3 need an automated test that connects as `overwatch_runtime` with each role context and asserts that cross-tenant reads return zero rows. Access control that isn't tested is access control that will regress.

**Replace the AI-content heuristic.** The burstiness statistic is weak and openly labeled as such. A real perplexity model — `transformers` and `torch` are already installed for it — would be a genuine improvement, and the interface already returns a confidence label to carry it.

### Medium-term (2–4 months)

Recruiter-defined scoring profiles, so a startup weighting scrappiness and an enterprise weighting consistency can both use the same platform — the hackathon `scoring_config` JSONB pattern generalizes directly. Bias auditing across demographic proxies, which matters more the more the platform is actually used for hiring decisions. Webhook integrations for Greenhouse and Lever, since no recruiter is abandoning their existing ATS. Assessment support for JavaScript and Java alongside Python.

### Longer-term

Time-series talent trajectory modeling — the `computed_at` history is already accumulating for it. Team composition analysis for hackathon organizers. Multi-language resume parsing. Self-hosted Langfuse for organizations that can't send LLM traces to a third party.

Deliberately not on this roadmap: automated rejection. The platform ranks, explains and surfaces evidence, and a human decides. Every guardrail described in this document assumes a person in the loop: human review gating fraud penalties, confidence labels on scores, and component breakdowns instead of bare numbers. Automating the decision would invalidate the design.

## 10.3 Troubleshooting Matrix

| Symptom | Root cause | Resolution |
| :--- | :--- | :--- |
| `pydantic_core.ValidationError: jwt_secret_key Field required` at startup | No default exists for this variable, by design | Add `JWT_SECRET_KEY` to `.env`; generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `asyncpg.exceptions.InvalidCatalogNameError: database "talent_platform" does not exist` | Postgres container not running or still initializing | `docker compose -f infra/docker-compose.yml up -d`; wait for `healthy` in `docker compose ps` |
| `alembic.util.exc.CommandError: Can't locate revision identified by '...'` | `alembic_version` table references a revision not in `versions/` | `python -m alembic stamp head` on a fresh DB, or check out the commit containing that revision |
| `sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 overflow 20 reached` | A handler holds a connection across a slow LLM call | Wrap the pipeline in `db.without_db_connection()`. Raising pool size only delays the same exhaustion |
| Row stuck at `"processing"` forever | The API restarted while a background pipeline was running; in-memory tasks do not survive a restart | Re-trigger the operation (re-upload, reconnect, or "Recompute"). There are no automatic retries |
| `LLM_UNAVAILABLE` / HTTP 503 on AI endpoints | Provider key missing or invalid for `LLM_PROVIDER` | Set the matching key. Mechanical scores are unaffected and still compute |
| `QdrantUnavailable` on career guidance | Qdrant container down or collections missing | Start the container, then `python scripts/ensure_qdrant_indexes.py` |
| Filtered vector search returns fewer results than `limit` | Payload indexes missing — Qdrant filters post-hoc after retrieval | `python scripts/ensure_qdrant_indexes.py` (idempotent) |
| First AI request after startup times out | Embedder still downloading (~1.3 GB on first run) | Wait for `Embedder model pre-loaded successfully` in the log. Subsequent starts use the cache |
| All sub-scores look uniform / percentile ranks all 50.0 | Candidate population below the 30-row threshold, so fallbacks engage | `python scripts/seed_candidates_hardcoded.py` |
| `SalaryModelUnavailable` in career guidance | The `.joblib` artifact hasn't been trained | Run `train_salary_model.py` against a Developer Survey CSV, or accept guidance without a salary range |
| `.ppt` upload returns 422 | LibreOffice not on PATH for legacy conversion | Install headless LibreOffice and set `LIBREOFFICE_BINARY`, or convert to `.pptx` first |
| Certificate OCR returns empty text | Tesseract not installed | Install `tesseract-ocr` |
| Uploads return 503 | `CLOUDINARY_URL` unset | Configure Cloudinary, or use features that don't require file storage |
| CORS error in browser console | Frontend origin missing from `CORS_ALLOWED_ORIGINS` | Add it (comma-separated). Restart the API — settings are `lru_cache`d |
| 429 responses far earlier than expected | Multiple Uvicorn workers each holding in-memory counters | Ensure Redis is reachable so counters are shared |
| Pyodide fails only in production | Missing COEP/COOP headers, so `SharedArrayBuffer` is unavailable | Add the cross-origin isolation headers from §9.1. Works locally because `localhost` is a secure context |
| `tsc --noEmit` errors after a backend change | Frontend types drifted from the Pydantic schemas | Update `apps/web/src/lib/api.ts` to match `packages/shared_schemas/` |
| Playwright tests fail immediately | Dev servers not running — `webServer` is intentionally unconfigured | Start both the API and the Next.js dev server before `npm run e2e` |
| Emulator can't reach a local API | `usesCleartextTraffic="false"` blocks plaintext HTTP | Point at an HTTPS endpoint, or add a debug network-security config |

## 10.4 Licensing & Intellectual Property Terms

Released under the MIT License.

```
MIT License

Copyright (c) 2026 TRACE

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Third-Party Licenses

| Component | License | Notes |
| :--- | :--- | :--- |
| FastAPI, Pydantic, SQLAlchemy, Alembic | MIT / BSD-3 | Permissive |
| Next.js, React | MIT | Permissive |
| LangGraph, langchain-core | MIT | Permissive |
| PyTorch, sentence-transformers | BSD-3 / Apache-2.0 | Permissive |
| `BAAI/bge-large-en-v1.5` | MIT | Model weights; commercial use permitted |
| Qdrant | Apache-2.0 | Permissive |
| Redis 7 | BSD-3 | Version 7 predates the RSAL relicense |
| PostgreSQL | PostgreSQL License | Permissive |
| Pyodide | MPL-2.0 | File-level copyleft; used unmodified |
| **PyMuPDF** | **AGPL-3.0** | **See note below** |
| Monaco Editor | MIT | Permissive |
| Recharts, dnd-kit, Framer Motion | MIT | Permissive |
| shadcn/ui, Base UI | MIT | Source copied into the repo by design |
| Tesseract OCR | Apache-2.0 | External binary |
| LibreOffice | MPL-2.0 | External binary, invoked via subprocess |

> **Important Note:** PyMuPDF is licensed under AGPL-3.0, which is the one dependency in this table with copyleft obligations that reach an entire distribution. Review it before any proprietary fork.

PyMuPDF is AGPL-3.0. Under an MIT-licensed distribution this is fine, but a *commercial closed-source* deployment would require either a commercial PyMuPDF license from Artifex or swapping resume PDF extraction to a permissively-licensed library such as `pypdf` or `pdfplumber`. The dependency is isolated to resume text extraction, so the swap is contained. Anyone forking this for proprietary use needs to handle it deliberately.

### Data & Attribution

The salary model trains on the publicly available Stack Overflow Developer Survey, released under ODbL. Candidate GitHub data is accessed only under explicit OAuth grant and only within the scopes the candidate approves. Generated documents remain the property of the candidate who requested them.

## 10.5 Error Log Book

This register catalogs the failure modes this architecture is exposed to: the mechanism behind each one, why it arises, and the specific mitigation that addresses it. Several describe failures that are common to systems of this shape and are the reason certain decisions elsewhere in this document look defensive for their size.

The register is ordered by severity. Each entry names the failure, its mechanism, the mitigation, and where in this document that mitigation lives.

---

### R-01 — Connection pool exhaustion under concurrent AI work

**Severity:** Critical · **Where it bites:** Every endpoint, not just the AI ones

**Mechanism.** A request handler acquires a pooled Postgres connection through the `get_db` dependency and holds it for the whole request — including the seconds or minutes spent awaiting an LLM response. With a default pool of 5 + 10 overflow, fifteen concurrent AI interviews pin every connection while performing no database work at all. The symptom is total: trivial reads with no AI involvement start failing with `QueuePool limit of size N overflow M reached, connection timed out`.

**Mitigation.** A `without_db_connection()` context manager that returns the connection to the pool for the duration of an AI call and reacquires afterwards. Any handler invoking a LangGraph pipeline uses it. Pool size is set to 20 + 20, but that is secondary and the config comments say so — a larger pool moves the failure threshold and changes nothing else.

**Why it ranks first.** It is the most likely way this system falls over under load, and it presents as "the whole app is broken" rather than "the AI feature is slow," which makes it expensive to diagnose. See §2.4 and §8.3.3.

---

### R-02 — Background jobs lost on restart, rows stuck at "processing"

**Severity:** Critical · **Where it bites:** Candidate ingestion, matching, grading

**Mechanism.** FastAPI's `BackgroundTasks` is the obvious way to run long pipelines and has three properties that together make an application feel broken. Tasks share the API process's event loop, so CPU-bound embedding work stalls every other in-flight request. Tasks exist only in memory, so a restart or deploy drops them without trace and the row they were meant to finish stays at `'processing'` forever. And there is no retry, so one transient GitHub or LLM blip fails the job permanently.

**Status: accepted, partially mitigated.** The pipelines currently run as `BackgroundTasks` (§4.4.1). A separate arq/Redis worker was built and then removed: its extra process and Redis dependency made the setup fragile, and a queue with no live worker failed silently, which was worse than this. What is in place: embedding runs off the event loop via `asyncio.to_thread`, handlers release their pooled connection across LLM calls, and the `ingestion_stage` column makes a dropped run visible so the user can re-trigger it. What is not: durability across restarts and automatic retries. A durable worker is the first change before production load.

---

### R-04 — Demo scaffolding producing fabricated scores

**Severity:** Critical · **Where it bites:** Credibility, irrecoverably

**Mechanism.** Building a matching UI before real candidate data exists invites a hardcoded demo pool. That pool then flows through the entire scoring pipeline and emerges with match percentages and generated fit explanations indistinguishable from genuine output. The same pattern produces buttons wired to placeholder handlers that return plausible results from nothing.

**Mitigation.** Demo data lives in seed scripts that write to the database (`scripts/seed_db.py`, `scripts/seed_candidates_hardcoded.py`), never in the application code path. If the matching pipeline has no candidates, it returns an empty result. Any UI control without a working backend ships disabled rather than faking a response.

**Why this one matters most.** A platform whose entire premise is eliminating unverifiable claims cannot itself generate them. Of everything in this register, this is the failure the architecture is most deliberately shaped to exclude.

---

### R-05 — Prompt templates rendered without variable substitution

**Severity:** Critical · **Where it bites:** Every agent output, invisibly

**Mechanism.** A prompt loader that returns raw template text without substituting variables sends the model literal `{{ candidate_skills }}` placeholders. The model answers around them, producing output that is generic but entirely coherent — so it reads as an LLM quality problem, not a bug, and can survive a long time undetected.

**Mitigation.** `services/agents/prompts_loader.py` interpolates `{variable}` placeholders and raises `ValueError` naming the prompt and every missing key, so a missing variable fails loudly rather than shipping a literal `{merged_profile_json}` to a paid LLM call. (The Jinja2 registry this originally described was deleted — it had no importers and pulled in an undeclared dependency.) `services/agents/tests/test_prompts_loader.py` asserts substitution, heading retention, and the missing-variable error.

**Principle.** A bug that quietly degrades output without ever raising is far harder to find than one that crashes. It needs a test written specifically for it, because nothing else will catch it.

---

### R-06 — Vector search silently returning incomplete results

**Severity:** High · **Where it bites:** Copilot search, skill gap, deck plagiarism

**Mechanism.** Without payload indexes, Qdrant applies filters *after* vector retrieval rather than during it. A selective filter over a top-k result set discards most of what was retrieved. The query succeeds, returns fewer results than requested — sometimes zero — and reports no error.

**Mitigation.** Payload indexes created at collection setup, plus `scripts/ensure_qdrant_indexes.py` as an idempotent backfill for environments provisioned before the index definitions existed. Covered in §4.4.3.

---

### R-07 — Rate limit multiplied by worker count

**Severity:** High · **Where it bites:** Any multi-worker deployment

**Mechanism.** Counters held in a process-local dictionary mean each Uvicorn worker enforces its own independent limit. Four workers with `RATE_LIMIT_PER_MINUTE=60` permit roughly 240 requests per minute. The same code invites a second defect: an unbounded `defaultdict` accumulating one permanent entry per distinct client IP, which is a slow memory leak on anything internet-facing.

**Mitigation.** Redis-backed counters shared across processes, with a bounded in-memory fallback capped at 10,000 buckets. The fallback degrades rather than failing, on the reasoning that a rate limiter returning 500s is worse than one that is merely per-process. See §4.1.4.

---

### R-08 — TCP handshake on every LLM call

**Severity:** Medium · **Where it bites:** Latency across all AI features

**Mechanism.** Constructing a provider SDK client per call builds a fresh httpx client with an empty connection pool each time, so every LLM call pays a full TCP and TLS handshake and reuses nothing. Latency sits consistently above the provider's own reported times with no obvious cause.

**Mitigation.** `get_llm_client()` is an `lru_cache` singleton. Provider SDK clients are thread-safe and intended to be long-lived. `lru_cache` does not cache exceptions, so a call failing on a missing API key still re-evaluates cleanly once the key is configured.

---

### R-09 — Startup pre-warming that blocks startup

**Severity:** Medium · **Where it bites:** First request after every deploy

**Mechanism.** The embedder takes tens of seconds to load, so the first request that needs it times out. The obvious fix — load it in a startup hook — makes things worse if written naively: calling `get_embedder()` directly blocks the event loop for the entire load, achieving precisely the opposite of the intent.

**Mitigation.** `asyncio.create_task` wrapping `await asyncio.to_thread(get_embedder)`, so the CPU-bound load genuinely leaves the event loop and startup proceeds.

**Principle.** "Run it in the background" means nothing in async code if the work is synchronous and CPU-bound. It has to actually move off the loop.

---

### R-10 — Single-row assumptions on multi-row data

**Severity:** Medium · **Where it bites:** Latest-score queries

**Mechanism.** `scalar_one()` raises `MultipleResultsFound` when more than one row matches. Append-only history tables are the obvious trap: `talent_scores` accumulates a row per rescore, so any query assuming a single row per candidate 500s the moment a candidate is scored twice.

**Mitigation.** Queries that logically want "the current one" order explicitly — `computed_at DESC` for scores — and take the first row. Historical rows are retained for the audit trail rather than deleted.

---

### R-11 — Speech recognition discarding candidate answers

**Severity:** High · **Where it bites:** AI interviews, at the worst possible moment

**Mechanism.** The Web Speech API fires an `end` event when it detects a pause. A handler that treats this as a session reset clears accumulated interim transcript text, so a candidate who pauses mid-thought watches their answer disappear.

**Mitigation.** Transcript state accumulates across recognition restarts and is never cleared by an `end` event — only by an explicit turn submission.

**Why it ranks high.** In a hiring context this is not a UI annoyance. It destroys a candidate's answer in an evaluation that affects whether they get a job.

---

### R-12 — Cross-region latency masquerading as slow code

**Severity:** High · **Where it bites:** Every page, on every request

**Mechanism.** Pointing at managed database and vector services in a different region than the application means every query pays a public-internet round trip. Query execution time reads in single-digit milliseconds while pages take seconds, and the gap is invisible to a query profiler because the time is spent in transit rather than in execution.

**Mitigation.** Postgres, Qdrant and Redis all run as local containers in the default development setup — `infra/docker-compose.yml`, no cloud accounts required. For production, §9.2 co-locates the API and its data stores, and §9.1 pins the frontend region to sit near the backend.

**Diagnostic heuristic.** Query timings that look fine while pages feel slow mean the time is going somewhere the profiler cannot see. Check the network path before optimizing the query.

---

### R-13 — Sequential scans on unindexed foreign keys

**Severity:** Medium · **Where it bites:** Dashboard, portfolio, recruiter pool build

**Mechanism.** Postgres creates indexes automatically for primary keys and unique constraints — not for foreign key columns. `github_snapshots.candidate_id` is read on the candidate dashboard, the public portfolio, the GitHub summary endpoint, and IN-filtered across the entire candidate set on every recruiter pool build. Unindexed, all four are sequential scans, and the degradation is gradual enough to be mistaken for normal growth.

**Mitigation.** Explicit indexes on hot-path foreign keys, enumerated in §6.2.5, plus `idx_match_scores_job_sort` carrying an explicit `DESC` direction so the ranked match list needs no sort step at all.

---

### R-14 — Global talent scores ranking specialists below generalists

**Severity:** Medium · **Where it bites:** Match quality, which is the core product

**Mechanism.** Applying one global Talent Score unmodified to every job means a candidate with exceptional depth in exactly the required stack scores identically against that job as against an unrelated one. Breadth-heavy generalists with higher global scores then consistently outrank the specialist the recruiter actually wants.

**Mitigation.** The job-contextual adjustment in §5.1.5 — `coding_ability` and `problem_solving` scaled by skill overlap ratio, `project_quality` and `innovation` at 0.8 times that ratio, recomposed with the original weights. The adjustment factor is returned and persisted so the recruiter sees both numbers.

---

### R-15 — Consistency scoring that penalizes long histories

**Severity:** Medium · **Where it bites:** Experienced candidates, unfairly

**Mechanism.** An unweighted coefficient of variation across a 52-week window treats the normal variation in a long career — vacations, job changes, project cycles — as inconsistency. A three-month history has less room to vary and therefore scores *better* than four years of dense contribution. The function does exactly what it was written to do; the formula itself is wrong.

**Mitigation.** Recency weighting via exponential decay, a staleness penalty for long gaps since the last active week, and a sustained-activity bonus above 75% window coverage. Full derivation in §5.2.6.

**How problems like this surface.** No unit test finds it, because the code matches its specification. It shows up only by cross-checking sub-scores by hand against real profiles with known characteristics — which is why §8.2 lists that as an explicit validation step rather than an afterthought.

---

### R-16 — Cross-origin isolation missing in production only

**Severity:** Medium · **Where it bites:** The coding assessment, in production only

**Mechanism.** Pyodide needs `SharedArrayBuffer`, which requires cross-origin isolation via COEP and COOP headers. Locally everything works, because `localhost` is treated as a secure context. In production the sandbox fails with an opaque error. A bug that appears only after deployment is one that no amount of local testing will surface.

**Mitigation.** Both headers are set explicitly on `.wasm` responses in the Vercel and Netlify configurations in §9.1, where the reason they are load-bearing rather than boilerplate is documented inline.

---

### R-17 — Toolchain friction with WebAssembly assets

**Severity:** Low · **Where it bites:** Local development

**Mechanism.** Bundler resolution of Pyodide's WebAssembly assets is not uniformly supported, and Turbopack in particular has trouble with them.

**Mitigation.** The `dev` script pins `--webpack`. This is an accepted workaround rather than a fix; the build-time difference does not justify the effort of resolving it properly.

---

### R-18 — Lint debt obscuring real warnings

**Severity:** Low · **Where it bites:** Everything, slowly

**Mechanism.** Warnings accumulate under time pressure — unused imports from refactors, `any` escapes added in a hurry. Individually harmless. Past a certain count nobody reads the list, and a genuinely important warning becomes invisible.

**Mitigation.** Zero-warning baseline enforced in CI (§9.2). A lint list nobody reads is equivalent to no linter at all.

---

### What This Register Is For

Three of these — R-04, R-05 and R-06 — describe failures that produce *plausible wrong output* rather than errors. Those are the genuinely dangerous ones, because a crash announces itself and a fabricated match score does not. Much of the architecture in this document exists to make that category structurally difficult: typed errors instead of fallback values, `None` instead of `0.0`, human review gating anything punitive, and component breakdowns persisted alongside every score so a wrong number can at least be traced back to its inputs.

The register is maintained as a living document, and new entries are added as new failure modes are identified.

---

*End of document.*
