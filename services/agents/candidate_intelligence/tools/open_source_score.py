"""Open-source contributions scoring — percentile-normalized external PR/contribution activity."""

import math

from packages.shared_schemas.candidates import SubScore
from services.agents.candidate_intelligence.tools.github import GithubAnalysis
from services.agents.candidate_intelligence.tools.normalization import (
    percentile_normalize,
    winsorize,
)


def open_source_contributions(
    analysis: GithubAnalysis, *, contribution_population: list[float]
) -> SubScore:
    """Score based on external contributions: PRs to non-owned repos, diversity,
    and fork activity. Higher weight on merged PRs (external_contributions) and
    spread across distinct repos (activity breadth).

    Percentile-normalized against candidate pool to prevent gaming and reflect
    peer comparison (analogous to stars in community_participation). No negative
    component — candidates with no external contributions just get None (cold start).
    """
    if analysis.external_contributions == 0:
        return SubScore(
            value=None,
            rationale="No external pull requests or contributions found — cold start.",
        )

    external_repos_count = sum(
        1 for repo in analysis.repos if repo.is_fork or (repo.pr_count and repo.pr_count > 0)
    )

    external_pr_component = min(
        50.0,
        analysis.external_contributions * 5.0,  # Each external PR worth 5 points, capped at 50
    )

    breadth_component = min(
        30.0,
        external_repos_count * 3.0,  # Each distinct repo contributed to worth 3 points, capped at 30
    )

    language_diversity = len(set(lang for repo in analysis.repos for lang in (repo.languages or {}).keys()))
    diversity_component = min(
        20.0,
        language_diversity * 2.5,  # Each distinct language worth 2.5 points, capped at 20
    )

    raw_value = external_pr_component + breadth_component + diversity_component

    value = percentile_normalize(
        raw_value,
        contribution_population,
        fallback_fn=lambda v: v,  # Use raw value as fallback if population too small
    )

    return SubScore(
        value=round(value, 1),
        rationale=(
            f"{analysis.external_contributions} external merged PRs across "
            f"{external_repos_count} distinct repos, "
            f"{language_diversity} programming languages, "
            "percentile-normalized vs. candidate pool."
        ),
    )
