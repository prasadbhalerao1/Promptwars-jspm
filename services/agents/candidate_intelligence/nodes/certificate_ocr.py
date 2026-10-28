"""Certificate OCR Agent — doc 01 §4. Node contract: constraints.md §2.3.

Returns only the keys it changes — see resume_parser.py's note on why (parallel fan-out).
"""

import asyncio
from dataclasses import asdict

from services.agents.candidate_intelligence.state import CandidateProfileState
from services.agents.candidate_intelligence.tools.certificate import extract_certificate


async def run(state: CandidateProfileState) -> dict:
    if not state.get("certificate_file_bytes"):
        return {}

    # Tesseract is blocking/CPU-bound — keep it off the event loop.
    extraction = await asyncio.to_thread(extract_certificate, state["certificate_file_bytes"])
    result: dict = {"certificate_extracted": asdict(extraction)}
    if extraction.ocr_confidence < 0.5:
        result["conflicts"] = ["certificate_low_ocr_confidence: flagged for manual review"]
    return result
