"""AI-Content Heuristic Agent — doc 04 §4 (FR-6). Node contract: constraints.md §2.3."""

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.ai_content_heuristic import compute_ai_content_signal


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    return {"ai_content_signal": compute_ai_content_signal(slides)}
