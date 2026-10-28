"""Static Analysis Agent — FR-1.3. Node contract: constraints.md §2.3."""

import asyncio

from services.agents.assessment.state import VerificationState
from services.agents.assessment.tools.static_analysis import run_static_analysis


async def run(state: VerificationState) -> dict:
    source = state["code_or_answers"].get("code", "")
    if not source:
        # MCQ / project_analysis submissions have no pasted source to statically analyze.
        return {"static_analysis": {"skipped": "no source code in this submission type"}}
    # radon + lizard + bandit: CPU-bound AST walking plus temp-file disk I/O —
    # keep it off the event loop.
    return {"static_analysis": await asyncio.to_thread(run_static_analysis, source)}
