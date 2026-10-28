# TRACE — UX Overhaul Progress Log

Working log for the smooth-UX pass. Started from a full performance audit; the plan lives
at `~/.claude/plans/your-job-is-to-structured-quokka.md`.

**Status as of 2026-08-16: all seven phases complete.**

**Nothing is committed.** Everything below is in the working tree.

---

## Verification status

All re-run after the final change:

| Check | Command | Result |
| :--- | :--- | :--- |
| Python tests | `uv run pytest -q` | **82 passed** |
| API imports | `python -c "from services.api.main import app"` | **15 routes OK** |
| Typecheck | `npx tsc --noEmit` | **clean** |
| Lint | `npx eslint src` | **clean** |
| E2E | `npx playwright test` (production build) | **3 passed** |
| Schema | fresh DB from baseline vs. live `pg_dump --schema-only` | **identical** |
| Model drift | `alembic revision --autogenerate` | **empty** |

Verified live against the running API rather than by unit tests alone — a missing `func`
import in Phase 2 passed all 82 tests and would have `NameError`d on every dashboard
load. **Always hit the running API too.**

---

## What was fixed

### 1. The "Failed to fetch" errors while the API was running — root cause found

**This was a real bug, not a copy problem.** The rate limiter was set to
**60 requests/minute per user**. One dashboard load issues ~6 requests, and the limit is
per *user* across all endpoints, so a handful of navigations inside one minute returned
`429`s. The frontend had **no 429 handling at all**, so they surfaced as raw errors.

Reproduced directly: 75 rapid `GET /me` → `59 × 200, 16 × 429`.

Three fixes:

- `rate_limit_per_minute` default **60 → 600** (`services/api/core/config.py`), and the
  same in `.env` / `.env.example`. This is an abuse ceiling, not a usage budget.
- **CORS preflights exempted** (`services/api/core/rate_limit.py`). `OPTIONS` carries no
  `Authorization` header, so it fell through to the shared client-IP bucket — a page's
  real requests competed with their own preflights, and everyone behind one NAT shared
  the allowance.
- **Transient failures now auto-retry** with exponential backoff in `useAsyncResource`
  and `CurrentUserProvider` (429/502/503/504 and connection-level failures). Retries
  happen in place, so the section never flashes back to a loading state.

Verified after: 120 rapid `GET /me` → **120 × 200**; 30 preflights → **30 × 200**.

### 2. Boot-state error handling

A bare `TypeError: Failed to fetch` is indistinguishable from an app error to a user, but
usually just means the API hasn't finished pre-warming its 1.3GB embedding model.

New `ConnectionState` component (`apps/web/src/components/common/ConnectionState.tsx`)
distinguishes them: a connection failure has no HTTP status attached, a real error does.
It shows "Connecting to the server…" with automatic retry, escalating to "Still can't
reach the server" after 4 attempts. Wired into `WorkspaceShell`; genuine API errors still
get the red `SectionError` box.

### 3. Onboarding wizard — and the bug that made it unreachable

**`/onboarding` did not exist**, yet every workspace layout redirected there. Worse,
`GET /me` hardcoded `onboarding_required = False` whenever a `users` row existed — a
state signup makes unreachable — so the flag was effectively **always false** and the
redirect could never fire anyway.

- `_candidate_onboarding_incomplete` (`services/api/modules/users/router.py`) now checks
  `full_name`, `headline`, `location`, and a first `education` entry with both
  `institution` and `degree`. Read-only by design: `/me` runs on nearly every page load
  and must not create a profile row as a side effect. Only candidates are gated.
- Three-step wizard at `/onboarding` (identity → background → connect) with a progress
  rail, per-field validation, and a save through `PATCH /candidates/me` after each step
  so a refresh or OAuth detour never loses typed answers.
- GitHub is **required-but-skippable** — a hard block would strand users whenever OAuth
  is misconfigured, and the gap keeps surfacing on the `/home` completeness meter.
