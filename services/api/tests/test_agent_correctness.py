"""Regression tests for the correctness bugs found in the agent-layer audit.

Each test here corresponds to one defect that shipped. They share a theme: none of them
raised an error, and none would have been caught by a test asserting "the pipeline
returns a result". They produced *wrong results confidently* — a verified document that
was never checked, an accusation derived from a rate-limit blip, a crash that took down
an entire hackathon because one team pasted a bad URL.
"""

from __future__ import annotations

import uuid
from importlib import import_module

import pytest


# --- fact_check: all([]) is True -----------------------------------------------------


def test_empty_findings_fails_rather_than_passing() -> None:
    """A model returning zero findings must not mark a document verified.

    `all([])` is True, so `{"findings": []}` — schema-valid, and a plausible response to a
    short document — marked the document PASSED with nothing actually checked. A passing
    fact-check is what releases a generated resume to the candidate, so this silently
    disabled the guardrail entirely for that response.
    """
    import inspect

    from services.agents.candidate_intelligence.tools import fact_check

    source = inspect.getsource(fact_check)
    assert "findings and all(" in source, "empty findings must fail the check"


@pytest.mark.parametrize(
    "findings,expected",
    [
        ([], "failed"),
        ([{"claim": "x", "supported": True}], "passed"),
        ([{"claim": "x", "supported": True}, {"claim": "y", "supported": False}], "failed"),
        ([{"claim": "x", "supported": False}], "failed"),
    ],
)
def test_fact_check_status_logic(findings, expected) -> None:
    status = "passed" if findings and all(f.get("supported") for f in findings) else "failed"
    assert status == expected


# --- github_contribution: swallowed errors became accusations ------------------------


def test_incomplete_data_is_distinguished_from_zero_contribution() -> None:
    """A failed GitHub lookup must not read as "this person contributed nothing".

    Four `except GithubException` blocks degraded to 0, and a genuine zero renders as
    "No attributable commits, PRs, or reviews found for this member — flagged for human
    review". So a transient rate limit produced a human-facing claim about a real person
    having done no work on their team's project.
    """
    from services.agents.assessment.tools.contribution_weighting import compute_shares
    from services.agents.assessment.tools.github_contribution import MemberCommitStats

    genuine_zero = MemberCommitStats("alice", commits=0, lines_survived=0, prs_opened=0, prs_reviewed=0)
    lookup_failed = MemberCommitStats(
        "bob", commits=0, lines_survived=0, prs_opened=0, prs_reviewed=0, data_incomplete=True
    )
    contributor = MemberCommitStats("carol", commits=40, lines_survived=900, prs_opened=6, prs_reviewed=3)

    shares = compute_shares({"alice": genuine_zero, "bob": lookup_failed, "carol": contributor})

    assert "No attributable commits" in shares["alice"]["anomaly_note"]
    assert "could not be fully retrieved" in shares["bob"]["anomaly_note"]
    assert shares["bob"]["data_incomplete"] is True
    assert shares["alice"]["data_incomplete"] is False
    assert shares["carol"]["anomaly_note"] is None


def test_member_stats_defaults_to_complete_data() -> None:
    """Existing construction sites must keep working without passing the new flag."""
    from services.agents.assessment.tools.github_contribution import MemberCommitStats

    assert MemberCommitStats("x", 1, 1, 1, 1).data_incomplete is False


# --- fraud report: template fallback was indistinguishable from real analysis --------


def test_fallback_summary_is_marked_as_not_generated() -> None:
    """A reviewer must be able to tell a stub from a considered judgment."""
    from services.agents.fraud.tools.report_llm import _deterministic_fallback

    result = _deterministic_fallback("fake_certificate", ["issuer returned 404"])
    assert result["summary_generated"] is False
    assert result["cited_evidence"] == ["issuer returned 404"]


def test_invented_evidence_citations_are_dropped() -> None:
    """`cited_evidence` must be a subset of the input, enforced rather than requested.

    The schema description told the model this must "never be invented", but a description
    is not a constraint. An invented citation in a fraud flag is a fabricated basis for an
    accusation against a real person.
    """
    from services.agents.fraud.tools.report_llm import _enforce_evidence_subset

    supplied = ["photo hash distance 2 to candidate 9c3e"]
    result = _enforce_evidence_subset(
        {
            "summary": "...",
            "cited_evidence": [
                "photo hash distance 2 to candidate 9c3e",
                "candidate admitted to sharing an account",  # never supplied
            ],
        },
        supplied,
        "duplicate_profile",
    )
    assert result["cited_evidence"] == supplied


def test_real_citations_survive_enforcement() -> None:
    from services.agents.fraud.tools.report_llm import _enforce_evidence_subset

    supplied = ["a", "b", "c"]
    result = _enforce_evidence_subset({"cited_evidence": ["a", "c"]}, supplied, "x")
    assert result["cited_evidence"] == ["a", "c"]


# --- hackathon ranking: KeyError on a partial organizer config -----------------------


@pytest.mark.parametrize(
    "weights",
    [
        {"judge_score_component": 0.5},                      # partial — used to KeyError
        {"bogus_key": 1.0},                                  # unknown key
        {"judge_score_component": -5},                       # negative
        {"judge_score_component": "heavy"},                  # non-numeric
        {"judge_score_component": True},                     # bool is an int subclass
        {},                                                  # empty
        None,                                                # absent
    ],
)
def test_malformed_scoring_config_never_crashes_finalization(weights) -> None:
    """`Hackathon.scoring_config` is an organizer-editable JSONB column.

    A partial config raised KeyError inside `compute_composite_score`, which failed
    finalization for the entire event — every team, not just the affected component.
    """
    from services.agents.hackathon.tools.ranking import compute_composite_score

    score, breakdown = compute_composite_score(80, 70, 60, 50, weights=weights)
    assert score is not None
    assert 0 <= score <= 100
    assert "renormalized" in breakdown


