"""The three LLM-backed steps of the Recruiter Copilot (FR-3): Query Understanding,
Re-ranking, and Explanation. Routed through `services.api.core.llm.generate_structured`
(same pattern as `assessment/tools/llm_review.py`) — a JSON-schema parameters object,
`RecruitmentUnavailable` raised (never a silent fallback) when the configured provider
is unavailable or the call fails.

Per doc/multi-agent-architecture/02 §4 and the `langgraph-agents` skill's explicit
warning: the Query Understanding Agent must "reject and re-prompt on schema-validation
failure, never silently accept a malformed filter" — implemented here as a single
corrective retry (not an unbounded loop) before raising, since Anthropic's forced
tool-use already makes most schema failures rare.
"""

import json
import time

from services.api.core.llm import LLMUnavailable, generate_structured
from services.agents.recruitment.tools.embeddings import RecruitmentUnavailable

# Recruiters often issue near-identical queries back-to-back within a session (typo fix,
# re-running the same search) — a short in-process TTL cache on the parsed filters avoids
# a repeat LLM round-trip. Keyed on (raw_query, prior_filters) since prior_filters changes
# the parse (follow-up refinement vs. fresh search). Same pattern as
# recruitment/router.py's _candidate_pool_cache — no infra dependency, self-expiring.
_UNDERSTAND_QUERY_CACHE_TTL_SECONDS = 30
_understand_query_cache: dict[str, tuple[float, dict]] = {}

_QUERY_UNDERSTANDING_PARAMETERS = {
    "type": "object",
    "properties": {
        "location": {
            "type": ["string", "null"],
            "description": "A city/region mentioned, or null if none was mentioned.",
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Technical skills, languages, or frameworks the recruiter wants "
                "(e.g. ['react', 'genai']). Empty array if none mentioned."
            ),
        },
        "min_talent_score": {
            "type": ["number", "null"],
            "description": (
                "A minimum overall Talent Score (0-100) ONLY if the recruiter explicitly "
                "asked for a quality/skill bar (e.g. 'top', 'highly rated', 'best'). Use a "
                "conservative 70 for vague terms like 'top' or 'best', null otherwise — "
                "never invent a specific number the recruiter didn't imply."
            ),
        },
        "hackathon_experience": {
            "type": ["boolean", "null"],
            "description": "true if the recruiter specifically wants hackathon participants, else null.",
        },
        "remote_ok": {
            "type": ["boolean", "null"],
            "description": "true/false only if remote work was explicitly discussed, else null.",
        },
        "semantic_query": {
            "type": "string",
            "description": (
                "The residual free-text intent that isn't captured by the structured fields "
                "above (e.g. 'active LangChain contributor', 'built a fintech project') — "
                "used for the vector-similarity search step. Empty string if the query is "
                "fully captured by the structured fields."
            ),
        },
    },
    "required": ["skills", "semantic_query"],
}

_RERANK_PARAMETERS = {
    "type": "object",
    "properties": {
        "ordered_candidate_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "candidate_id values from the input list, best-fit first, no additions or omissions.",
        }
    },
    "required": ["ordered_candidate_ids"],
}

_EXPLANATION_PARAMETERS = {
    "type": "object",
    "properties": {
        "explanations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "explanation": {
                        "type": "string",
                        "description": (
                            "One sentence, must cite specific fields from the evidence given "
                            "(repo names, stars, hackathon wins, talent score, skills) — never "
                            "invent an achievement not present in the evidence."
                        ),
                    },
                },
                "required": ["candidate_id", "explanation"],
            },
        }
    },
    "required": ["explanations"],
}


async def _call_structured(
    schema_name: str, schema_description: str, parameters: dict, prompt: str, *, is_fast: bool, max_tokens: int, agent_name: str
) -> dict:
    """Thin wrapper translating the gateway's `LLMUnavailable` into this module's
    `RecruitmentUnavailable` (defined in `tools/embeddings.py`, not here) so callers and
    routers that already `except RecruitmentUnavailable` keep working unchanged."""
    try:
        return await generate_structured(
            schema_name=schema_name,
            schema_description=schema_description,
            parameters=parameters,
            prompt=prompt,
            is_fast=is_fast,
            max_tokens=max_tokens,
            agent_name=agent_name,
        )
    except LLMUnavailable as exc:
        raise RecruitmentUnavailable(str(exc)) from exc


