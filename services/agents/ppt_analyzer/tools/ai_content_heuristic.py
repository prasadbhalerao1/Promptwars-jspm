"""AI-Content Heuristic Agent — doc 04 §4/FR-6. Best-effort SIGNAL, never a verdict.

Scope decision (documented in .agents/decisions.md): doc 08's ground rules note that a
full GPT-2-perplexity model via `transformers` is one option but call out that a
simpler statistical fallback is a legitimate scope-reduction for a 48-hour build (the
doc says this explicitly for §3's code-plagiarism algorithm; the same reasoning is
applied here) — this implementation uses burstiness + lexical-diversity statistics
instead of downloading/running a GPT-2 model, so it has no network dependency and no
multi-hundred-MB model download at runtime. `transformers`/`torch` are still installed
in this repo's venv (see .env.example / DEV_SERVERS.md) for a future upgrade path to
real perplexity scoring; this module doesn't import them.

AI-generated text tends to have LOWER burstiness (more uniform sentence length) and
flatter lexical variety than human writing — a well-documented, if imperfect, signal.
This is explicitly NOT presented as a reliable detector: confidence is always capped
and every score ships with a rationale + which sections were flagged, per FR-6/§9.
"""

import re
import statistics

from services.api.common.constants import AI_CONTENT_FLAG_THRESHOLD

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z']+")


def _sentence_lengths(text: str) -> list[int]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return [len(_WORD_RE.findall(s)) for s in sentences if _WORD_RE.findall(s)]


def _lexical_diversity(text: str) -> float | None:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if len(words) < 10:
        return None
    return len(set(words)) / len(words)


def _slide_ai_likelihood(text: str) -> float | None:
    """0-100 heuristic score for one slide's text, or None if there's too little text
    to say anything meaningful (avoids false-confidence on a 3-word title slide)."""
    lengths = _sentence_lengths(text)
    if len(lengths) < 3:
        return None

    burstiness = statistics.pstdev(lengths) / statistics.mean(lengths) if statistics.mean(lengths) else 0.0
    diversity = _lexical_diversity(text)
    if diversity is None:
        return None

    # Low burstiness (uniform sentences) + low lexical diversity -> higher AI-likelihood.
    # Both terms clamped to [0,1] before blending; tunable default weighting (0.5/0.5).
    burstiness_signal = max(0.0, min(1.0, 1.0 - burstiness))
    diversity_signal = max(0.0, min(1.0, 1.0 - diversity * 2))  # human prose is rarely >50% unique words
    return round(100.0 * (0.5 * burstiness_signal + 0.5 * diversity_signal), 1)


def compute_ai_content_signal(slides: list[dict]) -> dict:
    """Returns {score, confidence_label, flagged_sections, rationale} — FR-6's hard
    requirement: always a confidence label + evidence, never a bare boolean."""
    per_slide: list[tuple[int, float]] = []
    for slide in slides:
        text = " ".join(filter(None, [slide.get("title"), slide.get("body"), slide.get("notes")]))
        score = _slide_ai_likelihood(text)
        if score is not None:
            per_slide.append((slide["index"], score))

    if not per_slide:
        return {
            "score": None,
            "confidence_label": "low",
            "flagged_sections": [],
            "rationale": "Not enough extracted text per slide to compute a meaningful signal.",
        }

    avg_score = round(sum(s for _, s in per_slide) / len(per_slide), 1)
    flagged = [f"slide_{i}" for i, s in per_slide if s >= AI_CONTENT_FLAG_THRESHOLD]

    # Confidence in the SIGNAL (not in "is it AI"): more slides with enough text -> more
    # confidence the average is representative, capped at "medium" since this heuristic
    # is not a validated detector at any sample size (FR-6's explicit "never a definitive
    # verdict" requirement).
    confidence_label = "medium" if len(per_slide) >= 5 else "low"

    return {
        "score": avg_score,
        "confidence_label": confidence_label,
        "flagged_sections": flagged,
        "rationale": (
            f"Statistical burstiness/lexical-diversity heuristic over {len(per_slide)} slide(s) with "
            "enough text to score. This is NOT a validated AI-text detector — false positives are "
            "expected, especially for non-native-English writers and heavily-templated slide text. "
            "Treat as a prompt for human review, not a verdict."
        ),
    }