- `/onboarding` sits **outside every route group**, since those layouts are what redirect
  to it.

**Also found:** `completeOnboarding()` in `lib/api.ts` posted to `POST /users/onboarding`,
**an endpoint that has never existed** — only its Pydantic schema does. Every call would
have 404'd. It had no callers; removed.

**Seed gap fixed:** no seeded candidate had `education`, and the demo candidate had no
`location`, so every demo account would have been forced through the wizard on sign-in.
Fixed in `scripts/seed_db.py` and backfilled on the 8 live rows. Verified
`demo_candidate` / `alice` / `bob` all return `onboarding_required = False`.

### 4. Consent system removed entirely

Table, model, FK, all 8 backend enforcement points, all 6 frontend call sites, and
**every trace in comments, docstrings and documentation**.

- Migration `u6v7w8x9y0z1` drops `consents` and `interview_sessions.consent_id`. That
  column was **NOT NULL**, so it had to go first — the plan hadn't caught this. The
  downgrade mirrors the real table exactly (including `revoked_at`, `ip_address`,
  `terms_version` and both server defaults, which the ORM model never mapped).
  Round-trip tested.
- `_require_consent`, `POST /candidates/me/consents/{type}`, `grantConsent()` all gone.
- The interview page's consent card is gone; `/interview/new` now starts the session on
  arrival. `consentGiven` state renamed to `sessionStarted` — it never tracked consent,
  only whether the chat should render.
- In `check_profile_duplicate`, both comparison corpora were consent-gated; both now
  always run.
- Docs updated: `Hackathon_Submission.md` (§4.1.3 removed and sections renumbered, ER
  diagram, DDL, table/revision counts, security narrative, pitfall section), plus
  `00`, `09`, `13`, and three guides.
- **Dead config removed:** `INTERVIEW_CONSENT_REQUIRED` was in `.env`/`.env.example` but
  read by no code.

`grep -rni consent` across code and docs now returns nothing outside this log and the
drop migration itself.

### 5. GitHub OAuth return path

The callback hard-coded a redirect to `/profile/edit`, so the wizard couldn't get the
user back. Added a `return_to` parameter carried through the OAuth `state`.

It is an **allowlist keyed by name, not a URL** — `state` survives a full round trip
through github.com, so echoing back an arbitrary value would be an open-redirect
primitive. Verified: `bogus_evil`, `//evil.com`, `""` and `None` all fall back to
`/profile/edit`.

The key rides inside the existing `_oauth_state_cache` tuple rather than a parallel dict,
so it's discarded by the same `.pop()` — a second map would leak an entry for every
abandoned OAuth flow.

### 6. Earlier in this pass (Phases 1 / 1.5.2 / 1.5.3)

- **28 fetchers were being invalidated on every render.** `AuthProvider` and
  `CurrentUserProvider` both returned fresh object literals with unmemoized functions;
  every fetcher in the app is memoized on `getToken`. `useCallback` + `useMemo` on both.
- `/me` cached in `localStorage`, hydration-safe via an `isLoaded` gate.
- `WorkspaceShell` renders the sidebar immediately; only `children` waits on `/me`.
- 14 `loading.tsx` skeletons.
- `/home` role-based hub; `/dashboard` moved inside `(candidate)` so it has a sidebar.
- Rebrand to TRACE; e2e suite rewritten off Clerk; uv/`pyproject.toml` + `SETUP.md`.

---

### 7. Population + vector DB seeded (Phase 2 backend)

**The O(N²) ingestion queries.** Six unbounded population queries ran on every ingestion,
three of them window-function scans over the append-only `talent_scores` table. The
absurdity: `percentile_normalize` discards the population below 30 candidates, so all six
ran and were thrown away. Now one COUNT gates them, three window scans collapse to a
single `DISTINCT ON`, and results cache for 5 minutes — **6 scans → 1 COUNT** under 30
candidates. Verified against real Postgres by bypassing the guard.

