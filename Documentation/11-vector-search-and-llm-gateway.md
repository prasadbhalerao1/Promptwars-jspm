# Vector Search & LLM Gateway (Shared AI Infrastructure)

## What this infrastructure does

The "AI plumbing" every feature builds on: Qdrant vector database for semantic search,
`sentence-transformers` embeddings (`BAAI/bge-large-en-v1.5`), and a multi-provider LLM
gateway abstracting Anthropic/OpenAI/Groq/Gemini/OpenAI-compatible endpoints behind one
interface. The embedder is cached via a `functools.lru_cache` singleton in
`services/agents/recruitment/tools/embeddings.py:46-54`; a second, separate embeddings
module exists at `services/agents/ppt_analyzer/tools/embeddings.py` for pitch-deck slide
text, since that module's embedding lifecycle (per-analysis, not persisted long-term) is
different enough from the recruitment/candidate embeddings to warrant its own loader rather
than sharing state with the recruitment singleton.

## The Qdrant vector database layer

Every Qdrant collection:

| Collection | Purpose | Stored | Indexed |
|---|---|---|---|
| `candidate_skills` | Job matching candidate pool | Candidate skill vectors | skill embeddings |
| `job_skills` | Job matching job requirements | Job skill vectors | skill embeddings |
| `novelty_corpus` | Hackathon solution uniqueness | Prior hackathon solution summaries | novelty embeddings |
| `plagiarism_decks` | Pitch deck plagiarism detection | Deck slide text vectors | deck embeddings |
| `plagiarism_code` | Code submission plagiarism | Code token fingerprints | code embeddings |
| `skill_taxonomy` | Career guidance role requirements | Role → skills vectors | role embeddings |

**Key Finding**: The "bare skill-name vs described-skill embedding" discovery.

```
Problem: Bare skill embeddings are ambiguous
    "Vue.js" embed:  [0.12, 0.34, ...]
    "React" embed:   [0.11, 0.35, ...]
    "Photoshop" embed: [0.13, 0.33, ...]
    
    Cosine similarity (bare):
    - Vue.js ↔ React:     0.65
    - Photoshop ↔ React:  0.64  ← Same! They're indistinguishable!

Solution: Add one-sentence descriptions to each skill
    "Vue.js: a progressive JavaScript frontend framework..."
    "React: a JavaScript library for building UIs..."
    "Photoshop: raster graphics editing software..."
    
    Cosine similarity (described):
    - Vue.js ↔ React:     0.89  ← Good! Related frameworks
    - Photoshop ↔ React:  0.66  ← Good! Clearly unrelated
```

**Where this is used**:
- Job matching: `best_skill_similarity()` compares described skills
- Skill gap analysis: same embeddings for role requirements
- Hard-filter fallback: when exact skill match fails

## The multi-provider LLM gateway

```
services/api/core/llm.py — get_llm_client()

Provider Configuration (in .env):
    LLM_PROVIDER=anthropic                        # anthropic | openai | groq | gemini | openai_compatible
    LLM_MODEL_FAST=claude-haiku-4-5-20251001       # Fast tier (low-latency responses)
    LLM_MODEL_JUDGMENT=claude-sonnet-4-6           # Judgment tier (high-quality reasoning)
```

Anthropic is the default and production provider (`config.py:34`,
`llm_provider: str = "anthropic"`). Groq is supported and used as a cheaper test-time
provider for CI/local dev — the gateway's own docstring says so directly — not as the
production intent; swapping providers is a config change, not a code change, because every
provider is normalized behind the same `get_llm_client()` interface.

Example usage (real model strings, not placeholders):

```python
from services.api.core.llm import get_llm_client

client = get_llm_client()
result = await client.generate_structured(
    prompt="Grade this code: ...",
    model=settings.llm_model_judgment,   # "claude-sonnet-4-6"
    temperature=0,
    max_tokens=1000,
)
```

**Why split fast/judgment tiers?**

```
Fast-tier use (low-latency, lower-cost):
    - Resume generation drafts
    - Interview turn evaluation (must feel responsive)
    - Query understanding (just parse user intent)
    Cost: ~$0.001 per call

Judgment-tier use (higher quality):
    - Code review (nuanced feedback)
    - Pitch deck rubric scoring (important decision)
    - Final hiring recommendation
    Cost: ~$0.01 per call

Why separate? Budget constraints + UX.
    - A slow resume generation (30sec) is acceptable
    - A slow turn-by-turn interview evaluation (30sec per turn) is not
    - Judgment-tier is 3-5x slower; reserve for decisions
```

## LLM reliability: typed errors, retry, timeouts, validation

The gateway originally collapsed every failure into a single `LLMUnavailable` with no
retry, no timeout and no validation of what came back. Callers therefore could not tell a
missing API key from an exhausted billing balance from "slow down", and the client retried
all of them identically — including the two that can never succeed by waiting.

