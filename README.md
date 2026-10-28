# TRACE: Talent Reliability & Assessment through Credential Evidence

A multi-agent platform for talent intelligence, recruitment matching, hackathon evaluation, and trust/fraud prevention.

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
