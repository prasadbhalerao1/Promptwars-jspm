# AI Talent Profile Engine & Talent Score

## What it does

A candidate connects GitHub, uploads a resume, and optionally uploads a certificate. The system pulls those three sources together into one profile, cross-checks them against each other, and computes a "Talent Score" — nine sub-scores (coding ability, problem solving, project quality, innovation, technical consistency, community participation, leadership, open-source contributions, hackathon performance) plus a single overall number — from real evidence rather than from what the candidate typed into a form. The score comes with a confidence rating so a recruiter can tell "this candidate scored low" apart from "this candidate hasn't given us enough to score yet."

## The problem it solves

A resume is a self-reported, unverifiable claim. "5 years of Python, expert in system design" costs nothing to write and nothing to fake. The traditional hiring funnel has no cheap way to check it before a human interviewer's time gets spent, so screening either over-trusts the resume or falls back on brand-name signals (which school, which company) that correlate weakly with actual ability.

This system's answer is to stop trusting any single source and instead triangulate. The `profile_merge` node (`services/agents/candidate_intelligence/nodes/profile_merge.py`) explicitly checks resume claims against GitHub activity: if a resume claims 2+ years of experience but the candidate's GitHub commit history shows less than half that in active weeks, it's flagged as an `experience_mismatch` conflict rather than silently accepted. The scoring layer goes further — most sub-scores are computed from things a candidate cannot simply assert (actual commit counts, actual cyclomatic complexity of sampled source files, actual assessment results, actual PR review counts), and where an LLM is used for judgment (project quality, innovation), it's one signal among several rather than the sole source of truth. The point isn't to catch fraud after the fact; it's to make the score itself hard to fabricate by construction.

## How it works (the real walkthrough)

### Trigger

Ingestion happens on three routes in `services/api/modules/candidates/router.py`:
- `POST /candidates/me/ingest/resume` — resume upload
- `POST /candidates/me/ingest/certificate` — certificate upload
- `GET /candidates/github/oauth/callback` — GitHub OAuth connect

