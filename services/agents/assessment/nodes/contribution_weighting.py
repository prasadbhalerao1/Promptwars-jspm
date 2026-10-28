"""Contribution Weighting Agent — FR-3.2. Node contract: constraints.md §2.3."""

from services.agents.assessment.state import ContributionState
from services.agents.assessment.tools.contribution_weighting import compute_shares
from services.agents.assessment.tools.github_contribution import MemberCommitStats


async def run(state: ContributionState) -> dict:
    stats = {
        username: MemberCommitStats(github_username=username, **{k: v for k, v in raw.items() if k != "github_username"})
        for username, raw in state["raw_stats"].items()
    }
    shares = compute_shares(stats)
    return {"shares": shares}
