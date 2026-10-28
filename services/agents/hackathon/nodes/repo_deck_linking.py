"""Repo/Deck Linking Agent — doc 05 §4, "rules" tier, "validates/dedupes references,
triggers async invocation of doc 03/04 pipelines."

Decks are NOT re-scored here: a team's deck is uploaded through Module 04's own real
`POST /presentations/upload` endpoint before/at hackathon submission time, so
`presentation_scores` already exists by the time rankings are finalized — the router
pre-fetches `pitch_score` (a plain table read) and this node just passes it through.

Repos ARE actively triggered here, since a hackathon repo link never goes through Module
03's own coding-assessment UI — this node invokes Module 03's real, unmodified
verification graph (`get_verification_graph()`, the exact entrypoint
`services/api/modules/assessments/router.py` itself calls) for any team whose repo hasn't been
scored yet. Reuses `_fetch_repo_sample_source` from that same router rather than
duplicating the GitHub-fetch logic.

Node stays DB-free (this codebase's universal convention — router fetches/persists,
nodes stay pure): the freshly-computed `repo_verification_results` are handed back in
state for the router to persist as real `Assessment`/`Submission` rows after this graph
completes, exactly like every other cross-module write in this codebase.
"""

import asyncio
import logging

from services.agents.assessment.state import VerificationState
from services.agents.assessment.tools.llm_review import AssessmentUnavailable
from services.agents.assessment.verification_graph import get_verification_graph
from services.agents.hackathon.state import HackathonRankingState
from services.api.modules.assessments.router import _fetch_repo_sample_source
from services.api.core.config import get_settings


# Cap on simultaneous repo verifications. Each one is a GitHub API fetch plus an LLM
# review, so this bounds pressure on both the GitHub rate limit and the LLM provider's
# concurrency limit while still overlapping the network waits that dominate the work.
logger = logging.getLogger(__name__)

_MAX_CONCURRENT_REPO_SCORES = get_settings().agent_max_concurrency
_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REPO_SCORES)


def _repo_full_name(repo_url: str) -> str:
    if "github.com/" in repo_url:
        return repo_url.rstrip("/").split("github.com/")[-1]
    return repo_url


async def _score_repo(repo_url: str) -> dict:
    repo_full_name = _repo_full_name(repo_url)
    # `_fetch_repo_sample_source` is synchronous PyGithub I/O. Called directly it blocks
    # the event loop for the whole GitHub round trip, which would both stall every other
    # in-flight request and serialize the concurrent scoring below into a queue.
    source = await asyncio.to_thread(_fetch_repo_sample_source, repo_full_name)

    initial_state: VerificationState = {
        "assessment_type": "project_analysis",
        "spec": {},
        "code_or_answers": {"repo_full_name": repo_full_name, "code": source},
        "test_results": [],
        "static_analysis": {},
        "tests_passed": 0,
        "tests_total": 0,
        "grading_rationale": None,
        "llm_review": None,
        "score": None,
    }
    result_state = await get_verification_graph().ainvoke(initial_state)
    return {
        "repo_full_name": repo_full_name,
        "static_analysis": result_state["static_analysis"],
        "llm_review": result_state["llm_review"],
        "score": result_state["score"],
    }


async def run(state: HackathonRankingState) -> dict:
    repo_scores: dict[str, float | None] = {}
    repo_verification_results: dict[str, dict] = {}

    pending: list[tuple[str, str]] = []
    for team in state["teams"]:
        team_id = team["team_id"]
        existing_repo_score = team.get("repo_score")
        if existing_repo_score is not None:
            repo_scores[team_id] = existing_repo_score
        elif not team.get("repo_url"):
            repo_scores[team_id] = None
        else:
            pending.append((team_id, team["repo_url"]))

    async def score_one(team_id: str, repo_url: str) -> tuple[str, dict | None]:
        async with _semaphore:
            try:
                return team_id, await _score_repo(repo_url)
            except AssessmentUnavailable:
                # Static analysis ran (it's pure Python, no external dependency) but the
                # LLM code review couldn't (e.g. missing ANTHROPIC_API_KEY) — degrade to
                # None, never fabricate a repo quality number, same pattern every other
                # module uses.
                return team_id, None
            except Exception:  # noqa: BLE001 - one bad repo must not fail the whole event
                # Only AssessmentUnavailable was caught before, so anything else — a
                # deleted or private repository, a GitHub rate limit, a malformed URL —
                # propagated out of `asyncio.gather` and failed finalization for EVERY
                # team, not just this one. A 30-team hackathon could not be finalized
                # because one team pasted a bad link.
                #
                # The team degrades to a null repo score, which `compute_composite_score`
                # renormalizes away, so they are ranked on their remaining components
                # rather than penalized for our failure to read their repository.
                logger.warning(
                    "Repo verification failed for team %s (%s) — scoring without it",
                    team_id, repo_url, exc_info=True,
                )
                return team_id, None

    # Each team's verification is an independent GitHub fetch + static analysis + LLM
    # review, and they were run strictly one after another — so finalizing a 30-team
    # hackathon took 30x one team's latency, most of it spent waiting on the network.
    # Bounded concurrency: fast enough to matter, capped so a large event doesn't open 100
    # simultaneous GitHub/LLM calls and trigger rate limiting (which `_score_repo`'s
    # AssessmentUnavailable path would silently turn into missing scores).
    for team_id, result in await asyncio.gather(*(score_one(t, u) for t, u in pending)):
        if result is None:
            repo_scores[team_id] = None
            continue
        repo_scores[team_id] = result["score"]
        repo_verification_results[team_id] = result

    return {"repo_scores": repo_scores, "repo_verification_results": repo_verification_results}
