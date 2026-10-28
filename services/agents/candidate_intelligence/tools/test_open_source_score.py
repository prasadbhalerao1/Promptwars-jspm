"""Unit tests for open_source_contributions scoring."""

from services.agents.candidate_intelligence.tools.github import GithubAnalysis, RepoSnapshot
from services.agents.candidate_intelligence.tools.open_source_score import open_source_contributions


def test_cold_start_no_external_contributions():
    """No external contributions → None (cold start)."""
    analysis = GithubAnalysis(
        repos=[],
        owned_repo_count=0,
        external_contributions=0,
        pr_review_count=0,
        total_stars=0,
        commit_activity_weekly=[],
        commit_activity_weekly_dated=[],
    )

    result = open_source_contributions(analysis, contribution_population=[])

    assert result.value is None
    assert "cold start" in result.rationale.lower()


def test_single_external_pr():
    """One external PR → score based on breadth and PR count."""
    analysis = GithubAnalysis(
        repos=[
            RepoSnapshot(
                repo_full_name="other/repo",
                stars=10,
                forks=2,
                commit_count=1,
                pr_count=1,
                issue_count=0,
                languages={"python": 100},
                is_fork=False,
                topics=["open-source"],
                pushed_at=None,
                description="External repo",
            )
        ],
        owned_repo_count=0,
        external_contributions=1,
        pr_review_count=0,
        total_stars=10,
        commit_activity_weekly=[],
        commit_activity_weekly_dated=[],
    )

    result = open_source_contributions(analysis, contribution_population=[50.0, 60.0, 70.0])

    assert result.value is not None
    assert 0 < result.value <= 100
    assert "1 external merged" in result.rationale


def test_high_contribution_activity():
    """Multiple external PRs across diverse repos and languages → higher score."""
    repos = [
        RepoSnapshot(
            repo_full_name="org1/repo1",
            stars=20,
            forks=5,
            commit_count=2,
            pr_count=2,
            issue_count=1,
            languages={"python": 80, "javascript": 20},
            is_fork=False,
            topics=["data"],
            pushed_at=None,
            description="",
        ),
        RepoSnapshot(
            repo_full_name="org2/repo2",
            stars=15,
            forks=3,
            commit_count=1,
            pr_count=1,
            issue_count=0,
            languages={"rust": 100},
            is_fork=False,
            topics=["systems"],
            pushed_at=None,
            description="",
        ),
    ]

    analysis = GithubAnalysis(
        repos=repos,
        owned_repo_count=1,
        external_contributions=5,
        pr_review_count=2,
        total_stars=35,
        commit_activity_weekly=[],
        commit_activity_weekly_dated=[],
    )

    result = open_source_contributions(analysis, contribution_population=[40.0, 60.0, 80.0])

    assert result.value is not None
    assert 0 < result.value <= 100
    assert "5 external merged" in result.rationale
