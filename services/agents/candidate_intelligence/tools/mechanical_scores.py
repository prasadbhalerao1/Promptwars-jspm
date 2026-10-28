"""Fully mechanical sub-scores — rules only, no LLM (doc 01 §4 model-routing table).

All population/assessment data is injected by the caller (the router, which owns the DB
session) rather than queried here — nodes/tools in this module stay pure and testable,
same convention as the rest of candidate_intelligence.
"""

import math

from packages.shared_schemas.candidates import SubScore
from services.agents.candidate_intelligence.tools.github import (
    GithubAnalysis,
    commit_consistency_score,
)
from services.agents.candidate_intelligence.tools.normalization import (
    percentile_normalize,
    winsorize,
)
from services.agents.common.scoring import weighted_renormalized_mean


def _language_score_fallback(total_commits: float) -> float:
    # Log-scale so a handful of high-volume repos don't dominate (doc 08 §1: "log-scaled
    # commit frequency"). 200 own commits ~= a strong signal; scaled to land near 80-90.
    return min(100.0, 100.0 * math.log1p(total_commits) / math.log1p(200))


def coding_ability(
    analysis: GithubAnalysis,
    *,
    commit_population: list[float],
    quality_score: float | None,
    assessment_score: float | None,
    assessment_population: list[float],
) -> SubScore:
    """0.25 language + 0.35 code quality + 0.40 assessment (proposal's weighting —
    assessments are the hardest signal to game, so they carry the most weight once
    available). Any missing term drops out and the remaining weights renormalize,
    same cold-start pattern as aggregate.compute_overall."""
    if not analysis.repos and assessment_score is None:
        return SubScore(value=None, rationale="No GitHub repos or assessment submissions — cold start.")

    total_commits = sum(r.commit_count for r in analysis.repos if not r.is_fork)
    language_score = (
        percentile_normalize(
            float(total_commits), commit_population, fallback_fn=_language_score_fallback
        )
        if analysis.repos
        else None
    )

    assessment_percentile = (
        percentile_normalize(assessment_score, winsorize(assessment_population), min_population=10)
        if assessment_score is not None
        else None
    )

    terms = {"language": (0.25, language_score), "quality": (0.35, quality_score), "assessment": (0.40, assessment_percentile)}
    available = {name: (w, v) for name, (w, v) in terms.items() if v is not None}
    if not available:
        return SubScore(value=None, rationale="No language, quality, or assessment signal available.")

    value = weighted_renormalized_mean(list(available.values()))

    return SubScore(
        value=round(value, 1),
        evidence=[r.repo_full_name for r in analysis.repos if not r.is_fork][:10],
        rationale=(
            f"{total_commits} commits across {analysis.owned_repo_count} owned repos; "
            f"components used: {', '.join(available)}"
            + (" (assessment score not yet available)" if "assessment" not in available else "")
        ),
    )


def technical_consistency(analysis: GithubAnalysis) -> SubScore:
    score = commit_consistency_score(analysis.commit_activity_weekly, analysis.commit_activity_weekly_dated)
    if score is None:
        return SubScore(value=None, rationale="Not enough weekly commit history yet.")
    return SubScore(
        value=round(score, 1),
        rationale=(
            "Recency-weighted coefficient of variation over the last 52 weeks of commit "
            "activity, with penalties for long inactivity and a bonus for sustained cadence."
        ),
    )


def community_participation(analysis: GithubAnalysis, *, star_population: list[float]) -> SubScore:
    if not analysis.repos and analysis.external_contributions == 0:
        return SubScore(value=None, rationale="No GitHub activity found — cold start.")
    # Percentile-normalized against other candidates rather than a fixed constant — a
    # star count only scores highly if it's high relative to real peers, which is harder
    # to game than beating a publicly-known log1p(100) target.
    star_component = 0.6 * percentile_normalize(
        float(analysis.total_stars),
        star_population,
        fallback_fn=lambda s: min(100.0, 100.0 * math.log1p(s) / math.log1p(100)),
    )
    contrib_component = min(40.0, analysis.external_contributions * 8.0)
    value = star_component + contrib_component
    return SubScore(
        value=round(value, 1),
        rationale=(
            f"{analysis.total_stars} total stars (percentile-normalized vs. candidate pool), "
            f"{analysis.external_contributions} external merged PRs "
            "(hackathon participation count not yet available)."
        ),
    )


def leadership(analysis: GithubAnalysis, *, leadership_population: list[float]) -> SubScore:
    if analysis.owned_repo_count == 0 and analysis.pr_review_count == 0:
        return SubScore(value=None, rationale="No maintainer or PR-review signal yet.")
    # Raw component kept as the fallback formula; percentile-normalized against the
    # population is the primary anti-gaming measure — still flagged as the most gameable
    # signal (doc 08 §1 practical note), now mitigated by more than just low weight.
    raw_maintainer = min(50.0, analysis.owned_repo_count * 10.0)
    raw_review = min(50.0, analysis.pr_review_count * 5.0)
    raw_value = raw_maintainer + raw_review
    value = percentile_normalize(raw_value, leadership_population, fallback_fn=lambda v: v)
    return SubScore(
        value=round(value, 1),
        rationale=(
            f"Owns/maintains {analysis.owned_repo_count} non-fork repos, "
            f"{analysis.pr_review_count} PR reviews found, percentile-normalized vs. candidate "
            "pool (team-lead flag from doc 03 not yet available)."
        ),
    )


def problem_solving(
    assessment_score: float | None, assessment_population: list[float]
) -> SubScore:
    """Directly from the candidate's latest assessment score, winsorized 5th-95th
    against the population per the proposal, then percentile-ranked. `None` only when
    the candidate truly has no assessment submissions yet — real cold start, not a
    permanent placeholder."""
    if assessment_score is None:
        return SubScore(
            value=None,
            rationale="No assessment submissions yet — problem solving requires at least one.",
        )
    winsorized_population = winsorize(assessment_population)
    value = percentile_normalize(assessment_score, winsorized_population, min_population=10)
    return SubScore(
        value=round(value, 1),
        rationale=f"Latest assessment score {assessment_score:.1f}, percentile-ranked (winsorized 5th-95th) vs. candidate pool.",
    )
