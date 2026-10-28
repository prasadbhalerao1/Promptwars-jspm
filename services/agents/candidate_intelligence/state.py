import operator
from typing import Annotated, Any, Optional, TypedDict

from packages.shared_schemas.candidates import SubScore


class CandidateProfileState(TypedDict):
    candidate_id: str
    user_id: str

    # Resume ingestion (in, then out)
    raw_resume_bytes: Optional[bytes]
    raw_resume_content_type: Optional[str]
    resume_parsed: Optional[dict]

    # GitHub ingestion (in, then out)
    github_username: Optional[str]
    github_access_token: Optional[str]  # transient, per FR-1.1 — never persisted
    github_raw: Optional[Any]  # GithubAnalysis dataclass while the graph is running

    # Certificate ingestion (in, then out)
    certificate_file_bytes: Optional[bytes]
    certificate_extracted: Optional[dict]

    # Merge output
    merged_profile: Optional[dict]
    # resume_parser, certificate_ocr, and profile_merge can each contribute conflicts in
    # the same superstep (parallel fan-out) — needs a reducer so concurrent partial
    # writes concatenate instead of colliding (langgraph's default channel only accepts
    # one write per step). Node functions must return only their OWN new entries here,
    # never the accumulated list, since the reducer does the accumulating.
    conflicts: Annotated[list[str], operator.add]

    # Scoring input — population/assessment data the router fetched via the DB session
    # it owns (nodes stay DB-free, same convention as the rest of this module).
    commit_population: list[float]
    star_population: list[float]
    leadership_population: list[float]
    contribution_population: list[float]
    assessment_score: Optional[float]
    assessment_population: list[float]

    # Hackathon data (platform-run and self-reported)
    hackathon_platform_results: Optional[list[dict]]
    hackathon_self_reported: Optional[list[dict]]

    # Scoring output
    sub_scores: dict[str, SubScore]
    overall_score: Optional[float]
    renormalized_subscores: list[str]
    confidence: Optional[Any]

    # Badge output
    badges: list[dict]


class CareerGuidanceState(TypedDict):
    """FR-4 (AI Career Guidance) — separate on-demand subgraph, not part of Flow A's
    ingestion fan-out. See `career_guidance_graph.py`'s module docstring for why."""

    candidate_id: str
    candidate_skills: list[str]
    location: Optional[str]
    years_experience_proxy: float
    talent_score: Optional[float]
    target_role: Optional[str]  # candidate-requested; None = auto-pick best-fit role
    # Small, static catalog fetched once by the API route (nodes don't touch the DB —
    # same convention as the rest of this module).
    course_catalog: list[dict]

    # skill_gap_analysis output
    resolved_target_role: Optional[str]
    skill_gaps: list[dict]
    covered_skills: list[str]

    # certification_mapping output (FR-4.2 + FR-4.5 — same catalog, filtered by gap)
    recommended_courses: list[dict]

    # career_roadmap output (FR-4.3)
    roadmap: Optional[dict]

    # salary_prediction output (FR-4.4) — range only, never a point estimate
    salary_estimate_low: Optional[int]
    salary_estimate_high: Optional[int]
    salary_rationale: Optional[str]
