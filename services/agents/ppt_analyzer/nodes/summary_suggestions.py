"""Summary & Suggestions Agent — doc 04 §4 (FR-7/FR-8). Node contract: constraints.md §2.3.

FR-8 requires suggestions "grounded in the specific rubric gaps found" — those gaps are
collected directly from the 3 scoring agents' structured output regardless of whether
the LLM summary call itself succeeds, so suggestions still populate even when
`ANTHROPIC_API_KEY` is missing (rule-based fallback: surface the raw gaps verbatim,
never fabricate advice that isn't grounded in an actual finding).
"""

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.rubric_scoring import PitchScoringUnavailable, generate_summary
from services.agents.ppt_analyzer.tools.text import slides_text


def _collect_gaps(state: PitchAnalysisState) -> list[str]:
    gaps: list[str] = []
    presentation_quality = state.get("presentation_quality") or {}
    gaps.extend(presentation_quality.get("gaps", []))

    innovation_business = state.get("innovation_business") or {}
    gaps.extend(innovation_business.get("innovation", {}).get("gaps", []))
    gaps.extend(innovation_business.get("business_potential", {}).get("gaps", []))

    technical_feasibility = state.get("technical_feasibility") or {}
    gaps.extend(technical_feasibility.get("gaps", []))

    # De-dup while preserving order (innovation/business_potential currently share the
    # same `gaps` list from one LLM call, so duplicates are expected without this).
    seen: set[str] = set()
    unique_gaps = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            unique_gaps.append(g)
    return unique_gaps


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    gaps = _collect_gaps(state)

    ai_signal = state.get("ai_content_signal") or {}
    if ai_signal.get("flagged_sections"):
        gaps.append(
            f"AI-content heuristic flagged {len(ai_signal['flagged_sections'])} slide(s) for review "
            f"(confidence: {ai_signal.get('confidence_label')}) — this is a signal, not a verdict."
        )

    plagiarism_matches = state.get("plagiarism_matches") or []
    if plagiarism_matches:
        gaps.append(
            f"{len(plagiarism_matches)} slide(s) matched prior submissions above the similarity "
            "threshold — review for originality."
        )

    suggestions = gaps  # rule-based fallback: the gaps themselves ARE grounded suggestions (FR-8)

    if not slides:
        return {"summary": "No slide content could be extracted from this deck.", "suggestions": suggestions}

    try:
        summary = await generate_summary(slides_text(slides))
    except PitchScoringUnavailable as exc:
        summary = f"Summary unavailable ({exc}). See per-section rubric scores and suggestions below."

    return {"summary": summary, "suggestions": suggestions}
