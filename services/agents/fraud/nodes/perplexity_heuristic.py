"""Perplexity Heuristic Agent node + verdict in one (doc 06 §4's AI-Generated Content
Signal subgraph is the simplest of the four — one detection step, one confidence-banded
signal). Doc 06 §8: AI-content signals must be corroborated by at least one independent
signal before ever contributing to an `upheld` decision — this node NEVER raises a flag
by itself even at high score; it only ever produces a `should_flag=False` verdict with
the signal recorded for a human/other-signal combination to consider. The "AI-generated
content (high confidence only)" penalty in doc 08 §10's table only applies once a human
has upheld the flag after reviewing this signal alongside other context — this pipeline
does not auto-raise on this signal alone, by design (the most conservative option per
doc 06's own guidance)."""

from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.perplexity_heuristic import compute_ai_content_signal

FLAG_TYPE = "ai_generated_content"
_HIGH_SCORE_THRESHOLD = 75.0


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    result = compute_ai_content_signal(ctx.get("sections", []))
    signal = {
        "signal_type": "ai_content_heuristic",
        "score": result["score"],
        "confidence_label": result["confidence_label"],
        "evidence": result["rationale"],
    }

    # should_flag stays False here by design (see module docstring) — this signal alone
    # never crosses into "raised for review" status; it's surfaced via
    # verification_records for a human reviewer (or a corroborating signal) to weigh, not
    # auto-raised as a standalone fraud_flags row.
    high_score = result["score"] is not None and result["score"] >= _HIGH_SCORE_THRESHOLD and result["confidence_label"] == "medium"
    verdict = {
        "flag_type": FLAG_TYPE,
        "should_flag": False,
        "confidence_label": result["confidence_label"],
        "evidence": [result["rationale"]] + ([f"Flagged sections: {result['flagged_sections']}"] if high_score else []),
    }
    return {"signals": [signal], "verdict": verdict}
