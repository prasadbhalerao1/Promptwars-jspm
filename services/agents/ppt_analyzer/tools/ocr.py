"""Slide Image/OCR Agent — doc 04 §4. Tesseract for literal text-in-image OCR (always
attempted, mechanical baseline, mirrors candidate_intelligence's certificate OCR); Claude
vision for *diagram/architecture understanding* only when `ANTHROPIC_API_KEY` is
configured — an enhancement, not a hard requirement, since FR-2's text extraction is
already satisfied by python-pptx/PyMuPDF. Both degrade to `None` on failure rather than
raising and aborting the whole graph run — OCR is best-effort augmentation here, unlike
the Anthropic/Cloudinary integrations the task calls out as needing a hard typed error.
"""

import asyncio
import base64
import io
from functools import lru_cache

import anthropic
import pytesseract
from PIL import Image

from services.api.core.config import get_settings
from services.api.core.tracing import start_llm_generation


@lru_cache(maxsize=1)
def _vision_client(api_key: str) -> anthropic.Anthropic:
    """Cached client — rebuilding the SDK client per slide is pure overhead."""
    return anthropic.Anthropic(api_key=api_key)

_VISION_DIAGRAM_SCHEMA = {
    "name": "diagram_understanding",
    "description": "Summarize what a slide's diagram/chart/architecture image communicates.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "1-2 sentence description of what the image shows"},
        },
        "required": ["summary"],
    },
}


def ocr_image(image_bytes: bytes) -> str | None:
    """Synchronous/CPU-bound — call via `ocr_image_async` from async code."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image).strip()
        return text or None
    except Exception:
        # Covers pytesseract.TesseractNotFoundError (binary missing on this host) and
        # any malformed-image error — best-effort signal, never a hard failure.
        return None


async def ocr_image_async(image_bytes: bytes) -> str | None:
    """Threaded wrapper so Tesseract doesn't block the event loop."""
    return await asyncio.to_thread(ocr_image, image_bytes)


async def vision_diagram_summary(image_bytes: bytes) -> str | None:
    """Claude-vision diagram understanding. Best-effort: returns None on any failure.

    The provider SDK is synchronous, so the network call runs via `asyncio.to_thread`
    to keep it off the event loop. This deliberately keeps its own Anthropic client
    rather than routing through `services.api.core.llm`: that gateway is
    provider-agnostic and has no vision/image content-block support, and this path is
    gated on `ANTHROPIC_API_KEY` independently of `LLM_PROVIDER` (which is often set to
    a text-only provider like Groq) so diagram understanding still works there.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    client = _vision_client(settings.anthropic_api_key)
    try:
        with start_llm_generation(
            name="ppt_analyzer.ocr.vision_diagram_summary",
            model=settings.llm_model_fast,
            input_data={"note": "slide image, diagram/chart/architecture understanding"},
        ) as generation:
            response = await asyncio.to_thread(
                client.messages.create,
                model=settings.llm_model_fast,
                max_tokens=256,
                tools=[_VISION_DIAGRAM_SCHEMA],
                tool_choice={"type": "tool", "name": "diagram_understanding"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64.b64encode(image_bytes).decode("ascii"),
                                },
                            },
                            {
                                "type": "text",
                                "text": "If this is a diagram, chart, or architecture image, summarize what it communicates.",
                            },
                        ],
                    }
                ],
            )
            for block in response.content:
                if block.type == "tool_use":
                    summary = block.input.get("summary")
                    generation.update(output=summary)
                    return summary
            generation.update(output=None)
    except anthropic.APIError:
        return None
    return None
