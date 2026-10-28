"""Combines Structural Similarity + Public-Repo Cross-Check into one plagiarism verdict.
Doc 06 §8: "AI-content and plagiarism signals are probabilistic, never forensic-grade —
must be corroborated by at least one independent signal" — here, a structural match
above threshold against ANOTHER CANDIDATE's submission is itself the primary evidence
(it's a direct pairwise comparison, not a statistical heuristic), so it alone is
sufficient to flag; the public-repo cross-check is additional corroborating evidence
attached to the same flag when it also fires."""

from services.agents.fraud.state import FraudCheckState
from services.agents.fraud.tools.structural_similarity import SIMILARITY_FLAG_THRESHOLD

FLAG_TYPE = "code_plagiarism"


async def run(state: FraudCheckState) -> dict:
    ctx = state["context"]
    structural_results = ctx.get("structural_similarity_results", [])
    top = structural_results[0] if structural_results else None
    github_result = ctx.get("github_crosscheck_result", {"matches": [], "evidence": ""})

    evidence: list[str] = []
    should_flag = False
    if top and top["similarity"] >= SIMILARITY_FLAG_THRESHOLD:
        should_flag = True
        evidence.append(top["evidence"])
    if github_result["matches"]:
        should_flag = True
        evidence.append(github_result["evidence"])

    confidence_label = "high" if (top and top["similarity"] >= 0.9) else ("medium" if should_flag else "low")

    verdict = {
        "flag_type": FLAG_TYPE,
        "should_flag": should_flag,
        "confidence_label": confidence_label,
        "evidence": evidence or ["No structural similarity or public-repo match found above threshold."],
    }
    return {"verdict": verdict}
