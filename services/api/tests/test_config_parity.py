"""Every value moved into Settings must still resolve to what it was hardcoded to.

The point of the configuration refactor was to make tunables tunable, not to change any
behaviour. That is easy to claim and easy to get subtly wrong — a fat-fingered `0.8` for
a weight of `0.08` would change every Talent Score on the platform while every other test
in the suite kept passing, because the rest of the suite asserts on structure, not on
these specific numbers.

So this file pins the numbers themselves. If a default here needs to change, that is a
product decision and this test should be updated deliberately in the same commit — which
is exactly the review moment the old scattered literals never got.
"""

from __future__ import annotations

import pytest

from services.api.core.config import get_settings


@pytest.fixture(scope="module")
def settings():
    return get_settings()


# --- Talent Score formula (was candidate_intelligence/tools/aggregate.py) ------------


_TALENT_WEIGHTS = {
    "weight_coding_ability": 0.15,
    "weight_problem_solving": 0.15,
    "weight_project_quality": 0.12,
    "weight_innovation": 0.11,
    "weight_technical_consistency": 0.08,
    "weight_community_participation": 0.08,
    "weight_leadership": 0.07,
    "weight_open_source_contributions": 0.09,
    "weight_hackathon_performance": 0.09,
    "weight_verified_credentials": 0.06,
}


def test_talent_score_weights_sum_to_one(settings) -> None:
    assert sum(getattr(settings, name) for name in _TALENT_WEIGHTS) == pytest.approx(1.0)


@pytest.mark.parametrize("name,expected", sorted(_TALENT_WEIGHTS.items()))
def test_talent_score_weight_defaults(settings, name, expected) -> None:
    assert getattr(settings, name) == expected


def test_talent_score_weights_sum_to_one(settings) -> None:
    total = sum(getattr(settings, name) for name in _TALENT_WEIGHTS)
    assert round(total, 6) == 1.0


def test_aggregate_module_reflects_configured_weights() -> None:
    """The module-level mapping other code imports must agree with Settings."""
    from services.agents.candidate_intelligence.tools.aggregate import SUB_SCORE_WEIGHTS

    assert dict(SUB_SCORE_WEIGHTS) == {
        name.removeprefix("weight_"): value for name, value in _TALENT_WEIGHTS.items()
    }


# --- Job-match formula (was recruitment/tools/matching.py) ---------------------------


_MATCH_WEIGHTS = {
    "match_weight_skill_overlap": 0.35,
    "match_weight_semantic_similarity": 0.30,
    "match_weight_experience_match": 0.15,
    "match_weight_talent_score_alignment": 0.20,
}


@pytest.mark.parametrize("name,expected", sorted(_MATCH_WEIGHTS.items()))
def test_match_weight_defaults(settings, name, expected) -> None:
    assert getattr(settings, name) == expected


def test_match_weights_sum_to_one(settings) -> None:
    assert round(sum(getattr(settings, n) for n in _MATCH_WEIGHTS), 6) == 1.0


def test_matching_module_reflects_configured_weights(settings) -> None:
    from services.agents.recruitment.tools import matching

    assert matching.W_SKILL_OVERLAP == settings.match_weight_skill_overlap
    assert matching.W_SEMANTIC_SIMILARITY == settings.match_weight_semantic_similarity
    assert matching.W_EXPERIENCE_MATCH == settings.match_weight_experience_match
    assert matching.W_TALENT_SCORE_ALIGNMENT == settings.match_weight_talent_score_alignment
    assert matching.SEMANTIC_ALPHA == settings.match_semantic_alpha


# --- Thresholds and bounds -----------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("match_semantic_alpha", 0.70),
        ("project_quality_mechanical_weight", 0.6),
        ("innovation_novelty_weight", 0.5),
        ("skill_similarity_threshold", 0.80),
        ("skill_gap_similarity_threshold", 0.72),
        ("text_fingerprint_similarity_threshold", 0.80),
        ("structural_similarity_threshold", 0.75),
        ("deck_plagiarism_similarity_threshold", 0.90),
        ("photo_hash_distance_threshold", 4),
        ("min_population_for_percentile", 30),
        ("min_population_for_assessment_percentile", 10),
        ("max_followups_per_topic", 1),
        ("document_generation_max_attempts", 2),
        ("recruitment_shortlist_limit", 50),
        ("interview_max_verbatim_turns", 6),
        ("interview_max_turn_chars", 1200),
        ("github_max_repos", 15),
        ("agent_max_concurrency", 5),
        ("github_http_timeout_seconds", 15.0),
        ("leetcode_http_timeout_seconds", 15.0),
        ("issuer_lookup_timeout_seconds", 6.0),
        ("photo_fetch_timeout_seconds", 8.0),
        ("oauth_exchange_timeout_seconds", 10.0),
        ("qdrant_timeout_seconds", 5.0),
        ("libreoffice_timeout_seconds", 60),
        ("career_recommendation_ttl_hours", 24),
        ("github_oauth_state_ttl_seconds", 600),
        ("stats_refresh_cooldown_minutes", 15),
        ("max_dashboard_projects", 50),
        ("max_score_history", 30),
        ("candidate_pool_cache_ttl_seconds", 30),
        ("max_candidate_pool", 5000),
        ("event_poll_interval_seconds", 30.0),
        ("salary_currency", "USD"),
        ("salary_talent_score_max_adjustment", 0.15),
        ("salary_talent_score_baseline", 50.0),
        # LLM reliability defaults — 1024 was the previously-hardcoded Anthropic ceiling.
        ("llm_max_tokens_default", 1024),
        ("llm_temperature_deterministic", 0.0),
    ],
)
def test_setting_default_matches_previous_literal(settings, name, expected) -> None:
    assert getattr(settings, name) == expected