def test_all_zero_weights_falls_back_to_defaults() -> None:
    """Weights summing to zero would make every composite meaningless."""
    from services.agents.hackathon.tools.ranking import _DEFAULT_WEIGHTS, compute_composite_score

    zeroed = {k: 0 for k in _DEFAULT_WEIGHTS}
    score, _ = compute_composite_score(80, 70, 60, 50, weights=zeroed)
    assert score is not None


def test_valid_custom_weights_are_respected() -> None:
    """The guard must not flatten a legitimate organizer configuration."""
    from services.agents.hackathon.tools.ranking import compute_composite_score

    judge_heavy, _ = compute_composite_score(
        100, 0, 0, 0,
        weights={"judge_score_component": 0.97, "pitch_score_component": 0.01,
                 "repo_quality_component": 0.01, "novelty_component": 0.01},
    )
    balanced, _ = compute_composite_score(100, 0, 0, 0)
    assert judge_heavy > balanced


# --- supervisor: unmapped intent crashed dispatch ------------------------------------


@pytest.mark.parametrize(
    "intent,expected",
    [
        ("candidate_score", "candidate_score"),
        ("job_match", "job_match"),
        (None, "candidate_score"),
        ("", "candidate_score"),
        ("unexpected_value", "candidate_score"),   # used to reach LangGraph unmapped
        ("CANDIDATE_SCORE", "candidate_score"),    # case mismatch
        ("both", "candidate_score"),
    ],
)
def test_router_never_returns_an_unmapped_intent(intent, expected) -> None:
    """`or "candidate_score"` covered None and empty string, but not an unexpected value.

    The conditional edge map has exactly two branches; anything else raises at dispatch
    time. Provider schema enforcement varies (this gateway also serves Groq, Gemini and
    Ollama through the OpenAI-compatible path), so this is reachable in practice.
    """
    from services.agents.supervisor.graph import _ROUTABLE_INTENTS, _route

    assert _route({"intent": intent}) == expected
    assert _route({"intent": intent}) in _ROUTABLE_INTENTS


# --- supervisor nodes: unguarded uuid.UUID() -----------------------------------------


async def test_malformed_candidate_id_returns_an_error_not_a_crash() -> None:
    node = import_module("services.agents.supervisor.nodes.candidate_intelligence")
    result = await node.run({"candidate_id": "not-a-uuid"}, {"configurable": {"db": None}})
    assert result["result"] is None
    assert "not a valid UUID" in result["error"]


async def test_malformed_job_id_returns_an_error_not_a_crash() -> None:
    node = import_module("services.agents.supervisor.nodes.recruitment")
    result = await node.run({"job_id": "12345"}, {"configurable": {"db": None}})
    assert result["result"] is None
    assert "not a valid UUID" in result["error"]


# --- interview report: unbounded transcript ------------------------------------------


def test_report_transcript_is_length_bounded() -> None:
    """The report joined every turn verbatim into a fixed-max_tokens call.

    `_render_history` (used per-turn) has always truncated; this path did not, so a
    candidate pasting a stack trace could push the prompt past the context window.
    """
    from services.agents.assessment.tools.interview_llm import _MAX_TURN_CHARS, _render_report_history

    rendered = _render_report_history(
        [{"role": "candidate", "text": "x" * 50_000}, {"role": "agent", "text": "next question"}]
    )
    assert len(rendered) < _MAX_TURN_CHARS + 500
    assert "truncated" in rendered
    assert "next question" in rendered, "bounding must cap turn length, not drop turns"


def test_report_keeps_every_turn() -> None:
    """Unlike the per-question renderer, the report must summarize the whole interview."""
    from services.agents.assessment.tools.interview_llm import _render_report_history

    transcript = [{"role": "candidate", "text": f"answer {i}"} for i in range(40)]
    rendered = _render_report_history(transcript)
    assert "answer 0" in rendered and "answer 39" in rendered


def test_empty_transcript_renders_a_sentinel() -> None:
    from services.agents.assessment.tools.interview_llm import _render_report_history

    assert _render_report_history([]) == "(no transcript recorded)"


# --- fraud photo_hash: context clobbering --------------------------------------------


def test_photo_hash_returns_only_its_own_context_key() -> None:
    """`{**ctx, ...}` writes a stale copy of sibling nodes' results over theirs.

    Harmless only because `duplicate_graph` runs sequentially today; parallelizing it —
    as doc 06's own diagram shows — would have silently destroyed `text_fingerprint`'s
    output and disabled half of duplicate detection, with no error anywhere.
    """
    import inspect

    from services.agents.fraud.nodes import photo_hash

    # Check the return statements, not the whole source: the module's explanatory comment
    # legitimately quotes the `{**ctx, ...}` anti-pattern it is warning against.
    returns = [
        line.strip()
        for line in inspect.getsource(photo_hash).splitlines()
        if line.strip().startswith("return ")
    ]
    assert returns, "expected the node to have return statements"
    for statement in returns:
        assert "{**ctx" not in statement, f"photo_hash echoes the merged context: {statement}"
