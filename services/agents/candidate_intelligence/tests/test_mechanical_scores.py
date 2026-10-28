from services.agents.candidate_intelligence.tools import mechanical_scores
from services.agents.candidate_intelligence.tools.github import GithubAnalysis, RepoSnapshot


def _analysis_with_commits(total_commits: int) -> GithubAnalysis:
    return GithubAnalysis(
        repos=[
            RepoSnapshot(
                repo_full_name="owner/repo",
                stars=5,
                forks=0,
                commit_count=total_commits,
                pr_count=0,
                issue_count=0,
                languages={"Python": 1000},
                is_fork=False,
            )
        ],
        owned_repo_count=1,
    )


def test_coding_ability_cold_start_no_repos_no_assessment():
    result = mechanical_scores.coding_ability(
        GithubAnalysis(),
        commit_population=[],
        quality_score=None,
        assessment_score=None,
        assessment_population=[],
    )
    assert result.value is None


def test_coding_ability_github_only_renormalizes_missing_terms():
    result = mechanical_scores.coding_ability(
        _analysis_with_commits(150),
        commit_population=[],  # below min_population -> fallback formula
        quality_score=None,
        assessment_score=None,
        assessment_population=[],
    )
    assert result.value is not None
    assert 0 <= result.value <= 100


def test_coding_ability_uses_assessment_when_available():
    result = mechanical_scores.coding_ability(
        _analysis_with_commits(150),
        commit_population=[],
        quality_score=80.0,
        assessment_score=90.0,
        assessment_population=[float(v) for v in range(1, 51)],  # >= min_population(10)
    )
    assert result.value is not None
    assert "assessment" in result.rationale


def test_problem_solving_none_without_assessment():
    result = mechanical_scores.problem_solving(None, [])
    assert result.value is None


def test_problem_solving_winsorized_percentile_with_population():
    population = [float(v) for v in range(1, 101)]
    result = mechanical_scores.problem_solving(50.0, population)
    assert result.value is not None
    assert 0 <= result.value <= 100


def test_community_participation_cold_start():
    result = mechanical_scores.community_participation(GithubAnalysis(), star_population=[])
    assert result.value is None


def test_community_participation_falls_back_below_min_population():
    analysis = GithubAnalysis(repos=[], total_stars=50, external_contributions=2)
    result = mechanical_scores.community_participation(analysis, star_population=[])
    assert result.value is not None


def test_leadership_cold_start():
    result = mechanical_scores.leadership(GithubAnalysis(), leadership_population=[])
    assert result.value is None


def test_leadership_percentile_normalized_against_population():
    analysis = GithubAnalysis(owned_repo_count=3, pr_review_count=2)
    population = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = mechanical_scores.leadership(analysis, leadership_population=population)
    assert result.value is not None


def test_technical_consistency_insufficient_history():
    result = mechanical_scores.technical_consistency(GithubAnalysis(commit_activity_weekly=[1, 0, 0, 0]))
    assert result.value is None
