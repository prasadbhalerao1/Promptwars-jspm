from typing import Optional, TypedDict


class VerificationState(TypedDict):
    """Flow A — skill verification (doc 03 §4), one `ainvoke()` per submission."""

    assessment_type: str  # coding | mcq | project_analysis
    spec: dict
    code_or_answers: dict
    test_results: list[dict]  # [{test_name, passed}] as reported by the client

    # static_analysis output
    static_analysis: dict  # {tool: {summary, details}}

    # grading output
    tests_passed: int
    tests_total: int
    grading_rationale: Optional[str]

    # llm_code_review output
    llm_review: Optional[dict]  # {readability, architecture, red_flags, rationale}

    # verification_report output
    score: Optional[float]


class InterviewState(TypedDict):
    """Flow B — AI interview (doc 03 §4), one `ainvoke()` per turn. `topic_plan`/
    `current_topic_idx`/`transcript`/`per_topic_scores`/`follow_up_count_this_topic` are
    loaded from `interview_sessions.state` before each call and re-saved after — no
    LangGraph checkpointer anywhere in this codebase (same convention as Module 02's
    Copilot)."""

    session_id: str
    candidate_id: str
    # "start" = first call, no answer to evaluate yet, just ask topic_plan[0]. "turn" =
    # `transcript` already has the candidate's newest answer appended; evaluate it first.
    mode: str
    candidate_profile_summary: str  # headline/skills, for question personalization
    job_context: Optional[dict]
    topic_plan: list[str]
    current_topic_idx: int
    transcript: list[dict]  # [{role, text}], full history so far (this turn's answer already appended)
    per_topic_scores: dict[str, float]
    follow_up_count_this_topic: int

    # question node output (only set when generating a NEW question, not evaluating an answer)
    next_question: Optional[str]
    interview_status: str  # in_progress | completed

    # turn_evaluation output
    last_answer_verdict: Optional[str]  # weak | sufficient


class InterviewReportState(TypedDict):
    """Separate on-demand subgraph — same pattern as Module 01's career_guidance_graph
    being separate from the main ingestion fan-out."""

    transcript: list[dict]
    per_topic_scores: dict[str, float]
    topic_plan: list[str]

    response_confidence_signal: Optional[float]
    technical_rating: Optional[float]
    communication_rating: Optional[float]
    hiring_recommendation: Optional[str]


class DefinitionQuestionState(TypedDict):
    """On-demand subgraph for drafting interview topics from role/JD/years-exp context."""

    role_title: str
    job_description: str
    years_experience: Optional[int]
    question_count: int
    topics: list[str]


class ContributionState(TypedDict):
    """Flow C — team contribution analytics (doc 03 §4), batch job over a shared repo."""

    repo_full_name: str
    github_usernames: list[str]
    access_token: Optional[str]

    # commit_attribution output
    raw_stats: dict  # username -> {commits, lines_survived, prs_opened, prs_reviewed}

    # contribution_weighting output
    shares: dict  # username -> 0-1
    narratives: dict  # username -> short narrative string

    # contribution_report output
    results: list[dict]  # [{github_username, contribution_share, commits, ..., anomaly_note}]
