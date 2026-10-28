# Architecture Overview

This is the "start here" document. It gives the full shape of the system before the
per-module docs go deep on any one piece.

## What this is

An AI-native hiring and hackathon platform: candidates build a verified profile (GitHub +
resume + certificates), get scored on a multi-dimensional Talent Score, get matched to jobs
by a recruiter copilot, get assessed via coding tests / project review / live AI interviews,
and get cross-checked by a fraud-detection layer that never auto-penalizes without a human
in the loop. A parallel hackathon track lets organizers run events whose top performers feed
directly into recruiter pipelines.

## High-level system shape

```
                    ┌──────────────────────────┐
                    │   Next.js 16 frontend      │
                    │   apps/web (App Router,    │
                    │   role route-groups)       │
                    └──────────────┬─────────────┘
                                   │ fetch + Bearer JWT
                                   ▼
                    ┌──────────────────────────┐
                    │   FastAPI backend          │
                    │   services/api             │
                    │   core/  +  modules/*      │
                    │   (routers own DB access)  │
                    └───┬───────────┬────────────┘
                        │           │
          invokes graphs│           │reads/writes
                        ▼           ▼
        ┌───────────────────┐  ┌─────────────────────┐
        │ LangGraph agents    │  │ PostgreSQL (local)   │
        │ services/agents/    │  │ packages/db models   │
        │ 7 modules, 12 graphs│  │ + Alembic migrations │
        │ (DB-free nodes)     │  └─────────────────────┘
        └───┬───────────┬────┘
            │           │
            ▼           ▼
   ┌────────────────┐ ┌──────────────┐    ┌───────────┐
   │ Qdrant (vector)  │ │ LLM gateway   │    │ Redis      │
   │ local Docker     │ │ Anthropic/    │    │ local      │
   │                  │ │ OpenAI/Groq/  │    │ Docker     │
   │                  │ │ Gemini        │    │ container  │
   └────────────────┘ └──────────────┘    └───────────┘
```

Requests flow frontend → API → (optionally) an agent graph → database, with Qdrant and the
LLM gateway as shared infrastructure any agent module can call into. Routers, not graph
nodes, own every database read/write — see
[10-multi-agent-architecture.md](10-multi-agent-architecture.md) for why.

## Tech stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend framework | Next.js 16.2.12, React 19.2.4 | App Router, route-group-based RBAC UI |
| Styling | Tailwind CSS 4, shadcn 4.16.0 | see [12-ui-design-system.md](12-ui-design-system.md) |
| Frontend animation | framer-motion 12.43.0 | |
| Frontend misc | @dnd-kit (kanban), @monaco-editor/react (code editor), recharts 3.10.1 (charts), pyodide 314.0.3 (in-browser Python execution for coding assessments), html2pdf.js, sonner, next-themes | |
| Backend framework | FastAPI 0.140.13, uvicorn 0.51.0 | |
| Backend data layer | SQLAlchemy 2.0.51 (async, asyncpg driver), Alembic 1.18.5 | |
| Backend validation | Pydantic 2.13.4 + pydantic-settings | |
| Auth | python-jose 3.5.0 (JWT), bcrypt 5.0.0 (password hashing) | fully custom, no external identity provider — see [01-authentication-and-rbac.md](01-authentication-and-rbac.md) |
| LLM gateway | `services/api/core/llm.py::get_llm_client()` | multi-provider: anthropic (default/production) / openai / groq / gemini / openai_compatible |
| Default models | fast tier `claude-haiku-4-5-20251001`, judgment tier `claude-sonnet-4-6` | `config.py:40-41` |
| Embeddings | `sentence-transformers`, `BAAI/bge-large-en-v1.5` | cached singleton, see [11-vector-search-and-llm-gateway.md](11-vector-search-and-llm-gateway.md) |
| Relational database | PostgreSQL via SQLAlchemy async + asyncpg | local Docker container, always-on |
| Vector database | Qdrant | local Docker container, always-on |
| Cache | Redis | local Docker container, always-on |
| File storage | Cloudinary | `services/api/core/storage.py`, `services/api/integrations/storage/cloudinary_adapter.py` |
| Background work | FastAPI `BackgroundTasks`, in-process | see "Task queue" note below — not a real distributed queue |

### Task queue — an honest note

There is no task queue. `services/api/core/event_consumer.py` uses a simple polling loop
instead of a message broker, and long pipelines (resume ingestion, job matching, assessment
grading, pitch-deck analysis, hackathon rankings) run as FastAPI `BackgroundTasks` inside the
API process. An arq/Redis worker existed for a while and was removed: it added a second
process to run for no benefit at this scale. The trade-off is that a job running when the
API restarts is lost and its row stays at "processing" until re-triggered.

## Top-level repo structure

