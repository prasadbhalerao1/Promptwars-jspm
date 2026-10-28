"""Module 04 (PPT Analyzer) shared schemas — imported by both services/api and
services/agents/ppt_analyzer, per constraints.md §2.2 (single source of truth)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# The 4 components that roll into Overall Pitch Score (doc 08 §7). Presentation Quality
# comes from the Problem & Solution Clarity agent's rubric (structure/clarity of the
# pitch itself); Innovation and Business Potential both come from the Innovation &
# Business Impact agent; Technical Feasibility from its own agent.
PITCH_SCORE_NAMES = (
    "innovation",
    "technical_feasibility",
    "presentation_quality",
    "business_potential",
)


class RubricScore(BaseModel):
    """A single rubric-scored dimension. `value` is None when the LLM judgment call
    couldn't run (no API key, model error) — never a fabricated number (cold-start
    pattern, same as Module 01's SubScore)."""

    value: float | None  # 0-100
    rationale: str | None = None
    gaps: list[str] = []  # specific rubric gaps found — feeds FR-8 suggestions


class AIContentSignal(BaseModel):
    """FR-6 — always a signal with a confidence label and evidence, never a bare
    AI-generated yes/no verdict (doc 04 §9 hard requirement)."""

    score: float | None  # 0-100, higher = more AI-like heuristic signal
    confidence_label: str  # "low" | "medium" | "high" — confidence in the SIGNAL itself
    flagged_sections: list[str] = []  # e.g. ["slide_3", "slide_7"]
    rationale: str


class SlideOut(BaseModel):
    model_config = {"from_attributes": True}

    slide_index: int
    title: str | None
    body: str | None
    notes: str | None
    has_image: bool
    ocr_text: str | None = None


class PlagiarismMatchOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    presentation_id: UUID
    matched_presentation_id: UUID
    slide_index: int
    similarity: float
    flagged_at: datetime


class PresentationUploadResponse(BaseModel):
    presentation_id: UUID
    status: str


class PresentationStatusResponse(BaseModel):
    presentation_id: UUID
    status: str


class RequirementCoverageItem(BaseModel):
    requirement_id: str
    description: str
    status: str  # "fully_addressed" | "partially_addressed" | "unaddressed" | "unassessed"
    slides: list[int] = []
    evidence_excerpt: str | None = None
    gaps: list[str] = []
    recommendation: str | None = None


class RubricDimensionScore(BaseModel):
    score: float
    weight: float
    weighted_contribution: float
    anchors_met: str
    slide_citations: list[int] = []
    deductions: list[str] = []
    rationale: str


class PresentationReportResponse(BaseModel):
    presentation_id: UUID
    status: str
    linked_repo: str | None
    problem_statement: str | None = None
    slides: list[SlideOut]
    scores: dict[str, RubricScore]  # legacy compatibility
    rubric_breakdown: dict[str, RubricDimensionScore] = {}
    requirement_coverage: list[RequirementCoverageItem] = []
    overall_pitch_score: float | None
    renormalized_scores: list[str]
    summary: str | None
    suggestions: list[str]
    ai_content_signal: AIContentSignal | None
    plagiarism_matches: list[PlagiarismMatchOut]
    plagiarism_checked: bool = True
    computed_at: datetime | None
