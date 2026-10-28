"""Talent Scoring Agent — doc 01 §4/§6, formula in doc 08 §1, v2 robustness pass.

Sonnet for Project Quality & Innovation (judgment calls); rules for the rest — this
node computes all 7 the same way the doc's agent registry describes, just without a
separate LLM call wrapper per sub-score (the LLM calls live inside the judgment tools).

Population/assessment data is injected via state (fetched by the router, which owns the
DB session) rather than queried here — this node stays DB-free, same convention as the
rest of candidate_intelligence.
"""

import asyncio

from packages.shared_schemas.candidates import SubScore
from services.agents.candidate_intelligence.state import CandidateProfileState
from services.agents.candidate_intelligence.tools import mechanical_scores
from services.agents.candidate_intelligence.tools.aggregate import compute_confidence, compute_overall
from services.agents.candidate_intelligence.tools.github import GithubAnalysis
from services.agents.candidate_intelligence.tools.judgment_scores import (
    code_quality_score,
    innovation,
    project_quality,
    sample_complexity,
)
from services.agents.candidate_intelligence.tools.open_source_score import open_source_contributions
from services.agents.candidate_intelligence.tools.hackathon_score import hackathon_performance
from services.agents.candidate_intelligence.tools.credentials_score import verified_credentials


async def run(state: CandidateProfileState) -> dict:
    github_raw: GithubAnalysis | None = state.get("github_raw")
    empty = GithubAnalysis()
    analysis = github_raw or empty

    assessment_score = state.get("assessment_score")
    assessment_population = state.get("assessment_population") or []

    # Sample repo complexity exactly once and share the result with both consumers
    # (code_quality_score and project_quality) — each used to run its own sampling pass,
    # duplicating every blocking PyGithub round trip. Threaded for the same reason as
    # github_analysis.py's node: it must not stall the event loop.
    if github_raw is not None:
        sampled = await asyncio.to_thread(
            sample_complexity, state["github_username"], state.get("github_access_token"), analysis
        )
        quality_score, _ = code_quality_score(
            state["github_username"], state.get("github_access_token"), analysis, sampled=sampled
        )
        # project_quality and innovation write disjoint keys and share no data
        # dependency — run their LLM/embedding round trips concurrently instead of
        # back-to-back.
        project_quality_score, innovation_score = await asyncio.gather(
            project_quality(
                state["github_username"], state.get("github_access_token"), analysis, sampled=sampled
            ),
            innovation(state["candidate_id"], analysis),
        )
    else:
        quality_score = None
        no_github = "No GitHub data ingested yet."
        project_quality_score = SubScore(value=None, rationale=no_github)
        innovation_score = SubScore(value=None, rationale=no_github)

    # Certificates on file plus one extracted in this run (persisted by the router only
    # after scoring, so it would otherwise miss its own rescore).
    certifications = list(state.get("certifications") or [])
    extracted = state.get("certificate_extracted")
    if extracted:
        certifications.append({**extracted, "verification_status": "unverified"})
    profile_data = state.get("merged_profile") or state.get("resume_parsed") or {}

    raw_sub_scores = {
        "coding_ability": mechanical_scores.coding_ability(
            analysis,
            commit_population=state.get("commit_population") or [],
            quality_score=quality_score,
            assessment_score=assessment_score,
            assessment_population=assessment_population,
        ),
        "problem_solving": mechanical_scores.problem_solving(
            assessment_score, assessment_population, leetcode_stats=state.get("leetcode_stats")
        ),
        "technical_consistency": mechanical_scores.technical_consistency(analysis),
        "community_participation": mechanical_scores.community_participation(
            analysis, star_population=state.get("star_population") or []
        ),
        "leadership": mechanical_scores.leadership(
            analysis, leadership_population=state.get("leadership_population") or []
        ),
        "project_quality": project_quality_score,
        "innovation": innovation_score,
        "open_source_contributions": (
            open_source_contributions(
                analysis, contribution_population=state.get("contribution_population") or []
            )
            if github_raw is not None
            else SubScore(value=None, rationale="No GitHub data ingested yet.")
        ),
        "hackathon_performance": hackathon_performance(
            platform_results=state.get("hackathon_platform_results"),
            self_reported=state.get("hackathon_self_reported"),
        ),
        "verified_credentials": verified_credentials(
            certifications,
            experience=profile_data.get("experience") or [],
            education=profile_data.get("education") or [],
            skills=profile_data.get("skills") or [],
        ),
    }

    from services.agents.candidate_intelligence.competency_registry import (
        EvidenceItem,
        build_competency_assessment,
    )

    enriched_scores: dict[str, SubScore] = {}
    for comp_id, raw in raw_sub_scores.items():
        ev_items: list[EvidenceItem] = []
        if comp_id == "coding_ability":
            for r in (analysis.repos or [])[:5]:
                if not r.is_fork and r.commit_count > 0:
                    ev_items.append(
                        EvidenceItem(
                            source=f"github:{r.repo_full_name}",
                            artifact_type="repository",
                            indicator=f"Authored {r.commit_count} commits in {r.repo_full_name}",
                            provenance=f"https://github.com/{r.repo_full_name}",
                            verification_status="verified",
                        )
                    )
            if assessment_score is not None:
                ev_items.append(
                    EvidenceItem(
                        source="assessment:platform",
                        artifact_type="code_assessment",
                        indicator=f"Completed platform assessment with score {assessment_score}",
                        provenance="platform://assessments",
                        verification_status="verified",
                    )
                )
        elif comp_id == "problem_solving":
            if assessment_score is not None:
                ev_items.append(
                    EvidenceItem(
                        source="assessment:platform",
                        artifact_type="code_assessment",
                        indicator=f"Objective algorithmic assessment score {assessment_score}",
                        provenance="platform://assessments",
                        verification_status="verified",
                    )
                )
            if state.get("leetcode_stats"):
                solved = state["leetcode_stats"].get("total_solved", 0)
                if solved > 0:
                    ev_items.append(
                        EvidenceItem(
                            source="leetcode:profile",
                            artifact_type="algorithmic_practice",
                            indicator=f"Solved {solved} verified LeetCode challenges",
                            provenance="https://leetcode.com",
                            verification_status="third_party",
                        )
                    )
        elif comp_id == "project_quality":
            for s in (sampled[1] if github_raw else []):
                ev_items.append(
                    EvidenceItem(
                        source=f"ast_analysis:{s}",
                        artifact_type="codebase_metrics",
                        indicator=f"Passed AST cyclomatic complexity inspection: {s}",
                        provenance=f"https://github.com/{s}",
                        verification_status="verified",
                    )
                )
        elif comp_id == "leadership":
            if analysis.pr_review_count > 0:
                ev_items.append(
                    EvidenceItem(
                        source="github:reviews",
                        artifact_type="code_reviews",
                        indicator=f"Conducted {analysis.pr_review_count} verified pull request reviews",
                        provenance="https://github.com",
                        verification_status="verified",
                    )
                )
            if analysis.owned_repo_count > 0:
                ev_items.append(
                    EvidenceItem(
                        source="github:maintainer",
                        artifact_type="repo_ownership",
                        indicator=f"Maintains {analysis.owned_repo_count} public repositories",
                        provenance="https://github.com",
                        verification_status="verified",
                    )
                )
        elif comp_id == "community_participation":
            total_forks = sum(r.forks for r in analysis.repos or [])
            if analysis.total_stars > 0 or total_forks > 0:
                ev_items.append(
                    EvidenceItem(
                        source="github:stars_forks",
                        artifact_type="peer_recognition",
                        indicator=f"Earned {analysis.total_stars} stars and {total_forks} forks from community",
                        provenance="https://github.com",
                        verification_status="verified",
                    )
                )
        elif comp_id == "open_source_contributions":
            if analysis.external_contributions > 0:
                ev_items.append(
                    EvidenceItem(
                        source="github:upstream_prs",
                        artifact_type="external_contributions",
                        indicator=f"Contributed {analysis.external_contributions} commits/PRs to external repositories",
                        provenance="https://github.com",
                        verification_status="verified",
                    )
                )
        elif comp_id == "technical_consistency":
            if analysis.commit_activity_weekly:
                active_weeks = sum(1 for w in analysis.commit_activity_weekly if w > 0)
                ev_items.append(
                    EvidenceItem(
                        source="github:weekly_cadence",
                        artifact_type="commit_history",
                        indicator=f"Active across {active_weeks} weeks in 52-week observation window",
                        provenance="https://github.com",
                        verification_status="verified",
                    )
                )
        elif comp_id == "verified_credentials":
            for cert in certifications:
                ev_items.append(
                    EvidenceItem(
                        source=f"certificate:{cert.get('title') or 'untitled'}",
                        artifact_type="certificate",
                        indicator=f"Certificate: {cert.get('title') or 'untitled'}",
                        provenance=cert.get("credential_id") or "uploaded certificate",
                        verification_status=(
                            "verified" if cert.get("verification_status") == "verified" else "self_reported"
                        ),
                    )
                )
        elif comp_id == "hackathon_performance":
            hackathons = state.get("hackathon_self_reported") or []
            for h in hackathons:
                ev_items.append(
                    EvidenceItem(
                        source=f"hackathon:{h.get('name')}",
                        artifact_type="competitive_hackathon",
                        indicator=f"{h.get('result', 'participant').capitalize()} at {h.get('name')}",
                        provenance=h.get('name'),
                        verification_status="self_reported",
                    )
                )

        assessment = build_competency_assessment(
            competency_id=comp_id,
            raw_value=raw.value,
            evidence_items=ev_items,
            rationale=raw.rationale or "Competency evaluation complete.",
        )
        enriched_scores[comp_id] = SubScore(
            value=assessment["value"],
            evidence=assessment["evidence"],
            rationale=assessment["rationale"],
            status=assessment["status"],
            rubric_level=assessment["rubric_level"],
            indicators=assessment["indicators"],
            missing_evidence=assessment["missing_evidence"],
            limitations=assessment["limitations"],
            evidence_coverage=assessment["evidence_coverage"],
            provenance_items=assessment["provenance_items"],
        )

    overall, renormalized = compute_overall(enriched_scores)
    confidence = compute_confidence(enriched_scores)

    return {
        "sub_scores": enriched_scores,
        "overall_score": overall,
        "renormalized_subscores": renormalized,
        "confidence": confidence,
    }