**Unbounded dashboard payloads.** Totals now aggregate in SQL instead of loading every
snapshot to sum five columns in Python; projects cap at 50, score history at 30 newest.
`latest_score` is selected directly rather than taken as `scores[-1]` of the full history.

**`scripts/seed_realistic_population.py`** — 60 correlated candidates + 266 real
embeddings. Deliberately not random: six real stacks (backend/frontend/ML/infra/mobile/
data) with seniority driving scores, repo count, stars and commits together, and a
right-skewed ability distribution. Uniform random data would make every percentile ~50
and make semantic search look broken while working correctly.

Results after seeding:

| Check | Before | After |
| :--- | :--- | :--- |
| Scored candidates | 6 | **66** (percentile path ACTIVE) |
| `percentile_normalize` | flat 50.0 for everyone | 3.2 / 25.8 / 75.8 / 98.4 across the range |
| Qdrant vectors | 0 | **266**, 0 orphans |
| Backend job → backend candidates | n/a | 65–67 |
| Backend job → mobile/UI candidates | n/a | ~54 |

Postgres is seeded through the real SQLAlchemy models with constraints enforced. Qdrant
vectors are real `SentenceTransformer` output in the exact payload shape
`judgment_scores.py` writes — but written by the script rather than by the ingestion
pipeline, which would need live GitHub OAuth per candidate. Referential integrity checked:
266 snapshots ↔ 266 vectors, zero orphans.

**A bug caught only by live testing:** I used `func.coalesce` without importing `func`.
All 82 unit tests passed — they don't exercise that path — and it would have been a
`NameError` on every dashboard load. Found by hitting the running API.

### 8. Phase 4 — interview leaks, lobby, and prompt guardrails

**E2E re-run first:** 3/3 passing in 8.6s against a production build. The onboarding gate
did not break sign-in.

**4A — four real bugs in `interview/[sessionId]/page.tsx`:**

| Bug | Fix |
| :--- | :--- |
| Unmount stopped **video tracks only** — the microphone stayed live after navigating away, OS indicator still lit | Cleanup now stops tracks, `recognition.stop()`, and `speechSynthesis.cancel()` |
| TTS kept talking on an unmounted page | Same cleanup |
| Effect depended on the whole `messages` array and `speak()` *queues* — every re-render stacked another reading of the same question | Track last-spoken index in a ref; `cancel()` before each new utterance |
| `recognition.onend` closed over a stale `interimTranscript` (always `""`), silently dropping the last partial phrase | Mirror into `interimTranscriptRef` |

**Verified in a real browser**, not just by reading: instrumented `getUserMedia`, turned
the camera on, navigated away via the sidebar, and asserted track state went
`"live"` → `"ended"`. Required adding `--use-fake-device-for-media-capture` to
`playwright.config.ts` (kept — useful for the lobby specs later).

**4B — `components/interview/InterviewLobby.tsx`:** two-pane device check. Camera preview
+ mic level meter (`AudioContext`/`AnalyserNode`) on the left, topic outline on the
right. Releases **all three** resources on unmount (tracks, `cancelAnimationFrame`,
`AudioContext.close()`) — the exact set 4A was leaking.

Both entry points now route through it. `handleStartDefinitionInterview` previously
called `startInterview()` *directly on click*, so candidates were dropped into a live
session with no chance to check anything. Joining with a denied camera is still allowed —
the interview is fully answerable by text.

**Prompt review** (`services/agents/assessment/prompts/`). The infrastructure is sound:
enforced JSON schemas, bounded history (`_MAX_VERBATIM_TURNS` avoids cost growing
quadratically with interview length), per-answer truncation. Two genuine gaps found:

- **`generate_definition_questions` never validated its output.** An empty `topics` array
  produced an empty `topic_plan`, and `turn_evaluation` indexed into it unguarded →
  **IndexError → 500 mid-interview, losing the turn.** Now raises `AssessmentUnavailable`
  on empty/blank, trims overshoot to `question_count`, and `turn_evaluation` guards the
  index the same way `question.run` already did.
