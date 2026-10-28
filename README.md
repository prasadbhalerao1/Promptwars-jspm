# TRACE: Talent Reliability & Assessment through Credential Evidence

A multi-agent platform for talent intelligence, recruitment matching, hackathon evaluation, and trust/fraud prevention.

**The problem:** resumes and keyword matching cannot tell a candidate who has *built* something from one who only *claims* it, and the evidence that would tell them apart (code, hackathon results, assessments, pitch decks) goes unused. **TRACE scores candidates on that verifiable evidence, explains every score, and gives recruiters a hiring pipeline built on it.**

## Problem Statement Coverage

Each mandatory module of the problem statement, and where it is implemented:

| Problem-statement module | What TRACE delivers | Implementation |
|---|---|---|
| **Candidate Intelligence Platform:** AI Talent Profile Engine, AI Talent Score, dashboard | Profile built from GitHub, résumé, certificates, LeetCode and hackathon results. Nine evidence-backed sub-scores with a weighted composite; missing signals are dropped and their weight redistributed, never zero-filled. | `services/agents/candidate_intelligence/`, `services/agents/common/scoring.py`, `apps/web/src/app/(candidate)/dashboard/` |
| **AI Resume & Portfolio Builder** | ATS-scored résumé builder and a public portfolio page | `apps/web/src/components/AtsResumeBuilder.tsx`, `apps/web/src/lib/atsScoring.ts`, `apps/web/src/app/(public)/[username]/` |
| **AI Career Guidance** | Skill gaps, learning roadmap and salary range | `services/agents/candidate_intelligence/career_guidance_graph.py`, `apps/web/src/app/(candidate)/career/` |
| **AI Recruitment Platform:** recruiter dashboard, AI job matching, recruiter copilot | Four-term match score (skill overlap weighted toward *verified* skills, semantic similarity, experience, job-contextual Talent Score), hiring pipeline, funnel analytics and natural-language candidate search | `services/agents/recruitment/`, `services/api/modules/recruitment/`, `apps/web/src/app/(recruiter)/` |
| **AI Assessment & Verification:** skill verification, AI interview agent, team contribution analytics | Timed coding/MCQ assessments with static analysis and LLM code review; an adaptive AI interviewer (voice/text, or a live TruGen video avatar) grounded in the role's job description; per-member contribution reports | `services/agents/assessment/`, `services/api/core/trugen.py`, `apps/web/src/app/(candidate)/interviews/` |
| **AI PPT Analyzer** | Pitch-deck scoring on problem/solution, innovation and technical feasibility, with plagiarism and AI-content signals | `services/agents/ppt_analyzer/`, `apps/web/src/app/pitch-deck/` |
| **Hackathon-to-Hiring Pipeline** | Event creation, team import, judge scoring, ranking finalization, and top finishers pushed into recruiter feeds | `services/agents/hackathon/`, `services/api/modules/hackathons/`, `apps/web/src/app/(organizer)/`, `(judge)/` |
| **Trust & Fraud Prevention** | Certificate verification, code plagiarism, duplicate-profile and AI-content detection. A flag has no effect until a human upholds it, and the candidate can dispute it. | `services/agents/fraud/`, `services/api/modules/fraud/`, `apps/web/src/app/(admin)/fraud-review/` |

**Not implemented:** LinkedIn profile import. Profiles are built from the sources listed above.

## Quality Gates

Every push runs `.github/workflows/ci.yml`: backend `pytest` (API authorization boundaries, scoring formulas, agents, TruGen client), and frontend ESLint, TypeScript, Vitest and a production build.

---

## 1. Project Architecture & Modular Structure

The codebase is organized into clean, maintainable, decoupled packages and services:

```
TRACE/
├── apps/
│   └── web/                             # Next.js 16 (React 19, Tailwind CSS, Turbopack)
│       ├── e2e/                         # Playwright E2E test suite & setup
│       └── src/
│           ├── app/                     # Route groups: (candidate), (recruiter), (organizer), (judge), (admin), (public)
│           ├── components/              # Shadcn UI, Base UI, & custom control-plane components
│           └── lib/                     # API client functions (api.ts) & utilities
│
├── packages/
│   ├── db/                              # Database layer
│   │   ├── models/                      # SQLAlchemy async ORM models (User, Candidate, Job, Hackathon, Fraud, etc.)
│   │   └── migrations/                  # Alembic database migrations & revision versions
│   └── shared_schemas/                  # Pydantic schemas shared across FastAPI and frontend API calls
│
├── services/
│   ├── api/                             # FastAPI application & REST endpoints (91 routes)
│   │   ├── common/                      # Shared constants (page limits, truncation)
│   │   ├── core/                        # DB session, auth, LLM gateway, rate limiting, Qdrant, Sentry, audit logging
│   │   ├── integrations/                # Third-party clients
│   │   └── modules/                     # Endpoint routers (users, candidates, recruitment, assessments, hackathons, etc.)
│   └── agents/                          # 17 LangGraph subgraphs across 7 domains, + 24 prompt files
│       ├── candidate_intelligence/      # Talent Profile Engine, Talent Score™, Career Guidance
│       ├── recruitment/                 # Flow B Matching, Recruiter Copilot Query Understanding
│       ├── assessment/                  # Code Verification, AI Interview Agent, Contribution Scan
│       ├── ppt_analyzer/                # Pitch Deck 4-subagent domain analyzer & Sonnet synthesis
│       ├── hackathon/                   # Hackathon Evaluation Pipeline & Leaderboard rollup
│       ├── fraud/                       # Certificate OCR, Code Plagiarism, Duplicate Profile, AI Content
│       ├── supervisor/                  # Master Supervisor intent classifier & router
│       ├── catalogs.py                  # DB-backed curated catalogs (role skills, skill descriptions)
│       └── prompts_loader.py            # Loads {module}/prompts/{name}.md
│
├── scripts/                             # seed_db.py, seed_candidates_hardcoded.py, dev-up.ps1
├── infra/                               # docker-compose.yml (local development)
├── .agents/decisions.md                 # Architecture decisions — why the code is shaped this way
└── Documentation/                       # Module docs (00-15), guides/, PROGRESS_LOG.md
```

