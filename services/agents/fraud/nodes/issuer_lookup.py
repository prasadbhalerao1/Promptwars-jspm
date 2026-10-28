from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.issuer_lookup import lookup_issuer


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    result = await lookup_issuer(
        ctx.get("issuer"), ctx.get("credential_id"), ctx.get("trusted_issuers") or []
    )
    signal = {
        "signal_type": "issuer_lookup",
        "score": None,
        "confidence_label": "high" if result["resolvable"] else "low",
        "evidence": result["evidence"],
    }
    # Stashed for the conditional edge + downstream nodes (auto_verify needs
    # page_text_sample/http_status; the router needs the resolvable flag to decide which
    # branch ran) — merged back into context rather than a top-level key, since context
    # isn't reduced/appended like signals (LangGraph's default "last write wins" is fine
    # here, only one node ever writes `context`).
    # Only this node's own key — `merge_context` folds it into the shared dict.
    return {"signals": [signal], "context": {"issuer_lookup_result": result}}
