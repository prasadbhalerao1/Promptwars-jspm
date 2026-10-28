"""Constants shared across modules that must not be allowed to drift apart.

Each value here previously existed as two or more independent literals. That is not a
style complaint: every duplication in this file had a comment somewhere asking a human
to keep the copies in sync, and at least one such pair had already drifted in this
repository with real consequences (the reserved-username list, where six names existed
only on the client and `POST /auth/signup` with `username="admin"` returned 201).

Values that belong to a single module stay in that module. Values that are genuinely
deployment-tunable belong in `core/config.py` Settings instead — these are the ones that
are structural rather than tunable, where two call sites disagreeing is simply a bug.
"""

from __future__ import annotations

# Ceiling applied by every paginated list endpoint, so a client cannot request an
# unbounded page by passing a huge `limit`. Was written inline as
# `max(1, min(limit, 500))` in two routers, one of which carried a comment noting it was
# copying the other.
MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 100

# How much of an exception message is persisted to a `*_error` column. Copy-pasted as
# `str(exc)[:2000]` at six sites across five routers.
ERROR_TRUNCATE_CHARS = 2000

# Score at or above which a slide/section is flagged as likely AI-generated. Shared by
# the PPT analyzer and the fraud module, which are documented as deliberately using the
# *same* method so their verdicts cannot diverge — yet each re-declared this cutoff, and
# the frontend badge hardcoded a third copy.
AI_CONTENT_FLAG_THRESHOLD = 70.0


def clamp_page_size(limit: int, *, maximum: int = MAX_PAGE_SIZE) -> int:
    """Clamp a caller-supplied page size into `[1, maximum]`."""
    return max(1, min(limit, maximum))


def truncate_error(exc: BaseException | str, *, limit: int = ERROR_TRUNCATE_CHARS) -> str:
    """Render an exception for storage in a bounded `*_error` column.

    Bounded because these columns are surfaced to users and, more importantly, because
    an unbounded provider traceback in a JSONB/Text column is a slow way to fill a
    database with noise nobody reads past the first line of.
    """
    return str(exc)[:limit]
