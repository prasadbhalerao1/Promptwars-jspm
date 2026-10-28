"""Slide Image/OCR Agent — doc 04 §4. Node contract: constraints.md §2.3.

Runs off content_extraction in parallel with slide_embedding/problem_solution_clarity/
innovation_business_impact/ai_content_heuristic — returns only `slide_ocr_notes`.
"""

import asyncio

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.ocr import ocr_image_async, vision_diagram_summary
from services.api.core.config import get_settings

# Bounds concurrent slide processing: a large deck would otherwise fire N Tesseract
# threads and N Claude-vision calls at once, exhausting the threadpool / hitting rate limits.
_MAX_CONCURRENT_SLIDES = get_settings().agent_max_concurrency


async def _process_slide(index: int, images: list, semaphore: asyncio.Semaphore) -> dict | None:
    async with semaphore:
        # OCR every image on the slide, plus one vision pass on the first image, all
        # concurrently — they're independent network/CPU calls.
        ocr_results, diagram_summary = await asyncio.gather(
            asyncio.gather(*(ocr_image_async(img) for img in images)),
            vision_diagram_summary(images[0]) if images else _none(),
        )

    ocr_texts = [t for t in ocr_results if t]
    if not ocr_texts and not diagram_summary:
        return None
    return {
        "index": index,
        "ocr_text": " ".join(ocr_texts) or None,
        "diagram_summary": diagram_summary,
    }


async def _none() -> None:
    return None


async def run(state: PitchAnalysisState) -> dict:
    slide_images: dict[int, list] = state.get("slide_images") or {}
    if not slide_images:
        return {"slide_ocr_notes": []}

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_SLIDES)
    results = await asyncio.gather(
        *(_process_slide(index, images, semaphore) for index, images in slide_images.items())
    )

    # Preserve deterministic slide order — gather returns results in argument order.
    return {"slide_ocr_notes": [note for note in results if note is not None]}
