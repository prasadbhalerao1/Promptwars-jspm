"""Skill Gap Analysis — FR-4.1. Embeds the candidate's skill set, compares it against
embedded requirement sets for target roles via Qdrant similarity search, and returns a
ranked gap list (biggest gap first). Implements doc/SRS/01 §7's exact method: cosine
similarity between the candidate's skill-embedding **centroid** and each target-role
embedding decides which role to target (when the candidate didn't pick one); a role
skill is then a gap when its embedding similarity to the candidate's skills is below
threshold AND there's no direct (literal) match in the candidate's skill list.

Real Qdrant + sentence-transformers integration, same "write the real integration code,
raise a clear typed error rather than fabricate" convention as
`tools/resume.py`'s `ResumeExtractionUnavailable` / `services/api/core/storage.py`'s
`StorageUnavailable`. Unlike the Talent Score's cold-start degrade-to-`None` (which is
fine because a sub-score is one of seven inputs to a re-normalized sum), Qdrant being
unreachable here means FR-4.1's entire output is missing, so it's a hard error, not a
silent partial result.
"""

import uuid
from dataclasses import dataclass, field

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from services.agents.candidate_intelligence.tools.role_taxonomy import ROLE_SKILL_TAXONOMY
from services.agents.recruitment.tools.embeddings import RecruitmentUnavailable, get_embedder
from services.api.core.config import get_settings
from services.api.core.qdrant import QdrantUnavailable
from services.api.core.qdrant import get_qdrant_client as _get_qdrant_client

_COLLECTION = "skill_taxonomy_embeddings"
# Below this cosine similarity to the candidate's closest matching skill, a required
# skill counts as a real gap rather than "already covered under a different name."
_GAP_SIMILARITY_THRESHOLD = get_settings().skill_gap_similarity_threshold


class CareerGuidanceUnavailable(RuntimeError):
    """Raised when Qdrant or the embedding model isn't reachable — never fabricate a
    skill-gap list or silently fall back to an empty one."""


@dataclass
class SkillGapResult:
    target_role: str
    gaps: list[dict] = field(default_factory=list)  # [{skill, similarity, weight, priority}]
    covered_skills: list[str] = field(default_factory=list)


def _client() -> QdrantClient:
    try:
        return _get_qdrant_client(raise_on_unavailable=True)
    except QdrantUnavailable as exc:
        raise CareerGuidanceUnavailable(str(exc)) from exc


def _embedder():
    """Shared process-level singleton with recruitment/tools/embeddings.py:get_embedder()
    — this used to load its own uncached SentenceTransformer from disk on every call,
    which is on FR-4.1's synchronous request path (every skill-gap analysis paid the
    multi-second model-load cost). Same drift class as the Qdrant client constructor
    duplication already found and fixed."""
    try:
        return get_embedder()
    except RecruitmentUnavailable as exc:
        raise CareerGuidanceUnavailable(f"Embedding model unavailable: {exc}") from exc


def _ensure_seeded(client: QdrantClient, model) -> None:
    """Idempotently seeds each (role, skill) requirement as its own Qdrant point, keyed
    by a deterministic UUID (uuid5 of "role:skill") so re-running never duplicates
    points and a later taxonomy edit just upserts the changed ones."""
    texts: list[str] = []
    points_meta: list[tuple[str, str, float]] = []
    for role, skills in ROLE_SKILL_TAXONOMY.items():
        for skill_name, weight in skills:
            texts.append(skill_name)
            points_meta.append((role, skill_name, weight))

    if client.collection_exists(_COLLECTION) and client.count(_COLLECTION).count >= len(texts):
        return

    vectors = model.encode(texts).tolist()
    if not client.collection_exists(_COLLECTION):
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=qmodels.VectorParams(size=len(vectors[0]), distance=qmodels.Distance.COSINE),
        )
    client.upsert(
        _COLLECTION,
        points=[
            qmodels.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{role}:{skill_name}")),
                vector=vector,
                payload={"role": role, "skill_name": skill_name, "weight": weight},
            )
            for vector, (role, skill_name, weight) in zip(vectors, points_meta)
        ],
    )