Agent domains and their graphs: `candidate_intelligence` (3), `assessment` (5), `fraud` (4),
`recruitment` (2), `hackathon` (1), `ppt_analyzer` (1), `supervisor` (1).

---

## 2. Platform Modules & Roles

### Roles & Access Flow
* **Candidate**: Profile ingestion, Talent Score™, AI career guidance, Pyodide code sandbox assessments, AI audio interviews, job browse/apply, hackathon submission, dispute flags.
* **Recruiter**: Job posting, AI Copilot search assistant, Flow B match reranking with fit explanations, drag-and-drop pipeline kanban, top performers feed.
* **Organizer**: Create hackathons, structured team import (`POST /hackathons/{id}/import/csv`, JSON rows — no spreadsheet parsing), manage rosters, custom judge weight sliders, leaderboard finalization.
* **Judge**: Evaluation queue, submission review, rubric scoring & feedback entry.
* **Admin**: User directory, RBAC role updates, multi-tenant organization assignment, system audit log viewer, trust/fraud review queue.

---

## 3. Quick Start & Setup

### Prerequisites
* Python 3.12 (`>=3.12,<3.13` — 3.13 is not supported)
* Node.js 20+
* Docker (for Postgres, Qdrant, and Redis)

### 1. Infrastructure — all local, no cloud accounts

Postgres, Qdrant, and Redis all run as local containers. Nothing here needs an API key.

```bash
docker compose -f infra/docker-compose.yml up -d
```

### 2. Environment configuration

Copy `.env.example` to `.env`. Its defaults already point at the containers above:

```bash
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost:5432/talent_platform
DATABASE_SSL_REQUIRED=false
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379

# External services. Without an LLM key, AI features raise LLMNotConfigured and the API
# answers 503 with code LLM_NOT_CONFIGURED — deliberately, rather than inventing a score.
# Mechanical/deterministic signals still work; the LLM-derived ones report as unavailable.
LLM_PROVIDER=anthropic          # or: openai | grok | groq | gemini | openai_compatible
ANTHROPIC_API_KEY=""
CLOUDINARY_URL=""               # optional: file uploads
SENTRY_DSN=""                   # optional: error reporting
```

See [Documentation/15-local-development-setup.md](Documentation/15-local-development-setup.md)
for how to obtain each optional key.

### 3. Backend (FastAPI)

```bash
# Create the schema, then load demo data
python -m alembic upgrade head
python scripts/seed_db.py                     # catalogs, trusted issuers, reference data
python scripts/seed_candidates_hardcoded.py   # demo users you can actually log in as

uvicorn services.api.main:app --reload --port 8000
```

Seed logins: `alice@example.com` … `evan@example.com`, password `password123`. These come
from `seed_candidates_hardcoded.py` — run it, or you will have a schema with no account to
sign in with. Both scripts are idempotent (`select`-then-insert), so re-running is safe.

### 4. Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

---

## 4. Verification & Testing

```bash
# Python test suite
python -m pytest -q

# OpenAPI still builds and every route registers
python -c "from services.api.main import app; print(len(app.openapi()['paths']), 'routes')"

# Frontend: types, lint, unit tests
cd apps/web
npx tsc --noEmit
npx eslint src --max-warnings=0
npx vitest run

# Production build
npm run build

# End-to-end (needs the API and frontend running)
npx playwright test
```

A few tests are worth knowing about, because they fail on classes of mistake that are
otherwise silent:

| Test | Catches |
|---|---|
| `test_config_parity.py` | A setting whose default drifted from the literal it replaced |
| `test_api_contract_sync.py` | A required API response field missing from the TypeScript client |
| `test_reserved_usernames.py`, `test_cross_language_constants.py` | Python/TypeScript constants drifting apart |
| `test_prompt_standard.py` | A prompt missing guardrails, edge cases or examples |
| `test_docs_references.py` | Documentation pointing at a file that no longer exists |
