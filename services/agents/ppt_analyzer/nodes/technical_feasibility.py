"""Technical Feasibility Agent — doc 04 §4 (FR-5). Node contract: constraints.md §2.3.

Has TWO incoming edges in graph.py (content_extraction AND slide_image_ocr, matching
the doc's mermaid diagram) — LangGraph waits for both predecessors before running this
node, so `slide_ocr_notes` is guaranteed populated (possibly empty) by the time this runs.
"""

import asyncio

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.repo_crosscheck import fetch_repo_evidence
from services.agents.ppt_analyzer.tools.rubric_scoring import (
    PitchScoringUnavailable,
    score_technical_feasibility,
)
from services.agents.ppt_analyzer.tools.text import slides_text
from services.api.core.llm import validated_score


def _ocr_context(slide_ocr_notes: list[dict]) -> str | None:
    parts = [
        f"Slide {n['index']}: {n.get('diagram_summary') or n.get('ocr_text')}"
        for n in slide_ocr_notes
        if n.get("diagram_summary") or n.get("ocr_text")
    ]
    return "\n".join(parts) or None


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    if not slides:
        return {"technical_feasibility": {"value": None, "rationale": "No slide text extracted.", "gaps": []}}

    ocr_context = _ocr_context(state.get("slide_ocr_notes") or [])
    # Blocking PyGithub calls — run off-thread so this async node doesn't stall the
    # event loop, same pattern as candidate_intelligence/nodes/github_analysis.py.
    repo_evidence = await asyncio.to_thread(fetch_repo_evidence, state.get("linked_repo"))

    try:
        result = await score_technical_feasibility(slides_text(slides), ocr_context, repo_evidence)
        return {
            "technical_feasibility": {
                "value": validated_score(result.get("score")),
                "rationale": result.get("rationale"),
                "gaps": result.get("gaps", []),
            }
        }
    except PitchScoringUnavailable as exc:
        return {"technical_feasibility": {"value": None, "rationale": f"unavailable: {exc}", "gaps": []}}
