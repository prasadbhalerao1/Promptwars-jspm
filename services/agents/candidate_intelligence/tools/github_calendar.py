"""GitHub GraphQL contribution calendar — Codolio-style "Development Stats" (the classic
green-square calendar, current/longest streak, total contributions).

The REST API (services/agents/candidate_intelligence/tools/github.py) has no equivalent
of `contributionsCollection` — that data only exists via GitHub's GraphQL v4 API, and
GraphQL requires an authenticated token (no unauthenticated GraphQL calls), so this can
only run with the candidate's own OAuth access token, right after
`services/api/modules/candidates/router.py`'s `github_oauth_callback` obtains one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import httpx
from services.api.core.config import get_settings

_GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

_CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    bio
    company
    websiteUrl
    createdAt
    followers {
      totalCount
    }
    following {
      totalCount
    }
    repositories(privacy: PUBLIC) {
      totalCount
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


class GithubCalendarUnavailable(Exception):
    pass


@dataclass
class ContributionDay:
    date: str
    count: int


@dataclass
class GithubCalendar:
    total_contributions: int
    current_streak: int
    longest_streak: int
    active_days: int
    bio: str | None = None
    company: str | None = None
    website_url: str | None = None
    account_created_at: str | None = None
    followers: int = 0
    following: int = 0
    public_repos: int = 0
    days: list[ContributionDay] = field(default_factory=list)


def _compute_streaks(days: list[ContributionDay]) -> tuple[int, int, int]:
    """Returns (current_streak, longest_streak, active_days). `days` must be date-ascending."""
    longest = current = 0
    active_days = 0
    today = date.today()

    for day in days:
        if day.count > 0:
            active_days += 1
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    # Current streak counts backward from today (or yesterday, so a day still in
    # progress with no contributions yet doesn't zero out an ongoing streak).
    by_date = {d.date: d.count for d in days}
    streak = 0
    cursor = today
    if by_date.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    while True:
        count = by_date.get(cursor.isoformat())
        if count is None or count == 0:
            break
        streak += 1
        cursor -= timedelta(days=1)

    return streak, longest, active_days


async def fetch_github_calendar(github_username: str, access_token: str) -> GithubCalendar:
    """Fetches the last 365 days of contribution activity via GitHub's GraphQL API."""
    now = datetime.now(timezone.utc)
    variables = {
        "login": github_username,
        "from": (now - timedelta(days=365)).isoformat(),
        "to": now.isoformat(),
    }

    async with httpx.AsyncClient(timeout=get_settings().github_http_timeout_seconds) as client:
        response = await client.post(
            _GITHUB_GRAPHQL_URL,
            json={"query": _CONTRIBUTIONS_QUERY, "variables": variables},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise GithubCalendarUnavailable(f"GitHub GraphQL returned {response.status_code}")

    payload = response.json()
    if payload.get("errors"):
        raise GithubCalendarUnavailable(str(payload["errors"]))

    user = payload.get("data", {}).get("user")
    if user is None:
        raise GithubCalendarUnavailable("github_user_not_found")

    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        ContributionDay(date=d["date"], count=d["contributionCount"])
        for week in calendar["weeks"]
        for d in week["contributionDays"]
    ]
    current_streak, longest_streak, active_days = _compute_streaks(days)

    return GithubCalendar(
        total_contributions=calendar["totalContributions"],
        current_streak=current_streak,
        longest_streak=longest_streak,
        active_days=active_days,
        bio=user.get("bio"),
        company=user.get("company"),
        website_url=user.get("websiteUrl"),
        account_created_at=user.get("createdAt"),
        followers=user["followers"]["totalCount"],
        following=user["following"]["totalCount"],
        public_repos=user["repositories"]["totalCount"],
        days=days,
    )
