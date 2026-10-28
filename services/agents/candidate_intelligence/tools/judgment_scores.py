"""Project Quality & Innovation — the two sub-scores doc 01 §4 routes to Sonnet.

Both are "Mixed"/"Subjective": a mechanical component that always runs, plus an
LLM/embedding component that calls out to Anthropic/the embedding model for real and
degrades to `None` (never a fabricated number) if that dependency isn't reachable —
whether because a key is missing or the service/model isn't available in this
environment. Doc 08 §1.1's cold-start re-normalization is what absorbs that gracefully.
"""

import asyncio
import base64
import uuid

from github import Github
from github.GithubException import GithubException
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from radon.complexity import cc_visit

from packages.shared_schemas.candidates import SubScore
from services.agents.candidate_intelligence.tools.github import GithubAnalysis
from services.agents.candidate_intelligence.tools.normalization import recency_weight
from services.agents.recruitment.tools.embeddings import get_embedder
from services.api.core.config import get_settings
from services.api.core.llm import LLMUnavailable, generate_structured, validated_score
from services.agents.recruitment.tools.embeddings import CANDIDATE_PROJECT_EMBEDDINGS_COLLECTION
from services.api.core.qdrant import ensure_payload_indexes
from services.api.core.qdrant import get_qdrant_client as _get_qdrant_client

_JUDGMENT_PARAMETERS = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "description": "0-100"},
        "rationale": {"type": "string"},
    },
    "required": ["score", "rationale"],
}

_QDRANT_COLLECTION = CANDIDATE_PROJECT_EMBEDDINGS_COLLECTION


def _penalty_curve(avg_complexity: float) -> float:
    """Mild penalty up to cyclomatic complexity 15, steeper past it (doc 08 §1 note)."""
    if avg_complexity <= 5:
        return 100.0
    if avg_complexity <= 15:
        return 100.0 - (avg_complexity - 5) * 2.0
    return max(0.0, 80.0 - (avg_complexity - 15) * 5.0)


def sample_complexity(
    github_username: str, access_token: str | None, analysis: GithubAnalysis, max_repos: int = 3
) -> tuple[float | None, list[str]]:
    client = Github(login_or_token=access_token, retry=None) if access_token else Github(retry=None)
    complexities: list[float] = []
    sampled: list[str] = []

    python_repos = [r for r in analysis.repos if not r.is_fork and "Python" in r.languages][:max_repos]
    for repo_snapshot in python_repos:
        try:
            repo = client.get_repo(repo_snapshot.repo_full_name)
            contents = repo.get_contents("")
            py_files = [c for c in contents if c.path.endswith(".py") and c.size < 50_000]
            if not py_files:
                continue
            source = base64.b64decode(py_files[0].content).decode("utf-8", errors="ignore")
            blocks = cc_visit(source)
            if blocks:
                complexities.extend(b.complexity for b in blocks)
                sampled.append(f"{repo_snapshot.repo_full_name}:{py_files[0].path}")
        except (GithubException, UnicodeDecodeError, SyntaxError):
            continue

    if not complexities:
        return None, []
    return sum(complexities) / len(complexities), sampled


async def _llm_quality_judgment(project_summaries: list[str], settings) -> tuple[float | None, str | None]:
    from services.agents.prompts_loader import load_prompt

    if not project_summaries:
        return None, None
    prompt = load_prompt(
        "candidate_intelligence",
        "judgment_scores",
        project_summaries="\n---\n".join(project_summaries),
    )
    try:
        result = await generate_structured(
            schema_name="project_quality_judgment",
            schema_description="Rate architecture/README quality of a candidate's projects.",
            parameters=_JUDGMENT_PARAMETERS,
            prompt=prompt,
            max_tokens=512,
            agent_name="candidate_intelligence.judgment_scores.llm_quality_judgment",
        )
    except LLMUnavailable:
        return None, None
    # Clamped rather than `float(...)`: this value becomes a TalentScore sub-score, which
    # recruiter matching, salary prediction and hackathon composites all read. A model
    # answering on a 0-10 scale used to persist verbatim as e.g. 8.5/100.
    return validated_score(result.get("score")), result.get("rationale")


def code_quality_score(
    github_username: str,
    access_token: str | None,
    analysis: GithubAnalysis,
    sampled: tuple[float | None, list[str]] | None = None,
) -> tuple[float | None, list[str]]:
    """Public wrapper around the complexity sample + penalty curve — shared between
    project_quality's mechanical component and coding_ability's quality_score term
    (proposal's `coding_ability = 0.25 language + 0.35 quality + 0.40 assessment`) so
    the same static-analysis pass isn't run twice per candidate per scoring cycle.

    Pass `sampled` (an existing `sample_complexity` result) to reuse a sampling pass
    the caller already ran — see `project_quality`'s identical parameter."""
    avg_complexity, sampled_files = (
        sampled if sampled is not None else sample_complexity(github_username, access_token, analysis)
    )
    if avg_complexity is None:
        return None, sampled_files
    return _penalty_curve(avg_complexity), sampled_files


