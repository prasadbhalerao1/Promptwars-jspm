"""Deterministic GitHub data pull — no LLM involved. FR-1.1 / doc 01 §2.

Uses the candidate's own OAuth token when available (per-candidate auth, never a shared
server-side token) so rate limits and access scope are the candidate's own.
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime

from github import Github
from github.GithubException import GithubException


@dataclass
class RepoSnapshot:
    repo_full_name: str
    stars: int
    forks: int
    commit_count: int
    pr_count: int
    issue_count: int
    languages: dict[str, int]
    is_fork: bool
    topics: list[str] = field(default_factory=list)
    pushed_at: datetime | None = None
    description: str | None = None


@dataclass
class GithubAnalysis:
    repos: list[RepoSnapshot] = field(default_factory=list)
    total_stars: int = 0
    external_contributions: int = 0  # PRs merged into repos the candidate doesn't own
    commit_activity_weekly: list[int] = field(default_factory=list)  # last 52 weeks, own non-fork repos
    # Same weekly totals as above, paired with each week's start date — lets recency
    # weighting use real timestamps instead of assuming index position maps to week
    # offset. Kept as a separate field rather than changing commit_activity_weekly's
    # shape so existing consumers of the plain int list are unaffected.
    commit_activity_weekly_dated: list[tuple[datetime, int]] = field(default_factory=list)
    owned_repo_count: int = 0
    pr_review_count: int = 0


def fetch_github_analysis(
    github_username: str, access_token: str | None = None, max_repos: int = 15
) -> GithubAnalysis:
    """Pulls repo stats, language breakdown, commit cadence, and PR-review activity.

    Bounded to `max_repos` most-recently-pushed repos to keep ingestion under the <30s
    NFR target (doc 01 §10) — a candidate's full history isn't needed for the mechanical
    sub-scores, just a representative recent sample.
    """
    # retry=None: fail fast on rate limits (GithubException) instead of PyGithub's default
    # backoff-and-retry, which can block for the full rate-limit reset window.
    client = Github(login_or_token=access_token, retry=None) if access_token else Github(retry=None)
    user = client.get_user(github_username)

    analysis = GithubAnalysis()
    repos = sorted(user.get_repos(), key=lambda r: r.pushed_at, reverse=True)[:max_repos]

    for repo in repos:
        if repo.fork:
            is_fork = True
        else:
            is_fork = False
            analysis.owned_repo_count += 1

        try:
            languages = repo.get_languages()
        except GithubException:
            languages = {}

        try:
            commit_count = repo.get_commits().totalCount
        except GithubException:
            commit_count = 0

        try:
            pr_count = repo.get_pulls(state="all").totalCount
        except GithubException:
            pr_count = 0

        try:
            issue_count = repo.get_issues(state="all").totalCount
        except GithubException:
            issue_count = 0

        try:
            topics = repo.get_topics()
        except GithubException:
            topics = []

        analysis.repos.append(
            RepoSnapshot(
                repo_full_name=repo.full_name,
                stars=repo.stargazers_count,
                forks=repo.forks_count,
                commit_count=commit_count,
                pr_count=pr_count,
                issue_count=issue_count,
                languages=languages,
                is_fork=is_fork,
                topics=topics,
                pushed_at=repo.pushed_at,
                description=repo.description,
            )
        )
        analysis.total_stars += repo.stargazers_count

        if not is_fork:
            try:
                weekly = repo.get_stats_commit_activity() or []
                counts = [w.total for w in weekly]
                weeks = [w.week for w in weekly]
                if counts:
                    if not analysis.commit_activity_weekly:
                        analysis.commit_activity_weekly = counts
                        analysis.commit_activity_weekly_dated = list(zip(weeks, counts))
                    else:
                        analysis.commit_activity_weekly = [
                            a + b for a, b in zip(analysis.commit_activity_weekly, counts)
                        ]
                        # Weeks align across repos (GitHub buckets to the same Sunday-
                        # aligned 52-week window for every repo) — sum counts, keep dates.
                        analysis.commit_activity_weekly_dated = [
                            (week, existing_count + new_count)
                            for (week, existing_count), new_count in zip(
                                analysis.commit_activity_weekly_dated, counts
                            )
                        ]
            except GithubException:
                pass

    try:
        # External contributions: merged PRs authored by this user against repos not owned by them.
        issues = client.search_issues(
            query=f"type:pr author:{github_username} is:merged -user:{github_username}"
        )
        analysis.external_contributions = issues.totalCount
    except GithubException:
        analysis.external_contributions = 0

    try:
        reviewed = client.search_issues(query=f"type:pr reviewed-by:{github_username}")
        analysis.pr_review_count = reviewed.totalCount
    except GithubException:
        analysis.pr_review_count = 0

    return analysis


def commit_consistency_score(
    weekly_counts: list[int], weekly_dated: list[tuple[datetime, int]] | None = None
) -> float | None:
    """Technical Consistency mechanical sub-score (doc 08 §1): regularity, not volume.

    Coefficient of variation (stdev/mean) inverted to a 0-100 scale — low variance
    (steady cadence) scores high, bursty/inactive-then-frantic cadence scores low.

    When `weekly_dated` is available, each week is recency-weighted before computing
    mean/stdev (proposed algorithm's "Technical Consistency" section) so a candidate who
    was consistent a year ago but has since gone quiet isn't scored the same as one who
    is consistent right now. Falls back to unweighted CV over `weekly_counts` otherwise.
    """
    active_weeks = [c for c in weekly_counts if c > 0]
    if len(active_weeks) < 4:
        return None  # not enough signal yet — cold start, not a penalty

    if weekly_dated:
        from services.agents.candidate_intelligence.tools.normalization import recency_weight

        weighted_counts = [count * recency_weight(week, half_life_days=180.0) for week, count in weekly_dated]
    else:
        weighted_counts = [float(c) for c in weekly_counts]

    mean = statistics.mean(weighted_counts)
    if mean == 0:
        return None
    cv = statistics.pstdev(weighted_counts) / mean
    base = max(0.0, min(100.0, 100.0 * (1 / (1 + cv))))

    # Long-inactivity penalty: weeks since the most recent active week, on top of CV.
    penalty = 0.0
    bonus = 0.0
    if weekly_dated:
        active_dated = [(week, count) for week, count in weekly_dated if count > 0]
        if active_dated:
            most_recent = max(week for week, _ in active_dated)
            weeks_inactive = max(0.0, recency_weight(most_recent, half_life_days=180.0))
            # weeks_inactive here is actually a decayed weight (1.0 = active now, ->0 = long
            # gap) — invert to a 0-20 point penalty for staleness.
            penalty = 20.0 * (1.0 - weeks_inactive)
        # Sustained activity bonus: rewards candidates active across most of the window,
        # not just a recent burst.
        active_week_fraction = len(active_weeks) / len(weekly_counts)
        if active_week_fraction > 0.75:
            bonus = 10.0 * (active_week_fraction - 0.75) / 0.25

    return max(0.0, min(100.0, base - penalty + bonus))
