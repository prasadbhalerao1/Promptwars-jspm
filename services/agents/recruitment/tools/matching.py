"""Deterministic scoring primitives for FR-2 (AI Job Matching Engine). Plain functions,
no LLM, no I/O — same convention as candidate_intelligence's `mechanical_scores.py`.
Implements doc/multi-agent-architecture/08 §2's 4-term formula exactly:

    MatchScore = w1*SkillOverlap + w2*SemanticSimilarity + w3*ExperienceMatch + w4*TalentScoreAlignment

Weights below are the doc's explicitly-called-out "tunable default, not a validated
constant" — chosen and logged in .agents/decisions.md rather than silently picked, same
resolution style as Module 01's additive-but-undocumented schema choices.
"""

from dataclasses import dataclass

from services.agents.common.scoring import weighted_renormalized_mean
from services.api.core.config import get_settings
from services.agents.recruitment.tools.embeddings import SKILL_SIMILARITY_THRESHOLD, best_skill_similarity

# doc 08 §2 canonical weights — tunable defaults, sum to 1.0. Now resolved from Settings
# rather than frozen as literals: this module already described them as "tunable", which
# is exactly the argument for not requiring a deploy to tune them. Module-level names are
# kept so existing importers and tests are unaffected.
_settings = get_settings()
W_SKILL_OVERLAP = _settings.match_weight_skill_overlap
W_SEMANTIC_SIMILARITY = _settings.match_weight_semantic_similarity
W_EXPERIENCE_MATCH = _settings.match_weight_experience_match
W_TALENT_SCORE_ALIGNMENT = _settings.match_weight_talent_score_alignment

# Internal blend ratio for SemanticSimilarity = alpha*cos(v_C, v_J) + (1-alpha)*FilterMatchRatio.
SEMANTIC_ALPHA = _settings.match_semantic_alpha


@dataclass
class CandidateSkillSignal:
    """A candidate's skill, tagged with how it was sourced — `verified` skills (GitHub
    repo language stats, verified certificates) count more than raw self-declared resume
    text, per doc 08 §2: "SkillOverlap weights verified signals ... to reduce
    keyword-stuffing." Mirrors the same anti-gaming intent as Module 01's Talent Score."""

    name: str
    verified: bool


def skill_overlap(candidate_skills: list[CandidateSkillSignal], required_skills: list[str]) -> float:
    """0-100. Each required skill present (case-insensitive) in the candidate's skill
    list contributes to the overlap ratio; a `verified` match contributes a full point,
    an unverified (self-declared) match contributes a discounted 0.6 point — this is
    what makes resume keyword-stuffing score lower than the same skill backed by an
    actual GitHub repo or verified certificate.

    A required skill with no exact/case-insensitive match falls back to embedding
    similarity against the candidate's own skill list (e.g. a candidate listing "Vue.js"
    against a job requiring "React" previously scored zero overlap for that skill, even
    though Qdrant already computes exactly this kind of skill-name embedding elsewhere in
    this codebase for Copilot search). A near-miss above SKILL_SIMILARITY_THRESHOLD earns
    partial, similarity-scaled credit, further discounted like an unverified match since
    it's inferred rather than a literal skill the candidate actually claimed."""
    if not required_skills:
        return 0.0
    candidate_by_name = {s.name.lower(): s.verified for s in candidate_skills}
    candidate_names = [s.name for s in candidate_skills]
    earned = 0.0
    for required in required_skills:
        verified = candidate_by_name.get(required.lower())
        if verified is True:
            earned += 1.0
        elif verified is False:
            earned += 0.6
        else:
            _, similarity = best_skill_similarity(candidate_names, required)
            if similarity >= SKILL_SIMILARITY_THRESHOLD:
                earned += 0.6 * similarity
    return round(100.0 * earned / len(required_skills), 1)


def experience_match(candidate_years: float | None, min_experience_years: int | None) -> float | None:
    """0-100. `None` (never 0) when the job has no stated minimum — an unconstrained job
    isn't a bad experience match, it's an inapplicable one, and the aggregation step must
    re-normalize around it rather than punish every candidate equally."""
    if min_experience_years is None or min_experience_years <= 0:
        return None
    if candidate_years is None:
        return 0.0
    ratio = candidate_years / min_experience_years
    # Meeting the bar is full credit; exceeding it doesn't keep climbing forever (a 20-year
    # veteran isn't a "200% match" for a 2-year-minimum role) but isn't penalized either.
    return round(100.0 * min(ratio, 1.0), 1)


