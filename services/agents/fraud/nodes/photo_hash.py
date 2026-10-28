from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.photo_hash import (
    HAMMING_DISTANCE_FLAG_THRESHOLD,
    find_duplicate_photos,
)


async def run(state: FraudCheckState) -> dict:
    # Return ONLY this node's own context key, never `{**ctx, ...}`. Every sibling node in
    # this package carries the same note: `context` is reduced by `merge_context`, which
    # merges partial dicts, so echoing the whole context back writes a stale copy of other
    # nodes' results over theirs. That is harmless only because `duplicate_graph` currently
    # runs sequentially — parallelizing it (as doc 06's own diagram shows) would have made
    # this node silently clobber `text_fingerprint_results` and disable half of duplicate
    # detection, with no error anywhere.
    ctx = state["context"]
    target_hash = ctx.get("photo_hash")
    if not target_hash:
        signal = {
            "signal_type": "photo_hash",
            "score": None,
            "confidence_label": "low",
            "evidence": "No profile photo available to hash (candidate has not uploaded one).",
        }
        return {"signals": [signal], "context": {"photo_hash_results": []}}

    results = find_duplicate_photos(target_hash, ctx.get("photo_corpus", []))
    top = results[0] if results else None
    signal = {
        "signal_type": "photo_hash",
        "score": None,
        "confidence_label": "high" if top and top["hamming_distance"] <= HAMMING_DISTANCE_FLAG_THRESHOLD else "low",
        "evidence": top["evidence"] if top else "No matching profile photo found in the corpus.",
    }
    return {"signals": [signal], "context": {"photo_hash_results": results}}
