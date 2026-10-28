"""Slide Embedding Agent — doc 04 §4. Self-hosted `bge-large-en-v1.5`, no chat LLM
(same model/pattern as candidate_intelligence's innovation novelty check). Degrades to
`None` if the model can't be loaded (e.g. no network to fetch weights the first time) —
downstream nodes (similarity/plagiarism) treat that as cold-start, not an error.

Model loading itself is shared with `recruitment/tools/embeddings.py:get_embedder()`,
which caches the `SentenceTransformer` as a process-level singleton — this module
previously re-loaded it from disk on every call (multi-second cost), the same "one copy
got optimized, the others didn't" drift already found and fixed once for the Qdrant
client constructor.
"""

from services.agents.recruitment.tools.embeddings import RecruitmentUnavailable, get_embedder


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    if not texts:
        return None
    try:
        model = get_embedder()
        return model.encode(texts).tolist()
    except RecruitmentUnavailable:
        return None
