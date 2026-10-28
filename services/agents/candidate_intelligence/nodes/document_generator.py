"""Resume/Cover-Letter Generator node — Flow B, doc 01 §3/§4. Node contract:
constraints.md §2.3 (returns only changed keys).

Dispatches on `document_type`; this node runs standalone (no parallel fan-out siblings
in `resume_graph.py`, unlike Flow A), so returning only changed keys isn't strictly
required for correctness here, but kept for consistency with the rest of the module.
"""

from services.agents.candidate_intelligence.document_state import DocumentBuilderState
from services.agents.candidate_intelligence.tools.document_generation import (
    DocumentGenerationUnavailable,
    generate_cover_letter_content,
    generate_resume_content,
)


async def run(state: DocumentBuilderState) -> dict:
    attempts = state.get("attempts", 0) + 1
    try:
        if state["document_type"] == "resume":
            content = await generate_resume_content(state["merged_profile"], state.get("target_job_description"))
        else:
            content = await generate_cover_letter_content(
                state["merged_profile"], state.get("target_job_description") or ""
            )
    except DocumentGenerationUnavailable as exc:
        return {"generation_error": str(exc), "attempts": attempts}

    return {"generated_content": content, "generation_error": None, "attempts": attempts}
