"""Slide Embedding Agent — doc 04 §4. Node contract: constraints.md §2.3."""

import asyncio

from services.agents.ppt_analyzer.state import PitchAnalysisState
from services.agents.ppt_analyzer.tools.embeddings import embed_texts


def _slide_text(slide: dict) -> str:
    return " ".join(filter(None, [slide.get("title"), slide.get("body"), slide.get("notes")]))


async def run(state: PitchAnalysisState) -> dict:
    slides = state.get("slides") or []
    if not slides:
        return {"slide_embeddings": None}

    texts = [_slide_text(s) for s in slides]
    # model.encode() is CPU-bound — keep it off the event loop.
    return {"slide_embeddings": await asyncio.to_thread(embed_texts, texts)}