- **`generate_question.md` had no examples**, unlike its three siblings. Added three
  weak/good pairs plus an explicit "never invent history" rule.

All guards verified with mocked LLM responses — **zero credit spent**.

### 9. Phases 5, 6, 7 — polish, hygiene, and the migration squash

**Phase 5.** Two audit claims turned out to be **already handled by Next 16**:
`lucide-react` and `recharts` are in `optimizePackageImports`' default list, so adding
them would have been a no-op that reads like a win. `@base-ui/react` is imported via deep
subpaths, so there is no barrel there either. Only `framer-motion` genuinely qualified.

Real fixes: Monaco now dynamic (MCQ assessments downloaded it and never rendered it),
recharts lazy on the public portfolio via a client wrapper (the page is a Server
Component, so it cannot call `next/dynamic` with `ssr: false` itself), `useCountdown`
clears at zero (was re-rendering the sidebar at 1 Hz forever), `Promise.all` on the jobs
page, and a shared `pollDelay()` that pauses all four pollers while the tab is hidden.

Also on the backend: `GET /candidates/{id}/authenticity-score` **inserted a row on every
read** — the table grew with page views. Now computed and returned, never persisted. And
the dispute reviewer-assist summary is cached on the dispute row instead of firing a live
LLM call, while holding a DB connection, on every flag-detail page load.

**Phase 6.** `events` partial index (the consumer seq-scanned the whole table every 30s
forever) plus `FOR UPDATE SKIP LOCKED`; `agent_runs` composite index; `/jobs/open`
paginated; both analytics endpoints moved from Python `defaultdict` counting to SQL
`GROUP BY`. Skipped the `lazy="joined"` → `lazy="select"` change as planned — it touches
every profile query app-wide and wasn't worth the risk here.

**Phase 7 — and this is why the order mattered.** The plan's step 1 says to confirm
autogenerate produces an *empty* migration before squashing. **It did not.** Real drift
existed between the models and the database:

- 13 indexes created by an old migration but never declared on any model — the squash
  would have **silently dropped every one of them**
- `candidate_profiles.hackathon_experience` was `json` in the DB but `JSONB` in the model
- three `NOT NULL` constraints missing from the DB
- five genuinely redundant indexes (exact duplicates, or prefixes of composites)

Fixed all of it first: dropped the redundant five, declared the real ones on the models,
converted the column, added the constraints. Only then did autogenerate come back empty.

Squash result: **33 migrations → 1 baseline** (`e8c387ea8123`). Verified by building a
fresh database from the baseline and diffing `pg_dump --schema-only` against the live
schema — **identical**, after aligning three auto-named constraints (checked first that
no code referenced the old names). Post-squash autogenerate is empty. Old chain backed up
to `/tmp/migration_backup/` before deletion.

## Remaining / deferred

Everything in the plan is done. Three things were deliberately left:

1. **Browser testing of the lobby's permission states** — grant both, deny camera only,
   deny both, no devices. The camera-release fix *was* verified in a real browser
   (`"live"` → `"ended"`); it is the lobby's four permission branches that are untested.
   `playwright.config.ts` already carries `--use-fake-device-for-media-capture`, so this
   needs no hardware.
2. **Live LLM verification** — one `generate-questions` call and one interview turn.
   Everything else was verified structurally or with mocked responses to conserve credit.
   Note a real LLM question *was* observed end-to-end during Phase 4A debugging: the
   interview page generated a FastAPI/LangGraph question grounded in the seeded profile.
3. **`lazy="joined"` → `lazy="select"`** on `CandidateProfile.user` — skipped on purpose.
   It touches every profile query app-wide and needs the assessments attempts list,
   public portfolio, and recruiter match list all exercised.

---

## Resuming (paused 2026-08-16)

### Bring the stack back up

