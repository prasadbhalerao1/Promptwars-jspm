"""A plagiarism check that failed must not render as a clean result.

`find_and_record_matches` wrapped its whole body in `except Exception: return []`, and an
empty list means exactly one thing to every consumer: "no similarity matches found against
prior submissions." That sentence is what the reader sees.

This is not hypothetical. The function's own comment records that a
`search_batch`-removed-in-1.18 `AttributeError` was swallowed here, so "plagiarism
checking reported 'no matches' for every deck rather than surfacing the breakage." The
API call was fixed; the swallow that concealed it for as long as it did was not.

Same defect class as the GitHub-contribution bug: a failed lookup degrading into a
confident negative claim about someone's work. The fix is the same shape — make
"could not check" a distinct, disclosed state.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.agents.ppt_analyzer.tools.plagiarism import (
    PlagiarismCheckUnavailable,
    find_and_record_matches,
)

_SLIDES = [{"index": 0, "text": "Problem statement"}]
_EMBEDDINGS = [[0.1] * 8]


def test_a_backend_failure_raises_rather_than_returning_empty() -> None:
    """The distinction the whole fix rests on: broken is not the same as clean."""
    with patch(
        "services.agents.ppt_analyzer.tools.plagiarism._get_client",
        side_effect=RuntimeError("qdrant exploded"),
    ):
        with pytest.raises(PlagiarismCheckUnavailable):
            find_and_record_matches("deck-1", _SLIDES, _EMBEDDINGS)


def test_an_api_incompatibility_is_surfaced_not_swallowed() -> None:
    """The exact failure that shipped: a removed client method raising AttributeError."""

    class BrokenClient:
        def query_batch_points(self, *args, **kwargs):
            raise AttributeError("'QdrantClient' object has no attribute 'search_batch'")

    with patch(
        "services.agents.ppt_analyzer.tools.plagiarism._get_client",
        return_value=BrokenClient(),
    ):
        with pytest.raises(PlagiarismCheckUnavailable):
            find_and_record_matches("deck-1", _SLIDES, _EMBEDDINGS)


def test_no_embeddings_is_still_a_quiet_empty_result() -> None:
    """Not every empty result is a failure — a deck with no embeddable text is genuinely
    unmatchable, and must not be reported as a broken check."""
    assert find_and_record_matches("deck-1", _SLIDES, None) == []
    assert find_and_record_matches("deck-1", _SLIDES, []) == []


def test_an_unconfigured_qdrant_is_disclosed_rather_than_reported_clean() -> None:
    """A deployment without Qdrant cannot check plagiarism at all.

    Returning `[]` there produced the same false all-clear on every single deck.
    """
    with patch(
        "services.agents.ppt_analyzer.tools.plagiarism._get_client", return_value=None
    ):
        with pytest.raises(PlagiarismCheckUnavailable):
            find_and_record_matches("deck-1", _SLIDES, _EMBEDDINGS)


# --- the node must translate that into disclosed state, not a crash -------------------


async def test_node_reports_the_check_as_unavailable() -> None:
    """The graph must not die because plagiarism is down — but it must say so."""
    from services.agents.ppt_analyzer.nodes import similarity_plagiarism

    with patch(
        "services.agents.ppt_analyzer.nodes.similarity_plagiarism.find_and_record_matches",
        side_effect=PlagiarismCheckUnavailable("qdrant unreachable"),
    ):
        result = await similarity_plagiarism.run(
            {"presentation_id": "d", "slides": _SLIDES, "slide_embeddings": _EMBEDDINGS}
        )

    assert result["plagiarism_matches"] == []
    assert result["plagiarism_checked"] is False


async def test_a_successful_check_is_marked_as_checked() -> None:
    from services.agents.ppt_analyzer.nodes import similarity_plagiarism

    with patch(
        "services.agents.ppt_analyzer.nodes.similarity_plagiarism.find_and_record_matches",
        return_value=[],
    ):
        result = await similarity_plagiarism.run(
            {"presentation_id": "d", "slides": _SLIDES, "slide_embeddings": _EMBEDDINGS}
        )

    assert result["plagiarism_matches"] == []
    assert result["plagiarism_checked"] is True, (
        "a genuine clean result must be distinguishable from a failed one"
    )
