"""Text Fingerprint Agent — doc 06 §4, "embedding + hashing (datasketch MinHash/LSH) +
embedding similarity". FR-4 (duplicate profile detection via near-duplicate resume/
profile text across accounts).

MinHash-only (no embedding call) for the deterministic baseline signal — matches doc 08's
"deterministic and rule-based unless explicitly marked LLM judgment" ground rule; an
embedding-similarity term would need an extra Anthropic/embedding-model call for what
MinHash/Jaccard already answers well for near-duplicate (not just semantically similar)
text, which is the specific "same person, reworded slightly" pattern this check targets.
"""

import re

from datasketch import MinHash
from services.api.core.config import get_settings

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_NUM_PERM = 128
_SHINGLE_SIZE = 3  # word-level 3-shingles


def _shingles(text: str) -> set[str]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if len(words) < _SHINGLE_SIZE:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + _SHINGLE_SIZE]) for i in range(len(words) - _SHINGLE_SIZE + 1)}


def compute_minhash(text: str) -> MinHash | None:
    shingles = _shingles(text)
    if not shingles:
        return None
    mh = MinHash(num_perm=_NUM_PERM)
    for s in shingles:
        mh.update(s.encode("utf-8"))
    return mh


# Tunable default — near-duplicate text (same person, lightly reworded profile) tends to
# land well above generic "both candidates are backend engineers" boilerplate overlap.
SIMILARITY_FLAG_THRESHOLD = get_settings().text_fingerprint_similarity_threshold


def find_similar_profiles(text: str, corpus: list[tuple[str, str]]) -> list[dict]:
    """`corpus` is [(other_candidate_id, other_text), ...]. Returns
    [{other_candidate_id, similarity, evidence}] sorted descending, for every corpus
    entry with enough text to compare (same "report everything, let the router decide
    the flag threshold" pattern as `structural_similarity.py`)."""
    target = compute_minhash(text)
    if target is None:
        return []

    results: list[dict] = []
    for other_id, other_text in corpus:
        other = compute_minhash(other_text)
        if other is None:
            continue
        similarity = round(float(target.jaccard(other)), 4)
        results.append(
            {
                "other_candidate_id": other_id,
                "similarity": similarity,
                "evidence": f"{similarity * 100:.1f}% MinHash/Jaccard text overlap with candidate {other_id}'s profile.",
            }
        )
    return sorted(results, key=lambda r: r["similarity"], reverse=True)
