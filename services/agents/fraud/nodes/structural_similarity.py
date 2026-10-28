import asyncio

from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.structural_similarity import (
    SIMILARITY_FLAG_THRESHOLD,
    compute_structural_similarity,
)


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    # O(corpus-size) CPU-bound pairwise comparison — keep it off the event loop.
    results = await asyncio.to_thread(
        compute_structural_similarity,
        ctx.get("code", ""),
        ctx.get("corpus", []),
        ctx.get("language_hint", "python"),
    )
    top = results[0] if results else None
    signal = {
        "signal_type": "structural_similarity",
        "score": top["similarity"] * 100 if top else None,
        "confidence_label": "high" if top and top["similarity"] >= SIMILARITY_FLAG_THRESHOLD else "low",
        "evidence": top["evidence"] if top else "No comparable submissions in the corpus.",
    }
    # Return only this node's own context key — `merge_context` folds it into the shared
    # dict, so returning `{**ctx, ...}` would clobber a parallel node's contribution.
    return {"signals": [signal], "context": {"structural_similarity_results": results}}
