"""Structural Similarity Agent — doc 06 §4, "tool only" (`copydetect`, a Dolos-style
token-based structural clone detector — doc 08 §3's canonical algorithm, "robust to
variable renaming, unlike raw text diff"). Shared logic for FR-2 (project plagiarism)
and FR-5 (Module 03 submission plagiarism) — both compare one piece of source code
against a corpus of other candidates' code.

`copydetect` was not pre-installed in this repo's venv (confirmed via import check
before adding it — same "check first" step this session confirmed `radon`/`lizard`/
`bandit` already existed for Module 03); installed via `uv pip install --python
services/api/.venv copydetect`, matching the pattern the assignment file names.
"""

import io

from copydetect import CodeFingerprint, compare_files
from services.api.core.config import get_settings

# Doc 08 §3's own tunable default for AST-winnowing similarity (J(A,B) > 0.75 raises a
# flag). copydetect's `compare_files` returns two similarity ratios (one per file, since
# each file's total token count differs) — this module uses the max of the two as the
# single Jaccard-like overlap score, consistent with "did either submission end up mostly
# copied from the other."
SIMILARITY_FLAG_THRESHOLD = get_settings().structural_similarity_threshold
_WINNOW_K = 15
_WINNOW_WINDOW = 10


def _fingerprint(code: str, language_hint: str) -> CodeFingerprint | None:
    if not code or not code.strip():
        return None
    ext = {"python": "py", "javascript": "js", "typescript": "ts", "java": "java", "c": "c", "cpp": "cpp"}.get(
        language_hint, "py"
    )
    try:
        return CodeFingerprint(file=f"submission.{ext}", k=_WINNOW_K, win_size=_WINNOW_WINDOW, fp=io.StringIO(code))
    except Exception:
        return None


def compute_structural_similarity(
    code: str, corpus: list[tuple[str, str]], language_hint: str = "python"
) -> list[dict]:
    """`corpus` is [(other_submission_id, other_code), ...]. Returns
    [{other_submission_id, similarity, evidence}] for every corpus entry, sorted by
    similarity descending — the router decides which ones cross the flag threshold, this
    tool just reports the measured overlap for every comparison (full evidence trail,
    per doc 06 §7's "every flag must cite the specific evidence" — the underlying
    verification_records rows this feeds are the trail, not just the flagged subset)."""
    target_fp = _fingerprint(code, language_hint)
    if target_fp is None:
        return []

    results: list[dict] = []
    for other_id, other_code in corpus:
        other_fp = _fingerprint(other_code, language_hint)
        if other_fp is None:
            continue
        try:
            _, (sim_a, sim_b), _ = compare_files(target_fp, other_fp)
        except Exception:
            continue
        similarity = round(max(float(sim_a), float(sim_b)), 4)
        results.append(
            {
                "other_submission_id": other_id,
                "similarity": similarity,
                "evidence": f"{similarity * 100:.1f}% structural (AST-winnowing) token overlap with submission {other_id}.",
            }
        )

    return sorted(results, key=lambda r: r["similarity"], reverse=True)
