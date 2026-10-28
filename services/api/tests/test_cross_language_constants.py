"""Constants that exist in both Python and TypeScript, and must not drift.

The repo has a history here: `RESERVED_USERNAMES` lived in both languages with a comment
asking humans to keep them in sync, six names drifted out of the Python copy, and
`POST /auth/signup` with `username="admin"` returned 201. `test_reserved_usernames.py`
now pins that pair.

This module covers the remaining cross-language duplication. The preferred fix is not a
matching test but removing the duplication — having the API publish the value so there is
only one definition. Where that is done, the test asserts the publication exists; where a
literal genuinely must live in both places, it asserts the two agree.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_SRC = _REPO_ROOT / "apps" / "web" / "src"


def _read(relative: str) -> str:
    path = _WEB_SRC / relative
    assert path.exists(), f"expected {path} to exist"
    return path.read_text(encoding="utf-8")


# --- stats refresh cooldown ----------------------------------------------------------


def test_cooldown_is_configurable_on_the_backend() -> None:
    """The backend value moved to Settings in the config pass."""
    from services.api.core.config import get_settings

    assert get_settings().stats_refresh_cooldown_minutes == 15


def test_profile_response_publishes_the_cooldown() -> None:
    """The client must not have to know the cooldown to render the countdown.

    The backend cooldown is env-tunable (`STATS_REFRESH_COOLDOWN_MINUTES`), but the
    dashboard hardcoded `15 * 60 * 1000` to compute when the refresh button re-enables.
    Raising the env var therefore produced a UI that enabled the button early and an API
    that answered 429 — the drift is invisible until a deployment changes the setting.
    """
    from packages.shared_schemas.candidates import CandidateProfileResponse

    assert "stats_refresh_cooldown_seconds" in CandidateProfileResponse.model_fields


def test_dashboard_does_not_hardcode_the_cooldown() -> None:
    source = _read("components/CandidateDashboard.tsx")
    # Strip comments: the explanatory comment legitimately names the old literal.
    code = re.sub(r"/\*[\s\S]*?\*/", "", source)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.MULTILINE)

    assert "15 * 60 * 1000" not in code, "cooldown must come from the API, not a literal"
    assert "stats_refresh_cooldown_seconds" in code


# --- sparse profile threshold --------------------------------------------------------


def test_sparse_profile_threshold_is_not_claimed_to_mirror_the_backend() -> None:
    """There is no backend threshold to mirror — the claim was false.

    `ScoreDisplay.tsx` documented 0.5 as mirroring "the backend threshold documented on
    `EvidenceConfidence`". That backend threshold is a sentence of English prose in a
    docstring ("below the 50% confidence threshold"), enforced by no Python code. So the
    TypeScript constant is the only real definition, and the comment invited a future
    reader to go "sync" it with something that does not exist.
    """
    source = _read("components/common/ScoreDisplay.tsx")
    assert "SPARSE_PROFILE_THRESHOLD = 0.5" in source
    assert "Mirrors the backend threshold" not in source, (
        "the comment asserts a backend constant that does not exist"
    )
