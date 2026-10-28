"""Unit tests for hackathon_performance scoring."""

import pytest

from services.agents.candidate_intelligence.tools.hackathon_score import (
    hackathon_performance,
    normalize_weight,
    RESULT_TIER_SCORES,
)


def test_cold_start_no_hackathons():
    """No hackathon participation → None (cold start)."""
    result = hackathon_performance()

    assert result.value is None
    assert "cold start" in result.rationale.lower()


def test_single_self_reported_winner():
    """One self-reported winner entry → score reflects winner tier."""
    self_reported = [
        {
            "name": "HackIndia 2025",
            "result": "winner",
            "weight": 1.0,
            "date": "2025-03-01",
        }
    ]

    result = hackathon_performance(self_reported=self_reported)

    assert result.value is not None
    assert 0 < result.value <= 100
    expected_score = RESULT_TIER_SCORES["winner"] * normalize_weight(1.0)
    assert result.value == round(min(100.0, expected_score), 1)


def test_weight_normalization():
    """1-5 weight scale normalizes to 0.2-1.0 range."""
    # approx(): these are binary-float divisions (3/5 == 0.6000000000000001), so exact
    # equality fails on a correct implementation.
    assert normalize_weight(1) == pytest.approx(0.2)
    assert normalize_weight(3) == pytest.approx(0.6)  # middle of range
    assert normalize_weight(5) == pytest.approx(1.0)
    assert normalize_weight(None) == pytest.approx(1.0)  # default platform weight


def test_multiple_hackathons_capped():
    """Multiple hackathons combined with capping at 100."""
    self_reported = [
        {"name": "Hack1", "result": "winner", "weight": 5},
        {"name": "Hack2", "result": "top5", "weight": 5},
        {"name": "Hack3", "result": "finalist", "weight": 5},
    ]

    result = hackathon_performance(self_reported=self_reported)

    assert result.value is not None
    assert result.value <= 100.0  # must be capped
    assert result.value > 0


def test_platform_results_rank_mapping():
    """Platform results: rank 1 → winner, 2-5 → top5, etc."""
    platform_results = [
        {"rank": 1, "composite_score": 95.0, "hackathon_id": "h1"},
        {"rank": 3, "composite_score": 85.0, "hackathon_id": "h2"},
        {"rank": 8, "composite_score": 65.0, "hackathon_id": "h3"},
    ]

    result = hackathon_performance(platform_results=platform_results)

    assert result.value is not None
    assert 0 < result.value <= 100
    assert "3 hackathon(s)" in result.rationale
    assert "3 platform" in result.rationale


def test_combined_platform_and_self_reported():
    """Mix of platform-run and self-reported hackathons."""
    platform_results = [
        {"rank": 2, "composite_score": 90.0, "hackathon_id": "h1"},
    ]

    self_reported = [
        {"name": "External1", "result": "winner", "weight": 4},
    ]

    result = hackathon_performance(platform_results=platform_results, self_reported=self_reported)

    assert result.value is not None
    assert 0 < result.value <= 100
    assert "2 hackathon(s)" in result.rationale
    assert "1 platform" in result.rationale
    assert "1 self-reported" in result.rationale