```powershell
docker compose -f infra\docker-compose.yml up -d          # postgres, redis, qdrant
uv run uvicorn services.api.main:app --port 8000          # NO --reload; see below
cd apps\web; npm run dev
```

Or `powershell -ExecutionPolicy Bypass -File scripts\dev-restart.ps1` for all of it.

Nothing needs re-seeding — the Docker volumes persist. Expected state on restart:
**69 candidate profiles, 66 scored, 266 Qdrant vectors**, migration head
`e8c387ea8123`. If any of those read zero, the volume was dropped; re-run the three
seeders in §8 of SETUP.md.

### Working tree

**Nothing is committed.** 64 files changed on branch `dev`, last commit `c53402e`.
That includes **31 deletions** — 33 old migrations minus 2, plus the consent model and
the Clerk e2e setup. Four new paths:

- `packages/db/migrations/versions/e8c387ea8123_baseline_schema.py` — the only migration
- `scripts/seed_realistic_population.py`
- `apps/web/src/components/interview/` (the lobby)
- `apps/web/src/components/charts/CommitActivityChartLazy.tsx`

The pre-squash chain is archived in `.archive/pre-squash-migrations/` (33 files) with the
matching schema dump. Safe to delete; see `.archive/README.md`.

### First thing to do

Decide whether to **commit**. This is a large, coherent, fully-verified change set, and
64 uncommitted files is a lot to be carrying — a squashed migration chain in particular
is awkward to reconstruct if the tree is lost.

### Then, if you want to close out the deferred work

1. Lobby permission states in a browser (no hardware needed — the fake-device flags are
   already in `playwright.config.ts`).
2. One live `generate-questions` call and one interview turn.

## Notes for whoever resumes

- **An Anthropic key IS configured, and credit is low.** Spend it deliberately. Almost
  everything in this pass was verified structurally or with mocked responses instead —
  `generate-questions` raises a typed 503 without a key rather than fabricating, so the
  no-key path is genuinely testable for free. One real LLM question *was* observed
  end-to-end during Phase 4A (a FastAPI/LangGraph question grounded in the seeded
  profile), so the loop is known to work.
- The API does **not** run with `--reload`; restart it manually after backend edits.
  Several confusing results during this work traced back to a stale process.
- **If auth suddenly 500s, check Docker first.** The containers stopped cleanly mid-session
  (Docker Desktop shutting down), and `asyncpg` surfaces that as
  `ConnectionRefusedError` inside a generic 500 — it reads like an application bug.
  `docker compose -f infra/docker-compose.yml up -d` fixes it; the named volume means no
  data is lost.
- `lucide-react` no longer ships brand icons — there is no `Github` icon. `GitBranch` is
  used in the wizard.
- `seed_db.py` and `seed_candidates_hardcoded.py` are **not** idempotent — re-running
  raises `UniqueViolationError`. `seed_realistic_population.py` **is** (skips existing
  emails, deterministic vector ids), so it is safe to re-run.

---

## UI/UX redesign pass (2026-08-17)

Followed `apps/web/DESIGN.md`, written first as the specification the build answers to.
Behavior was preserved throughout: no API, permission, or business-logic changes, and the
optimistic pipeline updates, `useAsyncResource` retry semantics and interview
resource-cleanup fixes are untouched.

### Measured outcomes

| | Before | After |
| :--- | ---: | ---: |
| `dark:` variants (app code) | 364 | 0 |
| Hardcoded `slate/zinc/indigo` | 772 | 0 |
| Hex literals | 12 | 0 |
| Hand-rolled fetchers in pages | 15 | 2 (both justified) |
| Pages using `PageHeader` | 0 | 35 |
| Raw `<h1>` in pages | 33 | 2 (landing hero, root `error.tsx`) |
| `error.tsx` boundaries | 1 | 7 |
| `aria-live` regions | 1 | 5 |
| Native `confirm()` | 1 | 0 |

### Bugs found and fixed while redesigning

These were defects, not styling:

