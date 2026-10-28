"""State for Flow B — on-demand resume/cover-letter builder (doc 01 §3/§4, FR-5).

Separate TypedDict + separate compiled graph from `state.py`/`graph.py`'s Flow A
(ingestion & scoring): FR-5 generation is triggered per-request from the API, not part
of the FR-1 ingestion fan-out, and its own request loop (generate -> fact-check ->
retry-or-deliver) has nothing to do with Flow A's parallel-branch shape. Kept in this
same module per the task's ownership split (FR-5 is still Module 1 / Candidate
Intelligence), just a distinct subgraph — see `resume_graph.py`.
"""

from typing import Optional, TypedDict


class DocumentBuilderState(TypedDict):
    candidate_id: str
    document_type: str  # "resume" | "cover_letter"
    # Snapshot of candidate_profiles at request time — the ONLY source of truth the
    # generator and fact-checker are allowed to draw facts from (FR-5.4 grounding).
    merged_profile: dict
    target_job_description: Optional[str]

    generated_content: Optional[dict]
    # Set only when the generator tool itself couldn't run (e.g. no ANTHROPIC_API_KEY) —
    # routes straight to END, skipping fact-check since there's nothing to check.
    generation_error: Optional[str]

    fact_check_status: Optional[str]  # "passed" | "failed"
    fact_check_findings: Optional[list[dict]]

    attempts: int
