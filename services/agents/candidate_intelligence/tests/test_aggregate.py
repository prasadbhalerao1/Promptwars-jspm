from packages.shared_schemas.candidates import SubScore
from services.agents.candidate_intelligence.tools.aggregate import (
    SUB_SCORE_WEIGHTS,
    compute_confidence,
    compute_overall,
)


def _all_sub_scores(**overrides) -> dict[str, SubScore]:
    """Every sub-score in SUB_SCORE_WEIGHTS, all populated.

    Must stay in sync with `aggregate.SUB_SCORE_WEIGHTS` — a sub-score present there but
    absent here is reported as "missing" by compute_overall, which previously broke these
    tests when open_source_contributions/hackathon_performance were added to the model.
    """
    base = {
        "coding_ability": SubScore(value=80.0),
        "problem_solving": SubScore(value=70.0),
        "project_quality": SubScore(value=60.0),
        "innovation": SubScore(value=50.0),
        "technical_consistency": SubScore(value=90.0),
        "community_participation": SubScore(value=40.0),
        "leadership": SubScore(value=30.0),
        "open_source_contributions": SubScore(value=55.0),
        "hackathon_performance": SubScore(value=45.0),
    }
    assert set(base) == set(SUB_SCORE_WEIGHTS), "fixture drifted from SUB_SCORE_WEIGHTS"
    base.update(overrides)
    return base


def test_compute_overall_all_present():
    overall, missing = compute_overall(_all_sub_scores())
    assert missing == []
    assert overall is not None


def test_compute_overall_renormalizes_missing():
    sub_scores = _all_sub_scores(problem_solving=SubScore(value=None))
    overall, missing = compute_overall(sub_scores)
    assert missing == ["problem_solving"]
    assert overall is not None


def test_compute_overall_all_missing_returns_none():
    sub_scores = {name: SubScore(value=None) for name in _all_sub_scores()}
    overall, missing = compute_overall(sub_scores)
    assert overall is None
    assert set(missing) == set(sub_scores.keys())


def test_compute_confidence_full_evidence():
    confidence = compute_confidence(_all_sub_scores())
    assert confidence.available_signals == len(SUB_SCORE_WEIGHTS)
    assert confidence.expected_signals == len(SUB_SCORE_WEIGHTS)
    assert confidence.confidence == 1.0


def test_compute_confidence_partial_evidence_below_threshold():
    # Null out a majority of the 9 sub-scores so confidence lands below the 0.5
    # threshold this test is about (3 of 9 available = 0.33).
    sub_scores = _all_sub_scores(
        problem_solving=SubScore(value=None),
        project_quality=SubScore(value=None),
        innovation=SubScore(value=None),
        community_participation=SubScore(value=None),
        open_source_contributions=SubScore(value=None),
        hackathon_performance=SubScore(value=None),
    )
    confidence = compute_confidence(sub_scores)
    assert confidence.available_signals == 3
    assert confidence.confidence < 0.5


def test_compute_confidence_no_evidence():
    sub_scores = {name: SubScore(value=None) for name in _all_sub_scores()}
    confidence = compute_confidence(sub_scores)
    assert confidence.available_signals == 0
    assert confidence.confidence == 0.0
