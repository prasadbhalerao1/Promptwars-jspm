"""Resume Parser Agent — doc 01 §4. Node contract: constraints.md §2.3.

Returns only the keys it changes (never the full state) — required for langgraph's
parallel fan-out (this node, github_analysis, and certificate_ocr all run in the same
superstep and write into shared channels; returning untouched keys causes
"Can receive only one value per step" errors).
"""

import asyncio

from services.agents.candidate_intelligence.state import CandidateProfileState
from services.agents.candidate_intelligence.tools.resume import (
    ResumeExtractionUnavailable,
    extract_resume_fields,
    extract_resume_text,
)


async def run(state: CandidateProfileState) -> dict:
    if not state.get("raw_resume_bytes"):
        return {}

    # pdfplumber/python-docx parsing is blocking/CPU-bound — keep it off the event loop.
    text = await asyncio.to_thread(
        extract_resume_text, state["raw_resume_bytes"], state["raw_resume_content_type"]
    )
    try:
        return {"resume_parsed": await extract_resume_fields(text)}
    except ResumeExtractionUnavailable as exc:
        return {"conflicts": [f"resume_extraction_unavailable: {exc}"]}
