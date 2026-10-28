"""Signup must not let a visitor assign themselves a privileged role.

`SignupRequest.role` was the full `Role` enum, taken from the request body straight into
`User(role=...)`. Since `Role` includes `admin`, `POST /auth/signup` with
`{"role": "admin"}` returned 201 and a token that opened `/admin/users` (role
reassignment for every account), `/admin/audit-log` and the trusted-issuer registry —
making every `require_role` check in the codebase gate on a role the caller chose. The
sign-up form offered "Admin" in its dropdown outright.

The enum is the enforcement point, so these assert on the enum rather than on any one
route: a future route that accepts a `SignupRequest` inherits the restriction.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.shared_schemas.users import Role, SignupRequest, SignupRole

_CONSTANTS_TS = (
    Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "lib" / "constants.ts"
)

_PRIVILEGED = {"admin", "organizer", "judge"}


def test_self_assignable_roles_exclude_privileged() -> None:
    assert {r.value for r in SignupRole} == {"candidate", "recruiter"}
    assert not ({r.value for r in SignupRole} & _PRIVILEGED)


@pytest.mark.parametrize("role", sorted(_PRIVILEGED))
def test_signup_rejects_privileged_role(role: str) -> None:
    with pytest.raises(ValidationError):
        SignupRequest(email="a@b.com", password="pw", role=role)


@pytest.mark.parametrize("role", ["candidate", "recruiter"])
def test_signup_accepts_public_roles(role: str) -> None:
    assert SignupRequest(email="a@b.com", password="pw", role=role).role.value == role


def test_privileged_roles_still_exist_for_admin_assignment() -> None:
    """They are not self-assignable, but must remain assignable by an admin."""
    assert _PRIVILEGED <= {r.value for r in Role}


def test_signup_roles_match_frontend() -> None:
    """The form must not offer a role the API will reject.

    Same cross-language drift guard as test_reserved_usernames.py: the TS list is what
    renders the dropdown, the Python enum is what enforces. When they disagreed, the
    dropdown offered Admin.
    """
    source = _CONSTANTS_TS.read_text(encoding="utf-8")
    block = re.search(r"SIGNUP_ROLES:\s*readonly Role\[\]\s*=\s*\[(.*?)\]", source, re.S)
    assert block, "could not find `SIGNUP_ROLES: readonly Role[] = [...]` in constants.ts"
    frontend = set(re.findall(r'"([^"]+)"', block.group(1)))

    assert frontend, "parsed no roles; check the regex"
    assert frontend == {r.value for r in SignupRole}
