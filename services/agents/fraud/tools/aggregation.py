"""Authenticity Aggregation Agent — doc 06 §4, "rules (transparent weighted formula)".
FR-6. Formula is doc 08 §10's explicit canonical version — copied verbatim, not
reinvented:

    AuthenticityScore = max(0, 100 - sum(penalty_k * 1[flag_k.status == 'upheld']))

Only `upheld` flags count — a `raised` flag sitting in the review queue has ZERO effect,
per doc 06 §7/§8's binding "fraud flags never silently affect a score" rule. This
function is pure (no DB access) — the router fetches the candidate's `upheld` flags and
passes them in, then persists the result as a new `authenticity_scores` row.
"""

# Doc 08 §10's penalty table, tunable defaults — logged in .agents/decisions.md as this
# session's chosen weights (the doc explicitly flags these as tunable, not validated).
FLAG_TYPE_PENALTIES: dict[str, float] = {
    "fake_certificate": 30.0,
    "code_plagiarism": 35.0,
    "duplicate_profile": 40.0,
    "ai_generated_content": 15.0,
    # Weaker signal than "fake_certificate" — this means the issuer isn't in the trusted
    # registry yet, not that the credential was positively confirmed forged. Smaller
    # penalty reflects that; still requires a human to move it to 'upheld' before it
    # affects anything, same as every other flag type.
    "unrecognized_issuer": 10.0,
}


def compute_authenticity_score(upheld_flags: list[dict]) -> dict:
    """`upheld_flags` is [{flag_type, id}, ...] — already filtered to status='upheld' by
    the caller (this function has no way to check status itself, so callers MUST filter
    first; never pass raised/dismissed/under_review flags in). Returns
    {score, components} where `components` lists exactly which flags contributed which
    penalty, for the "not a hidden adjustment" provenance trail (same pattern as doc
    08 §1.1's Talent Score re-normalization provenance)."""
    penalties_applied: list[dict] = []
    total_penalty = 0.0
    for flag in upheld_flags:
        penalty = FLAG_TYPE_PENALTIES.get(flag["flag_type"], 10.0)  # unknown flag_type: small default penalty, never zero
        penalties_applied.append({"flag_id": flag["id"], "flag_type": flag["flag_type"], "penalty": penalty})
        total_penalty += penalty

    score = max(0.0, 100.0 - total_penalty)
    return {
        "score": round(score, 1),
        "components": {
            "starting_score": 100.0,
            "penalties_applied": penalties_applied,
            "total_penalty": round(total_penalty, 1),
        },
    }
