"""Combines whichever branch ran (Auto-Verify or Visual Forensics — doc 06 §4's
Certificate Verification subgraph) into a single certificate verdict. Conservative by
design (doc 06's "when unsure, pick the more conservative option"): only a CONFIRMED
non-match (`auto_verify_result.verified is False`) or a `high` visual-forensics suspicion
crosses the flag-raising bar — an inconclusive/unreachable check never raises a flag on
its own, it's still recorded as a `verification_records` row (full evidence trail) but
doesn't accuse anyone.

An unrecognized issuer (`issuer_lookup_result.is_recognized_issuer is False`) is always
recorded as its own `verification_records` signal (via `nodes/issuer_lookup.py`), but
only becomes its own `unrecognized_issuer` FraudFlag verdict when the other check
(auto-verify/visual-forensics) didn't already find something concrete to flag — a
confirmed non-match or high visual suspicion is a stronger, more specific claim and takes
priority over the issuer being unrecognized. This keeps "unrecognized issuer" as its own
distinct, lower-confidence signal (still requires human review before it affects
anything, same as every other flag type) rather than folding it into `fake_certificate`'s
verdict, which would conflate "this credential looks forged" with "we simply don't have
this issuer in our trusted registry yet"."""

from services.agents.fraud.state import FraudCheckState

FLAG_TYPE = "fake_certificate"
UNRECOGNIZED_ISSUER_FLAG_TYPE = "unrecognized_issuer"


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    auto_verify_result = ctx.get("auto_verify_result")
    visual_result = ctx.get("visual_forensics_result")
    issuer_lookup_result = ctx.get("issuer_lookup_result")

    # `confirmed_genuine` only becomes True when a check POSITIVELY confirmed the
    # credential — auto-verify actually matched it against the issuer's own page. A
    # visual-forensics result, even a "low" suspicion one, is never treated as a positive
    # confirmation, just "not obviously fake" — so it must NOT suppress the
    # unrecognized-issuer signal below the way a genuine auto-verify match should.
    confirmed_genuine = False

    if auto_verify_result is not None:
        if auto_verify_result["verified"] is False:
            return {
                "verdict": {
                    "flag_type": FLAG_TYPE,
                    "should_flag": True,
                    "confidence_label": auto_verify_result["confidence_label"],
                    "evidence": [auto_verify_result["evidence"]],
                }
            }
        confirmed_genuine = True
        verdict = {
            "flag_type": FLAG_TYPE,
            "should_flag": False,
            "confidence_label": auto_verify_result["confidence_label"],
            "evidence": [auto_verify_result["evidence"]],
        }
    elif visual_result is not None:
        if visual_result["suspicion_label"] == "high":
            return {
                "verdict": {
                    "flag_type": FLAG_TYPE,
                    "should_flag": True,
                    "confidence_label": visual_result["confidence_label"],
                    "evidence": visual_result["evidence"] if isinstance(visual_result["evidence"], list) else [visual_result["evidence"]],
                }
            }
        verdict = {
            "flag_type": FLAG_TYPE,
            "should_flag": False,
            "confidence_label": visual_result["confidence_label"],
            "evidence": visual_result["evidence"] if isinstance(visual_result["evidence"], list) else [visual_result["evidence"]],
        }
    else:
        verdict = {
            "flag_type": FLAG_TYPE,
            "should_flag": False,
            "confidence_label": "low",
            "evidence": ["No verification branch produced a usable result."],
        }

    # Neither branch found a strong reason to flag on its own, and nothing positively
    # confirmed this specific credential as genuine — an unrecognized issuer is the
    # next-strongest signal available, still routed through the same human-review-
    # required flag mechanism, never auto-rejecting.
    if (
        not confirmed_genuine
        and issuer_lookup_result is not None
        and issuer_lookup_result.get("is_recognized_issuer") is False
    ):
        return {
            "verdict": {
                "flag_type": UNRECOGNIZED_ISSUER_FLAG_TYPE,
                "should_flag": True,
                "confidence_label": "medium",
                "evidence": [
                    issuer_lookup_result["evidence"],
                    "No other verification signal positively confirmed this certificate as genuine, "
                    "so the unrecognized issuer is the deciding factor for review.",
                ],
            }
        }

    return {"verdict": verdict}