**Typed error taxonomy.** All subclass `LLMUnavailable`, so pre-existing
`except LLMUnavailable` handlers keep working unchanged:

| Exception | Retryable | Meaning |
|---|---|---|
| `LLMNotConfigured` | no | Missing/invalid API key — a deployment problem, not a transient one |
| `LLMQuotaExhausted` | **no** | Billing/credit exhausted. Retrying spends time on a guaranteed failure |
| `LLMRateLimited` | yes | Provider 429; carries `retry_after` when the provider supplies one |
| `LLMTimeout` | yes | Call exceeded `LLM_TIMEOUT_SECONDS` |
| `LLMOverloaded` | yes | Provider 503/529 |
| `LLMInvalidOutput` | yes | Response failed schema validation |

`_classify_provider_error()` maps each provider's SDK exceptions onto these in one place.
Quota markers (`insufficient_quota`, `exceeded your current quota`, `billing`,
`credit balance`) are checked **first**, because quota exhaustion arrives as a 429 that is
otherwise indistinguishable from an ordinary rate limit — and the two need opposite
handling.

**Retry.** `_call_with_retry()` wraps both `generate_completion` and
`generate_structured`: exponential backoff with jitter, bounded by `LLM_MAX_RETRIES`,
honouring the provider's `Retry-After`. Only retryable classes are retried.

**Output validation** — the highest-impact fix. `float(result["score"])` was written
straight to DB columns at six sites, so a model answering `8.5` on a 0–100 scale persisted
as 8.5/100 and fed recruiter matching, salary prediction and hackathon rankings.

- `validated_score(raw)` clamps to `[0,100]` and returns `None` for null/bool/non-numeric/
  NaN/inf rather than raising out of a graph node.
- `validate_structured(result, parameters)` checks required keys and JSON types before the
  result is returned, raising `LLMInvalidOutput` (which triggers one retry).

**How this surfaces to the user.** `_LLM_ERROR_RESPONSES` in `services/api/main.py` maps
each type to a status, a stable `code`, and an explicit `retryable` flag:

| Exception | HTTP | `code` | `retryable` |
|---|---|---|---|
| `LLMQuotaExhausted` | 402 | `LLM_QUOTA_EXHAUSTED` | false |
| `LLMRateLimited` | 429 | `LLM_RATE_LIMITED` | true |
| `LLMNotConfigured` | 503 | `LLM_NOT_CONFIGURED` | false |
| `LLMTimeout` | 504 | `LLM_TIMEOUT` | true |
| `LLMInvalidOutput`, `LLMUnavailable` | 503 | `LLM_UNAVAILABLE` | true |

The handler walks `type(exc).__mro__`, so a future subclass inherits its parent's treatment
rather than falling through to a generic 500. On the frontend, `apps/web/src/lib/errors.ts`
reads `code` and `retryable` and refuses to auto-retry the two that cannot succeed — a
user staring at a spinner during four backoff attempts against a billing failure learns
nothing, while the admin who could actually fix it is never told.

## The shared scoring aggregation helper

```
services/agents/common/scoring.py::weighted_renormalized_mean()

Problem: 5 separate implementations of "weighted sum with cold-start"
    - Talent Score (candidate_intelligence/tools/aggregate.py)
    - Pitch Score (hackathon/tools/ranking.py)
    - Job Matching (recruitment/tools/matching.py)
    - Coding Ability (assessment/tools/coding_score.py)
    - Mechanical Scores (candidate_intelligence/tools/mechanical_scores.py)

All 5 did the same thing:
    if missing_term: skip it
    renormalize remaining weights to sum to 1.0
    return weighted average

Solution: One function, called by all 5
    weighted_renormalized_mean([
        (0.40, judge_score or None),
        (0.30, pitch_score or None),
        (0.20, repo_score or None),
        (0.10, novelty_score or None),
    ])
    
    Returns: numeric score (never 0 or "unknown" as fallback)
    Drops missing terms, renormalizes, averages

Verified: numerically identical to pre-refactor implementations
```

## Failure modes and graceful degradation

Qdrant availability affects different callers differently, by design — some signals are
load-bearing enough that a missing vector DB should fail loudly, others are one input among
several and should just degrade:

**Hard failures (raised as `QdrantUnavailable`, propagates to the caller as HTTP 503):**
- Recruitment matching — without `semantic_similarity`, candidates can't be ranked at all,
  so the endpoint fails explicitly rather than silently returning an unranked or
  wrongly-ranked list.
- Skill gap analysis — without the skill-taxonomy collection, there's nothing to compare a
  candidate's skills against, so career guidance fails explicitly rather than guessing.

**Soft failures (caught, degrade to `None`, cold-start-safe):**
- Innovation novelty (Talent Score) — one signal among several; if Qdrant is unreachable the
  sub-score falls back to whatever else is available (or `None`, dropped by
  `weighted_renormalized_mean`) rather than blocking the whole scoring pipeline.
