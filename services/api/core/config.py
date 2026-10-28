from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # True for a TLS/pooled Postgres endpoint — enables TLS and disables asyncpg's
    # server-side prepared-statement caching, which breaks against PgBouncer-style
    # transaction poolers. False (the default, and what this project runs) for the
    # local docker-compose Postgres.
    database_ssl_required: bool = False
    # SQLAlchemy async engine pool — defaults (5 + 10 overflow) were too small once
    # matching/copilot/dashboard requests run concurrently: starving the pool queues
    # requests behind each other instead of running them in parallel.
    #
    # 20 + 20 overflow is ample now that no request holds a connection across a slow AI
    # call: handlers that invoke a LangGraph/LLM pipeline wrap it in
    # `db.without_db_connection()`, returning the connection to the pool for the seconds
    # or minutes that call takes. Before that, twenty concurrent AI interviews pinned all
    # twenty connections and every other endpoint — including trivial reads — blocked for
    # up to `db_pool_timeout_seconds`. Raise these only in response to observed
    # QueuePool timeout errors; a bigger pool is not a substitute for releasing
    # connections, it just delays the same exhaustion.
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    # Langfuse `environment` attribute (services/api/core/tracing.py) — keeps test/dev
    # traces separate from production in dashboards and evaluations.
    environment: str = "development"
    cors_allowed_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 604800

    # Shared secret for POST /hackathons/{id}/webhook, which registers teams from an
    # external platform (Devfolio/Unstop) and so cannot authenticate as a user. Callers
    # present it as `X-Webhook-Secret`. Empty means the endpoint is disabled: it performs
    # unauthenticated writes, so defaulting to open would silently expose every
    # deployment that has not configured it.
    hackathon_webhook_secret: str = ""

    # Module 1 (Candidate Intelligence) & Multi-Provider LLM Gateway — see doc/SRS/01 §9.
    llm_provider: str = "anthropic"  # "anthropic" | "openai" | "grok" | "gemini" | "openai_compatible"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    grok_api_key: str = ""
    gemini_api_key: str = ""
    llm_base_url: str = ""
    llm_model_fast: str = "claude-haiku-4-5-20251001"
    llm_model_judgment: str = "claude-sonnet-4-6"

    # --- LLM reliability (services/api/core/llm.py) ---
    #
    # Before these existed the gateway had no timeout, no retry and no output
    # validation: a hung provider connection held a request open indefinitely, one
    # transient 429 permanently failed an agent run, and a model answering `8.5` for a
    # field documented as 0-100 was written to the database verbatim.
    #
    # Per-call ceiling passed to both provider SDKs. Generous, because judgment-tier
    # calls over a long interview transcript legitimately take tens of seconds — this is
    # a backstop against a hung socket, not a latency target.
    llm_timeout_seconds: float = 60.0
    # Retries are *additional* attempts after the first. Only failures that could
    # plausibly succeed on an identical retry are re-issued (rate limits, timeouts,
    # provider overload, malformed structured output); an exhausted quota or a bad API
    # key is never retried. 2 is deliberately low: agent pipelines chain many calls, so
    # a high per-call retry count multiplies into minutes of user-visible wait.
    llm_max_retries: int = 2
    # Base for exponential backoff (doubled per attempt, plus jitter). A provider-sent
    # `Retry-After` header always overrides this.
    llm_retry_base_delay_seconds: float = 1.0
    # Output-token budgets. These replace 17 scattered literals across the agent tools,
    # where 8 distinct values had accumulated with no rationale for the differences.
    # They are the single largest per-call cost driver, so they belong next to the
    # provider/model settings rather than buried in individual agent modules.
    llm_max_tokens_small: int = 256      # one-sentence rationales, short classifications
    llm_max_tokens_default: int = 1024   # ordinary structured scoring/extraction
    llm_max_tokens_large: int = 2048     # resume/cover-letter generation, long reports
    # Temperature for calls that must be reproducible (rubric scoring). Anything scored
    # and persisted should not vary between two runs over identical input.
    llm_temperature_deterministic: float = 0.0
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_redirect_uri: str = ""
    cloudinary_url: str = ""
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    embedding_model: str = "BAAI/bge-large-en-v1.5"

    # --- Scoring weights & thresholds ---
    #
    # These were Python literals scattered across services/agents/**, so tuning the
    # product's core output required a code deploy. Every default below is exactly the
    # value that was previously hardcoded, so a stock .env reproduces prior behaviour
    # byte for byte (services/api/tests/test_config_parity.py asserts this).
    #
    # Talent Score sub-score weights (doc 08 SS1). Renormalized over whichever sub-scores
    # actually resolved, so they need not sum to 1.0 after an override — but they should.
    weight_coding_ability: float = 0.16
    weight_problem_solving: float = 0.16
    weight_project_quality: float = 0.12
    weight_innovation: float = 0.12
    weight_technical_consistency: float = 0.08
    weight_community_participation: float = 0.08
    weight_leadership: float = 0.08
    weight_open_source_contributions: float = 0.10
    weight_hackathon_performance: float = 0.10

    # Job-match weights (doc 08 SS2). The matching module docstring already described
    # these as "tunable defaults", which is precisely an argument for configurability.
    match_weight_skill_overlap: float = 0.35
    match_weight_semantic_similarity: float = 0.30
    match_weight_experience_match: float = 0.15
    match_weight_talent_score_alignment: float = 0.20
    # SemanticSimilarity = alpha*cosine + (1-alpha)*filter_match_ratio.
    match_semantic_alpha: float = 0.70

    # How much of a judgment sub-score comes from mechanical signals vs. the LLM's
    # reading of the same evidence. Previously bare inline literals inside expressions.
    project_quality_mechanical_weight: float = 0.6
    innovation_novelty_weight: float = 0.5

    # Similarity thresholds. Five values lived in five modules, two of them sharing the
    # identifier `SIMILARITY_FLAG_THRESHOLD` with *different* values — a genuine footgun
    # when read side by side. Named per purpose here so the differences are deliberate.
    #
    # Note `skill_similarity_threshold` is only meaningful for the configured
    # `embedding_model`: changing the model silently invalidates the calibration, which
    # is why the two now sit together in one file.
    skill_similarity_threshold: float = 0.80        # recruiter search / matching
    skill_gap_similarity_threshold: float = 0.72    # career-guidance gap detection
    text_fingerprint_similarity_threshold: float = 0.80   # duplicate-profile fraud
    structural_similarity_threshold: float = 0.75   # code-plagiarism fraud
    deck_plagiarism_similarity_threshold: float = 0.90    # pitch-deck plagiarism
    photo_hash_distance_threshold: int = 4          # duplicate-photo Hamming distance

    # Percentile normalization needs a population large enough to be meaningful; below
    # it, `percentile_normalize` returns a neutral midpoint instead of a false signal.
    # This existed as three literals (30/30/10) across two modules, with a comment
    # asking humans to keep them in sync.
    min_population_for_percentile: int = 30
    min_population_for_assessment_percentile: int = 10

    # --- Agent bounds (cost, latency and loop-termination controls) ---
    # Follow-ups per interview topic. Total interview turns is bounded by
    # 2 x len(topic_plan), so this is one of the two numbers deciding worst-case cost.
    max_followups_per_topic: int = 1
    # Generate -> fact-check -> regenerate attempts in the resume/cover-letter graph.
    document_generation_max_attempts: int = 2
    # How many candidates survive retrieval to reach the expensive judgment-tier rerank.
    recruitment_shortlist_limit: int = 50
    # Interview history sent verbatim before older turns are collapsed to a summary.
    interview_max_verbatim_turns: int = 6
    interview_max_turn_chars: int = 1200
    # Ceiling on a caller-supplied interview topic plan. Without it, a large plan yields
    # an arbitrarily long interview at two judgment-tier LLM calls per turn.
    interview_max_topics: int = 12
    # Repositories crawled per candidate during ingestion (bounded for the <30s NFR).
    github_max_repos: int = 15
    # Concurrent outbound work in fan-out nodes — protects third-party rate limits.
    agent_max_concurrency: int = 5

    # --- Outbound HTTP timeouts (seconds) ---
    # Five different values were scattered across the agents and routers with no stated
    # policy. Grouped here so the differences are visible and intentional.
    github_http_timeout_seconds: float = 15.0
    leetcode_http_timeout_seconds: float = 15.0
    issuer_lookup_timeout_seconds: float = 6.0
    photo_fetch_timeout_seconds: float = 8.0
    oauth_exchange_timeout_seconds: float = 10.0
    qdrant_timeout_seconds: float = 5.0
    libreoffice_timeout_seconds: int = 60

    # --- Router TTLs, cooldowns and page caps ---
    career_recommendation_ttl_hours: int = 24
    github_oauth_state_ttl_seconds: int = 600
    stats_refresh_cooldown_minutes: int = 15
    max_dashboard_projects: int = 50
    max_score_history: int = 30
    candidate_pool_cache_ttl_seconds: int = 30
    max_candidate_pool: int = 5000
    event_poll_interval_seconds: float = 30.0

    # Salary prediction. `salary_currency` was hardcoded "USD" on every prediction even
    # though the underlying model is trained on a global survey.
    salary_currency: str = "USD"
    salary_talent_score_max_adjustment: float = 0.15
    salary_talent_score_baseline: float = 50.0

    # FR-4.4 salary regression — see tools/train_salary_model.py for how this artifact
    # gets produced (offline, from a downloaded Stack Overflow Developer Survey CSV).
    salary_model_path: str = "data/models/salary_regressor.joblib"

    # Candidate ingestion uploads (POST /candidates/me/ingest/resume, .../certificate).
    # Both routes used to call `await file.read()` with no ceiling and no type check,
    # then hand the bytes straight to pdfplumber/python-docx/Tesseract. An oversized or
    # wrong-typed upload was therefore read fully into memory, copied again into the
    # queue payload, and only rejected (if at all) deep inside a parser. The deck route
    # next door has enforced both since it was written — this is the same guard.
    resume_max_file_size_mb: int = 10
    certificate_max_file_size_mb: int = 10

    # Module 4 (PPT Analyzer) — see doc/SRS/04 §9.
    presentation_max_file_size_mb: int = 50
    # LibreOffice headless binary for legacy .ppt -> .pptx conversion (doc 04 §4). Not
    # bundled with this repo's Python venv — degrades gracefully (LegacyPptConversionUnavailable)
    # if not found on PATH, same "typed error, never fabricate" pattern as Anthropic/Cloudinary.
    libreoffice_binary: str = "soffice"

    # Platform Hardening & Observability track (2026-07-30) — see .agents/decisions.md's
    # dated entry for what's wired vs. still gated on real credentials.
    # Langfuse tracing (services/api/core/tracing.py) — empty/placeholder keys mean a
    # clean no-op (langfuse_trace_id stays None on every AgentRun, same as before this
    # track), never a crash. Same "typed empty default, fails closed" pattern as
    # anthropic_api_key/cloudinary_url above.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Sentry error reporting (services/api/main.py startup) — empty DSN means
    # sentry_sdk.init() is never called at all.
    sentry_dsn: str = ""

    # Rate-limit middleware (services/api/core/rate_limit.py), Redis-backed with an
    # in-process fallback.
    #
    # Was 60/min, which a single user could exhaust just by using the app normally: one
    # dashboard load issues ~6 requests, and the limit is per *user*, not per endpoint,
    # so a handful of navigations inside one minute returned 429s that surfaced as raw
    # errors in the UI. This is an abuse ceiling, not a usage budget — it needs to sit
    # far above what an engaged human generates while still stopping a runaway client.
    rate_limit_per_minute: int = 600

    # Durable background-job queue (services/api/core/queue.py, services/workers/runner.py).
    # Long AI pipelines (candidate ingestion, job matching, assessment grading, deck
    # analysis, hackathon ranking) used to run as FastAPI BackgroundTasks inside the API
    # process: they shared its event loop and were lost silently on restart/deploy,
    # leaving rows stuck in "processing" forever with no retry.
    #
    # When `queue_enabled` is false, or Redis is simply unreachable, every enqueue falls
    # back to the in-process BackgroundTasks path so local development and the demo work
    # with no extra moving parts — the queue is an upgrade, never a hard requirement.
    redis_url: str = "redis://localhost:6379"
    queue_enabled: bool = True
    # Per-job ceiling. Must exceed the slowest pipeline (a large GitHub crawl or a
    # multi-team hackathon finalization), or arq cancels work that would have succeeded.
    queue_job_timeout_seconds: int = 900
    # Total attempts per job, including the first. Note that arq only retries a job when
    # the task raises `arq.worker.Retry` (or is cancelled) — an ordinary exception is
    # recorded as failed and never re-run. `services/workers/tasks.py` translates the
    # transient infrastructure failures worth retrying into `Retry`; permanent ones
    # (bad input, missing row) deliberately stay non-retryable.
    queue_max_tries: int = 3
    # Base delay for the retry backoff in `services/workers/tasks.py` (doubled per try).
    queue_retry_base_delay_seconds: int = 5
    # How long completed job results stay in Redis for status inspection.
    queue_result_ttl_seconds: int = 3600



@lru_cache
def get_settings() -> Settings:
    return Settings()
