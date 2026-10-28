from datetime import datetime, timedelta, timezone

from services.agents.candidate_intelligence.tools.github import commit_consistency_score


def _weeks_ago(n: int, as_of: datetime) -> datetime:
    return as_of - timedelta(weeks=n)


def test_commit_consistency_none_with_insufficient_history():
    assert commit_consistency_score([1, 0, 0, 0, 0]) is None


def test_commit_consistency_unweighted_fallback_without_dates():
    weekly = [5] * 10 + [0] * 42
    score = commit_consistency_score(weekly)
    assert score is not None
    assert 0 <= score <= 100


def test_commit_consistency_recency_weighted_penalizes_stale_activity():
    as_of = datetime(2026, 7, 31, tzinfo=timezone.utc)
    # Steady activity, but all of it a year ago -> should be penalized for inactivity.
    stale_dated = [(_weeks_ago(52 - i, as_of), 5) for i in range(10)] + [
        (_weeks_ago(42 - i, as_of), 0) for i in range(42)
    ]
    stale_counts = [c for _, c in stale_dated]

    # Recent, equally steady activity -> should score higher than the stale version.
    recent_dated = [(_weeks_ago(10 - i, as_of), 5) for i in range(10)] + [
        (_weeks_ago(0, as_of), 0) for _ in range(42)
    ]
    recent_counts = [c for _, c in recent_dated]

    stale_score = commit_consistency_score(stale_counts, stale_dated)
    recent_score = commit_consistency_score(recent_counts, recent_dated)

    assert stale_score is not None and recent_score is not None
    assert recent_score > stale_score


def test_commit_consistency_bonus_for_sustained_activity():
    as_of = datetime(2026, 7, 31, tzinfo=timezone.utc)
    sustained_dated = [(_weeks_ago(52 - i, as_of), 3) for i in range(50)] + [
        (_weeks_ago(2, as_of), 0),
        (_weeks_ago(1, as_of), 0),
    ]
    sustained_counts = [c for _, c in sustained_dated]

    bursty_dated = [(_weeks_ago(52 - i, as_of), 0) for i in range(48)] + [
        (_weeks_ago(3, as_of), 40),
        (_weeks_ago(2, as_of), 40),
        (_weeks_ago(1, as_of), 40),
        (_weeks_ago(0, as_of), 40),
    ]
    bursty_counts = [c for _, c in bursty_dated]

    sustained_score = commit_consistency_score(sustained_counts, sustained_dated)
    bursty_score = commit_consistency_score(bursty_counts, bursty_dated)

    assert sustained_score is not None and bursty_score is not None
    assert sustained_score > bursty_score
