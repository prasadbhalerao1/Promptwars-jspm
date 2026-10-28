"""Population queries for percentile normalization — DB access only, never called from
graph nodes (nodes stay pure per this module's convention; the router fetches this once
per ingestion request and passes it in via state, same as any other node input).

Three properties matter here, because this runs on *every* ingestion — resume upload,
certificate upload, GitHub connect, and every hackathon-experience edit — and therefore
sits directly on the user-visible "processing" wait:

1. **The size guard comes first.** `percentile_normalize` discards the population
   entirely below `min_population` (30) and uses a fixed-constant fallback instead. The
   old code fetched every population *before* discovering that, so a small deployment
   paid the full cost of six table scans on every ingestion and then threw all six
   results away.
2. **One query, not three.** `talent_scores` is append-only, so "latest per candidate"
   needs deduplication. Three separate window-function subqueries each scanned and sorted
   the whole table for one column; a single `DISTINCT ON` returns all three at once.
3. **Cached briefly.** A population is a platform-wide aggregate — it barely moves
   between two ingestions seconds apart, and every concurrent ingestion recomputed it
   independently.
"""

import time

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from packages.db.models.candidate import CandidateProfile, TalentScore

# Sub-scores percentile-normalized against the population (doc: community_participation,
# leadership). coding_ability/problem_solving use assessment_bridge.py's population instead.
_POPULATION_FIELDS = ("community_participation", "leadership")

# Mirrors `percentile_normalize(min_population=30)`. Below this the populations are never
# consulted, so fetching them is pure waste — this module short-circuits on the same
# threshold rather than duplicating the policy silently. Keep the two in sync.
MIN_POPULATION = 30

# Populations are platform-wide aggregates that shift only as candidates are rescored, so
# a short TTL is safe and removes the repeated cost across concurrent ingestions. Same
# in-process pattern as recruitment/router.py's candidate-pool cache — deliberately not
# Redis: a stale-by-seconds population changes a percentile by a fraction of a point.
_CACHE_TTL_SECONDS = 300.0
_cache: dict[str, tuple[float, object]] = {}


def cache_get(key: str) -> object | None:
    """Cached value for `key`, or None if absent or expired.

    Public because assessment_bridge.py caches its own population on identical terms;
    keeping one TTL policy in one module beats two implementations that can drift.
    """
    entry = _cache.get(key)
    if entry is None or entry[0] < time.monotonic():
        return None
    return entry[1]


def cache_put(key: str, value: object) -> None:
    _cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, value)


def clear_population_cache() -> None:
    """Drop all cached populations. Exists for tests and for callers that have just
    written scores and want the next read to reflect them immediately."""
    _cache.clear()


async def scored_candidate_count(db: AsyncSession) -> int:
    """How many distinct candidates have any TalentScore row.

    Cheap upper bound on every `talent_scores`-derived population: no per-column
    population can exceed it, so one COUNT decides whether fetching any of them is
    worthwhile at all.
    """
    cached = cache_get("scored_count")
    if cached is not None:
        return int(cached)  # type: ignore[arg-type]
    result = await db.execute(select(func.count(distinct(TalentScore.candidate_id))))
    count = int(result.scalar() or 0)
    cache_put("scored_count", count)
    return count


async def latest_subscore_populations(
    db: AsyncSession, field_names: tuple[str, ...]
) -> dict[str, list[float]]:
    """Latest TalentScore row per candidate, projected to the requested sub-score columns.

    One `DISTINCT ON (candidate_id) ... ORDER BY candidate_id, computed_at DESC` replaces
    one `row_number()` window subquery per column. `talent_scores` is append-only, so its
    size grows with total platform history rather than candidate count, which is what
    made repeating that scan per column worth removing.

    Returns `{field: []}` for every requested field when the platform has fewer than
    `MIN_POPULATION` scored candidates, since `percentile_normalize` would discard the
    values anyway.
    """
    for field_name in field_names:
        if field_name not in _POPULATION_FIELDS and field_name not in TalentScore.__table__.columns:
            raise ValueError(f"Unknown TalentScore field: {field_name}")

    if await scored_candidate_count(db) < MIN_POPULATION:
        return {field_name: [] for field_name in field_names}

    cache_key = f"subscores:{','.join(sorted(field_names))}"
    cached = cache_get(cache_key)
    if cached is not None:
        return dict(cached)  # type: ignore[arg-type]

    columns = [getattr(TalentScore, field_name) for field_name in field_names]
    stmt = (
        select(*columns)
        .distinct(TalentScore.candidate_id)
        .order_by(TalentScore.candidate_id, TalentScore.computed_at.desc())
    )
    result = await db.execute(stmt)

    # NULLs are filtered per column rather than in the WHERE clause: a candidate's latest
    # score row can have one sub-score populated and another not, and excluding the whole
    # row would drop that candidate from every other column's population too.
    populations: dict[str, list[float]] = {field_name: [] for field_name in field_names}
    for row in result.all():
        for field_name, value in zip(field_names, row):
            if value is not None:
                populations[field_name].append(float(value))

    cache_put(cache_key, populations)
    return populations


async def latest_subscore_population(db: AsyncSession, field_name: str) -> list[float]:
    """Single-column wrapper over `latest_subscore_populations`.

    Kept so existing call sites and tests keep working; prefer the plural form when
    fetching more than one column so they share a single query.
    """
    return (await latest_subscore_populations(db, (field_name,)))[field_name]


async def commit_count_population(db: AsyncSession) -> list[float]:
    """Total commit counts (sum of each candidate's github_stats.commit_activity_weekly)
    across all candidates with GitHub data — feeds coding_ability's language_score
    percentile normalization. No dedicated commit-count table exists; this JSONB column
    is the cheapest available population proxy (candidate_id is the primary key, so no
    "latest per candidate" window function is needed here, unlike TalentScore)."""
    cached = cache_get("commit_counts")
    if cached is not None:
        return list(cached)  # type: ignore[arg-type]

    # Counted with the same query rather than a separate COUNT: this population comes
    # from candidate_profiles (one row per candidate), so the row count is only known
    # after filtering out candidates whose github_stats carry no weekly activity.
    result = await db.execute(
        select(CandidateProfile.github_stats).where(CandidateProfile.github_stats.is_not(None))
    )
    totals: list[float] = []
    for (stats,) in result.all():
        weekly = (stats or {}).get("commit_activity_weekly") or []
        if weekly:
            totals.append(float(sum(weekly)))

    cache_put("commit_counts", totals)
    return totals
