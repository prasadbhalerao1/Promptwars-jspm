"""LeetCode public GraphQL API — Codolio-style "Problem Solving Stats".

Unlike GitHub's GraphQL API, LeetCode's `https://leetcode.com/graphql` endpoint serves a
user's public profile stats (questions solved by difficulty, submission calendar, contest
rating history) without any auth token — connection is by username only, same as Codolio.
This is an unofficial/undocumented API (LeetCode ships no public API docs or SDK), so
failures are treated as routine (profile private, username typo'd, schema drift) rather
than exceptional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx
from services.api.core.config import get_settings

_LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

_PROFILE_QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      ranking
      reputation
    }
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
  }
  userContestRankingHistory(username: $username) {
    attended
    rating
    ranking
    contest {
      title
      startTime
    }
  }
}
"""

_CALENDAR_QUERY = """
query userCalendar($username: String!) {
  matchedUser(username: $username) {
    userCalendar {
      activeYears
      streak
      totalActiveDays
      submissionCalendar
    }
  }
}
"""


class LeetcodeUnavailable(Exception):
    pass


@dataclass
class ContestPoint:
    title: str
    rating: float
    ranking: int
    start_time: int


@dataclass
class LeetcodeStats:
    total_solved: int
    easy_solved: int
    medium_solved: int
    hard_solved: int
    ranking: int | None
    current_streak: int
    total_active_days: int
    submission_calendar: dict[str, int]  # unix-day-timestamp (str) -> submission count
    contest_history: list[ContestPoint] = field(default_factory=list)
    latest_rating: float | None = None


async def _graphql(query: str, username: str) -> dict:
    async with httpx.AsyncClient(timeout=get_settings().leetcode_http_timeout_seconds) as client:
        response = await client.post(
            _LEETCODE_GRAPHQL_URL,
            json={"query": query, "variables": {"username": username}},
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
        )
    if response.status_code != 200:
        raise LeetcodeUnavailable(f"LeetCode GraphQL returned {response.status_code}")
    payload = response.json()
    if payload.get("errors"):
        raise LeetcodeUnavailable(str(payload["errors"]))
    return payload.get("data") or {}


async def fetch_leetcode_stats(leetcode_username: str) -> LeetcodeStats:
    profile_data = await _graphql(_PROFILE_QUERY, leetcode_username)
    matched_user = profile_data.get("matchedUser")
    if matched_user is None:
        raise LeetcodeUnavailable("leetcode_user_not_found")

    counts = {row["difficulty"]: row["count"] for row in matched_user["submitStatsGlobal"]["acSubmissionNum"]}

    contest_history = [
        ContestPoint(
            title=entry["contest"]["title"],
            rating=entry["rating"],
            ranking=entry["ranking"],
            start_time=entry["contest"]["startTime"],
        )
        for entry in (profile_data.get("userContestRankingHistory") or [])
        if entry.get("attended")
    ]
    latest_rating = contest_history[-1].rating if contest_history else None

    calendar_data = await _graphql(_CALENDAR_QUERY, leetcode_username)
    user_calendar = (calendar_data.get("matchedUser") or {}).get("userCalendar") or {}

    submission_calendar_raw = user_calendar.get("submissionCalendar") or "{}"
    try:
        submission_calendar = {k: int(v) for k, v in json.loads(submission_calendar_raw).items()}
    except (ValueError, TypeError):
        submission_calendar = {}

    return LeetcodeStats(
        total_solved=counts.get("All", 0),
        easy_solved=counts.get("Easy", 0),
        medium_solved=counts.get("Medium", 0),
        hard_solved=counts.get("Hard", 0),
        ranking=matched_user["profile"]["ranking"],
        current_streak=user_calendar.get("streak", 0),
        total_active_days=user_calendar.get("totalActiveDays", 0),
        submission_calendar=submission_calendar,
        contest_history=contest_history,
        latest_rating=latest_rating,
    )
