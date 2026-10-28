"""Perplexity Heuristic Agent — doc 06 §4, "statistical tool, shared approach with doc
04's AI-content agent". FR-3.

Per the assignment file's explicit instruction ("read `services/agents/ppt_analyzer/` for
the exact method before reimplementing... so the two don't diverge in method"), this
reuses `ppt_analyzer/tools/ai_content_heuristic.py`'s private per-text scoring function
directly rather than re-deriving the burstiness/lexical-diversity formula a second time —
the two detectors must agree on what "AI-generated-sounding text" means. Only the
aggregation across sections (a resume's summary/experience bullets, vs. a deck's slides)
differs, since the input shape differs (free text sections vs. slide dicts)."""

from services.agents.ppt_analyzer.tools.ai_content_heuristic import _slide_ai_likelihood
from services.api.common.constants import AI_CONTENT_FLAG_THRESHOLD


def compute_ai_content_signal(sections: list[str]) -> dict:
    """`sections` is free-form text blocks (e.g. resume summary, each experience bullet
    group). Returns {score, confidence_label, flagged_sections, rationale} — identical
    shape/semantics to doc 04's agent, per FR-3's "shared approach" requirement."""
    per_section: list[tuple[int, float]] = []
    for idx, text in enumerate(sections):
        score = _slide_ai_likelihood(text or "")
        if score is not None:
            per_section.append((idx, score))

    if not per_section:
        return {
            "score": None,
            "confidence_label": "low",
            "flagged_sections": [],
            "rationale": "Not enough extracted text to compute a meaningful AI-content signal.",
        }

    avg_score = round(sum(s for _, s in per_section) / len(per_section), 1)
    flagged = [f"section_{i}" for i, s in per_section if s >= AI_CONTENT_FLAG_THRESHOLD]
    confidence_label = "medium" if len(per_section) >= 3 else "low"

    return {
        "score": avg_score,
        "confidence_label": confidence_label,
        "flagged_sections": flagged,
        "rationale": (
            f"Statistical burstiness/lexical-diversity heuristic (same method as the PPT Analyzer's "
            f"AI-content agent) over {len(per_section)} text section(s). This is NOT a validated "
            "AI-text detector — false positives are expected, especially for non-native-English "
            "writers and heavily-templated resume text. Never a binary verdict; treat as a prompt "
            "for human review."
        ),
    }
