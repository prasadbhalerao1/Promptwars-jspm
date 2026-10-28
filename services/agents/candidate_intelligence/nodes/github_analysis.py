"""GitHub Analysis Agent — doc 01 §4. Node contract: constraints.md §2.3.

Returns only the keys it changes — see resume_parser.py's note on why (parallel fan-out).
"""

import asyncio

from services.agents.candidate_intelligence.state import CandidateProfileState
from services.agents.candidate_intelligence.tools.github import fetch_github_analysis


async def run(state: CandidateProfileState) -> dict:
    if not state.get("github_username"):
        return {}

    # fetch_github_analysis makes ~dozens of sequential blocking PyGithub HTTP calls
    # (per doc 01 §10's <30s ingestion NFR) — run off-thread so it doesn't stall the
    # single-threaded event loop for every other in-flight request, same pattern as
    # services/api/core/llm.py's blocking SDK calls.
    analysis = await asyncio.to_thread(
        fetch_github_analysis, state["github_username"], state.get("github_access_token")
    )
    return {"github_raw": analysis}
