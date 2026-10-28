"""Shared weighted-renormalization arithmetic — the "drop any missing term, renormalize
the remaining weights to sum to 1.0" cold-start pattern (doc 08 §1.1) that Talent Score,
Pitch Score, Hackathon Ranking, Job Matching, and the Coding Ability sub-score each
implemented as their own copy of the same three lines. Consolidated here after finding
the arithmetic was byte-identical everywhere; each caller keeps its own return shape,
rounding precision, and edge-case handling (some return `None` on total failure, one
returns `0.0`) rather than being forced into one shape — only the actual sum/divide is
shared, to avoid changing behavior on business-critical scoring formulas right before a
demo.
"""


def weighted_renormalized_mean(terms: list[tuple[float, float | None]]) -> float | None:
    """`terms` is a list of (weight, value_or_None). Missing (`None`) terms are dropped
    and the remaining weights renormalized to sum to 1.0 before averaging. Returns `None`
    if every term is missing or the available weights sum to zero — never a fabricated
    0.0 passed off as a real score; callers that want a `0.0` fallback in that case should
    apply it themselves at the call site."""
    available = [(w, v) for w, v in terms if v is not None]
    weight_sum = sum(w for w, _ in available)
    if not available or weight_sum == 0:
        return None
    return sum(w * v for w, v in available) / weight_sum
