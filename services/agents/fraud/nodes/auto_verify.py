from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.auto_verify import auto_verify


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    lookup = ctx["issuer_lookup_result"]
    result = auto_verify(ctx.get("credential_id"), lookup.get("page_text_sample", ""), lookup.get("http_status"))
    signal = {
        "signal_type": "auto_verify",
        "score": 100.0 if result["verified"] else (0.0 if result["verified"] is False else None),
        "confidence_label": result["confidence_label"],
        "evidence": result["evidence"],
    }
    # Only this node's own key — `merge_context` folds it into the shared dict.
    return {"signals": [signal], "context": {"auto_verify_result": result}}
