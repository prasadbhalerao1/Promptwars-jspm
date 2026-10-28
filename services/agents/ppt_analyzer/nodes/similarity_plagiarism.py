"""Similarity/Plagiarism Agent — doc 04 §4. Node contract: constraints.md §2.3.

Runs after slide_embedding (needs the embeddings, hence the single incoming edge in
graph.py rather than fanning out straight from content_extraction).
"""

import logging

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.plagiarism import (
    PlagiarismCheckUnavailable,
    find_and_record_matches,
)

logger = logging.getLogger(__name__)


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    embeddings = state.get("slide_embeddings")
    if not slides or not embeddings:
        # Genuinely nothing to match: a deck with no embeddable slide text is
        # unmatchable, which is a real (empty) result rather than a failed check.
        return {"plagiarism_matches": [], "plagiarism_checked": True}

    try:
        matches = find_and_record_matches(state["presentation_id"], slides, embeddings)
    except PlagiarismCheckUnavailable:
        # A broken check must not fail the whole analysis — the four rubric scores are
        # still valid and worth showing. But it must not be reported as a pass either:
        # `plagiarism_checked=False` is what lets the UI say "could not be checked"
        # instead of "no similarity matches found against prior submissions".
        logger.warning(
            "Plagiarism check unavailable for presentation %s",
            state.get("presentation_id"),
            exc_info=True,
        )
        return {"plagiarism_matches": [], "plagiarism_checked": False}

    return {"plagiarism_matches": matches, "plagiarism_checked": True}