- **Data loss on timed assessments.** `(candidate)/assessments/[id]` had `if (error) return`
  above the render, so a *submission* failure unmounted the editor and destroyed the
  candidate's typed code. Load and submit errors are now separate states.
- **Silent admin privilege escalation.** `(admin)/users` committed a role change the instant
  the `<select>` changed — granting full admin took one stray interaction with no undo.
  Now confirms, and states what the role grants.
- **Judge score scale mismatch.** The scoring form asked for 0–100 while the evaluation queue
  rendered the same value as `/10`, so entering 90 displayed "90/10". The backend takes an
  unbounded `float`, so the UI was the only place the scale was defined. Aligned to `/10`.
- **Fabricated personal data in a production path.** `AtsResumeBuilder` shipped a fully
  populated `INITIAL_RESUME` for a named individual — real-looking name, email, phone,
  LinkedIn/GitHub, employment history, CGPA — that was never replaced by the signed-in
  user's data. Every candidate opened the builder prefilled with a stranger's details and
  "Export PDF" would produce that as their resume. Now starts empty and seeds from the
  user's own profile.
- **`WARNING`-level accessibility failure.** `--color-amber-pending #c98a2c` measured
  **2.93:1 on white — fails WCAG AA** while encoding "pending" status. Darkened to
  `#96661c` (4.98:1).
- **Frontend dropped `confidence`.** `TalentScoreResponse` was missing the field the backend
  has always returned, so the data that exists specifically to stop a recruiter reading a
  sparse profile as a weak candidate never reached the UI.
- **Broken navigation for two roles.** Recruiter `/recruiter/interviews` 404'd and organizer
  "My Hackathons" bounced to `/home`; route groups contribute nothing to the URL, so both
  paths could never resolve. Built the two missing pages, which also unlocked two complete
  backends that had no UI (`fetchMyHackathons` had no caller at all).
- **Errors swallowed as empty states.** `(candidate)/interviews` caught every fetch failure
  and rendered "no open interviews", so a candidate with invitations waiting saw an empty
  page and no retry.
- **Rankings weights disagreed with the code.** The UI described `0.40/0.30/0.20/0.10` while
  the request sent `0.25` each.
- **Scores styled as verdicts.** Match percentage, ATS readiness and submission score were
  hardcoded `text-success`, so a 21% match rendered in the same affirmative green as 94%.

Also removed internal leakage that was reaching users: architecture doc paths
(`doc/SRS/00-Master-Architecture...`), requirement IDs (`FR-7a`, `FR-4.3`), raw scoring
formulas, unrendered literal `**markdown**`, an invented product name ("CVInsight Engine"),
and UUIDs used as page titles.

### Verification

- `npx tsc --noEmit`, `npx eslint src`, `npm run build` — all clean; 33 pages compile.
- `check-nav.js` — 25 nav hrefs resolved against 45 routes, all pass.
- 28 routes probed live, all 200, no runtime errors in the dev log.
- **Responsive verified by measurement, not by reading classes**: a Playwright script
  loaded all 28 routes at 375 / 768 / 1280 and compared `documentElement.scrollWidth`
  against the viewport. **No horizontal overflow anywhere.** This caught three real
  breaks that source review had missed (unprefixed `grid-cols-3`/`grid-cols-2` in
  analytics, the hackathon join form, and the resume builder).

### Deliberately not converted

Two pages keep hand-rolled `useEffect` fetching, because converting them would regress
working fixes rather than improve anything:

- `(candidate)/interview/[sessionId]` — six effects carrying the media-cleanup and
  TTS-deduplication fixes from the previous pass.
- `(candidate)/profile/edit` — a sequenced load with a one-time `fullName` seed gated on
  `me` arriving, which `useAsyncResource` cannot express.

Three `dark:` variants and seven icons without `aria-hidden` remain inside vendored
`ui/*` primitives. Editing those would conflict with future `shadcn` updates for no
user-facing gain; application code is at zero.

