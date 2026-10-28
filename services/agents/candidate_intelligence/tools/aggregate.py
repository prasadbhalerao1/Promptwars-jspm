"""Talent Score aggregation — doc 08 §1 formula + §1.1 cold-start re-normalization."""

from packages.shared_schemas.candidates import EvidenceConfidence, SubScore
from services.agents.common.scoring import weighted_renormalized_mean
from services.api.core.config import get_settings

def _sub_score_weights() -> dict[str, float]:
    """The Talent Score formula, resolved from Settings on each call.

    Was a module-level dict literal, which made the product's central formula a
    deploy-only change. Read through `get_settings()` (itself `lru_cache`d, so this is a
    dict rebuild rather than any I/O) so a deployment can retune weights via .env
    without a code change. Defaults are byte-identical to the previous literals.
    """
    s = get_settings()
    return {
        "coding_ability": s.weight_coding_ability,
        "problem_solving": s.weight_problem_solving,
        "project_quality": s.weight_project_quality,
        "innovation": s.weight_innovation,
        "technical_consistency": s.weight_technical_consistency,
        "community_participation": s.weight_community_participation,
        "leadership": s.weight_leadership,
        "open_source_contributions": s.weight_open_source_contributions,
        "hackathon_performance": s.weight_hackathon_performance,
    }


class _SubScoreWeights(dict):
    """Backwards-compatible view over the configured weights.

    `SUB_SCORE_WEIGHTS` is imported and iterated by other modules and by tests as a
    plain mapping. Subclassing dict and refreshing from Settings on construction keeps
    every existing `SUB_SCORE_WEIGHTS[name]` / `.keys()` / `in` usage working unchanged.
    """

    def __init__(self) -> None:
        super().__init__(_sub_score_weights())


SUB_SCORE_WEIGHTS = _SubScoreWeights()


def compute_overall(sub_scores: dict[str, SubScore]) -> tuple[float | None, list[str]]:
    """Returns (overall_score, names_of_sub_scores_that_were_renormalized_away).

    S = sum(w_i' * S_i), where w_i' zeroes out any N/A sub-score's weight and
    re-normalizes the rest to sum to 1.0 (doc 08 §1.1) — candidates aren't penalized
    for profile incompleteness.
    """
    available = {name: s for name, s in sub_scores.items() if s.value is not None}
    missing = [name for name in SUB_SCORE_WEIGHTS if name not in available]

    overall = weighted_renormalized_mean(
        [(SUB_SCORE_WEIGHTS[name], s.value) for name, s in available.items()]
    )
    if overall is None:
        return None, missing
    return round(overall, 1), missing


def compute_confidence(sub_scores: dict[str, SubScore]) -> EvidenceConfidence:
    """Evidence Confidence Score (proposed algorithm): how much of the Talent Score is
    backed by real evidence vs. cold-start gaps — available_signals / expected_signals,
    where "signals" are the 7 sub-scores that resolved to a value. A score's overall
    number is never withheld below the 50% threshold, only flagged for the recruiter.
    """
    expected_signals = len(SUB_SCORE_WEIGHTS)
    available_signals = sum(1 for s in sub_scores.values() if s.value is not None)
    confidence = available_signals / expected_signals if expected_signals else 0.0
    return EvidenceConfidence(
        available_signals=available_signals,
        expected_signals=expected_signals,
        confidence=round(confidence, 2),
    )
