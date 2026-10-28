"""The reserved-handle list is duplicated across the language boundary; this keeps it honest.

`RESERVED_USERNAMES` (apps/web/src/lib/constants.ts) and `_RESERVED_USERNAMES`
(services/api/modules/candidates/router.py) have to agree. They cannot literally share a
definition — one is TypeScript shipped to the browser, the other Python — so the only
thing preventing drift is a check like this one.

Drift is not cosmetic. The client list is a courtesy that fails fast in the signup form;
the server list is the actual enforcement, because the API is reachable directly. When six
names ("home", "admin", "recruiter", "organizer", "judge", "settings") were added to the
client only, `POST /auth/signup` with `username="admin"` returned 201 and a candidate
could claim `/admin` as their public portfolio handle.

Parsing the .ts file with a regex rather than importing it is deliberate: it needs no node
toolchain in the Python test run, and the list is a flat array of string literals whose
shape is asserted below (a non-trivial edit that breaks parsing fails the test loudly
instead of silently matching nothing).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.api.modules.candidates.router import (
    _RESERVED_USERNAMES,
    _USERNAME_PATTERN,
)

_CONSTANTS_TS = (
    Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "lib" / "constants.ts"
)


def _frontend_literals(source: str, declaration: str) -> set[str]:
    """Extract the string literals from a `new Set([...])` declaration."""
    block = re.search(
        rf"{declaration}\s*=\s*new Set\(\[(.*?)\]\)", source, re.S
    )
    assert block, f"could not find `{declaration} = new Set([...])` in constants.ts"
    return set(re.findall(r'"([^"]+)"', block.group(1)))


@pytest.fixture(scope="module")
def constants_source() -> str:
    assert _CONSTANTS_TS.is_file(), f"missing {_CONSTANTS_TS}"
    return _CONSTANTS_TS.read_text(encoding="utf-8")


def test_reserved_usernames_match_frontend(constants_source: str) -> None:
    frontend = _frontend_literals(constants_source, "RESERVED_USERNAMES")

    # Guards the regex above: if the declaration is reformatted into something this
    # cannot parse, an empty set would otherwise "match" a backend that is also empty.
    assert len(frontend) > 20, "parsed suspiciously few names; check the regex"

    client_only = frontend - _RESERVED_USERNAMES
    server_only = _RESERVED_USERNAMES - frontend

    assert not client_only, (
        "these handles are blocked in the browser but accepted by the API, so they can "
        f"be claimed by calling it directly: {sorted(client_only)}"
    )
    assert not server_only, (
        "these handles are rejected by the API but offered as valid in the signup form, "
        f"so the user only finds out after submitting: {sorted(server_only)}"
    )


def test_username_pattern_matches_frontend(constants_source: str) -> None:
    """The two regexes are written in different dialects but must accept the same handles."""
    declared = re.search(
        r"USERNAME_PATTERN\s*=\s*/(.+?)/[a-z]*\s*;", constants_source
    )
    assert declared, "could not find USERNAME_PATTERN in constants.ts"
    assert declared.group(1) == _USERNAME_PATTERN.pattern, (
        "frontend and backend username patterns differ:\n"
        f"  frontend: {declared.group(1)}\n"
        f"  backend:  {_USERNAME_PATTERN.pattern}"
    )


@pytest.mark.parametrize("handle", ["admin", "home", "judge", "recruiter", "organizer", "settings"])
def test_role_and_route_handles_are_reserved(handle: str) -> None:
    """Regression test for the specific gap found: role names and `/home` were claimable.

    These are called out separately from the sync test because they are the ones with
    real consequences — a portfolio served at `/admin` reads as an official page, and a
    handle matching a route shadows it.
    """
    assert handle in _RESERVED_USERNAMES
