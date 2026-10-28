"""Fact-Check Agent node — Flow B, doc 01 §3/§4. Node contract: constraints.md §2.3.

If the fact-check LLM call itself can't run (no API key, API error), this is treated as
a FAILED check, never a silent pass — per doc 01 §10's "zero tolerance for fabricated
experience," an unverifiable document must not be delivered to the candidate as if it
were verified.
"""

from services.agents.candidate_intelligence.document_state import DocumentBuilderState
from services.agents.candidate_intelligence.tools.fact_check import (
    FactCheckUnavailable,
    fact_check_claims,
)


async def run(state: DocumentBuilderState) -> dict:
    try:
        status, findings = await fact_check_claims(
            state["merged_profile"], state["generated_content"], state["document_type"]
        )
    except FactCheckUnavailable as exc:
        return {
            "fact_check_status": "failed",
            "fact_check_findings": [
                {"claim": "fact_check_agent_unavailable", "supported": False, "note": str(exc)}
            ],
        }

    return {"fact_check_status": status, "fact_check_findings": findings}
