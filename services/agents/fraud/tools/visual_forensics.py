"""Visual Forensics Agent — doc 06 §4, "Haiku + vision... outputs low/medium/high
suspicion, never certainty". Runs only when Issuer Lookup found no verification URL/API
for this issuer (doc 06 §4's Certificate Verification subgraph).

Rules-first (OCR confidence + metadata completeness — cheap, always available, no
network dependency), with an OPTIONAL Haiku vision pass over the certificate image when
one exists (`File.public_url`) and `ANTHROPIC_API_KEY` is configured, matching this
codebase's established "LLM call is a best-effort enhancement layered on a working
rules baseline, never the only path" pattern (e.g. `ppt_analyzer/tools/plagiarism.py`'s
"Haiku for narrative is optional UI-copy enhancement"). Never outputs certainty — always
one of low/medium/high suspicion, per the hard constraint in doc 06 §4/§8.
"""

import asyncio
from functools import lru_cache

import anthropic

from services.api.core.config import get_settings
from services.api.core.tracing import start_llm_generation


@lru_cache(maxsize=1)
def _vision_client(api_key: str) -> anthropic.Anthropic:
    """Cached client — rebuilding the SDK client per certificate is pure overhead."""
    return anthropic.Anthropic(api_key=api_key)

# Below this OCR confidence, the extracted cert fields themselves are unreliable — that's
# a data-quality signal worth surfacing, not proof of forgery, so it only pushes suspicion
# to "medium" at most on its own.
_LOW_OCR_CONFIDENCE_THRESHOLD = 0.55


def _rules_based_suspicion(issuer: str | None, title: str | None, credential_id: str | None, ocr_confidence: float | None) -> dict:
    reasons: list[str] = []
    suspicion_points = 0

    if not issuer:
        reasons.append("No issuer name extracted from the certificate.")
        suspicion_points += 1
    if not title:
        reasons.append("No certificate title/course name extracted.")
        suspicion_points += 1
    if not credential_id:
        reasons.append("No credential ID present — cannot be cross-checked against any issuer record.")
        suspicion_points += 1
    if ocr_confidence is not None and ocr_confidence < _LOW_OCR_CONFIDENCE_THRESHOLD:
        reasons.append(f"Low OCR extraction confidence ({ocr_confidence:.2f}) on the certificate scan.")
        suspicion_points += 1

    if suspicion_points >= 3:
        label = "high"
    elif suspicion_points >= 1:
        label = "medium"
    else:
        label = "low"

    if not reasons:
        reasons.append("Certificate metadata is complete and internally consistent; no rules-based anomaly found.")

    return {"suspicion_label": label, "reasons": reasons}


async def _vision_pass(public_url: str, issuer: str | None, title: str | None) -> dict | None:
    """Best-effort Haiku vision call. Returns None (not an error) if unavailable — the
    rules-based signal above always stands on its own.

    The Anthropic SDK is synchronous, so the network call runs via `asyncio.to_thread`
    to keep it off the event loop. Kept on its own client rather than the
    `services.api.core.llm` gateway: that gateway is provider-agnostic with no
    vision/image content-block support, and this path is gated on `ANTHROPIC_API_KEY`
    independently of `LLM_PROVIDER`.
    """
    settings = get_settings()
    if not settings.anthropic_api_key or not public_url:
        return None
    try:
        client = _vision_client(settings.anthropic_api_key)
        with start_llm_generation(
            name="fraud.visual_forensics",
            model=settings.llm_model_fast,
            input_data={"issuer": issuer, "title": title, "image_url": public_url},
        ) as generation:
            response = await asyncio.to_thread(
                client.messages.create,
                model=settings.llm_model_fast,
                max_tokens=400,
                tools=[
                    {
                        "name": "visual_forensics_verdict",
                        "description": "Layout/font/seal plausibility assessment of a certificate image. Never claim certainty.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "suspicion_label": {"type": "string", "enum": ["low", "medium", "high"]},
                                "rationale": {"type": "string"},
                            },
                            "required": ["suspicion_label", "rationale"],
                        },
                    }
                ],
                tool_choice={"type": "tool", "name": "visual_forensics_verdict"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"This is a certificate image claiming to be issued by '{issuer}' for "
                                    f"'{title}'. Assess layout consistency, font consistency, and whether a "
                                    "seal/signature area looks template-plausible for this issuer. You have "
                                    "no ground-truth genuine template to compare against, so NEVER claim "
                                    "certainty — output only low/medium/high suspicion with a short rationale."
                                ),
                            },
                            {"type": "image", "source": {"type": "url", "url": public_url}},
                        ],
                    }
                ],
            )
            for block in response.content:
                if block.type == "tool_use":
                    generation.update(output=block.input)
                    return block.input
            generation.update(output=None)
    except Exception:
        return None
    return None


async def assess_visual_forensics(
    issuer: str | None,
    title: str | None,
    credential_id: str | None,
    ocr_confidence: float | None,
    public_url: str | None,
) -> dict:
    """Returns {suspicion_label, confidence_label, evidence}. `confidence_label` here
    describes confidence in the SIGNAL itself (per FR-3's "always confidence-banded"
    requirement, extended to this agent too) — this heuristic is not forensic-grade
    (doc 06 §8)."""
    rules = _rules_based_suspicion(issuer, title, credential_id, ocr_confidence)
    vision = await _vision_pass(public_url, issuer, title) if public_url else None

    if vision is not None:
        # Escalate to the higher of the two suspicion labels rather than average —
        # conservative by design (doc 06's "when unsure, pick the more conservative
        # option" guidance), never silently down-weight a rules-based flag because the
        # vision pass happened to look benign.
        order = {"low": 0, "medium": 1, "high": 2}
        final_label = max(rules["suspicion_label"], vision["suspicion_label"], key=lambda l: order[l])
        evidence = rules["reasons"] + [f"Visual forensics (Haiku): {vision['rationale']}"]
        confidence_label = "medium"
    else:
        final_label = rules["suspicion_label"]
        evidence = rules["reasons"]
        # No vision pass ran (no image URL or no API key) — this is metadata-only,
        # capped at "low" confidence in the signal itself.
        confidence_label = "low"

    return {
        "suspicion_label": final_label,
        "confidence_label": confidence_label,
        "evidence": evidence,
    }
