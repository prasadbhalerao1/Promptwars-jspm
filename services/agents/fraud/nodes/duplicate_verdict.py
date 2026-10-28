"""Combines Text Fingerprint + Photo Perceptual-Hash into one duplicate-profile verdict.
Doc 06 §8's "corroborated by at least one independent signal" rule is applied literally
here: either signal alone crossing its threshold is real pairwise evidence (a specific
other candidate's text/photo), same reasoning as `plagiarism_verdict.py`."""

from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.photo_hash import HAMMING_DISTANCE_FLAG_THRESHOLD
from services.agents.fraud.tools.text_fingerprint import SIMILARITY_FLAG_THRESHOLD

FLAG_TYPE = "duplicate_profile"


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    text_results = ctx.get("text_fingerprint_results", [])
    photo_results = ctx.get("photo_hash_results", [])
    top_text = text_results[0] if text_results else None
    top_photo = photo_results[0] if photo_results else None

    evidence: list[str] = []
    should_flag = False
    if top_text and top_text["similarity"] >= SIMILARITY_FLAG_THRESHOLD:
        should_flag = True
        evidence.append(top_text["evidence"])
    if top_photo and top_photo["hamming_distance"] <= HAMMING_DISTANCE_FLAG_THRESHOLD:
        should_flag = True
        evidence.append(top_photo["evidence"])

    confidence_label = "high" if len(evidence) >= 2 else ("medium" if should_flag else "low")

    verdict = {
        "flag_type": FLAG_TYPE,
        "should_flag": should_flag,
        "confidence_label": confidence_label,
        "evidence": evidence or ["No near-duplicate profile text or photo found above threshold."],
    }
    return {"verdict": verdict}