### Test-suite collection fix (2026-08-18)

`uv run pytest -q` failed collection on a clean checkout with
`ModuleNotFoundError: No module named 'services'` across 7 test modules. Tests import
their subjects as `services.*` / `packages.*`, which resolves only with the repo root on
`sys.path`; because the project is declared virtual (`[tool.uv] package = false`), nothing
is installed into site-packages to supply it.

The suite was only ever passing for callers who happened to have the root on `PYTHONPATH`.
Fixed by adding `pythonpath = ["."]` to `[tool.pytest.ini_options]`. A bare
`uv run pytest -q` now collects and passes 82 tests with no environment setup, which is
what the verification steps in the plan and this log assume.

## Security & consistency audit (2026-08-18)

Triggered by a cross-agent change set (onboarding revamp, handle enforcement, role
centralization). Everything below was **confirmed by exploiting it against the running
API**, then re-tested after the fix — not inferred from reading code.

### 1. Reserved-handle lists had drifted apart (privilege-adjacent)

`RESERVED_USERNAMES` (frontend) held 34 names; `_RESERVED_USERNAMES` (backend) held 28.
Six were client-only: `home`, `admin`, `recruiter`, `organizer`, `judge`, `settings`.

The client is not a security boundary. `POST /auth/signup` with `username="admin"`
returned **201**, so a candidate could claim `/admin` as their public portfolio handle —
`/[username]` is a sibling route of the real ones, so the profile both shadows a route and
reads as an official page.

Fixed by adding the six to the backend set. Both lists now agree at 34, and
`services/api/tests/test_reserved_usernames.py` parses `constants.ts` and fails if they
ever diverge again — in *either* direction, plus a pattern-equality check. The test was
verified to actually fail by temporarily removing one name.

### 2. Deactivation revoked nothing (authorization)

`is_active` was checked only in the login handler. Tokens live for
`jwt_expiry_seconds` = **604800s (7 days)** and were never re-checked, so deactivating an
account left the user with full access until their token expired on its own. Verified:
flipped `is_active=false` in the database, and `/me` still returned 200.

Fixed in `get_current_user` (`services/api/core/rbac.py`), which every protected route
resolves through. `GET /me` needed the check repeated because it depends on
`get_auth_context` directly — a deliberate bypass so it can report `onboarding_required`
for a user with no profile row. It was the only such bypass in the codebase.

After: `/me` and `/candidates/me` both 403 while deactivated, 200 again once restored.

### 3. `POST /hackathons/{id}/webhook` accepted unauthenticated writes

No auth, no signature, no shared secret. Anyone who knew a hackathon ID could create
teams; because `_upsert_team` matches on team name, a request could also **overwrite an
existing team's members**. Verified with a bare `curl` — HTTP 201, row created, then
removed.

It cannot use `require_role` (the caller is another service, not a user), so it now
requires an `X-Webhook-Secret` header compared with `secrets.compare_digest` — a
short-circuiting `!=` would leak the secret a byte at a time. An unset secret **disables**
the endpoint (503) rather than leaving it open, so no deployment is silently exposed.
Documented in `.env.example`.

After: no secret → 401, wrong secret → 401, correct secret → 201.

### What was verified as already correct

- Role comes from the **database**, never from JWT claims — a forged or stale token cannot
  escalate.
- A candidate token gets 403 on all of `/admin/*`, `/analytics/hiring-funnel`,
  `/judging/queue`, `/hackathons`, `/interview-definitions/mine`.
- Self-promotion via `PATCH /candidates/me` with `{"role":"admin"}` is ignored; the role
  stays `candidate`.
- Reserved handles are rejected on the **update** path too, not just signup.

### Known gap, not fixed here

Public routes render no `<main>` landmark (only `WorkspaceShell` provides one), so
`getByRole("main")` finds nothing on `/sign-in`. Screen-reader users get no main-content
skip target on public pages. Out of scope for this pass; the e2e specs scope by `form`
instead.
