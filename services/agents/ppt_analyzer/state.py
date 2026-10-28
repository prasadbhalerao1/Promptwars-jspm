from typing import Any, Optional, TypedDict


class PitchAnalysisState(TypedDict):
    """Doc 04 §4's `PitchAnalysisState` sketch, extended for this repo's node contract
    (constraints.md §2.3 — every parallel node returns ONLY the keys it changes).

    Every node fanning out from `content_extraction` writes to a DISTINCT top-level key
    (mirrors services/agents/candidate_intelligence/state.py's resume_parsed /
    github_raw / certificate_extracted split) so no two nodes in the same superstep ever
    write the same channel — the exact bug documented in
    .agents/decisions.md's "LangGraph parallel fan-out" entry.
    """

    presentation_id: str

    # Format normalization / content extraction (in, then out)
    file_bytes: Optional[bytes]
    file_name: Optional[str]
    file_content_type: Optional[str]
    linked_repo: Optional[str]
    problem_statement: Optional[str]
    requirement_coverage: Optional[list[dict]]
    rubric_breakdown: Optional[dict]

    normalized_pptx_bytes: Optional[bytes]  # set only if a .ppt -> .pptx conversion ran
    normalization_error: Optional[str]  # e.g. LibreOffice not available — degrade, don't crash

    slides: list[dict]  # {index, title, body, notes, has_image}
    # Transient only (not persisted verbatim) — raw per-slide image bytes for the OCR
    # node to consume. Keyed by slide index since a dict channel needs one writer.
    slide_images: dict[int, list[bytes]]
    extraction_error: Optional[str]

    # Slide Image/OCR Agent output
    slide_ocr_notes: list[dict]  # {index, ocr_text, diagram_summary}

    # Slide Embedding Agent output
    slide_embeddings: Optional[list[list[float]]]

    # Similarity/Plagiarism Agent output
    plagiarism_matches: list[dict]  # [{matched_presentation_id, slide_idx, similarity}]
    # False when the check could not run at all. An empty `plagiarism_matches` alone is
    # ambiguous — it reads to the user as "nothing matched", which is a positive claim
    # this flag prevents us from making when we simply do not know.
    plagiarism_checked: bool

    # Problem & Solution Clarity Agent output -> becomes "presentation_quality" score
    presentation_quality: Optional[dict]  # {value, rationale, gaps}

    # Innovation & Business Impact Agent output -> two scores at once
    innovation_business: Optional[dict]  # {innovation: {...}, business_potential: {...}}

    # Technical Feasibility Agent output
    technical_feasibility: Optional[dict]  # {value, rationale, gaps}

    # AI-Content Heuristic Agent output — never a bare boolean (FR-6)
    ai_content_signal: Optional[dict]  # {score, confidence_label, flagged_sections, rationale}

    # Aggregation Agent output
    scores: dict[str, Any]  # {innovation, technical_feasibility, presentation_quality, business_potential}
    overall_score: Optional[float]
    renormalized_scores: list[str]

    # Summary & Suggestions Agent output
    summary: Optional[str]
    suggestions: list[str]
