from datetime import datetime, timedelta, timezone

from services.agents.candidate_intelligence.tools.normalization import (
    percentile_normalize,
    recency_weight,
    winsorize,
)


def test_percentile_normalize_below_min_population_uses_fallback():
    result = percentile_normalize(50.0, [1.0, 2.0, 3.0], min_population=30, fallback_fn=lambda v: v * 2)
    assert result == 100.0


def test_percentile_normalize_below_min_population_no_fallback_returns_neutral():
    result = percentile_normalize(50.0, [1.0, 2.0], min_population=30)
    assert result == 50.0


def test_percentile_normalize_ranks_against_population():
    population = list(range(1, 101))  # 1..100
    result = percentile_normalize(50.0, [float(v) for v in population], min_population=30)
    assert result == 50.0  # exactly 50 values <= 50 out of 100


def test_percentile_normalize_top_of_population():
    population = [float(v) for v in range(1, 101)]
    result = percentile_normalize(100.0, population, min_population=30)
    assert result == 100.0


def test_recency_weight_at_zero_days_is_one():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert recency_weight(now, as_of=now) == 1.0


def test_recency_weight_halves_at_half_life():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    past = now - timedelta(days=180)
    weight = recency_weight(past, as_of=now, half_life_days=180.0)
    assert abs(weight - 0.5) < 1e-6


def test_recency_weight_handles_naive_datetime():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    past_naive = datetime(2026, 1, 1) - timedelta(days=90)
    weight = recency_weight(past_naive, as_of=now, half_life_days=180.0)
    assert 0.0 < weight < 1.0


def test_winsorize_clips_outliers():
    values = [1.0] + [50.0] * 18 + [1000.0]
    result = winsorize(values, lower_pct=5.0, upper_pct=95.0)
    assert max(result) < 1000.0
    assert min(result) > 1.0


def test_winsorize_empty_list():
    assert winsorize([]) == []