- Plagiarism detection (PPT Analyzer / fraud) — one corroborating signal; falls back to
  text-fingerprint-only comparison.
- Project relevance (job matching sub-term) — returns `None` if a candidate has no seeded
  project embeddings; renormalized away rather than scored as zero.

The pattern in code: `get_qdrant_client(raise_on_unavailable=False)` returns `None` instead
of raising for every soft-failure call site, so each caller decides its own failure
posture instead of the client forcing one globally.

## Performance characteristics

| Operation | Typical latency | Notes |
|---|---|---|
| `embed_texts()` (1 item) | ~1ms | Cached model, CPU inference |
| `search()` (1 query) | ~10ms | HNSW index, loopback round trip |
| `search_batch()` (100 queries) | ~50ms | One round trip instead of 100 sequential ones |
| `upsert()` (1 point) | ~20ms | Immediate index update |
| Skill centroid (10 skills) | ~5ms | NumPy mean, no Qdrant call involved |

The batching optimization matters concretely: scoring semantic relevance for 100 candidates
one-by-one against a job posting is ~100 sequential ~10ms round trips (≈1s); batching the
same 100 candidates into one `search_batch()` call is ≈50ms — a ~20x difference that matters
when it's in the request path of a recruiter loading a matches page.

## Qdrant configuration notes

- Qdrant runs as a local Docker container (`trace_qdrant`) on `http://localhost:6333`,
  read from `QDRANT_URL` in `.env`. No API key is needed; `QDRANT_API_KEY` is blank.
- Collections are auto-created on first upsert; vector size is inferred from the first point
  written, and distance metric is COSINE across every collection (not L2/Manhattan).
- Point IDs are deterministic (`uuid5(namespace, seed_string)`, e.g. `uuid5(..., f"job:{job_id}")`)
  specifically so re-running a seed/backfill script is idempotent — re-seeding never
  duplicates points.
- Qdrant queries use server-side payload filters (e.g. filtering by `candidate_id`) rather
  than fetching everything and filtering in Python — the HNSW index skips non-matching
  points server-side, which is materially faster than a fetch-all-then-filter approach once
  a collection has any real size.

## Key design decisions

1. **Single canonical Qdrant client** (services/api/core/qdrant.py):
   - Was: 4 separate client constructors in different modules
   - Now: One `get_qdrant_client(raise_on_unavailable=True)`
   - Supports both failure modes (hard exception or soft None)

2. **Embedding model is cached singleton**:
   - Sentence transformer loaded ONCE at startup via `@functools.lru_cache`
   - NOT reloaded per request (that was a 2-3sec performance bug)
   - All embeddings use same model (reproducible)

3. **Skill descriptions are hand-maintained, not auto-generated**:
   - ~45 curated skills with descriptions
   - New skills fall back to bare name (degrades gracefully)
   - Not generated via LLM (consistency + cost)
   - Now stored in the `skill_descriptions` table rather than a Python dict, so curating
     them is an operational action instead of a code change + redeploy. Seeded by
     `scripts/seed_db.py`; falls back to the built-in seed data (with a warning) when the
     DB is unreachable, so agents still run on a cold start.

4. **Weights are config but validated**:
   - Hackathon weights configurable via `scoring_config` (organizer-editable JSONB)
   - Malformed input (partial keys, unknown keys, negative, non-numeric, all-zero) falls
     back to defaults and renormalizes rather than raising. A partial config previously
     raised `KeyError` inside `compute_composite_score`, which failed finalization for the
     *entire event* — every team, not just the affected component.
   - The `breakdown` returned alongside the score reports whether renormalization occurred,
     so the adjustment is inspectable rather than silent.

## Limitations

- Embedding model is frozen (sentence-transformers model, trained offline)
- Qdrant collections aren't versioned (schema changes are risky)
- Multi-provider support adds complexity (not all providers support structured output equally)
- Cold-start: Qdrant collections start empty (plagiarism corpus, novelty corpus build over time)

## Where this lives

| Component | File |
|---|---|
| Qdrant client helper | `services/api/core/qdrant.py` |
| LLM gateway | `services/api/core/llm.py` |
| Embedding model loader | `services/agents/recruitment/tools/embeddings.py::get_embedder()` |
| Skill descriptions | `skill_descriptions` table, read via `services/agents/catalogs.py` |
| Shared scoring helper | `services/agents/common/scoring.py` |
| Role taxonomy | `role_skill_requirements` table, read via `services/agents/catalogs.py` |
| LLM error taxonomy | `services/api/core/llm.py` (raised), `services/api/main.py::_LLM_ERROR_RESPONSES` (mapped to HTTP) |
| Frontend error classification | `apps/web/src/lib/errors.ts` |
| Config: LLM provider | `services/api/core/config.py::LLM_PROVIDER, LLM_MODEL_*` |
| Config: Qdrant endpoint | `services/api/core/config.py::QDRANT_URL` |
