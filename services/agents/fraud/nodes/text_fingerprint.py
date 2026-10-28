from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.text_fingerprint import (
    SIMILARITY_FLAG_THRESHOLD,
    find_similar_profiles,
)


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    results = find_similar_profiles(ctx.get("profile_text", ""), ctx.get("text_corpus", []))
    top = results[0] if results else None
    signal = {
        "signal_type": "text_fingerprint",
        "score": top["similarity"] * 100 if top else None,
        "confidence_label": "high" if top and top["similarity"] >= SIMILARITY_FLAG_THRESHOLD else "low",
        "evidence": top["evidence"] if top else "No comparable profile text in the corpus.",
    }
    # Only this node's own key — `merge_context` folds it into the shared dict. Critical
    # here: this node fans out in parallel with `photo_hash` in `duplicate_graph`.
    return {"signals": [signal], "context": {"text_fingerprint_results": results}}
