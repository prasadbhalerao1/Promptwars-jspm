import asyncio

from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.github_crosscheck import crosscheck_public_repos


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    # Blocking PyGithub search call — run off-thread so this async node doesn't stall
    # the event loop, same pattern as candidate_intelligence/nodes/github_analysis.py.
    result = await asyncio.to_thread(
        crosscheck_public_repos, ctx.get("code", ""), ctx.get("candidate_github_username")
    )
    signal = {
        "signal_type": "public_repo_crosscheck",
        "score": None,
        "confidence_label": "medium" if result["matches"] else "low",
        "evidence": result["evidence"],
    }
    # Return only this node's own context key — `merge_context` folds it into the shared
    # dict, so returning `{**ctx, ...}` would clobber a parallel node's contribution.
    return {"signals": [signal], "context": {"github_crosscheck_result": result}}
