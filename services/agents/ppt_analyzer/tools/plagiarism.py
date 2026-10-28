"""Similarity/Plagiarism Agent — doc 04 §4/§5. Qdrant search against the
`presentation_slide_embeddings` corpus of prior submissions, then upserts this
presentation's own slides into that corpus for future comparisons (same
build-the-corpus-as-you-go pattern as candidate_intelligence's innovation novelty check).

Rule-based, not an LLM call — the doc's "Haiku for narrative" is treated as an optional
UI-copy enhancement, not part of the actual detection; the structured match (matched
presentation, slide index, similarity score) is itself the evidence, consistent with
FR-6/§9's "always ships with evidence, never a bare boolean" requirement extended here
to plagiarism too.
"""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from services.api.core.qdrant import ensure_payload_indexes
from services.api.core.qdrant import get_qdrant_client as _get_qdrant_client
from services.api.core.config import get_settings

_QDRANT_COLLECTION = "presentation_slide_embeddings"
# Tunable default (doc 08 §3 uses 0.75 for code AST-winnowing similarity; slide-text
# cosine similarity is a different signal so a higher bar is used here to reduce false
# positives from generically-worded slides like "Problem Statement" / "Thank You").
SIMILARITY_THRESHOLD = get_settings().deck_plagiarism_similarity_threshold


class PlagiarismCheckUnavailable(RuntimeError):
    """The plagiarism check could not run.

    Distinct from "ran and found nothing". This module used to return `[]` for both, and
    `[]` renders to the reader as "No similarity matches found against prior submissions"
    — an affirmative all-clear. A removed-in-1.18 client method once raised AttributeError
    in here and every deck was reported clean until someone noticed by hand.

    Callers must surface this as an undetermined state, never as a passing check.
    """


def _get_client() -> QdrantClient | None:
    return _get_qdrant_client(raise_on_unavailable=False)


def find_and_record_matches(
    presentation_id: str,
    slides: list[dict],
    embeddings: list[list[float]] | None,
) -> list[dict]:
    """Returns [{matched_presentation_id, slide_index, similarity}] for slides that
    match a PRIOR submission above the threshold, then upserts this deck's own slide
    embeddings so later uploads can be checked against it too."""
    if not embeddings:
        return []

    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001 - client construction failure is undetermined
        raise PlagiarismCheckUnavailable(f"Qdrant client unavailable: {exc}") from exc
    if client is None:
        # Was `return []`, i.e. an all-clear. A deployment with no Qdrant cannot check
        # plagiarism at all, so every deck it ever saw was reported clean.
        raise PlagiarismCheckUnavailable("Qdrant is not configured or unreachable")

    try:
        if not client.collection_exists(_QDRANT_COLLECTION):
            client.create_collection(
                collection_name=_QDRANT_COLLECTION,
                vectors_config=qmodels.VectorParams(size=len(embeddings[0]), distance=qmodels.Distance.COSINE),
            )
            # Every slide's search filters `presentation_id` (must_not, to exclude this
            # deck's own slides), and this collection grows without bound as decks are
            # uploaded — the worst combination for an unindexed payload filter.
            ensure_payload_indexes(client, _QDRANT_COLLECTION, {"presentation_id": "keyword"})

        # One batched round trip for the whole deck instead of a sequential search per
        # slide — same batching fix as
        # `recruitment/tools/embeddings.py:batch_candidate_project_relevance`.
        #
        # `query_batch_points`, not the removed-in-1.18 `search_batch`: the old call
        # raised `AttributeError`, which this function's `except Exception: return []`
        # swallowed — so plagiarism checking reported "no matches" for every deck rather
        # than surfacing the breakage.
        exclude_self = qmodels.Filter(
            must_not=[
                qmodels.FieldCondition(
                    key="presentation_id", match=qmodels.MatchValue(value=presentation_id)
                )
            ]
        )
        batch_results = client.query_batch_points(
            _QDRANT_COLLECTION,
            requests=[
                qmodels.QueryRequest(query=vector, filter=exclude_self, limit=3, with_payload=True)
                for vector in embeddings
            ],
        )

        matches: list[dict] = []
        for slide, response in zip(slides, batch_results):
            for hit in response.points:
                if hit.score >= SIMILARITY_THRESHOLD:
                    matches.append(
                        {
                            "matched_presentation_id": hit.payload.get("presentation_id"),
                            "slide_index": slide["index"],
                            "similarity": round(float(hit.score), 4),
                        }
                    )

        client.upsert(
            _QDRANT_COLLECTION,
            points=[
                qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"presentation_id": presentation_id, "slide_index": slide["index"]},
                )
                for slide, vector in zip(slides, embeddings)
            ],
        )
        return matches
    except Exception as exc:  # noqa: BLE001 - any backend failure is undetermined
        # Deliberately not `return []`. See PlagiarismCheckUnavailable's docstring: an
        # empty list is a positive claim to the reader, and swallowing failures into it
        # is what let a broken client method report every deck as clean.
        raise PlagiarismCheckUnavailable(f"plagiarism check failed: {exc}") from exc
