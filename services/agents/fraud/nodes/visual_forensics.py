from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.visual_forensics import assess_visual_forensics


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    result = await assess_visual_forensics(
        ctx.get("issuer"),
        ctx.get("title"),
        ctx.get("credential_id"),
        ctx.get("ocr_confidence"),
        ctx.get("certificate_image_url"),
    )
    signal = {
        "signal_type": "visual_forensics",
        "score": None,
        "confidence_label": result["confidence_label"],
        "evidence": result["evidence"],
    }
    # Only this node's own key — `merge_context` folds it into the shared dict.
    return {"signals": [signal], "context": {"visual_forensics_result": result}}
