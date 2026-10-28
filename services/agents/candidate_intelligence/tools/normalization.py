"""Population-relative normalization — doc 08 §"Normalization" / proposed algorithm.

Fixed-constant log/min-max scaling (e.g. log1p(stars)/log1p(100)) is easy to reverse-
engineer and target. Percentile rank against the actual candidate population is harder
to game (an attacker doesn't control what everyone else's numbers look like) and adapts
automatically as the pool grows or skews. Below `min_population`, percentile ranks are
statistically meaningless (a handful of candidates can swing the whole distribution), so
callers fall back to a fixed-constant formula instead.
"""

import math
from collections.abc import Callable
from datetime import datetime, timezone


def percentile_normalize(
    value: float,
    population_values: list[float],
    *,
    min_population: int = 30,
    fallback_fn: Callable[[float], float] | None = None,
) -> float:
    """Percentile rank of `value` within `population_values`, scaled to 0-100.

    Falls back to `fallback_fn(value)` when the population is too small to rank
    against meaningfully. If no fallback is given, returns 50.0 (neutral) below
    threshold rather than a rank that swings wildly with each new candidate.
    """
    if len(population_values) < min_population:
        return fallback_fn(value) if fallback_fn is not None else 50.0

    at_or_below = sum(1 for v in population_values if v <= value)
    return 100.0 * at_or_below / len(population_values)


def recency_weight(
    reference_date: datetime,
    *,
    as_of: datetime | None = None,
    half_life_days: float = 180.0,
) -> float:
    """w = e^(-lambda * t), lambda chosen so weight halves every `half_life_days`."""
    now = as_of or datetime.now(timezone.utc)
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)
    days_elapsed = max(0.0, (now - reference_date).total_seconds() / 86400.0)
    lam = math.log(2) / half_life_days
    return math.exp(-lam * days_elapsed)


def winsorize(values: list[float], *, lower_pct: float = 5.0, upper_pct: float = 95.0) -> list[float]:
    """Clip values to the [lower_pct, upper_pct] percentile range of themselves."""
    if not values:
        return []
    sorted_values = sorted(values)
    n = len(sorted_values)

    def _percentile(pct: float) -> float:
        idx = (pct / 100.0) * (n - 1)
        lo, hi = math.floor(idx), math.ceil(idx)
        if lo == hi:
            return sorted_values[int(idx)]
        frac = idx - lo
        return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac

    lower_bound = _percentile(lower_pct)
    upper_bound = _percentile(upper_pct)
    return [min(max(v, lower_bound), upper_bound) for v in values]