def _pick_target_role(client: QdrantClient, model, candidate_skills: list[str]) -> str:
    """No target role given — pick the best-fit role via Qdrant similarity search of
    the candidate's skill-embedding **centroid** against every seeded (role, skill)
    point (doc/SRS/01 §7: "cosine similarity ... between candidate skill-embedding
    centroid and target-role embedding") — the mean of each individual skill's
    embedding, not an embedding of the concatenated skill names."""
    if not candidate_skills:
        return next(iter(ROLE_SKILL_TAXONOMY))

    skill_vectors = np.array(model.encode(candidate_skills).tolist())
    centroid = skill_vectors.mean(axis=0).tolist()
    # Use query_points() (renamed from search() in qdrant-client >= 1.8)
    response = client.query_points(_COLLECTION, query=centroid, limit=len(ROLE_SKILL_TAXONOMY) * 5)
    role_scores: dict[str, list[float]] = {role: [] for role in ROLE_SKILL_TAXONOMY}
    for hit in response.points:
        role_scores[hit.payload["role"]].append(hit.score)

    def avg(role: str) -> float:
        scores = role_scores[role]
        return sum(scores) / len(scores) if scores else 0.0

    return max(ROLE_SKILL_TAXONOMY, key=avg)


def analyze_skill_gaps(candidate_skills: list[str], target_role: str | None) -> SkillGapResult:
    if target_role and target_role not in ROLE_SKILL_TAXONOMY:
        raise ValueError(f"Unknown target_role '{target_role}'. Known roles: {sorted(ROLE_SKILL_TAXONOMY)}")

    settings = get_settings()
    client = _client()
    model = _embedder()
    try:
        _ensure_seeded(client, model)
        resolved_role = target_role or _pick_target_role(client, model, candidate_skills)
    except CareerGuidanceUnavailable:
        raise
    except Exception as exc:
        # `_client()`'s own get_collections() pre-flight can succeed even when a later
        # call (seed upsert, similarity search) can't reach Qdrant — guard the whole
        # round-trip, not just the connectivity check.
        raise CareerGuidanceUnavailable(f"Qdrant is not reachable at {settings.qdrant_url}: {exc}") from exc
    required = ROLE_SKILL_TAXONOMY[resolved_role]
    required_names = [name for name, _ in required]
    required_vectors = np.array(model.encode(required_names).tolist())

    candidate_vectors = np.array(model.encode(candidate_skills).tolist()) if candidate_skills else None
    candidate_norms = (
        np.linalg.norm(candidate_vectors, axis=1) if candidate_vectors is not None else None
    )

    candidate_skill_names_lower = {s.lower() for s in candidate_skills}

    gaps: list[dict] = []
    covered: list[str] = []
    for (skill_name, weight), skill_vector in zip(required, required_vectors):
        # doc/SRS/01 §7: "gaps = role skills with similarity below threshold AND no
        # direct match in candidate_profiles.skills" — a literal (case-insensitive)
        # match always counts as covered, independent of the embedding threshold.
        if skill_name.lower() in candidate_skill_names_lower:
            covered.append(skill_name)
            continue

        best_similarity = 0.0
        if candidate_vectors is not None:
            skill_norm = np.linalg.norm(skill_vector)
            sims = (candidate_vectors @ skill_vector) / (candidate_norms * skill_norm + 1e-9)
            best_similarity = float(sims.max())

        if best_similarity < _GAP_SIMILARITY_THRESHOLD:
            gaps.append({"skill": skill_name, "similarity": round(best_similarity, 3), "weight": weight})
        else:
            covered.append(skill_name)

    # Worst-covered (lowest similarity), highest-weight gaps first.
    gaps.sort(key=lambda g: (g["similarity"], -g["weight"]))
    for rank, gap in enumerate(gaps, start=1):
        gap["priority"] = rank

    return SkillGapResult(target_role=resolved_role, gaps=gaps, covered_skills=covered)
