"""Format Normalization Agent — doc 04 §4. Node contract: constraints.md §2.3.

Detects the uploaded format and converts legacy `.ppt` to `.pptx` up front so
`content_extraction` only ever has to deal with `.pptx`/`.pdf`. Degrades (sets
`normalization_error`, leaves `normalized_pptx_bytes` unset) instead of raising when
LibreOffice isn't available — the graph still runs to completion with an empty/partial
extraction rather than a hard failure on the whole upload.
"""

import asyncio

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.extraction import (
    LegacyPptConversionUnavailable,
    UnsupportedDeckFormat,
    convert_ppt_to_pptx,
    detect_format,
)


async def run(state: PitchAnalysisState) -> dict:
    from services.api.core.config import get_settings

    file_bytes = state.get("file_bytes")
    if not file_bytes:
        return {"normalization_error": "No file bytes provided."}

    try:
        fmt = detect_format(state.get("file_name"), state.get("file_content_type"))
    except UnsupportedDeckFormat as exc:
        return {"normalization_error": str(exc)}

    if fmt != "ppt":
        return {}  # .pptx and .pdf pass straight through to content_extraction

    settings = get_settings()
    try:
        # Spawns headless LibreOffice (up to a 60s subprocess) — keep it off the event loop.
        converted = await asyncio.to_thread(
            convert_ppt_to_pptx, file_bytes, settings.libreoffice_binary
        )
        return {"normalized_pptx_bytes": converted}
    except LegacyPptConversionUnavailable as exc:
        return {"normalization_error": str(exc)}
