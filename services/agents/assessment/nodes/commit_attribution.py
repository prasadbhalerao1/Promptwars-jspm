"""Commit Attribution Agent — FR-3.1. Node contract: constraints.md §2.3."""

import asyncio
from dataclasses import asdict

from services.agents.assessment.state import ContributionState
from services.agents.assessment.tools.github_contribution import attribute_commits


async def run(state: ContributionState) -> dict:
    # Blocking PyGithub calls (per-member commit/PR pulls) — run off-thread so this
    # async node doesn't stall the event loop, same pattern as
    # candidate_intelligence/nodes/github_analysis.py.
    stats = await asyncio.to_thread(
        attribute_commits, state["repo_full_name"], state["github_usernames"], state.get("access_token")
    )
    return {"raw_stats": {username: asdict(s) for username, s in stats.items()}}