Each of these sets `ingestion_status = "processing"` and schedules `_run_ingestion_background` as a FastAPI `BackgroundTask` rather than awaiting it inline. The reasoning is in the code's own comment: `fetch_github_analysis` alone makes dozens of sequential blocking PyGithub HTTP calls, plus there are LLM round-trips for resume extraction and judgment scoring — synchronously awaiting all of that in the request handler would stall the uploading candidate's own connection and (because Python's event loop is single-threaded) degrade every other concurrent request too. The frontend polls `GET /candidates/me/ingestion-status` until the status flips to `done` or `failed`.

### The graph

`services/agents/candidate_intelligence/graph.py` wires up a LangGraph `StateGraph` over `CandidateProfileState` (`services/agents/candidate_intelligence/state.py`):

```
resume_parser   --\
github_analysis --+--> profile_merge --> talent_scoring --> badge_assignment
certificate_ocr --/
```

The first three nodes fan out from `START` in parallel (same superstep) because they're independent data pulls with no dependency on each other. Each is a no-op if its input isn't present in state (e.g. `resume_parser.run` returns `{}` immediately if `raw_resume_bytes` is empty) — this is what lets ingestion work standalone for GitHub-only or resume-only updates, not just full onboarding.

**`resume_parser`** (`nodes/resume_parser.py`) — extracts raw text mechanically (`pdfplumber` for PDF, `python-docx` for Word) with no network call, then sends that text to an LLM (`extract_resume_fields` in `tools/resume.py`) with a structured-output schema to pull out headline, skills, experience, and education. If the LLM call fails (`LLMUnavailable`, e.g. no API key configured), it doesn't fabricate a profile — it returns a conflict entry (`resume_extraction_unavailable: ...`) and the ingestion continues without resume data.

**`github_analysis`** (`nodes/github_analysis.py` → `tools/github.py`) — fully deterministic, no LLM. Pulls up to 15 most-recently-pushed repos via PyGithub, per-repo language breakdown, commit/PR/issue counts, weekly commit activity (52 weeks, both as a plain count list and as `(week_date, count)` pairs so recency weighting can use real dates instead of assuming index-N means "N weeks ago"), external merged PRs (PRs the candidate authored into repos they don't own — a genuine signal of open-source contribution rather than just personal-project activity), and PR review counts (a leadership proxy). It uses the candidate's own OAuth token, never a shared server-side token, so rate limits are the candidate's own.

**`certificate_ocr`** (`nodes/certificate_ocr.py` → `tools/certificate.py`) — Tesseract OCR extracts title, issue date, and credential ID via regex over the recognized text. If OCR confidence is below 0.5, it adds a `certificate_low_ocr_confidence` conflict for manual review. No LLM-vision fallback is wired up yet (noted directly in the code as a known follow-up).

**`profile_merge`** (`nodes/profile_merge.py`) — deterministic, rule-based, explicitly not an LLM call ("no LLM call needed for this node in this slice" — the doc's own note says an LLM conflict-summary pass is a future refinement). It builds the merged profile from resume fields and detects the resume-vs-GitHub experience mismatch described above. It also accumulates `conflicts` using LangGraph's `operator.add` reducer channel, because three parallel nodes (`resume_parser`, `certificate_ocr`, `profile_merge`) can each contribute conflict entries in the same superstep, and LangGraph's default channel semantics reject more than one write per step unless a reducer is declared.

**`talent_scoring`** (`nodes/talent_scoring.py`) — the core of the Talent Score. This is where all 7 sub-scores get computed. Population data (needed for percentile normalization) and the candidate's latest assessment score are fetched by the router *before* the graph runs and injected into state — the node itself never touches the database. Per sub-score:

- **coding_ability** (`tools/mechanical_scores.py::coding_ability`) — weighted blend of three terms: 0.25 × language/commit-volume score (percentile-normalized total commit count, log-scaled fallback below population threshold), 0.35 × code-quality score (see project_quality below — shared, not recomputed), 0.40 × assessment-score percentile (winsorized 5th–95th against the population). Assessments get the highest weight because they're explicitly called out as the hardest signal to game.
- **problem_solving** (`mechanical_scores.py::problem_solving`) — the candidate's latest assessment score, winsorized then percentile-ranked against the candidate population. `None` if there are no submissions yet.
- **technical_consistency** (`tools/github.py::commit_consistency_score`) — not a volume metric but a *regularity* metric: coefficient of variation (stdev/mean) of recency-weighted weekly commit counts, inverted to 0–100 (low variance = steady cadence = high score). Requires at least 4 active weeks or returns `None`. On top of the CV base score it applies a staleness penalty (recency-decayed weight on the most recent active week, inverted into a 0–20 point deduction) and a sustained-activity bonus (+0–10 points if the candidate was active in more than 75% of the 52-week window) — so a candidate who was consistent a year ago and has since gone quiet scores lower than one who is consistent right now.
- **community_participation** (`mechanical_scores.py::community_participation`) — 0.6 × percentile-normalized total GitHub stars + up to 40 points from external merged PRs (capped at 8 points each, i.e. 5+ external PRs maxes this term out).
- **leadership** (`mechanical_scores.py::leadership`) — a raw score from owned/maintained repo count and PR-review count, then percentile-normalized against the population (not just capped at a fixed constant). The code's own comment flags this as "the most gameable signal," mitigated (not solved) by population normalization instead of relying purely on low weight.
- **project_quality** (`tools/judgment_scores.py::project_quality`) — a mechanical component (`sample_complexity`: pulls up to 3 Python repos, runs `radon`'s cyclomatic-complexity analyzer on a sampled source file, applies a penalty curve — flat 100 up to complexity 5, linear decay to complexity 15, steeper decay beyond that) blended 0.6/0.4 with an LLM judgment call (Sonnet rates README/architecture quality from repo summaries, via `generate_structured`). If either component is unavailable, the other one is used alone; if both are unavailable, the sub-score is `None`.
- **innovation** (`judgment_scores.py::innovation`) — a novelty score from vector similarity: the candidate's repo descriptions get embedded (shared `SentenceTransformer` singleton with the recruitment matching code) and compared against a Qdrant collection of other candidates' project embeddings (`CANDIDATE_PROJECT_EMBEDDINGS_COLLECTION`) — lower average cosine similarity to the existing corpus scores higher (calculated as `100 * (1 - avg_similarity)`). This is blended 50/50 with an LLM judgment call, then the whole thing is multiplied by a recency-decay factor (365-day half-life on the most recently pushed repo) so an idea that was novel two years ago but has been abandoned since doesn't outscore active work. The candidate's own repos also get upserted into the same Qdrant collection afterward, so the corpus grows as more candidates get scored — an explicit cold-start/bootstrapping mechanism.

- **open_source_contributions** — merged PRs into repos the candidate doesn't own, counted and percentile-ranked against the population, with a bonus for spread across multiple distinct projects rather than all activity concentrated on one repo (a candidate with 6 merged PRs across 4 different projects scores higher than 6 merged PRs on a single one).
- **hackathon_performance** — a blend of verified results (hackathons run on this platform: win / top-5 / finalist / participant, each a fixed weight) and self-reported external hackathons (included but weighted lower than verified results, since they're unverifiable claims).

Two of the nine sub-scores route to an LLM (project_quality, innovation) because the doc's own model-routing table classifies them as genuinely subjective judgment calls; the other seven are pure rules. This split is enforced in code, not just convention — `mechanical_scores.py`'s module docstring says outright "rules only, no LLM."

`compute_overall` (`tools/aggregate.py`) then combines the nine sub-scores using fixed weights (coding_ability 0.16, problem_solving 0.16, project_quality 0.12, innovation 0.12, technical_consistency 0.08, community_participation 0.08, leadership 0.08, open_source_contributions 0.10, hackathon_performance 0.10) via `weighted_renormalized_mean` (`services/agents/common/scoring.py`) — explained in the design-decisions section below. `compute_confidence` computes an Evidence Confidence Score: `available_signals / expected_signals`, i.e. what fraction of the 9 sub-scores actually resolved to a number rather than `None`.

**`badge_assignment`** (`nodes/badge_assignment.py`) — rules only. A skill claimed on the resume gets a corroborated badge only if the same skill/language also shows up in the candidate's actual GitHub repo languages. This is small but tells the same story as the rest of the system: self-reported claims alone earn nothing; they need a second, independently-sourced signal.

### Persistence

Back in the router (`_run_ingestion_and_persist`), the merged profile overwrites the corresponding `CandidateProfile` columns (headline, skills, experience, education, `merged_conflicts`), GitHub raw stats are merged (not replaced) into the `github_stats` JSONB column, each fetched repo becomes a `GithubSnapshot` row, and if a certificate was processed it becomes an unverified `Certification` row. If sub-scores were computed, a new `TalentScore` row is inserted — note this is **append-only history**, not an update-in-place: `computed_at` plus an index on `(candidate_id, computed_at)` lets the frontend show a score trend line over time. Alongside it, an `AgentRun` row logs the scoring agent's inputs/outputs and the Langfuse trace ID for explainability/auditing. Any new badges are inserted (de-duplicated against existing skill names first).

### Frontend

`apps/web/src/components/CandidateDashboard.tsx` fetches everything with one batched call (`fetchDashboard`) hitting `GET /candidates/me/dashboard`, which server-side already joins profile + latest score + score history + badges + GitHub summary into one payload — deliberately consolidated (per the component's own comment) so there's one round trip instead of three separate ones, while UI sections (`profileResource`, `githubResource`, `talentResource`) still expose independent loading/error states so one section's absence doesn't blank the whole page. The Talent Score card shows the overall number and a radar chart across the 7 sub-scores (`ScoreRadarChart`), a trend line across history (`ScoreTrendLine`), and an `EvidenceReceipt` component that presumably surfaces the rationale/evidence strings each sub-score returns (so a recruiter/candidate can see *why* a score is what it is, not just the number).

## Key design decisions and why

**Cold-start renormalization instead of penalizing missing data.** If a candidate hasn't connected LeetCode yet, `problem_solving` is `None`, not `0`. `compute_overall` drops any `None` sub-score entirely and renormalizes the remaining weights to sum back to 1.0 (`weighted_renormalized_mean` in `services/agents/common/scoring.py`), so a candidate who has only connected GitHub is scored purely on what GitHub actually shows, not dragged down by an assumed zero on dimensions they simply haven't provided evidence for yet. The same pattern is reused (per that file's own docstring) across Talent Score, Pitch Score, Hackathon Ranking, and Job Matching — it was found to be byte-identical logic in several places and was pulled into one shared function rather than four subtly-diverging copies, while still letting each caller keep its own rounding/edge-case behavior (some return `None` on total failure, one returns `0.0`) so consolidating it didn't silently change any of those scoring formulas right before a demo.

**Evidence Confidence Score as a first-class, separate number from the overall score.** Rather than trying to fold "how much data do we actually have" into the 0–100 number itself (which would conflate "this candidate is weak" with "this candidate is under-profiled"), confidence is computed and stored separately (`available_signals / expected_signals`) and surfaced to the API response. The explicit intent, stated in the code, is that a score is never withheld below some confidence threshold — it's flagged for the recruiter's judgment, not hidden.

**Percentile normalization against the live candidate population instead of fixed constants.** Several sub-scores originally would have used something like `100 * log1p(stars) / log1p(100)` — simple, but an attacker can read that formula and know exactly what number of stars saturates it. `tools/normalization.py::percentile_normalize` instead ranks a candidate's raw value against everyone else's actual values, which is much harder to game because no single candidate controls what the rest of the population looks like, and it adapts automatically as the pool grows or shifts. The tradeoff, handled explicitly: below `min_population` (30, or 10 for assessment-based percentiles) a percentile is statistically meaningless — a handful of early candidates could swing the whole distribution — so the code falls back to the old fixed-constant formula until there's a real population to rank against.

**Nodes stay DB-free; the router owns all database access.** Every scoring/analysis node docstring repeats a version of the same line: population data, assessment scores, and course catalogs are fetched by the router (which owns the DB session) and injected into graph state, not queried from inside a node. This keeps the LangGraph nodes pure functions of their input state, which is why the test suite (`tests/test_mechanical_scores.py`, `tests/test_aggregate.py`, `tests/test_normalization.py`) can unit-test scoring logic without spinning up a database or mocking a session.

**Mixed LLM/mechanical sub-scores degrade gracefully, never fabricate.** `project_quality` and `innovation` each have a mechanical half (complexity analysis; embedding similarity) and an LLM-judgment half. If the LLM call fails — `LLMUnavailable`, e.g. missing API key — the sub-score falls back to whichever half still succeeded, and only becomes `None` if both fail. Nothing here returns a plausible-looking placeholder number; a `None` propagates all the way to the renormalization step honestly.

**Fully parallel ingestion fan-out with an explicit reducer for shared state.** `resume_parser`, `github_analysis`, and `certificate_ocr` all run in the same LangGraph superstep because they don't depend on each other and this is what keeps ingestion under the project's own <30s target when a candidate connects everything at once. The catch, called out directly in the code, is that LangGraph's default state channels only accept one write per step — three parallel nodes writing to the same `conflicts` list would normally throw "can receive only one value per step." The fix is declaring `conflicts: Annotated[list[str], operator.add]` so LangGraph concatenates concurrent partial writes instead of colliding, with the added constraint (documented in each node) that a node must return *only its own new entries*, never the accumulated list, since the reducer does the accumulating.

## What could go wrong / current limitations

**The "hardest to game" scores still have soft spots.** Leadership is explicitly called out in its own code comment as the most gameable sub-score — owning a lot of solo repos and reviewing a few PRs on them is cheap to manufacture, and percentile normalization only makes gaming *relatively* harder (everyone's baseline moves together), it doesn't make it impossible. Community participation's external-PR term is also fairly easy to inflate with low-effort drive-by PRs against permissive repos.

**Percentile normalization is only as good as the population.** Below `min_population` (30, or 10 for assessment scores) the system falls back to a fixed formula — which is exactly the gameable case it was designed to avoid. Early in the product's life, or for any niche population slice, most candidates are effectively scored on the old, easier-to-reverse-engineer curve without that being obviously visible to a viewer of the dashboard.

**GitHub is a proxy for a proxy.** Everything downstream of `github_analysis` assumes a candidate's public GitHub activity is representative of their real engineering ability. It systematically undercounts candidates who do most of their real work in private repos, at a job, or on a platform other than GitHub (GitLab, Bitbucket) — the pipeline has no signal for them at all beyond resume/assessment data, and `coding_ability`/`technical_consistency` can silently be `None` or low for people who are actually strong engineers.

**The LLM judgment components are single-shot and unverified against each other.** `project_quality` and `innovation` each make one Sonnet call per candidate with no cross-check, self-consistency sampling, or calibration against a human-labeled set. If asked "how do you know this score is meaningful," the honest answer is: there's a stated rationale returned with every sub-score for transparency, and the LLM's numeric output is capped in influence (40% or 50% weight, blended with a mechanical component), but there's no evaluation harness in this codebase demonstrating the LLM judgments correlate with actual code quality or actual innovation — that would be the natural next thing a rigorous reviewer should ask to see.

**Certificate OCR is genuinely weak.** It's a Tesseract baseline with regex-based date/credential-ID extraction and a "longest line is probably the title" heuristic. It flags low-confidence extractions (<0.5) for manual review but does nothing to verify the certificate is authentic — `verification_status` defaults to `unverified` and stays that way unless something else in the system (not shown in this module) verifies it.

**Ingestion runs as an unmanaged background task, not a durable job queue.** `_run_ingestion_background` is a FastAPI `BackgroundTask`, which lives only as long as the server process. If the process restarts mid-ingestion, the candidate's `ingestion_status` is stuck at `"processing"` indefinitely with no automatic retry or timeout — the frontend would poll forever.

**No re-scoring cadence beyond manual re-connect.** The module docstring for `graph.py` itself notes that a weekly automatic refresh is a "Phase-1 follow-up" — today, a Talent Score only updates when the candidate re-uploads a resume, reconnects GitHub, or uploads a new certificate. A candidate who was scored once and never returns has a score that silently goes stale.

## Open-source contributions and hackathon performance (the two newer sub-scores)

The original seven-dimension score under-weighted two signals the platform itself is well
positioned to observe: activity a candidate contributes to *other* people's projects, and
track record in the platform's own hackathon events. Two sub-scores were added to close
that gap, and all nine weights were rebalanced so the total still sums to 1.0:

| Sub-score | Weight (old → new) |
|---|---|
| coding_ability | 0.20 → 0.16 |
| problem_solving | 0.20 → 0.16 |
| project_quality | 0.15 → 0.12 |
| innovation | 0.15 → 0.12 |
| technical_consistency | 0.10 → 0.08 |
| community_participation | 0.10 → 0.08 |
| leadership | 0.10 → 0.08 |
| open_source_contributions | — → 0.10 (new) |
| hackathon_performance | — → 0.10 (new) |

**Open Source Contributions** measures how active a candidate is in the wider open-source
community, not just on their own repos — merged pull requests into projects they don't own,
counted and percentile-ranked against the population, with a diversity bonus for spreading
that activity across multiple projects instead of drive-by-contributing to just one. This is
a distinct signal from `community_participation`'s external-PR term (which measures *raw
count*, capped) and from `leadership` (which measures *reviewing* others' PRs, not
*submitting* them) — this sub-score is specifically about a candidate showing up and
contributing to code they don't control.

**Hackathon Performance** measures track record in time-pressured, judged competition —
something GitHub commit history alone can't capture (a strong hackathon performer under a
48-hour deadline and public judging is a meaningfully different signal than steady solo
commit cadence). It blends two tiers of evidence: **verified** results from hackathons run
on this platform (win / top-5 / finalist / participant — each has a fixed, ordered weight,
since a platform-run hackathon's outcome is data the system trusts directly), and
**self-reported** external hackathons the candidate lists themselves, included but weighted
lower precisely because they're an unverified claim, consistent with the rest of the
platform's "don't trust unverifiable self-reports at face value" posture.

Both new sub-scores follow the same cold-start rule as the original seven: no signal means
`None`, not `0`, and `weighted_renormalized_mean` drops it and rebalances the remaining
weights rather than penalizing a candidate for not having hackathon history.

## Job-contextual score adjustment

The Talent Score described above is a *general* score — "how strong is this candidate,
overall." But a 77/100 general score means something different for a backend Python role
than for a frontend React role, and the platform makes that adjustment explicit rather than
showing recruiters one undifferentiated number for every job.

When a candidate is matched against a specific job, the system computes a **skill overlap
ratio** — what fraction of the job's required skills the candidate actually has, using the
same embedding-based skill similarity used elsewhere (see
[11-vector-search-and-llm-gateway.md](11-vector-search-and-llm-gateway.md)), so a candidate
doesn't get zero credit for "PostgreSQL" against a job that asked for "SQL." A job needing
Python, SQL, and Docker where the candidate has verified Python, embedding-similar
PostgreSQL, and no Docker produces roughly a 51% overlap ratio (`1.0 + 0.54 + 0.0` averaged
over 3 required skills).

That ratio then scales the *technical* sub-scores — coding_ability, problem_solving,
project_quality, and innovation — down toward the candidate's actual fit for this specific
stack (project_quality and innovation are scaled slightly more conservatively, at
`overlap × 0.8`, since they're less stack-specific to begin with). The *non-technical*
sub-scores — leadership, community_participation — are left unchanged, on the reasoning that
being a good collaborator or maintainer is valuable regardless of which tech stack a
specific job happens to need. The adjusted sub-scores are then re-combined with the same
weighted-renormalized-mean helper to produce a job-specific score, shown to recruiters
alongside (not instead of) the candidate's general score, with the skill-overlap ratio and
which sub-scores were adjusted shown explicitly — so a recruiter sees *why* a strong general
candidate might show a lower number for this particular req, rather than a single opaque
figure. This mechanism is documented in full, judge-facing form in
`docs/TALENT_SCORE_EXPLAINED_FOR_JUDGES.md`.

## Where this lives in the code

| Feature | Path |
|---|---|
| API endpoints (ingest, score, dashboard, badges) | `services/api/modules/candidates/router.py` |
| Graph definition (Flow A: ingestion + scoring) | `services/agents/candidate_intelligence/graph.py` |
| Graph state shape | `services/agents/candidate_intelligence/state.py` |
| Resume parsing node / tool | `services/agents/candidate_intelligence/nodes/resume_parser.py`, `tools/resume.py` |
| GitHub analysis node / tool | `services/agents/candidate_intelligence/nodes/github_analysis.py`, `tools/github.py` |
| Certificate OCR node / tool | `services/agents/candidate_intelligence/nodes/certificate_ocr.py`, `tools/certificate.py` |
| Profile merge + conflict detection | `services/agents/candidate_intelligence/nodes/profile_merge.py` |
| Talent scoring node | `services/agents/candidate_intelligence/nodes/talent_scoring.py` |
| Mechanical sub-scores (coding ability, technical consistency, community, leadership, problem solving) | `services/agents/candidate_intelligence/tools/mechanical_scores.py` |
| LLM/mixed sub-scores (project quality, innovation) | `services/agents/candidate_intelligence/tools/judgment_scores.py` |
| Score aggregation + confidence | `services/agents/candidate_intelligence/tools/aggregate.py` |
| Percentile normalization / winsorization / recency weighting | `services/agents/candidate_intelligence/tools/normalization.py` |
| Shared weighted-renormalized-mean utility | `services/agents/common/scoring.py` |
| Population queries (for percentile ranking) | `services/agents/candidate_intelligence/tools/population.py`, `tools/assessment_bridge.py` |
| Badge assignment | `services/agents/candidate_intelligence/nodes/badge_assignment.py` |
| DB models (CandidateProfile, TalentScore, Badge, GithubSnapshot, Certification) | `packages/db/models/candidate.py` |
| API response schemas | `packages/shared_schemas/candidates.py` |
| Frontend dashboard | `apps/web/src/components/CandidateDashboard.tsx` |
| Scoring unit tests | `services/agents/candidate_intelligence/tests/test_mechanical_scores.py`, `test_aggregate.py`, `test_normalization.py`, `test_github_consistency.py` |
