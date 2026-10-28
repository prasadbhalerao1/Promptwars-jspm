"""Contribution Report Agent — FR-3.3. Node contract: constraints.md §2.3. Rules only —
assembles the final per-member rows from `contribution_weighting`'s output. The optional
Haiku narrative summary described in doc 03 §5 is intentionally left for a follow-up
(the numeric breakdown + anomaly note already satisfies FR-3.2/3.3's actual requirement
of showing the raw components, not just a bare share)."""

from services.agents.assessment.state import ContributionState


async def run(state: ContributionState) -> dict:
    results = []
    for username, detail in state["shares"].items():
        results.append(
            {
                "github_username": username,
                "contribution_share": detail["share"],
                "commits": detail["raw"]["commits"],
                "lines_survived": detail["raw"]["lines_survived"],
                "prs_opened": detail["raw"]["prs_opened"],
                "prs_reviewed": detail["raw"]["prs_reviewed"],
                "anomaly_note": detail["anomaly_note"],
            }
        )
    return {"results": results}
