"""Commit Attribution Agent — FR-3.1/3.2, "tools only" per doc 03 §5. Reuses
`candidate_intelligence/tools/github.py`'s exact client-construction/error-handling
pattern (per-repo try/except, `retry=None` to fail fast on rate limits).
"""

import logging
from dataclasses import dataclass

from github import Github
from github.GithubException import GithubException

logger = logging.getLogger(__name__)


@dataclass
class MemberCommitStats:
    github_username: str
    commits: int
    # Net additions across this member's commits — an approximation of "lines that
    # survive to HEAD" (doc 03 §7's exact phrase implies blame-based tracking of what's
    # still present at HEAD, which needs a full git blame pass; commit-level net
    # additions is the practical proxy available from the GitHub REST API without
    # cloning the repo). Documented here, not hidden.
    lines_survived: int
    prs_opened: int
    prs_reviewed: int
    # True when at least one GitHub lookup for this member failed (rate limit, transient
    # 5xx, deleted account). Without it, a swallowed error was indistinguishable from a
    # genuine zero — and a genuine zero renders as "No attributable commits, PRs, or
    # reviews found for this member ... flagged for human review", i.e. a rate-limit
    # blip was silently reported as a real person having contributed nothing.
    data_incomplete: bool = False


def attribute_commits(
    repo_full_name: str, github_usernames: list[str], access_token: str | None = None
) -> dict[str, MemberCommitStats]:
    client = Github(login_or_token=access_token, retry=None) if access_token else Github(retry=None)
    repo = client.get_repo(repo_full_name)

    results: dict[str, MemberCommitStats] = {}
    for username in github_usernames:
        # Each lookup below degrades to an empty/zero result on a GitHub error, which is
        # correct — one member's failed query must not abort attribution for the whole
        # team. What is NOT correct is letting that zero read as a finding, so every
        # failure is recorded and surfaced as `data_incomplete`.
        incomplete = False

        try:
            commits = list(repo.get_commits(author=username))
        except GithubException:
            logger.warning(
                "commit lookup failed for %s on %s — attribution for this member is incomplete",
                username, repo_full_name, exc_info=True,
            )
            commits = []
            incomplete = True

        net_additions = 0
        for c in commits:
            try:
                stats = c.stats
                net_additions += (stats.additions or 0) - (stats.deletions or 0)
            except GithubException:
                # A single unreadable commit understates the line count slightly; it does
                # not make the member's whole record unknown, so it is not escalated.
                continue

        try:
            prs_opened = client.search_issues(
                query=f"repo:{repo_full_name} type:pr author:{username} is:merged"
            ).totalCount
        except GithubException:
            logger.warning("PR-opened lookup failed for %s on %s", username, repo_full_name, exc_info=True)
            prs_opened = 0
            incomplete = True

        try:
            prs_reviewed = client.search_issues(
                query=f"repo:{repo_full_name} type:pr reviewed-by:{username}"
            ).totalCount
        except GithubException:
            logger.warning("PR-reviewed lookup failed for %s on %s", username, repo_full_name, exc_info=True)
            prs_reviewed = 0
            incomplete = True

        results[username] = MemberCommitStats(
            github_username=username,
            commits=len(commits),
            lines_survived=max(0, net_additions),
            prs_opened=prs_opened,
            prs_reviewed=prs_reviewed,
            data_incomplete=incomplete,
        )

    return results
