"""Bridges candidate_intelligence's Talent Score to the assessment module (Module 3),
which produces real 0-100 Submission.score values but was never read by scoring — the
proposal's "assessment should remain the strongest signal because GitHub alone isn't
enough" gets applied here: coding_ability and problem_solving both draw on it.

DB access only, called from the router (not from graph nodes) — same convention as
population.py.

InterviewReport/ContributionReport are NOT bridged here: technical_rating and
contribution_share are on different scales (a 1-10ish rating and a 0-1 share, not a
0-100 score) and need their own normalization design before they can be blended in.
Left as a followup, not silently dropped.
"""

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from packages.db.models.assessment import Submission
from services.agents.candidate_intelligence.tools.population import (
    MIN_POPULATION,
    cache_get,
    cache_put,
)


async def latest_assessment_score(db: AsyncSession, candidate_id: str) -> float | None:
    result = await db.execute(
        select(Submission.score)
        .where(Submission.candidate_id == candidate_id, Submission.score.is_not(None))
        .order_by(Submission.submitted_at.desc())
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def assessment_score_population(db: AsyncSession) -> list[float]:
    """Latest Submission.score per candidate, across all candidates with a submission.

    Guarded by a COUNT and cached on the same terms as population.py's queries: this runs
    on every ingestion, and `percentile_normalize` throws the result away below
    `MIN_POPULATION`, so the scan is pure waste on a small deployment. `DISTINCT ON`
    replaces the `row_number()` window subquery — same result, no sort of the full table.
    """
    cached = cache_get("assessment_scores")
    if cached is not None:
        return list(cached)  # type: ignore[arg-type]

    count_result = await db.execute(
        select(func.count(distinct(Submission.candidate_id))).where(Submission.score.is_not(None))
    )
    if int(count_result.scalar() or 0) < MIN_POPULATION:
        cache_put("assessment_scores", [])
        return []

    result = await db.execute(
        select(Submission.score)
        .where(Submission.score.is_not(None))
        .distinct(Submission.candidate_id)
        .order_by(Submission.candidate_id, Submission.submitted_at.desc())
    )
    scores = [float(row[0]) for row in result.all()]
    cache_put("assessment_scores", scores)
    return scores
