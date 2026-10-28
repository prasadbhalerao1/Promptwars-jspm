"""`weighted_renormalized_mean`: the cold-start arithmetic shared by Talent Score, Pitch
Score, Hackathon Ranking, Job Matching and Coding Ability.

The contract that matters: a missing signal is *dropped and its weight redistributed*,
and "no data at all" is `None` — never a fabricated 0.0 that would read as a real score.
"""

from __future__ import annotations

import pytest

from services.agents.common.scoring import weighted_renormalized_mean


def test_all_terms_present_is_the_plain_weighted_mean() -> None:
    assert weighted_renormalized_mean([(0.5, 80.0), (0.5, 60.0)]) == pytest.approx(70.0)
    assert weighted_renormalized_mean([(0.75, 100.0), (0.25, 0.0)]) == pytest.approx(75.0)


def test_missing_terms_are_dropped_and_weights_renormalized() -> None:
    # The 0.5-weight term is unknown, so the other two split the whole weight 0.3:0.2.
    result = weighted_renormalized_mean([(0.3, 90.0), (0.2, 40.0), (0.5, None)])
    assert result == pytest.approx((0.3 * 90 + 0.2 * 40) / 0.5)


def test_a_missing_term_is_not_treated_as_zero() -> None:
    with_missing = weighted_renormalized_mean([(0.5, 80.0), (0.5, None)])
    with_zero = weighted_renormalized_mean([(0.5, 80.0), (0.5, 0.0)])
    assert with_missing == pytest.approx(80.0)
    assert with_zero == pytest.approx(40.0)


@pytest.mark.parametrize(
    "terms",
    [[], [(0.5, None), (0.5, None)], [(0.0, 70.0), (0.0, 30.0)]],
    ids=["empty", "all-missing", "zero-weight"],
)
def test_no_usable_signal_is_none_not_zero(terms) -> None:
    assert weighted_renormalized_mean(terms) is None


def test_genuine_zero_scores_are_kept() -> None:
    assert weighted_renormalized_mean([(1.0, 0.0)]) == 0.0


def test_result_stays_within_the_input_range() -> None:
    terms = [(0.4, 12.0), (0.35, 99.5), (0.25, 55.0)]
    result = weighted_renormalized_mean(terms)
    assert min(v for _, v in terms) <= result <= max(v for _, v in terms)