async def understand_query(raw_query: str, prior_filters: dict | None) -> dict:
    """Parses a recruiter's NL query into structured filters. `prior_filters` (from the
    same conversation's previous turn, if any) is given as context so a follow-up like
    "now only show ones open to remote" is understood as a refinement, not a fresh query
    that drops the earlier location/skills filters."""
    from services.agents.prompts_loader import load_prompt

    cache_key = json.dumps({"raw_query": raw_query, "prior_filters": prior_filters}, sort_keys=True)
    cached = _understand_query_cache.get(cache_key)
    if cached is not None:
        cached_at, result = cached
        if time.monotonic() - cached_at < _UNDERSTAND_QUERY_CACHE_TTL_SECONDS:
            return result

    prior_context = (
        f"\n\nThe recruiter's PREVIOUS filters in this conversation were: "
        f"{json.dumps(prior_filters)}. If this new message is a refinement/follow-up "
        f"(e.g. 'now only show remote ones', 'add Python too'), merge sensibly with the "
        f"previous filters rather than discarding them. If it reads like a brand-new, "
        f"unrelated search, start fresh instead."
        if prior_filters
        else ""
    )
    prompt = load_prompt(
        "recruitment",
        "understand_query",
        raw_query=raw_query,
        prior_context=prior_context,
    )
    schema_description = (
        "Convert a recruiter's natural-language candidate search into structured search "
        "filters. Only extract what the recruiter actually stated or clearly implied — "
        "never invent a filter value that wasn't in the query."
    )

    try:
        result = await _call_structured(
            "structured_search_filters",
            schema_description,
            _QUERY_UNDERSTANDING_PARAMETERS,
            prompt,
            is_fast=True,
            max_tokens=1024,
            agent_name="recruitment.copilot.understand_query",
        )
    except RecruitmentUnavailable:
        # Single corrective retry — the `langgraph-agents` skill's explicit instruction
        # to "reject and re-prompt on schema-validation failure, never silently accept a
        # malformed filter" rather than an unbounded loop.
        result = await _call_structured(
            "structured_search_filters",
            schema_description,
            _QUERY_UNDERSTANDING_PARAMETERS,
            prompt + "\n\nYour previous response did not match the required schema. "
            "Respond again using the structured_search_filters tool exactly as specified.",
            is_fast=True,
            max_tokens=1024,
            agent_name="recruitment.copilot.understand_query_retry",
        )

    _understand_query_cache[cache_key] = (time.monotonic(), result)
    return result


async def rerank_candidates(raw_query: str, candidates: list[dict]) -> list[str]:
    """`candidates` is the cheap-retrieval shortlist (already bounded to ~20-50 by the
    caller — this function does not itself limit the input, cost-bounding is the
    caller's responsibility per doc 02 §2's "LLM only on the final shortlist" rule).
    Returns `candidate_id`s in best-fit-first order."""
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt(
        "recruitment",
        "rerank_candidates",
        raw_query=raw_query,
        candidates_json=json.dumps(candidates, default=str),
    )
    result = await _call_structured(
        "reranked_candidates",
        "Re-order a shortlist of candidates by genuine fit to the recruiter's query.",
        _RERANK_PARAMETERS,
        prompt,
        is_fast=False,
        max_tokens=1024,
        agent_name="recruitment.copilot.rerank",
    )
    return result.get("ordered_candidate_ids", [])


async def explain_matches(raw_query: str, candidates: list[dict]) -> dict[str, str]:
    """One grounded sentence per candidate. `candidates` must already include whatever
    concrete evidence fields (repo names, stars, hackathon wins, talent score) the
    explanation is allowed to cite — the prompt explicitly forbids inventing anything not
    present in that evidence, mirroring Module 01's fact-check guardrail language."""
    from services.agents.prompts_loader import load_prompt

    prompt = load_prompt(
        "recruitment",
        "explain_matches",
        raw_query=raw_query,
        candidates_json=json.dumps(candidates, default=str),
    )
    result = await _call_structured(
        "match_explanations",
        "One grounded, evidence-citing sentence per candidate explaining why they matched.",
        _EXPLANATION_PARAMETERS,
        prompt,
        is_fast=True,
        max_tokens=1536,
        agent_name="recruitment.copilot.explain_matches",
    )
    return {item["candidate_id"]: item["explanation"] for item in result.get("explanations", [])}