@pytest.mark.parametrize(
    "module_path,attribute,setting_name",
    [
        ("services.agents.recruitment.tools.embeddings", "SKILL_SIMILARITY_THRESHOLD", "skill_similarity_threshold"),
        ("services.agents.candidate_intelligence.tools.skill_gap", "_GAP_SIMILARITY_THRESHOLD", "skill_gap_similarity_threshold"),
        ("services.agents.fraud.tools.text_fingerprint", "SIMILARITY_FLAG_THRESHOLD", "text_fingerprint_similarity_threshold"),
        ("services.agents.fraud.tools.structural_similarity", "SIMILARITY_FLAG_THRESHOLD", "structural_similarity_threshold"),
        ("services.agents.ppt_analyzer.tools.plagiarism", "SIMILARITY_THRESHOLD", "deck_plagiarism_similarity_threshold"),
        ("services.agents.fraud.tools.photo_hash", "HAMMING_DISTANCE_FLAG_THRESHOLD", "photo_hash_distance_threshold"),
        ("services.agents.recruitment.nodes.hybrid_search", "_SHORTLIST_LIMIT", "recruitment_shortlist_limit"),
        ("services.agents.assessment.nodes.turn_evaluation", "_MAX_FOLLOWUPS_PER_TOPIC", "max_followups_per_topic"),
        ("services.agents.candidate_intelligence.resume_graph", "MAX_ATTEMPTS", "document_generation_max_attempts"),
    ],
)
def test_agent_constants_resolve_from_settings(settings, module_path, attribute, setting_name) -> None:
    """Each agent constant must be the configured value, not a stale duplicate literal."""
    from importlib import import_module

    assert getattr(import_module(module_path), attribute) == getattr(settings, setting_name)


def test_the_two_similarity_thresholds_that_used_to_share_a_name_are_distinct() -> None:
    """`SIMILARITY_FLAG_THRESHOLD` existed twice, in two modules, with different values.

    They are legitimately different numbers for different jobs — the hazard was that
    reading one told you nothing about the other. They now have distinct setting names;
    this guards against someone "tidying" them into a single value.
    """
    from services.agents.fraud.tools import structural_similarity, text_fingerprint

    assert text_fingerprint.SIMILARITY_FLAG_THRESHOLD != structural_similarity.SIMILARITY_FLAG_THRESHOLD


# --- Shared constants ----------------------------------------------------------------


def test_shared_constants_match_the_literals_they_replaced() -> None:
    from services.api.common.constants import (
        AI_CONTENT_FLAG_THRESHOLD,
        ERROR_TRUNCATE_CHARS,
        MAX_PAGE_SIZE,
        clamp_page_size,
        truncate_error,
    )

    assert MAX_PAGE_SIZE == 500
    assert ERROR_TRUNCATE_CHARS == 2000
    assert AI_CONTENT_FLAG_THRESHOLD == 70.0
    assert clamp_page_size(9999) == 500
    assert clamp_page_size(0) == 1
    assert clamp_page_size(50) == 50
    assert len(truncate_error(Exception("x" * 5000))) == 2000


def test_ai_content_threshold_is_shared_by_both_detectors() -> None:
    """The PPT and fraud detectors are documented as deliberately using the same method.

    They previously re-declared the flag cutoff independently, so the two could drift
    into disagreeing about the same text.
    """
    import inspect

    from services.agents.fraud.tools import perplexity_heuristic
    from services.agents.ppt_analyzer.tools import ai_content_heuristic

    for module in (ai_content_heuristic, perplexity_heuristic):
        source = inspect.getsource(module)
        assert "AI_CONTENT_FLAG_THRESHOLD" in source
        assert ">= 70.0" not in source, f"{module.__name__} still hardcodes the cutoff"