async def project_quality(
    github_username: str,
    access_token: str | None,
    analysis: GithubAnalysis,
    sampled: tuple[float | None, list[str]] | None = None,
) -> SubScore:
    """`sampled` is an already-computed `sample_complexity` result, as returned by
    `code_quality_score`. Callers that have run the sampling pass should pass it in:
    it's a set of blocking PyGithub round trips, and re-running it here duplicated
    every one of those network calls per scoring cycle."""
    settings = get_settings()
    if sampled is None:
        # Blocking PyGithub calls (repo contents fetch) — run off-thread so this async
        # node doesn't stall the event loop, same pattern as github_analysis.py's node.
        sampled = await asyncio.to_thread(
            sample_complexity, github_username, access_token, analysis
        )
    avg_complexity, sampled_files = sampled
    mechanical = _penalty_curve(avg_complexity) if avg_complexity is not None else None

    summaries = [f"{r.repo_full_name}: {r.stars} stars, languages {list(r.languages)}" for r in analysis.repos[:5]]
    llm_score, llm_rationale = await _llm_quality_judgment(summaries, settings)

    if mechanical is None and llm_score is None:
        return SubScore(value=None, rationale="No sampled Python source and no LLM judgment available.")
    if mechanical is not None and llm_score is not None:
        value = 0.6 * mechanical + 0.4 * llm_score
        rationale = f"Complexity-based (avg cc={avg_complexity:.1f}) + LLM: {llm_rationale}"
    elif mechanical is not None:
        value = mechanical
        rationale = f"Complexity-based only (avg cc={avg_complexity:.1f}); LLM judgment unavailable."
    else:
        value = llm_score
        rationale = f"LLM judgment only; no Python source sampled. {llm_rationale}"
    return SubScore(value=round(value, 1), evidence=sampled_files, rationale=rationale)


def _get_qdrant() -> QdrantClient | None:
    return _get_qdrant_client(raise_on_unavailable=False)


def _embed(texts: list[str]) -> list[list[float]] | None:
    try:
        # Shared process-level singleton with recruitment/tools/embeddings.py — avoids
        # loading a second SentenceTransformer instance from disk in the same process.
        model = get_embedder()
        return model.encode(texts).tolist()
    except Exception:
        return None


def _novelty_score(candidate_id: str, descriptions: list[str]) -> float | None:
    """Blocking: SentenceTransformer encode + Qdrant round trips. Call via
    `asyncio.to_thread` — never directly from an async context."""
    novelty_score: float | None = None
    qdrant = _get_qdrant() if descriptions else None
    embeddings = _embed(descriptions) if qdrant else None
    if qdrant is not None and embeddings:
        try:
            if not qdrant.collection_exists(_QDRANT_COLLECTION):
                qdrant.create_collection(
                    collection_name=_QDRANT_COLLECTION,
                    vectors_config=qmodels.VectorParams(
                        size=len(embeddings[0]), distance=qmodels.Distance.COSINE
                    ),
                )
                # `candidate_id` is the single hottest payload filter in the codebase:
                # recruitment's `batch_candidate_project_relevance` issues one
                # candidate_id-filtered search *per candidate in the pool* on every
                # matching run. Unindexed, each of those degrades toward scanning the
                # whole collection, so matching cost grew with total corpus size rather
                # than with pool size.
                ensure_payload_indexes(qdrant, _QDRANT_COLLECTION, {"candidate_id": "keyword"})
            corpus_count = qdrant.count(_QDRANT_COLLECTION).count
            if corpus_count > 0:
                # `query_points`, not the removed-in-1.18 `.search()` — that call raised
                # `AttributeError` straight into the `except Exception: pass` below, so
                # innovation-novelty silently stayed `None` on every Talent Score run.
                hits = qdrant.query_points(
                    _QDRANT_COLLECTION, query=embeddings[0], limit=5
                ).points
                avg_similarity = sum(h.score for h in hits) / len(hits) if hits else 0.0
                novelty_score = max(0.0, min(100.0, 100.0 * (1 - avg_similarity)))
            qdrant.upsert(
                _QDRANT_COLLECTION,
                points=[
                    qmodels.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vec,
                        payload={"candidate_id": candidate_id, "repo_name": desc},
                    )
                    for vec, desc in zip(embeddings, descriptions)
                ],
            )
        except Exception:
            pass  # keep whatever was computed before the failure

    return novelty_score


async def innovation(candidate_id: str, analysis: GithubAnalysis) -> SubScore:
    settings = get_settings()
    # Already sorted most-recently-pushed-first (fetch_github_analysis) — recency-decay
    # the novelty score itself so a project that was innovative years ago and has since
    # been abandoned doesn't score as highly as one that's actively developed.
    candidate_repos = analysis.repos[:5]
    descriptions = [f"{r.repo_full_name}: {list(r.languages)}" for r in candidate_repos]
    most_recent_push = max((r.pushed_at for r in candidate_repos if r.pushed_at), default=None)
    decay = recency_weight(most_recent_push, half_life_days=365.0) if most_recent_push else 1.0

    # Embedding/Qdrant work is blocking and independent of the LLM judgment — thread the
    # former and run both concurrently instead of serially on the event loop.
    novelty_score, (llm_score, llm_rationale) = await asyncio.gather(
        asyncio.to_thread(_novelty_score, candidate_id, descriptions),
        _llm_quality_judgment(descriptions, settings),  # reuse judgment shape
    )

    if novelty_score is None and llm_score is None:
        return SubScore(
            value=None,
            rationale="No embedding corpus yet (cold start) and no LLM judgment available.",
        )
    if novelty_score is not None and llm_score is not None:
        value = decay * (0.5 * novelty_score + 0.5 * llm_score)
        rationale = f"Novelty vs corpus + LLM judgment (recency weight {decay:.2f}): {llm_rationale}"
    elif novelty_score is not None:
        value = decay * novelty_score
        rationale = f"Embedding-novelty vs corpus only (recency weight {decay:.2f}); LLM judgment unavailable."
    else:
        value = llm_score
        rationale = f"LLM judgment only; no embedding corpus yet. {llm_rationale}"
    return SubScore(value=round(value, 1), rationale=rationale)