```
apps/web/              Next.js 16 frontend (App Router, route-group-based RBAC UI)
services/api/          FastAPI backend — core/, modules/ (routers), integrations/
services/agents/       LangGraph agent modules (7 domains, 12 graphs total)
packages/db/           Shared SQLAlchemy models/ + Alembic migrations/
packages/shared_schemas/ Shared Pydantic schemas between api/ and agents/
infra/                  docker-compose.yml (local-dev-only)
scripts/                dev-up.ps1, seed_db.py, seed_candidates_hardcoded.py — dev/seed helpers
alembic.ini             Root Alembic config
```

## Frontend route groups

Under `apps/web/src/app/`: `(admin)/`, `(candidate)/`, `(judge)/`, `(organizer)/`,
`(public)/`, `(recruiter)/`, plus non-grouped `dashboard/` and `pitch-deck/` top-level
routes, plus `api/` (Next.js route handlers, mostly OAuth passthroughs). Each role group has
its own `layout.tsx` that gates access for UX purposes only — real enforcement is
server-side. See [01-authentication-and-rbac.md](01-authentication-and-rbac.md).

## LangGraph agent inventory

7 domain modules, 12 graph files total:

| Module | Graph entry file(s) |
|---|---|
| `candidate_intelligence/` | `graph.py` |
| `recruitment/` | `matching_graph.py`, `copilot_graph.py` |
| `assessment/` | `contribution_graph.py`, `interview_definition_graph.py`, `interview_graph.py`, `interview_report_graph.py`, `verification_graph.py` (5 graphs) |
| `fraud/` | `cert_graph.py`, `content_graph.py`, `duplicate_graph.py`, `plagiarism_graph.py` (4 graphs) |
| `hackathon/` | `graph.py` |
| `ppt_analyzer/` | `graph.py` |
| `supervisor/` | `graph.py` |
| `common/` | shared code (scoring helper etc.), no graph of its own |

The supervisor fronts only 2 of these 7 modules (candidate_intelligence, recruitment); the
other 5 are invoked directly by their own FastAPI routers. Full explanation in
[10-multi-agent-architecture.md](10-multi-agent-architecture.md).

## Database models

`packages/db/models/`, 14 files, 34 exported classes, migrated via Alembic
(`alembic.ini` at repo root, `packages/db/migrations/`):

| File | Classes |
|---|---|
| `base.py` | `Base` |
| `organization.py` | `Organization` |
| `user.py` | `User` |
| `file.py` | `File` |
| `event.py` | `Event` |
| `agent_run.py` | `AgentRun` |
| `audit_log.py` | `AuditLog` |
| `candidate.py` | `CandidateProfile`, `GithubSnapshot`, `Certification`, `TalentScore`, `Badge`, `GeneratedDocument`, `CourseCatalogEntry`, `CareerRecommendation` |
| `presentation.py` | `Presentation`, `PlagiarismMatch`, `PresentationScore`, `Slide` |
| `recruitment.py` | `Job`, `Application`, `MatchScore`, `CopilotConversation`, `SkillTaxonomyEntry`, `LocationAlias` |
| `assessment.py` | `Assessment`, `Submission`, `InterviewSession`, `InterviewTranscriptTurn`, `InterviewReport`, `InterviewDefinition`, `ContributionReport` |
| `hackathon.py` | `Hackathon`, `HackathonTeam`, `HackathonTeamMember`, `HackathonSubmission`, `HackathonRanking`, `RecruiterWatchlist` |
| `fraud.py` | `VerificationRecord`, `FraudFlag`, `AuthenticityScore`, `Dispute`, `TrustedIssuer` |

## Current deployment status

This runs today as local development servers, not a deployed production stack:

- **Backend**: `uvicorn services.api.main:app --reload --port 8000` from the repo root.
- **Frontend**: `npm run dev` in `apps/web`, served on `:3000`.
- **Data layer**: Postgres, Qdrant and Redis all run as local Docker containers,
  brought up together by `docker compose -f infra/docker-compose.yml up -d`. No
  account, API key or network access is needed for any of them. The only outbound
  calls the app makes are to the LLM provider, GitHub and Cloudinary — none of which
  hold application state.

There is **no committed deployment manifest** in this repository — no `Dockerfile`, no
`render.yaml`, no `vercel.json` anywhere in the working tree. This is a factual statement,
not a criticism: the project's infrastructure investment went into the agent pipelines, the
fraud-detection design, and the scoring system rather than into packaging a one-click
production deploy. Anyone standing this up outside local dev would need to write that
packaging themselves. See [15-local-development-setup.md](15-local-development-setup.md)
for the actual, working local setup.

## Where to go next

- New to the codebase? Read this doc, then
  [10-multi-agent-architecture.md](10-multi-agent-architecture.md) for the orchestration
  model, then [09-trust-and-fraud-prevention.md](09-trust-and-fraud-prevention.md) for the
  most detailed single module.
- Setting up locally? Go straight to
  [15-local-development-setup.md](15-local-development-setup.md).
- Evaluating a specific feature? Use the [README](README.md) table of contents.
