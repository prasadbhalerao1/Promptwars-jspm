"""Content Extraction Agent — doc 04 §4. Node contract: constraints.md §2.3.

Runs after format_normalization. Extracts per-slide title/body/notes/images (FR-2) via
python-pptx or PyMuPDF depending on format. Image bytes are kept only transiently in
`slide_images` (keyed by slide index) for the OCR node to consume in this same graph
run — they are never persisted to the `slides` table (only a `has_image` flag + any
resulting OCR text are).
"""

import asyncio

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.extraction import (
    UnsupportedDeckFormat,
    detect_format,
    extract_slides_from_pdf,
    extract_slides_from_pptx,
)


async def run(state: PitchAnalysisState) -> dict:
    if state.get("normalization_error"):
        return {"extraction_error": state["normalization_error"], "slides": []}

    file_bytes = state.get("file_bytes")
    if not file_bytes:
        return {"extraction_error": "No file bytes provided.", "slides": []}

    # python-pptx / PyMuPDF parsing is blocking CPU work — keep it off the event loop.
    normalized = state.get("normalized_pptx_bytes")
    if normalized:
        extracted = await asyncio.to_thread(extract_slides_from_pptx, normalized)
    else:
        try:
            fmt = detect_format(state.get("file_name"), state.get("file_content_type"))
        except UnsupportedDeckFormat as exc:
            return {"extraction_error": str(exc), "slides": []}

        try:
            if fmt == "pptx":
                extracted = await asyncio.to_thread(extract_slides_from_pptx, file_bytes)
            elif fmt == "pdf":
                extracted = await asyncio.to_thread(extract_slides_from_pdf, file_bytes)
            else:
                return {"extraction_error": f"Unhandled format at extraction time: {fmt}", "slides": []}
        except Exception as exc:  # malformed/corrupt file — degrade, don't crash the graph
            return {"extraction_error": f"Failed to parse deck: {exc}", "slides": []}

    slides = [
        {"index": s.index, "title": s.title, "body": s.body, "notes": s.notes, "has_image": s.has_image}
        for s in extracted
    ]
    slide_images = {s.index: s.image_bytes for s in extracted if s.image_bytes}

    return {"slides": slides, "slide_images": slide_images}
