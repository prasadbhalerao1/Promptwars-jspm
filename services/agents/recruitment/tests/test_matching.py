"""Job-matching formula (FR-2): the four terms and their weighted aggregation.

These functions decide which candidates a recruiter sees first, so the rules that matter
most are pinned directly:

* a verified skill beats the same skill merely claimed on a résumé (anti keyword-stuffing);
* a job with no stated requirement is *inapplicable*, never a zero that drags everyone
  down equally — its weight is redistributed instead;
* every term stays within 0-100 regardless of input.

The embedding fallback (`best_skill_similarity`) is replaced with a deterministic stub, so
no test loads the sentence-transformer model.
"""

from __future__ import annotations

import pytest

from services.agents.recruitment.tools import matching
from services.agents.recruitment.tools.matching import CandidateSkillSignal as Skill


@pytest.fixture
def no_fuzzy_matches(monkeypatch):
    monkeypatch.setattr(matching, "best_skill_similarity", lambda names, required: ("", 0.0))


@pytest.fixture
def fuzzy(monkeypatch):
    """Configure near-miss similarities: `fuzzy({"React": 0.9})`."""

    def install(similarities: dict[str, float]) -> None:
        monkeypatch.setattr(
            matching,
            "best_skill_similarity",
            lambda names, required: ("near", similarities.get(required, 0.0)),
        )

    return install


# --- skill_overlap ---------------------------------------------------------------------


def test_verified_skill_outscores_the_same_skill_self_declared(no_fuzzy_matches) -> None:
    verified = matching.skill_overlap([Skill("Python", True)], ["Python"])
    claimed = matching.skill_overlap([Skill("Python", False)], ["Python"])
    assert verified == 100.0
    assert claimed == 60.0


def test_skill_match_is_case_insensitive(no_fuzzy_matches) -> None:
    assert matching.skill_overlap([Skill("postgresql", True)], ["PostgreSQL"]) == 100.0


def test_overlap_is_the_share_of_required_skills_covered(no_fuzzy_matches) -> None:
    skills = [Skill("Python", True), Skill("Docker", False)]
    # 1.0 (verified) + 0.6 (claimed) + 0 (missing) over 3 required skills.
    assert matching.skill_overlap(skills, ["Python", "Docker", "Kubernetes"]) == pytest.approx(53.3)


def test_no_required_skills_scores_zero_rather_than_dividing_by_zero(no_fuzzy_matches) -> None:
    assert matching.skill_overlap([Skill("Python", True)], []) == 0.0


def test_near_miss_skill_earns_discounted_partial_credit(fuzzy) -> None:
    threshold = matching.SKILL_SIMILARITY_THRESHOLD
    fuzzy({"React": 0.9, "Rust": threshold - 0.01})
    skills = [Skill("Vue.js", True)]

    assert matching.skill_overlap(skills, ["React"]) == pytest.approx(round(100 * 0.6 * 0.9, 1))
    # Below the similarity threshold earns nothing.
    assert matching.skill_overlap(skills, ["Rust"]) == 0.0


# --- experience_match ------------------------------------------------------------------


@pytest.mark.parametrize("minimum", [None, 0, -1])
def test_job_without_a_minimum_is_inapplicable_not_zero(minimum) -> None:
    assert matching.experience_match(5, minimum) is None


@pytest.mark.parametrize(
    ("years", "minimum", "expected"),
    [(None, 3, 0.0), (0, 3, 0.0), (1.5, 3, 50.0), (3, 3, 100.0), (20, 2, 100.0)],
)
def test_experience_ratio_is_capped_at_full_credit(years, minimum, expected) -> None:
    assert matching.experience_match(years, minimum) == expected


# --- filter_match_ratio / semantic_similarity -----------------------------------------


@pytest.mark.parametrize(
    ("candidate", "job", "remote", "expected"),
    [
        ("Pune", "Mumbai", True, 1.0),  # remote role: location never filters
        ("Pune", None, False, 1.0),  # no location requirement
        (None, "Pune", False, 0.5),  # unknown candidate location is not a hard fail
        (" pune ", "Pune", False, 1.0),  # normalized comparison
        ("Pune", "Mumbai", False, 0.0),
    ],
)
def test_location_filter(candidate, job, remote, expected) -> None:
    assert matching.filter_match_ratio(candidate, job, remote) == expected


@pytest.mark.parametrize("cosine", [-1.0, -0.2, 0.0, 0.5, 1.0, 1.7])
def test_semantic_similarity_stays_in_range(cosine) -> None:
    for ratio in (0.0, 0.5, 1.0):
        assert 0.0 <= matching.semantic_similarity(cosine, ratio) <= 100.0


def test_negative_cosine_is_clamped_to_no_semantic_credit() -> None:
    alpha = matching.SEMANTIC_ALPHA
    assert matching.semantic_similarity(-0.8, 1.0) == pytest.approx(round(100 * (1 - alpha), 1))


# --- talent_score_alignment -------------------------------------------------------------


def test_no_base_score_yields_none() -> None:
    score, meta = matching.talent_score_alignment(None)
    assert score is None
    assert meta["reason"] == "no_base_score"


def test_missing_context_passes_the_base_score_through_clamped() -> None:
    assert matching.talent_score_alignment(82.44)[0] == 82.4
    assert matching.talent_score_alignment(130.0)[0] == 100.0


def test_full_skill_coverage_does_not_penalize(no_fuzzy_matches) -> None:
    subs = {"coding_ability": 80.0, "problem_solving": 70.0, "leadership": 60.0}
    score, meta = matching.talent_score_alignment(
        75.0, subs, [Skill("Python", True)], ["Python"]
    )
    assert meta["skill_overlap_ratio"] == 1.0
    # Only project_quality/innovation are discounted at full coverage, and neither is present.
    assert meta["adjusted_sub_scores"] == subs
    assert 0.0 <= score <= 100.0


def test_missing_job_skills_lower_the_contextual_score(no_fuzzy_matches) -> None:
    subs = {"coding_ability": 90.0, "problem_solving": 90.0, "leadership": 50.0}
    covered, _ = matching.talent_score_alignment(80.0, subs, [Skill("Go", True)], ["Go"])
    uncovered, meta = matching.talent_score_alignment(80.0, subs, [Skill("Go", True)], ["Rust"])
    assert meta["skill_overlap_ratio"] == 0.0
    assert uncovered < covered


# --- aggregate_match_score ---------------------------------------------------------------


def test_aggregate_with_all_terms_is_the_weighted_sum() -> None:
    expected = (
        matching.W_SKILL_OVERLAP * 80
        + matching.W_SEMANTIC_SIMILARITY * 60
        + matching.W_EXPERIENCE_MATCH * 100
        + matching.W_TALENT_SCORE_ALIGNMENT * 70
    ) / (
        matching.W_SKILL_OVERLAP
        + matching.W_SEMANTIC_SIMILARITY
        + matching.W_EXPERIENCE_MATCH
        + matching.W_TALENT_SCORE_ALIGNMENT
    )
    assert matching.aggregate_match_score(80, 60, 100, 70) == pytest.approx(round(expected, 1))


def test_missing_terms_redistribute_weight_instead_of_counting_as_zero() -> None:
    # With experience and talent alignment unknown, a candidate perfect on the remaining
    # two terms is a perfect match — not penalized by the inapplicable terms.
    assert matching.aggregate_match_score(100, 100, None, None) == 100.0
    assert matching.aggregate_match_score(100, 100, 0.0, 0.0) < 100.0
