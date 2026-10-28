"""Innovation & Business Impact Agent — doc 04 §4 (FR-4). Node contract: constraints.md §2.3.

Produces both the Innovation and Business Potential components of the Overall Pitch
Score in one call (doc 04 §3's agent registry: "rubric + Qdrant novelty check").
"""

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.rubric_scoring import (
    PitchScoringUnavailable,
    score_innovation_business,
)
from services.agents.ppt_analyzer.tools.text import slides_text
from services.api.core.llm import validated_score


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    if not slides:
        return {
            "innovation_business": {
                "innovation": {"value": None, "rationale": "No slide text extracted.", "gaps": []},
                "business_potential": {"value": None, "rationale": "No slide text extracted.", "gaps": []},
            }
        }

    try:
        # Scored on the deck alone, with no novelty context.
        #
        # This node used to read `state["plagiarism_matches"]` and fold a "N slides matched
        # prior submissions" line into the prompt, described in a comment as data that "may
        # not have landed in this superstep yet". It never had: `similarity_plagiarism` sits
        # a full superstep further down a parallel branch
        # (content_extraction -> slide_embedding -> similarity_plagiarism), while this node
        # runs immediately after content_extraction. So the context was always None, and had
        # the scheduling ever changed, the same deck would have scored differently run to run
        # — nondeterminism in a number persisted against a real submission and shown to
        # organizers.
        #
        # The novelty signal is not lost. `similarity_plagiarism` is joined by `aggregation`,
        # and the matches are surfaced to the reader directly as `plagiarism_matches` rather
        # than silently discounted inside a score they cannot inspect.
        result = await score_innovation_business(slides_text(slides))
        gaps = result.get("gaps", [])
        return {
            "innovation_business": {
                "innovation": {
                    "value": validated_score(result.get("innovation_score")),
                    "rationale": result.get("innovation_rationale"),
                    "gaps": gaps,
                },
                "business_potential": {
                    "value": validated_score(result.get("business_potential_score")),
                    "rationale": result.get("business_potential_rationale"),
                    "gaps": gaps,
                },
            }
        }
    except PitchScoringUnavailable as exc:
        unavailable = {"value": None, "rationale": f"unavailable: {exc}", "gaps": []}
        return {"innovation_business": {"innovation": unavailable, "business_potential": dict(unavailable)}}