def talent_score_alignment(
    candidate_overall_talent_score: float | None,
    candidate_sub_scores: dict[str, float | None] | None = None,
    candidate_skills: list[CandidateSkillSignal] | None = None,
    required_skills: list[str] | None = None,
) -> tuple[float | None, dict]:
    """Job-contextual Talent Score (0-100). Adjusts the candidate's base Talent Score based on
    how well their demonstrated skills match this specific job's requirements.

    Returns (adjusted_score, metadata) where metadata includes adjustment_factor and reasoning.
    When candidate has no sub-scores or required_skills is empty/None, returns the base score
    unadjusted (backward-compatible).

    Algorithm:
    1. Compute skill overlap ratio (how many job-required skills the candidate has)
    2. Adjust coding_ability and problem_solving by this ratio (job-critical dimensions)
    3. Adjust project_quality and innovation by ratio × 0.8 (related but not primary)
    4. Recompute overall score with adjusted sub-scores, using original weights
    """
    if candidate_overall_talent_score is None:
        return None, {"adjustment_factor": 1.0, "reason": "no_base_score"}

    # Backward compat: if sub-scores/skills/requirements missing, passthrough
    if not candidate_sub_scores or not required_skills or not candidate_skills:
        return (
            round(max(0.0, min(100.0, candidate_overall_talent_score)), 1),
            {"adjustment_factor": 1.0, "reason": "insufficient_context"},
        )

    # Compute skill overlap ratio: what fraction of job-required skills does candidate have?
    candidate_by_name = {s.name.lower(): s for s in candidate_skills}
    matched_skills = 0
    for required in required_skills:
        if required.lower() in candidate_by_name:
            matched_skills += 1
        else:
            candidate_names = [s.name for s in candidate_skills]
            _, similarity = best_skill_similarity(candidate_names, required)
            if similarity >= SKILL_SIMILARITY_THRESHOLD:
                matched_skills += similarity

    skill_overlap_ratio = matched_skills / len(required_skills) if required_skills else 0.0
    skill_overlap_ratio = min(1.0, max(0.0, skill_overlap_ratio))

    # Adjust specific sub-scores based on skill match
    from services.agents.candidate_intelligence.tools.aggregate import SUB_SCORE_WEIGHTS

    adjusted_sub_scores = {}
    for name, value in candidate_sub_scores.items():
        if value is None:
            adjusted_sub_scores[name] = None
        elif name in ("coding_ability", "problem_solving"):
            adjusted_sub_scores[name] = value * skill_overlap_ratio
        elif name in ("project_quality", "innovation"):
            adjusted_sub_scores[name] = value * (skill_overlap_ratio * 0.8)
        else:
            adjusted_sub_scores[name] = value

    # Recompute overall score with adjusted sub-scores, using original weights
    available = {name: s for name, s in adjusted_sub_scores.items() if s is not None}
    if not available:
        return (
            round(max(0.0, min(100.0, candidate_overall_talent_score)), 1),
            {"adjustment_factor": 1.0, "reason": "no_available_sub_scores_after_adjustment"},
        )

    adjusted_overall = weighted_renormalized_mean(
        [(SUB_SCORE_WEIGHTS.get(name, 0.0), s) for name, s in available.items()]
    )

    if adjusted_overall is None:
        adjusted_overall = candidate_overall_talent_score

    adjusted_overall = round(max(0.0, min(100.0, adjusted_overall)), 1)
    adjustment_factor = adjusted_overall / candidate_overall_talent_score if candidate_overall_talent_score else 1.0

    return adjusted_overall, {
        "adjustment_factor": round(adjustment_factor, 2),
        "skill_overlap_ratio": round(skill_overlap_ratio, 2),
        "reason": "contextual_adjustment",
        "adjusted_sub_scores": {k: round(v, 1) if v is not None else None for k, v in adjusted_sub_scores.items()},
    }


def filter_match_ratio(
    candidate_location: str | None,
    job_location: str | None,
    job_is_remote: bool,
) -> float:
    """0-1. The FilterMatchRatio half of SemanticSimilarity's blend (doc 08 §2) — how many
    of the job's hard filters (right now: location/remote) the candidate satisfies."""
    if job_is_remote:
        return 1.0
    if not job_location:
        return 1.0
    if not candidate_location:
        return 0.5  # unknown, not a hard fail
    return 1.0 if candidate_location.strip().lower() == job_location.strip().lower() else 0.0


def semantic_similarity(cosine_similarity: float, filter_match_ratio_value: float) -> float:
    """0-100. `cosine_similarity` is expected in [-1, 1] from the embedding comparison;
    clamped to [0, 1] before blending since a negative cosine isn't a meaningful "match
    quality" signal here."""
    cos = max(0.0, min(1.0, cosine_similarity))
    blended = SEMANTIC_ALPHA * cos + (1 - SEMANTIC_ALPHA) * filter_match_ratio_value
    return round(100.0 * blended, 1)


def aggregate_match_score(
    skill_overlap_value: float,
    semantic_similarity_value: float,
    experience_match_value: float | None,
    talent_score_alignment_value: float | None,
) -> float:
    """The 4-term weighted sum, re-normalized (same technique as doc 08 §1.1's Talent
    Score cold-start handling) when experience_match or talent_score_alignment is `None`
    — their weight is redistributed proportionally across whichever terms ARE available,
    never silently treated as a zero score."""
    terms = [
        (W_SKILL_OVERLAP, skill_overlap_value),
        (W_SEMANTIC_SIMILARITY, semantic_similarity_value),
        (W_EXPERIENCE_MATCH, experience_match_value),
        (W_TALENT_SCORE_ALIGNMENT, talent_score_alignment_value),
    ]
    result = weighted_renormalized_mean(terms)
    # Unlike the other 4 sites reusing this helper, a total weight of zero here falls
    # back to 0.0 rather than None — skill_overlap_value/semantic_similarity_value are
    # never actually None in practice (both always resolve to a number upstream), so
    # this branch is effectively unreachable defensive code, not a real cold-start case.
    return round(result, 1) if result is not None else 0.0
