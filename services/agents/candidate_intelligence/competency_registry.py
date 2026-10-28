"""Versioned Competency Registry — TRACE Talent Intelligence (v2.0).

Enforces Measurement Validity:
1. Every competency defines precise measurable behavior, applicable job families,
   observable indicators, permitted evidence sources, and explicit exclusions.
2. Concrete behavioral rating anchors (Level 1-5).
3. Status outcomes: SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, NOT_ASSESSED.
4. Separates evidence coverage from demonstrated score performance.
5. No silent zeros for unobserved criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssessmentStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_ASSESSED = "not_assessed"
    CONFLICTING = "conflicting"


@dataclass
class EvidenceItem:
    source: str
    artifact_type: str
    indicator: str
    provenance: str
    verification_status: str  # "verified" | "self_reported" | "third_party"
    excerpt: str | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "artifact_type": self.artifact_type,
            "indicator": self.indicator,
            "provenance": self.provenance,
            "verification_status": self.verification_status,
            "excerpt": self.excerpt,
            "timestamp": self.timestamp,
        }


@dataclass
class CompetencyDefinition:
    id: str
    name: str
    version: str
    definition: str
    applicable_job_families: list[str]
    observable_indicators: list[str]
    permitted_sources: list[str]
    explicit_exclusions: list[str]
    rubric_anchors: dict[int, str]
    min_evidence_items: int = 1


COMPETENCY_REGISTRY: dict[str, CompetencyDefinition] = {
    "coding_ability": CompetencyDefinition(
        id="coding_ability",
        name="Coding Ability & Implementation Depth",
        version="v2.0",
        definition="Observable capacity to write syntactically correct, modular, maintainable code and solve algorithmic challenges.",
        applicable_job_families=["Software Engineering", "Full Stack", "Backend", "Frontend", "AI / Data Systems"],
        observable_indicators=[
            "Multi-file modular architecture (functions, classes, packages)",
            "Systematic error handling and input validation in core paths",
            "Automated test suites (unit, integration, or e2e tests)",
            "Algorithmic correctness on objective platform coding assessments",
        ],
        permitted_sources=["github_repositories", "github_commits", "code_assessments"],
        explicit_exclusions=[
            "High commit count alone does not establish coding ability.",
            "Forked code without attributable commits is excluded.",
            "Generic framework boilerplate without original logic is excluded.",
        ],
        rubric_anchors={
            1: "Minimal / Incomplete: Fragmentary code, syntax errors, or trivial single-file scripts.",
            2: "Basic / Unverified: Basic scripts functioning but lacking modularity, error handling, or tests.",
            3: "Competent: Production-style code with clear module separation, basic error handling, and clean structure.",
            4: "Advanced: Robust codebases with automated testing, clear architectural patterns, and defensive exception handling.",
            5: "Exemplary: High-complexity systems, reusable libraries, high test coverage, and proven algorithmic efficiency.",
        },
    ),
    "problem_solving": CompetencyDefinition(
        id="problem_solving",
        name="Analytical Problem Solving",
        version="v2.0",
        definition="Capacity to dissect complex technical challenges, handle edge cases, balance trade-offs, and implement verifiable solutions.",
        applicable_job_families=["Software Engineering", "Full Stack", "Backend", "AI / Data Systems"],
        observable_indicators=[
            "Verified solutions to data structure and algorithm challenges across difficulty tiers",
            "Handling of boundary and edge cases verified by passing test suites",
            "Optimization of asymptotic time and space complexity",
        ],
        permitted_sources=["leetcode_verified", "code_assessments", "complex_repo_architectures"],
        explicit_exclusions=[
            "LeetCode problem counts alone do not measure broad real-world problem-solving capability.",
            "Closing GitHub issues without code changes is excluded.",
        ],
        rubric_anchors={
            1: "Unassessed: No verified algorithmic or technical problem-solving artifacts available.",
            2: "Foundational: Demonstrates solutions to elementary, single-pattern challenges.",
            3: "Competent: Solves multi-step algorithmic and data structure problems with correct asymptotic complexity.",
            4: "Advanced: Solves diverse medium/hard technical challenges, handles non-trivial edge cases, and optimizes bottlenecks.",
            5: "Exceptional: Proven track record in complex competitive or distributed system problem decomposition.",
        },
    ),
    "project_quality": CompetencyDefinition(
        id="project_quality",
        name="Software Engineering Quality & Architecture",
        version="v2.0",
        definition="Adherence to software design principles, low cyclomatic complexity, clear abstraction boundaries, and maintainable structure.",
        applicable_job_families=["Software Engineering", "Full Stack", "Backend", "Frontend", "AI / Data Systems"],
        observable_indicators=[
            "Low average cyclomatic complexity (Radon CC <= 10)",
            "Clear separation of concerns (controller, service, repository, UI)",
            "Comprehensive documentation and environment setup guides",
        ],
        permitted_sources=["static_code_analysis", "ast_complexity", "github_repositories"],
        explicit_exclusions=[
            "Total lines of code or repo size does NOT measure technical quality.",
            "Over-engineered or convoluted code is penalized, not rewarded as quality.",
        ],
        rubric_anchors={
            1: "High Complexity: Monolithic files, cyclomatic complexity > 25, lacking structure.",
            2: "Acceptable: Working code with moderate complexity, partial organization.",
            3: "Good: Clean separation, standard package conventions, low complexity in critical paths.",
            4: "High: Idiomatic design patterns, comprehensive type annotations, modular components.",
            5: "Outstanding: Production-grade architectural rigor, comprehensive testing, and optimal complexity metrics.",
        },
    ),
    "leadership": CompetencyDefinition(
        id="leadership",
        name="Technical Ownership & Leadership",
        version="v2.0",
        definition="Observable ownership of technical initiatives, architectural decision records, code review guidance, and project coordination.",
        applicable_job_families=["Software Engineering", "Full Stack", "Backend", "Engineering Leadership"],
        observable_indicators=[
            "Authoring and merging substantive PRs across collaborative repositories",
            "Conducting code reviews and providing actionable review feedback",
            "Writing architectural documentation, RFCs, or contributing guides",
            "Maintaining active open-source projects used by external developers",
        ],
        permitted_sources=["code_reviews", "pull_request_reviews", "repo_ownership", "maintainer_contributions"],
        explicit_exclusions=[
            "Self-reported titles (e.g. 'Team Lead', 'Founder') without observable technical artifacts are claims, not proof.",
            "Star counts on personal forks do not establish leadership.",
        ],
        rubric_anchors={
            1: "Individual Contributor: Contributes code without observable review or coordination artifacts.",
            2: "Emerging Ownership: Owns personal projects with clear issue tracking and release management.",
            3: "Collaborative Leader: Conducts pull request reviews, mentors teammates, and defines project structure.",
            4: "Proven Technical Lead: Manages multi-contributor projects, arbitrates architecture decisions, and maintains release cadence.",
            5: "Organization / Community Leader: Recognized maintainer of multi-stakeholder systems with high external adoption.",
        },
    ),
    "innovation": CompetencyDefinition(
        id="innovation",
        name="Technical Innovation & Novelty",
        version="v2.0",
        definition="Introduction of novel architectures, creative domain applications, or unique integration solutions beyond standard tutorial clones.",
        applicable_job_families=["Software Engineering", "AI / Data Systems", "R&D"],
        observable_indicators=[
            "Implementation of non-boilerplate architectures (custom agent graphs, distributed queues, specialized ML)",
            "Addressing uncommon problems or combining disparate domains creatively",
            "Semantic divergence from cookie-cutter tutorial repositories",
        ],
        permitted_sources=["project_novelty_embeddings", "unique_domain_implementations"],
        explicit_exclusions=[
            "Using a newly released framework or an API wrapper does NOT constitute technical innovation.",
            "Complexity for complexity's sake is not rewarded.",
        ],
        rubric_anchors={
            1: "Derivative: Standard tutorial implementations, cloned template projects.",
            2: "Applied: Standard stack applied to familiar domain with minor customizations.",
            3: "Substantive: Custom business logic, novel integration of multiple services or custom data pipelines.",
            4: "Innovative: Original system architecture, specialized algorithms, or novel problem space solutions.",
            5: "Groundbreaking: Breakthrough open-source tooling, published research implementation, or novel technical patents/paradigms.",
        },
    ),
    "technical_consistency": CompetencyDefinition(
        id="technical_consistency",
        name="Engineering Consistency & Delivery Cadence",
        version="v2.0",
        definition="Regular, recency-weighted software delivery cadence demonstrating sustained commitment and maintenance over time.",
        applicable_job_families=["Software Engineering", "Full Stack", "Backend", "Frontend"],
        observable_indicators=[
            "Steady weekly or bi-weekly commit activity over a 52-week window",
            "Sustained active day streaks without year-long abandons",
            "Ongoing maintenance of repositories post-initial release",
        ],
        permitted_sources=["github_calendar", "commit_activity_weekly"],
        explicit_exclusions=[
            "Inactivity periods due to proprietary employment or private repos are not penalized as unreliability.",
            "Artificially generated bot commits (e.g. scheduled readme updaters) are disqualified.",
        ],
        rubric_anchors={
            1: "Sporadic: Single isolated burst of activity with no follow-up maintenance.",
            2: "Intermittent: Activity clustered in 1-2 months of the year.",
            3: "Consistent: Active across multiple quarters with steady development cadence.",
            4: "Highly Reliable: Multi-week continuous delivery, active maintenance across several projects.",
            5: "Exceptional Cadence: Sustained year-round active development and high maintenance discipline.",
        },
    ),
    "community_participation": CompetencyDefinition(
        id="community_participation",
        name="Ecosystem & Community Engagement",
        version="v2.0",
        definition="Engagement with the wider developer community through open feedback, issues, discussions, and external stars.",
        applicable_job_families=["Software Engineering", "Open Source Developer", "Developer Relations"],
        observable_indicators=[
            "External developers starring or forking owned repositories",
            "Participating in technical discussions, filing high-quality bug reports, and answering community questions",
        ],
        permitted_sources=["github_stars", "github_forks", "external_contributions"],
        explicit_exclusions=[
            "Self-stars, bot stars, and star-for-star exchange rings are excluded.",
        ],
        rubric_anchors={
            1: "Isolated: Zero external engagement, no stars, no forks.",
            2: "Recognized: Modest peer recognition (1-10 organic stars, occasional issue interaction).",
            3: "Active Participant: 10-50 stars, active issue dialogue, recognized community contributor.",
            4: "Broad Reach: 50-250 stars, multiple external contributors, active issue triage.",
            5: "High-Impact Ecosystem: Widely starred repositories (>250), active community adoption.",
        },
    ),
    "open_source_contributions": CompetencyDefinition(
        id="open_source_contributions",
        name="Upstream Open Source Contributions",
        version="v2.0",
        definition="Measurable contributions made to repositories owned by external organizations or third parties.",
        applicable_job_families=["Software Engineering", "Open Source Developer"],
        observable_indicators=[
            "Pull requests merged into external non-fork repositories",
            "Code reviews submitted to open-source projects",
            "Fixing upstream issues or contributing to documentation and testing",
        ],
        permitted_sources=["external_pull_requests", "merged_commits_in_external_repos"],
        explicit_exclusions=[
            "Commits to personal repositories or forks under the candidate's own handle do NOT count as open source contributions.",
        ],
        rubric_anchors={
            1: "No Upstream Evidence: All activity is confined to owned personal repositories.",
            2: "Initial Explorer: 1-2 merged PRs or documentation contributions to external repos.",
            3: "Active Contributor: Multiple merged PRs with substantive code changes in foreign repos.",
            4: "Core Contributor: Regular upstream contributor to notable open-source dependencies.",
            5: "Key Maintainer: Active maintainer or major contributor to high-visibility open-source projects.",
        },
    ),
    "hackathon_performance": CompetencyDefinition(
        id="hackathon_performance",
        name="Competitive Hackathon & Innovation Performance",
        version="v2.0",
        definition="Demonstrated ability to rapidly prototype, present, and place in competitive time-constrained innovation hackathons.",
        applicable_job_families=["Software Engineering", "Product Engineer", "Full Stack"],
        observable_indicators=[
            "Documented winner, finalist, or top-5 placement in competitive hackathons",
            "Delivery of working end-to-end prototypes under hackathon constraints",
        ],
        permitted_sources=["platform_hackathons", "verified_external_hackathon_entries"],
        explicit_exclusions=[
            "Participation certificates without working project submissions carry minimal weight.",
        ],
        rubric_anchors={
            1: "Participant: Registered or attended hackathon without verifiable placed finish.",
            2: "Completed: Submitted working project meeting all hackathon requirements.",
            3: "Finalist: Top 10 or finalist placement in competitive hackathon.",
            4: "Winner / Top 3: 1st-3rd place finish in university or regional hackathon.",
            5: "Major Champion: Winner of national or international flagship hackathon.",
        },
    ),
}


def build_competency_assessment(
    competency_id: str,
    raw_value: float | None,
    evidence_items: list[EvidenceItem],
    rationale: str,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluates raw score against defined rubric anchors and produces a fully explainable assessment."""
    defn = COMPETENCY_REGISTRY.get(competency_id)
    if not defn:
        return {
            "value": raw_value,
            "status": AssessmentStatus.NOT_ASSESSED.value,
            "rationale": rationale,
            "evidence": [],
            "indicators": [],
            "missing_evidence": [],
            "limitations": limitations or [],
            "evidence_coverage": 0.0,
        }

    # Determine status
    if raw_value is None or not evidence_items:
        status = AssessmentStatus.INSUFFICIENT_EVIDENCE
        rubric_level = "Level 1: Insufficient Evidence"
        coverage = 0.0
        missing = defn.observable_indicators.copy()
    else:
        # Determine rubric level from 0-100 scale
        if raw_value < 30:
            level = 1
        elif raw_value < 50:
            level = 2
        elif raw_value < 70:
            level = 3
        elif raw_value < 85:
            level = 4
        else:
            level = 5

        rubric_level = f"Level {level}: {defn.rubric_anchors.get(level, '')}"
        status = (
            AssessmentStatus.SUPPORTED
            if len(evidence_items) >= defn.min_evidence_items
            else AssessmentStatus.PARTIALLY_SUPPORTED
        )
        coverage = min(1.0, len(evidence_items) / (defn.min_evidence_items + 2))
        missing = [
            ind
            for ind in defn.observable_indicators
            if not any(ind.lower() in ev.indicator.lower() for ev in evidence_items)
        ]

    effective_limitations = list(limitations or [])
    effective_limitations.extend(defn.explicit_exclusions[:2])

    return {
        "value": round(raw_value, 1) if raw_value is not None else None,
        "status": status.value,
        "rubric_level": rubric_level,
        "indicators": [ev.indicator for ev in evidence_items],
        "evidence": [ev.source for ev in evidence_items],
        "provenance_items": [ev.to_dict() for ev in evidence_items],
        "missing_evidence": missing[:3],
        "limitations": effective_limitations,
        "evidence_coverage": round(coverage, 2),
        "rationale": rationale,
    }
